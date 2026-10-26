"""Adaptadores que unifican SyncDatabaseManager con el contrato documental interno."""

from __future__ import annotations

from typing import Any

from ...application.ports import DocumentationSourcePort, EngineReadinessReportView, EngineReadinessSourcePort


class SyncDatabaseManagerAdapter:
    """Adapta ``SyncDatabaseManager`` al contrato ``DocumentationBackendPort``.

    Delega en el manager la lectura del catálogo (snapshot por lotes y DDL de tabla), la metadata opcional y las
    consultas del inventario, y añade ``imprimir_config``. Las lecturas por objeto (columnas, claves, índices…) no
    pasan por aquí: ``DocumentationSession`` las sirve desde el snapshot, y el inventario de almacenamiento lo arma
    ``StorageInventoryReportService`` con ``get_storage_rows``.

    Con ``schema`` (4.1.0, util_bbdd_web G22), todas las lecturas del catálogo, el contexto de metadatos y las
    consultas de almacenamiento van a ese schema en lugar del contexto del manager.
    """

    def __init__(
        self, db_manager: DocumentationSourcePort, imprimir_config: dict[str, Any], schema: str | None = None
    ) -> None:
        self._db_manager = db_manager
        self.imprimir_config: dict[str, Any] = imprimir_config
        self.db_type: str = db_manager.db_type
        self.database: str = db_manager.database
        self.conn_params: dict[str, Any] = db_manager.conn_params
        self._schema: str | None = schema.strip() if schema and schema.strip() else None

    # --- Catálogo -----------------------------------------------------------------

    def get_query_context_database(self) -> str:
        if self._schema is None:
            return self._db_manager.get_query_context_database()
        # Nombre normalizado por el dialecto (Oracle: mayúsculas), sin consultar nada: snapshot sin tipos de objeto
        return str(self._db_manager.get_schema_metadata(self._schema, kinds=frozenset()).schema)

    def get_ddl(self, table_name: str, /, *, schema: str | None = None) -> str:
        resolved: str | None = schema or self._schema
        if resolved is None:
            return self._db_manager.get_ddl(table_name)
        return self._db_manager.get_ddl(table_name, schema=resolved)

    def get_schema_metadata(self, schema: str | None = None, **kwargs: Any) -> Any:
        """Lectura por lotes del manager (ADR-003); de ella salen todas las lecturas por objeto de la sesión."""
        return self._db_manager.get_schema_metadata(schema or self._schema, **kwargs)

    # --- Métodos de metadata opcional delegados --------------------------------

    def get_database_version(self) -> Any:
        return self._db_manager.get_database_version()

    def get_database_charset_collation(self) -> Any:
        return self._db_manager.get_database_charset_collation()

    def get_columns_charset_collation(self, table_name: str, /, *, schema: str | None = None) -> Any:
        resolved: str | None = schema or self._schema
        if resolved is None:
            return self._db_manager.get_columns_charset_collation(table_name)
        return self._db_manager.get_columns_charset_collation(table_name, schema=resolved)

    # --- Consultas del inventario de almacenamiento (StorageInventoryManagerProtocol) ---

    def get_storage_rows(self, query_name: str, **params: Any) -> Any:
        if self._schema is not None:
            params.setdefault("schema", self.get_query_context_database())
        return self._db_manager.get_storage_rows(query_name, **params)

    # --- Condiciones del motor (EngineReadinessSourcePort, opcional) ---------------

    def get_engine_readiness(self) -> EngineReadinessReportView | None:
        """Verificación del motor del manager; ``None`` si el origen no la ofrece."""
        if isinstance(self._db_manager, EngineReadinessSourcePort):
            return self._db_manager.get_engine_readiness()
        return None
