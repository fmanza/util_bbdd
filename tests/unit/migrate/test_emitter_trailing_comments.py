"""H3: los comentarios al final de una columna (aviso de migración, comentario de columna) no deben tragarse la coma.

Los emitters añadían ``-- ...`` al final de la línea de columna y después unían las líneas con ``",\\n"``: la coma
quedaba dentro del comentario y el ``CREATE TABLE`` resultante no era válido en ningún motor.
"""

from __future__ import annotations

import pytest

from util_bbdd.migrate import (
    MariaDBDDLEmitter,
    MySQLDDLEmitter,
    OracleDDLEmitter,
    PostgreSQLDDLEmitter,
    SQLServerDDLEmitter,
)
from util_bbdd.migrate.ir.models import CanonicalColumn, CanonicalTable

EMITTERS = {
    "mariadb": lambda: MariaDBDDLEmitter(charset="utf8mb4", collation="utf8mb4_unicode_ci"),
    "mysql": lambda: MySQLDDLEmitter(charset="utf8mb4", collation="utf8mb4_0900_ai_ci"),
    "postgresql": lambda: PostgreSQLDDLEmitter(),
    "sqlserver": lambda: SQLServerDDLEmitter(),
    "oracle": lambda: OracleDDLEmitter(),
}


def _table() -> CanonicalTable:
    return CanonicalTable(
        name="t",
        original_name="t",
        schema="s",
        columns=[
            CanonicalColumn("id", "id", "INT", "INT", False, None, "", 1),
            CanonicalColumn(
                "datos",
                "datos",
                "JSONB",
                "LONGTEXT",
                True,
                None,
                "texto -- con guiones",
                2,
                ddl_comment="-- AVISO: JSONB → LONGTEXT",
            ),
            CanonicalColumn("nota", "nota", "TEXT", "TEXT", True, "'a -- b'", "", 3, ddl_comment="-- AVISO: fin"),
        ],
        primary_key=["id"],
        indexes=[],
        foreign_keys=[],
        comment="",
        warnings=[],
    )


def _definition_lines(ddl: str) -> list[str]:
    """Líneas de definición del primer CREATE TABLE (entre ``(`` y el cierre)."""
    lines = ddl.splitlines()
    start = next(i for i, line in enumerate(lines) if "CREATE TABLE" in line)
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith(")"))
    return [line for line in lines[start + 1 : end] if line.strip() and not line.strip().startswith("--")]


@pytest.mark.parametrize("engine", list(EMITTERS))
def test_comma_is_placed_before_trailing_comment(engine: str) -> None:
    definitions = _definition_lines(EMITTERS[engine]().emit([_table()]))
    for line in definitions[:-1]:
        if "AVISO" in line:
            # La coma separa la definición del comentario final; nunca al final de la línea (dentro del comentario).
            assert ", -- " in line, f"{engine}: falta la coma antes del comentario: {line!r}"
            assert not line.rstrip().endswith(","), f"{engine}: la coma quedó dentro del comentario: {line!r}"
        else:
            assert line.rstrip().endswith(","), f"{engine}: falta la coma: {line!r}"
    assert not definitions[-1].rstrip().endswith(",")


@pytest.mark.parametrize("engine", list(EMITTERS))
def test_warning_comment_is_kept(engine: str) -> None:
    ddl = EMITTERS[engine]().emit([_table()])
    assert "AVISO: JSONB → LONGTEXT" in ddl
    assert "\x00" not in ddl
