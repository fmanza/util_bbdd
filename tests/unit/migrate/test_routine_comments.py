"""F4 (0.23.0): comentarios de rutinas desde MySQL/MariaDB, SQL Server y PostgreSQL.

Solo se leen: el emisor ya los escribe como ``-- COMMENT:`` en el script. No hay sentencia real (``COMMENT ON
FUNCTION``, ``sp_addextendedproperty``) porque las rutinas se copian tal cual del origen y en otro motor no se crean;
un comentario sobre una rutina que no existe haría fallar ``execute()``. Oracle no admite comentarios de rutinas.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from util_bbdd.metadata.mariadb.tables import fetch_routines_sql as mariadb_routines_sql
from util_bbdd.metadata.postgresql.routines import (
    fetch_routine_comments_for_schema_sql,
    fetch_routines_sql as pg_routines_sql,
)
from util_bbdd.metadata.sqlserver._adapter_helpers import build_sqlserver_routines_query
from util_bbdd.metadata.sqlserver.tables import fetch_routine_bodies_for_schema_sql
from util_bbdd.migrate.emitters.postgresql import PostgreSQLDDLEmitter
from util_bbdd.migrate.extractors.mariadb import MariaDBSchemaExtractor
from util_bbdd.migrate.extractors.postgresql import PostgreSQLSchemaExtractor
from util_bbdd.migrate.extractors.sqlserver import SQLServerSchemaExtractor
from util_bbdd.migrate.ir.models import CanonicalRoutine


def _manager(results: dict[str, list[tuple[Any, ...]]]) -> MagicMock:
    """Manager simulado: responde por el texto exacto de cada consulta."""
    manager = MagicMock()
    manager.execute_custom_many.side_effect = lambda sql, params: results.get(sql, [])
    return manager


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        (("p", "PROCEDURE", "s", "BEGIN END", None, " Proc ñ "), "Proc ñ"),
        (("p", "PROCEDURE", "s", "BEGIN END", None, ""), ""),
        (("p", "PROCEDURE", "s", "BEGIN END", None), ""),  # consulta anterior, sin ROUTINE_COMMENT
    ],
    ids=["con-comentario", "vacio", "sin-columna"],
)
def test_mariadb_routine_comment(row: tuple[Any, ...], expected: str) -> None:
    [routine] = MariaDBSchemaExtractor(_manager({mariadb_routines_sql(): [row]})).extract_routines("s")
    assert routine.comment == expected


def test_sqlserver_routine_comment_is_kept_without_body() -> None:
    manager = _manager(
        {
            build_sqlserver_routines_query(): [("p", "PROCEDURE"), ("cifrada", "PROCEDURE"), ("sin", "FUNCTION")],
            fetch_routine_bodies_for_schema_sql(): [
                ("p", "CREATE PROCEDURE p AS SELECT 1", "Proc ñ"),
                ("cifrada", None, "Sin cuerpo (WITH ENCRYPTION)"),
                ("sin", "CREATE FUNCTION sin() ...", None),
            ],
        }
    )
    routines = {r.name: r for r in SQLServerSchemaExtractor(manager).extract_routines("dbo")}
    assert routines["p"].comment == "Proc ñ"
    assert routines["cifrada"].comment == "Sin cuerpo (WITH ENCRYPTION)" and routines["cifrada"].body == ""
    assert routines["sin"].comment == ""


def test_postgresql_routine_comment_skips_overloads() -> None:
    routine_rows = [
        ("f", "FUNCTION", "s", "CREATE FUNCTION f() ...", "integer"),
        ("g", "FUNCTION", "s", "CREATE FUNCTION g(a int) ...", "integer"),
        ("g", "FUNCTION", "s", "CREATE FUNCTION g(a text) ...", "integer"),
        ("h", "PROCEDURE", "s", "CREATE PROCEDURE h() ...", ""),
    ]
    manager = _manager(
        {
            pg_routines_sql("s"): routine_rows,
            fetch_routine_comments_for_schema_sql(): [("f", " Función ñ "), ("g", "Solo la de int")],
        }
    )
    comments = [(r.name, r.comment) for r in PostgreSQLSchemaExtractor(manager).extract_routines("s")]
    # g tiene dos sobrecargas: sin oid no se sabe de cuál es el comentario, así que ninguna lo lleva.
    assert comments == [("f", "Función ñ"), ("g", ""), ("g", ""), ("h", "")]


def test_postgresql_without_routines_does_not_query_comments() -> None:
    manager = _manager({})
    assert PostgreSQLSchemaExtractor(manager).extract_routines("s") == []
    assert manager.execute_custom_many.call_count == 1


def test_comment_goes_to_the_script_as_one_line() -> None:
    routine = CanonicalRoutine("f", "f", "s", "FUNCTION", "CREATE FUNCTION f() ...", "", "Línea 1\nLínea 2", [])
    [statement] = PostgreSQLDDLEmitter().emit_statements([], [], [routine])
    assert "-- COMMENT: Línea 1 Línea 2" in statement
    assert "COMMENT ON" not in statement
