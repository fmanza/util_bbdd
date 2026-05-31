"""Tests unitarios para PKSequenceSyncer y PKSyncResult."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from sqlalchemy.sql.elements import TextClause

from util_bbdd.bulk._models import PKSyncResult
from util_bbdd.bulk._support.pk_sync import PKSequenceSyncer, _get_identity_pk_cols

# ---------------------------------------------------------------------------
# Helpers de construcción de mocks
# ---------------------------------------------------------------------------


def _make_engine(dialect_name: str) -> MagicMock:
    engine = MagicMock()
    engine.dialect.name = dialect_name
    engine.dialect.identifier_preparer.quote.side_effect = lambda name: name
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    engine.connect.return_value = conn
    return engine


def _make_col(name: str, *, autoincrement: bool = False, identity=None) -> MagicMock:
    col = MagicMock()
    col.name = name
    col.autoincrement = autoincrement
    col.identity = identity
    return col


def _make_table(name: str, pk_cols: list, schema: str | None = None) -> MagicMock:
    table = MagicMock()
    table.name = name
    table.schema = schema
    table.primary_key.columns = pk_cols
    return table


def _make_identity(always: bool = False) -> MagicMock:
    identity = MagicMock()
    identity.always = always
    return identity


def _text_sql_calls(conn: MagicMock) -> list[str]:
    """Extrae el SQL de las llamadas conn.execute(text(...)).

    Filtra sólo los argumentos que son TextClause (DDL/DML literales);
    ignora select() y otros objetos compilados.
    """
    result = []
    for c in conn.execute.call_args_list:
        if c.args and isinstance(c.args[0], TextClause):
            result.append(str(c.args[0]))
    return result


# ---------------------------------------------------------------------------
# PKSyncResult
# ---------------------------------------------------------------------------


class TestPKSyncResult:
    def test_defaults(self):
        r = PKSyncResult(
            table_name="users",
            column_name="id",
            engine_dialect="postgresql",
            max_value=42,
            status="synced",
        )
        assert r.error_msg == ""
        assert r.max_value == 42
        assert r.status == "synced"

    def test_no_rows_status(self):
        r = PKSyncResult(
            table_name="t",
            column_name="id",
            engine_dialect="mssql",
            max_value=None,
            status="no_rows",
        )
        assert r.max_value is None

    def test_error_status(self):
        r = PKSyncResult(
            table_name="t",
            column_name="id",
            engine_dialect="oracle",
            max_value=None,
            status="error",
            error_msg="ORA-00942",
        )
        assert "ORA-00942" in r.error_msg


# ---------------------------------------------------------------------------
# _get_identity_pk_cols
# ---------------------------------------------------------------------------


class TestGetIdentityPkCols:
    def test_returns_autoincrement_col(self):
        col = _make_col("id", autoincrement=True)
        natural = _make_col("code", autoincrement=False)
        table = _make_table("t", [col, natural])
        result = _get_identity_pk_cols(table)
        assert result == [col]

    def test_returns_identity_col(self):
        identity = _make_identity()
        col = _make_col("id", identity=identity)
        table = _make_table("t", [col])
        result = _get_identity_pk_cols(table)
        assert result == [col]

    def test_empty_when_no_identity(self):
        col = _make_col("code", autoincrement=False)
        table = _make_table("t", [col])
        assert _get_identity_pk_cols(table) == []

    def test_empty_table_pk(self):
        table = _make_table("t", [])
        assert _get_identity_pk_cols(table) == []


# ---------------------------------------------------------------------------
# PKSequenceSyncer — dialecto no soportado
# ---------------------------------------------------------------------------


class TestUnsupportedDialect:
    def test_sync_table_returns_unsupported(self):
        engine = _make_engine("sqlite")
        col = _make_col("id", autoincrement=True)
        table = _make_table("t", [col])
        syncer = PKSequenceSyncer(engine)
        results = syncer.sync_table(table)
        assert len(results) == 1
        assert results[0].status == "unsupported"
        assert "sqlite" in results[0].error_msg

    def test_sync_table_no_identity_cols_returns_empty(self):
        engine = _make_engine("sqlite")
        col = _make_col("code", autoincrement=False)
        table = _make_table("t", [col])
        syncer = PKSequenceSyncer(engine)
        assert syncer.sync_table(table) == []


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------


class TestPostgreSQL:
    def _make_pg_engine(self) -> MagicMock:
        return _make_engine("postgresql")

    def test_synced_with_rows(self):
        engine = self._make_pg_engine()
        conn = engine.connect.return_value
        # Llamadas a .scalar() en orden: pg_get_serial_sequence → seq name, MAX → 99
        conn.execute.return_value.scalar.side_effect = ["public.users_id_seq", 99]

        col = _make_col("id", identity=_make_identity())
        table = _make_table("users", [col], schema="public")

        syncer = PKSequenceSyncer(engine, schema="public")
        results = syncer.sync_table(table)

        assert len(results) == 1
        r = results[0]
        assert r.status == "synced"
        assert r.max_value == 99
        assert r.column_name == "id"

        # Verificar que se llamó setval con is_called=true
        sql_calls = _text_sql_calls(conn)
        assert any("setval" in s and "true" in s for s in sql_calls)

    def test_no_rows_empty_table(self):
        engine = self._make_pg_engine()
        conn = engine.connect.return_value
        conn.execute.return_value.scalar.side_effect = ["public.orders_id_seq", None]

        col = _make_col("id", autoincrement=True)
        table = _make_table("orders", [col], schema="public")

        syncer = PKSequenceSyncer(engine)
        results = syncer.sync_table(table)

        assert results[0].status == "no_rows"
        assert results[0].max_value is None
        # Verifica setval con is_called=false (tabla vacía)
        sql_calls = _text_sql_calls(conn)
        assert any("setval" in s and "false" in s for s in sql_calls)

    def test_skipped_when_no_sequence(self):
        engine = self._make_pg_engine()
        conn = engine.connect.return_value
        conn.execute.return_value.scalar.return_value = None

        col = _make_col("id", autoincrement=True)
        table = _make_table("t", [col])

        syncer = PKSequenceSyncer(engine)
        results = syncer.sync_table(table)

        assert results[0].status == "skipped"

    def test_error_is_captured(self):
        from sqlalchemy.exc import OperationalError

        engine = self._make_pg_engine()
        conn = engine.connect.return_value
        conn.execute.side_effect = OperationalError("stmt", {}, RuntimeError("permission denied"))

        col = _make_col("id", autoincrement=True)
        table = _make_table("t", [col])

        syncer = PKSequenceSyncer(engine)
        results = syncer.sync_table(table)

        assert results[0].status == "error"
        assert results[0].error_msg != ""


# ---------------------------------------------------------------------------
# SQL Server
# ---------------------------------------------------------------------------


class TestSQLServer:
    def _make_mssql_engine(self) -> MagicMock:
        return _make_engine("mssql")

    def test_synced_with_rows(self):
        engine = self._make_mssql_engine()
        conn = engine.connect.return_value
        conn.execute.return_value.scalar.return_value = 500

        col = _make_col("id", identity=_make_identity())
        table = _make_table("orders", [col], schema="dbo")

        syncer = PKSequenceSyncer(engine, schema="dbo")
        results = syncer.sync_table(table)

        assert results[0].status == "synced"
        assert results[0].max_value == 500

        sql_calls = _text_sql_calls(conn)
        assert any("RESEED" in s and "500" in s for s in sql_calls)

    def test_no_rows_reseeds_to_zero(self):
        engine = self._make_mssql_engine()
        conn = engine.connect.return_value
        conn.execute.return_value.scalar.return_value = None

        col = _make_col("id", identity=_make_identity())
        table = _make_table("t", [col])

        syncer = PKSequenceSyncer(engine)
        results = syncer.sync_table(table)

        assert results[0].status == "no_rows"
        sql_calls = _text_sql_calls(conn)
        assert any("RESEED" in s and ", 0" in s for s in sql_calls)

    def test_skipped_when_no_identity_property(self):
        engine = self._make_mssql_engine()

        # autoincrement=True pero sin propiedad identity declarativa
        col = _make_col("id", autoincrement=True, identity=None)
        table = _make_table("t", [col])

        syncer = PKSequenceSyncer(engine)
        results = syncer.sync_table(table)

        assert results[0].status == "skipped"


# ---------------------------------------------------------------------------
# MariaDB / MySQL
# ---------------------------------------------------------------------------


class TestMariaDB:
    @pytest.mark.parametrize("dialect", ["mariadb", "mysql"])
    def test_synced_with_rows(self, dialect):
        engine = _make_engine(dialect)
        conn = engine.connect.return_value
        conn.execute.return_value.scalar.return_value = 200

        col = _make_col("id", autoincrement=True)
        table = _make_table("products", [col])

        syncer = PKSequenceSyncer(engine)
        results = syncer.sync_table(table)

        assert results[0].status == "synced"
        assert results[0].max_value == 200

        sql_calls = _text_sql_calls(conn)
        assert any("AUTO_INCREMENT" in s and "201" in s for s in sql_calls)

    @pytest.mark.parametrize("dialect", ["mariadb", "mysql"])
    def test_no_rows_sets_auto_increment_to_1(self, dialect):
        engine = _make_engine(dialect)
        conn = engine.connect.return_value
        conn.execute.return_value.scalar.return_value = None

        col = _make_col("id", autoincrement=True)
        table = _make_table("t", [col])

        syncer = PKSequenceSyncer(engine)
        results = syncer.sync_table(table)

        assert results[0].status == "no_rows"
        assert results[0].max_value is None
        sql_calls = _text_sql_calls(conn)
        assert any("AUTO_INCREMENT" in s and "= 1" in s for s in sql_calls)


# ---------------------------------------------------------------------------
# Oracle >= 12c
# ---------------------------------------------------------------------------


class TestOracle:
    def _make_oracle_engine(self) -> MagicMock:
        return _make_engine("oracle")

    def test_synced_12c_with_schema(self):
        engine = self._make_oracle_engine()
        conn = engine.connect.return_value

        # fetchone devuelve la fila del catálogo; scalar devuelve MAX
        conn.execute.return_value.fetchone.return_value = ("ISEQ$$_74291",)
        conn.execute.return_value.scalar.return_value = 1000

        col = _make_col("id", identity=_make_identity(always=False))
        table = _make_table("employees", [col], schema="HR")

        syncer = PKSequenceSyncer(engine, schema="HR")
        results = syncer.sync_table(table)

        assert results[0].status == "synced"
        assert results[0].max_value == 1000

        sql_calls = _text_sql_calls(conn)
        assert any("RESTART START WITH" in s and "1001" in s for s in sql_calls)

    def test_synced_12c_no_schema_uses_user_view(self):
        engine = self._make_oracle_engine()
        conn = engine.connect.return_value

        conn.execute.return_value.fetchone.return_value = ("ISEQ$$_99999",)
        conn.execute.return_value.scalar.return_value = 50

        col = _make_col("id", identity=_make_identity())
        table = _make_table("orders", [col], schema=None)

        syncer = PKSequenceSyncer(engine)
        results = syncer.sync_table(table)

        assert results[0].status == "synced"
        # Verificar que se usó user_tab_identity_cols (sin schema → USER view)
        sql_calls = _text_sql_calls(conn)
        assert any("user_tab_identity_cols" in s.lower() for s in sql_calls)

    def test_unsupported_pre_12c_no_identity_attr(self):
        engine = self._make_oracle_engine()

        # Oracle pre-12c: autoincrement=True pero identity=None
        col = _make_col("id", autoincrement=True, identity=None)
        table = _make_table("t", [col])

        syncer = PKSequenceSyncer(engine)
        results = syncer.sync_table(table)

        assert results[0].status == "unsupported"
        assert "pre-12c" in results[0].error_msg.lower()

    def test_unsupported_sequence_not_found_in_catalog(self):
        engine = self._make_oracle_engine()
        conn = engine.connect.return_value
        conn.execute.return_value.fetchone.return_value = None

        col = _make_col("id", identity=_make_identity())
        table = _make_table("t", [col])

        syncer = PKSequenceSyncer(engine)
        results = syncer.sync_table(table)

        assert results[0].status == "unsupported"
        assert "not found" in results[0].error_msg.lower()

    def test_no_rows_restarts_at_1(self):
        engine = self._make_oracle_engine()
        conn = engine.connect.return_value

        conn.execute.return_value.fetchone.return_value = ("ISEQ$$_11111",)
        conn.execute.return_value.scalar.return_value = None  # tabla vacía

        col = _make_col("id", identity=_make_identity())
        table = _make_table("t", [col])

        syncer = PKSequenceSyncer(engine)
        results = syncer.sync_table(table)

        assert results[0].status == "no_rows"
        assert results[0].max_value is None
        sql_calls = _text_sql_calls(conn)
        assert any("RESTART START WITH 1" in s for s in sql_calls)


# ---------------------------------------------------------------------------
# sync_all
# ---------------------------------------------------------------------------


class TestSyncAll:
    def test_aggregates_results_from_all_tables(self):
        engine = _make_engine("postgresql")
        conn = engine.connect.return_value
        # Dos tablas: cada sync_table abre su propio with engine.connect() as conn
        # Ambas comparten el mismo mock conn. side_effect consume en orden.
        conn.execute.return_value.scalar.side_effect = [
            "seq_a",
            10,  # tabla a: pg_get_serial_sequence → seq, MAX → 10
            "seq_b",
            20,  # tabla b: pg_get_serial_sequence → seq, MAX → 20
        ]

        col_a = _make_col("id", autoincrement=True)
        col_b = _make_col("id", autoincrement=True)
        table_a = _make_table("a", [col_a])
        table_b = _make_table("b", [col_b])

        syncer = PKSequenceSyncer(engine)
        results = syncer.sync_all([table_a, table_b])

        assert len(results) == 2
        assert all(r.status == "synced" for r in results)
        assert {r.table_name for r in results} == {"a", "b"}

    def test_empty_table_list_returns_empty(self):
        engine = _make_engine("postgresql")
        syncer = PKSequenceSyncer(engine)
        assert syncer.sync_all([]) == []

    def test_table_without_identity_cols_not_in_results(self):
        engine = _make_engine("postgresql")
        natural_pk = _make_col("code", autoincrement=False)
        table = _make_table("lookup", [natural_pk])

        syncer = PKSequenceSyncer(engine)
        assert syncer.sync_all([table]) == []
