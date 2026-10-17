"""
Módulo para gestionar auditoría de operaciones CRUD en base de datos.

AuditManager se mantiene como fachada pública de ``bulk`` y delega en el módulo de auditoría centralizado
(``util_bbdd.audit``, sesión 2026-10-02c):
- legacy_csv: persistencia CSV (formato congelado) + caché y validación de registros
- analytics: estadísticas y filtros
- exporters: Excel, JSON y HTML

Su logger sigue siendo ``util_bbdd.bulk.audit``.
"""

from __future__ import annotations

import logging
import warnings

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import pandas as pd

from .._core.validation import StrPath, validate_optional_path
from ..audit.analytics import AuditAnalyticsService
from ..audit.exporters import AuditExporters
from ..audit.legacy_csv import AUDIT_COLUMNS, AuditCsvRepository, AuditRecord, AuditRecordValidator
from ..audit.readiness import ReadinessBlock
from ..connection.performance_advisor import EngineReadinessAdvisor
from ._audit.errors import (
    AuditConfigError,
    AuditDataError,
    AuditError,
    AuditExportError,
    AuditFileError,
    AuditValidationError,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


class AuditManager:
    """Fachada pública del subsistema de auditoría."""

    ERROR_AUDIT_PATH_REQUIRED: str = "❌ Debes especificar un archivo de auditoría válido."

    def __init__(
        self,
        audit_csv_path: StrPath | None = None,
        cache_enabled: bool = True,
        cache_ttl_seconds: int = 300,
        *,
        warn_if_disabled: bool = True,
        engine: Engine | None = None,
    ) -> None:
        """
        Args:
            audit_csv_path: CSV de auditoría (``str`` o ``Path``). ``None`` deshabilita la escritura.
            cache_enabled: Cachear las lecturas del CSV.
            cache_ttl_seconds: Vigencia de la caché de lectura.
            warn_if_disabled: Si ``True`` (default), sin ``audit_csv_path`` la primera operación registrada emite un
                WARNING "Auditoría deshabilitada". ``False`` lo omite (M-4, audit-code de ``ParallelBulkLoader``: el
                loader crea una instancia por partición y avisa él una sola vez).
            engine: Engine cuyas condiciones (``EngineReadinessAdvisor``) se añaden como hoja ``Condiciones_motor`` en
                :meth:`exportar_resumen_excel`. ``BulkCrud`` pasa el suyo; sin engine no se añade la hoja.
        """
        self.logger: logging.Logger = logging.getLogger(__name__)

        columnas_auditoria: list[str] = list(AUDIT_COLUMNS)

        self._repository: AuditCsvRepository = AuditCsvRepository(
            audit_csv_path=self._audit_path(audit_csv_path),
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
        self._aviso_deshabilitada_emitido: bool = not warn_if_disabled
        self._engine: Engine | None = engine

    @property
    def audit_csv_path(self) -> Path | None:
        return self._repository.audit_csv_path

    @audit_csv_path.setter
    def audit_csv_path(self, value: StrPath | None) -> None:
        self._repository.audit_csv_path = self._audit_path(value)

    @staticmethod
    def _audit_path(value: StrPath | None) -> Path | None:
        """``value`` como ``Path`` (v1.1.0: también ``str``); otro tipo, ``AuditConfigError`` como una ruta inaccesible."""
        try:
            return validate_optional_path(value, "audit_csv_path")
        except ValueError as error:
            raise AuditConfigError(f"❌ No se puede acceder a la ruta de auditoría: {error}") from error

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
        AuditRecordValidator.validate(tabla, motor, operacion, rowcount, elapsed)

    def leer_auditoria(self, usar_cache: bool = True) -> pd.DataFrame:
        """Leer el registro de auditoría desde CSV.

        Args:
            usar_cache: Devuelve una copia de la lectura en caché si sigue siendo válida.

        Returns:
            Una fila por registro de auditoría.
        """
        return self._repository.leer_auditoria(usar_cache=usar_cache)

    def limpiar_cache(self) -> None:
        """Limpiar el cache en memoria de auditoría."""
        self._repository.limpiar_cache()

    def invalidar_cache(self) -> None:
        """Invalidar el cache en memoria (alias de limpiar_cache)."""
        self.limpiar_cache()

    def exportar_resumen_excel(
        self,
        agrupar_por: Literal["tabla", "fecha", "tabla_fecha"] = "tabla",
        *,
        engine: Engine | None = None,
    ) -> Path:
        """Exportar resumen de auditoría a archivo Excel.

        Con un engine (``engine`` o el del constructor) añade al final la hoja ``Condiciones_motor``: las condiciones de
        ese engine verificadas en este proceso (``EngineReadinessAdvisor.engine_report``; si ``BulkCrud`` ya lo verificó
        al crearse, sin nueva conexión).

        Args:
            agrupar_por: Agrupación de las hojas por operación.
            engine: Engine de la carga, para un ``AuditManager`` creado aparte (p.ej. tras ``ParallelBulkLoader``).

        Examples:
            >>> crud = BulkCrud(engine, audit=AuditOptions(csv_path=Path("audit.csv")))
            >>> crud.bulk_insert_from_df(df, "clientes")
            >>> crud.audit_manager.exportar_resumen_excel()  # incluye la hoja Condiciones_motor
        """
        return self._exporters.exportar_resumen_excel(
            agrupar_por=agrupar_por, condiciones_motor=self._readiness_blocks(engine or self._engine)
        )

    @staticmethod
    def _readiness_blocks(engine: Engine | None) -> list[ReadinessBlock]:
        """Bloque de condiciones del motor de ``engine``; sin engine, ninguno."""
        if engine is None:
            return []
        advisor = EngineReadinessAdvisor()
        return [(f"Engine · {advisor.describe_engine(engine)}", advisor.engine_report(engine))]

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
        """Filtrar operaciones que tardaron más de un umbral.

        Args:
            umbral_segundos: Tiempo mínimo, excluido (``tiempo_seg > umbral_segundos``).

        Returns:
            Las operaciones lentas, de la más lenta a la más rápida.
        """
        return self._service.obtener_operaciones_lentas(umbral_segundos)

    def filtrar_por_operacion(self, operacion: str) -> pd.DataFrame:
        """Filtrar registros de auditoría por tipo de operación.

        Args:
            operacion: ``INSERT``, ``UPDATE`` o ``DELETE`` (en mayúsculas).

        Raises:
            AuditValidationError: Si ``operacion`` no es una de las tres.
        """
        return self._service.filtrar_por_operacion(operacion)

    def filtrar_por_tabla(self, tabla: str) -> pd.DataFrame:
        """Filtrar registros de auditoría por tabla.

        Args:
            tabla: Nombre de la tabla tal como figura en el CSV (comparación exacta).
        """
        return self._service.filtrar_por_tabla(tabla)

    def filtrar_por_motor(self, motor: str) -> pd.DataFrame:
        """Filtrar registros de auditoría por motor de BD.

        Args:
            motor: Motor tal como figura en el CSV (comparación exacta).
        """
        return self._service.filtrar_por_motor(motor)

    def filtrar_por_rango_tiempo(self, inicio: datetime, fin: datetime) -> pd.DataFrame:
        """Filtrar registros de auditoría por rango de fechas.

        Args:
            inicio: Inicio del rango, incluido.
            fin: Fin del rango, incluido.

        Returns:
            Los registros del rango, ordenados por ``timestamp``.

        Raises:
            AuditValidationError: Si ``inicio`` es posterior a ``fin``.
        """
        return self._service.filtrar_por_rango_tiempo(inicio, fin)

    def filtrar_multiple(
        self,
        operacion: str | None = None,
        tabla: str | None = None,
        motor: str | None = None,
        umbral_tiempo: float | None = None,
    ) -> pd.DataFrame:
        """Filtrar registros de auditoría con múltiples criterios simultáneamente (se cumplen todos).

        Args:
            operacion: ``INSERT``, ``UPDATE`` o ``DELETE``; ``None`` no filtra.
            tabla: Nombre exacto de la tabla; vacío o ``None`` no filtra.
            motor: Motor exacto; vacío o ``None`` no filtra.
            umbral_tiempo: Tiempo mínimo, excluido (``tiempo_seg > umbral_tiempo``, como en
                :meth:`obtener_operaciones_lentas`); ``None`` no filtra.

        Raises:
            AuditValidationError: Si ``operacion`` no es ``None`` ni una de las tres.
        """
        return self._service.filtrar_multiple(
            operacion=operacion,
            tabla=tabla,
            motor=motor,
            umbral_tiempo=umbral_tiempo,
        )

    def exportar_resumen_json(self, output_path: StrPath | None = None) -> Path:
        """Exportar resumen de auditoría a archivo JSON.

        Args:
            output_path: Ruta del fichero (``str`` o ``Path``); por defecto ``auditoria.json`` junto al CSV.

        Returns:
            Ruta del fichero escrito.
        """
        return self._exporters.exportar_resumen_json(output_path=validate_optional_path(output_path, "output_path"))

    def exportar_resumen_html(self, output_path: StrPath | None = None) -> Path:
        """Exportar resumen de auditoría a archivo HTML interactivo.

        Args:
            output_path: Ruta del fichero (``str`` o ``Path``); por defecto ``auditoria.html`` junto al CSV.

        Returns:
            Ruta del fichero escrito.
        """
        return self._exporters.exportar_resumen_html(output_path=validate_optional_path(output_path, "output_path"))


__all__: list[str] = [
    "AuditConfigError",
    "AuditDataError",
    "AuditExportError",
    "AuditError",
    "AuditFileError",
    "AuditManager",
    "AuditValidationError",
]
