"""Clases base reutilizables para adaptadores multi-driver.

Proporciona utilidades compartidas: logging, caché, generación de keys,
normalizaciones genéricas. Los adaptadores concretos heredan estas utilidades
sin duplicar lógica.

Responsabilidad: encapsular patrones comunes entre MariaDB, PostgreSQL, SQLite, etc.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from logging import Logger

    from ...managers._manager_cache_service import CacheService

__all__: list[str] = ["BaseSourceAdapter", "BaseRoutineAdapter"]


class BaseSourceAdapter:
    """Clase base con utilidades compartidas para adaptadores de tablas/columnas/constraints.

    Subclases concretas (MariaDBSourceAdapter, PostgreSQLSourceAdapter, etc.)
    heredan: logging, caché, normalización de keys.
    """

    def __init__(self, logger: Logger, cache_service: CacheService):
        """Inicializa el adapter base.

        Args:
            logger: Logger inyectado para trazabilidad.
            cache_service: CacheService inyectado para caché coherente.
        """
        self.logger = logger
        self.cache = cache_service

    def _get_cache_key_tables(self, schema: str) -> str:
        """Genera una clave genérica de caché para tablas de un schema.

        Args:
            schema: Nombre del esquema/database.

        Returns:
            str: Clave única por motor e schema (p.ej. 'tables:mariadb:mydb').
        """
        return f"tables:{schema}"

    def _get_cache_key_columns(self, schema: str, table: str) -> str:
        """Genera una clave genérica de caché para columnas de una tabla.

        Args:
            schema: Nombre del esquema.
            table: Nombre de la tabla.

        Returns:
            str: Clave única (p.ej. 'columns:mydb:users').
        """
        return f"columns:{schema}:{table}"

    def _get_cache_key_primary_keys(self, schema: str, table: str) -> str:
        """Genera una clave genérica de caché para PKs.

        Args:
            schema: Nombre del esquema.
            table: Nombre de la tabla.

        Returns:
            str: Clave única (p.ej. 'pk:mydb:users').
        """
        return f"pk:{schema}:{table}"

    def _get_cache_key_foreign_keys(self, schema: str, table: str) -> str:
        """Genera una clave genérica de caché para FKs.

        Args:
            schema: Nombre del esquema.
            table: Nombre de la tabla.

        Returns:
            str: Clave única (p.ej. 'fk:mydb:users').
        """
        return f"fk:{schema}:{table}"

    def _get_cache_key_indexes(self, schema: str, table: str) -> str:
        """Genera una clave genérica de caché para índices.

        Args:
            schema: Nombre del esquema.
            table: Nombre de la tabla.

        Returns:
            str: Clave única (p.ej. 'idx:mydb:users').
        """
        return f"idx:{schema}:{table}"

    def _log_fetch_start(self, metadata_type: str, schema: str, table: str | None = None) -> None:
        """Loguea el inicio de una extracción de metadatos.

        Args:
            metadata_type: Tipo de metadato ('tables', 'columns', 'pk', 'fk', 'indexes').
            schema: Nombre del esquema.
            table: Nombre de la tabla (opcional, solo para tipos relacionados con tablas).
        """
        if table:
            self.logger.debug(f"🔍 Obteniendo {metadata_type} para {schema}.{table}")
        else:
            self.logger.debug(f"🔍 Obteniendo {metadata_type} del schema {schema}")

    def _log_fetch_success(self, metadata_type: str, schema: str, count: int, table: str | None = None) -> None:
        """Loguea el éxito de una extracción de metadatos.

        Args:
            metadata_type: Tipo de metadato.
            schema: Nombre del esquema.
            count: Número de filas obtenidas.
            table: Nombre de la tabla (opcional).
        """
        if table:
            self.logger.debug(f"✅ {count} {metadata_type} obtenidos para {schema}.{table}")
        else:
            self.logger.debug(f"✅ {count} {metadata_type} obtenidos del schema {schema}")

    def _log_cache_hit(self, cache_key: str) -> None:
        """Loguea un acierto de caché.

        Args:
            cache_key: Clave de caché consultada.
        """
        self.logger.debug(f"♻️  Usando caché para: {cache_key}")

    def _log_cache_miss(self, cache_key: str) -> None:
        """Loguea un fallo de caché.

        Args:
            cache_key: Clave de caché consultada.
        """
        self.logger.debug(f"💾 Almacenando caché para: {cache_key}")

    def _log_error(self, metadata_type: str, error: Exception, schema: str, table: str | None = None) -> None:
        """Loguea un error durante la extracción de metadatos.

        Args:
            metadata_type: Tipo de metadato.
            error: Excepción capturada.
            schema: Nombre del esquema.
            table: Nombre de la tabla (opcional).
        """
        context = f"{schema}.{table}" if table else schema
        self.logger.error(f"❌ Error obteniendo {metadata_type} para {context}: {error}")


class BaseRoutineAdapter:
    """Clase base con utilidades compartidas para adaptadores de routines.

    Subclases concretas heredan: logging, caché, parsing de routines.
    """

    def __init__(self, logger: Logger, cache_service: CacheService):
        """Inicializa el adapter base para routines.

        Args:
            logger: Logger inyectado.
            cache_service: CacheService inyectado.
        """
        self.logger = logger
        self.cache = cache_service

    def _get_cache_key_routines(self, schema: str) -> str:
        """Genera una clave genérica de caché para routines de un schema.

        Args:
            schema: Nombre del esquema/database.

        Returns:
            str: Clave única (p.ej. 'routines:mydb').
        """
        return f"routines:{schema}"

    def _get_cache_key_routine_parameters(self, schema: str, routine: str, routine_type: str) -> str:
        """Genera una clave genérica de caché para parámetros de una routine.

        Args:
            schema: Nombre del esquema.
            routine: Nombre de la routine.
            routine_type: Tipo de routine ('PROCEDURE' o 'FUNCTION').

        Returns:
            str: Clave única (p.ej. 'params:mydb:sp_users:PROCEDURE').
        """
        return f"params:{schema}:{routine}:{routine_type.upper()}"

    def _get_cache_key_routine_definition(self, schema: str, routine: str, routine_type: str) -> str:
        """Genera una clave genérica de caché para definición de routine.

        Args:
            schema: Nombre del esquema.
            routine: Nombre de la routine.
            routine_type: Tipo de routine.

        Returns:
            str: Clave única (p.ej. 'def:mydb:sp_users:PROCEDURE').
        """
        return f"def:{schema}:{routine}:{routine_type.upper()}"

    def _log_fetch_routine_start(self, schema: str) -> None:
        """Loguea el inicio de extracción de routines.

        Args:
            schema: Nombre del esquema.
        """
        self.logger.debug(f"🔍 Obteniendo routines del schema {schema}")

    def _log_fetch_routine_success(self, schema: str, count: int) -> None:
        """Loguea el éxito de extracción de routines.

        Args:
            schema: Nombre del esquema.
            count: Número de routines obtenidas.
        """
        self.logger.debug(f"✅ {count} routines obtenidas del schema {schema}")

    def _log_routine_cache_hit(self, cache_key: str) -> None:
        """Loguea un acierto de caché para routines.

        Args:
            cache_key: Clave de caché consultada.
        """
        self.logger.debug(f"♻️  Usando caché para routines: {cache_key}")

    def _log_routine_error(self, error: Exception, schema: str, routine: str | None = None) -> None:
        """Loguea un error durante extracción de routines.

        Args:
            error: Excepción capturada.
            schema: Nombre del esquema.
            routine: Nombre de la routine (opcional).
        """
        context = f"{schema}.{routine}" if routine else schema
        self.logger.error(f"❌ Error obteniendo routines para {context}: {error}")
