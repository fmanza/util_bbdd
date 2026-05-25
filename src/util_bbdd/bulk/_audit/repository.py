"""Capa repository de auditoría: persistencia CSV y caché."""

from __future__ import annotations

import csv
import logging

from datetime import datetime
from pathlib import Path

import pandas as pd

from .errors import AuditConfigError, AuditDataError, AuditFileError


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
            raise AuditConfigError("❌ 'audit_csv_path' no está establecido.")

        self.auditar_lote_csv(
            audit_path=self.audit_csv_path,
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
        audit_path: Path,
        tabla: str,
        motor: str,
        operacion: str,
        rowcount: int,
        elapsed: float,
        genero_sql: bool = False,
    ) -> None:
        """Escribe una fila de auditoría en CSV."""
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        file_exists: bool = audit_path.exists()

        with open(audit_path, "a", newline="", encoding="utf-8") as file_handle:
            writer = csv.writer(file_handle, delimiter="\t")
            if not file_exists:
                writer.writerow(self.columnas_auditoria)

            tiempo_formateado: str = f"{elapsed:.3f}".replace(".", ",")
            sql_texto: str = "Sí" if genero_sql else "No"
            writer.writerow(
                [
                    datetime.now().isoformat(timespec="seconds"),
                    tabla,
                    motor,
                    operacion,
                    rowcount,
                    tiempo_formateado,
                    sql_texto,
                ]
            )

    def leer_auditoria(self, usar_cache: bool = True) -> pd.DataFrame:
        """Lee el CSV de auditoría con soporte de caché temporal."""
        if usar_cache and self.cache_enabled and self.es_cache_valido() and self._cache_df is not None:
            self.logger.debug("📦 Usando caché para lectura de auditoría")
            return self._cache_df.copy()

        if self.audit_csv_path is None:
            raise AuditConfigError("❌ 'audit_csv_path' no está establecido.")
        if not self.audit_csv_path.exists():
            raise AuditFileError(f"❌ Archivo de auditoría no encontrado: {self.audit_csv_path}")

        try:
            dataframe: pd.DataFrame = pd.read_csv(str(self.audit_csv_path), delimiter="\t", parse_dates=["timestamp"])
            if "tiempo_seg" in dataframe.columns:
                dataframe["tiempo_seg"] = pd.to_numeric(
                    dataframe["tiempo_seg"].astype(str).str.replace(",", ".", regex=False),
                    errors="coerce",
                )

            if self.cache_enabled:
                self._cache_df = dataframe.copy()
                self._cache_timestamp = datetime.now()
                self.logger.debug(f"💾 Caché actualizado ({len(dataframe)} filas)")

            return dataframe
        except Exception as error:
            raise AuditDataError(f"❌ Error al leer el archivo CSV de auditoría: {error}") from error

    def es_cache_valido(self) -> bool:
        """Indica si el caché actual sigue siendo válido por TTL."""
        if self._cache_df is None or self._cache_timestamp is None:
            return False
        elapsed_seconds: float = (datetime.now() - self._cache_timestamp).total_seconds()
        return elapsed_seconds < self.cache_ttl_seconds

    def limpiar_cache(self) -> None:
        """Limpia el contenido del caché."""
        self._cache_df = None
        self._cache_timestamp = None
        self.logger.info("🧹 Caché limpiado")

    def invalidar_cache(self) -> None:
        """Alias de limpieza de caché para mantener contrato interno."""
        self.limpiar_cache()


__all__: list[str] = ["AuditCsvRepository"]
