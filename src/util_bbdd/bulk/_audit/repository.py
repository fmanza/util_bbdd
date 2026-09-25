"""Capa repository de auditoría: persistencia CSV y caché."""

from __future__ import annotations

import csv
import logging
import threading

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import TextIO

import pandas as pd

from .errors import AuditConfigError, AuditDataError, AuditFileError
from .record import AuditRecord

_ERR_NO_CSV_PATH = "❌ 'audit_csv_path' no está establecido."

# Locks por-ruta compartidos a nivel de proceso. Permiten que múltiples instancias
# AuditManager/AuditCsvRepository (p.ej. una BulkCrud por hilo en el volcado paralelo)
# que apuntan al MISMO fichero CSV serialicen sus escrituras, evitando filas
# intercaladas y cabeceras duplicadas. El alcance es intra-proceso (hilos): no
# coordina escrituras entre procesos distintos.
_FILE_LOCKS: dict[str, threading.Lock] = {}
_FILE_LOCKS_GUARD = threading.Lock()


def _get_file_lock(path: Path) -> threading.Lock:
    """Devuelve el lock compartido para ``path`` (creándolo si no existe).

    La clave se normaliza con ``resolve()`` para que rutas relativa y absoluta al
    mismo fichero compartan el mismo lock.
    """
    key = str(path.resolve())
    with _FILE_LOCKS_GUARD:
        lock = _FILE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _FILE_LOCKS[key] = lock
        return lock


class AuditCsvRepository:
    """Gestiona almacenamiento CSV de auditoría y caché de lecturas."""

    def __init__(
        self,
        *,
        audit_csv_path: Path | None,
        columnas_auditoria: list[str],
        logger: logging.Logger,
        cache_enabled: bool = True,
        cache_ttl_seconds: int = 300,
    ) -> None:
        self.audit_csv_path: Path | None = audit_csv_path
        self.columnas_auditoria: list[str] = columnas_auditoria
        self.logger: logging.Logger = logger
        self.cache_enabled: bool = cache_enabled
        self.cache_ttl_seconds: int = cache_ttl_seconds
        self._cache_df: pd.DataFrame | None = None
        self._cache_timestamp: datetime | None = None
        # H6 (audit-code 2026-09-25): (st_mtime_ns, st_size) del CSV al cachear; si cambia, otra instancia escribió.
        self._cache_firma: tuple[int, int] | None = None
        # QW-2 (audit-code de AuditManager 2026-09-25): el lock de la ruta se resuelve una vez y se reutiliza mientras
        # audit_csv_path no cambie. Path.resolve() costaba ~70 µs por escritura en Windows.
        self._lock_path: Path | None = None
        self._lock: threading.Lock | None = None

        if self.audit_csv_path is not None:
            self.validar_ruta(self.audit_csv_path)

    def validar_ruta(self, ruta: Path) -> None:
        """Valida que la ruta de auditoría sea accesible."""
        try:
            ruta.parent.mkdir(parents=True, exist_ok=True)
        except Exception as error:
            raise ValueError(f"❌ No se puede acceder a la ruta de auditoría: {error}") from error

    def registrar_operacion(
        self,
        *,
        tabla: str,
        motor: str,
        operacion: str,
        rowcount: int,
        elapsed: float,
        genero_sql: bool = False,
    ) -> None:
        """Persistencia principal para una operación de auditoría."""
        if self.audit_csv_path is None:
            raise AuditConfigError(_ERR_NO_CSV_PATH)

        self.auditar_lote_csv(
            tabla=tabla,
            motor=motor,
            operacion=operacion,
            rowcount=rowcount,
            elapsed=elapsed,
            genero_sql=genero_sql,
        )
        self.invalidar_cache()

    def auditar_lote_csv(
        self,
        *,
        tabla: str,
        motor: str,
        operacion: str,
        rowcount: int,
        elapsed: float,
        genero_sql: bool = False,
    ) -> None:
        """Escribe una fila de auditoría en el CSV configurado (self.audit_csv_path)."""
        self.escribir_registros(
            [
                AuditRecord(
                    tabla=tabla,
                    motor=motor,
                    operacion=operacion,
                    rowcount=rowcount,
                    elapsed=elapsed,
                    genero_sql=genero_sql,
                )
            ]
        )

    def registrar_operaciones(self, registros: Sequence[AuditRecord]) -> None:
        """Persiste varias operaciones con una sola apertura del CSV (auditoría diferida de ``bulk_session``)."""
        self.escribir_registros(registros)
        self.invalidar_cache()

    def escribir_registros(self, registros: Sequence[AuditRecord]) -> None:
        """Añade ``registros`` al CSV configurado, escribiendo antes la cabecera si el fichero está vacío."""
        if self.audit_csv_path is None:
            raise AuditConfigError(_ERR_NO_CSV_PATH)
        if not registros:
            return

        # Sección crítica: existencia → cabecera → fila debe ser atómica frente a otros
        # hilos que escriban el mismo CSV (volcado paralelo con una BulkCrud por hilo).
        with self._file_lock(self.audit_csv_path):
            with self._open_for_append(self.audit_csv_path) as file_handle:
                writer = csv.writer(file_handle, delimiter="\t")
                # H4 (audit-code 2026-09-25): en modo "a" el fichero se abre al final; posición 0 = nuevo o vacío.
                # Con exists(), un CSV de 0 bytes se quedaba sin cabecera y su primera fila de datos pasaba a serlo.
                if file_handle.tell() == 0:
                    writer.writerow(self.columnas_auditoria)

                writer.writerows(
                    [
                        registro.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        registro.tabla,
                        registro.motor,
                        registro.operacion,
                        registro.rowcount,
                        f"{registro.elapsed:.3f}".replace(".", ","),
                        "Sí" if registro.genero_sql else "No",
                    ]
                    for registro in registros
                )

    def _file_lock(self, path: Path) -> threading.Lock:
        """Lock compartido de ``path``, cacheado mientras la ruta no cambie."""
        if self._lock is None or path != self._lock_path:
            self._lock = _get_file_lock(path)
            self._lock_path = path
        return self._lock

    @staticmethod
    def _open_for_append(path: Path) -> TextIO:
        """Abre ``path`` para añadir; si su directorio no existe (p.ej. se borró a mitad de carga), lo crea y reintenta.

        QW-2: sustituye al ``mkdir(parents=True, exist_ok=True)`` que se hacía en cada escritura (~60 µs en Windows).
        """
        try:
            return open(path, "a", newline="", encoding="utf-8")
        except FileNotFoundError:
            path.parent.mkdir(parents=True, exist_ok=True)
            return open(path, "a", newline="", encoding="utf-8")

    def leer_auditoria(self, usar_cache: bool = True) -> pd.DataFrame:
        """Lee el CSV de auditoría con soporte de caché temporal."""
        if usar_cache and self.cache_enabled and self.es_cache_valido() and self._cache_df is not None:
            self.logger.debug("📦 Usando caché para lectura de auditoría")
            return self._cache_df.copy()

        if self.audit_csv_path is None:
            raise AuditConfigError(_ERR_NO_CSV_PATH)
        if not self.audit_csv_path.exists():
            raise AuditFileError(f"❌ Archivo de auditoría no encontrado: {self.audit_csv_path}")

        # La firma se toma antes de leer: una escritura durante la lectura la cambia y fuerza releer la próxima vez.
        firma: tuple[int, int] | None = self._firma_fichero()
        try:
            dataframe: pd.DataFrame = pd.read_csv(str(self.audit_csv_path), delimiter="\t")
            if "timestamp" in dataframe.columns:
                dataframe["timestamp"] = pd.to_datetime(dataframe["timestamp"], format="mixed")
            if "tiempo_seg" in dataframe.columns:
                dataframe["tiempo_seg"] = pd.to_numeric(
                    dataframe["tiempo_seg"].astype(str).str.replace(",", ".", regex=False),
                    errors="coerce",
                )

            if self.cache_enabled:
                self._cache_df = dataframe.copy()
                self._cache_timestamp = datetime.now()
                self._cache_firma = firma
                self.logger.debug(f"💾 Caché actualizado ({len(dataframe)} filas)")

            return dataframe
        except Exception as error:
            raise AuditDataError(f"❌ Error al leer el archivo CSV de auditoría: {error}") from error

    def es_cache_valido(self) -> bool:
        """Indica si el caché actual sigue siendo válido: dentro del TTL y con el CSV sin cambios desde que se leyó."""
        if self._cache_df is None or self._cache_timestamp is None:
            return False
        elapsed_seconds: float = (datetime.now() - self._cache_timestamp).total_seconds()
        if elapsed_seconds >= self.cache_ttl_seconds:
            return False
        # H6: el TTL no basta; otras instancias pueden haber escrito en el mismo CSV.
        return self._cache_firma is not None and self._firma_fichero() == self._cache_firma

    def _firma_fichero(self) -> tuple[int, int] | None:
        """``(st_mtime_ns, st_size)`` del CSV, o ``None`` si no hay ruta o el fichero no existe."""
        if self.audit_csv_path is None:
            return None
        try:
            stat = self.audit_csv_path.stat()
        except OSError:
            return None
        return stat.st_mtime_ns, stat.st_size

    def limpiar_cache(self) -> None:
        """Limpia el contenido del caché."""
        self._cache_df = None
        self._cache_timestamp = None
        self._cache_firma = None
        self.logger.debug("🧹 Caché limpiado")

    def invalidar_cache(self) -> None:
        """Alias de limpieza de caché para mantener contrato interno."""
        self.limpiar_cache()


__all__: list[str] = ["AuditCsvRepository"]
