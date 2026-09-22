"""Tests para el contrato de transform_views documentado en transformers/base.py."""

from __future__ import annotations

import inspect

from util_bbdd.migrate.transformers.mariadb_to_oracle import MariaDBToOracleTransformer
from util_bbdd.migrate.transformers.mariadb_to_postgresql import MariaDBToPostgreSQLTransformer
from util_bbdd.migrate.transformers.mariadb_to_sqlserver import MariaDBToSQLServerTransformer
from util_bbdd.migrate.transformers.oracle_to_mariadb import OracleToMariaDBTransformer
from util_bbdd.migrate.transformers.oracle_to_postgresql import OracleToPostgreSQLTransformer
from util_bbdd.migrate.transformers.oracle_to_sqlserver import OracleToSQLServerTransformer
from util_bbdd.migrate.transformers.postgresql_to_mariadb import PostgreSQLToMariaDBTransformer
from util_bbdd.migrate.transformers.postgresql_to_oracle import PostgreSQLToOracleTransformer
from util_bbdd.migrate.transformers.postgresql_to_sqlserver import PostgreSQLToSQLServerTransformer
from util_bbdd.migrate.transformers.sqlserver_to_mariadb import SQLServerToMariaDBTransformer
from util_bbdd.migrate.transformers.sqlserver_to_oracle import SQLServerToOracleTransformer
from util_bbdd.migrate.transformers.sqlserver_to_postgresql import SQLServerToPostgreSQLTransformer

_ORACLE_SOURCE_TRANSFORMERS = {
    OracleToMariaDBTransformer,
    OracleToPostgreSQLTransformer,
    OracleToSQLServerTransformer,
}

_ALL_TRANSFORMERS = {
    MariaDBToOracleTransformer,
    MariaDBToPostgreSQLTransformer,
    MariaDBToSQLServerTransformer,
    OracleToMariaDBTransformer,
    OracleToPostgreSQLTransformer,
    OracleToSQLServerTransformer,
    PostgreSQLToMariaDBTransformer,
    PostgreSQLToOracleTransformer,
    PostgreSQLToSQLServerTransformer,
    SQLServerToMariaDBTransformer,
    SQLServerToOracleTransformer,
    SQLServerToPostgreSQLTransformer,
}


def _uses_oracle_view_rewriter(transformer_cls: type) -> bool:
    """True si _transform_view del transformer invoca rewrite_oracle_view."""
    transform_view = vars(transformer_cls).get("_transform_view")
    if transform_view is None:
        return False
    return "rewrite_oracle_view" in inspect.getsource(transform_view)


class TestTransformViewsOracleRewritingScope:
    """MIG-06 (AUDIT_CODE 2026-09-22): el docstring de SchemaTransformer.transform_views
    describía la reescritura de SQL Oracle como si aplicara a los 12 pares
    origen→destino. transform_views en sí (BaseTransformer) nunca se sobrescribe —
    es el hook privado _transform_view el que varía, y solo los 3 pares con Oracle
    como origen invocan rewrite_oracle_view desde ese hook (otros pares pueden
    sobrescribir _transform_view por motivos ajenos a la reescritura SQL, p.ej.
    advertencias de revisión manual). Este test ata esa afirmación del docstring
    al código real para detectar drift."""

    def test_transform_views_itself_is_never_overridden(self) -> None:
        for transformer_cls in _ALL_TRANSFORMERS:
            assert "transform_views" not in vars(transformer_cls), (
                f"{transformer_cls.__name__} sobrescribe transform_views directamente; "
                "el hook de personalización esperado es _transform_view."
            )

    def test_only_oracle_source_pairs_apply_oracle_sql_rewriting(self) -> None:
        assert len(_ALL_TRANSFORMERS) == 12
        for transformer_cls in _ALL_TRANSFORMERS:
            uses_rewriter = _uses_oracle_view_rewriter(transformer_cls)
            expected = transformer_cls in _ORACLE_SOURCE_TRANSFORMERS
            assert uses_rewriter == expected, (
                f"{transformer_cls.__name__}: usa rewrite_oracle_view={uses_rewriter}, "
                f"se esperaba {expected} (¿origen Oracle?)"
            )
