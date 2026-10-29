"""CSV de auditoría de ``bulk``: registro, validación, escritura y lectura con caché. **Formato congelado.**

Movido desde ``util_bbdd.bulk._audit`` (``record.py`` y ``repository.py``) en la sesión 2026-10-02c sin cambios de
comportamiento; ``bulk/_audit/record.py`` y ``bulk/_audit/repository.py`` lo re-exportan.

Formato (lo fija ``tests/unit/audit/test_legacy_format.py`` byte a byte contra un fichero de v0.28.0): UTF-8, separador
tabulador, fin de línea ``\\r\\n`` (módulo ``csv``), 7 columnas ``timestamp, tabla, motor, operacion, total_filas,
tiempo_seg, sql``; ``timestamp`` ``%Y-%m-%d %H:%M:%S`` (hora local, truncada al segundo); ``tiempo_seg`` con coma
decimal y 3 decimales; ``sql`` = ``Sí``/``No``. Cualquier mejora del formato va a un destino nuevo
(:class:`~util_bbdd.audit.sinks.JsonLinesAuditSink`), nunca aquí.
"""

from __future__ import annotations

import csv
import io
import logging
import threading

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TextIO

import pandas as pd

from .._core.exceptions import AuditConfigError, AuditDataError, AuditFileError, AuditValidationError
from .files import AuditFiles
from .locks import path_lock

# Operaciones que admite el CSV de auditoría.
AUDIT_OPERATIONS: tuple[str, ...] = ("INSERT", "UPDATE", "DELETE")

#: Columnas del CSV, en orden.
AUDIT_COLUMNS: tuple[str, ...] = ("timestamp", "tabla", "motor", "operacion", "total_filas", "tiempo_seg", "sql")

_ERR_NO_CSV_PATH = "❌ 'audit_csv_path' no está establecido."


@dataclass(frozen=True, slots=True)
class AuditRecord:
    """Una fila del CSV de auditoría.

    ``timestamp`` es el momento en que terminó la operación, no el de la escritura: dentro de ``BulkCrud.bulk_session``
    la fila se escribe al confirmarse la transacción, que puede ser bastante después.
    """

    tabla: str
    motor: str
    operacion: str
    rowcount: int
    elapsed: float
    genero_sql: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


class AuditRecordValidator:
    """Validación de los campos de un registro antes de escribirlo (mensajes y excepción de siempre)."""

    @staticmethod
    def validate(tabla: str, motor: str, operacion: str, rowcount: int, elapsed: float) -> None:
        """Lanza :class:`AuditValidationError` si algún campo no es válido."""
        if not tabla or not str(tabla).strip():
            raise AuditValidationError("❌ 'tabla' no puede estar vacío")
        if not motor or not str(motor).strip():
            raise AuditValidationError("❌ 'motor' no puede estar vacío")
        if operacion not in AUDIT_OPERATIONS:
            raise AuditValidationError(f"❌ Operación inválida: '{operacion}'. Debe ser INSERT, UPDATE o DELETE")
        if not isinstance(rowcount, int) or rowcount < 0:
            raise AuditValidationError(f"❌ 'rowcount' debe ser un entero >= 0, se recibió {rowcount}")
        if not isinstance(elapsed, (int, float)) or elapsed < 0:
            raise AuditValidationError(f"❌ 'elapsed' debe ser un número >= 0, se recibió {elapsed}")


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
        # (ruta, columnas) cuya cabecera ya se comprobó: una vez por instancia, y otra si cambia la ruta o las columnas
        # (``columnas_auditoria`` del repositorio; ``AuditManager`` ya no deja cambiarlas, 5.0.0); ver
        # ``_asegurar_cabecera``.
        self._cabecera_validada: tuple[Path, tuple[str, ...]] | None = None

        if self.audit_csv_path is not None:
            self.validar_ruta(self.audit_csv_path)

    def validar_ruta(self, ruta: Path) -> None:
        """Valida que la ruta de auditoría sea accesible."""
        try:
            ruta.parent.mkdir(parents=True, exist_ok=True)
        except Exception as error:
            raise AuditConfigError(f"❌ No se puede acceder a la ruta de auditoría: {error}") from error

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
            clave = (self.audit_csv_path, tuple(self.columnas_auditoria))
            if self._cabecera_validada != clave:
                self._asegurar_cabecera(self.audit_csv_path)
                self._cabecera_validada = clave
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

    def _asegurar_cabecera(self, path: Path) -> None:
        """Aparta el CSV existente si su cabecera no es la esperada, para empezar uno nuevo con cabecera correcta.

        Un CSV abierto y guardado con otra herramienta (p.ej. cada línea entrecomillada al re-guardarlo con coma como
        delimitador) no se puede leer: sin esta comprobación se le seguían añadiendo filas y todos los lectores
        (``leer_auditoria``, el resumen de ``dump``) fallaban. Se renombra a ``<nombre>.invalid-<fecha><ext>`` (no se
        pierde nada) y se registra un WARNING. Se llama con el lock de la ruta tomado.
        """
        if not path.is_file():
            return  # no existe (se creará con cabecera) o no es un fichero: la escritura fallará como siempre
        try:
            primera = AuditFiles.first_line(path)
        except OSError:
            return  # sin permisos u otro fallo de E/S: no es una cabecera inválida; la escritura informará del error
        if AuditFiles.has_header(primera, "\t".join(self.columnas_auditoria)):
            return
        try:
            apartado = AuditFiles.set_aside(path)
        except OSError as error:
            raise AuditFileError(
                f"❌ El CSV de auditoría '{path}' tiene una cabecera no válida y no se pudo apartar: {error}"
            ) from error
        self.logger.warning(
            "El CSV de auditoría '%s' tenía una cabecera no válida (%r); se ha apartado como '%s' y se empieza uno "
            "nuevo.",
            path,
            primera[:120],
            apartado.name,
        )

    @staticmethod
    def _ruta_apartado(path: Path) -> Path:
        """``<nombre>.invalid-<fecha><ext>``, con sufijo ``_2``, ``_3``… si ya existe (ver :meth:`AuditFiles.aside_path`)."""
        return AuditFiles.aside_path(path)

    def _file_lock(self, path: Path) -> threading.Lock:
        """Lock compartido de ``path``, cacheado mientras la ruta no cambie."""
        if self._lock is None or path != self._lock_path:
            self._lock = path_lock(path)
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
            dataframe: pd.DataFrame = self.parse_frame(pd.read_csv(str(self.audit_csv_path), delimiter="\t"))

            if self.cache_enabled:
                self._cache_df = dataframe.copy()
                self._cache_timestamp = datetime.now()
                self._cache_firma = firma
                self.logger.debug(f"💾 Caché actualizado ({len(dataframe)} filas)")

            return dataframe
        except Exception as error:
            raise AuditDataError(f"❌ Error al leer el archivo CSV de auditoría: {error}") from error

    @staticmethod
    def parse_frame(dataframe: pd.DataFrame) -> pd.DataFrame:
        """Tipos de las columnas del CSV tal como se escriben: ``timestamp`` a fecha y ``tiempo_seg`` (coma decimal) a número.

        Modifica y devuelve ``dataframe``. Lo usa también :meth:`read_since` (resumen de ``dump``, 3.4 / PF-08).
        """
        if "timestamp" in dataframe.columns:
            dataframe["timestamp"] = pd.to_datetime(dataframe["timestamp"], format="mixed")
        if "tiempo_seg" in dataframe.columns:
            dataframe["tiempo_seg"] = pd.to_numeric(
                dataframe["tiempo_seg"].astype(str).str.replace(",", ".", regex=False),
                errors="coerce",
            )
        return dataframe

    @classmethod
    def read_since(cls, audit_path: Path, start_offset: int | None) -> pd.DataFrame:
        """CSV de auditoría con los registros añadidos desde ``start_offset`` (o entero, si no se puede acotar).

        3.4 / PF-08 (performance-audit de dump 2026-09-25): leer el CSV histórico completo en cada volcado era lineal
        (0,72 s con 500K registros). El CSV es de solo añadir: se lee la cabecera y lo escrito desde el tamaño que tenía
        al empezar, con las mismas conversiones que :meth:`leer_auditoria`. Si no hay desplazamiento, o el fichero es
        ahora más pequeño (se truncó o rotó), se lee entero.
        """
        size = AuditFiles.file_size(audit_path) or 0
        if not start_offset or size < start_offset:
            return cls._read_whole(audit_path)
        with audit_path.open("rb") as fh:
            header = fh.readline()
            if start_offset <= len(header):
                return cls._read_whole(audit_path)
            fh.seek(start_offset - 1)
            if fh.read(1) != b"\n":  # empezó a mitad de una fila (escritura de otro proceso): salta a la siguiente
                fh.readline()
            tail = fh.read()
        df = pd.read_csv(io.BytesIO(header + tail), delimiter="\t", encoding="utf-8")
        return cls.parse_frame(df)

    @classmethod
    def _read_whole(cls, audit_path: Path) -> pd.DataFrame:
        """El CSV entero, sin caché (lectura puntual)."""
        repository = cls(
            audit_csv_path=audit_path,
            columnas_auditoria=list(AUDIT_COLUMNS),
            logger=logging.getLogger(__name__),
            cache_enabled=False,
        )
        return repository.leer_auditoria()

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


__all__: list[str] = [
    "AUDIT_COLUMNS",
    "AUDIT_OPERATIONS",
    "AuditCsvRepository",
    "AuditRecord",
    "AuditRecordValidator",
]
