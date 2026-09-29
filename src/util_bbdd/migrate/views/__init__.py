"""Vistas de ``migrate``: transpilado entre motores con ``sqlglot`` (dependencia opcional, extra ``util_bbdd[migrate]``).

``MigrationPlanner(view_strategy=...)`` decide si se usa: ``"auto"`` (por defecto) transpila si ``sqlglot`` está
instalado y, si no, emite las vistas sin reescribir; ``"transpile"`` lo exige; ``"passthrough"`` mantiene el
comportamiento anterior. El transpilador (``transpiler.py``) solo se importa cuando se usa.
"""

from __future__ import annotations

from ._dialects import SQLGLOT_DIALECT, VALID_VIEW_STRATEGIES, ViewStrategy, resolve_view_strategy, sqlglot_available

__all__: list[str] = [
    "SQLGLOT_DIALECT",
    "VALID_VIEW_STRATEGIES",
    "ViewStrategy",
    "resolve_view_strategy",
    "sqlglot_available",
]
