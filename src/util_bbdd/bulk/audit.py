"""
Módulo para gestionar auditoría de operaciones CRUD en base de datos.

AuditManager se mantiene como fachada pública y delega en:
- repository: persistencia CSV + caché
- service: estadísticas y filtros
- exporters: Excel, JSON y HTML
"""

from __future__ import annotations

import copy
import logging

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from ._audit.errors import AuditConfigError, AuditDataError, AuditError, AuditFileError, AuditValidationError
from ._audit.exporters import AuditExporters
from ._audit.repository import AuditCsvRepository
from ._audit.service import AuditAnalyticsService


class AuditTransaction:
    """Context manager para gestionar transacciones de auditoría."""

    def __init__(self, manager: AuditManager, nombre: str) -> None:
        if not nombre or not nombre.strip():
            raise AuditValidationError("❌ El nombre de la transacción no puede estar vacío.")
        if not isinstance(manager, AuditManager):
            raise AuditValidationError("❌ El manager debe ser una instancia de AuditManager.")

        self.manager: AuditManager = manager
        self.nombre: str = nombre.strip()
        self.inicio: datetime | None = None
        self.fin: datetime | None = None
        self.operaciones: list[dict[str, Any]] = []
        self.exito: bool = False
        self.audit_error: Exception | None = None
        self.logger: logging.Logger = logging.getLogger(__name__)

    def __enter__(self) -> AuditTransaction:
        self.inicio = datetime.now()
        self.logger.info(f"⏱️  Iniciando transacción: {self.nombre}")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.fin = datetime.now()
        duracion: timedelta = self.fin - self.inicio if self.inicio else timedelta(0)
        self.exito = exc_type is None

        try:
            if self.exito:
                self._registrar_transaccion_exitosa(duracion)
            else:
                self._registrar_transaccion_fallida(duracion, exc_type, exc_val)
        except Exception as error:
            self.logger.error(f"❌ Error al finalizar transacción {self.nombre}: {error}")
            self.audit_error = error

    def _registrar_transaccion_exitosa(self, duracion: timedelta) -> None:
        tiempo_segundos: float = duracion.total_seconds()
        total_ops: int = len(self.operaciones)
        self.logger.info(
            f"✅ Transacción '{self.nombre}' completada: {total_ops} operaciones en {tiempo_segundos:.3f}s"
        )
        self.manager._historial_transacciones.append(self.obtener_resumen())
        if self.manager.cache_enabled:
            self.manager.invalidar_cache()

    def _registrar_transaccion_fallida(self, duracion: timedelta, exc_type: Any, exc_val: Any) -> None:
        tiempo_segundos: float = duracion.total_seconds()
        total_ops: int = len(self.operaciones)
        self.logger.error(
            f"❌ Transacción '{self.nombre}' FALLIDA: {total_ops} operaciones en {tiempo_segundos:.3f}s - "
            f"Error: {exc_type.__name__}: {exc_val}"
        )
        self.manager._historial_transacciones.append(self.obtener_resumen())
        if self.manager.cache_enabled:
            self.manager.invalidar_cache()

    def agregar_operacion(
        self,
        tabla: str,
        motor: str,
        operacion: str,
        rowcount: int,
        elapsed: float,
        genero_sql: bool = False,
    ) -> None:
        if self.inicio is None or self.fin is not None:
            raise AuditValidationError("❌ No se puede agregar operaciones a una transacción cerrada.")

        self.operaciones.append(
            {
                "tabla": tabla,
                "motor": motor,
                "operacion": operacion,
                "rowcount": rowcount,
                "elapsed": elapsed,
                "genero_sql": genero_sql,
                "timestamp": datetime.now(),
            }
        )
        self.logger.debug(f"📝 Operación agregada a transacción {self.nombre}: {tabla}.{operacion}")

    @property
    def duracion_segundos(self) -> float:
        if self.inicio and self.fin:
            return (self.fin - self.inicio).total_seconds()
        return 0.0

    @property
    def total_operaciones(self) -> int:
        return len(self.operaciones)

    @property
    def total_filas(self) -> int:
        return sum(op.get("rowcount", 0) for op in self.operaciones)

    def obtener_resumen(self) -> dict[str, Any]:
        """
        Obtener resumen de la transacción actual.

        Returns:
            Diccionario con:
            - nombre: Nombre de la transacción
            - inicio: Timestamp de inicio
            - fin: Timestamp de fin (o None si aún está en curso)
            - duracion_segundos: Segundos transcurridos
            - total_operaciones: Cantidad de operaciones registradas
            - total_filas: Cantidad total de filas afectadas
            - exito: Booleano indicando si completó exitosamente
            - operaciones: Lista de operaciones registradas
        """
        return {
            "nombre": self.nombre,
            "exito": self.exito,
            "duracion_segundos": self.duracion_segundos,
            "total_operaciones": self.total_operaciones,
            "total_filas": self.total_filas,
            "operaciones": copy.deepcopy(self.operaciones),
        }


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
        self._historial_transacciones: list[dict[str, Any]] = []

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
            rowcount: Número de filas afectadas
            elapsed: Tiempo en segundos que tardó la operación
            genero_sql: Si la operación generó SQL personalizado (default False)

        Raises:
            AuditValidationError: Si algún parámetro es inválido
        """
        if self.audit_csv_path is None:
            self.logger.warning("⚠️ Auditoría deshabilitada: audit_csv_path es None")
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
        self.logger.info(f"🟢 {operacion} - filas {rowcount} - {elapsed:.3f}s registrado en auditoría")

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

    def iniciar_transaccion(self, nombre: str) -> AuditTransaction:
        """Iniciar una transacción de auditoría (context manager)."""
        return AuditTransaction(self, nombre)

    def obtener_historial_transacciones(self) -> list[dict[str, Any]]:
        """Obtener historial de transacciones completadas."""
        return self._historial_transacciones.copy()


__all__: list[str] = [
    "AuditConfigError",
    "AuditDataError",
    "AuditError",
    "AuditFileError",
    "AuditManager",
    "AuditTransaction",
    "AuditValidationError",
]
