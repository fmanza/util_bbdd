"""Tests para OracleToPostgreSQLTransformer."""

from __future__ import annotations

from util_bbdd.migrate._compat.identifier_rules import MAX_POSTGRESQL_IDENTIFIER_LENGTH
from util_bbdd.migrate.ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalTable,
)
from util_bbdd.migrate.transformers.oracle_to_postgresql import OracleToPostgreSQLTransformer


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
        self.t = OracleToPostgreSQLTransformer()

    def test_varchar2_maps_to_varchar_with_length(self) -> None:
        col = _make_column(oracle_type="VARCHAR2", char_length=200)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "VARCHAR(200)"

    def test_nvarchar2_maps_to_varchar(self) -> None:
        col = _make_column(oracle_type="NVARCHAR2", char_length=50)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "VARCHAR(50)"

    def test_char_maps_to_char_with_length(self) -> None:
        col = _make_column(oracle_type="CHAR", char_length=10)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "CHAR(10)"

    def test_nchar_maps_to_char(self) -> None:
        col = _make_column(oracle_type="NCHAR", char_length=5)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "CHAR(5)"

    def test_integer_maps_to_integer(self) -> None:
        col = _make_column(oracle_type="INTEGER", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "INTEGER"

    def test_clob_maps_to_text(self) -> None:
        col = _make_column(oracle_type="CLOB", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "TEXT"

    def test_nclob_maps_to_text(self) -> None:
        col = _make_column(oracle_type="NCLOB", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "TEXT"

    def test_blob_maps_to_bytea(self) -> None:
        col = _make_column(oracle_type="BLOB", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "BYTEA"

    def test_raw_maps_to_bytea(self) -> None:
        col = _make_column(oracle_type="RAW", char_length=255)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "BYTEA"

    def test_date_maps_to_timestamp_with_warning(self) -> None:
        col = _make_column(oracle_type="DATE", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "TIMESTAMP"
        assert result.columns[0].ddl_comment is not None
        assert len(result.columns[0].warnings) > 0

    def test_timestamp_maps_to_timestamp_with_precision(self) -> None:
        col = _make_column(oracle_type="TIMESTAMP", char_length=None, scale=3)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "TIMESTAMP(3)"

    def test_timestamp_precision_capped_at_6(self) -> None:
        col = _make_column(oracle_type="TIMESTAMP", char_length=None, scale=9)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "TIMESTAMP(6)"

    def test_timestamp_no_scale_defaults_to_6(self) -> None:
        col = _make_column(oracle_type="TIMESTAMP", char_length=None, scale=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "TIMESTAMP(6)"

    def test_timestamp_with_tz_maps_to_timestamptz(self) -> None:
        col = _make_column(oracle_type="TIMESTAMP WITH TIME ZONE", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "TIMESTAMPTZ"

    def test_interval_year_to_month_maps_to_interval(self) -> None:
        col = _make_column(oracle_type="INTERVAL YEAR TO MONTH", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "INTERVAL"
        # PG soporta INTERVAL nativo — severity INFO, no WARNING
        assert result.columns[0].warnings[0].severity == "INFO"

    def test_interval_day_to_second_maps_to_interval(self) -> None:
        col = _make_column(oracle_type="INTERVAL DAY TO SECOND", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "INTERVAL"
        assert result.columns[0].warnings[0].severity == "INFO"

    def test_rowid_omitted(self) -> None:
        col = _make_column(oracle_type="ROWID", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].omit is True
        assert result.columns[0].warnings[0].severity == "ERROR"

    def test_unknown_type_maps_to_text(self) -> None:
        col = _make_column(oracle_type="TIPO_INVENTADO", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "TEXT"
        assert result.columns[0].ddl_comment is not None

    def test_xmltype_maps_to_xml(self) -> None:
        col = _make_column(oracle_type="XMLTYPE", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "XML"


class TestNumberMapping:
    def setup_method(self) -> None:
        self.t = OracleToPostgreSQLTransformer()

    def test_number_no_precision_maps_to_double_precision(self) -> None:
        col = _make_column(oracle_type="NUMBER", char_length=None)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "DOUBLE PRECISION"
        assert len(result.columns[0].warnings) > 0

    def test_number_5_0_maps_to_integer(self) -> None:
        col = _make_column(oracle_type="NUMBER", char_length=None, precision=5, scale=0)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "INTEGER"

    def test_number_18_0_maps_to_bigint(self) -> None:
        col = _make_column(oracle_type="NUMBER", char_length=None, precision=18, scale=0)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "BIGINT"

    def test_number_4_0_maps_to_smallint(self) -> None:
        col = _make_column(oracle_type="NUMBER", char_length=None, precision=4, scale=0)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "SMALLINT"

    def test_number_15_2_maps_to_numeric(self) -> None:
        col = _make_column(oracle_type="NUMBER", char_length=None, precision=15, scale=2)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "NUMERIC(15,2)"

    def test_number_pk_no_precision_forced_to_integer(self) -> None:
        col = _make_column(name="ID", oracle_type="NUMBER", char_length=None, is_primary_key=True)
        table = _make_table(columns=[col], pk=["ID"])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "INTEGER"
        # No debe quedar warning de DOUBLE PRECISION
        warnings_dbl = [w for w in result.columns[0].warnings if "DOUBLE PRECISION" in w.message]
        assert len(warnings_dbl) == 0

    def test_custom_fallback(self) -> None:
        t = OracleToPostgreSQLTransformer(number_fallback="NUMERIC(38,10)")
        col = _make_column(oracle_type="NUMBER", char_length=None)
        table = _make_table(columns=[col])
        result = t.transform([table])[0]
        assert result.columns[0].target_type == "NUMERIC(38,10)"


class TestIdentityHandling:
    def setup_method(self) -> None:
        self.t = OracleToPostgreSQLTransformer()

    def test_nextval_column_becomes_serial(self) -> None:
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

    def test_pk_integer_single_becomes_serial(self) -> None:
        col = _make_column(
            name="ID",
            oracle_type="NUMBER",
            char_length=None,
            precision=9,
            scale=0,
            is_primary_key=True,
        )
        table = _make_table(columns=[col], pk=["ID"])
        result = self.t.transform([table])[0]
        assert result.columns[0].auto_increment is True
        assert result.columns[0].nullable is False

    def test_pk_number_no_precision_forced_integer_and_serial(self) -> None:
        col = _make_column(
            name="ID",
            oracle_type="NUMBER",
            char_length=None,
            is_primary_key=True,
        )
        table = _make_table(columns=[col], pk=["ID"])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "INTEGER"
        assert result.columns[0].auto_increment is True

    def test_composite_pk_no_serial(self) -> None:
        col1 = _make_column(
            name="ID1", oracle_type="NUMBER", char_length=None, precision=9, scale=0, is_primary_key=True
        )
        col2 = _make_column(
            name="ID2", oracle_type="NUMBER", char_length=None, precision=9, scale=0, is_primary_key=True
        )
        table = _make_table(columns=[col1, col2], pk=["ID1", "ID2"])
        result = self.t.transform([table])[0]
        assert result.columns[0].auto_increment is False
        assert result.columns[1].auto_increment is False

    def test_sequence_non_pk_column_gets_warning(self) -> None:
        col = _make_column(
            name="SEQ_COL",
            oracle_type="NUMBER",
            char_length=None,
            precision=10,
            scale=0,
            default="MY_SEQ.NEXTVAL",
        )
        table = _make_table(columns=[col], pk=[])
        result = self.t.transform([table])[0]
        assert result.columns[0].auto_increment is True
        assert any("no es PK" in w.message for w in result.warnings)

    def test_bigint_pk_uses_bigserial_info(self) -> None:
        col = _make_column(
            name="ID",
            oracle_type="NUMBER",
            char_length=None,
            precision=18,
            scale=0,
            is_primary_key=True,
        )
        table = _make_table(columns=[col], pk=["ID"])
        result = self.t.transform([table])[0]
        assert result.columns[0].target_type == "BIGINT"
        assert result.columns[0].auto_increment is True


class TestIdentifierTruncation:
    def setup_method(self) -> None:
        self.t = OracleToPostgreSQLTransformer()

    def test_long_table_name_truncated_to_63(self) -> None:
        long_name = "A" * 70
        col = _make_column()
        table = _make_table(name=long_name, columns=[col])
        result = self.t.transform([table])[0]
        assert len(result.name) <= MAX_POSTGRESQL_IDENTIFIER_LENGTH
        assert any(w.oracle_type == "IDENTIFIER" for w in result.warnings)

    def test_long_column_name_truncated(self) -> None:
        long_col_name = "C" * 70
        col = _make_column(name=long_col_name)
        table = _make_table(columns=[col])
        result = self.t.transform([table])[0]
        assert len(result.columns[0].name) <= MAX_POSTGRESQL_IDENTIFIER_LENGTH

    def test_short_identifier_not_truncated(self) -> None:
        col = _make_column(name="SHORT_COL")
        table = _make_table(name="MY_TABLE", columns=[col])
        result = self.t.transform([table])[0]
        assert result.name == "MY_TABLE"
        assert result.columns[0].name == "SHORT_COL"


class TestFKHandling:
    def setup_method(self) -> None:
        self.t = OracleToPostgreSQLTransformer()

    def test_external_fk_gets_warning(self) -> None:
        fk = CanonicalFK(
            name="FK_EXTERNAL",
            original_name="FK_EXTERNAL",
            columns=["COL1"],
            ref_table="OTHER_SCHEMA.OTHER_TABLE",
            ref_columns=["ID"],
            on_delete="",
            on_update="",
            is_external=True,
        )
        col = _make_column()
        table = _make_table(columns=[col], fks=[fk])
        result = self.t.transform([table])[0]
        assert any("fuera del schema" in w.message for w in result.warnings)

    def test_internal_fk_no_warning(self) -> None:
        fk = CanonicalFK(
            name="FK_INTERNAL",
            original_name="FK_INTERNAL",
            columns=["COL1"],
            ref_table="SAME_SCHEMA_TABLE",
            ref_columns=["ID"],
            on_delete="",
            on_update="",
            is_external=False,
        )
        col = _make_column()
        table = _make_table(columns=[col], fks=[fk])
        result = self.t.transform([table])[0]
        fk_warnings = [w for w in result.warnings if "FOREIGN KEY" in w.oracle_type]
        assert len(fk_warnings) == 0


class TestTransformPreservation:
    def setup_method(self) -> None:
        self.t = OracleToPostgreSQLTransformer()

    def test_original_table_not_mutated(self) -> None:
        col = _make_column(oracle_type="DATE", char_length=None)
        original_type = col.oracle_type
        table = _make_table(columns=[col])
        self.t.transform([table])
        assert col.oracle_type == original_type
        assert col.target_type == ""

    def test_multiple_tables_transformed_independently(self) -> None:
        t1 = _make_table("T1", columns=[_make_column(oracle_type="VARCHAR2", char_length=100)])
        t2 = _make_table("T2", columns=[_make_column(oracle_type="CLOB", char_length=None)])
        results = self.t.transform([t1, t2])
        assert results[0].columns[0].target_type == "VARCHAR(100)"
        assert results[1].columns[0].target_type == "TEXT"
