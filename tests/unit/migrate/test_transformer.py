"""Tests para OracleToMariaDBTransformer."""

from __future__ import annotations

from util_bbdd.migrate.ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalTable,
)
from util_bbdd.migrate.transformers.oracle_to_mariadb import OracleToMariaDBTransformer


def _make_column(
    name: str = "COL1",
    oracle_type: str = "VARCHAR2",
    nullable: bool = True,
    default: str | None = None,
    ordinal: int = 1,
    char_length: int | None = 100,
    precision: int | None = None,
    scale: int | None = None,
) -> CanonicalColumn:
    return CanonicalColumn(
        name=name,
        original_name=name,
        oracle_type=oracle_type,
        target_type="",
        nullable=nullable,
        default=default,
        comment="",
        ordinal=ordinal,
        char_length=char_length,
        precision=precision,
        scale=scale,
    )


def _make_table(
    name: str = "MY_TABLE",
    columns: list[CanonicalColumn] | None = None,
    pk: list[str] | None = None,
    fks: list[CanonicalFK] | None = None,
    indexes: list[CanonicalIndex] | None = None,
) -> CanonicalTable:
    return CanonicalTable(
        name=name,
        original_name=name,
        schema="TEST",
        columns=columns or [],
        primary_key=pk or [],
        indexes=indexes or [],
        foreign_keys=fks or [],
        comment="",
        warnings=[],
    )


class TestColumnTypeMapping:
    def setup_method(self) -> None:
        self.t = OracleToMariaDBTransformer()

    def test_varchar2_maps_correctly(self) -> None:
        col = _make_column(oracle_type="VARCHAR2", char_length=200)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "VARCHAR(200)"

    def test_number_no_precision_maps_to_double(self) -> None:
        col = _make_column(oracle_type="NUMBER", char_length=None, precision=None, scale=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "DOUBLE"
        assert len(result.columns[0].warnings) > 0

    def test_number_with_scale_maps_to_decimal(self) -> None:
        col = _make_column(oracle_type="NUMBER", char_length=None, precision=10, scale=2)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "DECIMAL(10,2)"

    def test_number_integer_maps_to_bigint(self) -> None:
        col = _make_column(oracle_type="NUMBER", char_length=None, precision=15, scale=0)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "BIGINT"

    def test_date_maps_to_datetime_with_warning(self) -> None:
        col = _make_column(oracle_type="DATE", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "DATETIME"
        assert len(result.columns[0].warnings) > 0

    def test_clob_maps_to_longtext_utf8mb4(self) -> None:
        col = _make_column(oracle_type="CLOB", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert "LONGTEXT" in result.columns[0].target_type
        assert "utf8mb4" in result.columns[0].target_type

    def test_blob_maps_to_longblob(self) -> None:
        col = _make_column(oracle_type="BLOB", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "LONGBLOB"

    def test_rowid_column_is_omitted(self) -> None:
        col = _make_column(oracle_type="ROWID", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].omit is True

    def test_raw_maps_to_varbinary(self) -> None:
        col = _make_column(oracle_type="RAW", char_length=64)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "VARBINARY(64)"

    def test_timestamp_with_scale_maps_to_datetime_n(self) -> None:
        col = _make_column(oracle_type="TIMESTAMP", char_length=None, scale=6)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "DATETIME(6)"

    def test_unknown_type_maps_to_text_with_warning(self) -> None:
        col = _make_column(oracle_type="MYWEIRDTYPE", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "TEXT"
        assert len(result.columns[0].warnings) > 0


class TestSequenceDetection:
    def setup_method(self) -> None:
        self.t = OracleToMariaDBTransformer()

    def test_nextval_default_becomes_auto_increment(self) -> None:
        col = _make_column(
            name="ID",
            oracle_type="NUMBER",
            char_length=None,
            precision=10,
            scale=0,
            default="MY_SEQ.NEXTVAL",
        )
        table = _make_table(columns=[col], pk=["ID"])
        result = self.t.transform([table])[0]
        assert result.columns[0].auto_increment is True
        assert result.columns[0].default is None

    def test_nextval_column_not_pk_gets_warning_and_pk(self) -> None:
        col = _make_column(
            name="ID",
            oracle_type="NUMBER",
            char_length=None,
            precision=10,
            scale=0,
            default="MY_SEQ.NEXTVAL",
        )
        table = _make_table(columns=[col], pk=[])
        result = self.t.transform([table])[0]
        assert result.columns[0].auto_increment is True
        assert "ID" in result.primary_key
        assert any(w.severity == "WARNING" for w in result.warnings)

    def test_no_sequence_column_unchanged(self) -> None:
        col = _make_column(name="NAME", oracle_type="VARCHAR2", default=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].auto_increment is False


class TestIdentifierTruncation:
    def setup_method(self) -> None:
        self.t = OracleToMariaDBTransformer()

    def test_long_table_name_truncated_with_warning(self) -> None:
        long_name = "TABLE_" + "A" * 65
        table = _make_table(name=long_name)
        result = self.t.transform([table])[0]
        assert len(result.name) <= 64
        assert any(w.oracle_type == "IDENTIFIER" for w in result.warnings)

    def test_short_table_name_unchanged(self) -> None:
        table = _make_table(name="MY_TABLE")
        result = self.t.transform([table])[0]
        assert result.name == "MY_TABLE"
        assert not any(w.oracle_type == "IDENTIFIER" for w in result.warnings)


class TestIntDisplayWidth:
    def test_integer_oracle_type_gets_display_width(self) -> None:
        col = _make_column(oracle_type="INTEGER", char_length=None)
        table = _make_table(columns=[col])
        result = OracleToMariaDBTransformer().transform([table])[0]
        assert result.columns[0].target_type == "INT(11)"

    def test_int_oracle_type_gets_display_width(self) -> None:
        col = _make_column(oracle_type="INT", char_length=None)
        table = _make_table(columns=[col])
        result = OracleToMariaDBTransformer().transform([table])[0]
        assert result.columns[0].target_type == "INT(11)"

    def test_custom_display_width(self) -> None:
        col = _make_column(oracle_type="INTEGER", char_length=None)
        table = _make_table(columns=[col])
        result = OracleToMariaDBTransformer(int_display_width=8).transform([table])[0]
        assert result.columns[0].target_type == "INT(8)"

    def test_zero_display_width_disables_it(self) -> None:
        col = _make_column(oracle_type="INTEGER", char_length=None)
        table = _make_table(columns=[col])
        result = OracleToMariaDBTransformer(int_display_width=0).transform([table])[0]
        assert result.columns[0].target_type == "INT"

    def test_number_small_precision_gets_int_display_width(self) -> None:
        col = _make_column(oracle_type="NUMBER", char_length=None, precision=8, scale=0)
        table = _make_table(columns=[col])
        result = OracleToMariaDBTransformer().transform([table])[0]
        assert result.columns[0].target_type == "INT(11)"


class TestPKAutoIncrement:
    def setup_method(self) -> None:
        self.t = OracleToMariaDBTransformer()

    def test_single_bigint_pk_becomes_auto_increment(self) -> None:
        col = _make_column(name="ID", oracle_type="NUMBER", precision=15, scale=0, char_length=None)
        table = _make_table(columns=[col], pk=["ID"])
        result = self.t.transform([table])[0]
        assert result.columns[0].auto_increment is True

    def test_single_int_pk_becomes_auto_increment(self) -> None:
        col = _make_column(name="ID", oracle_type="NUMBER", precision=8, scale=0, char_length=None)
        table = _make_table(columns=[col], pk=["ID"])
        result = self.t.transform([table])[0]
        assert result.columns[0].auto_increment is True

    def test_composite_pk_not_auto_increment(self) -> None:
        col1 = _make_column(name="ID1", oracle_type="NUMBER", precision=10, scale=0, char_length=None)
        col2 = _make_column(name="ID2", oracle_type="NUMBER", precision=10, scale=0, char_length=None)
        table = _make_table(columns=[col1, col2], pk=["ID1", "ID2"])
        result = self.t.transform([table])[0]
        assert result.columns[0].auto_increment is False
        assert result.columns[1].auto_increment is False

    def test_varchar_pk_not_auto_increment(self) -> None:
        col = _make_column(name="CODE", oracle_type="VARCHAR2", char_length=10)
        table = _make_table(columns=[col], pk=["CODE"])
        result = self.t.transform([table])[0]
        assert result.columns[0].auto_increment is False

    def test_nextval_pk_not_double_set(self) -> None:
        col = _make_column(name="ID", oracle_type="NUMBER", precision=10, scale=0,
                           char_length=None, default="MY_SEQ.NEXTVAL")
        table = _make_table(columns=[col], pk=["ID"])
        result = self.t.transform([table])[0]
        assert result.columns[0].auto_increment is True
        # Solo una advertencia INFO de sequence (no dos)
        seq_infos = [w for w in result.warnings if "AUTO_INCREMENT" in w.message]
        assert len(seq_infos) == 1

    def test_pk_auto_increment_emits_info_warning(self) -> None:
        col = _make_column(name="ID", oracle_type="NUMBER", precision=15, scale=0, char_length=None)
        table = _make_table(columns=[col], pk=["ID"])
        result = self.t.transform([table])[0]
        assert any(w.severity == "INFO" and "AUTO_INCREMENT" in w.message for w in result.warnings)


class TestExternalFK:
    def setup_method(self) -> None:
        self.t = OracleToMariaDBTransformer()

    def test_external_fk_gets_warning(self) -> None:
        fk = CanonicalFK(
            name="FK_EXT",
            original_name="FK_EXT",
            columns=["REF_ID"],
            ref_table="OTHER_TABLE",
            ref_columns=["ID"],
            on_delete="NO ACTION",
            on_update="NO ACTION",
            is_external=True,
        )
        table = _make_table(fks=[fk])
        result = self.t.transform([table])[0]
        fk_warnings = [w for w in result.warnings if "FK_EXT" in w.message or "FK" in w.oracle_type]
        assert len(fk_warnings) > 0
