"""SQL de ``SHOW … STATUS`` y ``SHOW CREATE`` de routines MariaDB/MySQL (``metadata/mariadb/tables.py``, uso: comparar)."""

from __future__ import annotations

import pytest

from util_bbdd.metadata.mariadb.tables import fetch_routine_status_sql, fetch_show_create_routine_sql


@pytest.mark.parametrize("kind", ["PROCEDURE", "FUNCTION"])
def test_status_sql_filters_by_db_bind(kind: str) -> None:
    assert fetch_routine_status_sql(kind) == f"SHOW {kind} STATUS WHERE Db=:db"


def test_show_create_is_qualified_and_quoted() -> None:
    assert fetch_show_create_routine_sql("PROCEDURE", "ventas", "p`x") == "SHOW CREATE PROCEDURE `ventas`.`p``x`"


def test_show_create_without_database_uses_connection_db() -> None:
    assert fetch_show_create_routine_sql("FUNCTION", "", "f") == "SHOW CREATE FUNCTION `f`"


@pytest.mark.parametrize("builder", [fetch_routine_status_sql, lambda k: fetch_show_create_routine_sql(k, "d", "n")])
def test_unknown_kind_is_rejected(builder: object) -> None:
    """El tipo va interpolado en el SQL: solo se admiten las dos palabras clave."""
    with pytest.raises(ValueError, match="PROCEDURE o FUNCTION"):
        builder("TABLE; DROP")  # type: ignore[operator]
