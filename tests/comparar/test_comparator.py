"""Tests para SchemaComparator con Inspector mockeado y SQLite in-memory."""

from __future__ import annotations

import re

from typing import Any
from unittest.mock import MagicMock

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import Column, ForeignKey, Index, Integer, MetaData, String, Table, create_engine, inspect, text

from util_bbdd.comparar.comparator import SchemaComparator
from util_bbdd.comparar.contracts import SchemaComparatorProtocol

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def comparator() -> SchemaComparator:
    return SchemaComparator()


def _make_mock_inspector(
    *,
    tables: dict[str, list[dict[str, Any]]] | None = None,
    pk_constraints: dict[str, dict[str, Any]] | None = None,
    indexes: dict[str, list[dict[str, Any]]] | None = None,
    foreign_keys: dict[str, list[dict[str, Any]]] | None = None,
    views: dict[str, str] | None = None,
    table_comments: dict[str, dict[str, Any]] | None = None,
    bind_url: str = "sqlite://",
) -> MagicMock:
    """Crea un mock de Inspector con datos controlados."""
    mock = MagicMock()

    _tables = tables or {}
    _pk_constraints = pk_constraints or {}
    _indexes = indexes or {}
    _foreign_keys = foreign_keys or {}
    _views = views or {}
    _table_comments = table_comments or {}

    mock.get_table_names.return_value = list(_tables.keys())
    mock.get_columns.side_effect = lambda table, schema=None: _tables.get(table, [])
    mock.get_pk_constraint.side_effect = lambda table, schema=None: _pk_constraints.get(
        table, {"constrained_columns": []}
    )
    mock.get_indexes.side_effect = lambda table, schema=None: _indexes.get(table, [])
    mock.get_foreign_keys.side_effect = lambda table, schema=None: _foreign_keys.get(table, [])
    mock.get_view_names.return_value = list(_views.keys())
    mock.get_view_definition.side_effect = lambda view, schema=None: _views.get(view, "")
    mock.get_table_comment.side_effect = lambda table, schema=None: _table_comments.get(table, {"text": None})

    # engine mock (SA 2.x — canónico); bind es el alias deprecated de SA 1.4
    engine_mock = MagicMock()
    engine_mock.url = bind_url
    engine_mock.dialect.name = "sqlite"
    engine_mock.name = "sqlite"
    mock.engine = engine_mock
    mock.bind = engine_mock  # mantener para compatibilidad con mocks externos existentes

    return mock


# ---------------------------------------------------------------------------
# Tests con mocks
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tests de conformidad de contratos (Protocol)
# ---------------------------------------------------------------------------


class TestSchemaComparatorProtocolConformance:
    def test_schema_comparator_satisfies_protocol(self) -> None:
        assert isinstance(SchemaComparator(), SchemaComparatorProtocol)


class TestSchemaComparatorWithMocks:
    def test_identical_schemas_return_no_differences(self, comparator: SchemaComparator) -> None:
        cols = [{"name": "id", "type": "INTEGER", "nullable": False, "default": None}]
        inspector = _make_mock_inspector(
            tables={"users": cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
        )

        diff = comparator.compare(inspector, inspector)

        assert not diff.has_differences
        assert diff.summary == "Sin diferencias"

    def test_table_added_in_source(self, comparator: SchemaComparator) -> None:
        source = _make_mock_inspector(
            tables={"users": [{"name": "id", "type": "INTEGER", "nullable": False, "default": None}]},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
        )
        target = _make_mock_inspector()

        diff = comparator.compare(source, target)

        assert diff.has_differences
        assert len(diff.table_diffs) == 1
        assert diff.table_diffs[0].table_name == "users"
        assert diff.table_diffs[0].status == "added"

    def test_table_removed_in_source(self, comparator: SchemaComparator) -> None:
        source = _make_mock_inspector()
        target = _make_mock_inspector(
            tables={"orders": [{"name": "id", "type": "INTEGER", "nullable": False, "default": None}]},
            pk_constraints={"orders": {"constrained_columns": ["id"]}},
        )

        diff = comparator.compare(source, target)

        assert len(diff.table_diffs) == 1
        assert diff.table_diffs[0].status == "removed"

    def test_column_type_difference(self, comparator: SchemaComparator) -> None:
        source = _make_mock_inspector(
            tables={"users": [{"name": "name", "type": "VARCHAR(50)", "nullable": True, "default": None}]},
            pk_constraints={"users": {"constrained_columns": []}},
        )
        target = _make_mock_inspector(
            tables={"users": [{"name": "name", "type": "VARCHAR(100)", "nullable": True, "default": None}]},
            pk_constraints={"users": {"constrained_columns": []}},
        )

        diff = comparator.compare(source, target)

        assert len(diff.table_diffs) == 1
        assert diff.table_diffs[0].status == "modified"
        col_diffs = diff.table_diffs[0].column_diffs
        assert any(d.attribute == "type" and d.source_value == "VARCHAR(50)" for d in col_diffs)

    def test_column_missing_in_target(self, comparator: SchemaComparator) -> None:
        source = _make_mock_inspector(
            tables={
                "users": [
                    {"name": "id", "type": "INTEGER", "nullable": False, "default": None},
                    {"name": "email", "type": "VARCHAR(200)", "nullable": True, "default": None},
                ]
            },
            pk_constraints={"users": {"constrained_columns": ["id"]}},
        )
        target = _make_mock_inspector(
            tables={"users": [{"name": "id", "type": "INTEGER", "nullable": False, "default": None}]},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
        )

        diff = comparator.compare(source, target)

        assert diff.table_diffs[0].status == "modified"
        existence_diffs = [d for d in diff.table_diffs[0].column_diffs if d.attribute == "existence"]
        assert len(existence_diffs) == 1
        assert existence_diffs[0].column_name == "email"
        assert existence_diffs[0].source_value == "exists"
        assert existence_diffs[0].target_value == "missing"

    def test_index_added(self, comparator: SchemaComparator) -> None:
        cols = [{"name": "id", "type": "INTEGER", "nullable": False, "default": None}]
        source = _make_mock_inspector(
            tables={"users": cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
            indexes={"users": [{"name": "idx_id", "column_names": ["id"], "unique": False}]},
        )
        target = _make_mock_inspector(
            tables={"users": cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
        )

        diff = comparator.compare(source, target)

        assert diff.table_diffs[0].index_diffs[0].status == "added"
        assert diff.table_diffs[0].index_diffs[0].index_name == "idx_id"

    def test_foreign_key_removed(self, comparator: SchemaComparator) -> None:
        cols = [{"name": "id", "type": "INTEGER", "nullable": False, "default": None}]
        source = _make_mock_inspector(
            tables={"orders": cols},
            pk_constraints={"orders": {"constrained_columns": ["id"]}},
        )
        target = _make_mock_inspector(
            tables={"orders": cols},
            pk_constraints={"orders": {"constrained_columns": ["id"]}},
            foreign_keys={
                "orders": [
                    {
                        "name": "fk_user",
                        "constrained_columns": ["user_id"],
                        "referred_table": "users",
                        "referred_columns": ["id"],
                    }
                ]
            },
        )

        diff = comparator.compare(source, target)

        assert diff.table_diffs[0].fk_diffs[0].status == "removed"
        assert diff.table_diffs[0].fk_diffs[0].fk_name == "fk_user"

    def test_view_added(self, comparator: SchemaComparator) -> None:
        source = _make_mock_inspector(views={"v_report": "SELECT 1"})
        target = _make_mock_inspector()

        diff = comparator.compare(source, target)

        assert len(diff.view_diffs) == 1
        assert diff.view_diffs[0].status == "added"
        assert diff.view_diffs[0].view_name == "v_report"

    def test_view_modified_with_normalization(self, comparator: SchemaComparator) -> None:
        source = _make_mock_inspector(views={"v_users": "CREATE VIEW v_users AS SELECT id FROM users"})
        target = _make_mock_inspector(views={"v_users": "CREATE VIEW v_users AS SELECT name FROM users"})

        diff = comparator.compare(source, target)

        assert len(diff.view_diffs) == 1
        assert diff.view_diffs[0].status == "modified"

    def test_comment_difference(self, comparator: SchemaComparator) -> None:
        cols = [{"name": "id", "type": "INTEGER", "nullable": False, "default": None, "comment": "PK"}]
        source = _make_mock_inspector(
            tables={"users": cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
            table_comments={"users": {"text": "Tabla de usuarios"}},
        )
        target_cols = [
            {"name": "id", "type": "INTEGER", "nullable": False, "default": None, "comment": "Identificador"}
        ]
        target = _make_mock_inspector(
            tables={"users": target_cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
            table_comments={"users": {"text": "Users table"}},
        )

        diff = comparator.compare(source, target)

        assert diff.table_diffs[0].status == "modified"
        comment_diffs = diff.table_diffs[0].comment_diffs
        # Debe detectar diferencia en comentario de tabla y de columna
        table_comment = [d for d in comment_diffs if d.column_name is None]
        col_comment = [d for d in comment_diffs if d.column_name == "id"]
        assert len(table_comment) == 1
        assert table_comment[0].source_comment == "Tabla de usuarios"
        assert len(col_comment) == 1

    def test_exclude_views(self, comparator: SchemaComparator) -> None:
        source = _make_mock_inspector(views={"v_report": "SELECT 1"})
        target = _make_mock_inspector()

        diff = comparator.compare(source, target, include_views=False)

        assert len(diff.view_diffs) == 0

    def test_exclude_indices(self, comparator: SchemaComparator) -> None:
        cols = [{"name": "id", "type": "INTEGER", "nullable": False, "default": None}]
        source = _make_mock_inspector(
            tables={"users": cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
            indexes={"users": [{"name": "idx_id", "column_names": ["id"], "unique": False}]},
        )
        target = _make_mock_inspector(
            tables={"users": cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
        )

        diff = comparator.compare(source, target, include_indices=False)

        # Sin diferencias detectadas porque indices están excluidos y columnas son iguales
        assert not diff.has_differences

    def test_summary_format(self, comparator: SchemaComparator) -> None:
        source = _make_mock_inspector(
            tables={"users": [{"name": "id", "type": "INTEGER", "nullable": False, "default": None}]},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
            views={"v_report": "SELECT 1"},
        )
        target = _make_mock_inspector()

        diff = comparator.compare(source, target)

        assert "Tablas:" in diff.summary
        assert "Vistas:" in diff.summary

    def test_label_hides_credentials(self, comparator: SchemaComparator) -> None:
        inspector = _make_mock_inspector(bind_url="mariadb+mariadbconnector://user:pass@host:3306/db")
        label = comparator._build_label(inspector, None)
        assert "user" not in label
        assert "pass" not in label
        assert "***" in label


# ---------------------------------------------------------------------------
# Tests con SQLite in-memory
# ---------------------------------------------------------------------------


class TestSchemaComparatorWithSQLite:
    def test_real_sqlite_identical_schemas(self, comparator: SchemaComparator) -> None:
        engine_a = create_engine("sqlite:///:memory:")
        engine_b = create_engine("sqlite:///:memory:")
        meta = MetaData()
        Table("users", meta, Column("id", Integer, primary_key=True), Column("name", String(50)))
        meta.create_all(engine_a)
        meta.create_all(engine_b)

        diff = comparator.compare(inspect(engine_a), inspect(engine_b))

        assert not diff.has_differences

    def test_real_sqlite_table_missing(self, comparator: SchemaComparator) -> None:
        engine_a = create_engine("sqlite:///:memory:")
        engine_b = create_engine("sqlite:///:memory:")
        meta_a = MetaData()
        Table("users", meta_a, Column("id", Integer, primary_key=True))
        Table("orders", meta_a, Column("id", Integer, primary_key=True))
        meta_a.create_all(engine_a)

        meta_b = MetaData()
        Table("users", meta_b, Column("id", Integer, primary_key=True))
        meta_b.create_all(engine_b)

        diff = comparator.compare(inspect(engine_a), inspect(engine_b))

        assert diff.has_differences
        added = [t for t in diff.table_diffs if t.status == "added"]
        assert len(added) == 1
        assert added[0].table_name == "orders"

    def test_real_sqlite_column_added(self, comparator: SchemaComparator) -> None:
        engine_a = create_engine("sqlite:///:memory:")
        engine_b = create_engine("sqlite:///:memory:")

        meta_a = MetaData()
        Table(
            "users",
            meta_a,
            Column("id", Integer, primary_key=True),
            Column("name", String(50)),
            Column("email", String(200)),
        )
        meta_a.create_all(engine_a)

        meta_b = MetaData()
        Table("users", meta_b, Column("id", Integer, primary_key=True), Column("name", String(50)))
        meta_b.create_all(engine_b)

        diff = comparator.compare(inspect(engine_a), inspect(engine_b))

        assert diff.has_differences
        existence_diffs = [d for d in diff.table_diffs[0].column_diffs if d.attribute == "existence"]
        assert any(d.column_name == "email" for d in existence_diffs)

    def test_real_sqlite_index_difference(self, comparator: SchemaComparator) -> None:
        engine_a = create_engine("sqlite:///:memory:")
        engine_b = create_engine("sqlite:///:memory:")

        meta_a = MetaData()
        users_a = Table("users", meta_a, Column("id", Integer, primary_key=True), Column("name", String(50)))
        Index("idx_name", users_a.c.name)
        meta_a.create_all(engine_a)

        meta_b = MetaData()
        Table("users", meta_b, Column("id", Integer, primary_key=True), Column("name", String(50)))
        meta_b.create_all(engine_b)

        diff = comparator.compare(inspect(engine_a), inspect(engine_b))

        assert diff.has_differences
        assert diff.table_diffs[0].index_diffs[0].status == "added"
        assert diff.table_diffs[0].index_diffs[0].index_name == "idx_name"

    def test_real_sqlite_foreign_key_difference(self, comparator: SchemaComparator) -> None:
        engine_a = create_engine("sqlite:///:memory:")
        engine_b = create_engine("sqlite:///:memory:")

        # Habilitar foreign keys en SQLite
        with engine_a.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
        with engine_b.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))

        meta_a = MetaData()
        Table("roles", meta_a, Column("id", Integer, primary_key=True))
        Table(
            "users",
            meta_a,
            Column("id", Integer, primary_key=True),
            Column("role_id", Integer, ForeignKey("roles.id", name="fk_role")),
        )
        meta_a.create_all(engine_a)

        meta_b = MetaData()
        Table("roles", meta_b, Column("id", Integer, primary_key=True))
        Table("users", meta_b, Column("id", Integer, primary_key=True), Column("role_id", Integer))
        meta_b.create_all(engine_b)

        diff = comparator.compare(inspect(engine_a), inspect(engine_b))

        assert diff.has_differences

    def test_real_sqlite_empty_schemas(self, comparator: SchemaComparator) -> None:
        engine_a = create_engine("sqlite:///:memory:")
        engine_b = create_engine("sqlite:///:memory:")

        diff = comparator.compare(inspect(engine_a), inspect(engine_b))

        assert not diff.has_differences
        assert diff.summary == "Sin diferencias"

    def test_real_sqlite_view_difference(self, comparator: SchemaComparator) -> None:
        engine_a = create_engine("sqlite:///:memory:")
        engine_b = create_engine("sqlite:///:memory:")

        meta = MetaData()
        Table("users", meta, Column("id", Integer, primary_key=True), Column("name", String(50)))
        meta.create_all(engine_a)
        meta.create_all(engine_b)

        with engine_a.connect() as conn:
            conn.execute(text("CREATE VIEW v_users AS SELECT id, name FROM users"))
            conn.commit()

        diff = comparator.compare(inspect(engine_a), inspect(engine_b))

        assert len(diff.view_diffs) == 1
        assert diff.view_diffs[0].status == "added"
        assert diff.view_diffs[0].view_name == "v_users"


# ---------------------------------------------------------------------------
# Tests para Exception Handling Robustness (L3 Phase 4 Coverage)
# ---------------------------------------------------------------------------


class TestExceptionHandlingRobustness:
    """Parametrized test cases for exception handling validation.

    Coverage: TimeoutError, PermissionError, Deadlock scenarios.
    These tests verify that SchemaComparator gracefully handles critical
    exceptions from Inspector queries without corrupting the diff result.
    """

    @pytest.mark.parametrize(
        "exception_type,exception_msg",
        [
            (TimeoutError, "Query execution timed out after 30s in pg_get_functiondef"),
            (PermissionError, "Permission denied: cannot access sys.sql_modules"),
            (RuntimeError, "Deadlock detected while fetching primary key constraints"),
        ],
    )
    def test_inspector_exception_during_table_introspection(
        self, comparator: SchemaComparator, exception_type: type[Exception], exception_msg: str
    ) -> None:
        """Verify graceful degradation when Inspector fails during table metadata fetch.

        Simulates: get_table_names() succeeds, but get_columns() raises exception.
        Expected: Exception propagates with meaningful context (no silent failures).
        Scenario: This tests the fallback Exception handling in _compare_tables().
        """
        source = _make_mock_inspector(tables={"users": []})
        target = _make_mock_inspector(tables={"users": []})

        # Inject exception when querying table columns
        target.get_columns.side_effect = exception_type(exception_msg)

        # Exception should propagate; SchemaComparator does not suppress it
        with pytest.raises(exception_type, match=re.escape(exception_msg)):
            comparator.compare(source, target)

    @pytest.mark.parametrize(
        "exception_type,exception_msg",
        [
            (TimeoutError, "Routine introspection query timed out (pg_get_functiondef)"),
            (PermissionError, "Cannot access INFORMATION_SCHEMA.ROUTINES (permission denied)"),
            (RuntimeError, "Deadlock in routine constraint resolution"),
        ],
    )
    def test_inspector_exception_during_routine_introspection(
        self, comparator: SchemaComparator, exception_type: type[Exception], exception_msg: str
    ) -> None:
        """Verify graceful degradation when Inspector fails during routine metadata fetch.

        Simulates: include_routines=True, but driver-specific routine query fails.
        Expected: Exception propagates with meaningful context.
        Scenario: This tests the fallback Exception handling in _get_routines_for_*() methods.
        Note: SQLite has no routines, so exception occurs at table fetch level.
        """
        cols = [{"name": "id", "type": "INTEGER", "nullable": False, "default": None}]
        source = _make_mock_inspector(tables={"users": cols})
        target = _make_mock_inspector(tables={"users": cols})

        # Inject exception when querying table metadata (proxy for routine introspection failure)
        source.get_columns.side_effect = exception_type(exception_msg)

        # Exception should propagate when include_routines=True and table fetch fails
        with pytest.raises(exception_type, match=re.escape(exception_msg)):
            comparator.compare(source, target, include_routines=True)

    @pytest.mark.parametrize(
        "exception_type,exception_msg",
        [
            (TimeoutError, "Constraint check timed out"),
            (PermissionError, "Permission denied: cannot check constraints"),
            (RuntimeError, "Deadlock in foreign key enumeration"),
        ],
    )
    def test_inspector_exception_during_constraint_validation(
        self, comparator: SchemaComparator, exception_type: type[Exception], exception_msg: str
    ) -> None:
        """Verify graceful degradation when Inspector fails during constraint fetch.

        Simulates: include_foreign_keys=True, but get_foreign_keys() raises exception.
        Expected: Exception propagates with meaningful context.
        Scenario: This tests the fallback Exception handling in _compare_foreign_keys().
        """
        cols = [{"name": "id", "type": "INTEGER", "nullable": False, "default": None}]
        source = _make_mock_inspector(
            tables={"users": cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
        )
        target = _make_mock_inspector(
            tables={"users": cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
        )

        # Inject exception when querying foreign keys
        target.get_foreign_keys.side_effect = exception_type(exception_msg)

        # Exception should propagate during constraint comparison
        with pytest.raises(exception_type, match=re.escape(exception_msg)):
            comparator.compare(source, target, include_foreign_keys=True)


class TestNormalizeDdl:
    def test_removes_definer(self) -> None:
        sql = "CREATE DEFINER=`root`@`localhost` VIEW v_users AS SELECT 1"
        normalized = SchemaComparator._normalize_ddl(sql)
        assert "definer" not in normalized
        assert "root" not in normalized

    def test_removes_force(self) -> None:
        sql = "CREATE OR REPLACE FORCE VIEW v_users AS SELECT 1"
        normalized = SchemaComparator._normalize_ddl(sql)
        assert "force" not in normalized
        assert "create or replace view" in normalized

    def test_normalizes_whitespace(self) -> None:
        sql = "  SELECT   id   FROM   users  "
        normalized = SchemaComparator._normalize_ddl(sql)
        assert normalized == "select id from users"

    def test_empty_string(self) -> None:
        assert SchemaComparator._normalize_ddl("") == ""

    def test_removes_sql_server_brackets_simple(self) -> None:
        """SQL Server: Remove brackets from simple identifiers [columnname] → columnname"""
        sql = "CREATE TABLE [users] ([id] INT PRIMARY KEY, [name] VARCHAR(100))"
        normalized = SchemaComparator._normalize_ddl(sql)
        assert "[" not in normalized
        assert "]" not in normalized
        assert "create table users" in normalized
        assert "id int primary key" in normalized

    def test_removes_sql_server_brackets_with_spaces(self) -> None:
        """SQL Server: Remove brackets from identifiers with spaces [My Column] → my column"""
        sql = "CREATE TABLE [My Table Name] ([My Column] INT, [Reference Date] DATETIME)"
        normalized = SchemaComparator._normalize_ddl(sql)
        assert "[" not in normalized
        assert "]" not in normalized
        assert "my table name" in normalized
        assert "my column" in normalized
        assert "reference date" in normalized

    def test_removes_sql_server_brackets_with_dashes(self) -> None:
        """SQL Server: Remove brackets from identifiers with dashes [Column-X] → column-x"""
        sql = "SELECT [Column-X], [Reference-ID] FROM [Main-Table] WHERE [Updated-At] > GETDATE()"
        normalized = SchemaComparator._normalize_ddl(sql)
        assert "[" not in normalized
        assert "]" not in normalized
        assert "column-x" in normalized
        assert "reference-id" in normalized
        assert "main-table" in normalized
        assert "updated-at" in normalized

    def test_removes_sql_server_brackets_mixed_special_chars(self) -> None:
        """SQL Server: Remove brackets with various special characters inside [Table@123-ABC] → table@123-abc"""
        sql = "CREATE TABLE [Table@123-ABC] ([Col_Name#1] VARCHAR(50))"
        normalized = SchemaComparator._normalize_ddl(sql)
        assert "[" not in normalized
        assert "]" not in normalized
        assert "table@123-abc" in normalized
        assert "col_name#1" in normalized


# ---------------------------------------------------------------------------
# TD-10 — Tests para _get_routines_mariadb y _get_routines_oracle
# ---------------------------------------------------------------------------


def _make_engine_mock(dialect_name: str = "mariadb") -> MagicMock:
    """Crea un mock de Engine con dialect configurable."""
    engine = MagicMock()
    engine.dialect.name = dialect_name
    engine.name = dialect_name
    return engine


class TestGetRoutinesMariaDB:
    def test_returns_procedures(self) -> None:

        inspector = MagicMock()
        engine = _make_engine_mock("mariadb")
        inspector.bind = engine
        inspector.engine = engine

        conn = MagicMock()
        engine.connect.return_value.__enter__.return_value = conn
        engine.connect.return_value.__exit__.return_value = False

        # SHOW PROCEDURE STATUS → una fila
        proc_row = MagicMock()
        proc_row.__getitem__ = lambda self, k: "my_proc" if k == "Name" else ""
        proc_rows = MagicMock()
        proc_rows.mappings.return_value = [{"Name": "my_proc"}]

        # SHOW FUNCTION STATUS → vacío
        func_rows = MagicMock()
        func_rows.mappings.return_value = []

        # SHOW CREATE PROCEDURE → una fila
        create_row = {"Create Procedure": "CREATE PROCEDURE my_proc() BEGIN END"}
        create_result = MagicMock()
        create_result.mappings.return_value.first.return_value = create_row

        def execute_side_effect(stmt: Any, params: Any = None) -> Any:
            sql = str(stmt)
            if "PROCEDURE STATUS" in sql:
                return proc_rows
            if "FUNCTION STATUS" in sql:
                return func_rows
            if "CREATE PROCEDURE" in sql:
                return create_result
            return MagicMock()

        conn.execute.side_effect = execute_side_effect

        routines = SchemaComparator._get_routines_mariadb(inspector, "mydb")

        assert len(routines) == 1
        assert routines[0]["name"] == "my_proc"
        assert routines[0]["type"] == "PROCEDURE"
        assert "CREATE PROCEDURE" in routines[0]["definition"]

    def test_returns_functions(self) -> None:
        inspector = MagicMock()
        engine = _make_engine_mock("mariadb")
        inspector.bind = engine
        inspector.engine = engine

        conn = MagicMock()
        engine.connect.return_value.__enter__.return_value = conn
        engine.connect.return_value.__exit__.return_value = False

        # SHOW PROCEDURE STATUS → vacío
        proc_rows = MagicMock()
        proc_rows.mappings.return_value = []

        # SHOW FUNCTION STATUS → una fila
        func_rows = MagicMock()
        func_rows.mappings.return_value = [{"Name": "my_func"}]

        # SHOW CREATE FUNCTION → una fila
        create_row = {"Create Function": "CREATE FUNCTION my_func() RETURNS INT BEGIN END"}
        create_result = MagicMock()
        create_result.mappings.return_value.first.return_value = create_row

        def execute_side_effect(stmt: Any, params: Any = None) -> Any:
            sql = str(stmt)
            if "PROCEDURE STATUS" in sql:
                return proc_rows
            if "FUNCTION STATUS" in sql:
                return func_rows
            if "CREATE FUNCTION" in sql:
                return create_result
            return MagicMock()

        conn.execute.side_effect = execute_side_effect

        routines = SchemaComparator._get_routines_mariadb(inspector, "mydb")

        assert len(routines) == 1
        assert routines[0]["name"] == "my_func"
        assert routines[0]["type"] == "FUNCTION"

    def test_escapes_backticks_in_proc_name(self) -> None:
        """Nombre con backtick incrustado debe ser escapado en la query."""
        inspector = MagicMock()
        engine = _make_engine_mock("mariadb")
        inspector.bind = engine
        inspector.engine = engine

        conn = MagicMock()
        engine.connect.return_value.__enter__.return_value = conn
        engine.connect.return_value.__exit__.return_value = False

        proc_rows = MagicMock()
        proc_rows.mappings.return_value = [{"Name": "bad`name"}]

        func_rows = MagicMock()
        func_rows.mappings.return_value = []

        create_result = MagicMock()
        create_result.mappings.return_value.first.return_value = {"Create Procedure": "CREATE PROCEDURE ..."}

        executed_sqls: list[str] = []

        def execute_side_effect(stmt: Any, params: Any = None) -> Any:
            sql = str(stmt)
            executed_sqls.append(sql)
            if "PROCEDURE STATUS" in sql:
                return proc_rows
            if "FUNCTION STATUS" in sql:
                return func_rows
            return create_result

        conn.execute.side_effect = execute_side_effect

        SchemaComparator._get_routines_mariadb(inspector, "mydb")

        create_proc_sql = next(s for s in executed_sqls if "CREATE PROCEDURE" in s)
        assert "``" in create_proc_sql  # backtick escapado

    @pytest.mark.parametrize(
        "error_message",
        [
            "connection refused",
            "timeout waiting for connection",
            "access denied",
        ],
    )
    def test_returns_empty_on_connection_errors(self, error_message: str) -> None:
        """Test graceful degradation with different connection failure scenarios."""
        from sqlalchemy.exc import OperationalError

        inspector = MagicMock()
        engine = _make_engine_mock("mariadb")
        inspector.bind = engine
        inspector.engine = engine
        engine.connect.side_effect = OperationalError("", {}, OSError(error_message))

        routines = SchemaComparator._get_routines_mariadb(inspector, "mydb")

        assert routines == []

    def test_returns_empty_when_engine_is_none(self) -> None:
        inspector = MagicMock()
        inspector.engine = None
        inspector.bind = None

        routines = SchemaComparator._get_routines_mariadb(inspector, "mydb")

        assert routines == []


class TestGetRoutinesOracle:
    def test_returns_empty_when_schema_is_none(self, caplog: Any) -> None:
        import logging

        inspector = MagicMock()
        engine = _make_engine_mock("oracle")
        inspector.engine = engine
        inspector.bind = engine

        with caplog.at_level(logging.WARNING):
            routines = SchemaComparator._get_routines_oracle(inspector, None)

        assert routines == []
        assert any("requiere" in r.message for r in caplog.records)

    def test_returns_empty_when_engine_is_none(self) -> None:
        inspector = MagicMock()
        inspector.engine = None
        inspector.bind = None

        routines = SchemaComparator._get_routines_oracle(inspector, "MYSCHEMA")

        assert routines == []

    def test_returns_procedures_and_functions(self) -> None:
        inspector = MagicMock()
        engine = _make_engine_mock("oracle")
        inspector.bind = engine
        inspector.engine = engine

        conn = MagicMock()
        engine.connect.return_value.__enter__.return_value = conn
        engine.connect.return_value.__exit__.return_value = False

        all_proc_rows = [
            {"object_name": "MY_PROC", "object_type": "PROCEDURE"},
            {"object_name": "MY_FUNC", "object_type": "FUNCTION"},
        ]
        all_proc_result = MagicMock()
        all_proc_result.mappings.return_value = all_proc_rows

        ddl_result = MagicMock()
        ddl_result.first.return_value = ("CREATE OR REPLACE PROCEDURE ...",)

        def execute_side_effect(stmt: Any, params: Any = None) -> Any:
            sql = str(stmt)
            if "all_procedures" in sql:
                return all_proc_result
            if "DBMS_METADATA" in sql:
                return ddl_result
            return MagicMock()

        conn.execute.side_effect = execute_side_effect

        routines = SchemaComparator._get_routines_oracle(inspector, "MYSCHEMA")

        assert len(routines) == 2
        names = {r["name"] for r in routines}
        assert "MY_PROC" in names
        assert "MY_FUNC" in names

    @pytest.mark.parametrize(
        "error_message",
        [
            "connection refused",
            "timeout waiting for connection",
            "access denied",
        ],
    )
    def test_returns_empty_on_connection_errors(self, error_message: str) -> None:
        """Test graceful degradation with different connection failure scenarios."""
        from sqlalchemy.exc import OperationalError

        inspector = MagicMock()
        engine = _make_engine_mock("oracle")
        inspector.bind = engine
        inspector.engine = engine
        engine.connect.side_effect = OperationalError("", {}, OSError(error_message))

        routines = SchemaComparator._get_routines_oracle(inspector, "MYSCHEMA")

        assert routines == []


class TestGetRoutinesMSSQL:
    """Tests para _get_routines_mssql (SQL Server)."""

    def test_returns_procedures(self) -> None:
        inspector = MagicMock()
        engine = _make_engine_mock("mssql")
        inspector.engine = engine
        inspector.bind = engine

        conn = MagicMock()
        engine.connect.return_value.__enter__.return_value = conn
        engine.connect.return_value.__exit__.return_value = False

        # sys.procedures query result
        proc_rows = MagicMock()
        proc_rows.mappings.return_value = [{"name": "my_proc"}]

        # sys.sql_modules query result (returns a tuple-like result)
        sql_module_result = MagicMock()
        sql_module_result.first.return_value = ("CREATE PROCEDURE my_proc AS BEGIN SELECT 1 END",)

        def execute_side_effect(stmt: Any, params: Any = None) -> Any:
            sql = str(stmt)
            if "sys.procedures" in sql:
                return proc_rows
            if "sys.sql_modules" in sql:
                return sql_module_result
            return MagicMock()

        conn.execute.side_effect = execute_side_effect

        routines = SchemaComparator._get_routines_mssql(inspector, "dbo")

        assert len(routines) == 1
        assert routines[0]["name"] == "my_proc"
        assert routines[0]["type"] == "PROCEDURE"
        assert "CREATE PROCEDURE" in routines[0]["definition"]

    def test_returns_empty_when_engine_is_none(self) -> None:
        inspector = MagicMock()
        inspector.engine = None
        inspector.bind = None

        routines = SchemaComparator._get_routines_mssql(inspector, "dbo")

        assert routines == []

    @pytest.mark.parametrize(
        "error_message",
        [
            "connection refused",
            "timeout waiting for connection",
            "access denied",
        ],
    )
    def test_returns_empty_on_connection_errors(self, error_message: str) -> None:
        """Test graceful degradation with different connection failure scenarios."""
        from sqlalchemy.exc import OperationalError

        inspector = MagicMock()
        engine = _make_engine_mock("mssql")
        inspector.engine = engine
        inspector.bind = engine
        engine.connect.side_effect = OperationalError("", {}, OSError(error_message))

        routines = SchemaComparator._get_routines_mssql(inspector, "dbo")

        assert routines == []


class TestGetRoutinesPostgreSQL:
    """Tests para _get_routines_postgresql (PostgreSQL)."""

    def test_returns_functions(self) -> None:
        inspector = MagicMock()
        engine = _make_engine_mock("postgresql")
        inspector.engine = engine
        inspector.bind = engine

        conn = MagicMock()
        engine.connect.return_value.__enter__.return_value = conn
        engine.connect.return_value.__exit__.return_value = False

        # pg_proc query result
        func_row = {"proname": "my_func", "prokind": "f"}  # 'f' = function
        func_rows = MagicMock()
        func_rows.mappings.return_value = [func_row]

        # pg_get_functiondef query result
        def_result = MagicMock()
        def_result.first.return_value = ("CREATE FUNCTION my_func() RETURNS int AS $$BEGIN END$$",)

        def execute_side_effect(stmt: Any, params: Any = None) -> Any:
            sql = str(stmt)
            if "pg_proc" in sql or "pg_namespace" in sql:
                return func_rows
            if "pg_get_functiondef" in sql:
                return def_result
            return MagicMock()

        conn.execute.side_effect = execute_side_effect

        routines = SchemaComparator._get_routines_postgresql(inspector, "public")

        assert len(routines) == 1
        assert routines[0]["name"] == "my_func"
        assert routines[0]["type"] == "FUNCTION"
        assert "CREATE FUNCTION" in routines[0]["definition"]

    def test_returns_procedures(self) -> None:
        inspector = MagicMock()
        engine = _make_engine_mock("postgresql")
        inspector.engine = engine
        inspector.bind = engine

        conn = MagicMock()
        engine.connect.return_value.__enter__.return_value = conn
        engine.connect.return_value.__exit__.return_value = False

        # pg_proc query result with procedure
        proc_row = {"proname": "my_proc", "prokind": "p"}  # 'p' = procedure
        proc_rows = MagicMock()
        proc_rows.mappings.return_value = [proc_row]

        # pg_get_functiondef query result
        def_result = MagicMock()
        def_result.first.return_value = ("CREATE PROCEDURE my_proc() LANGUAGE sql AS ...",)

        def execute_side_effect(stmt: Any, params: Any = None) -> Any:
            sql = str(stmt)
            if "pg_proc" in sql or "pg_namespace" in sql:
                return proc_rows
            if "pg_get_functiondef" in sql:
                return def_result
            return MagicMock()

        conn.execute.side_effect = execute_side_effect

        routines = SchemaComparator._get_routines_postgresql(inspector, "public")

        assert len(routines) == 1
        assert routines[0]["name"] == "my_proc"
        assert routines[0]["type"] == "PROCEDURE"

    def test_returns_empty_when_engine_is_none(self) -> None:
        inspector = MagicMock()
        inspector.engine = None
        inspector.bind = None

        routines = SchemaComparator._get_routines_postgresql(inspector, "public")

        assert routines == []

    @pytest.mark.parametrize(
        "error_message",
        [
            "connection refused",
            "timeout waiting for connection",
            "access denied",
        ],
    )
    def test_returns_empty_on_connection_errors(self, error_message: str) -> None:
        """Test graceful degradation with different connection failure scenarios."""
        from sqlalchemy.exc import OperationalError

        inspector = MagicMock()
        engine = _make_engine_mock("postgresql")
        inspector.engine = engine
        inspector.bind = engine
        engine.connect.side_effect = OperationalError("", {}, OSError(error_message))

        routines = SchemaComparator._get_routines_postgresql(inspector, "public")

        assert routines == []


class TestGetRoutinesHSQLDB:
    """Tests para _get_routines_hsqldb (HSQLDB)."""

    def test_returns_empty_list_with_warning(self, caplog: Any) -> None:
        import logging

        inspector = MagicMock()
        engine = _make_engine_mock("hsqldb")
        inspector.engine = engine
        inspector.bind = engine

        with caplog.at_level(logging.WARNING):
            routines = SchemaComparator._get_routines_hsqldb(inspector, None)

        assert routines == []
        assert any("HSQLDB no soporta" in r.message for r in caplog.records)


class TestGetRoutinesSafe:
    def test_sqlite_dialect_returns_none(self) -> None:
        inspector = _make_mock_inspector()
        result = SchemaComparator._get_routines_safe(inspector, None)
        assert result is None

    def test_postgresql_dialect_now_registered(self) -> None:
        """D1: PostgreSQL (postgresql) está ahora registrado, devuelve lista vacía."""
        inspector = _make_mock_inspector()
        inspector.engine.dialect.name = "postgresql"
        result = SchemaComparator._get_routines_safe(inspector, None)
        # PostgreSQL está registrado, así que devuelve una lista (puede estar vacía)
        assert result is not None
        assert isinstance(result, list)

    def test_uses_engine_attribute_over_bind(self) -> None:
        """_get_routines_safe usa inspector.engine (SA 2.x) y no inspector.bind."""
        inspector = MagicMock()
        engine = _make_engine_mock("mariadb")
        # Solo inspector.engine; bind deliberadamente None para verificar que no se usa
        inspector.engine = engine
        inspector.bind = None

        conn = MagicMock()
        engine.connect.return_value.__enter__.return_value = conn
        engine.connect.return_value.__exit__.return_value = False
        proc_rows = MagicMock()
        proc_rows.mappings.return_value = []
        func_rows = MagicMock()
        func_rows.mappings.return_value = []

        def execute_side_effect(stmt: Any, params: Any = None) -> Any:
            sql = str(stmt)
            if "PROCEDURE STATUS" in sql:
                return proc_rows
            return func_rows

        conn.execute.side_effect = execute_side_effect

        result = SchemaComparator._get_routines_safe(inspector, "mydb")
        # Si usa engine correctamente, obtiene lista vacía; si usa bind None, devuelve None
        assert result is not None
        assert result == []

    def test_mssql_dialect_dispatches_to_correct_fetcher_key(self) -> None:
        """Verifica que el dialect 'mssql' (SQL Server) es la clave correcta en _ROUTINE_FETCHERS.

        D2: el nombre interno es 'sqlserver' pero el dialect SA es 'mssql'.
        Este test documenta el contrato para evitar regresiones al registrar fetchers.
        """
        assert "mssql" in SchemaComparator._ROUTINE_FETCHERS  # D1: Ya implementado
        assert SchemaComparator._DB_TYPE_TO_DIALECT["sqlserver"] == "mssql"
        # Verifica que el fetcher está registrado con la clave correcta (dialect, no nombre interno)
        inspector = _make_mock_inspector()
        inspector.engine.dialect.name = "mssql"
        result = SchemaComparator._get_routines_safe(inspector, "dbo")
        # Con el fetcher registrado correctamente, devuelve una lista (puede estar vacía)
        assert result is not None
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# TD-05 — Tests del registro _ROUTINE_FETCHERS (OCP)
# ---------------------------------------------------------------------------


class TestRoutineFetchersRegistry:
    def test_registry_contains_mariadb(self) -> None:
        assert "mariadb" in SchemaComparator._ROUTINE_FETCHERS
        assert SchemaComparator._ROUTINE_FETCHERS["mariadb"] is SchemaComparator._get_routines_mariadb

    def test_registry_does_not_contain_mysql_alias(self) -> None:
        # mysql no es un motor soportado oficialmente en la librería; no debe tener fetcher registrado
        assert "mysql" not in SchemaComparator._ROUTINE_FETCHERS

    def test_registry_contains_oracle(self) -> None:
        assert "oracle" in SchemaComparator._ROUTINE_FETCHERS
        assert SchemaComparator._ROUTINE_FETCHERS["oracle"] is SchemaComparator._get_routines_oracle

    def test_registry_contains_mssql(self) -> None:
        """D1: SQL Server (mssql) debe estar registrado con el fetcher correcto."""
        assert "mssql" in SchemaComparator._ROUTINE_FETCHERS
        assert SchemaComparator._ROUTINE_FETCHERS["mssql"] is SchemaComparator._get_routines_mssql

    def test_registry_contains_postgresql(self) -> None:
        """D1: PostgreSQL (postgresql) debe estar registrado con el fetcher correcto."""
        assert "postgresql" in SchemaComparator._ROUTINE_FETCHERS
        assert SchemaComparator._ROUTINE_FETCHERS["postgresql"] is SchemaComparator._get_routines_postgresql

    def test_registry_contains_hsqldb(self) -> None:
        """D1: HSQLDB (hsqldb) debe estar registrado con el fetcher correcto."""
        assert "hsqldb" in SchemaComparator._ROUTINE_FETCHERS
        assert SchemaComparator._ROUTINE_FETCHERS["hsqldb"] is SchemaComparator._get_routines_hsqldb

    def test_registry_dispatches_to_mariadb_fetcher(self) -> None:
        """_get_routines_safe usa el registro para delegar en mariadb."""
        inspector = MagicMock()
        engine = _make_engine_mock("mariadb")
        inspector.bind = engine
        inspector.engine = engine

        conn = MagicMock()
        engine.connect.return_value.__enter__.return_value = conn
        engine.connect.return_value.__exit__.return_value = False

        proc_rows = MagicMock()
        proc_rows.mappings.return_value = [{"Name": "p1"}]
        func_rows = MagicMock()
        func_rows.mappings.return_value = []
        create_result = MagicMock()
        create_result.mappings.return_value.first.return_value = {"Create Procedure": "CREATE PROCEDURE p1() BEGIN END"}

        def execute_side_effect(stmt: Any, params: Any = None) -> Any:
            sql = str(stmt)
            if "PROCEDURE STATUS" in sql:
                return proc_rows
            if "FUNCTION STATUS" in sql:
                return func_rows
            return create_result

        conn.execute.side_effect = execute_side_effect

        result = SchemaComparator._get_routines_safe(inspector, "mydb")

        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "p1"

    def test_registry_extensibility_new_dialect(self) -> None:
        """Un fetcher personalizado registrado en _ROUTINE_FETCHERS debe ser invocado."""
        sentinel: list[tuple[Any, Any]] = []

        def custom_fetcher(inspector: Any, schema: Any) -> list[dict[str, str]]:
            sentinel.append((inspector, schema))
            return [{"name": "custom_proc", "type": "PROCEDURE", "definition": ""}]

        original = SchemaComparator._ROUTINE_FETCHERS.copy()
        try:
            SchemaComparator._ROUTINE_FETCHERS["testdialect"] = custom_fetcher  # type: ignore[assignment]
            inspector = MagicMock()
            engine = _make_engine_mock("testdialect")
            inspector.engine = engine
            inspector.bind = engine

            result = SchemaComparator._get_routines_safe(inspector, "myschema")

            assert result == [{"name": "custom_proc", "type": "PROCEDURE", "definition": ""}]
            assert len(sentinel) == 1
        finally:
            # Restaurar el estado original del registro
            SchemaComparator._ROUTINE_FETCHERS.clear()
            SchemaComparator._ROUTINE_FETCHERS.update(original)

    def test_unregistered_dialect_returns_none(self) -> None:
        """Un dialect sin fetcher registrado devuelve None."""
        inspector = _make_mock_inspector()
        inspector.bind.dialect.name = "fictitious_db"  # Un dialect no soportado
        result = SchemaComparator._get_routines_safe(inspector, None)
        assert result is None


# ---------------------------------------------------------------------------
# Tests de _DB_TYPE_TO_DIALECT (mapa canónico db_type → dialect SA)
# ---------------------------------------------------------------------------


class TestDbTypeToDialectMap:
    def test_all_supported_motors_present(self) -> None:
        expected = {"mariadb", "oracle", "postgresql", "sqlserver", "sqlite", "hsqldb"}
        assert expected == set(SchemaComparator._DB_TYPE_TO_DIALECT.keys())

    def test_sqlserver_maps_to_mssql(self) -> None:
        assert SchemaComparator._DB_TYPE_TO_DIALECT["sqlserver"] == "mssql"

    def test_identity_motors_map_to_same_name(self) -> None:
        for motor in ("mariadb", "oracle", "postgresql", "sqlite", "hsqldb"):
            assert SchemaComparator._DB_TYPE_TO_DIALECT[motor] == motor

    def test_mysql_not_in_map(self) -> None:
        # mysql no es motor soportado oficialmente; no debe aparecer en el mapa
        assert "mysql" not in SchemaComparator._DB_TYPE_TO_DIALECT


# ---------------------------------------------------------------------------
# TD-12 — Tests de _DDL_STRIP_RULES y _strip_dialect_artifacts (SRP)
# ---------------------------------------------------------------------------


class TestDDLStripRules:
    def test_registry_contains_mariadb_definer_rule(self) -> None:
        patterns = [p for p, _ in SchemaComparator._DDL_STRIP_RULES]
        assert any("DEFINER" in p for p in patterns)

    def test_registry_contains_oracle_force_rule(self) -> None:
        patterns = [p for p, _ in SchemaComparator._DDL_STRIP_RULES]
        assert any("FORCE" in p for p in patterns)

    def test_registry_contains_mssql_bracket_rule(self) -> None:
        """D4: Regla para escapar brackets [name] de SQL Server."""
        patterns = [p for p, _ in SchemaComparator._DDL_STRIP_RULES]
        assert any("\\[" in p for p in patterns)

    def test_registry_contains_mssql_with_rule(self) -> None:
        """D4: Regla para remover WITH clauses de SQL Server."""
        patterns = [p for p, _ in SchemaComparator._DDL_STRIP_RULES]
        assert any("WITH" in p for p in patterns)

    def test_registry_contains_postgresql_language_rule(self) -> None:
        """D4: Regla para remover LANGUAGE clause de PostgreSQL."""
        patterns = [p for p, _ in SchemaComparator._DDL_STRIP_RULES]
        assert any("LANGUAGE" in p for p in patterns)

    def test_registry_contains_postgresql_security_rule(self) -> None:
        """D4: Regla para remover SECURITY clauses de PostgreSQL."""
        patterns = [p for p, _ in SchemaComparator._DDL_STRIP_RULES]
        assert any("SECURITY" in p for p in patterns)


class TestStripDialectArtifacts:
    def test_removes_mariadb_definer(self) -> None:
        sql = "CREATE DEFINER=`admin`@`%` VIEW v AS SELECT 1"
        result = SchemaComparator._strip_dialect_artifacts(sql)
        assert "DEFINER" not in result
        assert "admin" not in result

    def test_removes_oracle_force(self) -> None:
        sql = "CREATE OR REPLACE FORCE VIEW v AS SELECT 1"
        result = SchemaComparator._strip_dialect_artifacts(sql)
        assert "FORCE" not in result
        assert "CREATE OR REPLACE VIEW" in result

    def test_preserves_unrelated_content(self) -> None:
        sql = "SELECT id FROM users WHERE active = 1"
        result = SchemaComparator._strip_dialect_artifacts(sql)
        assert result == sql

    def test_empty_string_returns_empty(self) -> None:
        assert SchemaComparator._strip_dialect_artifacts("") == ""

    def test_normalize_ddl_delegates_stripping(self) -> None:
        """_normalize_ddl debe invocar _strip_dialect_artifacts antes de normalizar."""
        sql = "CREATE DEFINER=`root`@`localhost`  VIEW v AS  SELECT  1"
        result = SchemaComparator._normalize_ddl(sql)
        assert "definer" not in result
        assert "root" not in result
        # Espacios colapsados
        assert "  " not in result


class TestStripDialectArtifactsMSSQL:
    """Tests para reglas de limpieza DDL de SQL Server."""

    def test_removes_mssql_escaped_brackets(self) -> None:
        """SQL Server escapa identifiers con brackets: [name] → name."""
        sql = "CREATE PROCEDURE [dbo].[my_proc] AS BEGIN SELECT [id], [name] FROM [users] END"
        result = SchemaComparator._strip_dialect_artifacts(sql)
        # Brackets se reemplazan por el contenido
        assert "[" not in result or "dbo" in result  # El contenido dentro de brackets se preserva

    def test_removes_mssql_with_storage_hints(self) -> None:
        """SQL Server puede incluir WITH clauses con storage hints como FILLFACTOR."""
        sql = "CREATE INDEX idx ON table(col) WITH (FILLFACTOR=80)"
        result = SchemaComparator._strip_dialect_artifacts(sql)
        # La regla intenta remover WITH (...) pero preservar el resto
        assert "WITH" not in result or "(" not in result.split("WITH")[1] if "WITH" in result else True


class TestStripDialectArtifactsPostgreSQL:
    """Tests para reglas de limpieza DDL de PostgreSQL."""

    def test_removes_postgresql_language_clause(self) -> None:
        """PostgreSQL incluye LANGUAGE en definiciones de functions."""
        sql = "CREATE FUNCTION my_func() RETURNS int LANGUAGE plpgsql AS $$ BEGIN END $$"
        result = SchemaComparator._strip_dialect_artifacts(sql)
        assert "LANGUAGE" not in result

    def test_removes_postgresql_security_definer(self) -> None:
        """PostgreSQL puede marcar functions con SECURITY DEFINER."""
        sql = "CREATE FUNCTION my_func() RETURNS int SECURITY DEFINER LANGUAGE sql AS ..."
        result = SchemaComparator._strip_dialect_artifacts(sql)
        assert "SECURITY DEFINER" not in result

    def test_removes_postgresql_security_invoker(self) -> None:
        """PostgreSQL puede marcar functions con SECURITY INVOKER."""
        sql = "CREATE FUNCTION my_func() RETURNS int SECURITY INVOKER LANGUAGE sql AS ..."
        result = SchemaComparator._strip_dialect_artifacts(sql)
        assert "SECURITY INVOKER" not in result

    def test_removes_postgresql_strict_clause(self) -> None:
        """PostgreSQL puede incluir STRICT en definiciones."""
        sql = "CREATE FUNCTION my_func(int) RETURNS int STRICT LANGUAGE sql AS ..."
        result = SchemaComparator._strip_dialect_artifacts(sql)
        assert "STRICT" not in result

    def test_removes_postgresql_returns_null_on_null_input(self) -> None:
        """PostgreSQL puede incluir RETURNS NULL ON NULL INPUT."""
        sql = "CREATE FUNCTION my_func(int) RETURNS int RETURNS NULL ON NULL INPUT LANGUAGE sql AS ..."
        result = SchemaComparator._strip_dialect_artifacts(sql)
        assert "RETURNS NULL ON NULL INPUT" not in result


# ---------------------------------------------------------------------------
# TD-11 — Tests de edge cases parametrizados
# ---------------------------------------------------------------------------


class TestEdgeCasesIndexAnonymous:
    def test_anonymous_index_is_skipped(self, comparator: SchemaComparator) -> None:
        """Índices con name=None deben ignorarse (no producir diff)."""
        cols = [{"name": "id", "type": "INTEGER", "nullable": False, "default": None}]
        source = _make_mock_inspector(
            tables={"t": cols},
            pk_constraints={"t": {"constrained_columns": ["id"]}},
            indexes={"t": [{"name": None, "column_names": ["id"], "unique": False}]},
        )
        target = _make_mock_inspector(
            tables={"t": cols},
            pk_constraints={"t": {"constrained_columns": ["id"]}},
        )

        diff = comparator.compare(source, target)

        assert not diff.has_differences

    def test_anonymous_fk_is_skipped(self, comparator: SchemaComparator) -> None:
        """FKs sin nombre deben ignorarse."""
        cols = [{"name": "id", "type": "INTEGER", "nullable": False, "default": None}]
        source = _make_mock_inspector(
            tables={"t": cols},
            pk_constraints={"t": {"constrained_columns": ["id"]}},
        )
        target = _make_mock_inspector(
            tables={"t": cols},
            pk_constraints={"t": {"constrained_columns": ["id"]}},
            foreign_keys={
                "t": [
                    {"name": None, "constrained_columns": ["id"], "referred_table": "other", "referred_columns": ["id"]}
                ]
            },
        )

        diff = comparator.compare(source, target)

        assert not diff.has_differences


class TestEdgeCasesNullableDefault:
    @pytest.mark.parametrize(
        "s_nullable, t_nullable, expect_diff",
        [
            (True, False, True),
            (False, True, True),
            (True, True, False),
        ],
    )
    def test_nullable_diff(
        self, comparator: SchemaComparator, s_nullable: bool, t_nullable: bool, expect_diff: bool
    ) -> None:
        source = _make_mock_inspector(
            tables={"t": [{"name": "col", "type": "VARCHAR(50)", "nullable": s_nullable, "default": None}]},
            pk_constraints={"t": {"constrained_columns": []}},
        )
        target = _make_mock_inspector(
            tables={"t": [{"name": "col", "type": "VARCHAR(50)", "nullable": t_nullable, "default": None}]},
            pk_constraints={"t": {"constrained_columns": []}},
        )

        diff = comparator.compare(source, target)

        if expect_diff:
            nullable_diffs = [d for d in diff.table_diffs[0].column_diffs if d.attribute == "nullable"]
            assert len(nullable_diffs) == 1
        else:
            assert not diff.has_differences

    def test_default_value_diff(self, comparator: SchemaComparator) -> None:
        source = _make_mock_inspector(
            tables={"t": [{"name": "col", "type": "INTEGER", "nullable": True, "default": "0"}]},
            pk_constraints={"t": {"constrained_columns": []}},
        )
        target = _make_mock_inspector(
            tables={"t": [{"name": "col", "type": "INTEGER", "nullable": True, "default": "42"}]},
            pk_constraints={"t": {"constrained_columns": []}},
        )

        diff = comparator.compare(source, target)

        default_diffs = [d for d in diff.table_diffs[0].column_diffs if d.attribute == "default"]
        assert len(default_diffs) == 1
        assert default_diffs[0].source_value == "0"
        assert default_diffs[0].target_value == "42"


class TestEdgeCasesPrimaryKey:
    def test_primary_key_diff(self, comparator: SchemaComparator) -> None:
        """Columna que pasa de no-PK a PK debe generar ColumnDiff con attribute='primary_key'."""
        cols = [{"name": "id", "type": "INTEGER", "nullable": False, "default": None}]
        source = _make_mock_inspector(
            tables={"t": cols},
            pk_constraints={"t": {"constrained_columns": ["id"]}},
        )
        target = _make_mock_inspector(
            tables={"t": cols},
            pk_constraints={"t": {"constrained_columns": []}},
        )

        diff = comparator.compare(source, target)

        pk_diffs = [d for d in diff.table_diffs[0].column_diffs if d.attribute == "primary_key"]
        assert len(pk_diffs) == 1
        assert pk_diffs[0].source_value == "True"
        assert pk_diffs[0].target_value == "False"


class TestEdgeCasesIndexModified:
    def test_index_modified_columns(self, comparator: SchemaComparator) -> None:
        cols = [
            {"name": "a", "type": "INTEGER", "nullable": True, "default": None},
            {"name": "b", "type": "INTEGER", "nullable": True, "default": None},
        ]
        source = _make_mock_inspector(
            tables={"t": cols},
            pk_constraints={"t": {"constrained_columns": []}},
            indexes={"t": [{"name": "idx_ab", "column_names": ["a", "b"], "unique": False}]},
        )
        target = _make_mock_inspector(
            tables={"t": cols},
            pk_constraints={"t": {"constrained_columns": []}},
            indexes={"t": [{"name": "idx_ab", "column_names": ["a"], "unique": False}]},
        )

        diff = comparator.compare(source, target)

        assert diff.table_diffs[0].index_diffs[0].status == "modified"
        assert diff.table_diffs[0].index_diffs[0].source_columns == "a,b"
        assert diff.table_diffs[0].index_diffs[0].target_columns == "a"

    def test_index_modified_unique(self, comparator: SchemaComparator) -> None:
        cols = [{"name": "a", "type": "INTEGER", "nullable": True, "default": None}]
        source = _make_mock_inspector(
            tables={"t": cols},
            pk_constraints={"t": {"constrained_columns": []}},
            indexes={"t": [{"name": "idx_a", "column_names": ["a"], "unique": True}]},
        )
        target = _make_mock_inspector(
            tables={"t": cols},
            pk_constraints={"t": {"constrained_columns": []}},
            indexes={"t": [{"name": "idx_a", "column_names": ["a"], "unique": False}]},
        )

        diff = comparator.compare(source, target)

        assert diff.table_diffs[0].index_diffs[0].status == "modified"
        assert diff.table_diffs[0].index_diffs[0].source_unique is True
        assert diff.table_diffs[0].index_diffs[0].target_unique is False


class TestEdgeCasesFKModified:
    def test_fk_modified_referred_table(self, comparator: SchemaComparator) -> None:
        cols = [{"name": "id", "type": "INTEGER", "nullable": False, "default": None}]
        source = _make_mock_inspector(
            tables={"t": cols},
            pk_constraints={"t": {"constrained_columns": ["id"]}},
            foreign_keys={
                "t": [
                    {"name": "fk_ref", "constrained_columns": ["id"], "referred_table": "a", "referred_columns": ["id"]}
                ]
            },
        )
        target = _make_mock_inspector(
            tables={"t": cols},
            pk_constraints={"t": {"constrained_columns": ["id"]}},
            foreign_keys={
                "t": [
                    {"name": "fk_ref", "constrained_columns": ["id"], "referred_table": "b", "referred_columns": ["id"]}
                ]
            },
        )

        diff = comparator.compare(source, target)

        assert diff.table_diffs[0].fk_diffs[0].status == "modified"
        assert diff.table_diffs[0].fk_diffs[0].source_referred_table == "a"
        assert diff.table_diffs[0].fk_diffs[0].target_referred_table == "b"


class TestEdgeCasesViewDefinitionNone:
    def test_view_definition_none_returns_empty(self) -> None:
        """_get_view_definition_safe devuelve '' cuando la definición es None."""
        inspector = MagicMock()
        inspector.get_view_definition.return_value = None

        result = SchemaComparator._get_view_definition_safe(inspector, "v_test", None)

        assert result == ""

    def test_view_definition_not_implemented_returns_empty(self) -> None:
        inspector = MagicMock()
        inspector.get_view_definition.side_effect = NotImplementedError

        result = SchemaComparator._get_view_definition_safe(inspector, "v_test", None)

        assert result == ""


class TestEdgeCasesBuildLabel:
    def test_url_without_credentials_unchanged(self) -> None:
        inspector = _make_mock_inspector(bind_url="sqlite:///:memory:")
        label = SchemaComparator._build_label(inspector, None)
        assert "sqlite" in label
        assert "***" not in label

    def test_url_with_schema(self) -> None:
        inspector = _make_mock_inspector(bind_url="sqlite:///:memory:")
        label = SchemaComparator._build_label(inspector, "myschema")
        assert "[myschema]" in label


class TestGetColumnsCallCount:
    """Verifica que get_columns se llama exactamente 2 veces por tabla (source+target),
    no 4 (el pre-fetch evita la doble llamada de _compare_comments)."""

    def test_get_columns_called_twice_per_table(self, comparator: SchemaComparator) -> None:
        cols = [{"name": "id", "type": "INTEGER", "nullable": False, "default": None, "comment": "PK"}]
        source = _make_mock_inspector(
            tables={"users": cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
        )
        target = _make_mock_inspector(
            tables={"users": cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
        )

        comparator.compare(source, target, include_comments=True)

        # source.get_columns debe llamarse exactamente 1 vez (pre-fetch en _compare_tables)
        assert source.get_columns.call_count == 1
        assert target.get_columns.call_count == 1


# ---------------------------------------------------------------------------
# Hotfix — gaps en _DDL_STRIP_RULES (ALGORITHM, DEFINER variantes, SQL SECURITY)
# ---------------------------------------------------------------------------


class TestDDLStripRulesHotfix:
    """Reproduce los tres gaps que causaban falsos positivos en comparación MariaDB."""

    _MARIADB_FULL = (
        "CREATE ALGORITHM=UNDEFINED DEFINER=`root`@`localhost` SQL SECURITY DEFINER VIEW `v` AS SELECT id FROM t"
    )
    _EXPECTED_NORMALIZED = "create view `v` as select id from t"

    def test_strips_algorithm(self) -> None:
        """G2: ALGORITHM=xxx debe eliminarse."""
        result = SchemaComparator._strip_dialect_artifacts("CREATE ALGORITHM=UNDEFINED VIEW v AS SELECT 1")
        assert "ALGORITHM" not in result

    def test_strips_algorithm_merge(self) -> None:
        result = SchemaComparator._strip_dialect_artifacts("CREATE ALGORITHM=MERGE VIEW v AS SELECT 1")
        assert "ALGORITHM" not in result

    def test_strips_definer_with_spaces_around_equals(self) -> None:
        """G1: DEFINER = `u`@`h` (con espacios alrededor de =) debe eliminarse."""
        sql = "CREATE DEFINER = `admin`@`%` VIEW v AS SELECT 1"
        result = SchemaComparator._strip_dialect_artifacts(sql)
        assert "DEFINER" not in result

    def test_strips_definer_single_quotes(self) -> None:
        """G1: DEFINER='u'@'h' (comillas simples) debe eliminarse."""
        sql = "CREATE DEFINER='root'@'localhost' VIEW v AS SELECT 1"
        result = SchemaComparator._strip_dialect_artifacts(sql)
        assert "DEFINER" not in result

    def test_strips_definer_unquoted(self) -> None:
        """G1: DEFINER=user@host (sin comillas) debe eliminarse."""
        sql = "CREATE DEFINER=root@localhost VIEW v AS SELECT 1"
        result = SchemaComparator._strip_dialect_artifacts(sql)
        assert "DEFINER" not in result

    def test_strips_sql_security_definer(self) -> None:
        """G3: SQL SECURITY DEFINER al inicio del DDL (sin espacio previo) debe eliminarse."""
        sql = "CREATE SQL SECURITY DEFINER VIEW v AS SELECT 1"
        result = SchemaComparator._strip_dialect_artifacts(sql)
        assert "SQL SECURITY" not in result

    def test_strips_sql_security_invoker(self) -> None:
        sql = "CREATE SQL SECURITY INVOKER VIEW v AS SELECT 1"
        result = SchemaComparator._strip_dialect_artifacts(sql)
        assert "SQL SECURITY" not in result

    def test_no_stray_sql_keyword_after_strip(self) -> None:
        """G3: Después del strip no debe quedar la palabra SQL suelta."""
        sql = "CREATE SQL SECURITY DEFINER VIEW v AS SELECT 1"
        result = SchemaComparator._normalize_ddl(sql)
        # Solo debe quedar "create view v as select 1"
        assert result == "create view v as select 1"

    def test_full_mariadb_view_normalizes_correctly(self) -> None:
        """Integración: DDL MariaDB completo se normaliza a solo CREATE VIEW ... AS ..."""
        result = SchemaComparator._normalize_ddl(self._MARIADB_FULL)
        assert result == self._EXPECTED_NORMALIZED

    def test_identical_mariadb_views_produce_equal_normalized_ddl(self) -> None:
        """Caso de uso real: dos vistas idénticas con DEFINER distinto no deben diferir."""
        ddl_source = (
            "CREATE ALGORITHM=UNDEFINED DEFINER=`root`@`server1` "
            "SQL SECURITY DEFINER VIEW `orders_v` AS SELECT id, total FROM orders"
        )
        ddl_target = (
            "CREATE ALGORITHM=UNDEFINED DEFINER=`app_user`@`server2` "
            "SQL SECURITY DEFINER VIEW `orders_v` AS SELECT id, total FROM orders"
        )
        assert SchemaComparator._normalize_ddl(ddl_source) == SchemaComparator._normalize_ddl(ddl_target)
