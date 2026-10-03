"""H5: el DDL reconstruido desde metadatos no debe entrecomillar dos veces los defaults de texto.

MariaDB (≥ 10.2.7) devuelve en ``COLUMN_DEFAULT`` los literales ya entrecomillados (``'x'``); MySQL, sin comillas
(``x``). ``format_mariadb_default`` sirve a ambos (el adapter de MySQL delega en el de MariaDB).
"""

from __future__ import annotations

import pytest

from util_bbdd.metadata.ddl import mysql_table_ddl
from util_bbdd.metadata.mariadb import format_mariadb_default
from util_bbdd.metadata.mariadb.catalog import MariaDBCatalog
from util_bbdd.metadata.model import ColumnMeta, PrimaryKeyMeta


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # MariaDB ≥ 10.2.7: literales ya entrecomillados
        ("'x'", "'x'"),
        ("'it''s'", "'it''s'"),
        ("''", "''"),
        ("'0'", "'0'"),
        # MySQL: literales sin comillas
        ("x", "'x'"),
        ("it's", "'it''s'"),
        ("sin nombre", "'sin nombre'"),
        # Comunes
        ("NULL", "NULL"),
        ("0.00", "0.00"),
        ("current_timestamp()", "current_timestamp()"),
        ("CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP"),
    ],
)
def test_format_mariadb_default(raw: str, expected: str) -> None:
    assert format_mariadb_default(raw) == expected


def _column(name: str, data_type: str, *, nullable: bool, default: str | None = None, **kw: object) -> ColumnMeta:
    return ColumnMeta("t", name, 1, data_type, data_type.split("(")[0], nullable, default=default, **kw)  # type: ignore[arg-type]


def test_table_ddl_keeps_mariadb_quoted_default() -> None:
    columns = [
        _column("id", "int(11)", nullable=False, identity="by default"),
        _column("nombre", "varchar(50)", nullable=False, default="'x'"),
    ]
    ddl = mysql_table_ddl("t", columns, PrimaryKeyMeta("t", "PRIMARY", ("id",)))
    assert ddl == (
        "CREATE TABLE `t` (\n"
        "  `id` int(11) NOT NULL auto_increment,\n"
        "  `nombre` varchar(50) NOT NULL DEFAULT 'x',\n"
        "  PRIMARY KEY (`id`)\n"
        ")"
    )


def test_table_ddl_keeps_on_update() -> None:
    columns = [_column("alta", "datetime", nullable=True, default="CURRENT_TIMESTAMP", on_update="CURRENT_TIMESTAMP")]
    ddl = mysql_table_ddl("t", columns, None)
    assert "`alta` datetime NULL DEFAULT CURRENT_TIMESTAMP on update CURRENT_TIMESTAMP" in ddl


def test_table_ddl_without_columns_is_empty() -> None:
    assert mysql_table_ddl("t", [], None) == ""


@pytest.mark.parametrize(
    ("extra", "on_update"),
    [
        ("DEFAULT_GENERATED", None),
        ("DEFAULT_GENERATED on update CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP"),
        ("on update current_timestamp()", "current_timestamp()"),
        ("auto_increment", None),
    ],
)
def test_catalog_reads_on_update_from_extra(extra: str, on_update: str | None) -> None:
    """El catálogo separa ``ON UPDATE`` del ``EXTRA`` (MySQL añade ``DEFAULT_GENERATED``, que no es SQL)."""
    row = (
        "t",
        "alta",
        1,
        "datetime",
        "datetime",
        "YES",
        None,
        None,
        None,
        "CURRENT_TIMESTAMP",
        None,
        None,
        extra,
        None,
    )
    (column,) = MariaDBCatalog._parse_columns([row], "s")
    assert column.on_update == on_update
