"""``SHOW CREATE TABLE`` de todo un schema MySQL/MariaDB a partir de ``information_schema`` (H-29, ADR-003).

SQLAlchemy refleja MySQL/MariaDB tabla a tabla: un ``SHOW CREATE TABLE`` por tabla (más una consulta de corrección de
mayúsculas de las FK en MySQL 8) que interpreta ``MySQLTableDefinitionParser``. Aquí se reconstruye ese texto para
todas las tablas con cinco consultas por schema, con las reglas de formato de cada servidor medidas en el banco
(MySQL 8.4 y MariaDB 11):

- **Defaults**: MySQL entrecomilla todos los literales (``DEFAULT '0'``), deja ``CURRENT_TIMESTAMP…`` y ``b'…'`` tal
  cual y pone las demás expresiones entre paréntesis (``DEFAULT (uuid())``); MariaDB devuelve ``COLUMN_DEFAULT`` ya en
  forma SQL (``0``, ``'x'``, ``NULL``, ``uuid()``).
- **Collation**: ``CHARACTER SET … COLLATE …`` si la de la columna no es la de la tabla (los dos servidores).
- **Columnas generadas**: ``GENERATED ALWAYS AS (<GENERATION_EXPRESSION>) VIRTUAL|STORED``.
- **FK**: MySQL omite ``NO ACTION``; MariaDB omite ``RESTRICT``.

El texto se interpreta con el parser del propio dialecto, así que tipos, collations, ``computed``, longitudes de
índice… salen exactamente como tabla a tabla (``tests/integration/test_comparar_prefetch_engines.py``). Lo que este
texto no reproduce (``WITH PARSER`` de índices ``FULLTEXT``, ``CHECK``, opciones de tabla salvo motor, collation y
comentario) no lo usa la reflexión de columnas, PK, índices, FK y comentarios.
"""

from __future__ import annotations

import re

from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

#: Consultas por schema (bind ``:schema``); el orden de columnas es el que espera :func:`build_show_create`.
TABLES_SQL = (
    "SELECT TABLE_NAME, ENGINE, TABLE_COLLATION, TABLE_COMMENT FROM information_schema.TABLES "
    "WHERE TABLE_SCHEMA = :schema AND TABLE_TYPE IN ('BASE TABLE', 'SYSTEM VERSIONED')"
)
COLUMNS_SQL = (
    "SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, EXTRA, COLUMN_COMMENT, "
    "CHARACTER_SET_NAME, COLLATION_NAME, GENERATION_EXPRESSION FROM information_schema.COLUMNS "
    "WHERE TABLE_SCHEMA = :schema ORDER BY TABLE_NAME, ORDINAL_POSITION"
)
_STATISTICS_SQL = (
    "SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, COLUMN_NAME, SUB_PART, COLLATION, INDEX_TYPE, {expression} "
    "FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = :schema ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX"
)
FK_COLUMNS_SQL = (
    "SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_SCHEMA, REFERENCED_TABLE_NAME, "
    "REFERENCED_COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE "
    "WHERE TABLE_SCHEMA = :schema AND REFERENCED_TABLE_NAME IS NOT NULL "
    "ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION"
)
FK_RULES_SQL = (
    "SELECT TABLE_NAME, CONSTRAINT_NAME, DELETE_RULE, UPDATE_RULE FROM information_schema.REFERENTIAL_CONSTRAINTS "
    "WHERE CONSTRAINT_SCHEMA = :schema"
)


def statistics_sql(server: str) -> str:
    """``STATISTICS`` con la expresión de los índices funcionales (solo MySQL 8.0.13+ tiene ``EXPRESSION``)."""
    return _STATISTICS_SQL.format(expression="EXPRESSION" if server == "mysql" else "NULL")


@dataclass
class SchemaRows:
    """Filas de las cinco consultas, agrupadas por tabla."""

    tables: dict[str, tuple[Any, ...]] = field(default_factory=dict)
    columns: dict[str, list[tuple[Any, ...]]] = field(default_factory=lambda: defaultdict(list))
    indexes: dict[str, dict[str, list[tuple[Any, ...]]]] = field(default_factory=lambda: defaultdict(dict))
    fks: dict[str, dict[str, list[tuple[Any, ...]]]] = field(default_factory=lambda: defaultdict(dict))
    rules: dict[tuple[str, str], tuple[Any, Any]] = field(default_factory=dict)

    @classmethod
    def from_results(cls, tables: Sequence[Any], columns: Sequence[Any], stats: Sequence[Any], fks: Sequence[Any],
                     rules: Sequence[Any]) -> SchemaRows:  # fmt: skip
        rows = cls()
        rows.tables = {str(r[0]): tuple(r) for r in tables}
        for r in columns:
            rows.columns[str(r[0])].append(tuple(r))
        for r in stats:
            rows.indexes[str(r[0])].setdefault(str(r[1]), []).append(tuple(r))
        for r in fks:
            rows.fks[str(r[0])].setdefault(str(r[1]), []).append(tuple(r))
        rows.rules = {(str(r[0]), str(r[1])): (r[2], r[3]) for r in rules}
        return rows


def _literal(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def _default(server: str, row: tuple[Any, ...]) -> str:
    """`` DEFAULT …`` (y ``ON UPDATE``) como lo escribe ``SHOW CREATE TABLE``."""
    column_type, default, extra = str(row[2]), row[4], str(row[5] or "")
    on_update = re.search(r"on update (\S+)", extra, re.IGNORECASE)
    suffix = f" ON UPDATE {on_update.group(1)}" if on_update else ""
    if default is None:
        return suffix
    text = str(default)
    if server == "mariadb":
        return f" DEFAULT {text}{suffix}"
    if "DEFAULT_GENERATED" in extra.upper():
        rendered = text if text.upper().startswith("CURRENT_TIMESTAMP") else f"({text})"
    elif column_type.lower().startswith("bit") and text.startswith("b'"):
        rendered = text
    else:
        rendered = _literal(text)
    return f" DEFAULT {rendered}{suffix}"


def _column_line(server: str, row: tuple[Any, ...], table_collation: str | None, quote: Callable[[str], str]) -> str:
    _, name, column_type, nullable, _default_value, extra, comment, charset, collation, generated = row[:10]
    line = f"  {quote(str(name))} {column_type}"
    if collation and collation != table_collation:
        line += f" CHARACTER SET {charset} COLLATE {collation}"
    extra_upper = str(extra or "").upper()
    if generated:
        persistence = "STORED" if "STORED" in extra_upper else "VIRTUAL"
        line += f" GENERATED ALWAYS AS ({generated}) {persistence}"
        if nullable == "NO":
            line += " NOT NULL"
    else:
        if nullable == "NO":
            line += " NOT NULL"
        line += _default(server, row)
        if "AUTO_INCREMENT" in extra_upper:
            line += " AUTO_INCREMENT"
    if comment:
        line += f" COMMENT {_literal(str(comment))}"
    return line


def _key_line(name: str, rows: list[tuple[Any, ...]], quote: Callable[[str], str]) -> tuple[int, str]:
    """``(orden, línea)``: PRIMARY, UNIQUE, KEY y FULLTEXT/SPATIAL, como los agrupa ``SHOW CREATE TABLE``."""
    parts = []
    for r in rows:
        column, sub_part, collation, expression = r[3], r[4], r[5], r[7]
        part = f"({expression})" if expression else quote(str(column))
        if sub_part is not None:
            part += f"({int(sub_part)})"
        if collation == "D":
            part += " DESC"
        parts.append(part)
    columns = ",".join(parts)
    index_type = str(rows[0][6] or "").upper()
    if name == "PRIMARY":
        return 0, f"  PRIMARY KEY ({columns})"
    if index_type in ("FULLTEXT", "SPATIAL"):
        return 3, f"  {index_type} KEY {quote(name)} ({columns})"
    if int(rows[0][2]) == 0:
        return 1, f"  UNIQUE KEY {quote(name)} ({columns})"
    return 2, f"  KEY {quote(name)} ({columns})"


def _fk_line(server: str, schema: str, name: str, rows: list[tuple[Any, ...]], rules: tuple[Any, Any],
             quote: Callable[[str], str]) -> str:  # fmt: skip
    local = ", ".join(quote(str(r[2])) for r in rows)
    foreign = ", ".join(quote(str(r[5])) for r in rows)
    ref_schema, ref_table = str(rows[0][3]), str(rows[0][4])
    target = quote(ref_table) if ref_schema == schema else f"{quote(ref_schema)}.{quote(ref_table)}"
    line = f"  CONSTRAINT {quote(name)} FOREIGN KEY ({local}) REFERENCES {target} ({foreign})"
    implicit = "NO ACTION" if server == "mysql" else "RESTRICT"
    for clause, rule in (("ON DELETE", rules[0]), ("ON UPDATE", rules[1])):
        if rule and str(rule) != implicit:
            line += f" {clause} {rule}"
    return line


def build_show_create(server: str, schema: str, table: str, rows: SchemaRows, quote: Callable[[str], str]) -> str:
    """Texto equivalente a ``SHOW CREATE TABLE`` de ``table`` (``server``: ``"mysql"`` o ``"mariadb"``)."""
    _, engine, collation, comment = rows.tables[table]
    lines = [_column_line(server, r, collation, quote) for r in rows.columns.get(table, [])]
    keys = sorted(
        (_key_line(name, index_rows, quote) for name, index_rows in rows.indexes.get(table, {}).items()),
        key=lambda item: item[0],
    )
    lines += [line for _, line in keys]
    lines += [
        _fk_line(server, schema, name, fk_rows, rows.rules.get((table, name), (None, None)), quote)
        for name, fk_rows in rows.fks.get(table, {}).items()
    ]
    options = f") ENGINE={engine}" if engine else ")"
    if collation:
        options += f" DEFAULT CHARSET={str(collation).split('_')[0]} COLLATE={collation}"
    if comment:
        options += f" COMMENT={_literal(str(comment))}"
    return f"CREATE TABLE {quote(table)} (\n" + ",\n".join(lines) + "\n" + options


__all__: list[str] = [
    "COLUMNS_SQL",
    "FK_COLUMNS_SQL",
    "FK_RULES_SQL",
    "TABLES_SQL",
    "SchemaRows",
    "build_show_create",
    "statistics_sql",
]
