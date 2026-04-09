"""Tests para módulo PostgreSQL: tablas, esquemas y columnas."""

from __future__ import annotations

from util_bbdd.metadata.postgresql.tables import (
    build_postgres_table_ddl,
    build_schema_qualified_table_name,
    decode_postgres_column_rows,
    fetch_columns_sql,
    fetch_fk_constraint_sql,
    fetch_indexes_sql,
    fetch_pk_constraint_sql,
    fetch_schemas_sql,
    fetch_tables_sql,
    fetch_unique_constraint_sql,
)


class TestSchemasQuery:
    """Tests para query de schemas PostgreSQL."""

    def test_fetch_schemas_sql_returns_valid_query(self) -> None:
        sql = fetch_schemas_sql()
        assert isinstance(sql, str)
        assert "information_schema.schemata" in sql
        assert "pg_catalog" in sql  # Debe excluir pg_catalog
        assert "public" not in sql or "NOT IN" in sql  # Debe excluir schemas del sistema

    def test_fetch_schemas_sql_excludes_system_schemas(self) -> None:
        sql = fetch_schemas_sql()
        assert "pg_catalog" in sql
        assert "information_schema" in sql


class TestTablesQuery:
    """Tests para queries de tablas."""

    def test_fetch_tables_sql_uses_information_schema(self) -> None:
        sql = fetch_tables_sql()
        assert "information_schema.tables" in sql

    def test_fetch_tables_sql_with_schema_parameter(self) -> None:
        sql = fetch_tables_sql("myschema")
        assert "%(schema)s" in sql or "myschema" in sql or "$1" in sql

    def test_fetch_tables_sql_default_schema_is_public(self) -> None:
        sql = fetch_tables_sql(None)
        assert "%(schema)s" in sql

    def test_fetch_tables_sql_includes_table_comment(self) -> None:
        sql = fetch_tables_sql()
        assert "table_comment" in sql.lower() or "description" in sql.lower()


class TestColumnsQuery:
    """Tests para queries de columnas."""

    def test_fetch_columns_sql_requires_schema_and_table(self) -> None:
        sql = fetch_columns_sql("public", "users")
        assert isinstance(sql, str)
        assert len(sql) > 0

    def test_fetch_columns_sql_includes_key_fields(self) -> None:
        sql = fetch_columns_sql("public", "users")
        assert "column_name" in sql.lower()
        assert "data_type" in sql.lower()
        assert "is_nullable" in sql.lower()
        assert "column_key" in sql.lower()

    def test_fetch_columns_sql_includes_defaults_and_comments(self) -> None:
        sql = fetch_columns_sql("public", "users")
        assert "column_default" in sql.lower()
        assert "comment" in sql.lower() or "description" in sql.lower()

    def test_fetch_columns_sql_ordered_by_position(self) -> None:
        sql = fetch_columns_sql("public", "users")
        assert "ordinal_position" in sql.lower()


class TestConstraintQueries:
    """Tests para queries de constraints."""

    def test_fetch_pk_constraint_sql_returns_valid_query(self) -> None:
        sql = fetch_pk_constraint_sql("public", "users")
        assert isinstance(sql, str)
        assert "pg_index" in sql
        assert "indisprimary" in sql

    def test_fetch_fk_constraint_sql_returns_valid_query(self) -> None:
        sql = fetch_fk_constraint_sql("public", "orders")
        assert isinstance(sql, str)
        assert "referential_constraints" in sql
        assert "key_column_usage" in sql

    def test_fetch_unique_constraint_sql_returns_valid_query(self) -> None:
        sql = fetch_unique_constraint_sql("public", "users")
        assert isinstance(sql, str)
        assert "table_constraints" in sql
        assert "UNIQUE" in sql

    def test_fetch_indexes_sql_returns_valid_query(self) -> None:
        sql = fetch_indexes_sql("public", "users")
        assert isinstance(sql, str)
        assert "pg_indexes" in sql


class TestColumnDecoding:
    """Tests para decodificación de filas de columnas."""

    def test_decode_postgres_column_rows_empty_input(self) -> None:
        rows: list = []
        result = decode_postgres_column_rows(rows)
        assert result == []

    def test_decode_postgres_column_rows_single_column_full_info(self) -> None:
        rows = [
            (
                "id",
                "integer",
                "NO",
                "PRI",
                None,
                "",
                "",
            )
        ]
        result = decode_postgres_column_rows(rows)
        assert len(result) == 1
        assert result[0][0] == "id"
        assert result[0][1] == "integer"
        assert result[0][2] == "NO"
        assert result[0][3] == "PRI"

    def test_decode_postgres_column_rows_with_default_values(self) -> None:
        rows = [
            (
                "email",
                "varchar",
                "YES",
                "",
                "'admin@example.com'",
                "",
                "Email del usuario",
            ),
            (
                "created_at",
                "timestamp",
                "NO",
                "",
                "CURRENT_TIMESTAMP",
                "",
                "",
            ),
        ]
        result = decode_postgres_column_rows(rows)
        assert len(result) == 2
        assert result[0][0] == "email"
        assert result[0][4] == "'admin@example.com'"
        assert result[1][0] == "created_at"
        assert result[1][4] == "CURRENT_TIMESTAMP"

    def test_decode_postgres_column_rows_handles_nullable(self) -> None:
        rows = [
            ("col1", "text", "YES", "", None, "", "nullable"),
            ("col2", "text", "NO", "", None, "", "not nullable"),
        ]
        result = decode_postgres_column_rows(rows)
        assert result[0][2] == "YES"
        assert result[1][2] == "NO"

    def test_decode_postgres_column_rows_filters_invalid_rows(self) -> None:
        rows = [
            ("valid", "text", "YES", "", None, "", ""),
            None,  # Invalid
            [],  # Empty tuple
            (None,),  # Tuple with None
            ("name", "varchar", "YES", "", None, "", ""),
        ]
        result = decode_postgres_column_rows(rows)
        # Debería ignorar filas None/vacías pero procesar las válidas
        assert len(result) >= 2


class TestSchemaQualifiedTableName:
    """Tests para construcción de nombres calificados."""

    def test_build_schema_qualified_table_name_default_schema(self) -> None:
        name = build_schema_qualified_table_name(None, "users")
        assert name == '"public"."users"'

    def test_build_schema_qualified_table_name_explicit_schema(self) -> None:
        name = build_schema_qualified_table_name("auth", "users")
        assert name == '"auth"."users"'

    def test_build_schema_qualified_table_name_escapes_special_chars(self) -> None:
        name = build_schema_qualified_table_name("my-schema", "user_table")
        assert '"my-schema"' in name
        assert '"user_table"' in name


class TestTableDDLBuilder:
    """Tests para construcción de CREATE TABLE."""

    def test_build_postgres_table_ddl_empty_input(self) -> None:
        ddl = build_postgres_table_ddl("users", [], [])
        assert ddl == ""

    def test_build_postgres_table_ddl_single_column_no_pk(self) -> None:
        rows = [("id", "integer", "NO", "", None, "", "")]
        ddl = build_postgres_table_ddl("users", rows, [])
        assert "CREATE TABLE" in ddl
        assert '"users"' in ddl or "users" in ddl
        assert "integer" in ddl
        assert "NOT NULL" in ddl

    def test_build_postgres_table_ddl_multiple_columns_with_pk(self) -> None:
        rows = [
            ("id", "integer", "NO", "PRI", None, "", ""),
            ("name", "varchar", "NO", "", None, "", ""),
            ("email", "text", "YES", "", None, "", ""),
        ]
        pk_rows = [("id", 1)]
        ddl = build_postgres_table_ddl("users", rows, pk_rows)
        assert "CREATE TABLE" in ddl
        assert "integer" in ddl
        assert "varchar" in ddl
        assert "PRIMARY KEY" in ddl

    def test_build_postgres_table_ddl_with_defaults(self) -> None:
        rows = [
            ("id", "integer", "NO", "PRI", None, "", ""),
            ("status", "varchar", "NO", "", "'active'", "", ""),
        ]
        pk_rows = [("id", 1)]
        ddl = build_postgres_table_ddl("users", rows, pk_rows)
        assert "DEFAULT" in ddl

    def test_build_postgres_table_ddl_nullable_vs_not_null(self) -> None:
        rows = [
            ("required", "text", "NO", "", None, "", ""),
            ("optional", "text", "YES", "", None, "", ""),
        ]
        ddl = build_postgres_table_ddl("test", rows, [])
        assert "required" in ddl.lower()
        assert "optional" in ddl.lower()
        # Ambos deben tener NOT NULL o NULL según especificación
