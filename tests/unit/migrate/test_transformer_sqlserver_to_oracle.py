"""Tests para SQLServerToOracleTransformer."""

from __future__ import annotations

from util_bbdd.migrate.ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalTable,
    CanonicalView,
)
from util_bbdd.migrate.transformers.sqlserver_to_oracle import SQLServerToOracleTransformer


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
        oracle_type=ss_type,  # campo histórico = tipo fuente
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
    indexes: list[CanonicalIndex] | None = None,
) -> CanonicalTable:
    return CanonicalTable(
        name=name,
        original_name=name,
        schema="dbo",
        columns=columns or [],
        primary_key=pk or [],
        indexes=indexes or [],
        foreign_keys=fks or [],
        comment="",
        warnings=[],
    )


class TestColumnTypeMappingOracle:
    def setup_method(self) -> None:
        self.t = SQLServerToOracleTransformer()

    def test_int_maps_to_number10(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="INT")])])[0]
        assert result.columns[0].target_type == "NUMBER(10,0)"

    def test_bigint_maps_to_number19(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="BIGINT")])])[0]
        assert result.columns[0].target_type == "NUMBER(19,0)"

    def test_bit_maps_to_number1(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="BIT")])])[0]
        assert result.columns[0].target_type == "NUMBER(1,0)"

    def test_decimal_with_precision_scale(self) -> None:
        col = _col(ss_type="DECIMAL", precision=10, scale=2)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "NUMBER(10,2)"

    def test_decimal_default_precision(self) -> None:
        col = _col(ss_type="DECIMAL", precision=None, scale=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "NUMBER(18,0)"

    def test_varchar_with_length(self) -> None:
        col = _col(ss_type="VARCHAR", char_length=200)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "VARCHAR2(200)"

    def test_nvarchar_with_length(self) -> None:
        col = _col(ss_type="NVARCHAR", char_length=100)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "NVARCHAR2(100)"

    def test_varchar_max_maps_to_clob(self) -> None:
        col = _col(ss_type="VARCHAR", char_length=-1)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "CLOB"

    def test_nvarchar_max_maps_to_clob(self) -> None:
        col = _col(ss_type="NVARCHAR", char_length=-1)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "CLOB"

    def test_varchar_exceeds_oracle_limit_maps_to_clob(self) -> None:
        col = _col(ss_type="VARCHAR", char_length=5000)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "CLOB"

    def test_char_with_length(self) -> None:
        col = _col(ss_type="CHAR", char_length=10)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "CHAR(10)"

    def test_nchar_with_length(self) -> None:
        col = _col(ss_type="NCHAR", char_length=5)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "NCHAR(5)"

    def test_binary_with_length(self) -> None:
        col = _col(ss_type="BINARY", char_length=16)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "RAW(16)"

    def test_varbinary_with_length(self) -> None:
        col = _col(ss_type="VARBINARY", char_length=500)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "RAW(500)"

    def test_varbinary_exceeds_raw_limit_maps_to_blob(self) -> None:
        col = _col(ss_type="VARBINARY", char_length=3000)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "BLOB"

    def test_varbinary_max_maps_to_blob(self) -> None:
        col = _col(ss_type="VARBINARY", char_length=-1)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "BLOB"

    def test_datetime2_maps_to_timestamp(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="DATETIME2")])])[0]
        assert result.columns[0].target_type == "TIMESTAMP"

    def test_datetimeoffset_maps_to_timestamp_tz(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="DATETIMEOFFSET")])])[0]
        assert "TIME ZONE" in result.columns[0].target_type

    def test_uniqueidentifier_maps_to_char36(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="UNIQUEIDENTIFIER")])])[0]
        assert result.columns[0].target_type == "CHAR(36)"

    def test_money_maps_to_number19_4(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="MONEY")])])[0]
        assert result.columns[0].target_type == "NUMBER(19,4)"

    def test_image_maps_to_blob(self) -> None:
        result = self.t.transform([_table(columns=[_col(ss_type="IMAGE")])])[0]
        assert result.columns[0].target_type == "BLOB"

    def test_unknown_type_maps_to_clob_with_warning(self) -> None:
        col = _col(ss_type="CURSOR")
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "CLOB"
        assert len(result.columns[0].warnings) > 0


class TestIdentityPreserved:
    def test_identity_column_preserves_auto_increment(self) -> None:
        col = _col(ss_type="INT", auto_increment=True, is_primary_key=True)
        result = SQLServerToOracleTransformer().transform([_table(columns=[col], pk=["COL"])])[0]
        assert result.columns[0].auto_increment is True


class TestPKComposite:
    def test_composite_pk_marked_correctly(self) -> None:
        cols = [
            _col("A", "INT"),
            _col("B", "INT"),
            _col("C", "NVARCHAR", char_length=50),
        ]
        t = _table(columns=cols, pk=["A", "B"])
        result = SQLServerToOracleTransformer().transform([t])[0]
        a = next(c for c in result.columns if c.name == "A")
        b = next(c for c in result.columns if c.name == "B")
        c_col = next(c for c in result.columns if c.name == "C")
        assert a.is_primary_key is True
        assert b.is_primary_key is True
        assert c_col.is_primary_key is False


class TestIdentifierTruncation:
    def test_table_name_truncated_at_30(self) -> None:
        long_name = "A" * 35
        t = _table(name=long_name)
        result = SQLServerToOracleTransformer().transform([t])[0]
        assert len(result.name) <= 30
        assert len(result.warnings) > 0

    def test_column_name_truncated_at_30(self) -> None:
        col = _col(name="C" * 35, ss_type="INT")
        result = SQLServerToOracleTransformer().transform([_table(columns=[col])])[0]
        assert len(result.columns[0].name) <= 30


class TestFKTransform:
    def test_internal_fk_no_warning(self) -> None:
        fk = CanonicalFK(
            name="FK_TEST", original_name="FK_TEST",
            columns=["COL_A"], ref_table="OTHER_TABLE", ref_columns=["ID"],
            on_delete="NO ACTION", on_update="NO ACTION", is_external=False,
        )
        t = _table(columns=[_col("COL_A", "INT")], fks=[fk])
        result = SQLServerToOracleTransformer().transform([t])[0]
        fk_warnings = [w for w in result.warnings if "FOREIGN KEY" in w.oracle_type]
        assert len(fk_warnings) == 0

    def test_external_fk_gets_warning(self) -> None:
        fk = CanonicalFK(
            name="FK_EXT", original_name="FK_EXT",
            columns=["COL_A"], ref_table="EXT_TABLE", ref_columns=["ID"],
            on_delete="NO ACTION", on_update="NO ACTION", is_external=True,
        )
        t = _table(columns=[_col("COL_A", "INT")], fks=[fk])
        result = SQLServerToOracleTransformer().transform([t])[0]
        fk_warnings = [w for w in result.warnings if "FK_EXT" in w.message]
        assert len(fk_warnings) > 0

    def test_on_update_cascade_gets_warning(self) -> None:
        fk = CanonicalFK(
            name="FK_UPD", original_name="FK_UPD",
            columns=["COL_A"], ref_table="T2", ref_columns=["ID"],
            on_delete="NO ACTION", on_update="CASCADE", is_external=False,
        )
        t = _table(columns=[_col("COL_A", "INT")], fks=[fk])
        result = SQLServerToOracleTransformer().transform([t])[0]
        upd_warns = [w for w in result.warnings if "ON UPDATE" in w.message]
        assert len(upd_warns) > 0


class TestViewTransform:
    def test_view_gets_passthrough_warning(self) -> None:
        view = CanonicalView(
            name="V_REPORT", original_name="V_REPORT", schema="dbo",
            query="SELECT GETDATE(), ISNULL(a, b) FROM t",
            columns=["a", "b"], comment="", warnings=[],
        )
        result = SQLServerToOracleTransformer().transform_views([view])[0]
        assert any("pass-through" in w.message for w in result.warnings)

    def test_view_name_truncated_at_30(self) -> None:
        view = CanonicalView(
            name="V_" + "X" * 35, original_name="V_" + "X" * 35, schema="dbo",
            query="SELECT 1", columns=[], comment="", warnings=[],
        )
        result = SQLServerToOracleTransformer().transform_views([view])[0]
        assert len(result.name) <= 30
