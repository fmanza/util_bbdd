"""Tests para PostgreSQLSchemaExtractor (sin BD externa — manager mock)."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.migrate.extractors.postgresql import PostgreSQLSchemaExtractor, _parse_raw_column

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_manager(
    tables: list[tuple] | None = None,
    columns: list[tuple] | None = None,
    pks: list[tuple] | None = None,
    fks: list[tuple] | None = None,
    indexes: list[tuple] | None = None,
    views: list[tuple] | None = None,
    view_columns: list[tuple] | None = None,
) -> MagicMock:
    """Construye un manager mock que devuelve filas predefinidas por consulta."""
    manager = MagicMock()

    def side_effect(sql: str, params: dict) -> list:
        sql_upper = sql.upper()
        if "INFORMATION_SCHEMA.VIEWS" in sql_upper and "VIEW_DEFINITION" in sql_upper:
            return views or []
        if "INFORMATION_SCHEMA.VIEWS" in sql_upper:
            return view_columns or []
        if "INFORMATION_SCHEMA.TABLES" in sql_upper:
            return tables or []
        if "PG_CATALOG.PG_INDEX" in sql_upper or "PG_CATALOG" in sql_upper:
            return indexes or []
        if "CONSTRAINT_TYPE = 'PRIMARY KEY'" in sql_upper:
            return pks or []
        if "REFERENTIAL_CONSTRAINTS" in sql_upper:
            return fks or []
        if "INFORMATION_SCHEMA.COLUMNS" in sql_upper:
            return columns or []
        return []

    manager.execute_custom_many.side_effect = side_effect
    return manager


def _col_row(
    name: str = "col1",
    data_type: str = "integer",
    char_length: int | None = None,
    numeric_precision: int | None = None,
    numeric_scale: int | None = None,
    is_nullable: str = "YES",
    default: str | None = None,
    ordinal: int = 1,
) -> tuple:
    return (name, data_type, char_length, numeric_precision, numeric_scale, is_nullable, default, ordinal)


# ── Tests _parse_raw_column ───────────────────────────────────────────────────


class TestParseRawColumn:
    def test_basic_integer_column(self) -> None:
        row = _col_row("ID", "integer", None, 32, 0, "NO", None, 1)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["name"] == "ID"
        assert parsed["data_type"] == "INTEGER"
        assert parsed["auto_increment"] is False
        assert parsed["nullable"] is False

    def test_serial_auto_increment(self) -> None:
        row = _col_row("ID", "integer", None, 32, 0, "NO", "nextval('orders_id_seq'::regclass)", 1)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["auto_increment"] is True

    def test_serial_nextval_case_insensitive(self) -> None:
        row = _col_row("ID", "integer", None, 32, 0, "NO", "NEXTVAL('seq'::regclass)", 1)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["auto_increment"] is True

    def test_character_varying_with_length(self) -> None:
        row = _col_row("NAME", "character varying", 200, None, None, "YES", None, 2)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["data_type"] == "CHARACTER VARYING"
        assert parsed["char_length"] == 200
        assert parsed["nullable"] is True

    def test_character_varying_no_limit(self) -> None:
        row = _col_row("NOTES", "character varying", None, None, None, "YES", None, 3)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["char_length"] is None

    def test_text_no_length(self) -> None:
        row = _col_row("BODY", "text", None, None, None, "YES", None, 2)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["data_type"] == "TEXT"
        assert parsed["char_length"] is None

    def test_timestamp_without_tz(self) -> None:
        row = _col_row("CREATED", "timestamp without time zone", None, None, None, "YES", None, 4)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["data_type"] == "TIMESTAMP WITHOUT TIME ZONE"

    def test_timestamp_with_tz(self) -> None:
        row = _col_row("UPDATED", "timestamp with time zone", None, None, None, "YES", None, 5)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["data_type"] == "TIMESTAMP WITH TIME ZONE"

    def test_numeric_precision_scale(self) -> None:
        row = _col_row("AMOUNT", "numeric", None, 18, 4, "NO", None, 1)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["precision"] == 18
        assert parsed["scale"] == 4

    def test_boolean_column(self) -> None:
        row = _col_row("ACTIVE", "boolean", None, None, None, "NO", "true", 2)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["data_type"] == "BOOLEAN"
        assert parsed["default"] == "true"

    def test_uuid_column(self) -> None:
        row = _col_row("TOKEN", "uuid", None, None, None, "YES", None, 3)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["data_type"] == "UUID"

    def test_jsonb_column(self) -> None:
        row = _col_row("PAYLOAD", "jsonb", None, None, None, "YES", None, 2)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["data_type"] == "JSONB"

    def test_too_short_row_returns_none(self) -> None:
        assert _parse_raw_column(("col", "integer")) is None

    def test_none_row_returns_none(self) -> None:
        assert _parse_raw_column(None) is None  # type: ignore[arg-type]

    def test_default_value_preserved(self) -> None:
        row = _col_row("STATUS", "integer", None, 32, 0, "NO", "0", 1)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["default"] == "0"

    def test_non_nextval_default_not_auto_increment(self) -> None:
        row = _col_row("STATUS", "integer", None, None, None, "NO", "1", 1)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["auto_increment"] is False


# ── Tests extract() ──────────────────────────────────────────────────────────


class TestExtract:
    def test_extract_empty_schema(self) -> None:
        manager = _make_manager(tables=[])
        ext = PostgreSQLSchemaExtractor(manager)
        result = ext.extract("public")
        assert result == []

    def test_extract_single_table(self) -> None:
        manager = _make_manager(
            tables=[("orders",)],
            columns=[_col_row("id", "integer", None, 32, 0, "NO", "nextval('orders_id_seq'::regclass)", 1)],
            pks=[("id",)],
        )
        ext = PostgreSQLSchemaExtractor(manager)
        result = ext.extract("public")
        assert len(result) == 1
        assert result[0].name == "orders"
        assert result[0].columns[0].name == "id"
        assert result[0].columns[0].auto_increment is True
        assert result[0].primary_key == ["id"]

    def test_pk_marks_column_is_primary_key(self) -> None:
        manager = _make_manager(
            tables=[("products",)],
            columns=[
                _col_row("product_id", "integer", None, 32, 0, "NO", "nextval('seq'::regclass)", 1),
                _col_row("name", "character varying", 200, None, None, "NO", None, 2),
            ],
            pks=[("product_id",)],
        )
        ext = PostgreSQLSchemaExtractor(manager)
        result = ext.extract("public")
        pk_col = next(c for c in result[0].columns if c.name == "product_id")
        other_col = next(c for c in result[0].columns if c.name == "name")
        assert pk_col.is_primary_key is True
        assert other_col.is_primary_key is False

    def test_schema_stored_in_table(self) -> None:
        manager = _make_manager(
            tables=[("t1",)],
            columns=[_col_row("c1", "integer")],
        )
        ext = PostgreSQLSchemaExtractor(manager)
        result = ext.extract("myschema")
        assert result[0].schema == "myschema"

    def test_char_varying_no_limit_preserved(self) -> None:
        manager = _make_manager(
            tables=[("docs",)],
            columns=[_col_row("body", "character varying", None, None, None, "YES", None, 1)],
        )
        ext = PostgreSQLSchemaExtractor(manager)
        result = ext.extract("public")
        assert result[0].columns[0].char_length is None


# ── Tests extract_views() ────────────────────────────────────────────────────


class TestExtractViews:
    def test_extract_empty_views(self) -> None:
        manager = _make_manager(views=[])
        ext = PostgreSQLSchemaExtractor(manager)
        result = ext.extract_views("public")
        assert result == []

    def test_extract_single_view(self) -> None:
        manager = _make_manager(
            views=[("v_orders", "SELECT id, name FROM orders")],
            view_columns=[("id",), ("name",)],
        )
        ext = PostgreSQLSchemaExtractor(manager)
        result = ext.extract_views("public")
        assert len(result) == 1
        assert result[0].name == "v_orders"
        assert result[0].query == "SELECT id, name FROM orders"

    def test_view_schema_stored(self) -> None:
        manager = _make_manager(
            views=[("v_test", "SELECT 1")],
            view_columns=[],
        )
        ext = PostgreSQLSchemaExtractor(manager)
        result = ext.extract_views("reporting")
        assert result[0].schema == "reporting"


# ── Tests FK extraction ───────────────────────────────────────────────────────


class TestExtractFKs:
    def test_internal_fk(self) -> None:
        fk_rows = [
            ("fk_order_customer", "customer_id", "public", "customers", "id", 1, "NO ACTION", "NO ACTION"),
        ]
        manager = _make_manager(
            tables=[("orders",)],
            columns=[
                _col_row("id", "integer", None, 32, 0, "NO", "nextval('seq'::regclass)", 1),
                _col_row("customer_id", "integer", None, 32, 0, "NO", None, 2),
            ],
            pks=[("id",)],
            fks=fk_rows,
        )
        ext = PostgreSQLSchemaExtractor(manager)
        result = ext.extract("public")
        fks = result[0].foreign_keys
        assert len(fks) == 1
        assert fks[0].name == "fk_order_customer"
        assert fks[0].columns == ["customer_id"]
        assert fks[0].ref_table == "customers"
        assert fks[0].is_external is False

    def test_external_fk(self) -> None:
        fk_rows = [
            ("fk_ext", "col_a", "other_schema", "ext_table", "id", 1, "CASCADE", "NO ACTION"),
        ]
        manager = _make_manager(
            tables=[("my_table",)],
            columns=[_col_row("col_a", "integer")],
            fks=fk_rows,
        )
        ext = PostgreSQLSchemaExtractor(manager)
        result = ext.extract("public")
        assert result[0].foreign_keys[0].is_external is True


# ── Tests index extraction ────────────────────────────────────────────────────


class TestExtractIndexes:
    def test_unique_index(self) -> None:
        idx_rows = [
            ("uq_email", "email", True, 1),
        ]
        manager = _make_manager(
            tables=[("users",)],
            columns=[
                _col_row("id", "integer", None, 32, 0, "NO", "nextval('seq'::regclass)", 1),
                _col_row("email", "character varying", 255, None, None, "NO", None, 2),
            ],
            pks=[("id",)],
            indexes=idx_rows,
        )
        ext = PostgreSQLSchemaExtractor(manager)
        result = ext.extract("public")
        assert len(result[0].indexes) == 1
        assert result[0].indexes[0].name == "uq_email"
        assert result[0].indexes[0].unique is True

    def test_non_unique_index(self) -> None:
        idx_rows = [("ix_status", "status", False, 1)]
        manager = _make_manager(
            tables=[("orders",)],
            columns=[_col_row("status", "integer")],
            indexes=idx_rows,
        )
        ext = PostgreSQLSchemaExtractor(manager)
        result = ext.extract("public")
        assert result[0].indexes[0].unique is False

    def test_composite_index_column_order(self) -> None:
        idx_rows = [
            ("ix_composite", "col_a", False, 1),
            ("ix_composite", "col_b", False, 2),
        ]
        manager = _make_manager(
            tables=[("t",)],
            columns=[
                _col_row("col_a", "integer", ordinal=1),
                _col_row("col_b", "integer", ordinal=2),
            ],
            indexes=idx_rows,
        )
        ext = PostgreSQLSchemaExtractor(manager)
        result = ext.extract("public")
        idx = result[0].indexes[0]
        assert idx.columns == ["col_a", "col_b"]
