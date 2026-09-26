"""Tests de las estrategias INSERT por motor y su resolución.

Cubre:
- ``InsertStrategyResolver``: enrutado por dialecto/driver (incluye el fix
  psycopg3 → COPY, antes código muerto al exigir ``psycopg2``).
- ``PostgresCopyStrategy``: construcción de ``COPY ... FROM STDIN`` y fallback
  para ``TextClause`` (sin BD real; cursor crudo mockeado).
- ``MySQLMultiRowInsertStrategy``: sentencia multi-fila ejecutada contra SQLite
  (SQL estándar) + sub-loteo por ``max_rows_per_statement``.
- ``MySQLDriverExecutemanyStrategy``: executemany del driver sin procesadores de tipo
  (SQLite con paramstyle ``qmark`` y conexión simulada con ``pyformat``).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from sqlalchemy import Column, Engine, Integer, MetaData, String, Table, bindparam, create_engine, insert, update
from sqlalchemy.sql.elements import TextClause

from util_bbdd.bulk._execution.batch import (
    DefaultInsertStrategy,
    InsertStrategyResolver,
    MariaDBConnectorInsertStrategy,
    MySQLDriverExecutemanyStrategy,
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
    @pytest.mark.parametrize("driver", ["mysqlconnector", "mysqldb"])
    def test_mysql_family_other_drivers_route_to_multirow(self, dialect: str, driver: str) -> None:
        resolver = InsertStrategyResolver()
        strategy = resolver.resolve(dialect, f"{dialect}+{driver}")
        assert isinstance(strategy, MySQLMultiRowInsertStrategy)

    @pytest.mark.parametrize("dialect", ["mysql", "mariadb"])
    def test_mariadb_connector_routes_to_its_strategy(self, dialect: str) -> None:
        # PF-09: executemany del driver si los tipos del lote son uniformes; si no, multi-fila.
        resolver = InsertStrategyResolver()
        strategy = resolver.resolve(dialect, f"{dialect}+mariadbconnector")
        assert isinstance(strategy, MariaDBConnectorInsertStrategy)

    @pytest.mark.parametrize("dialect", ["mysql", "mariadb"])
    def test_mysql_family_with_pymysql_routes_to_driver_executemany(self, dialect: str) -> None:
        # P-02: con PyMySQL el executemany del driver ya envía INSERT multi-fila (~2× más rápido).
        resolver = InsertStrategyResolver()
        strategy = resolver.resolve(dialect, f"{dialect}+pymysql")
        assert isinstance(strategy, MySQLDriverExecutemanyStrategy)

    @pytest.mark.parametrize("driver", ["mysql+pymysql", "mariadb+mariadbconnector"])
    def test_explicit_mysql_strategy_wins_for_any_driver(self, driver: str) -> None:
        legacy = MySQLMultiRowInsertStrategy()
        resolver = InsertStrategyResolver(mysql_strategy=legacy)
        assert resolver.resolve(driver.split("+")[0], driver) is legacy

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
        table = Table("items", MetaData(), Column("id", Integer), Column("name", String))
        stmt = insert(table)
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

    def test_update_stmt_falls_back_to_execute(self) -> None:
        # Regresión: Update también expone .table, por lo que hasattr(stmt, "table")
        # no basta para distinguirlo de un Insert real (bulk_update_from_df en
        # PostgreSQL generaba antes un COPY con columnas espurias, p.ej. "pk_id").
        connection, raw_cursor, _ = _mock_pg_connection()
        table = Table("items", MetaData(), Column("id", Integer), Column("name", String))
        stmt = update(table).where(table.c.id == bindparam("pk_id")).values(name=bindparam("name"))
        records = [{"name": "a", "pk_id": 1}]

        PostgresCopyStrategy().execute(connection=connection, stmt=stmt, records=records)

        connection.execute.assert_called_once_with(stmt, records)
        raw_cursor.copy.assert_not_called()


# ---------------------------------------------------------------------------
# PostgreSQLExecuteValuesStrategy (fallback path; execute_values path requiere psycopg2)
# ---------------------------------------------------------------------------


class TestPostgreSQLExecuteValuesStrategy:
    def test_update_stmt_falls_back_to_execute(self) -> None:
        connection = MagicMock(name="connection")
        table = Table("items", MetaData(), Column("id", Integer), Column("name", String))
        stmt = update(table).where(table.c.id == bindparam("pk_id")).values(name=bindparam("name"))
        records = [{"name": "a", "pk_id": 1}]

        PostgreSQLExecuteValuesStrategy().execute(connection=connection, stmt=stmt, records=records)

        connection.execute.assert_called_once_with(stmt, records)


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

    def test_update_stmt_executes_update_not_bogus_insert(self) -> None:
        # Regresión: antes del fix, un Update (que también expone .table) se trataba
        # como Insert y generaba "INSERT INTO items (name, pk_id) VALUES (...)" con
        # "pk_id" (alias del bindparam del WHERE) como columna inexistente → el error
        # de bulk_update_from_df en MySQL/MariaDB reportado en producción.
        engine, table = _make_items_table_engine()
        with engine.begin() as conn:
            conn.execute(table.insert(), [{"id": 1, "name": "old"}])

        stmt = update(table).where(table.c.id == bindparam("pk_id")).values(name=bindparam("name"))
        records = [{"name": "new", "pk_id": 1}]

        with engine.begin() as conn:
            MySQLMultiRowInsertStrategy().execute(connection=conn, stmt=stmt, records=records)

        with engine.connect() as conn:
            name = conn.exec_driver_sql("SELECT name FROM items WHERE id = 1").scalar()
        assert name == "new"


# ---------------------------------------------------------------------------
# MySQLDriverExecutemanyStrategy (P-02)
# ---------------------------------------------------------------------------


class TestMySQLDriverExecutemanyStrategy:
    def test_inserts_all_rows_with_one_driver_executemany(self) -> None:
        # SQLite usa paramstyle qmark: ejercita el mismo camino que el conector con "?".
        engine, table = _make_items_table_engine()
        records = [{"id": i, "name": f"n{i}"} for i in range(1, 6)]

        with engine.begin() as conn:
            MySQLDriverExecutemanyStrategy().execute(connection=conn, stmt=insert(table), records=records)

        with engine.connect() as conn:
            rows = conn.exec_driver_sql("SELECT id, name FROM items ORDER BY id").all()
        assert [tuple(r) for r in rows] == [(i, f"n{i}") for i in range(1, 6)]

    def test_values_bypass_type_processors(self) -> None:
        # Como la vía multi-fila con text(): el valor llega al driver tal cual (p.ej. el JSON ya serializado por
        # normalize_sql_literal no se vuelve a serializar).
        from sqlalchemy import JSON

        engine = create_engine("sqlite://")
        table = Table("docs", MetaData(), Column("id", Integer, primary_key=True), Column("j", JSON))
        table.metadata.create_all(engine)

        with engine.begin() as conn:
            MySQLDriverExecutemanyStrategy().execute(
                connection=conn, stmt=insert(table), records=[{"id": 1, "j": '{"k": 1}'}, {"id": 2, "j": None}]
            )

        with engine.connect() as conn:
            rows = conn.exec_driver_sql("SELECT id, j FROM docs ORDER BY id").all()
        assert [tuple(r) for r in rows] == [(1, '{"k": 1}'), (2, None)]

    def test_pyformat_uses_percent_placeholders_and_escapes_identifiers(self) -> None:
        from sqlalchemy.dialects.mysql.pymysql import MySQLDialect_pymysql

        table = Table("t%1", MetaData(), Column("id", Integer, primary_key=True), Column("a%b", String(10)))
        connection = MagicMock()
        connection.dialect = MySQLDialect_pymysql()

        MySQLDriverExecutemanyStrategy().execute(
            connection=connection, stmt=insert(table), records=[{"id": 1, "a%b": "x"}, {"id": 2, "a%b": "%s"}]
        )

        sql, params = connection.exec_driver_sql.call_args.args
        assert sql == "INSERT INTO `t%%1` (id, `a%%b`) VALUES (%s, %s)"
        assert params == [(1, "x"), (2, "%s")]
        connection.execute.assert_not_called()

    def test_empty_records_is_noop(self) -> None:
        connection = MagicMock()
        MySQLDriverExecutemanyStrategy().execute(connection=connection, stmt=MagicMock(), records=[])
        connection.exec_driver_sql.assert_not_called()
        connection.execute.assert_not_called()

    def test_update_stmt_falls_back_to_execute(self) -> None:
        engine, table = _make_items_table_engine()
        with engine.begin() as conn:
            conn.execute(table.insert(), [{"id": 1, "name": "old"}])

        stmt = update(table).where(table.c.id == bindparam("pk_id")).values(name=bindparam("name"))
        with engine.begin() as conn:
            MySQLDriverExecutemanyStrategy().execute(connection=conn, stmt=stmt, records=[{"name": "new", "pk_id": 1}])

        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT name FROM items WHERE id = 1").scalar() == "new"


# ---------------------------------------------------------------------------
# MariaDBConnectorInsertStrategy (PF-09)
# ---------------------------------------------------------------------------


class TestMariaDBConnectorInsertStrategy:
    """executemany del driver solo si cada columna del lote tiene un único tipo exacto (sin contar None)."""

    @staticmethod
    def _run(records: list[dict[str, Any]], stmt: Any | None = None) -> tuple[MagicMock, MagicMock]:
        table = Table("t", MetaData(), Column("id", Integer), Column("v", String))
        strategy = MariaDBConnectorInsertStrategy()
        strategy._driver_strategy = MagicMock()  # type: ignore[assignment]
        strategy._multirow_strategy = MagicMock()  # type: ignore[assignment]
        strategy.execute(connection=MagicMock(), stmt=insert(table) if stmt is None else stmt, records=records)
        return strategy._driver_strategy, strategy._multirow_strategy  # type: ignore[return-value]

    @pytest.mark.parametrize(
        "records",
        [
            [{"id": 1, "v": "a"}, {"id": 2, "v": "b"}],
            [{"id": 1, "v": None}, {"id": 2, "v": "b"}],  # None no rompe la uniformidad
            [{"id": 1, "v": None}, {"id": 2, "v": None}],
        ],
    )
    def test_uniform_types_use_driver_executemany(self, records: list[dict[str, Any]]) -> None:
        driver, multirow = self._run(records)
        driver.execute.assert_called_once()
        multirow.execute.assert_not_called()

    @pytest.mark.parametrize(
        "records",
        [
            [{"id": 1, "v": b"\x00"}, {"id": 2, "v": "texto"}],  # bytes + str: el driver falla
            [{"id": 1, "v": 1}, {"id": 2, "v": 2.5}],  # int + float: el driver falla
            [{"id": 1, "v": 1}, {"id": True, "v": 2}],  # int + bool: criterio estricto (tipo exacto)
        ],
    )
    def test_mixed_types_use_multirow(self, records: list[dict[str, Any]]) -> None:
        driver, multirow = self._run(records)
        multirow.execute.assert_called_once()
        driver.execute.assert_not_called()

    def test_non_insert_statement_uses_multirow(self) -> None:
        table = Table("t", MetaData(), Column("id", Integer), Column("v", String))
        driver, multirow = self._run([{"id": 1, "v": "a"}], stmt=update(table))
        multirow.execute.assert_called_once()
        driver.execute.assert_not_called()
