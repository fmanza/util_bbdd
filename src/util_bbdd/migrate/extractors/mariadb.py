"""Extractor de metadatos MariaDB hacia IR canónico (desde el snapshot de ``metadata/``, C3 de ADR-003).

El IR conserva las convenciones de ``INFORMATION_SCHEMA.COLUMNS`` que esperan los transformers ``mariadb_to_*``:
``source_type`` es ``DATA_TYPE`` en mayúsculas, ``char_length`` = ``CHARACTER_MAXIMUM_LENGTH`` (también en BLOB,
``ENUM`` y ``SET``) y ``NUMERIC_PRECISION``/``NUMERIC_SCALE`` también en enteros, coma flotante y ``BIT``.
MariaDB escribe ``'NULL'`` como default de las columnas nulables sin otro; el IR lo conserva.

El cuerpo de las routines es el ``CREATE`` completo que reconstruye
:func:`util_bbdd.metadata.mariadb.catalog.build_create_routine`.
"""

from __future__ import annotations

import re

from typing import ClassVar

from ...metadata.model import ColumnMeta
from ..ir.models import CanonicalColumn
from ._snapshot import SnapshotSchemaExtractor

#: NUMERIC_PRECISION / NUMERIC_SCALE de los tipos numéricos sin modificadores (``bigint unsigned``: 20).
_NUMERIC_PS: dict[str, tuple[int, int | None]] = {
    "tinyint": (3, 0),
    "smallint": (5, 0),
    "mediumint": (7, 0),
    "int": (10, 0),
    "bigint": (19, 0),
    "float": (12, None),
    "double": (22, None),
}
#: CHARACTER_MAXIMUM_LENGTH de los BLOB (los TEXT ya la traen del catálogo).
_BLOB_LENGTH: dict[str, int] = {
    "tinyblob": 255,
    "blob": 65535,
    "mediumblob": 16777215,
    "longblob": 4294967295,
}
_PARENS = re.compile(r"\(([^)]*)\)")
_VALUES = re.compile(r"'((?:[^']|'')*)'")


def _members(column_type: str) -> list[str]:
    """Valores de un ``enum(...)``/``set(...)`` tal como se declararon."""
    return [value.replace("''", "'") for value in _VALUES.findall(column_type)]


def information_schema_sizes(col: ColumnMeta) -> tuple[int | None, int | None, int | None]:
    """``(CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE)`` de una columna MySQL/MariaDB."""
    base, column_type = col.base_type.lower(), col.data_type.lower()
    length, precision, scale = col.length, col.precision, col.scale
    if base in _BLOB_LENGTH:
        length = _BLOB_LENGTH[base]
    elif base == "enum":
        length = max((len(v) for v in _members(col.data_type)), default=0)
    elif base == "set":
        members = _members(col.data_type)
        length = sum(len(v) for v in members) + max(len(members) - 1, 0)
    if base in _NUMERIC_PS:
        precision, scale = _NUMERIC_PS[base]
        if base == "bigint" and "unsigned" in column_type:
            precision = 20
        if base in ("float", "double") and (match := _PARENS.search(column_type)) and "," in match.group(1):
            p, s = match.group(1).split(",")
            precision, scale = int(p), int(s)
    elif base == "bit":
        match = _PARENS.search(column_type)
        precision = int(match.group(1)) if match else 1
    return length, precision, scale


class MariaDBSchemaExtractor(SnapshotSchemaExtractor):
    """Extrae el esquema MariaDB hacia el IR canónico.

    Args:
        source: Manager de util_bbdd o ``MetadataSource`` de MariaDB. ``schema`` es la base de datos.
    """

    engine: ClassVar[str] = "mariadb"
    #: ``source_type`` = ``COLUMN_TYPE`` completo (pares MySQL ↔ MariaDB) en vez de ``DATA_TYPE``.
    _full_types: bool = False
    #: MariaDB devuelve ``'NULL'`` como default de las columnas nulables; MySQL, ``NULL``.
    _NULL_DEFAULT_TEXT: ClassVar[bool] = True

    def _column(self, col: ColumnMeta) -> CanonicalColumn:
        length, precision, scale = information_schema_sizes(col)
        default = col.default
        if default is None and col.nullable and self._NULL_DEFAULT_TEXT:
            default = "NULL"
        return self._canonical_column(
            col,
            col.data_type if self._full_types else col.base_type.upper(),
            char_length=length,
            precision=precision,
            scale=scale,
            default=default,
        )


__all__: list[str] = ["MariaDBSchemaExtractor", "information_schema_sizes"]
