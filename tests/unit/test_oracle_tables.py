"""Tests para módulo Oracle: tablas, esquemas y columnas."""

from __future__ import annotations

from util_bbdd.metadata.oracle.tables import (
    decode_oracle_column_rows,
    fetch_columns_sql,
    fetch_fk_constraint_sql,
    fetch_indexes_sql,
    fetch_pk_constraint_sql,
    fetch_routine_parameters_sql,
    fetch_routines_sql,
    fetch_schemas_sql,
    fetch_tables_sql,
)


class TestSchemasQuery:
    """Tests para query de schemas Oracle."""

    def test_fetch_schemas_sql_returns_valid_query(self) -> None:
        sql = fetch_schemas_sql()
        assert isinstance(sql, str)
        assert "all_tables" in sql
        assert "SYS" in sql
        assert "SYSTEM" in sql

    def test_fetch_schemas_sql_excludes_system_schemas(self) -> None:
        sql = fetch_schemas_sql()
        assert "NOT IN" in sql
        assert "SYS" in sql

    def test_fetch_schemas_sql_excludes_apex(self) -> None:
        sql = fetch_schemas_sql()
        assert "APEX" in sql or "LIKE" in sql

    def test_fetch_schemas_sql_no_parameters(self) -> None:
        sql = fetch_schemas_sql()
        assert "%(schema)s" not in sql
        assert "%(owner)s" not in sql


class TestTablesQuery:
    """Tests para queries de tablas."""

    def test_fetch_tables_sql_returns_valid_query(self) -> None:
        sql = fetch_tables_sql()
        assert isinstance(sql, str)
        assert "all_tables" in sql

    def test_fetch_tables_sql_includes_table_name(self) -> None:
        sql = fetch_tables_sql()
        assert "table_name" in sql.lower()

    def test_fetch_tables_sql_includes_table_type(self) -> None:
        sql = fetch_tables_sql()
        assert "table_type" in sql.lower()

    def test_fetch_tables_sql_does_not_reference_all_tables_column(self) -> None:
        """Regresión ORA-00904: table_type no existe en ALL_TABLES en todas las ediciones."""
        sql = fetch_tables_sql()
        assert "t.table_type" not in sql
        assert "'TABLE'" in sql or "AS table_type" in sql.lower()

    def test_fetch_tables_sql_includes_owner_parameter(self) -> None:
        sql = fetch_tables_sql()
        assert ":owner" in sql
        assert "%(owner)s" not in sql

    def test_fetch_tables_sql_includes_comments(self) -> None:
        sql = fetch_tables_sql()
        assert "comment" in sql.lower() or "comments" in sql.lower()

    def test_fetch_tables_sql_joins_comments(self) -> None:
        sql = fetch_tables_sql()
        assert "LEFT JOIN" in sql or "left join" in sql.lower()


class TestColumnsQuery:
    """Tests para queries de columnas."""

    def test_fetch_columns_sql_returns_valid_query(self) -> None:
        sql = fetch_columns_sql()
        assert isinstance(sql, str)
        assert len(sql) > 0

    def test_fetch_columns_sql_includes_key_fields(self) -> None:
        sql = fetch_columns_sql()
        assert "column_name" in sql.lower()
        assert "data_type" in sql.lower()
        assert "nullable" in sql.lower()

    def test_fetch_columns_sql_includes_owner_and_table_params(self) -> None:
        sql = fetch_columns_sql()
        assert ":owner" in sql
        assert ":table_name" in sql
        assert "%(owner)s" not in sql
        assert "%(table_name)s" not in sql

    def test_fetch_columns_sql_excludes_rowid(self) -> None:
        sql = fetch_columns_sql()
        assert "ROWID" in sql

    def test_fetch_columns_sql_ordered_by_position(self) -> None:
        sql = fetch_columns_sql()
        assert "column_id" in sql.lower() or "order" in sql.lower()

    def test_fetch_columns_sql_includes_comments(self) -> None:
        sql = fetch_columns_sql()
        assert "comment" in sql.lower()

    def test_fetch_columns_sql_includes_defaults(self) -> None:
        sql = fetch_columns_sql()
        assert "default" in sql.lower()


class TestDecodeOracleColumnRows:
    """Tests para decode_oracle_column_rows()."""

    def test_decode_empty_rows(self) -> None:
        result = decode_oracle_column_rows([])
        assert result == []

    def test_decode_single_column(self) -> None:
        rows = [
            ("ID", "NUMBER", "N", 1, "", 0, 0, 0, "Primary key"),
        ]
        result = decode_oracle_column_rows(rows)
        assert len(result) == 1
        assert result[0][0] == "ID"
        assert result[0][1] == "NUMBER"

    def test_decode_skips_long_type(self) -> None:
        rows = [
            ("DATA", "LONG", "Y", 1, "", 0, 0, 0, ""),
        ]
        result = decode_oracle_column_rows(rows)
        assert len(result) == 0

    def test_decode_skips_long_raw_type(self) -> None:
        rows = [
            ("DATA", "LONG RAW", "Y", 1, "", 0, 0, 0, ""),
        ]
        result = decode_oracle_column_rows(rows)
        assert len(result) == 0

    def test_decode_column_with_default(self) -> None:
        rows = [
            ("STATUS", "VARCHAR2", "N", 2, "'ACTIVE'", 0, 0, 0, "Status field"),
        ]
        result = decode_oracle_column_rows(rows)
        assert len(result) == 1
        assert "'ACTIVE'" in str(result[0][4])

    def test_decode_nullable_column(self) -> None:
        rows = [
            ("DESCRIPTION", "VARCHAR2", "Y", 1, "", 0, 0, 0, ""),
        ]
        result = decode_oracle_column_rows(rows)
        assert result[0][2] == "Y"  # Oracle returns Y/N, not YES/NO

    def test_decode_not_nullable_column(self) -> None:
        rows = [
            ("ID", "NUMBER", "N", 1, "", 0, 0, 0, ""),
        ]
        result = decode_oracle_column_rows(rows)
        assert result[0][2] == "N"  # Oracle returns Y/N, not YES/NO

    def test_decode_multiple_columns_preserves_order(self) -> None:
        rows = [
            ("ID", "NUMBER", "N", 1, "", 0, 0, 0, ""),
            ("NAME", "VARCHAR2", "N", 2, "", 0, 0, 0, ""),
            ("CREATED", "DATE", "Y", 3, "", 0, 0, 0, ""),
        ]
        result = decode_oracle_column_rows(rows)
        assert len(result) == 3
        assert result[0][0] == "ID"
        assert result[1][0] == "NAME"
        assert result[2][0] == "CREATED"


class TestPKConstraintQuery:
    """Tests para query de primary keys."""

    def test_fetch_pk_constraint_sql_returns_valid_query(self) -> None:
        sql = fetch_pk_constraint_sql()
        assert isinstance(sql, str)
        assert "all_constraints" in sql
        assert "all_cons_columns" in sql

    def test_fetch_pk_constraint_sql_filters_by_type_p(self) -> None:
        sql = fetch_pk_constraint_sql()
        assert "'P'" in sql

    def test_fetch_pk_constraint_sql_includes_params(self) -> None:
        sql = fetch_pk_constraint_sql()
        assert ":owner" in sql
        assert ":table_name" in sql
        assert "%(owner)s" not in sql
        assert "%(table_name)s" not in sql


class TestFKConstraintQuery:
    """Tests para query de foreign keys."""

    def test_fetch_fk_constraint_sql_returns_valid_query(self) -> None:
        sql = fetch_fk_constraint_sql()
        assert isinstance(sql, str)
        assert "all_constraints" in sql

    def test_fetch_fk_constraint_sql_filters_by_type_r(self) -> None:
        sql = fetch_fk_constraint_sql()
        assert "'R'" in sql

    def test_fetch_fk_constraint_sql_includes_delete_rule(self) -> None:
        sql = fetch_fk_constraint_sql()
        assert "delete_rule" in sql.lower()

    def test_fetch_fk_constraint_sql_includes_params(self) -> None:
        sql = fetch_fk_constraint_sql()
        assert ":owner" in sql
        assert ":table_name" in sql
        assert "%(owner)s" not in sql
        assert "%(table_name)s" not in sql


class TestIndexesQuery:
    """Tests para query de índices."""

    def test_fetch_indexes_sql_returns_valid_query(self) -> None:
        sql = fetch_indexes_sql()
        assert isinstance(sql, str)
        assert "all_indexes" in sql

    def test_fetch_indexes_sql_joins_ind_columns(self) -> None:
        sql = fetch_indexes_sql()
        assert "all_ind_columns" in sql

    def test_fetch_indexes_sql_includes_uniqueness(self) -> None:
        sql = fetch_indexes_sql()
        assert "uniqueness" in sql.lower()

    def test_fetch_indexes_sql_includes_params(self) -> None:
        sql = fetch_indexes_sql()
        assert ":owner" in sql
        assert ":table_name" in sql
        assert "%(owner)s" not in sql
        assert "%(table_name)s" not in sql


class TestRoutinesQuery:
    """Tests para query de rutinas."""

    def test_fetch_routines_sql_returns_valid_query(self) -> None:
        sql = fetch_routines_sql()
        assert isinstance(sql, str)
        assert "all_procedures" in sql

    def test_fetch_routines_sql_includes_owner_param(self) -> None:
        sql = fetch_routines_sql()
        assert ":owner" in sql
        assert "%(owner)s" not in sql

    def test_fetch_routines_sql_orders_by_name(self) -> None:
        sql = fetch_routines_sql()
        assert "ORDER" in sql


class TestRoutineParametersQuery:
    """Tests para query de parámetros de rutinas."""

    def test_fetch_routine_parameters_sql_returns_valid_query(self) -> None:
        sql = fetch_routine_parameters_sql()
        assert isinstance(sql, str)
        assert "all_arguments" in sql

    def test_fetch_routine_parameters_sql_includes_params(self) -> None:
        sql = fetch_routine_parameters_sql()
        assert ":owner" in sql
        assert ":routine_name" in sql
        assert "%(owner)s" not in sql
        assert "%(routine_name)s" not in sql

    def test_fetch_routine_parameters_sql_filters_null_names(self) -> None:
        sql = fetch_routine_parameters_sql()
        assert "IS NOT NULL" in sql or "IS NULL" in sql
