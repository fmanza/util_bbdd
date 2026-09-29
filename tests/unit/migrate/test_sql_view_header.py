"""H7: la definición de vista de SQL Server incluye la cabecera ``CREATE VIEW ... AS``; ``migrate`` necesita solo la query.

``INFORMATION_SCHEMA.VIEWS.VIEW_DEFINITION`` devolvía la cabecera y además se truncaba a 4000 caracteres (también en
SQL Server 2022): ``migrate`` emitía ``CREATE OR ALTER VIEW v AS CREATE VIEW v AS ...`` o una vista cortada.
"""

from __future__ import annotations

import pytest

from util_bbdd.migrate._compat.sql_view_header import split_create_view_header


@pytest.mark.parametrize(
    ("definition", "query"),
    [
        ("CREATE VIEW dbo.v AS SELECT 1 AS a", "SELECT 1 AS a"),
        ("CREATE VIEW [dbo].[mi vista] AS\nSELECT a FROM t", "SELECT a FROM t"),
        ('create view "dbo"."v" as select a from t;', "select a from t"),
        ("CREATE OR ALTER VIEW v\nAS\n  SELECT a FROM t", "SELECT a FROM t"),
        ("CREATE VIEW v WITH SCHEMABINDING AS SELECT a FROM dbo.t", "SELECT a FROM dbo.t"),
        ("CREATE VIEW v WITH SCHEMABINDING, VIEW_METADATA AS SELECT a FROM dbo.t", "SELECT a FROM dbo.t"),
        ("-- comentario\n/* bloque */\nCREATE VIEW v AS SELECT a FROM t", "SELECT a FROM t"),
        ("CREATE VIEW v AS SELECT a FROM t WITH CHECK OPTION", "SELECT a FROM t WITH CHECK OPTION"),
        ("CREATE VIEW v AS SELECT 'AS' AS x", "SELECT 'AS' AS x"),
        # Sin cabecera (definiciones de otros motores o ya limpias): sin cambios
        ("SELECT a FROM t", "SELECT a FROM t"),
    ],
)
def test_query_without_header(definition: str, query: str) -> None:
    assert split_create_view_header(definition).query == query


def test_explicit_column_list_is_reported() -> None:
    split = split_create_view_header("CREATE VIEW v (x, [y z]) AS SELECT a, b FROM t")
    assert split.query == "SELECT a, b FROM t"
    assert split.column_list == "x, [y z]"


def test_without_column_list() -> None:
    assert split_create_view_header("CREATE VIEW v AS SELECT a FROM t").column_list is None
