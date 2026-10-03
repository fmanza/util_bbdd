"""F4 (0.23.0): comentarios de rutinas desde MySQL/MariaDB, SQL Server y PostgreSQL.

Solo se leen: el emisor ya los escribe como ``-- COMMENT:`` en el script. No hay sentencia real (``COMMENT ON
FUNCTION``, ``sp_addextendedproperty``) porque las rutinas se copian tal cual del origen y en otro motor no se crean;
un comentario sobre una rutina que no existe haría fallar ``execute()``. Oracle no admite comentarios de rutinas.
"""

from __future__ import annotations

import pytest

from util_bbdd.migrate.emitters.postgresql import PostgreSQLDDLEmitter
from util_bbdd.migrate.extractors.mariadb import MariaDBSchemaExtractor
from util_bbdd.migrate.extractors.postgresql import PostgreSQLSchemaExtractor
from util_bbdd.migrate.extractors.sqlserver import SQLServerSchemaExtractor
from util_bbdd.migrate.ir.models import CanonicalRoutine

from ._snapshot_source import fake_manager, routine


@pytest.mark.parametrize(("comment", "expected"), [("Proc ñ", "Proc ñ"), (None, "")], ids=["con-comentario", "sin"])
def test_mariadb_routine_comment(comment: str | None, expected: str) -> None:
    manager = fake_manager("mariadb", routine("p", "PROCEDURE", "CREATE PROCEDURE p() BEGIN END", comment=comment))
    [result] = MariaDBSchemaExtractor(manager).extract_routines("s")
    assert result.comment == expected


def test_sqlserver_routine_comment_is_kept_without_body() -> None:
    manager = fake_manager(
        "sqlserver",
        routine("p", "PROCEDURE", "CREATE PROCEDURE p AS SELECT 1", comment="Proc ñ"),
        routine("cifrada", "PROCEDURE", None, comment="Sin cuerpo (WITH ENCRYPTION)"),
        routine("sin", "FUNCTION", "CREATE FUNCTION sin() ..."),
    )
    routines = {r.name: r for r in SQLServerSchemaExtractor(manager).extract_routines("dbo")}
    assert routines["p"].comment == "Proc ñ"
    assert routines["cifrada"].comment == "Sin cuerpo (WITH ENCRYPTION)" and routines["cifrada"].body == ""
    assert routines["sin"].comment == ""


def test_postgresql_routine_comment_per_overload() -> None:
    """Desde C3 cada sobrecarga lleva su comentario: el snapshot identifica la routine por su firma (antes, sin oid,
    las sobrecargas se quedaban sin comentario)."""
    manager = fake_manager(
        "postgresql",
        routine("f", "FUNCTION", "CREATE FUNCTION f() ...", comment="Función ñ"),
        routine("g", "FUNCTION", "CREATE FUNCTION g(a int) ...", signature="a integer", comment="Solo la de int"),
        routine("g", "FUNCTION", "CREATE FUNCTION g(a text) ...", signature="a text"),
        routine("h", "PROCEDURE", "CREATE PROCEDURE h() ..."),
    )
    comments = [(r.name, r.comment) for r in PostgreSQLSchemaExtractor(manager).extract_routines("s")]
    assert comments == [("f", "Función ñ"), ("g", "Solo la de int"), ("g", ""), ("h", "")]


def test_comment_goes_to_the_script_as_one_line() -> None:
    routine = CanonicalRoutine("f", "f", "s", "FUNCTION", "CREATE FUNCTION f() ...", "", "Línea 1\nLínea 2", [])
    [statement] = PostgreSQLDDLEmitter().emit_statements([], [], [routine])
    assert "-- COMMENT: Línea 1 Línea 2" in statement
    assert "COMMENT ON" not in statement
