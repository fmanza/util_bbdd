"""Extractores de la familia MySQL/MariaDB hacia IR canónico para ``MigrationPlanner``.

``MySQLSchemaExtractor`` hereda de ``MariaDBSchemaExtractor`` (mismo ``INFORMATION_SCHEMA``) con dos diferencias:

- **Defaults**: MySQL no escribe ``'NULL'`` en las columnas nulables sin default. Sus literales llegan ya entre
  comillas desde el catálogo (``MySQLCatalog`` y ``metadata.mariadb.catalog.quote_literal_default``, convenio de
  MariaDB: ``'x'``); las expresiones, tal cual.
- **Tipo completo** (``full_column_types=True``): ``source_type`` guarda ``COLUMN_TYPE`` (``enum('a','b')``,
  ``int unsigned``) en lugar de ``DATA_TYPE``. Solo lo usan los pares dentro de la familia (MySQL ↔ MariaDB), cuyos
  transformers emiten el tipo tal cual; hacia otros motores se mantiene ``DATA_TYPE``, que es lo que esperan los
  mapas de tipos ``mariadb_to_*``.

``MariaDBFullTypeSchemaExtractor`` es la variante para MariaDB → MySQL: tipo completo con los defaults de MariaDB.
"""

from __future__ import annotations

from typing import Any, ClassVar

from .mariadb import MariaDBSchemaExtractor


class MySQLSchemaExtractor(MariaDBSchemaExtractor):
    """Extrae el esquema MySQL hacia el IR canónico (ver docstring del módulo).

    Args:
        source: Manager de util_bbdd o ``MetadataSource`` de MySQL.
        full_column_types: Si True, ``source_type`` guarda ``COLUMN_TYPE`` completo (pares MySQL ↔ MariaDB).
    """

    engine: ClassVar[str] = "mysql"
    _NULL_DEFAULT_TEXT: ClassVar[bool] = False

    def __init__(self, source: Any, *, full_column_types: bool = False) -> None:
        super().__init__(source)
        self._full_types = full_column_types


class MariaDBFullTypeSchemaExtractor(MariaDBSchemaExtractor):
    """Extractor MariaDB con ``COLUMN_TYPE`` completo, para el par MariaDB → MySQL."""

    _full_types: bool = True


__all__: list[str] = [
    "MariaDBFullTypeSchemaExtractor",
    "MySQLSchemaExtractor",
]
