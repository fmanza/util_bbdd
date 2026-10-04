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
    """Adapta ``SyncDatabaseManager`` al contrato ``DocumentationBackendPort``.

    Delega en el manager la lectura del catálogo (snapshot por lotes y DDL de tabla), la metadata opcional y las
    consultas del inventario, y añade ``imprimir_config`` y ``get_storage_inventory_report``, que no forman parte de
    la API pública del manager pero son requeridos por el runtime documental. Las lecturas por objeto (columnas,
    claves, índices…) no pasan por aquí: ``DocumentationSession`` las sirve desde el snapshot.
    """

    def __init__(self, db_manager: DocumentationSourcePort, imprimir_config: dict[str, Any]) -> None:
        self._db_manager = db_manager
        self.imprimir_config: dict[str, Any] = imprimir_config
        self.db_type: str = db_manager.db_type
        self.database: str = db_manager.database
        self.conn_params: dict[str, Any] = db_manager.conn_params

    # --- Catálogo -----------------------------------------------------------------

    def get_query_context_database(self) -> str:
        return self._db_manager.get_query_context_database()

    def get_ddl(self, table_name: str, /) -> str:
        return self._db_manager.get_ddl(table_name)

    def get_schema_metadata(self, schema: str | None = None, **kwargs: Any) -> Any:
        """Lectura por lotes del manager (ADR-003); de ella salen todas las lecturas por objeto de la sesión."""
        return self._db_manager.get_schema_metadata(schema, **kwargs)

    # --- Métodos de metadata opcional delegados --------------------------------

    def get_database_version(self) -> Any:
        return self._db_manager.get_database_version()

    def get_database_charset_collation(self) -> Any:
        return self._db_manager.get_database_charset_collation()

    def get_columns_charset_collation(self, table_name: str, /) -> Any:
        return self._db_manager.get_columns_charset_collation(table_name)

    # --- Métodos de ejecución delegados (requeridos por StorageInventoryManagerProtocol) ---

    def get_storage_rows(self, query_name: str, **params: Any) -> Any:
        return self._db_manager.get_storage_rows(query_name, **params)

    # --- Métodos añadidos por el adaptador -------------------------------------

    def get_storage_inventory_report(self) -> dict[str, Any]:
        """Genera el informe de almacenamiento delegando al runtime especializado."""
        return get_storage_inventory_report_runtime(
            db_manager=cast(StorageInventoryManagerProtocol, self._db_manager),
            logger=logging.getLogger(__name__),
            print_config=self.imprimir_config,
        )
