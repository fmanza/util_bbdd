"""Protocolos genéricos para adaptadores multi-driver de introspección.

Define contratos agnósticos del motor para extracción de metadatos.
Cada motor (MariaDB, PostgreSQL, SQLite) implementa estos Protocols
sin modificar el flujo de orquestación base.

Ejemplo de uso:
    class MariaDBSyncAdapter(SourceAdapterSync, RoutineAdapterSync):
        def __init__(self, manager: DbManagerProtocol, logger: Logger, cache: MetadataCachePort):
            self.manager = manager
            self.logger = logger
            self.cache = cache

        def fetch_tables_sync(self, schema: str | None = None) -> list[tuple]:
            # Implementación específica MariaDB (sync)
            pass

    class MariaDBAsyncAdapter(SourceAdapterAsync, RoutineAdapterAsync):
        async def fetch_tables_async(self, schema: str | None = None) -> list[tuple]:
            # Implementación específica MariaDB (async)
            pass
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ...results import Rows

__all__: list[str] = [
    "EngineMetadataAdapterAsync",
    "EngineMetadataAdapterSync",
    "MetadataCachePort",
    "SourceAdapterSync",
    "SourceAdapterAsync",
    "RoutineAdapterSync",
    "RoutineAdapterAsync",
]


@runtime_checkable
class MetadataCachePort(Protocol):
    """Contrato de invalidación de caché que los adaptadores reciben del manager.

    Lo cumple estructuralmente ``managers._manager_cache_service.CacheService``. Los adaptadores dependen de este
    contrato y no del manager: ``metadata/`` no importa de una capa superior (Regla #6). Los parámetros son
    posicionales: mypy no compara sus nombres al comprobar un Protocol, así que el contrato no puede apoyarse en ellos.
    """

    def clear_all(self) -> None: ...

    def clear_table(self, context: str, table: str, /) -> None: ...

    def clear_routine(self, context: str, routine: str, routine_type: str | None = None, /) -> None: ...

    def clear_context(self, context: str, /) -> None: ...


@runtime_checkable
class SourceAdapterSync(Protocol):
    """Adapter agnóstico de motor para introspección sync de BD: tablas, columnas, constraints, índices.

    Responsabilidades:
    - Extraer metadatos de tablas, columnas, PK, FK, índices.
    - Devolver tuples normalizadas (no objetos del driver).
    - Cachear resultados internamente.
    - Loguear operaciones.
    """

    def fetch_tables_sync(self, schema: str | None = None) -> list[tuple]:
        """Obtiene lista de tablas en modo síncrono.

        Args:
            schema: Nombre del esquema/database (opcional, engine.current_database() por defecto).

        Returns:
            list[tuple]: Filas (table_name, table_type, table_comment, ...)
        """
        ...

    def fetch_columns_sync(self, schema: str, table: str) -> list[tuple]:
        """Obtiene columnas de una tabla en modo síncrono.

        Args:
            schema: Nombre del esquema/database.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (column_name, column_type, is_nullable, column_key,
                               column_default, extra, column_comment, ...)
        """
        ...

    def fetch_primary_keys_sync(self, schema: str, table: str) -> list[tuple]:
        """Obtiene claves primarias en modo síncrono.

        Args:
            schema: Nombre del esquema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (column_name, ordinal_position, ...)
        """
        ...

    def fetch_foreign_keys_sync(self, schema: str, table: str) -> list[tuple]:
        """Obtiene claves foráneas en modo síncrono.

        Args:
            schema: Nombre del esquema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (constraint_name, column_name,
                               referenced_table_schema, referenced_table_name,
                               referenced_column_name, ...)
        """
        ...

    def fetch_indexes_sync(self, schema: str, table: str) -> list[tuple]:
        """Obtiene índices de una tabla en modo síncrono.

        Args:
            schema: Nombre del esquema.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas (index_name, column_name, seq_in_index,
                               is_unique, index_type, ...)
        """
        ...


@runtime_checkable
class SourceAdapterAsync(Protocol):
    """Adapter agnóstico de motor para introspección async de BD: tablas, columnas, constraints, índices."""

    async def fetch_tables_async(self, schema: str | None = None) -> list[tuple]:
        """Obtiene lista de tablas en modo asíncrono.

        Args:
            schema: Nombre del esquema/database (opcional).

        Returns:
            list[tuple]: Filas (table_name, table_type, table_comment, ...)
        """
        ...

    async def fetch_columns_async(self, schema: str, table: str) -> list[tuple]:
        """Obtiene columnas de una tabla en modo asíncrono.

        Args:
            schema: Nombre del esquema/database.
            table: Nombre de la tabla.

        Returns:
            list[tuple]: Filas de columnas.
        """
        ...

    async def fetch_primary_keys_async(self, schema: str, table: str) -> list[tuple]:
        """Obtiene claves primarias en modo asíncrono."""
        ...

    async def fetch_foreign_keys_async(self, schema: str, table: str) -> list[tuple]:
        """Obtiene claves foráneas en modo asíncrono."""
        ...

    async def fetch_indexes_async(self, schema: str, table: str) -> list[tuple]:
        """Obtiene índices de una tabla en modo asíncrono."""
        ...


@runtime_checkable
class RoutineAdapterSync(Protocol):
    """Adapter agnóstico de motor para introspección sync de routines: procedures, functions."""

    def fetch_routines_sync(self, schema: str | None = None) -> list[tuple]:
        """Obtiene lista de routines (procedures, functions) en modo síncrono.

        Args:
            schema: Nombre del esquema/database (opcional).

        Returns:
            list[tuple]: Filas (routine_name, routine_type, routine_comment, ...)
        """
        ...

    def fetch_routine_parameters_sync(self, schema: str, routine: str, routine_type: str) -> list[tuple]:
        """Obtiene parámetros de una routine en modo síncrono.

        Args:
            schema: Nombre del esquema.
            routine: Nombre de la routine.
            routine_type: Tipo de routine ('PROCEDURE' o 'FUNCTION').

        Returns:
            list[tuple]: Filas (parameter_name, parameter_type, data_type, ...)
        """
        ...

    def fetch_routine_definition_sync(self, schema: str, routine: str, routine_type: str) -> str:
        """Obtiene el DDL completo de una routine en modo síncrono.

        Args:
            schema: Nombre del esquema.
            routine: Nombre de la routine.
            routine_type: Tipo de routine ('PROCEDURE' o 'FUNCTION').

        Returns:
            str: DDL de la routine (p.ej. 'CREATE PROCEDURE ...')."""
        ...


@runtime_checkable
class RoutineAdapterAsync(Protocol):
    """Adapter agnóstico de motor para introspección async de routines: procedures, functions."""

    async def fetch_routines_async(self, schema: str | None = None) -> list[tuple]:
        """Obtiene lista de routines en modo asíncrono.

        Args:
            schema: Nombre del esquema/database (opcional).

        Returns:
            list[tuple]: Filas de routines.
        """
        ...

    async def fetch_routine_parameters_async(self, schema: str, routine: str, routine_type: str) -> list[tuple]:
        """Obtiene parámetros de una routine en modo asíncrono."""
        ...

    async def fetch_routine_definition_async(self, schema: str, routine: str, routine_type: str) -> str:
        """Obtiene el DDL completo de una routine en modo asíncrono."""
        ...


@runtime_checkable
class EngineMetadataAdapterSync(Protocol):
    """Lecturas de metadatos especializadas por motor que los managers delegan en su adapter (sync).

    Desde E2 de ADR-003 los managers ya no los usan (leen el snapshot de ``metadata/``); se retiran en E2c.
    """

    def fetch_routines(self, context_database: str, /) -> Rows:
        """Rutinas del contexto."""
        ...

    def fetch_view_from_information_schema(self, database: str, view_name: str, /) -> str:
        """DDL de una vista."""
        ...

    def fetch_columns_safe(self, context_database: str, table: str, /) -> Rows:
        """Columnas de una tabla, leídas de forma segura frente a problemas de charset."""
        ...

    def fetch_routine_parameters_public_rows(self, *, database: str, routine_name: str, routine_type: str) -> Rows:
        """Parámetros públicos de una rutina."""
        ...

    def fetch_routine_from_information_schema(self, database: str, routine_name: str, routine_type: str) -> str:
        """DDL de una rutina."""
        ...


@runtime_checkable
class EngineMetadataAdapterAsync(Protocol):
    """Lecturas de metadatos especializadas por motor que los managers delegan en su adapter (async).

    Mismo contrato que :class:`EngineMetadataAdapterSync` con métodos ``async``.
    """

    async def fetch_routines(self, context_database: str, /) -> Rows:
        """Rutinas del contexto."""
        ...

    async def fetch_view_from_information_schema(self, database: str, view_name: str, /) -> str:
        """DDL de una vista."""
        ...

    async def fetch_columns_safe(self, context_database: str, table: str, /) -> Rows:
        """Columnas de una tabla, leídas de forma segura frente a problemas de charset."""
        ...

    async def fetch_routine_parameters_public_rows(
        self, *, database: str, routine_name: str, routine_type: str
    ) -> Rows:
        """Parámetros públicos de una rutina."""
        ...

    async def fetch_routine_from_information_schema(self, database: str, routine_name: str, routine_type: str) -> str:
        """DDL de una rutina."""
        ...
