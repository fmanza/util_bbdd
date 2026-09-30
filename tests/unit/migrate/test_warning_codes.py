"""E1 (0.22.0): todo aviso con etiqueta en ``target_type`` lleva un ``code`` estable (:data:`WarningCode`).

``target_type`` guarda el tipo destino (``TYPE``), el nombre nuevo (``IDENTIFIER``) **o** una etiqueta legible
(``"VIEW (reescrita)"``, ``"(no body)"``…). Para filtrar en código se usa ``category`` + ``code``; este test recorre el
AST de ``migrate/`` para que un aviso nuevo con etiqueta no se quede sin código.
"""

from __future__ import annotations

import ast
import re

from pathlib import Path
from typing import get_args

import pytest

from util_bbdd.migrate import MigrationWarning, WarningCode

MIGRATE = Path(__file__).resolve().parents[3] / "src" / "util_bbdd" / "migrate"
CODES = set(get_args(WarningCode))
# Tipo SQL (``CLOB``, ``NVARCHAR(MAX)``, ``IDENTITY(1,1)``): el ``target_type`` dice lo que es y no necesita código.
_SQL_TYPE = re.compile(r"^[A-Z][A-Z0-9_]*(\((\d+(,\d+)?|MAX)\))?$")


def _calls() -> list[tuple[str, ast.Call]]:
    calls = []
    for path in sorted(MIGRATE.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) in ("MigrationWarning", "_warning"):
                calls.append((f"{path.relative_to(MIGRATE)}:{node.lineno}", node))
    return calls


def _code(call: ast.Call) -> ast.expr | None:
    keywords = {k.arg: k.value for k in call.keywords}
    if getattr(call.func, "id", None) == "_warning":  # transpiler._warning(view, code, target_type, message, ...)
        return call.args[1] if len(call.args) > 1 else keywords.get("code")
    return keywords.get("code")


def _is_label(call: ast.Call) -> bool:
    keywords = {k.arg: k.value for k in call.keywords}
    target = keywords.get("target_type")
    if getattr(call.func, "id", None) == "_warning":
        return True
    if isinstance(target, ast.JoinedStr):
        return True
    return isinstance(target, ast.Constant) and (target.value == "VIEW" or not _SQL_TYPE.match(str(target.value)))


def test_every_label_warning_has_a_code() -> None:
    missing = [where for where, call in _calls() if _is_label(call) and _code(call) is None]
    assert not missing, missing


def test_codes_are_known_literals() -> None:
    used = {}
    for where, call in _calls():
        code = _code(call)
        if code is None or (isinstance(code, ast.Name) and code.id == "code"):  # el propio _warning
            continue
        assert isinstance(code, ast.Constant) and code.value in CODES, where
        used[code.value] = where
    assert set(used) == CODES, f"códigos sin uso: {sorted(CODES - set(used))}"


def test_code_defaults_to_none_and_is_last() -> None:
    warning = MigrationWarning("t", None, "TYPE", "CLOB", "m")
    assert warning.code is None
    assert MigrationWarning.__dataclass_fields__.keys() - {"code"} == {
        "table",
        "column",
        "category",
        "target_type",
        "message",
        "severity",
        "source_type",
        "proposals",
    }
    assert list(MigrationWarning.__dataclass_fields__)[-1] == "code"


@pytest.mark.parametrize(
    ("sql", "code"),
    [
        ("SELECT id FROM zzv_t", "VIEW_REWRITTEN"),
        ("SELECT id FROM zzv_t CONNECT BY PRIOR id = id2 ORDER SIBLINGS BY id", "VIEW_NOT_REWRITTEN"),
    ],
)
def test_transpiler_warnings_carry_codes(sql: str, code: str) -> None:
    pytest.importorskip("sqlglot")
    from util_bbdd.migrate.ir.models import CanonicalView
    from util_bbdd.migrate.views.transpiler import ViewTranspileContext, transpile_view

    ctx = ViewTranspileContext(source_engine="oracle", target_engine="postgresql", source_schema="S")
    view = transpile_view(CanonicalView("v", "v", "S", sql, [], "", []), ctx)
    assert code in {w.code for w in view.warnings}
    assert all(w.code is not None for w in view.warnings)
