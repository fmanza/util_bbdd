"""Extractores de la familia MySQL/MariaDB hacia IR canónico para ``MigrationPlanner``.

``MySQLSchemaExtractor`` hereda de ``MariaDBSchemaExtractor`` (mismo ``INFORMATION_SCHEMA`` para tablas, PK, FK,
índices, vistas y rutinas) y solo cambia la lectura de columnas:

- **Defaults literales**: MySQL devuelve ``COLUMN_DEFAULT`` sin comillas (``x``) y MariaDB con ellas (``'x'``). En
  columnas no numéricas se entrecomilla el literal para seguir el convenio de MariaDB, que es el que esperan
  transformers y emitters; las expresiones (``EXTRA`` contiene ``DEFAULT_GENERATED``) se dejan tal cual.
- **Tipo completo** (``full_column_types=True``): ``oracle_type`` guarda ``COLUMN_TYPE`` (``enum('a','b')``,
  ``int unsigned``) en lugar de ``DATA_TYPE``. Solo lo usan los pares dentro de la familia (MySQL ↔ MariaDB), cuyos
  transformers emiten el tipo tal cual; hacia otros motores se mantiene ``DATA_TYPE``, que es lo que esperan los
  mapas de tipos ``mariadb_to_*``.

``MariaDBFullTypeSchemaExtractor`` es la variante para MariaDB → MySQL: tipo completo sin normalizar defaults.
"""

from __future__ import annotations

from typing import Any, ClassVar

from ...metadata.mysql.tables import fetch_columns_with_type_for_schema_sql
from ..ir.models import CanonicalColumn
from .mariadb import MariaDBSchemaExtractor, _parse_raw_column

#: DATA_TYPE numéricos: sus defaults literales van sin comillas en ambos motores.
_NUMERIC_DATA_TYPES: frozenset[str] = frozenset(
    {
        "TINYINT",
        "SMALLINT",
        "MEDIUMINT",
        "INT",
        "INTEGER",
        "BIGINT",
        "DECIMAL",
        "NUMERIC",
        "FLOAT",
        "DOUBLE",
        "REAL",
        "BIT",
        "BOOLEAN",
        "BOOL",
        "YEAR",
    }
)


def quote_literal_default(default: str | None, data_type: str, extra: str) -> str | None:
    """Entrecomilla un default literal de MySQL (convenio de MariaDB: ``'x'``).

    Args:
        default: ``COLUMN_DEFAULT`` tal cual lo devuelve MySQL.
        data_type: ``DATA_TYPE`` de la columna.
        extra: ``EXTRA`` de la columna (``DEFAULT_GENERATED`` marca una expresión).

    Returns:
        El default entrecomillado si es un literal de una columna no numérica; si no, sin cambios.
    """
    if default is None or "DEFAULT_GENERATED" in extra.upper():
        return default
    if data_type.strip().upper() in _NUMERIC_DATA_TYPES:
        return default
    if len(default) >= 2 and default.startswith("'") and default.endswith("'"):
        return default
    return "'" + default.replace("'", "''") + "'"


class MySQLSchemaExtractor(MariaDBSchemaExtractor):
    """Extrae el esquema MySQL hacia ``CanonicalTable`` (ver docstring del módulo).

    Args:
        manager: Manager con ``execute_custom_many(sql, params) → Rows`` (``SyncDatabaseManager`` compatible).
        full_column_types: Si True, ``oracle_type`` guarda ``COLUMN_TYPE`` completo (pares MySQL ↔ MariaDB).
    """

    _QUOTE_LITERAL_DEFAULTS: ClassVar[bool] = True

    def __init__(self, manager: Any, *, full_column_types: bool = False) -> None:
        super().__init__(manager)
        self._full_column_types = full_column_types

    def _columns_for_schema_sql(self) -> str:
        return fetch_columns_with_type_for_schema_sql()

    def _extract_columns(self, rows: list[tuple[Any, ...]]) -> list[CanonicalColumn]:
        columns: list[CanonicalColumn] = []

        for row in rows:
            parsed = _parse_raw_column(row)
            if parsed is None:
                continue
            extra: str = str(row[7]).strip() if row[7] else ""
            default: str | None = parsed["default"]
            if self._QUOTE_LITERAL_DEFAULTS:
                default = quote_literal_default(default, parsed["data_type"], extra)
            column_type: str = str(row[10]).strip() if len(row) > 10 and row[10] else ""
            source_type: str = column_type if self._full_column_types and column_type else parsed["data_type"]

            columns.append(
                CanonicalColumn(
                    name=parsed["name"],
                    original_name=parsed["name"],
                    oracle_type=source_type,
                    target_type="",  # el transformer lo rellena
                    nullable=parsed["nullable"],
                    default=default,
                    comment=parsed["comment"],
                    ordinal=parsed["ordinal"],
                    char_length=parsed["char_length"],
                    precision=parsed["precision"],
                    scale=parsed["scale"],
                    auto_increment=parsed["auto_increment"],
                )
            )

        return columns


class MariaDBFullTypeSchemaExtractor(MySQLSchemaExtractor):
    """Extractor MariaDB con ``COLUMN_TYPE`` completo, para el par MariaDB → MySQL.

    MariaDB ya devuelve los defaults literales entrecomillados, así que no se normalizan.
    """

    _QUOTE_LITERAL_DEFAULTS: ClassVar[bool] = False

    def __init__(self, manager: Any) -> None:
        super().__init__(manager, full_column_types=True)


__all__: list[str] = [
    "MariaDBFullTypeSchemaExtractor",
    "MySQLSchemaExtractor",
    "quote_literal_default",
]
