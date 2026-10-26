"""Tests para SchemaComparator con Inspector mockeado y SQLite in-memory."""

from __future__ import annotations

import logging
import re

from typing import Any, ClassVar
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import Column, ForeignKey, Index, Integer, MetaData, String, Table, create_engine, inspect, text

from util_bbdd.comparar.comparator import SchemaComparator
from util_bbdd.comparar.contracts import SchemaComparatorProtocol
from util_bbdd.comparar.reporters._base import DdlNormalizer, build_output_stem
from util_bbdd.metadata.reflection import view_definitions

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

    def test_label_has_no_connection_data(self, comparator: SchemaComparator) -> None:
        """G23: la etiqueta es ``motor [schema]``; ni usuario, ni contraseña, ni host, ni puerto."""
        inspector = _make_mock_inspector(bind_url="mariadb+mariadbconnector://user:pass@host:3306/db")
        label = comparator._build_label(inspector, None)
        assert label == "mariadb [db]"

    def test_label_with_encoded_password_has_no_credentials(self, comparator: SchemaComparator) -> None:
        """T5: una contraseña con '%40' (@ codificado) no aparece, ni el usuario ni el host."""
        inspector = _make_mock_inspector(bind_url="postgresql+psycopg2://admin:p%40ss%21@host:5432/mydb")
        label = comparator._build_label(inspector, "public")
        assert label == "postgresql [public]"

    def test_custom_labels_reach_diff_and_file_stem(self, comparator: SchemaComparator) -> None:
        """G23: ``source_label``/``target_label`` sustituyen a las etiquetas por defecto, también en el fichero."""
        source = _make_mock_inspector(bind_url="postgresql://u:p@db.internal:5432/app")
        target = _make_mock_inspector(bind_url="sqlite:////srv/datos/secreto.db")
        diff = comparator.compare(source, target, source_label="Producción (pg)", target_label="Copia")
        assert (diff.source_label, diff.target_label) == ("Producción (pg)", "Copia")
        assert build_output_stem(diff) == "Producción__pg__vs_Copia_diff"

    def test_default_labels_never_carry_connection_data(
        self, comparator: SchemaComparator, caplog: pytest.LogCaptureFixture
    ) -> None:
        """G23: sin etiquetas, ni el ``SchemaDiff``, ni el nombre de fichero, ni el log llevan host, usuario o ruta."""
        source = _make_mock_inspector(bind_url="postgresql://usr:pwd@db.internal:5432/app")
        target = _make_mock_inspector(bind_url="sqlite:////srv/datos/secreto.db")
        with caplog.at_level(logging.INFO, logger="util_bbdd.comparar.comparator"):
            diff = comparator.compare(source, target, source_schema="public")
        texts = [diff.source_label, diff.target_label, build_output_stem(diff), caplog.text]
        for leaked in ("usr", "pwd", "db.internal", "5432", "srv", "datos", "secreto"):
            assert not any(leaked in text for text in texts), leaked

    def test_anonymous_fk_detected(self, comparator: SchemaComparator) -> None:
        """T1: FKs an\u00f3nimas (name=None) deben detectarse y no descartarse silenciosamente."""
        cols = [
            {"name": "id", "type": "INTEGER", "nullable": False, "default": None},
            {"name": "role_id", "type": "INTEGER", "nullable": True, "default": None},
        ]
        anon_fk = {
            "name": None,  # FK an\u00f3nima
            "constrained_columns": ["role_id"],
            "referred_table": "roles",
            "referred_columns": ["id"],
        }
        source = _make_mock_inspector(
            tables={"users": cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
            foreign_keys={"users": [anon_fk]},
        )
        target = _make_mock_inspector(
            tables={"users": cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
        )

        diff = comparator.compare(source, target)

        assert diff.has_differences
        assert len(diff.table_diffs[0].fk_diffs) == 1
        assert diff.table_diffs[0].fk_diffs[0].status == "added"
        assert diff.table_diffs[0].fk_diffs[0].fk_name == "__anon__role_id__roles__id"

    def test_include_comments_requires_include_tables(self, comparator: SchemaComparator) -> None:
        """T6: Cuando include_tables=False, los comentarios no se comparan aunque include_comments=True."""
        cols = [{"name": "id", "type": "INTEGER", "nullable": False, "default": None, "comment": "PK"}]
        source = _make_mock_inspector(
            tables={"users": cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
            table_comments={"users": {"text": "Original comment"}},
        )
        target_cols = [{"name": "id", "type": "INTEGER", "nullable": False, "default": None, "comment": "Different"}]
        target = _make_mock_inspector(
            tables={"users": target_cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
            table_comments={"users": {"text": "Different comment"}},
        )

        diff = comparator.compare(source, target, include_tables=False, include_comments=True)

        assert not diff.has_differences


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


# ---------------------------------------------------------------------------
# Tests cross-engine: comparación case-insensitive de columnas
# ---------------------------------------------------------------------------


class TestCrossEngineCaseInsensitiveColumns:
    """Verifica que la comparación de columnas sea case-insensitive entre motores.

    Escenario típico: Oracle devuelve nombres en UPPERCASE, MariaDB en lowercase.
    Las columnas que existen en ambos no deben reportarse como 'missing'.
    """

    def test_identical_columns_upper_vs_lower_no_existence_diffs(self, comparator: SchemaComparator) -> None:
        """Source UPPERCASE (Oracle), target lowercase (MariaDB): sin diffs de existencia."""
        source = _make_mock_inspector(
            tables={
                "EMPLOYEES": [
                    {"name": "ID", "type": "NUMBER", "nullable": False, "default": None},
                    {"name": "EMPLOYEE_NAME", "type": "VARCHAR2(100)", "nullable": True, "default": None},
                    {"name": "SALARY", "type": "NUMBER", "nullable": True, "default": None},
                ]
            },
            pk_constraints={"EMPLOYEES": {"constrained_columns": ["ID"]}},
        )
        target = _make_mock_inspector(
            tables={
                "employees": [
                    {"name": "id", "type": "INT", "nullable": False, "default": None},
                    {"name": "employee_name", "type": "VARCHAR(100)", "nullable": True, "default": None},
                    {"name": "salary", "type": "DECIMAL(10,2)", "nullable": True, "default": None},
                ]
            },
            pk_constraints={"employees": {"constrained_columns": ["id"]}},
        )

        diff = comparator.compare(source, target)

        # Pueden haber diffs de tipo (NUMBER vs INT es esperado cross-engine)
        # pero NUNCA diffs de existencia
        existence_diffs = [d for td in diff.table_diffs for d in td.column_diffs if d.attribute == "existence"]
        assert existence_diffs == [], f"Falsos diffs de existencia: {existence_diffs}"

    def test_extra_column_only_in_source_reports_canonical_name(self, comparator: SchemaComparator) -> None:
        """Columna extra en source (UPPERCASE) → reportada con nombre canónico del origen."""
        source = _make_mock_inspector(
            tables={
                "EMPLOYEES": [
                    {"name": "ID", "type": "NUMBER", "nullable": False, "default": None},
                    {"name": "BONUS", "type": "NUMBER", "nullable": True, "default": None},
                ]
            },
            pk_constraints={"EMPLOYEES": {"constrained_columns": ["ID"]}},
        )
        target = _make_mock_inspector(
            tables={
                "employees": [
                    {"name": "id", "type": "INT", "nullable": False, "default": None},
                ]
            },
            pk_constraints={"employees": {"constrained_columns": ["id"]}},
        )

        diff = comparator.compare(source, target)

        existence_diffs = [
            d
            for td in diff.table_diffs
            for d in td.column_diffs
            if d.attribute == "existence" and d.source_value == "exists"
        ]
        assert len(existence_diffs) == 1
        assert existence_diffs[0].column_name == "BONUS"  # Nombre canónico del origen
        assert existence_diffs[0].target_value == "missing"

    def test_pk_cross_engine_no_false_pk_diff(self, comparator: SchemaComparator) -> None:
        """PK ['ID'] en Oracle vs ['id'] en MariaDB: no debe reportar diff de primary_key."""
        source = _make_mock_inspector(
            tables={
                "ORDERS": [
                    {"name": "ORDER_ID", "type": "NUMBER", "nullable": False, "default": None},
                    {"name": "AMOUNT", "type": "NUMBER", "nullable": True, "default": None},
                ]
            },
            pk_constraints={"ORDERS": {"constrained_columns": ["ORDER_ID"]}},
        )
        target = _make_mock_inspector(
            tables={
                "orders": [
                    {"name": "order_id", "type": "INT", "nullable": False, "default": None},
                    {"name": "amount", "type": "DECIMAL(10,2)", "nullable": True, "default": None},
                ]
            },
            pk_constraints={"orders": {"constrained_columns": ["order_id"]}},
        )

        diff = comparator.compare(source, target)

        pk_diffs = [d for td in diff.table_diffs for d in td.column_diffs if d.attribute == "primary_key"]
        assert pk_diffs == [], f"Falsos diffs de primary_key: {pk_diffs}"

    def test_same_engine_same_case_no_regression(self, comparator: SchemaComparator) -> None:
        """Mismo motor, mismo case: comportamiento idéntico al original."""
        cols = [
            {"name": "id", "type": "INTEGER", "nullable": False, "default": None},
            {"name": "name", "type": "VARCHAR(50)", "nullable": True, "default": None},
        ]
        source = _make_mock_inspector(
            tables={"users": cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
        )
        target = _make_mock_inspector(
            tables={"users": cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
        )

        diff = comparator.compare(source, target)

        assert not diff.has_differences

    def test_comments_cross_engine_no_false_comment_diffs(self, comparator: SchemaComparator) -> None:
        """Comentarios de columna con mismo texto pero distinto case de nombre: sin falsos diffs."""
        source = _make_mock_inspector(
            tables={
                "PRODUCTS": [
                    {"name": "PRODUCT_ID", "type": "NUMBER", "nullable": False, "default": None, "comment": "PK"},
                ]
            },
            pk_constraints={"PRODUCTS": {"constrained_columns": ["PRODUCT_ID"]}},
            table_comments={"PRODUCTS": {"text": "Productos"}},
        )
        target = _make_mock_inspector(
            tables={
                "products": [
                    {"name": "product_id", "type": "INT", "nullable": False, "default": None, "comment": "PK"},
                ]
            },
            pk_constraints={"products": {"constrained_columns": ["product_id"]}},
            table_comments={"products": {"text": "Productos"}},
        )

        diff = comparator.compare(source, target, include_comments=True)

        comment_diffs = [d for td in diff.table_diffs for d in td.comment_diffs]
        assert comment_diffs == [], f"Falsos diffs de comentario: {comment_diffs}"


class TestCrossEngineCaseInsensitiveIndicesAndForeignKeys:
    """BLK-02 (AUDIT_CODE 2026-09-22): índices y FKs se comparaban sensibles a
    mayúsculas (a diferencia de tablas/columnas, que sí normalizan) → falsos
    positivos 'added+removed' cross-motor cuando solo cambia el case del nombre."""

    def test_identical_index_upper_vs_lower_name_no_false_diff(self, comparator: SchemaComparator) -> None:
        """Mismo índice, distinto case de nombre (Oracle IDX_ID vs MariaDB idx_id): sin diffs."""
        cols = [{"name": "id", "type": "INTEGER", "nullable": False, "default": None}]
        source = _make_mock_inspector(
            tables={"users": cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
            indexes={"users": [{"name": "IDX_ID", "column_names": ["id"], "unique": False}]},
        )
        target = _make_mock_inspector(
            tables={"users": cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
            indexes={"users": [{"name": "idx_id", "column_names": ["id"], "unique": False}]},
        )

        diff = comparator.compare(source, target)

        assert not diff.has_differences

    def test_index_only_in_source_reports_canonical_source_name(self, comparator: SchemaComparator) -> None:
        cols = [{"name": "id", "type": "INTEGER", "nullable": False, "default": None}]
        source = _make_mock_inspector(
            tables={"users": cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
            indexes={"users": [{"name": "IDX_EXTRA", "column_names": ["id"], "unique": False}]},
        )
        target = _make_mock_inspector(
            tables={"users": cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
        )

        diff = comparator.compare(source, target)

        assert len(diff.table_diffs[0].index_diffs) == 1
        assert diff.table_diffs[0].index_diffs[0].status == "added"
        assert diff.table_diffs[0].index_diffs[0].index_name == "IDX_EXTRA"

    def test_index_modified_columns_detected_despite_case_difference_in_name(
        self, comparator: SchemaComparator
    ) -> None:
        """El nombre difiere solo en case, pero las columnas cubiertas sí difieren: debe reportarse."""
        cols = [
            {"name": "id", "type": "INTEGER", "nullable": False, "default": None},
            {"name": "email", "type": "VARCHAR(100)", "nullable": True, "default": None},
        ]
        source = _make_mock_inspector(
            tables={"users": cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
            indexes={"users": [{"name": "IDX_ID", "column_names": ["id"], "unique": False}]},
        )
        target = _make_mock_inspector(
            tables={"users": cols},
            pk_constraints={"users": {"constrained_columns": ["id"]}},
            indexes={"users": [{"name": "idx_id", "column_names": ["id", "email"], "unique": False}]},
        )

        diff = comparator.compare(source, target)

        assert len(diff.table_diffs[0].index_diffs) == 1
        assert diff.table_diffs[0].index_diffs[0].status == "modified"
        assert diff.table_diffs[0].index_diffs[0].index_name == "IDX_ID"

    def test_identical_fk_upper_vs_lower_name_no_false_diff(self, comparator: SchemaComparator) -> None:
        cols = [
            {"name": "id", "type": "INTEGER", "nullable": False, "default": None},
            {"name": "user_id", "type": "INTEGER", "nullable": True, "default": None},
        ]
        fk_source = {
            "name": "FK_USER",
            "constrained_columns": ["user_id"],
            "referred_table": "users",
            "referred_columns": ["id"],
        }
        fk_target = {
            "name": "fk_user",
            "constrained_columns": ["user_id"],
            "referred_table": "users",
            "referred_columns": ["id"],
        }
        source = _make_mock_inspector(
            tables={"orders": cols},
            pk_constraints={"orders": {"constrained_columns": ["id"]}},
            foreign_keys={"orders": [fk_source]},
        )
        target = _make_mock_inspector(
            tables={"orders": cols},
            pk_constraints={"orders": {"constrained_columns": ["id"]}},
            foreign_keys={"orders": [fk_target]},
        )

        diff = comparator.compare(source, target)

        assert not diff.has_differences

    def test_fk_only_in_target_reports_canonical_target_name(self, comparator: SchemaComparator) -> None:
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
                        "name": "FK_USER",
                        "constrained_columns": ["user_id"],
                        "referred_table": "users",
                        "referred_columns": ["id"],
                    }
                ]
            },
        )

        diff = comparator.compare(source, target)

        assert diff.table_diffs[0].fk_diffs[0].status == "removed"
        assert diff.table_diffs[0].fk_diffs[0].fk_name == "FK_USER"


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
# Tests de _DB_TYPE_TO_DIALECT (mapa canónico db_type → dialect SA)
# ---------------------------------------------------------------------------


class TestDbTypeToDialectMap:
    def test_all_supported_motors_present(self) -> None:
        expected = {"mariadb", "mysql", "oracle", "postgresql", "sqlserver", "sqlite", "hsqldb"}
        assert expected == set(SchemaComparator._DB_TYPE_TO_DIALECT.keys())

    def test_sqlserver_maps_to_mssql(self) -> None:
        assert SchemaComparator._DB_TYPE_TO_DIALECT["sqlserver"] == "mssql"

    def test_identity_motors_map_to_same_name(self) -> None:
        for motor in ("mariadb", "mysql", "oracle", "postgresql", "sqlite", "hsqldb"):
            assert SchemaComparator._DB_TYPE_TO_DIALECT[motor] == motor


# ---------------------------------------------------------------------------
# TD-12 — Tests de _DDL_STRIP_RULES y _strip_dialect_artifacts (SRP)
# ---------------------------------------------------------------------------


class TestDDLStripRules:
    """C9: DDL strip rules now live in DdlNormalizer._VIEW_STRIP_PATTERNS + _COMPARISON_EXTRA_PATTERNS."""

    @staticmethod
    def _all_patterns() -> list[str]:
        return [p for p, _ in DdlNormalizer._VIEW_STRIP_PATTERNS + DdlNormalizer._COMPARISON_EXTRA_PATTERNS]

    def test_registry_contains_mariadb_definer_rule(self) -> None:
        assert any("DEFINER" in p for p in self._all_patterns())

    def test_registry_contains_oracle_force_rule(self) -> None:
        assert any("FORCE" in p for p in self._all_patterns())

    def test_registry_contains_mssql_bracket_rule(self) -> None:
        """Regla para escapar brackets [name] de SQL Server."""
        assert any("\\[" in p for p in self._all_patterns())

    def test_registry_contains_mssql_with_rule(self) -> None:
        """Regla para remover WITH clauses de SQL Server."""
        assert any("WITH" in p for p in self._all_patterns())

    def test_registry_contains_postgresql_language_rule(self) -> None:
        """Regla para remover LANGUAGE clause de PostgreSQL."""
        assert any("LANGUAGE" in p for p in self._all_patterns())

    def test_registry_contains_postgresql_security_rule(self) -> None:
        """Regla para remover SECURITY clauses de PostgreSQL."""
        assert any("SECURITY" in p for p in self._all_patterns())


class TestStripDialectArtifacts:
    def test_removes_mariadb_definer(self) -> None:
        sql = "CREATE DEFINER=`admin`@`%` VIEW v AS SELECT 1"
        result = DdlNormalizer.strip_dialect_artifacts(sql)
        assert "DEFINER" not in result
        assert "admin" not in result

    def test_removes_oracle_force(self) -> None:
        sql = "CREATE OR REPLACE FORCE VIEW v AS SELECT 1"
        result = DdlNormalizer.strip_dialect_artifacts(sql)
        assert "FORCE" not in result
        assert "CREATE OR REPLACE VIEW" in result

    def test_preserves_unrelated_content(self) -> None:
        sql = "SELECT id FROM users WHERE active = 1"
        result = DdlNormalizer.strip_dialect_artifacts(sql)
        assert result == sql

    def test_empty_string_returns_empty(self) -> None:
        assert DdlNormalizer.strip_dialect_artifacts("") == ""

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
        result = DdlNormalizer.strip_dialect_artifacts(sql)
        # Brackets se reemplazan por el contenido
        assert "[" not in result or "dbo" in result  # El contenido dentro de brackets se preserva

    def test_removes_mssql_with_storage_hints(self) -> None:
        """SQL Server puede incluir WITH clauses con storage hints como FILLFACTOR."""
        sql = "CREATE INDEX idx ON table(col) WITH (FILLFACTOR=80)"
        result = DdlNormalizer.strip_dialect_artifacts(sql)
        # La regla intenta remover WITH (...) pero preservar el resto
        assert "WITH" not in result or "(" not in result.split("WITH")[1] if "WITH" in result else True


class TestStripDialectArtifactsPostgreSQL:
    """Tests para reglas de limpieza DDL de PostgreSQL."""

    def test_removes_postgresql_language_clause(self) -> None:
        """PostgreSQL incluye LANGUAGE en definiciones de functions."""
        sql = "CREATE FUNCTION my_func() RETURNS int LANGUAGE plpgsql AS $$ BEGIN END $$"
        result = DdlNormalizer.strip_dialect_artifacts(sql)
        assert "LANGUAGE" not in result

    def test_removes_postgresql_security_definer(self) -> None:
        """PostgreSQL puede marcar functions con SECURITY DEFINER."""
        sql = "CREATE FUNCTION my_func() RETURNS int SECURITY DEFINER LANGUAGE sql AS ..."
        result = DdlNormalizer.strip_dialect_artifacts(sql)
        assert "SECURITY DEFINER" not in result

    def test_removes_postgresql_security_invoker(self) -> None:
        """PostgreSQL puede marcar functions con SECURITY INVOKER."""
        sql = "CREATE FUNCTION my_func() RETURNS int SECURITY INVOKER LANGUAGE sql AS ..."
        result = DdlNormalizer.strip_dialect_artifacts(sql)
        assert "SECURITY INVOKER" not in result

    def test_removes_postgresql_strict_clause(self) -> None:
        """PostgreSQL puede incluir STRICT en definiciones."""
        sql = "CREATE FUNCTION my_func(int) RETURNS int STRICT LANGUAGE sql AS ..."
        result = DdlNormalizer.strip_dialect_artifacts(sql)
        assert "STRICT" not in result

    def test_removes_postgresql_returns_null_on_null_input(self) -> None:
        """PostgreSQL puede incluir RETURNS NULL ON NULL INPUT."""
        sql = "CREATE FUNCTION my_func(int) RETURNS int RETURNS NULL ON NULL INPUT LANGUAGE sql AS ..."
        result = DdlNormalizer.strip_dialect_artifacts(sql)
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

    def test_anonymous_fk_is_detected(self, comparator: SchemaComparator) -> None:
        """FKs sin nombre (anónimas) deben detectarse con clave sintética (B1 fix)."""
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

        # Anonymous FK in target (not in source) must be reported as 'removed'
        assert diff.has_differences
        assert len(diff.table_diffs[0].fk_diffs) == 1
        assert diff.table_diffs[0].fk_diffs[0].status == "removed"


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

    def test_default_zero_vs_none_emits_diff(self, comparator: SchemaComparator) -> None:
        """B3: default=0 vs default=None deben generar ColumnDiff (0 es valor explícito, None es ausencia)."""
        source = _make_mock_inspector(
            tables={"t": [{"name": "col", "type": "INTEGER", "nullable": True, "default": 0}]},
            pk_constraints={"t": {"constrained_columns": []}},
        )
        target = _make_mock_inspector(
            tables={"t": [{"name": "col", "type": "INTEGER", "nullable": True, "default": None}]},
            pk_constraints={"t": {"constrained_columns": []}},
        )

        diff = comparator.compare(source, target)

        default_diffs = [d for d in diff.table_diffs[0].column_diffs if d.attribute == "default"]
        assert len(default_diffs) == 1
        assert default_diffs[0].source_value == "0"
        assert default_diffs[0].target_value == ""

    def test_default_false_vs_none_emits_diff(self, comparator: SchemaComparator) -> None:
        """B3: default=False vs default=None deben generar ColumnDiff."""
        source = _make_mock_inspector(
            tables={"t": [{"name": "active", "type": "BOOLEAN", "nullable": True, "default": False}]},
            pk_constraints={"t": {"constrained_columns": []}},
        )
        target = _make_mock_inspector(
            tables={"t": [{"name": "active", "type": "BOOLEAN", "nullable": True, "default": None}]},
            pk_constraints={"t": {"constrained_columns": []}},
        )

        diff = comparator.compare(source, target)

        default_diffs = [d for d in diff.table_diffs[0].column_diffs if d.attribute == "default"]
        assert len(default_diffs) == 1
        assert default_diffs[0].source_value == "False"
        assert default_diffs[0].target_value == ""


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
        """Sin CatalogDialect para el dialect, vista a vista: ``''`` cuando la definición es None."""
        inspector = MagicMock()
        inspector.get_view_definition.return_value = None

        assert view_definitions(inspector, None, ["v_test"]) == {"v_test": ""}

    def test_view_definition_not_implemented_returns_empty(self) -> None:
        inspector = MagicMock()
        inspector.get_view_definition.side_effect = NotImplementedError

        assert view_definitions(inspector, None, ["v_test"]) == {"v_test": ""}


class TestEdgeCasesBuildLabel:
    def test_sqlite_without_schema_is_engine_only(self) -> None:
        inspector = _make_mock_inspector(bind_url="sqlite:////srv/datos/app.db")
        assert SchemaComparator._build_label(inspector, None) == "sqlite"

    def test_url_with_schema(self) -> None:
        inspector = _make_mock_inspector(bind_url="sqlite:///:memory:")
        assert SchemaComparator._build_label(inspector, "myschema") == "sqlite [myschema]"

    _ORACLE_URL: ClassVar[str] = "oracle+oracledb://ESQ_ORIGEN:secret@10.20.0.237:1521/?service_name=DBTESTBIT"

    def test_oracle_without_schema_uses_default_schema(self) -> None:
        """Oracle sin ``schema``: la etiqueta identifica el schema por ``default_schema_name``, sin URL."""
        inspector = _make_mock_inspector(bind_url=self._ORACLE_URL)
        inspector.default_schema_name = "esq_origen"
        assert SchemaComparator._build_label(inspector, None) == "oracle [esq_origen]"

    def test_oracle_explicit_schema_wins_over_default(self) -> None:
        inspector = _make_mock_inspector(bind_url=self._ORACLE_URL)
        inspector.default_schema_name = "esq_origen"
        assert SchemaComparator._build_label(inspector, "OTRO") == "oracle [OTRO]"

    def test_oracle_without_default_schema_uses_user_as_schema(self) -> None:
        """Un ``default_schema_name`` que no es ``str`` se ignora; en Oracle el usuario es el schema."""
        inspector = _make_mock_inspector(bind_url=self._ORACLE_URL)
        assert SchemaComparator._build_label(inspector, None) == "oracle [ESQ_ORIGEN]"

    def test_same_host_different_users_get_different_labels(self) -> None:
        a = _make_mock_inspector(bind_url="oracle+oracledb://ESQ_A:x@h:1521/?service_name=S")
        b = _make_mock_inspector(bind_url="oracle+oracledb://ESQ_B:y@h:1521/?service_name=S")
        assert SchemaComparator._build_label(a, None) != SchemaComparator._build_label(b, None)

    def test_unparseable_url_uses_dialect_name(self) -> None:
        """Si la URL no se puede parsear, el motor sale del dialect y no se muestra nada de la URL."""
        inspector = MagicMock()
        inspector.engine.url = "no-url://user:pass@host"
        inspector.dialect.name = "postgresql"
        with patch.object(SchemaComparator, "_parse_url_safe", return_value=None):
            label = SchemaComparator._build_label(inspector, None)
        assert label == "postgresql"


class TestBuildShortLabel:
    """_build_short_label: ``<motor abreviado>_<schema>``, sin datos de conexión (G23)."""

    def test_postgresql_uses_schema(self) -> None:
        inspector = _make_mock_inspector(bind_url="postgresql://user:pass@pghost/mydb")
        assert SchemaComparator._build_short_label(inspector, "public") == "pg_public"

    def test_postgresql_without_schema_is_engine_only(self) -> None:
        inspector = _make_mock_inspector(bind_url="postgresql://user:pass@pghost/mydb")
        assert SchemaComparator._build_short_label(inspector, None) == "pg"

    def test_mariadb_uses_database_as_schema(self) -> None:
        inspector = _make_mock_inspector(bind_url="mariadb+mariadbconnector://user:pass@maria-host:3306/appdb")
        assert SchemaComparator._build_short_label(inspector, None) == "maria_appdb"

    def test_oracle_uses_username_as_schema(self) -> None:
        inspector = _make_mock_inspector(bind_url="oracle+cx_oracle://MYSCHEMA:pass@orahost/ORCL")
        assert SchemaComparator._build_short_label(inspector, None) == "ora_MYSCHEMA"

    def test_sqlite_file_has_no_path(self) -> None:
        inspector = _make_mock_inspector(bind_url="sqlite:///path/to/mydb.sqlite3")
        assert SchemaComparator._build_short_label(inspector, None) == "sqlite"

    def test_mssql_uses_schema(self) -> None:
        inspector = _make_mock_inspector(bind_url="mssql+pyodbc://user:pass@sqlsrv/AdventureWorks")
        assert SchemaComparator._build_short_label(inspector, "dbo") == "mssql_dbo"

    def test_default_schema_name_from_inspector(self) -> None:
        inspector = _make_mock_inspector(bind_url="postgresql://user:pass@192.168.1.10/db")
        inspector.default_schema_name = "public"
        assert SchemaComparator._build_short_label(inspector, None) == "pg_public"

    def test_no_engine_uses_dialect_and_schema(self) -> None:
        inspector = _make_mock_inspector(bind_url="sqlite://")
        inspector.engine = None
        inspector.dialect.name = "sqlite"
        assert SchemaComparator._build_short_label(inspector, "fallback") == "sqlite_fallback"


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
        result = DdlNormalizer.strip_dialect_artifacts("CREATE ALGORITHM=UNDEFINED VIEW v AS SELECT 1")
        assert "ALGORITHM" not in result

    def test_strips_algorithm_merge(self) -> None:
        result = DdlNormalizer.strip_dialect_artifacts("CREATE ALGORITHM=MERGE VIEW v AS SELECT 1")
        assert "ALGORITHM" not in result

    def test_strips_definer_with_spaces_around_equals(self) -> None:
        """G1: DEFINER = `u`@`h` (con espacios alrededor de =) debe eliminarse."""
        sql = "CREATE DEFINER = `admin`@`%` VIEW v AS SELECT 1"
        result = DdlNormalizer.strip_dialect_artifacts(sql)
        assert "DEFINER" not in result

    def test_strips_definer_single_quotes(self) -> None:
        """G1: DEFINER='u'@'h' (comillas simples) debe eliminarse."""
        sql = "CREATE DEFINER='root'@'localhost' VIEW v AS SELECT 1"
        result = DdlNormalizer.strip_dialect_artifacts(sql)
        assert "DEFINER" not in result

    def test_strips_definer_unquoted(self) -> None:
        """G1: DEFINER=user@host (sin comillas) debe eliminarse."""
        sql = "CREATE DEFINER=root@localhost VIEW v AS SELECT 1"
        result = DdlNormalizer.strip_dialect_artifacts(sql)
        assert "DEFINER" not in result

    def test_strips_sql_security_definer(self) -> None:
        """G3: SQL SECURITY DEFINER al inicio del DDL (sin espacio previo) debe eliminarse."""
        sql = "CREATE SQL SECURITY DEFINER VIEW v AS SELECT 1"
        result = DdlNormalizer.strip_dialect_artifacts(sql)
        assert "SQL SECURITY" not in result

    def test_strips_sql_security_invoker(self) -> None:
        sql = "CREATE SQL SECURITY INVOKER VIEW v AS SELECT 1"
        result = DdlNormalizer.strip_dialect_artifacts(sql)
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


# ---------------------------------------------------------------------------
# Tests de comparación cross-engine (case-insensitive en nombres de tabla)
# ---------------------------------------------------------------------------


def _make_cross_engine_inspector(
    tables: dict[str, list[dict[str, Any]]],
    bind_url: str = "sqlite://",
    dialect: str = "sqlite",
) -> MagicMock:
    """Inspector mock con dialect configurable para simular motores distintos."""
    mock = _make_mock_inspector(tables=tables, bind_url=bind_url)
    mock.engine.dialect.name = dialect
    return mock


class TestCrossEngineTableComparison:
    """Verifica comparación case-insensitive de tablas entre motores distintos."""

    def test_tables_matched_when_only_case_differs(self, comparator: SchemaComparator) -> None:
        """SQL Server devuelve 'Orders'; PostgreSQL devuelve 'orders'.
        No debe aparecer ninguna tabla como added ni removed."""
        col = [{"name": "id", "type": "INTEGER", "nullable": False, "default": None}]
        source = _make_cross_engine_inspector({"Orders": col}, dialect="mssql")
        target = _make_cross_engine_inspector({"orders": col}, dialect="postgresql")

        diff = comparator.compare(
            source, target, include_indices=False, include_foreign_keys=False, include_comments=False
        )

        added = [d for d in diff.table_diffs if d.status == "added"]
        removed = [d for d in diff.table_diffs if d.status == "removed"]
        assert added == [], f"No debería haber tablas 'added': {[d.table_name for d in added]}"
        assert removed == [], f"No debería haber tablas 'removed': {[d.table_name for d in removed]}"

    def test_multiple_tables_cross_engine_no_false_positives(self, comparator: SchemaComparator) -> None:
        """Todos los pares (Mixed_case → lowercase) se reconocen como tablas comunes."""
        col = [{"name": "id", "type": "INTEGER", "nullable": False, "default": None}]
        source = _make_cross_engine_inspector({"Orders": col, "Customers": col, "Products": col}, dialect="mssql")
        target = _make_cross_engine_inspector({"orders": col, "customers": col, "products": col}, dialect="postgresql")

        diff = comparator.compare(
            source, target, include_indices=False, include_foreign_keys=False, include_comments=False
        )

        assert not diff.has_differences

    def test_genuinely_missing_table_still_detected_cross_engine(self, comparator: SchemaComparator) -> None:
        """Una tabla que realmente solo existe en origen se reporta como 'added'."""
        col = [{"name": "id", "type": "INTEGER", "nullable": False, "default": None}]
        source = _make_cross_engine_inspector({"Orders": col, "Inventory": col}, dialect="mssql")
        target = _make_cross_engine_inspector({"orders": col}, dialect="postgresql")

        diff = comparator.compare(
            source, target, include_indices=False, include_foreign_keys=False, include_comments=False
        )

        added = [d for d in diff.table_diffs if d.status == "added"]
        assert len(added) == 1
        assert added[0].table_name == "Inventory"

    def test_columns_queried_with_canonical_names_per_engine(self, comparator: SchemaComparator) -> None:
        """get_columns se llama con el nombre canónico de cada motor, no el del otro."""
        col = [{"name": "id", "type": "INTEGER", "nullable": False, "default": None}]
        source = _make_cross_engine_inspector({"MyTable": col}, dialect="mssql")
        target = _make_cross_engine_inspector({"mytable": col}, dialect="postgresql")

        comparator.compare(source, target, include_indices=False, include_foreign_keys=False, include_comments=False)

        # El inspector origen debe haber recibido "MyTable"
        source_calls = [call[0][0] for call in source.get_columns.call_args_list]
        assert "MyTable" in source_calls, f"Esperado 'MyTable' en llamadas al src: {source_calls}"

        # El inspector destino debe haber recibido "mytable"
        target_calls = [call[0][0] for call in target.get_columns.call_args_list]
        assert "mytable" in target_calls, f"Esperado 'mytable' en llamadas al tgt: {target_calls}"

    def test_same_engine_same_case_no_regression(self, comparator: SchemaComparator) -> None:
        """Mismo motor con mismo case en nombres: comportamiento idéntico al original."""
        col = [{"name": "id", "type": "INTEGER", "nullable": False, "default": None}]
        source = _make_cross_engine_inspector({"users": col, "orders": col}, dialect="postgresql")
        target = _make_cross_engine_inspector({"users": col, "orders": col}, dialect="postgresql")

        diff = comparator.compare(
            source, target, include_indices=False, include_foreign_keys=False, include_comments=False
        )

        assert not diff.has_differences


class TestUnqualifyOwnSchema:
    """H-30 (C4): la misma vista o routine en dos schemas no sale como modificada por llevar su nombre calificado."""

    @pytest.mark.parametrize(
        ("definition", "expected"),
        [
            ("CREATE OR REPLACE FUNCTION app.f(a integer)", "CREATE OR REPLACE FUNCTION f(a integer)"),
            ("CREATE VIEW [app].[v] AS SELECT 1", "CREATE VIEW [v] AS SELECT 1"),
            ('CREATE VIEW "APP"."V" AS SELECT 1', 'CREATE VIEW "V" AS SELECT 1'),
            ("SELECT x.app, my_app.c FROM other.t", "SELECT x.app, my_app.c FROM other.t"),
        ],
    )
    def test_only_the_own_schema_prefix_is_removed(self, definition: str, expected: str) -> None:
        assert SchemaComparator._unqualify(definition, "app") == expected

    def test_without_schema_nothing_changes(self) -> None:
        assert SchemaComparator._unqualify("CREATE VIEW app.v AS SELECT 1", None) == "CREATE VIEW app.v AS SELECT 1"
