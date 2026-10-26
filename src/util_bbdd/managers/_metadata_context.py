"""Resolución de contextos metadata y generación de claves de caché (patrón: Resolver + Factory)."""

from __future__ import annotations

from typing import Any

from ..connection.config import HSQLDBConnectionConfig, PostgreSQLConnectionConfig, SQLServerConnectionConfig

#: Schema de metadatos cuando ``conn_params`` no trae ``schema``: el default de cada ``*Config``.
_DEFAULT_SCHEMA: dict[str, str] = {
    "postgresql": str(PostgreSQLConnectionConfig.schema),
    "sqlserver": SQLServerConnectionConfig.schema,
    "hsqldb": HSQLDBConnectionConfig.schema,
}


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
            # ``schema`` (4.1.0, util_bbdd_web G21) elige otro owner con la misma conexión; sin él, el usuario
            oracle_owner: str = str(conn_params.get("schema") or conn_params.get("user", "")).strip()
            # Oracle guarda en mayúsculas los nombres sin comillas: «bench» y «BENCH» son el mismo owner (H-18)
            if len(oracle_owner) > 1 and oracle_owner.startswith('"') and oracle_owner.endswith('"'):
                oracle_owner = oracle_owner[1:-1]
            else:
                oracle_owner = oracle_owner.upper()
            context_database = oracle_owner or context_database
        elif db_type in _DEFAULT_SCHEMA:
            # Sin ``schema`` explícito, el schema por defecto de ``*Config`` (no el nombre de la BD): igual en sync,
            # donde el builder ya lo inyectaba, y en async (drivers-connections-audit B1, v0.37.0).
            explicit_context: str = str(conn_params.get("schema") or "").strip()
            context_database = explicit_context or _DEFAULT_SCHEMA[db_type]

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
