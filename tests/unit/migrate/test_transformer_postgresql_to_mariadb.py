"""Tests para PostgreSQLToMariaDBTransformer."""

from __future__ import annotations

from util_bbdd.migrate.ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalTable,
    CanonicalView,
)
from util_bbdd.migrate.transformers.postgresql_to_mariadb import PostgreSQLToMariaDBTransformer

# ── Helpers ───────────────────────────────────────────────────────────────────


def _col(
    name: str,
    pg_type: str,
    char_length: int | None = None,
    precision: int | None = None,
    scale: int | None = None,
    auto_increment: bool = False,
) -> CanonicalColumn:
    return CanonicalColumn(
        name=name,
        original_name=name,
        oracle_type=pg_type,
        target_type="",
        nullable=True,
        default=None,
        comment="",
        ordinal=1,
        char_length=char_length,
        precision=precision,
        scale=scale,
        auto_increment=auto_increment,
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


def _view(name: str) -> CanonicalView:
    return CanonicalView(
        name=name,
        original_name=name,
        schema="public",
        query="SELECT NOW()",
        columns=[],
        comment="",
        warnings=[],
    )


# ── Tests de tipos básicos ────────────────────────────────────────────────────


class TestTypeMapping:
    def test_integer_to_int(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table("t", [_col("c", "INTEGER")])])
        assert result[0].columns[0].target_type == "INT"

    def test_bigint_to_bigint(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table("t", [_col("c", "BIGINT")])])
        assert result[0].columns[0].target_type == "BIGINT"

    def test_smallint_to_smallint(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table("t", [_col("c", "SMALLINT")])])
        assert result[0].columns[0].target_type == "SMALLINT"

    def test_text_to_longtext(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table("t", [_col("c", "TEXT")])])
        assert result[0].columns[0].target_type == "LONGTEXT"

    def test_boolean_to_tinyint1(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table("t", [_col("c", "BOOLEAN")])])
        assert result[0].columns[0].target_type == "TINYINT(1)"

    def test_bytea_to_longblob(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table("t", [_col("c", "BYTEA")])])
        assert result[0].columns[0].target_type == "LONGBLOB"

    def test_uuid_to_char36(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table("t", [_col("c", "UUID")])])
        assert result[0].columns[0].target_type == "CHAR(36)"

    def test_timestamp_without_tz_to_datetime6(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table("t", [_col("c", "TIMESTAMP WITHOUT TIME ZONE")])])
        assert result[0].columns[0].target_type == "DATETIME(6)"

    def test_timestamp_with_tz_to_datetime6_with_warning(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table("t", [_col("c", "TIMESTAMP WITH TIME ZONE")])])
        assert result[0].columns[0].target_type == "DATETIME(6)"
        assert len(result[0].columns[0].warnings) > 0

    def test_date_to_date(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table("t", [_col("c", "DATE")])])
        assert result[0].columns[0].target_type == "DATE"

    def test_double_precision_to_double(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table("t", [_col("c", "DOUBLE PRECISION")])])
        assert result[0].columns[0].target_type == "DOUBLE"

    def test_real_to_float(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table("t", [_col("c", "REAL")])])
        assert result[0].columns[0].target_type == "FLOAT"

    def test_time_without_tz_to_time6(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table("t", [_col("c", "TIME WITHOUT TIME ZONE")])])
        assert result[0].columns[0].target_type == "TIME(6)"


# ── CHARACTER VARYING resolution ─────────────────────────────────────────────


class TestCharacterVaryingResolution:
    def test_char_varying_with_length(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table("t", [_col("c", "CHARACTER VARYING", char_length=255)])])
        assert result[0].columns[0].target_type == "VARCHAR(255)"

    def test_char_varying_no_limit_to_longtext(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table("t", [_col("c", "CHARACTER VARYING", char_length=None)])])
        assert result[0].columns[0].target_type == "LONGTEXT"

    def test_character_to_char_n(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table("t", [_col("c", "CHARACTER", char_length=5)])])
        assert result[0].columns[0].target_type == "CHAR(5)"


# ── NUMERIC resolution ────────────────────────────────────────────────────────


class TestNumericResolution:
    def test_numeric_with_precision_scale(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table("t", [_col("c", "NUMERIC", precision=10, scale=2)])])
        assert result[0].columns[0].target_type == "DECIMAL(10,2)"

    def test_numeric_fallback(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table("t", [_col("c", "NUMERIC")])])
        assert result[0].columns[0].target_type == "DECIMAL(38,10)"


# ── BIT resolution ────────────────────────────────────────────────────────────


class TestBitResolution:
    def test_bit_with_length(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table("t", [_col("c", "BIT", char_length=8)])])
        assert result[0].columns[0].target_type == "BIT(8)"

    def test_bit_varying_to_varbinary(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table("t", [_col("c", "BIT VARYING", char_length=16)])])
        # 16 bits = 2 bytes → VARBINARY(2)
        assert result[0].columns[0].target_type == "VARBINARY(2)"


# ── Identifier truncation (MariaDB limit 64) ──────────────────────────────────


class TestIdentifierTruncation:
    def test_table_name_over_64_truncated(self) -> None:
        long_name = "T" * 70
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table(long_name, [_col("c", "INTEGER")])])
        assert len(result[0].name) <= 64

    def test_short_name_not_truncated(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table("orders", [_col("id", "INTEGER")])])
        assert result[0].name == "orders"


# ── External FK warning ───────────────────────────────────────────────────────


class TestExternalFK:
    def test_external_fk_warning(self) -> None:
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
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([table])
        assert result[0].foreign_keys[0].is_external is True
        assert any("fuera del schema" in w.message for w in result[0].warnings)


# ── Vistas pass-through ───────────────────────────────────────────────────────


class TestViewsPassThrough:
    def test_view_gets_pg_warning(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform_views([_view("v_orders")])
        assert len(result[0].warnings) > 0
        assert any("PostgreSQL" in w.message for w in result[0].warnings)

    def test_empty_views_list(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        assert t.transform_views([]) == []


# ── auto_increment preservation ───────────────────────────────────────────────


class TestAutoIncrementPreservation:
    def test_serial_preserved(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        col = _col("id", "INTEGER", auto_increment=True)
        result = t.transform([_table("t", [col])])
        assert result[0].columns[0].auto_increment is True


# ── Unknown type fallback ─────────────────────────────────────────────────────


class TestUnknownType:
    def test_unknown_maps_to_longtext(self) -> None:
        t = PostgreSQLToMariaDBTransformer()
        result = t.transform([_table("t", [_col("c", "SOME_EXOTIC_TYPE")])])
        assert result[0].columns[0].target_type == "LONGTEXT"
