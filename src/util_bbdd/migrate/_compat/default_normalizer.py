"""Normalización de valores DEFAULT según el motor origen (H4).

Los emitters traducen defaults de un dialecto «canónico» (literales entrecomillados, números, ``NULL``,
``CURRENT_TIMESTAMP``, ``CURRENT_DATE``...). Sin este paso, la sintaxis propia de cada origen llegaba tal cual al
destino y el DDL no era válido: casts de PostgreSQL (``'x'::character varying``), paréntesis de SQL Server
(``((0))``, ``(N'x')``), ``SYSDATE`` de Oracle o ``current_timestamp()`` de MariaDB. Los literales de MariaDB llegan
con sus escapes de barra (``'C:\\\\x'``, ``\\n``) y se decodifican (A4); los emitters de MariaDB/MySQL vuelven a escapar
la barra.

Forma canónica que produce ``normalize_default``:

- literal de texto entrecomillado con comillas simples (``'x'``, comillas internas duplicadas);
- número sin comillas; ``NULL``;
- ``CURRENT_TIMESTAMP`` / ``CURRENT_TIMESTAMP(n)`` / ``CURRENT_DATE``;
- booleanos como ``1`` / ``0``.

Lo que no se reconoce se devuelve sin cambios (p. ej. ``SEQ.NEXTVAL``, que los transformers de Oracle usan para
detectar secuencias, o ``newid()``, para el que los emitters ya generan aviso).
"""

from __future__ import annotations

import re

_TIMESTAMP_FUNCTIONS: dict[str, frozenset[str]] = {
    "postgresql": frozenset(
        {"NOW()", "CURRENT_TIMESTAMP", "LOCALTIMESTAMP", "STATEMENT_TIMESTAMP()", "TRANSACTION_TIMESTAMP()"}
    ),
    "sqlserver": frozenset({"GETDATE()", "SYSDATETIME()", "CURRENT_TIMESTAMP", "GETUTCDATE()", "SYSUTCDATETIME()"}),
    "oracle": frozenset({"SYSDATE", "SYSTIMESTAMP", "CURRENT_TIMESTAMP", "LOCALTIMESTAMP"}),
    "mariadb": frozenset({"CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP()", "NOW()", "LOCALTIMESTAMP", "LOCALTIMESTAMP()"}),
    "mysql": frozenset({"CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP()", "NOW()", "LOCALTIMESTAMP", "LOCALTIMESTAMP()"}),
}
_DATE_FUNCTIONS: frozenset[str] = frozenset({"CURRENT_DATE", "CURRENT_DATE()", "CURDATE()"})
_TIMESTAMP_WITH_PRECISION_RE: re.Pattern[str] = re.compile(r"^(?:CURRENT_TIMESTAMP|NOW)\s*\(\s*(\d+)\s*\)$", re.I)
#: Cast de PostgreSQL al final del valor: ``::character varying``, ``::timestamp without time zone``, ``::text[]``.
_PG_CAST_RE: re.Pattern[str] = re.compile(r'::\s*[A-Za-z_"][\w\s".]*(\(\s*\d+(\s*,\s*\d+)?\s*\))?(\[\])*\s*$')
_PG_NUMERIC_CAST_RE: re.Pattern[str] = re.compile(
    r"::\s*(smallint|integer|bigint|int\d?|numeric|decimal|real|double precision|float\d?)\b", re.I
)
_NUMBER_RE: re.Pattern[str] = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")


def _is_number(value: str) -> bool:
    return bool(_NUMBER_RE.match(value))


def _is_quoted_literal(value: str) -> bool:
    """True si ``value`` es un único literal ``'...'`` (las comillas internas van duplicadas)."""
    if len(value) < 2 or not (value.startswith("'") and value.endswith("'")):
        return False
    return "'" not in value[1:-1].replace("''", "")


def _strip_outer_parens(value: str) -> str:
    """Quita paréntesis que envuelven el valor completo: ``((0))`` → ``0`` (no toca ``f(x)`` ni ``(a) + (b)``)."""
    while value.startswith("(") and value.endswith(")"):
        depth = 0
        wraps_all = True
        for index, char in enumerate(value):
            depth += char == "("
            depth -= char == ")"
            if depth == 0 and index < len(value) - 1:
                wraps_all = False
                break
        if not wraps_all:
            break
        value = value[1:-1].strip()
    return value


def _normalize_postgresql(value: str) -> str:
    numeric_cast: bool = bool(_PG_NUMERIC_CAST_RE.search(value))
    while True:
        stripped = _PG_CAST_RE.sub("", value).strip()
        if stripped == value:
            break
        value = stripped
    value = _strip_outer_parens(value)
    if numeric_cast and _is_quoted_literal(value) and _is_number(value[1:-1]):
        return value[1:-1]
    upper = value.upper()
    if upper == "TRUE":
        return "1"
    if upper == "FALSE":
        return "0"
    return value


def _normalize_sqlserver(value: str) -> str:
    value = _strip_outer_parens(value)
    if value[:2].upper() == "N'" and _is_quoted_literal(value[1:]):
        value = value[1:]
    return value


#: Escapes de un literal MySQL/MariaDB (``\%`` y ``\_`` conservan la barra); cualquier otro ``\x`` es ``x``.
_MYSQL_ESCAPES: dict[str, str] = {
    "0": "\0",
    "b": "\b",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "Z": "\x1a",
    "%": "\\%",
    "_": "\\_",
}


def _decode_mariadb_literal(value: str) -> str:
    """Literal de ``COLUMN_DEFAULT`` de MariaDB (``'C:\\\\x\\n'``, con escapes de barra) → literal canónico (A4).

    MariaDB devuelve los literales con su sintaxis: la barra escapada (``\\\\``), los saltos de línea como ``\\n`` y la
    comilla duplicada. La forma canónica solo duplica la comilla. Si ``value`` no es exactamente un literal, se devuelve
    sin cambios.
    """
    if len(value) < 2 or value[0] != "'" or value[-1] != "'":
        return value
    chars: list[str] = []
    index, end = 1, len(value) - 1
    while index < end:
        char = value[index]
        if char == "\\" and index + 1 < end:
            escaped = value[index + 1]
            chars.append(_MYSQL_ESCAPES.get(escaped, escaped))
            index += 2
        elif char == "'":
            if index + 1 < end and value[index + 1] == "'":
                chars.append("'")
                index += 2
            else:
                return value  # comilla sin duplicar: no es un único literal (p. ej. 'a' + 'b')
        else:
            chars.append(char)
            index += 1
    return "'" + "".join(chars).replace("'", "''") + "'"


def normalize_default(source_engine: str, value: str | None) -> str | None:
    """Devuelve ``value`` (DEFAULT tal como lo extrae el motor ``source_engine``) en forma canónica."""
    if value is None:
        return None
    normalized: str = value.strip()
    if not normalized:
        return None

    source: str = source_engine.strip().lower()
    if source == "postgresql":
        normalized = _normalize_postgresql(normalized)
    elif source == "sqlserver":
        normalized = _normalize_sqlserver(normalized)
    elif source == "mariadb":
        normalized = _decode_mariadb_literal(normalized)

    upper: str = normalized.upper()
    if upper == "NULL":
        return "NULL"
    if upper in _TIMESTAMP_FUNCTIONS.get(source, frozenset()):
        return "CURRENT_TIMESTAMP"
    if upper in _DATE_FUNCTIONS:
        return "CURRENT_DATE"
    precision = _TIMESTAMP_WITH_PRECISION_RE.match(normalized)
    if precision and source in {"mariadb", "mysql", "postgresql"}:
        return f"CURRENT_TIMESTAMP({precision.group(1)})"
    return normalized


__all__: list[str] = ["normalize_default"]
