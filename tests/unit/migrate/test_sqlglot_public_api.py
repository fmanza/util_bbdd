"""Hotfix (0.23.0): ``migrate`` solo usa la API pública de sqlglot para el tipo base de los nodos.

Desde sqlglot 30 la clase base pública es ``exp.Expr``; ``exp.Expression`` se importa en ``sqlglot.expressions`` en el
bloque que el propio sqlglot titula «Explicitly import private helpers (not exported by star imports)». Pylance lo
marca (``reportPrivateImportUsage``) y una versión 30.x podría retirarlo: los ``cast(exp.Expression, ...)`` fallarían en
tiempo de ejecución. Comprobado que ``Expr`` existe ya en 30.0.0 (rango de ``pyproject.toml``: ``sqlglot>=30,<31``).
"""

from __future__ import annotations

import re

from pathlib import Path

import pytest

MIGRATE = Path(__file__).resolve().parents[3] / "src" / "util_bbdd" / "migrate"


def test_migrate_does_not_use_the_private_expression_class() -> None:
    uses = [
        f"{path.relative_to(MIGRATE)}:{number}"
        for path in sorted(MIGRATE.rglob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if re.search(r"\bexp\.Expression\b", line)
    ]
    assert not uses, uses


def test_expr_is_the_public_base_class() -> None:
    exp = pytest.importorskip("sqlglot.expressions")
    for name in ("Column", "Select", "EQ", "And", "Condition", "Cast"):
        assert issubclass(getattr(exp, name), exp.Expr), name
