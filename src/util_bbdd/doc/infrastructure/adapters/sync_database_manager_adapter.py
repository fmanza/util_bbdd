"""Adaptadores que unifican SyncDatabaseManager con el contrato documental interno."""

from __future__ import annotations

import logging

from typing import Any, cast

from ...application.ports import DocumentationSourcePort
from ..storage.runtime import (
    StorageInventoryManagerProtocol,
    get_storage_inventory_report as get_storage_inventory_report_runtime,
)


class SyncDatabaseManagerAdapter:
    """Adapta ``SyncDatabaseManager`` al contrato ``DocumentationRuntimeManagerProtocol``.

    Delega todos los métodos de introspección al manager subyacente y añade
    ``imprimir_config`` y ``get_storage_inventory_report``, que no forman
    parte de la API pública del manager pero son requeridos por el runtime
    documental.
    """

    def __init__(self, db_manager: DocumentationSourcePort, imprimir_config: dict[str, Any]) -> None:
        self._db_manager = db_manager
        self.imprimir_config: dict[str, Any] = imprimir_config
        self.db_type: str = db_manager.db_type
        self.database: str = db_manager.database
        self.conn_params: dict[str, Any] = db_manager.conn_params
        self.relationship_cache = db_manager.relationship_cache

    # --- Métodos de introspección delegados ------------------------------------

    def get_query_context_database(self) -> str:
        return self._db_manager.get_query_context_database()

    def get_tables(self) -> list[Any]:
        return self._db_manager.get_tables()

    def get_views(self) -> list[Any]:
        return self._db_manager.get_views()

    def get_routines(self) -> list[Any]:
        return self._db_manager.get_routines()

    def get_ddl(self, table_name: str, /) -> str:
        return self._db_manager.get_ddl(table_name)

    def get_view_ddl(self, view_name: str, /) -> str:
        return self._db_manager.get_view_ddl(view_name)

    def get_columns(self, table_name: str, /) -> list[Any]:
        return self._db_manager.get_columns(table_name)

    def get_routine_ddl(self, routine_name: str, routine_type: str, /) -> str:
        return self._db_manager.get_routine_ddl(routine_name, routine_type)

    def get_routine_parameters(self, routine_name: str, routine_type: str, /) -> list[Any]:
        return self._db_manager.get_routine_parameters(routine_name, routine_type)

    def get_primary_keys(self, table_name: str, /) -> list[Any]:
        return self._db_manager.get_primary_keys(table_name)

    def get_foreign_keys(self, table_name: str, /) -> list[Any]:
        return self._db_manager.get_foreign_keys(table_name)

    def get_unique_constraints(self, table_name: str, /) -> list[Any]:
        return self._db_manager.get_unique_constraints(table_name)

    def get_indices(self, table_name: str, /) -> list[Any]:
        return self._db_manager.get_indices(table_name)

    # --- Métodos de metadata opcional delegados --------------------------------

    def get_database_version(self) -> Any:
        return self._db_manager.get_database_version()

    def get_database_charset_collation(self) -> Any:
        return self._db_manager.get_database_charset_collation()

    def get_columns_charset_collation(self, table_name: str, /) -> Any:
        return self._db_manager.get_columns_charset_collation(table_name)

    # --- Métodos de ejecución delegados (requeridos por StorageInventoryManagerProtocol) ---

    def resolve_query(self, query_name: str, **params: Any) -> Any:
        return self._db_manager.resolve_query(query_name, **params)

    def execute_query_many(self, query_name: str, **params: Any) -> Any:
        return self._db_manager.execute_query_many(query_name, **params)

    def execute_custom_one(self, query: str) -> Any:
        return self._db_manager.execute_custom_one(query)

    def get_query_info(self) -> dict[str, Any]:
        return self._db_manager.get_query_info()

    # --- Métodos añadidos por el adaptador -------------------------------------

    def get_storage_inventory_report(self) -> dict[str, Any]:
        """Genera el informe de almacenamiento delegando al runtime especializado."""
        return get_storage_inventory_report_runtime(
            db_manager=cast(StorageInventoryManagerProtocol, self._db_manager),
            logger=logging.getLogger(__name__),
            print_config=self.imprimir_config,
        )
