"""Adaptador sync de orquestación Oracle para SyncDatabaseManager.

Implementa los Protocols SourceAdapter y RoutineAdapter para introspección
de metadatos en Oracle (sync).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ._adapter_helpers import (
    build_oracle_columns_query,
    build_oracle_fk_query,
    build_oracle_indexes_query,
    build_oracle_parameters_query,
    build_oracle_pk_query,
    build_oracle_routine_body_query,
    build_oracle_routines_query,
    build_oracle_schemas_query,
    build_oracle_tables_query,
    decode_oracle_parameter_rows,
    decode_oracle_routine_body,
    decode_oracle_routine_rows,
    routine_entries_to_rows,
)
from ._manager_protocol import OracleSyncManagerProtocol
from ._oracle_models import OracleParameterDetail, OracleRoutineDetail
from .common import normalize_oracle_bind_identifier
from .constraints import OracleConstraintDefaults
from .indexes import decode_oracle_index_rows
from .tables import decode_oracle_column_rows


class OracleSyncAdapter:
    """Implementa SourceAdapter y RoutineAdapter para introspección sync de Oracle.

    Responsabilidades:
    - Extracción de metadatos: tablas, columnas, constraints, índices, routines.
    - Caché coherente a través de manager.
    - Normalización de retornos a list[tuple].

    Utiliza duck-typing; no hereda de Protocol explícitamente.
    """

    def __init__(self, manager: OracleSyncManagerProtocol) -> None:
        """Inicializa el adaptador con un manager.

        Args:
            manager: OracleSyncManagerProtocol con métodos execute_custom_many(), db_cache, etc.
        """
        self.manager = manager

    def _get_cached_entries(
        self,
        *,
        cache_lookup: Callable[[], list[Any] | None],
        cache_store: Callable[[list[Any]], None],
        fetch_entries: Callable[[], list[Any]],
        cache_hit_message: str,
        success_message: str,
        fetch_debug_message: str,
    ) -> list[Any]:
        """Abstracción genérica para caché coherente."""
        # Intentar usar el mecanismo de caché del manager si existe
        if hasattr(self.manager, "_get_cached_rows"):
            return list(
                self.manager._get_cached_rows(
                    cache_lookup=cache_lookup,
                    cache_store=cache_store,
                    fetch_rows=fetch_entries,
                    cache_hit_message=cache_hit_message,
                    success_message=success_message,
                    fetch_debug_message=fetch_debug_message,
                )
            )

        # Fallback: caché simple
        cached = cache_lookup()
        if cached is not None:
            return cached

        entries = fetch_entries()
        cache_store(entries)
        return entries

    def fetch_schemas_sync(self) -> list[tuple]:
        """Obtiene lista de schemas (owners) en modo síncrono.

        Returns:
            list[tuple]: Filas (schema_name,)
        """
        sql = build_oracle_schemas_query()
        rows = self.manager.execute_custom_many(sql, params={})
        return [(str(r[0]).strip(),) if r else ("",) for r in rows if r]

    def fetch_tables_sync(self, schema: str | None = None) -> list[tuple]:
        """Obtiene lista de tablas en modo síncrono.

        Args:
            schema: Nombre del esquema (owner).

        Returns:
            list[tuple]: Filas (table_name, table_type, table_comment)
        """
        schema_name = normalize_oracle_bind_identifier(schema) or ""
        sql = build_oracle_tables_query()
        rows = self.manager.execute_custom_many(sql, params={"owner": schema_name})
        return [(str(r[0]), str(r[1]) if len(r) > 1 else "TABLE", str(r[2]) if len(r) > 2 else "") for r in rows if r]

    def fetch_columns_sync(self, schema: str, table: str) -> list[tuple]:
        """Obtiene columnas de una tabla en modo síncrono.

        Args:
            schema: Nombre del schema (owner).
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (column_name, column_type, is_nullable,
                               ordinal_position, column_default, column_comment)
        """
        sql = build_oracle_columns_query()
        rows = self.manager.execute_custom_many(
            sql,
            params={
                "owner": normalize_oracle_bind_identifier(schema),
                "table_name": normalize_oracle_bind_identifier(table),
            },
        )
        return decode_oracle_column_rows(rows)

    def fetch_primary_keys_sync(self, schema: str, table: str) -> list[tuple]:
        """Obtiene claves primarias en modo síncrono.

        Args:
            schema: Nombre del schema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (constraint_name, column_name, ordinal_position)
        """
        sql = build_oracle_pk_query()
        rows = self.manager.execute_custom_many(
            sql,
            params={
                "owner": normalize_oracle_bind_identifier(schema),
                "table_name": normalize_oracle_bind_identifier(table),
            },
        )
        return OracleConstraintDefaults.decode_pk_rows(rows)

    def fetch_foreign_keys_sync(self, schema: str, table: str) -> list[tuple]:
        """Obtiene claves foráneas en modo síncrono.

        Args:
            schema: Nombre del schema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (constraint_name, column_name, ref_owner, ref_table,
                               ref_column, on_delete_action, on_update_action, ordinal_position)
        """
        sql = build_oracle_fk_query()
        rows = self.manager.execute_custom_many(
            sql,
            params={
                "owner": normalize_oracle_bind_identifier(schema),
                "table_name": normalize_oracle_bind_identifier(table),
            },
        )
        return OracleConstraintDefaults.decode_fk_rows(rows)

    def fetch_indexes_sync(self, schema: str, table: str) -> list[tuple]:
        """Obtiene índices en modo síncrono.

        Args:
            schema: Nombre del schema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (index_name, column_name, order_direction, uniqueness, ordinal_position)
        """
        sql = build_oracle_indexes_query()
        rows = self.manager.execute_custom_many(
            sql,
            params={
                "owner": normalize_oracle_bind_identifier(schema),
                "table_name": normalize_oracle_bind_identifier(table),
            },
        )
        return decode_oracle_index_rows(rows)

    def get_routine_details(self, schema: str | None = None) -> list[OracleRoutineDetail]:
        """Obtiene detalles de rutinas (funciones, procedimientos) del schema.

        Args:
            schema: Nombre del schema (owner).

        Returns:
            list[OracleRoutineDetail]: Rutinas decodificadas
        """
        schema_name = normalize_oracle_bind_identifier(schema) or ""
        cache_key: str = f"oracle:routines:{schema_name}"

        entries = self._get_cached_entries(
            cache_lookup=lambda: (
                self.manager.db_cache._routine_metadata_context_cache.get(cache_key)
                if hasattr(self.manager, "db_cache")
                else None
            ),
            cache_store=lambda items: (
                self.manager.db_cache._routine_metadata_context_cache.__setitem__(cache_key, list(items))
                if hasattr(self.manager, "db_cache")
                else None
            ),
            fetch_entries=lambda: decode_oracle_routine_rows(
                self.manager.execute_custom_many(
                    build_oracle_routines_query(),
                    params={"owner": schema_name},
                )
            ),
            cache_hit_message=f"♻️  Usando metadata detallada de rutinas Oracle en caché para {schema_name}",
            success_message=f"✅ {{count}} rutinas Oracle detalladas obtenidas para {schema_name}",
            fetch_debug_message=f"🔍 Obteniendo metadata detallada de rutinas Oracle para {schema_name}",
        )
        return [entry for entry in entries if isinstance(entry, OracleRoutineDetail)]

    def get_routine_parameters_details(
        self, schema: str | None = None, routine_name: str | None = None, routine_type: str = "PROCEDURE"
    ) -> list[OracleParameterDetail]:
        """Obtiene detalles de parámetros de rutinas del schema.

        Args:
            schema: Nombre del schema (owner).
            routine_name: Nombre de la rutina específica (si None, todas).
            routine_type: Tipo de rutina (PROCEDURE, FUNCTION, etc).

        Returns:
            list[OracleParameterDetail]: Parámetros decodificados
        """
        schema_name = normalize_oracle_bind_identifier(schema) or ""
        routine_name_param = normalize_oracle_bind_identifier(routine_name) or ""
        cache_key: str = f"oracle:routine_parameters:{schema_name}:{routine_name_param}"

        entries = self._get_cached_entries(
            cache_lookup=lambda: (
                self.manager.db_cache._routine_parameters_context_cache.get(cache_key)
                if hasattr(self.manager, "db_cache")
                else None
            ),
            cache_store=lambda items: (
                self.manager.db_cache._routine_parameters_context_cache.__setitem__(cache_key, list(items))
                if hasattr(self.manager, "db_cache")
                else None
            ),
            fetch_entries=lambda: decode_oracle_parameter_rows(
                schema_name,
                routine_name_param,
                routine_type,
                self.manager.execute_custom_many(
                    build_oracle_parameters_query(),
                    params={"owner": schema_name, "routine_name": routine_name_param},
                ),
            ),
            cache_hit_message=f"♻️  Usando metadata detallada de parámetros Oracle en caché para {schema_name}.{routine_name}",
            success_message=f"✅ {{count}} parámetros de rutinas Oracle obtenidos para {schema_name}.{routine_name}",
            fetch_debug_message=f"🔍 Obteniendo metadata detallada de parámetros de rutinas Oracle para {schema_name}.{routine_name}",
        )
        return [entry for entry in entries if isinstance(entry, OracleParameterDetail)]

    def get_routines_public_rows(self, schema: str | None = None) -> list[tuple]:
        """Obtiene rutinas en formato público de fila.

        Args:
            schema: Nombre del schema (owner).

        Returns:
            list[tuple]: Filas (routine_name, routine_type, routine_owner)
        """
        routines = self.get_routine_details(schema)
        return routine_entries_to_rows(routines)

    # ==================== RoutineAdapter Protocol ====================
    # MEO-01 (AUDIT_CODE 2026-09-22): OracleSyncAdapter se registra como routine adapter
    # (metadata/oracle/__init__.py) pero no implementaba estos 3 métodos del Protocol.

    def fetch_routines_sync(self, schema: str | None = None) -> list[tuple]:
        """Obtiene lista de routines en modo síncrono (RoutineAdapter).

        Args:
            schema: Nombre del esquema (owner).

        Returns:
            list[tuple]: Filas (routine_name, routine_type, routine_owner).
        """
        return self.get_routines_public_rows(schema)

    def fetch_routine_parameters_sync(self, schema: str, routine: str, routine_type: str) -> list[tuple]:
        """Obtiene parámetros de una routine en modo síncrono (RoutineAdapter).

        Args:
            schema: Nombre del esquema (owner).
            routine: Nombre de la routine.
            routine_type: Tipo de routine ('PROCEDURE' o 'FUNCTION').

        Returns:
            list[tuple]: Filas (in_out, parameter_name, data_type, ordinal_position).
        """
        details = self.get_routine_parameters_details(schema, routine, routine_type)
        return [detail.to_public_row() for detail in details]

    def fetch_routine_definition_sync(self, schema: str, routine: str, routine_type: str) -> str:
        """Obtiene el DDL completo de una routine en modo síncrono (RoutineAdapter).

        Args:
            schema: Nombre del esquema (owner).
            routine: Nombre de la routine.
            routine_type: Tipo de routine ('PROCEDURE' o 'FUNCTION').

        Returns:
            str: DDL de la rutina (p.ej. 'CREATE OR REPLACE PROCEDURE ...').
        """
        sql = build_oracle_routine_body_query()
        rows = self.manager.execute_custom_many(
            sql,
            params={
                "owner": normalize_oracle_bind_identifier(schema),
                "routine_name": normalize_oracle_bind_identifier(routine),
                "routine_type": routine_type.upper(),
            },
        )
        return decode_oracle_routine_body(routine_type, routine, rows)


__all__: list[str] = [
    "OracleSyncAdapter",
]
