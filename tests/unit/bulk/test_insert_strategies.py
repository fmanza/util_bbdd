"""Tests de las estrategias INSERT por motor y su resolución.

Cubre:
- ``InsertStrategyResolver``: enrutado por dialecto/driver (incluye el fix
  psycopg3 → COPY, antes código muerto al exigir ``psycopg2``).
- ``PostgresCopyStrategy``: construcción de ``COPY ... FROM STDIN`` y fallback
  para ``TextClause`` (sin BD real; cursor crudo mockeado).
- ``MySQLMultiRowInsertStrategy``: sentencia multi-fila ejecutada contra SQLite
  (SQL estándar) + sub-loteo por ``max_rows_per_statement``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from sqlalchemy import Engine, MetaData, Table, create_engine, insert
from sqlalchemy.sql.elements import TextClause

from util_bbdd.bulk._execution.batch import (
    DefaultInsertStrategy,
    InsertStrategyResolver,
    MySQLMultiRowInsertStrategy,
    PostgresCopyStrategy,
    PostgreSQLExecuteValuesStrategy,
)

# ---------------------------------------------------------------------------
# InsertStrategyResolver
# ---------------------------------------------------------------------------


class TestInsertStrategyResolver:
    def test_psycopg3_routes_to_copy(self) -> None:
        # Driver real de la librería: postgresql+psycopg (psycopg3) → COPY.
        resolver = InsertStrategyResolver()
        strategy = resolver.resolve("postgresql", "postgresql+psycopg")
        assert isinstance(strategy, PostgresCopyStrategy)

    def test_psycopg2_routes_to_execute_values(self) -> None:
        resolver = InsertStrategyResolver()
        strategy = resolver.resolve("postgresql", "postgresql+psycopg2")
        assert isinstance(strategy, PostgreSQLExecuteValuesStrategy)

    @pytest.mark.parametrize("dialect", ["mysql", "mariadb"])
    def test_mysql_family_routes_to_multirow(self, dialect: str) -> None:
        resolver = InsertStrategyResolver()
        strategy = resolver.resolve(dialect, f"{dialect}+mariadbconnector")
        assert isinstance(strategy, MySQLMultiRowInsertStrategy)

    @pytest.mark.parametrize(
        ("dialect", "driver"),
        [
            ("oracle", "oracle+oracledb"),
            ("mssql", "mssql+pyodbc"),
            ("sqlite", "sqlite+pysqlite"),
            ("hsqldb", "hsqldb+jaydebeapi"),
        ],
    )
    def test_other_engines_route_to_default(self, dialect: str, driver: str) -> None:
        resolver = InsertStrategyResolver()
        strategy = resolver.resolve(dialect, driver)
        assert isinstance(strategy, DefaultInsertStrategy)


# ---------------------------------------------------------------------------
# PostgresCopyStrategy (cursor crudo mockeado: sin PostgreSQL real)
# ---------------------------------------------------------------------------


def _mock_pg_connection() -> tuple[Any, Any, Any]:
    """Construye (connection, raw_cursor, copy_obj) mockeados para COPY."""
    copy_obj = MagicMock(name="copy")
    copy_cm = MagicMock(name="copy_cm")
    copy_cm.__enter__.return_value = copy_obj
    copy_cm.__exit__.return_value = False

    raw_cursor = MagicMock(name="raw_cursor")
    raw_cursor.copy.return_value = copy_cm

    connection = MagicMock(name="connection")
    connection.connection.cursor.return_value = raw_cursor

    preparer = connection.dialect.identifier_preparer
    preparer.format_table.return_value = '"items"'
    preparer.quote.side_effect = lambda c: f'"{c}"'
    return connection, raw_cursor, copy_obj


class TestPostgresCopyStrategy:
    def test_builds_copy_statement_and_writes_rows(self) -> None:
        connection, raw_cursor, copy_obj = _mock_pg_connection()
        stmt = MagicMock()
        stmt.table = MagicMock()
        records = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]

        PostgresCopyStrategy().execute(connection=connection, stmt=stmt, records=records)

        raw_cursor.copy.assert_called_once_with('COPY "items" ("id", "name") FROM STDIN')
        assert copy_obj.write_row.call_count == 2
        copy_obj.write_row.assert_any_call([1, "a"])
        copy_obj.write_row.assert_any_call([2, "b"])
        raw_cursor.close.assert_called_once()

    def test_empty_records_is_noop(self) -> None:
        connection, raw_cursor, _ = _mock_pg_connection()
        PostgresCopyStrategy().execute(connection=connection, stmt=MagicMock(), records=[])
        raw_cursor.copy.assert_not_called()

    def test_textclause_falls_back_to_execute(self) -> None:
        connection, raw_cursor, _ = _mock_pg_connection()
        # stmt sin atributo .table (p.ej. TextClause de OVERRIDING SYSTEM VALUE)
        stmt = TextClause("INSERT INTO items OVERRIDING SYSTEM VALUE ...")
        records = [{"id": 1, "name": "a"}]

        PostgresCopyStrategy().execute(connection=connection, stmt=stmt, records=records)

        connection.execute.assert_called_once_with(stmt, records)
        raw_cursor.copy.assert_not_called()


# ---------------------------------------------------------------------------
# MySQLMultiRowInsertStrategy (ejecutada contra SQLite: SQL estándar)
# ---------------------------------------------------------------------------


def _make_items_table_engine() -> tuple[Engine, Table]:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
    table = Table("items", MetaData(), autoload_with=engine)
    return engine, table


class TestMySQLMultiRowInsertStrategy:
    def test_inserts_all_rows_in_single_statement(self) -> None:
        engine, table = _make_items_table_engine()
        records = [{"id": i, "name": f"n{i}"} for i in range(1, 6)]

        with engine.begin() as conn:
            MySQLMultiRowInsertStrategy().execute(connection=conn, stmt=insert(table), records=records)

        with engine.connect() as conn:
            count = int(conn.exec_driver_sql("SELECT COUNT(*) FROM items").scalar() or 0)
        assert count == 5

    def test_sub_batches_respect_max_rows(self) -> None:
        engine, table = _make_items_table_engine()
        records = [{"id": i, "name": f"n{i}"} for i in range(1, 8)]

        captured: list[Any] = []
        real_execute = None

        with engine.begin() as conn:
            real_execute = conn.execute

            def _spy(*args: Any, **kwargs: Any) -> Any:
                captured.append(args)
                return real_execute(*args, **kwargs)

            conn.execute = _spy  # type: ignore[method-assign]
            MySQLMultiRowInsertStrategy(max_rows_per_statement=3).execute(
                connection=conn, stmt=insert(table), records=records
            )

        # 7 filas / 3 por sentencia → 3 sentencias (3 + 3 + 1)
        assert len(captured) == 3
        with engine.connect() as conn:
            count = int(conn.exec_driver_sql("SELECT COUNT(*) FROM items").scalar() or 0)
        assert count == 7

    def test_empty_records_is_noop(self) -> None:
        engine, table = _make_items_table_engine()
        with engine.begin() as conn:
            MySQLMultiRowInsertStrategy().execute(connection=conn, stmt=insert(table), records=[])
        with engine.connect() as conn:
            count = int(conn.exec_driver_sql("SELECT COUNT(*) FROM items").scalar() or 0)
        assert count == 0

    def test_invalid_max_rows_raises(self) -> None:
        with pytest.raises(ValueError, match="max_rows_per_statement"):
            MySQLMultiRowInsertStrategy(max_rows_per_statement=0)
