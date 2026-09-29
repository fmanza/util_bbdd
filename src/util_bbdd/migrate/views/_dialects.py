"""Dialectos de sqlglot por motor de ``migrate`` y disponibilidad de la dependencia opcional."""

from __future__ import annotations

import importlib.util

from typing import Literal

ViewStrategy = Literal["auto", "transpile", "passthrough"]
VALID_VIEW_STRATEGIES: frozenset[str] = frozenset({"auto", "transpile", "passthrough"})

#: sqlglot no tiene dialecto MariaDB: se usa el de MySQL (validado en V0 contra MariaDB 11.4).
SQLGLOT_DIALECT: dict[str, str] = {
    "mysql": "mysql",
    "mariadb": "mysql",
    "postgresql": "postgres",
    "sqlserver": "tsql",
    "oracle": "oracle",
}


def sqlglot_available() -> bool:
    """True si la dependencia opcional ``sqlglot`` (extra ``util_bbdd[migrate]``) está instalada."""
    return importlib.util.find_spec("sqlglot") is not None


def resolve_view_strategy(strategy: str) -> Literal["transpile", "passthrough"]:
    """Traduce ``view_strategy`` a la estrategia efectiva.

    Raises:
        ValueError: Si la estrategia no es válida.
        ImportError: Si se pide ``"transpile"`` sin ``sqlglot`` instalado.
    """
    normalized: str = strategy.strip().lower()
    if normalized not in VALID_VIEW_STRATEGIES:
        raise ValueError(f"view_strategy '{strategy}' no es válida. Valores aceptados: {sorted(VALID_VIEW_STRATEGIES)}")
    if normalized == "passthrough":
        return "passthrough"
    if sqlglot_available():
        return "transpile"
    if normalized == "transpile":
        raise ImportError("view_strategy='transpile' requiere sqlglot: pip install \"util_bbdd[migrate]\"")
    return "passthrough"


__all__: list[str] = [
    "SQLGLOT_DIALECT",
    "VALID_VIEW_STRATEGIES",
    "ViewStrategy",
    "resolve_view_strategy",
    "sqlglot_available",
]
