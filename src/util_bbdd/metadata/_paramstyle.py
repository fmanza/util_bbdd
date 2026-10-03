"""Bind parameters del SQL de catálogo: un solo estilo (``:nombre``) traducido al ``paramstyle`` del driver (ADR-003).

El SQL de ``metadata/<motor>/catalog.py`` se escribe siempre con ``:nombre``. Quien lo ejecuta lo traduce:

- con SQLAlchemy (``text()``) basta con :func:`expand_lists`;
- con un driver DB-API directo (managers) se usa :func:`to_driver` con el ``paramstyle`` del módulo del driver.

Antes de ADR-003 el SQL se escribía en el estilo de cada driver (``%(schema)s``, ``:owner``) o se interpolaba con
``str.format`` (H-12/H-13); en Oracle eso último costaba un *hard parse* por tabla.

Reglas del análisis: los literales entre comillas simples o dobles no se tocan (salvo escapar ``%`` en los estilos de
porcentaje), ``::`` (cast de PostgreSQL) no es un parámetro, y un parámetro con lista o tupla se expande a
``:p_0, :p_1, …`` para usarlo dentro de ``IN (...)`` (lista vacía → ``NULL``, que no coincide con nada).
"""

from __future__ import annotations

import re

from collections.abc import Mapping, Sequence
from typing import Any, Literal

#: ``dollar`` (``$1``) no es un ``paramstyle`` DB-API: es el de ``asyncpg``.
ParamStyle = Literal["named", "pyformat", "format", "qmark", "numeric", "dollar"]

_TOKEN = re.compile(
    r"(?P<literal>'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\")"
    r"|(?P<cast>::)"
    r"|(?<![\w:]):(?P<param>[A-Za-z_]\w*)"
    r"|(?P<percent>%)"
)
_LIST_TYPES = (list, tuple, set, frozenset)


def expand_lists(sql: str, params: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    """Expande los parámetros con varios valores (``IN (:tablas)`` → ``IN (:tablas_0, :tablas_1)``)."""
    lists = {name: list(value) for name, value in params.items() if isinstance(value, _LIST_TYPES)}
    if not lists:
        return sql, dict(params)
    out = {name: value for name, value in params.items() if name not in lists}

    def replace(match: re.Match[str]) -> str:
        name = match.group("param")
        if name is None or name not in lists:
            return match.group(0)
        values = lists[name]
        if not values:
            return "NULL"
        for i, value in enumerate(values):
            out[f"{name}_{i}"] = value
        return ", ".join(f":{name}_{i}" for i in range(len(values)))

    return _TOKEN.sub(replace, sql), out


def to_driver(
    sql: str, params: Mapping[str, Any], paramstyle: ParamStyle
) -> tuple[str, dict[str, Any] | list[Any] | None]:
    """Traduce SQL con ``:nombre`` al ``paramstyle`` de un driver DB-API.

    Returns:
        ``(sql, args)``. ``args`` es ``None`` si el SQL no tiene parámetros: el SQL se devuelve intacto y debe
        ejecutarse sin argumentos (con argumentos, los drivers de estilo ``%`` interpretarían los ``%`` literales).

    Raises:
        KeyError: Si el SQL usa un parámetro que no está en ``params``.
    """
    sql, flat = expand_lists(sql, params)
    if not any(m.group("param") for m in _TOKEN.finditer(sql)):
        return sql, None
    percent_style = paramstyle in ("pyformat", "format")
    positional: list[Any] = []

    def replace(match: re.Match[str]) -> str:
        if match.group("literal") is not None:
            literal = match.group("literal")
            return literal.replace("%", "%%") if percent_style else literal
        if match.group("cast") is not None:
            return "::"
        if match.group("percent") is not None:
            return "%%" if percent_style else "%"
        name = match.group("param")
        value = flat[name]
        if paramstyle == "named":
            return f":{name}"
        if paramstyle == "pyformat":
            return f"%({name})s"
        positional.append(value)
        if paramstyle == "format":
            return "%s"
        if paramstyle == "qmark":
            return "?"
        if paramstyle == "dollar":
            return f"${len(positional)}"
        return f":{len(positional)}"  # numeric

    translated = _TOKEN.sub(replace, sql)
    if paramstyle in ("named", "pyformat"):
        used = {m.group("param") for m in _TOKEN.finditer(sql) if m.group("param")}
        return translated, {name: flat[name] for name in used}
    return translated, positional


def placeholders(sql: str) -> Sequence[str]:
    """Nombres de parámetro ``:nombre`` del SQL, en orden de aparición (sin literales ni casts)."""
    return [m.group("param") for m in _TOKEN.finditer(sql) if m.group("param")]


__all__: list[str] = ["ParamStyle", "expand_lists", "placeholders", "to_driver"]
