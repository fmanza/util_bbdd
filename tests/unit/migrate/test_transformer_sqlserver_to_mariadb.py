"""Tests para SQLServerToMariaDBTransformer."""

from __future__ import annotations

from util_bbdd.migrate.ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalTable,
    CanonicalView,
)
from util_bbdd.migrate.transformers.sqlserver_to_mariadb import SQLServerToMariaDBTransformer


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
        oracle_type=ss_type,
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


class TestColumnTypeMappingMariaDB:
    def setup_method(self) -> None:
        self.t = SQLServerToMariaDBTransformer()

    def test_int_maps_to_int(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="INT")])])[0]
        assert result.columns[0].target_type == "INT"

    def test_bigint_maps_to_bigint(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="BIGINT")])])[0]
        assert result.columns[0].target_type == "BIGINT"

    def test_bit_maps_to_tinyint1(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="BIT")])])[0]
        assert result.columns[0].target_type == "TINYINT(1)"

    def test_tinyint_maps_to_smallint_with_warning(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="TINYINT")])])[0]
        assert result.columns[0].target_type == "SMALLINT"
        assert len(result.columns[0].warnings) > 0

    def test_decimal_with_precision_scale(self) -> None:
        col = _col(ss_type="DECIMAL", precision=12, scale=3)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "DECIMAL(12,3)"

    def test_float_maps_to_double(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="FLOAT")])])[0]
        assert result.columns[0].target_type == "DOUBLE"

    def test_varchar_with_length(self) -> None:
        col = _col(ss_type="VARCHAR", char_length=255)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "VARCHAR(255)"

    def test_nvarchar_with_length(self) -> None:
        col = _col(ss_type="NVARCHAR", char_length=100)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "VARCHAR(100)"

    def test_varchar_max_maps_to_longtext(self) -> None:
        col = _col(ss_type="VARCHAR", char_length=-1)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "LONGTEXT"

    def test_nvarchar_max_maps_to_longtext(self) -> None:
        col = _col(ss_type="NVARCHAR", char_length=-1)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "LONGTEXT"

    def test_char_with_length(self) -> None:
        col = _col(ss_type="CHAR", char_length=10)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "CHAR(10)"

    def test_nchar_with_length(self) -> None:
        col = _col(ss_type="NCHAR", char_length=5)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "CHAR(5)"

    def test_binary_with_length(self) -> None:
        col = _col(ss_type="BINARY", char_length=16)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "BINARY(16)"

    def test_varbinary_with_length(self) -> None:
        col = _col(ss_type="VARBINARY", char_length=500)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "VARBINARY(500)"

    def test_varbinary_max_maps_to_longblob(self) -> None:
        col = _col(ss_type="VARBINARY", char_length=-1)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "LONGBLOB"

    def test_datetime_maps_to_datetime(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="DATETIME")])])[0]
        assert result.columns[0].target_type == "DATETIME"

    def test_datetime2_maps_to_datetime6(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="DATETIME2")])])[0]
        assert result.columns[0].target_type == "DATETIME(6)"

    def test_datetimeoffset_maps_to_varchar35_with_warning(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="DATETIMEOFFSET")])])[0]
        assert result.columns[0].target_type == "VARCHAR(35)"
        assert len(result.columns[0].warnings) > 0

    def test_uniqueidentifier_maps_to_char36(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="UNIQUEIDENTIFIER")])])[0]
        assert result.columns[0].target_type == "CHAR(36)"

    def test_money_maps_to_decimal19_4(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="MONEY")])])[0]
        assert result.columns[0].target_type == "DECIMAL(19,4)"

    def test_image_maps_to_longblob_with_warning(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="IMAGE")])])[0]
        assert result.columns[0].target_type == "LONGBLOB"
        assert len(result.columns[0].warnings) > 0

    def test_unknown_maps_to_longtext_with_warning(self) -> None:
        col = _col(ss_type="CURSOR")
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "LONGTEXT"
        assert len(result.columns[0].warnings) > 0


class TestIdentityPreserved:
    def test_identity_preserved(self) -> None:
        col = _col(ss_type="INT", auto_increment=True, is_primary_key=True)
        result = SQLServerToMariaDBTransformer().transform([_table(columns=[col], pk=["COL"])])[0]
        assert result.columns[0].auto_increment is True


class TestPKComposite:
    def test_composite_pk(self) -> None:
        cols = [_col("A", "INT"), _col("B", "NVARCHAR", char_length=50)]
        result = SQLServerToMariaDBTransformer().transform([_table(columns=cols, pk=["A", "B"])])[0]
        assert result.columns[0].is_primary_key is True
        assert result.columns[1].is_primary_key is True


class TestIdentifierTruncation:
    def test_name_truncated_at_64(self) -> None:
        long_name = "T" * 70
        t = _table(name=long_name)
        result = SQLServerToMariaDBTransformer().transform([t])[0]
        assert len(result.name) <= 64


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
        result = SQLServerToMariaDBTransformer().transform([_table(columns=[_col("COL_A")], fks=[fk])])[0]
        assert any("FK_EXT" in w.message for w in result.warnings)


class TestViewTransform:
    def test_view_passthrough_warning(self) -> None:
        view = CanonicalView(
            name="V_TEST",
            original_name="V_TEST",
            schema="dbo",
            query="SELECT GETDATE(), TOP 10 * FROM t",
            columns=[],
            comment="",
            warnings=[],
        )
        result = SQLServerToMariaDBTransformer().transform_views([view])[0]
        assert any("pass-through" in w.message for w in result.warnings)
