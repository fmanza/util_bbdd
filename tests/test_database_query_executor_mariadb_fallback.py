"""Tests para fallback de columnas_tabla en MariaDB ante errores de decode/fetchrows."""

from __future__ import annotations

from typing import Any, cast

import pytest

from util_bbdd.database_queries import DatabaseQueryExecutor


class _FakeResolver:
    """Fake resolver que valida parámetros como lo hace QueryResolver."""

    def resolve(self, query_name: str, db_type: str, kwargs: dict[str, Any]) -> None:
        if query_name == "columnas_tabla":
            if "database" not in kwargs:
                raise ValueError("Falta parámetro requerido: database")
            if "tabla" not in kwargs:
                raise ValueError("Falta parámetro requerido: tabla")


class _FakeQueries:
    def __init__(self) -> None:
        self.db_type = "mariadb"
        self.queries = {"mariadb": {"columnas_tabla": "SELECT * FROM t"}}
        self.resolver = _FakeResolver()

    def get_query(self, query_name: str, **kwargs: Any) -> str:
        _ = kwargs
        return self.queries["mariadb"][query_name]


class _BrokenCursor:
    def execute(self, _query: str) -> None:
        return None

    def fetchall(self) -> list[tuple[Any, ...]]:
        raise RuntimeError("<method 'fetchrows' of 'mariadb.cursor' objects> returned a result with an exception set")


def test_execute_query_columnas_tabla_mariadb_uses_hex_fallback(monkeypatch) -> None:
    executor = DatabaseQueryExecutor(
        connection=object(),
        cursor=_BrokenCursor(),
        queries=cast(Any, _FakeQueries()),
    )

    expected_rows: list[tuple[Any, ...]] = [
        ("id", "int(11)", "NO", "PRI", None, "auto_increment", ""),
        ("nombre", "varchar(100)", "YES", "", None, "", "comentario"),
    ]

    def _fake_hex_fallback(*, database: str, table: str) -> list[tuple[Any, ...]]:
        assert database == "demo_db"
        assert table == "clientes"
        return expected_rows

    monkeypatch.setattr(executor, "_get_mariadb_columns_with_hex_fallback", _fake_hex_fallback)

    result = executor.execute_query(
        "columnas_tabla",
        fetch_one=False,
        database="demo_db",
        tabla="clientes",
    )

    assert result == expected_rows


def test_execute_query_columnas_tabla_missing_params_raises_value_error(monkeypatch) -> None:
    executor = DatabaseQueryExecutor(
        connection=object(),
        cursor=_BrokenCursor(),
        queries=cast(Any, _FakeQueries()),
    )

    def _must_not_be_called(*, database: str, table: str) -> list[tuple[Any, ...]]:
        _ = (database, table)
        raise AssertionError("No debe invocarse fallback HEX cuando faltan parámetros")

    monkeypatch.setattr(executor, "_get_mariadb_columns_with_hex_fallback", _must_not_be_called)

    with pytest.raises(ValueError):
        executor.execute_query(
            "columnas_tabla",
            fetch_one=False,
            # intencionalmente falta `tabla`
            database="demo_db",
        )
