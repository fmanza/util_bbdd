"""B1 (hotfix 2026-09-30): un salto de línea en texto del catálogo escrito tras ``--`` no puede salir del comentario.

Los emisores escriben comentarios de tabla, columna, vista y rutina, y nombres (FK externas, columnas omitidas,
rutinas, packages), en líneas ``-- ...``. Con ``\\n`` o ``\\r`` en ese texto, lo que seguía quedaba fuera del comentario
como SQL: DDL roto y vía de inyección desde el catálogo origen con ``MigrationPlan.execute``.
"""

from __future__ import annotations

import pytest

from util_bbdd.migrate.emitters.mariadb import MariaDBDDLEmitter
from util_bbdd.migrate.emitters.oracle import OracleDDLEmitter
from util_bbdd.migrate.emitters.postgresql import PostgreSQLDDLEmitter
from util_bbdd.migrate.emitters.sqlserver import SQLServerDDLEmitter
from util_bbdd.migrate.ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalRoutine,
    CanonicalTable,
    CanonicalView,
)

PAYLOAD = "nota\nPAYLOAD_LF\r\nPAYLOAD_CRLF\rPAYLOAD_CR"
_CLOSERS = {"'": "'", '"': '"', "`": "`", "[": "]"}


def _executable_sql(statement: str) -> str:
    """SQL fuera de comentarios ``--`` y de literales/identificadores entrecomillados (lo que el motor interpreta)."""
    code: list[str] = []
    index = 0
    while index < len(statement):
        char = statement[index]
        if statement.startswith("--", index):
            end = min((p for p in (statement.find("\n", index), statement.find("\r", index)) if p != -1), default=-1)
            index = len(statement) if end == -1 else end
        elif char in _CLOSERS:
            closer = _CLOSERS[char]
            index += 1
            while index < len(statement):
                if statement[index] == closer:
                    if statement[index + 1 : index + 2] == closer:  # comilla duplicada
                        index += 2
                        continue
                    break
                index += 1
            index += 1
        else:
            code.append(char)
            index += 1
    return "".join(code)


def _column(name: str, comment: str = "", omit: bool = False) -> CanonicalColumn:
    return CanonicalColumn(
        name=name,
        original_name=PAYLOAD if omit else name,
        oracle_type="NUMBER",
        target_type="NUMERIC(10,2)",
        nullable=True,
        default=None,
        comment=comment,
        ordinal=1,
        omit=omit,
    )


def _objects() -> tuple[list[CanonicalTable], list[CanonicalView], list[CanonicalRoutine]]:
    table = CanonicalTable(
        name="t",
        original_name="t",
        schema="s",
        columns=[_column("importe", comment=PAYLOAD), _column("rowid_col", omit=True)],
        primary_key=[],
        indexes=[],
        foreign_keys=[CanonicalFK(PAYLOAD, PAYLOAD, ["importe"], PAYLOAD, ["id"], "NO ACTION", "NO ACTION", True)],
        comment=PAYLOAD,
        warnings=[],
    )
    view = CanonicalView("v", "v", "s", "SELECT 1 AS x", [], PAYLOAD, [])
    routines = [
        CanonicalRoutine(PAYLOAD, PAYLOAD, "s", "PROCEDURE", "", "", PAYLOAD, []),
        CanonicalRoutine("p", "p", "s", "PROCEDURE", "", "", "", [], is_package_member=True, package_name=PAYLOAD),
    ]
    return [table], [view], routines


EMITTERS = [
    MariaDBDDLEmitter(charset="utf8mb4", collation="utf8mb4_bin"),
    OracleDDLEmitter(),
    PostgreSQLDDLEmitter(),
    SQLServerDDLEmitter(),
]


@pytest.mark.parametrize("emitter", EMITTERS, ids=lambda e: type(e).__name__)
def test_catalog_text_never_leaves_the_comment(emitter: object) -> None:
    tables, views, routines = _objects()
    statements = emitter.emit_statements(tables, views, routines)  # type: ignore[attr-defined]
    leaked = [s for s in statements if "PAYLOAD" in _executable_sql(s)]
    assert not leaked, leaked


@pytest.mark.parametrize("emitter", EMITTERS, ids=lambda e: type(e).__name__)
def test_comment_text_is_kept_on_one_line(emitter: object) -> None:
    tables, views, routines = _objects()
    script = "\n".join(emitter.emit_statements(tables, views, routines))  # type: ignore[attr-defined]
    assert "PAYLOAD_LF" in script and "PAYLOAD_CR" in script  # el texto se conserva, en la misma línea


def test_tokenizer_detects_the_original_bug() -> None:
    assert "PAYLOAD" in _executable_sql("-- COMMENT: a\nPAYLOAD_LF\nCREATE TABLE t (x INT)")
    assert "PAYLOAD" not in _executable_sql("COMMENT ON TABLE t IS 'a\nPAYLOAD_LF'")
