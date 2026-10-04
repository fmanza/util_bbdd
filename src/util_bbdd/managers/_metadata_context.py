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
            # Oracle guarda en mayúsculas los nombres sin comillas: «bench» y «BENCH» son el mismo owner (H-18)
            if len(oracle_user) > 1 and oracle_user.startswith('"') and oracle_user.endswith('"'):
                oracle_user = oracle_user[1:-1]
            else:
                oracle_user = oracle_user.upper()
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
        if not context or db_type in {"mariadb", "mysql"}:
            return params
        # PostgreSQL y HSQLDB también: sus plantillas create_view/create_rutina usan {esquema} (H-10).
        if db_type in {"oracle", "sqlserver", "postgresql", "hsqldb"}:
            params["esquema"] = context
        if db_type in {"postgresql", "hsqldb", "sqlserver"}:
            params["database"] = context
        return params


__all__: list[str] = [
    "MetadataContextResolver",
]
