"""
Módulo para gestionar auditoría de operaciones CRUD en base de datos.

AuditManager se mantiene como fachada pública y delega en:
- repository: persistencia CSV + caché
- service: estadísticas y filtros
- exporters: Excel, JSON y HTML
"""

from __future__ import annotations

import logging
import warnings

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from ._audit.errors import AuditConfigError, AuditDataError, AuditError, AuditFileError, AuditValidationError
from ._audit.exporters import AuditExporters
from ._audit.record import AuditRecord
from ._audit.repository import AuditCsvRepository
from ._audit.service import AuditAnalyticsService


class AuditManager:
    """Fachada pública del subsistema de auditoría."""

    ERROR_AUDIT_PATH_REQUIRED: str = "❌ Debes especificar un archivo de auditoría válido."

    def __init__(
        self,
        audit_csv_path: Path | None = None,
        cache_enabled: bool = True,
        cache_ttl_seconds: int = 300,
    ) -> None:
        self.logger: logging.Logger = logging.getLogger(__name__)

        columnas_auditoria: list[str] = [
            "timestamp",
            "tabla",
            "motor",
            "operacion",
            "total_filas",
            "tiempo_seg",
            "sql",
        ]

        self._repository: AuditCsvRepository = AuditCsvRepository(
            audit_csv_path=audit_csv_path,
            columnas_auditoria=columnas_auditoria,
            logger=self.logger,
            cache_enabled=cache_enabled,
            cache_ttl_seconds=cache_ttl_seconds,
        )
        self._service: AuditAnalyticsService = AuditAnalyticsService(repository=self._repository, logger=self.logger)
        self._exporters: AuditExporters = AuditExporters(
            repository=self._repository,
            service=self._service,
            logger=self.logger,
            error_audit_path_required=self.ERROR_AUDIT_PATH_REQUIRED,
        )
        self._aviso_deshabilitada_emitido: bool = False

    @property
    def audit_csv_path(self) -> Path | None:
        return self._repository.audit_csv_path

    @audit_csv_path.setter
    def audit_csv_path(self, value: Path | None) -> None:
        self._repository.audit_csv_path = value

    @property
    def columnas_auditoria(self) -> list[str]:
        return self._repository.columnas_auditoria

    @columnas_auditoria.setter
    def columnas_auditoria(self, value: list[str]) -> None:
        """Obsoleto: se retirará en la próxima versión menor.

        H7 (audit-code 2026-09-25): cambia la cabecera del CSV, pero cada fila se sigue escribiendo con las 7 columnas
        fijas, así que el fichero deja de poder leerse.
        """
        warnings.warn(
            "AuditManager.columnas_auditoria no debe asignarse: la cabecera dejaría de coincidir con las filas del CSV "
            "(siempre 7 columnas). El setter se retirará en la próxima versión menor.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._repository.columnas_auditoria = value

    @property
    def cache_enabled(self) -> bool:
        return self._repository.cache_enabled

    @cache_enabled.setter
    def cache_enabled(self, value: bool) -> None:
        self._repository.cache_enabled = value

    @property
    def cache_ttl_seconds(self) -> int:
        return self._repository.cache_ttl_seconds

    @cache_ttl_seconds.setter
    def cache_ttl_seconds(self, value: int) -> None:
        self._repository.cache_ttl_seconds = value

    def registrar_operacion(
        self,
        tabla: str,
        motor: str,
        operacion: str,
        rowcount: int,
        elapsed: float,
        genero_sql: bool = False,
    ) -> None:
        """
        Registrar una operación CRUD en el CSV de auditoría.

        Args:
            tabla: Nombre de la tabla modificada
            motor: Tipo de motor ('mariadb', 'oracle', 'postgresql', etc.)
            operacion: Tipo de operación ('INSERT', 'UPDATE', 'DELETE')
            rowcount: Número de filas enviadas a la operación (``BulkCrud`` pasa ``len(df)``). No es el número de filas
                que la BD dice haber modificado: un DELETE o UPDATE con claves inexistentes cuenta todas las enviadas.
            elapsed: Tiempo en segundos que tardó la operación
            genero_sql: Si la operación generó SQL personalizado (default False)

        Raises:
            AuditValidationError: Si algún parámetro es inválido
        """
        if self.audit_csv_path is None:
            # QW-3 (P-11): un solo aviso por instancia, no uno por operación.
            if not self._aviso_deshabilitada_emitido:
                self.logger.warning("⚠️ Auditoría deshabilitada: audit_csv_path es None")
                self._aviso_deshabilitada_emitido = True
            return

        self._validar_parametros_operacion(tabla, motor, operacion, rowcount, elapsed)
        self._repository.registrar_operacion(
            tabla=tabla,
            motor=motor,
            operacion=operacion,
            rowcount=rowcount,
            elapsed=elapsed,
            genero_sql=genero_sql,
        )
        self.logger.debug(f"🟢 {operacion} - filas {rowcount} - {elapsed:.3f}s registrado en auditoría")

    def _registrar_lote(self, registros: Sequence[AuditRecord]) -> None:
        """Registra varias operaciones con una sola escritura del CSV.

        Uso interno de ``BulkCrud.bulk_session``, que acumula la auditoría hasta confirmar la transacción. Valida todos
        los registros antes de escribir ninguno. Sin ``audit_csv_path`` no hace nada.
        """
        if self.audit_csv_path is None or not registros:
            return
        for registro in registros:
            self._validar_parametros_operacion(
                registro.tabla, registro.motor, registro.operacion, registro.rowcount, registro.elapsed
            )
        self._repository.registrar_operaciones(registros)
        self.logger.debug(f"🟢 {len(registros)} operaciones registradas en auditoría")

    def _validar_parametros_operacion(
        self, tabla: str, motor: str, operacion: str, rowcount: int, elapsed: float
    ) -> None:
        if not tabla or not str(tabla).strip():
            raise AuditValidationError("❌ 'tabla' no puede estar vacío")
        if not motor or not str(motor).strip():
            raise AuditValidationError("❌ 'motor' no puede estar vacío")
        if operacion not in ("INSERT", "UPDATE", "DELETE"):
            raise AuditValidationError(f"❌ Operación inválida: '{operacion}'. Debe ser INSERT, UPDATE o DELETE")
        if not isinstance(rowcount, int) or rowcount < 0:
            raise AuditValidationError(f"❌ 'rowcount' debe ser un entero >= 0, se recibió {rowcount}")
        if not isinstance(elapsed, (int, float)) or elapsed < 0:
            raise AuditValidationError(f"❌ 'elapsed' debe ser un número >= 0, se recibió {elapsed}")

    def leer_auditoria(self, usar_cache: bool = True) -> pd.DataFrame:
        """Leer el registro de auditoría desde CSV."""
        return self._repository.leer_auditoria(usar_cache=usar_cache)

    def limpiar_cache(self) -> None:
        """Limpiar el cache en memoria de auditoría."""
        self._repository.limpiar_cache()

    def invalidar_cache(self) -> None:
        """Invalidar el cache en memoria (alias de limpiar_cache)."""
        self.limpiar_cache()

    def exportar_resumen_excel(self, agrupar_por: Literal["tabla", "fecha", "tabla_fecha"] = "tabla") -> Path:
        """Exportar resumen de auditoría a archivo Excel."""
        return self._exporters.exportar_resumen_excel(agrupar_por=agrupar_por)

    def obtener_estadisticas(self) -> dict[str, Any]:
        """Obtener estadísticas generales de auditoría."""
        return self._service.obtener_estadisticas()

    def obtener_operaciones_por_tipo(self) -> dict[str, int]:
        """Contar operaciones por tipo (INSERT, UPDATE, DELETE)."""
        return self._service.obtener_operaciones_por_tipo()

    def obtener_operaciones_por_tabla(self) -> dict[str, int]:
        """Contar operaciones por tabla."""
        return self._service.obtener_operaciones_por_tabla()

    def obtener_operaciones_lentas(self, umbral_segundos: float = 5.0) -> pd.DataFrame:
        """Filtrar operaciones que tardaron más de un umbral."""
        return self._service.obtener_operaciones_lentas(umbral_segundos)

    def filtrar_por_operacion(self, operacion: str) -> pd.DataFrame:
        """Filtrar registros de auditoría por tipo de operación."""
        return self._service.filtrar_por_operacion(operacion)

    def filtrar_por_tabla(self, tabla: str) -> pd.DataFrame:
        """Filtrar registros de auditoría por tabla."""
        return self._service.filtrar_por_tabla(tabla)

    def filtrar_por_motor(self, motor: str) -> pd.DataFrame:
        """Filtrar registros de auditoría por motor de BD."""
        return self._service.filtrar_por_motor(motor)

    def filtrar_por_rango_tiempo(self, inicio: datetime, fin: datetime) -> pd.DataFrame:
        """Filtrar registros de auditoría por rango de fechas."""
        return self._service.filtrar_por_rango_tiempo(inicio, fin)

    def filtrar_multiple(
        self,
        operacion: str | None = None,
        tabla: str | None = None,
        motor: str | None = None,
        umbral_tiempo: float | None = None,
    ) -> pd.DataFrame:
        """Filtrar registros de auditoría con múltiples criterios simultáneamente."""
        return self._service.filtrar_multiple(
            operacion=operacion,
            tabla=tabla,
            motor=motor,
            umbral_tiempo=umbral_tiempo,
        )

    def exportar_resumen_json(self, output_path: Path | None = None) -> Path:
        """Exportar resumen de auditoría a archivo JSON."""
        return self._exporters.exportar_resumen_json(output_path=output_path)

    def exportar_resumen_html(self, output_path: Path | None = None) -> Path:
        """Exportar resumen de auditoría a archivo HTML interactivo."""
        return self._exporters.exportar_resumen_html(output_path=output_path)


__all__: list[str] = [
    "AuditConfigError",
    "AuditDataError",
    "AuditError",
    "AuditFileError",
    "AuditManager",
    "AuditValidationError",
]
