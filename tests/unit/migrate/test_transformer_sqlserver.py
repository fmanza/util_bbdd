"""Tests para OracleToSQLServerTransformer."""

from __future__ import annotations

from util_bbdd.migrate._compat.identifier_rules import MAX_SQLSERVER_IDENTIFIER_LENGTH
from util_bbdd.migrate.ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalTable,
)
from util_bbdd.migrate.transformers.oracle_to_sqlserver import OracleToSQLServerTransformer


def _make_column(
    name: str = "COL1",
    oracle_type: str = "VARCHAR2",
    nullable: bool = True,
    default: str | None = None,
    ordinal: int = 1,
    char_length: int | None = 100,
    precision: int | None = None,
    scale: int | None = None,
    is_primary_key: bool = False,
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
        is_primary_key=is_primary_key,
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
        self.t = OracleToSQLServerTransformer()

    def test_varchar2_maps_to_nvarchar_with_length(self) -> None:
        col = _make_column(oracle_type="VARCHAR2", char_length=200)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "NVARCHAR(200)"

    def test_nvarchar2_maps_to_nvarchar(self) -> None:
        col = _make_column(oracle_type="NVARCHAR2", char_length=50)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "NVARCHAR(50)"

    def test_char_maps_to_nchar(self) -> None:
        col = _make_column(oracle_type="CHAR", char_length=10)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "NCHAR(10)"

    def test_date_maps_to_datetime2_with_warning(self) -> None:
        col = _make_column(oracle_type="DATE", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        rcol = result.columns[0]
        assert rcol.target_type == "DATETIME2"
        assert rcol.ddl_comment is not None
        assert any(w.severity == "WARNING" for w in rcol.warnings)

    def test_timestamp_maps_to_datetime2_with_precision(self) -> None:
        col = _make_column(oracle_type="TIMESTAMP", scale=6, char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "DATETIME2(6)"

    def test_timestamp_precision_capped_at_7(self) -> None:
        col = _make_column(oracle_type="TIMESTAMP", scale=9, char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "DATETIME2(7)"

    def test_timestamp_no_scale_defaults_7(self) -> None:
        col = _make_column(oracle_type="TIMESTAMP", scale=None, char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "DATETIME2(7)"

    def test_timestamp_with_tz_maps_to_datetimeoffset(self) -> None:
        col = _make_column(oracle_type="TIMESTAMP WITH TIME ZONE", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "DATETIMEOFFSET"

    def test_clob_maps_to_nvarchar_max(self) -> None:
        col = _make_column(oracle_type="CLOB", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "NVARCHAR(MAX)"

    def test_blob_maps_to_varbinary_max(self) -> None:
        col = _make_column(oracle_type="BLOB", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "VARBINARY(MAX)"

    def test_raw_maps_to_varbinary_with_length(self) -> None:
        col = _make_column(oracle_type="RAW", char_length=100)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "VARBINARY(100)"

    def test_number_with_precision_scale_maps_to_numeric(self) -> None:
        col = _make_column(oracle_type="NUMBER", precision=15, scale=2, char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "NUMERIC(15,2)"

    def test_number_integer_precision_maps_to_int(self) -> None:
        col = _make_column(oracle_type="NUMBER", precision=9, scale=0, char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "INT"

    def test_number_no_precision_maps_to_float_with_warning(self) -> None:
        col = _make_column(oracle_type="NUMBER", precision=None, scale=None, char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        rcol = result.columns[0]
        assert rcol.target_type == "FLOAT"
        assert any(w.severity == "WARNING" for w in rcol.warnings)
        assert any("sin precisión" in w.message for w in rcol.warnings)

    def test_number_1_0_maps_to_tinyint_with_unsigned_warning(self) -> None:
        """CMP-01 (AUDIT_CODE 2026-09-22): NUMBER(1,0)/(2,0) Oracle es con signo, TINYINT SQL
        Server es unsigned (0-255); debe emitirse un aviso, no quedar en silencio."""
        col = _make_column(name="ID", oracle_type="NUMBER", precision=1, scale=0, char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        rcol = result.columns[0]
        assert rcol.target_type == "TINYINT"
        assert rcol.ddl_comment is not None
        assert "unsigned" in rcol.ddl_comment
        assert any(w.severity == "WARNING" for w in rcol.warnings)
        assert any("unsigned" in w.message for w in rcol.warnings)
        # El mensaje no debe ser el hardcodeado de la rama "sin precisión" (bug distinto ya
        # corregido: el texto del warning reflejaba siempre esa rama sin importar cuál disparó
        # el ddl_comment).
        assert not any("sin precisión" in w.message for w in rcol.warnings)

    def test_rowid_column_omitted(self) -> None:
        col = _make_column(oracle_type="ROWID", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        rcol = result.columns[0]
        assert rcol.omit is True
        assert rcol.target_type == ""
        assert any(w.severity == "ERROR" for w in rcol.warnings)

    def test_unknown_type_maps_to_nvarchar_max(self) -> None:
        col = _make_column(oracle_type="UNKNOWN_TYPE_XYZ", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        rcol = result.columns[0]
        assert rcol.target_type == "NVARCHAR(MAX)"
        assert any(w.severity == "WARNING" for w in rcol.warnings)

    def test_xmltype_maps_to_xml_with_proposals(self) -> None:
        col = _make_column(oracle_type="XMLTYPE", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        rcol = result.columns[0]
        assert rcol.target_type == "XML"
        assert rcol.ddl_comment is not None

    def test_integer_maps_to_int(self) -> None:
        col = _make_column(oracle_type="INTEGER", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "INT"


class TestVarchar2LengthLimit:
    def setup_method(self) -> None:
        self.t = OracleToSQLServerTransformer()

    def test_varchar2_4000_stays_nvarchar_4000(self) -> None:
        col = _make_column(oracle_type="VARCHAR2", char_length=4000)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "NVARCHAR(4000)"

    def test_varchar2_4001_becomes_nvarchar_max(self) -> None:
        col = _make_column(oracle_type="VARCHAR2", char_length=4001)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "NVARCHAR(MAX)"

    def test_varchar2_no_length_defaults_255(self) -> None:
        col = _make_column(oracle_type="VARCHAR2", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "NVARCHAR(255)"


class TestIdentifierRules:
    def setup_method(self) -> None:
        self.t = OracleToSQLServerTransformer()

    def test_short_identifier_unchanged(self) -> None:
        table = _make_table(name="SHORT_TABLE", columns=[_make_column()])
        result = self.t.transform([table])[0]
        assert result.name == "SHORT_TABLE"
        assert not result.warnings

    def test_identifier_at_128_unchanged(self) -> None:
        name = "T" * MAX_SQLSERVER_IDENTIFIER_LENGTH
        table = _make_table(name=name, columns=[_make_column()])
        result = self.t.transform([table])[0]
        assert result.name == name
        assert not result.warnings

    def test_identifier_over_128_truncated_with_warning(self) -> None:
        name = "X" * 130
        table = _make_table(name=name, columns=[_make_column()])
        result = self.t.transform([table])[0]
        assert len(result.name) <= MAX_SQLSERVER_IDENTIFIER_LENGTH
        assert any(w.oracle_type == "IDENTIFIER" for w in result.warnings)

    def test_column_identifier_over_128_truncated(self) -> None:
        col = _make_column(name="C" * 130)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert len(result.columns[0].name) <= MAX_SQLSERVER_IDENTIFIER_LENGTH


class TestPKIdentity:
    def setup_method(self) -> None:
        self.t = OracleToSQLServerTransformer()

    def test_single_int_pk_becomes_identity(self) -> None:
        col = _make_column("ID", oracle_type="NUMBER", precision=10, scale=0, char_length=None)
        table = _make_table(columns=[col], pk=["ID"])
        result = self.t.transform([table])[0]
        pk_col = result.columns[0]
        assert pk_col.auto_increment is True
        assert pk_col.nullable is False

    def test_pk_identity_warning_emitted(self) -> None:
        col = _make_column("ID", oracle_type="NUMBER", precision=10, scale=0, char_length=None)
        table = _make_table(columns=[col], pk=["ID"])
        result = self.t.transform([table])[0]
        assert any("IDENTITY" in w.message for w in result.warnings)

    def test_compound_pk_no_identity(self) -> None:
        col1 = _make_column("ID1", oracle_type="NUMBER", precision=9, scale=0, char_length=None)
        col2 = _make_column("ID2", oracle_type="NUMBER", precision=9, scale=0, char_length=None)
        table = _make_table(columns=[col1, col2], pk=["ID1", "ID2"])
        result = self.t.transform([table])[0]
        assert all(not c.auto_increment for c in result.columns)

    def test_number_no_precision_pk_becomes_int_identity(self) -> None:
        col = _make_column("ID", oracle_type="NUMBER", precision=None, scale=None, char_length=None)
        table = _make_table(columns=[col], pk=["ID"])
        result = self.t.transform([table])[0]
        pk_col = result.columns[0]
        assert pk_col.target_type == "INT"
        assert pk_col.auto_increment is True

    def test_already_identity_not_doubled(self) -> None:
        col = _make_column("ID", oracle_type="NUMBER", precision=9, scale=0, char_length=None)
        col.auto_increment = True
        table = _make_table(columns=[col], pk=["ID"])
        result = self.t.transform([table])[0]
        # No duplicate identity warning
        identity_warnings = [w for w in result.warnings if "IDENTITY" in w.message]
        assert len(identity_warnings) <= 1

    def test_non_integer_pk_no_identity(self) -> None:
        col = _make_column("CODE", oracle_type="VARCHAR2", char_length=20)
        table = _make_table(columns=[col], pk=["CODE"])
        result = self.t.transform([table])[0]
        assert result.columns[0].auto_increment is False


class TestSequenceColumns:
    def setup_method(self) -> None:
        self.t = OracleToSQLServerTransformer()

    def test_nextval_default_converted_to_identity(self) -> None:
        col = _make_column(
            "ID", oracle_type="NUMBER", precision=10, scale=0, default="MY_SEQ.NEXTVAL", char_length=None
        )
        table = _make_table(columns=[col], pk=["ID"])
        result = self.t.transform([table])[0]
        pk_col = result.columns[0]
        assert pk_col.auto_increment is True
        assert pk_col.default is None

    def test_nextval_non_pk_column_becomes_pk(self) -> None:
        col_id = _make_column("ID", oracle_type="NUMBER", precision=10, scale=0, char_length=None)
        col_seq = _make_column(
            "SEQ_COL", oracle_type="NUMBER", precision=10, scale=0, default="SOME_SEQ.NEXTVAL", char_length=None
        )
        table = _make_table(columns=[col_id, col_seq], pk=["ID"])
        result = self.t.transform([table])[0]
        seq_col = next(c for c in result.columns if c.name == "SEQ_COL")
        assert seq_col.auto_increment is True
        assert seq_col.is_primary_key is True
        assert any(
            w.severity == "WARNING"
            for w in result.warnings
            if "IDENTITY" in w.target_type or "secuencia" in w.message.lower()
        )


class TestFKExternal:
    def setup_method(self) -> None:
        self.t = OracleToSQLServerTransformer()

    def test_external_fk_flagged_with_warning(self) -> None:
        fk = CanonicalFK(
            name="FK_EXT",
            original_name="FK_EXT",
            columns=["OTHER_ID"],
            ref_table="EXTERNAL_TABLE",
            ref_columns=["ID"],
            on_delete="NO ACTION",
            on_update="NO ACTION",
            is_external=True,
        )
        col = _make_column("OTHER_ID", oracle_type="NUMBER", precision=9, scale=0, char_length=None)
        table = _make_table(columns=[col], fks=[fk])
        result = self.t.transform([table])[0]
        result_fk = result.foreign_keys[0]
        assert result_fk.is_external is True
        assert any("fuera del schema" in w.message for w in result.warnings)

    def test_internal_fk_no_external_warning(self) -> None:
        fk = CanonicalFK(
            name="FK_INT",
            original_name="FK_INT",
            columns=["OTHER_ID"],
            ref_table="INTERNAL_TABLE",
            ref_columns=["ID"],
            on_delete="NO ACTION",
            on_update="NO ACTION",
            is_external=False,
        )
        col = _make_column("OTHER_ID", oracle_type="NUMBER", precision=9, scale=0, char_length=None)
        table = _make_table(columns=[col], fks=[fk])
        result = self.t.transform([table])[0]
        assert not any("fuera del schema" in w.message for w in result.warnings)
