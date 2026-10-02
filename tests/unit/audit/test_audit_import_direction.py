"""``util_bbdd.audit`` no conoce a sus consumidores (regla 2 del prompt ``audit_module``).

``tests/unit/test_architecture_import_rules.py`` ya impide imports a capas iguales o superiores; este test lo dice con
nombre propio para ``audit``: ni ``bulk``, ni ``dump``, ni ``migrate``, tampoco perezosos ni bajo ``TYPE_CHECKING``.
"""

from __future__ import annotations

import ast

from pathlib import Path

import pytest

AUDIT = Path(__file__).resolve().parents[3] / "src" / "util_bbdd" / "audit"
FORBIDDEN = {"bulk", "dump", "migrate"}


def _imported_packages(path: Path) -> set[str]:
    """Paquetes de primer nivel de ``util_bbdd`` que importa ``path`` (absolutos y relativos, en cualquier ámbito)."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[1] for alias in node.names if alias.name.startswith("util_bbdd."))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level == 0 and module.startswith("util_bbdd."):
                found.add(module.split(".")[1])
            elif node.level >= 2:  # desde util_bbdd/audit/x.py, ``..`` es util_bbdd
                parts = module.split(".") if module else [alias.name for alias in node.names]
                found.update(parts[:1] if module else parts)
    return found


@pytest.mark.parametrize("path", sorted(AUDIT.rglob("*.py")), ids=lambda p: p.name)
def test_audit_no_importa_a_sus_consumidores(path: Path) -> None:
    assert _imported_packages(path) & FORBIDDEN == set()
