"""Tests para PostgreSQLToOracleTransformer."""

from __future__ import annotations

from util_bbdd.migrate.ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalTable,
    CanonicalView,
)
from util_bbdd.migrate.transformers.postgresql_to_oracle import PostgreSQLToOracleTransformer

# ── Helpers ───────────────────────────────────────────────────────────────────


def _col(
    name: str,
    pg_type: str,
    char_length: int | None = None,
    precision: int | None = None,
    scale: int | None = None,
    nullable: bool = True,
    auto_increment: bool = False,
    is_pk: bool = False,
) -> CanonicalColumn:
    return CanonicalColumn(
        name=name,
        original_name=name,
        source_type=pg_type,  # campo histórico; almacena el tipo fuente PG
        target_type="",
        nullable=nullable,
        default=None,
        comment="",
        ordinal=1,
        char_length=char_length,
        precision=precision,
        scale=scale,
        auto_increment=auto_increment,
        is_primary_key=is_pk,
    )


def _table(name: str, cols: list[CanonicalColumn], pk: list[str] | None = None) -> CanonicalTable:
    return CanonicalTable(
        name=name,
        original_name=name,
        schema="public",
        columns=cols,
        primary_key=pk or [],
        indexes=[],
        foreign_keys=[],
        comment="",
        warnings=[],
    )


def _view(name: str, query: str = "SELECT 1") -> CanonicalView:
    return CanonicalView(
        name=name,
        original_name=name,
        schema="public",
        query=query,
        columns=[],
        comment="",
        warnings=[],
    )


# ── Tests de tipos básicos ────────────────────────────────────────────────────


class TestTypeMapping:
    def test_integer_to_number10(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col("c", "INTEGER")])])
        assert result[0].columns[0].target_type == "NUMBER(10,0)"

    def test_bigint_to_number19(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col("c", "BIGINT")])])
        assert result[0].columns[0].target_type == "NUMBER(19,0)"

    def test_smallint_to_number5(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col("c", "SMALLINT")])])
        assert result[0].columns[0].target_type == "NUMBER(5,0)"

    def test_text_to_clob(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col("c", "TEXT")])])
        assert result[0].columns[0].target_type == "CLOB"

    def test_boolean_to_number1(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col("c", "BOOLEAN")])])
        assert result[0].columns[0].target_type == "NUMBER(1,0)"
        assert len(result[0].columns[0].warnings) > 0

    def test_bytea_to_blob(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col("c", "BYTEA")])])
        assert result[0].columns[0].target_type == "BLOB"

    def test_uuid_to_char36(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col("c", "UUID")])])
        assert result[0].columns[0].target_type == "CHAR(36)"

    def test_timestamp_without_tz(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col("c", "TIMESTAMP WITHOUT TIME ZONE")])])
        assert result[0].columns[0].target_type == "TIMESTAMP"

    def test_timestamp_with_tz(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col("c", "TIMESTAMP WITH TIME ZONE")])])
        assert "TIME ZONE" in result[0].columns[0].target_type

    def test_date_to_date(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col("c", "DATE")])])
        assert result[0].columns[0].target_type == "DATE"

    def test_double_precision_to_binary_double(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col("c", "DOUBLE PRECISION")])])
        assert result[0].columns[0].target_type == "BINARY_DOUBLE"

    def test_real_to_binary_float(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col("c", "REAL")])])
        assert result[0].columns[0].target_type == "BINARY_FLOAT"


# ── CHARACTER VARYING resolution ─────────────────────────────────────────────


class TestCharacterVaryingResolution:
    def test_char_varying_with_length_to_varchar2(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col("c", "CHARACTER VARYING", char_length=200)])])
        assert result[0].columns[0].target_type == "VARCHAR2(200)"

    def test_char_varying_no_limit_to_clob(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col("c", "CHARACTER VARYING", char_length=None)])])
        assert result[0].columns[0].target_type == "CLOB"

    def test_char_varying_over_4000_to_clob(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col("c", "CHARACTER VARYING", char_length=5000)])])
        assert result[0].columns[0].target_type == "CLOB"
        assert len(result[0].columns[0].warnings) > 0

    def test_char_varying_exactly_4000(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col("c", "CHARACTER VARYING", char_length=4000)])])
        assert result[0].columns[0].target_type == "VARCHAR2(4000)"

    def test_character_to_char_n(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col("c", "CHARACTER", char_length=10)])])
        assert result[0].columns[0].target_type == "CHAR(10)"


# ── NUMERIC resolution ────────────────────────────────────────────────────────


class TestNumericResolution:
    def test_numeric_with_precision_scale(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col("c", "NUMERIC", precision=18, scale=4)])])
        assert result[0].columns[0].target_type == "NUMBER(18,4)"

    def test_numeric_fallback_precision(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col("c", "NUMERIC")])])
        assert result[0].columns[0].target_type == "NUMBER(38,10)"


# ── BIT resolution ────────────────────────────────────────────────────────────


class TestBitResolution:
    def test_bit_with_length_to_char_n(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col("c", "BIT", char_length=8)])])
        assert result[0].columns[0].target_type == "CHAR(8)"

    def test_bit_varying_to_varchar2(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col("c", "BIT VARYING", char_length=16)])])
        assert result[0].columns[0].target_type == "VARCHAR2(16)"


# ── Identifier truncation (Oracle limit 30) ───────────────────────────────────


class TestIdentifierTruncation:
    def test_table_name_over_30_truncated(self) -> None:
        long_name = "T" * 35
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table(long_name, [_col("c", "INTEGER")])])
        assert len(result[0].name) <= 30
        assert len(result[0].warnings) > 0

    def test_column_name_over_30_truncated(self) -> None:
        long_col = "C" * 35
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col(long_col, "INTEGER")])])
        col = result[0].columns[0]
        assert len(col.name) <= 30
        assert len(col.warnings) > 0

    def test_short_name_not_truncated(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("orders", [_col("id", "INTEGER")])])
        assert result[0].name == "orders"
        assert result[0].columns[0].name == "id"


# ── FK handling ───────────────────────────────────────────────────────────────


class TestFKHandling:
    def test_on_update_cascade_generates_warning(self) -> None:
        fk = CanonicalFK(
            name="fk1",
            original_name="fk1",
            columns=["col_a"],
            ref_table="other_table",
            ref_columns=["id"],
            on_delete="NO ACTION",
            on_update="CASCADE",
            is_external=False,
        )
        table = CanonicalTable(
            name="t",
            original_name="t",
            schema="public",
            columns=[_col("col_a", "INTEGER")],
            primary_key=[],
            indexes=[],
            foreign_keys=[fk],
            comment="",
            warnings=[],
        )
        t = PostgreSQLToOracleTransformer()
        result = t.transform([table])
        assert any("ON UPDATE" in w.message for w in result[0].warnings)

    def test_external_fk_generates_warning(self) -> None:
        fk = CanonicalFK(
            name="fk_ext",
            original_name="fk_ext",
            columns=["col_a"],
            ref_table="ext_table",
            ref_columns=["id"],
            on_delete="NO ACTION",
            on_update="NO ACTION",
            is_external=True,
        )
        table = CanonicalTable(
            name="t",
            original_name="t",
            schema="public",
            columns=[_col("col_a", "INTEGER")],
            primary_key=[],
            indexes=[],
            foreign_keys=[fk],
            comment="",
            warnings=[],
        )
        t = PostgreSQLToOracleTransformer()
        result = t.transform([table])
        assert result[0].foreign_keys[0].is_external is True
        assert any("fuera del schema" in w.message for w in result[0].warnings)


# ── Vistas pass-through ───────────────────────────────────────────────────────


class TestViewsPassThrough:
    def test_view_gets_warning(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform_views([_view("v_orders")])
        assert len(result) == 1
        assert any("pass-through" in w.message for w in result[0].warnings)

    def test_view_query_preserved(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform_views([_view("v_t", "SELECT id FROM orders WHERE NOW() > created_at")])
        assert result[0].query == "SELECT id FROM orders WHERE NOW() > created_at"

    def test_empty_views_list(self) -> None:
        t = PostgreSQLToOracleTransformer()
        assert t.transform_views([]) == []


# ── Unknown type fallback ─────────────────────────────────────────────────────


class TestUnknownType:
    def test_unknown_pg_type_maps_to_clob(self) -> None:
        t = PostgreSQLToOracleTransformer()
        result = t.transform([_table("t", [_col("c", "SOME_EXOTIC_TYPE")])])
        assert result[0].columns[0].target_type == "CLOB"
        assert len(result[0].columns[0].warnings) > 0


# ── auto_increment preservation ───────────────────────────────────────────────


class TestAutoIncrementPreservation:
    def test_serial_auto_increment_preserved(self) -> None:
        t = PostgreSQLToOracleTransformer()
        col = _col("id", "INTEGER", auto_increment=True)
        result = t.transform([_table("t", [col])])
        assert result[0].columns[0].auto_increment is True
