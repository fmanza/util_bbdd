"""H5: el DDL reconstruido desde metadatos no debe entrecomillar dos veces los defaults de texto.

MariaDB (≥ 10.2.7) devuelve en ``COLUMN_DEFAULT`` los literales ya entrecomillados (``'x'``); MySQL, sin comillas
(``x``). ``format_mariadb_default`` sirve a ambos (el adapter de MySQL delega en el de MariaDB).
"""

from __future__ import annotations

import pytest

from util_bbdd.metadata.mariadb import build_mariadb_table_ddl, format_mariadb_default


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


def test_table_ddl_keeps_mariadb_quoted_default() -> None:
    rows = [("id", "int(11)", "NO", "PRI", None, ""), ("nombre", "varchar(50)", "NO", "", "'x'", "")]
    ddl = build_mariadb_table_ddl("t", rows, [("id",)])
    assert "`nombre` varchar(50) NOT NULL DEFAULT 'x'" in ddl
    assert "'''" not in ddl


@pytest.mark.parametrize(
    ("extra", "expected_tail"),
    [
        ("DEFAULT_GENERATED", "DEFAULT CURRENT_TIMESTAMP"),
        ("DEFAULT_GENERATED on update CURRENT_TIMESTAMP", "DEFAULT CURRENT_TIMESTAMP on update CURRENT_TIMESTAMP"),
        ("on update current_timestamp()", "DEFAULT CURRENT_TIMESTAMP on update current_timestamp()"),
    ],
)
def test_table_ddl_drops_mysql_default_generated_marker(extra: str, expected_tail: str) -> None:
    """MySQL marca en EXTRA los defaults de expresión con DEFAULT_GENERATED, que no es SQL."""
    rows = [("alta", "datetime", "YES", "", "CURRENT_TIMESTAMP", extra)]
    ddl = build_mariadb_table_ddl("t", rows, [])
    assert f"`alta` datetime NULL {expected_tail}" in ddl
    assert "DEFAULT_GENERATED" not in ddl
