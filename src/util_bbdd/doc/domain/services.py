"""Servicios puros de dominio para decisiones de documentación."""

from __future__ import annotations

from typing import Any


class DocumentationContextDomainService:
    """Resuelve contexto lógico de base de datos de forma determinista."""

    @staticmethod
    def resolve_database_context(
        *,
        db_type: str,
        database: str,
        conn_params: dict[str, Any],
        query_context_database: str,
    ) -> str:
        """Resuelve el identificador mostrado en generadores y metadatos."""
        resolved_context: str = str(query_context_database or "").strip()
        if resolved_context:
            return resolved_context

        normalized_db_type: str = str(db_type or "").strip().lower() or "unknown"
        database_value: str = str(database or "").strip()
        user_value: str = str(conn_params.get("user", "") or "").strip()
        schema_value: str = str(conn_params.get("schema", "") or "").strip()

        context_resolver: dict[str, str] = {
            "oracle": user_value or database_value or normalized_db_type,
            "postgresql": schema_value or database_value or "public",
            "hsqldb": schema_value or database_value or "PUBLIC",
            "sqlserver": schema_value or database_value or "dbo",
            "sqlite": database_value or normalized_db_type,
        }

        return context_resolver.get(normalized_db_type, database_value or user_value or normalized_db_type)


class DocumentationGraphDomainService:
    """Reglas de dominio para reutilización de generador de grafos."""

    @staticmethod
    def should_share_graph_generator(*, formatos: list[str], print_config: dict[str, Any]) -> bool:
        """Indica si Word y HTML pueden reutilizar un único generador de grafos."""
        if not {"word", "html"}.issubset(set(formatos)):
            return False
        graph_cfg: dict[str, Any] = print_config.get("grafo", {})
        return bool(graph_cfg.get("enabled", False))
