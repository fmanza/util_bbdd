"""Jerarquía centralizada de excepciones para util_bbdd.

Proporciona excepciones organizadas por categoría de error:
- ConnectionError: Errores de conexión y pool
- QueryError: Errores en ejecución de queries
- MetadataError: Errores en operaciones de metadatos
- ValidationError: Errores de validación
- DriverError: Errores de drivers
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class DatabaseException(Exception):
    """Excepción base para todas las excepciones de util_bbdd."""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        db_type: str | None = None,
        details: str | None = None,
    ) -> None:
        """Inicializa excepción con contexto de operación.

        Args:
            message: Mensaje de error principal
            operation: Tipo de operación (SELECT, INSERT, CONNECT, etc.)
            db_type: Tipo de base de datos (mariadb, oracle, etc.)
            details: Detalles adicionales del error
        """
        self.message: str = message
        self.operation: str = operation or "UNKNOWN"
        self.db_type: str = db_type or "UNKNOWN"
        self.details: str | None = details

        formatted_msg: str = f"{message}"
        if operation:
            formatted_msg += f" (Operación: {operation})"
        if db_type:
            formatted_msg += f" (BD: {db_type})"
        if details:
            formatted_msg += f" - {details}"

        super().__init__(formatted_msg)


# ============================================================================
# Categoría 1: Errores de Conexión y Pool
# ============================================================================


class ConnectionError(DatabaseException):
    """Error en conexión a base de datos."""

    pass


class PoolConnectionError(ConnectionError):
    """Error obteniendo/devolviendo conexión del pool."""

    pass


class PoolTimeoutError(ConnectionError):
    """Timeout esperando conexión disponible del pool."""

    def __init__(
        self,
        message: str = "Timeout esperando conexión del pool",
        timeout_seconds: float | None = None,
        operation: str | None = None,
        db_type: str | None = None,
    ) -> None:
        details = f"Timeout: {timeout_seconds}s" if timeout_seconds is not None else None
        super().__init__(message, operation=operation, db_type=db_type, details=details)
        self.timeout_seconds = timeout_seconds


# ============================================================================
# Categoría 2: Errores en Ejecución de Queries
# ============================================================================


class QueryError(DatabaseException):
    """Error en ejecución de query."""

    pass


class QueryTimeoutError(QueryError):
    """Query excedió timeout permitido."""

    pass


class QueryExecutionError(QueryError):
    """Error durante ejecución de query."""

    pass


class QueryNotFoundError(QueryError):
    """Query no encontrada en el registry."""

    pass


class QueryValidationError(QueryError):
    """Error validando parámetros de query."""

    pass


class QueryParameterError(QueryError):
    """Parámetro específico de query es inválido."""

    pass


# ============================================================================
# Categoría 3: Errores en Operaciones de Metadatos
# ============================================================================


class MetadataError(DatabaseException):
    """Error en operación de metadatos."""

    pass


class MetadataFetchError(MetadataError):
    """Error obteniendo metadatos."""

    pass


class MetadataNormalizationError(MetadataError):
    """Error normalizando metadatos."""

    pass


class DDLBuildError(MetadataError):
    """Error constructuyendo sentencia DDL."""

    pass


# ============================================================================
# Categoría 4: Errores de Validación
# ============================================================================


class ValidationError(DatabaseException):
    """Error de validación."""

    pass


class InvalidDatabaseType(ValidationError):
    """Tipo de base de datos no válido o no soportado."""

    pass


class InvalidConnectionConfig(ValidationError):
    """Configuración de conexión inválida."""

    pass


class InvalidQueryParameters(ValidationError):
    """Parámetros de query inválidos."""

    pass


# ============================================================================
# Categoría 5: Errores de Drivers
# ============================================================================


class DriverError(DatabaseException):
    """Error relacionado con drivers."""

    def __init__(
        self,
        message: str,
        driver_name: str | None = None,
        install_command: str | None = None,
        db_type: str | None = None,
        operation: str | None = None,
        details: str | None = None,
    ) -> None:
        self.driver_name = driver_name
        self.install_command = install_command
        extra: list[str] = []
        if driver_name:
            extra.append(f"Driver: {driver_name}")
        if install_command:
            extra.append(f"Instalar con: {install_command}")
        combined_details = " | ".join(extra) if extra else details
        super().__init__(message, operation=operation, db_type=db_type, details=combined_details)


class DriverNotFoundError(DriverError):
    """Driver requerido no está instalado."""

    pass


class DriverConfigurationError(DriverError):
    """Error configurando driver."""

    pass


# ============================================================================
# Errores Específicos de Operaciones
# ============================================================================


class DatabaseOperationError(DatabaseException):
    """Error genérico en operación de base de datos."""

    pass


class DatabaseConfigurationError(DatabaseException):
    """Error en configuración de SyncDatabaseManager."""

    pass


# ============================================================================
# Categoría 6: Errores de Comparación de Esquemas (módulo comparar/)
# ============================================================================


class ComparerError(DatabaseException):
    """Excepción base para errores del módulo de comparación de esquemas.

    Captura cualquier error que ocurra durante comparación, validación o
    generación de reportes de diferencias de esquemas entre dos bases de datos.
    """

    pass


class SchemaDiffValidationError(ComparerError):
    """Error validando entrada o parámetros de comparación/reporte.

    Cubre:
    - Dialect SQL no soportado
    - Formato de reporte no soportado
    - Rutas de salida o parámetros inválidos
    - Parámetros mal tipados
    """

    pass


class MetadataIntrospectionError(ComparerError):
    """Error obteniendo metadatos via SQLAlchemy Inspector.

    Cubre:
    - Inspector.get_columns() falla (tabla no existe, sin permisos, etc.)
    - Inspector.get_pk_constraint(), get_foreign_keys() falla
    - Inspector.get_indexes() no soportado en dialect
    - Fetching de vistas, routines (procedures/functions) falla
    - get_view_definition() no soportado en dialect
    - DDL retrieval falla inesperadamente
    """

    pass


# ============================================================================
# Categoría 7: Errores de Generación de Documentación (módulo doc/)
# ============================================================================


class DocumentationError(DatabaseException):
    """Excepción base para errores del módulo de documentación (doc/).

    Captura cualquier error que ocurra durante la generación de documentación
    de base de datos en formatos Word, Excel o HTML.
    """

    pass


class DocumentationConfigError(DocumentationError, ValueError):
    """Error en configuración del generador documental.

    Cubre:
    - Formato de salida no soportado
    - ``imprimir`` que no es un diccionario
    - Fichero de cabeceras inexistente o mal formado
    - Ruta de plantilla Word inválida o inexistente

    Hereda también de ``ValueError`` (como :class:`AuditConfigError`): hasta 0.40 ``DatabaseDocumentation`` lanzaba
    ``ValueError`` por estos casos y quien lo capturaba así sigue funcionando.
    """


class DocumentationRenderError(DocumentationError):
    """Error generando un documento de salida.

    Cubre:
    - WordGenerator / ExcelGenerator / HtmlGenerator falla al escribir
    - I/O error escribiendo archivo de salida

    La excepción original queda en ``__cause__``. Los errores de base de datos (leer el catálogo) no se envuelven:
    llegan con su propia clase (``DatabaseOperationError``…).
    """


# ============================================================================
# Categoría 8: Errores del módulo dump/
# ============================================================================


class DumpError(DatabaseException):
    """Excepción base para errores del módulo de volcado de datos (dump/).

    Cubre errores de orquestación, lectura de origen, escritura en destino,
    gestión de constraints y generación de informes Excel.
    """

    pass


class DumpConstraintError(DumpError):
    """Error desactivando o reactivando constraints en la BD destino."""

    pass


class DumpReportError(DumpError):
    """Error generando el informe Excel de auditoría del volcado.

    Cuando la lanza ``DumpOrchestrator.run()``, la carga ya ha terminado: ``result`` conserva el ``DumpResult`` completo
    (tablas, constraints, PK sync, auditoría) para que el llamador no lo pierda. Su ``report`` es la ruta prevista del
    informe, que no llegó a crearse.

    Attributes:
        output_path: Ruta prevista del informe, o ``None`` si falló antes de calcularla.
        result: ``DumpResult`` del volcado, o ``None`` si el error no viene de ``run()``. Tipado como ``Any`` porque
            ``_core`` no puede importar de ``dump`` (capas de ``docs/architecture.md``).

    Example:
        >>> try:
        ...     result = DumpOrchestrator(config).run()
        ... except DumpReportError as exc:
        ...     result = exc.result  # la carga se completó; solo falta el Excel
    """

    def __init__(self, message: str, *, output_path: Path | None = None) -> None:
        super().__init__(message)
        self.output_path: Path | None = output_path
        self.result: Any = None


# ============================================================================
# Auditoría de operaciones bulk (bulk/)
# ============================================================================


class AuditError(DatabaseException):
    """Excepción base para la auditoría de ``bulk`` (CSV de ``AuditManager``).

    Hereda de ``DatabaseException`` desde v0.18.0: antes heredaba de ``Exception`` y un ``except DatabaseException`` no
    la capturaba. Se lanza al configurar la auditoría, al leer o validar el CSV y, con ``audit_strict=True``, al no poder
    escribirlo.
    """


class AuditConfigError(AuditError, ValueError):
    """Error en configuración de auditoría.

    Hereda también de ``ValueError`` (H8, audit-code 2026-09-25): ``AuditCsvRepository.validar_ruta`` lanzaba
    ``ValueError`` y quien lo capturaba así sigue funcionando.
    """


class AuditFileError(AuditError):
    """Error en archivo de auditoría."""


class AuditDataError(AuditError):
    """Error en datos de auditoría."""


class AuditExportError(AuditDataError, OSError):
    """No se pudo escribir un informe de auditoría (p.ej. ``auditoria.xlsx`` abierto en Excel, disco lleno).

    Hereda también de ``OSError``: ``exportar_resumen_excel`` dejaba salir el ``OSError`` sin envolver, y quien lo
    captura así sigue funcionando; como ``AuditDataError`` da el mismo contrato que las exportaciones JSON y HTML.
    """


class AuditValidationError(AuditError):
    """Error en validación de parámetros."""


# ============================================================================
# Carga masiva paralela (bulk/)
# ============================================================================


class ParallelLoadError(DatabaseOperationError):
    """Alguna partición de una carga paralela de ``BulkCrud`` falló (v3.0.0, ``ParallelOptions``).

    La carga paralela no es atómica: las particiones que terminaron bien **quedan confirmadas**. ``result`` es el
    ``ParallelLoadResult`` (filas por partición, errores, contadores de auditoría) para decidir qué reintentar.

    Attributes:
        result: ``ParallelLoadResult`` de la carga. Tipado como ``Any`` porque ``_core`` no puede importar de ``bulk``.

    Example:
        >>> try:
        ...     crud.bulk_insert_from_df(df, "ventas", generar_sql=False)
        ... except ParallelLoadError as exc:
        ...     fallidas = [pr.index for pr in exc.result.partition_results if pr.error]
    """

    def __init__(self, message: str, *, result: Any = None) -> None:
        super().__init__(message)
        self.result: Any = result


# Las clases se definen aquí, pero su ruta pública es util_bbdd.exceptions (API 1.0): es la que muestran trazas, repr y
# logs, y la que guarda pickle. Los pickles con la ruta antigua (util_bbdd._core.exceptions.X) se siguen cargando.
_PUBLIC_MODULE = "util_bbdd.exceptions"


def _set_public_module() -> None:
    """Asigna ``_PUBLIC_MODULE`` como ``__module__`` de las excepciones de este módulo (sin variables de bucle globales)."""
    for value in globals().values():
        if isinstance(value, type) and issubclass(value, DatabaseException):
            value.__module__ = _PUBLIC_MODULE


_set_public_module()


__all__ = [
    # Base
    "DatabaseException",
    # Conexión
    "ConnectionError",
    "PoolConnectionError",
    "PoolTimeoutError",
    # Query
    "QueryError",
    "QueryTimeoutError",
    "QueryExecutionError",
    "QueryNotFoundError",
    "QueryValidationError",
    "QueryParameterError",
    # Metadatos
    "MetadataError",
    "MetadataFetchError",
    "MetadataNormalizationError",
    "DDLBuildError",
    # Validación
    "ValidationError",
    "InvalidDatabaseType",
    "InvalidConnectionConfig",
    "InvalidQueryParameters",
    # Drivers
    "DriverError",
    "DriverNotFoundError",
    "DriverConfigurationError",
    # Genéricos
    "DatabaseOperationError",
    "DatabaseConfigurationError",
    # Comparación de esquemas
    "ComparerError",
    "SchemaDiffValidationError",
    "MetadataIntrospectionError",
    # Documentación
    "DocumentationError",
    "DocumentationConfigError",
    "DocumentationRenderError",
    # Volcado de datos
    "DumpError",
    "DumpConstraintError",
    "DumpReportError",
    # Auditoría de bulk
    "AuditError",
    "AuditConfigError",
    "AuditFileError",
    "AuditDataError",
    "AuditExportError",
    "AuditValidationError",
    # Carga masiva paralela
    "ParallelLoadError",
]
