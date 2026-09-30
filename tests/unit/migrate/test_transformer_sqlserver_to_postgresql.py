"""Tests para SQLServerToPostgreSQLTransformer."""

from __future__ import annotations

from util_bbdd.migrate.ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalTable,
    CanonicalView,
)
from util_bbdd.migrate.transformers.sqlserver_to_postgresql import SQLServerToPostgreSQLTransformer


def _col(
    name: str = "COL",
    ss_type: str = "INT",
    nullable: bool = True,
    char_length: int | None = None,
    precision: int | None = None,
    scale: int | None = None,
    auto_increment: bool = False,
    is_primary_key: bool = False,
) -> CanonicalColumn:
    return CanonicalColumn(
        name=name,
        original_name=name,
        source_type=ss_type,
        target_type="",
        nullable=nullable,
        default=None,
        comment="",
        ordinal=1,
        char_length=char_length,
        precision=precision,
        scale=scale,
        auto_increment=auto_increment,
        is_primary_key=is_primary_key,
    )


def _table(
    name: str = "MY_TABLE",
    columns: list[CanonicalColumn] | None = None,
    pk: list[str] | None = None,
    fks: list[CanonicalFK] | None = None,
) -> CanonicalTable:
    return CanonicalTable(
        name=name,
        original_name=name,
        schema="dbo",
        columns=columns or [],
        primary_key=pk or [],
        indexes=[],
        foreign_keys=fks or [],
        comment="",
        warnings=[],
    )


class TestColumnTypeMappingPostgreSQL:
    def setup_method(self) -> None:
        self.t = SQLServerToPostgreSQLTransformer()

    def test_int_maps_to_integer(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="INT")])])[0]
        assert result.columns[0].target_type == "INTEGER"

    def test_bigint_maps_to_bigint(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="BIGINT")])])[0]
        assert result.columns[0].target_type == "BIGINT"

    def test_smallint_maps_to_smallint(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="SMALLINT")])])[0]
        assert result.columns[0].target_type == "SMALLINT"

    def test_tinyint_maps_to_smallint(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="TINYINT")])])[0]
        assert result.columns[0].target_type == "SMALLINT"

    def test_bit_maps_to_boolean(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="BIT")])])[0]
        assert result.columns[0].target_type == "BOOLEAN"

    def test_decimal_with_precision_scale(self) -> None:
        col = _col(ss_type="DECIMAL", precision=14, scale=4)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "NUMERIC(14,4)"

    def test_float_maps_to_double_precision(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="FLOAT")])])[0]
        assert result.columns[0].target_type == "DOUBLE PRECISION"

    def test_real_maps_to_real(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="REAL")])])[0]
        assert result.columns[0].target_type == "REAL"

    def test_money_maps_to_numeric19_4(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="MONEY")])])[0]
        assert result.columns[0].target_type == "NUMERIC(19,4)"

    def test_varchar_with_length(self) -> None:
        col = _col(ss_type="VARCHAR", char_length=200)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "VARCHAR(200)"

    def test_nvarchar_with_length(self) -> None:
        col = _col(ss_type="NVARCHAR", char_length=150)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "VARCHAR(150)"

    def test_varchar_max_maps_to_text(self) -> None:
        col = _col(ss_type="VARCHAR", char_length=-1)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "TEXT"

    def test_nvarchar_max_maps_to_text(self) -> None:
        col = _col(ss_type="NVARCHAR", char_length=-1)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "TEXT"

    def test_char_with_length(self) -> None:
        col = _col(ss_type="CHAR", char_length=10)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "CHAR(10)"

    def test_nchar_with_length(self) -> None:
        col = _col(ss_type="NCHAR", char_length=5)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "CHAR(5)"

    def test_binary_maps_to_bytea(self) -> None:
        col = _col(ss_type="BINARY", char_length=16)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "BYTEA"

    def test_varbinary_maps_to_bytea(self) -> None:
        col = _col(ss_type="VARBINARY", char_length=500)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "BYTEA"

    def test_varbinary_max_maps_to_bytea(self) -> None:
        col = _col(ss_type="VARBINARY", char_length=-1)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "BYTEA"

    def test_datetime_maps_to_timestamp(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="DATETIME")])])[0]
        assert result.columns[0].target_type == "TIMESTAMP"

    def test_datetime2_maps_to_timestamp6(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="DATETIME2")])])[0]
        assert result.columns[0].target_type == "TIMESTAMP(6)"

    def test_datetimeoffset_maps_to_timestamptz(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="DATETIMEOFFSET")])])[0]
        assert result.columns[0].target_type == "TIMESTAMPTZ"

    def test_uniqueidentifier_maps_to_uuid(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="UNIQUEIDENTIFIER")])])[0]
        assert result.columns[0].target_type == "UUID"

    def test_xml_maps_to_xml(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="XML")])])[0]
        assert result.columns[0].target_type == "XML"

    def test_image_maps_to_bytea_with_warning(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="IMAGE")])])[0]
        assert result.columns[0].target_type == "BYTEA"
        assert len(result.columns[0].warnings) > 0

    def test_unknown_maps_to_text_with_warning(self) -> None:
        col = _col(ss_type="CURSOR")
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "TEXT"
        assert len(result.columns[0].warnings) > 0


class TestIdentityPreserved:
    def test_identity_preserved(self) -> None:
        col = _col(ss_type="INT", auto_increment=True, is_primary_key=True)
        result = SQLServerToPostgreSQLTransformer().transform([_table(columns=[col], pk=["COL"])])[0]
        assert result.columns[0].auto_increment is True


class TestPKComposite:
    def test_composite_pk(self) -> None:
        cols = [_col("A", "BIGINT"), _col("B", "NVARCHAR", char_length=50)]
        result = SQLServerToPostgreSQLTransformer().transform([_table(columns=cols, pk=["A", "B"])])[0]
        assert result.columns[0].is_primary_key is True
        assert result.columns[1].is_primary_key is True


class TestIdentifierTruncation:
    def test_name_truncated_at_63(self) -> None:
        long_name = "T" * 70
        t = _table(name=long_name)
        result = SQLServerToPostgreSQLTransformer().transform([t])[0]
        assert len(result.name) <= 63


class TestFKTransform:
    def test_external_fk_gets_warning(self) -> None:
        fk = CanonicalFK(
            name="FK_EXT",
            original_name="FK_EXT",
            columns=["COL_A"],
            ref_table="EXT_TABLE",
            ref_columns=["ID"],
            on_delete="NO ACTION",
            on_update="NO ACTION",
            is_external=True,
        )
        result = SQLServerToPostgreSQLTransformer().transform([_table(columns=[_col("COL_A")], fks=[fk])])[0]
        assert any("FK_EXT" in w.message for w in result.warnings)


class TestViewTransform:
    def test_view_passthrough_warning(self) -> None:
        view = CanonicalView(
            name="V_TEST",
            original_name="V_TEST",
            schema="dbo",
            query="SELECT GETDATE(), ISNULL(a,b) FROM t",
            columns=[],
            comment="",
            warnings=[],
        )
        result = SQLServerToPostgreSQLTransformer().transform_views([view])[0]
        assert any("pass-through" in w.message for w in result.warnings)

    def test_view_name_truncated_at_63(self) -> None:
        view = CanonicalView(
            name="V_" + "X" * 65,
            original_name="V_" + "X" * 65,
            schema="dbo",
            query="SELECT 1",
            columns=[],
            comment="",
            warnings=[],
        )
        result = SQLServerToPostgreSQLTransformer().transform_views([view])[0]
        assert len(result.name) <= 63
