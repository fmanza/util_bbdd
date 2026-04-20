"""Resolución de contextos metadata y generación de claves de caché (patrón: Resolver + Factory)."""

from __future__ import annotations

from typing import Any


class MetadataContextResolver:
    """Resuelve contextos (schema/database) para queries de metadata según BD type.

    Centraliza la lógica de contextualización que varía por motor de BD,
    facilitando testing y mantenimiento.
    """

    @staticmethod
    def get_context_database(
        *,
        db_type: str,
        database: str,
        conn_params: dict[str, Any],
    ) -> str:
        """Resuelve el contexto schema/database para queries de metadata.

        Args:
            db_type: Tipo de base de datos (oracle, postgresql, etc.)
            database: Nombre de BD base
            conn_params: Parámetros de conexión específicos por BD

        Returns:
            str: Contexto resuelto (schema/database según BD)
        """
        context_database: str = str(database or "").strip()

        if db_type == "oracle":
            oracle_user: str = str(conn_params.get("user", "")).strip()
            context_database = oracle_user or context_database
        elif db_type == "postgresql":
            explicit_context: str = str(conn_params.get("schema", "")).strip()
            context_database = explicit_context or context_database or "public"
        elif db_type == "hsqldb":
            explicit_context = str(conn_params.get("schema", "")).strip()
            context_database = explicit_context or context_database or "PUBLIC"
        elif db_type == "sqlserver":
            explicit_context = str(conn_params.get("schema", "")).strip()
            context_database = explicit_context or context_database or "dbo"

        return context_database

    @staticmethod
    def get_context_label(db_type: str) -> str:
        """Devuelve la etiqueta descriptiva del contexto metadata.

        Args:
            db_type: Tipo de base de datos

        Returns:
            str: Etiqueta ("owner/schema" para Oracle, "database" para el resto)
        """
        return "owner/schema" if db_type == "oracle" else "database"

    @staticmethod
    def add_context_params(
        *,
        db_type: str,
        params: dict[str, Any],
        context: str | None,
    ) -> dict[str, Any]:
        """Añade parámetros de contexto metadata según el motor.

        Args:
            db_type: Tipo de base de datos
            params: Parámetros de query actuales
            context: Contexto (schema/database) a añadir

        Returns:
            dict[str, Any]: Parámetros extendidos con contexto
        """
        if not context or db_type == "mariadb":
            return params
        if db_type in {"oracle", "sqlserver"}:
            params["esquema"] = context
        if db_type in {"postgresql", "hsqldb", "sqlserver"}:
            params["database"] = context
        return params


class CacheKeyFactory:
    """Generador de claves normalizadas para caché de metadata (patrón: Factory).

    Proporciona claves coherentes y normalizadas para todas las cachés,
    facilitando mantenimiento y búsqueda de bugs.
    """

    @staticmethod
    def context_key(context_database: str) -> str:
        """Normaliza la clave de contexto para cachés.

        Args:
            context_database: Contexto a normalizar

        Returns:
            str: Clave normalizada
        """
        return str(context_database or "")

    @staticmethod
    def table_key(context_database: str, table_name: str) -> tuple[str, str]:
        """Construye clave de caché por tabla.

        Args:
            context_database: Contexto (schema/database)
            table_name: Nombre de tabla

        Returns:
            tuple[str, str]: (contexto, tabla)
        """
        return (CacheKeyFactory.context_key(context_database), str(table_name or ""))

    @staticmethod
    def routine_key(context_database: str, routine_name: str, routine_type: str) -> tuple[str, str, str]:
        """Construye clave de caché por rutina.

        Args:
            context_database: Contexto (schema/database)
            routine_name: Nombre de rutina
            routine_type: Tipo de rutina (PROCEDURE, FUNCTION, etc.)

        Returns:
            tuple[str, str, str]: (contexto, rutina, tipo)
        """
        return (
            CacheKeyFactory.context_key(context_database),
            str(routine_name or ""),
            str(routine_type or "").upper(),
        )


__all__: list[str] = [
    "MetadataContextResolver",
    "CacheKeyFactory",
]
