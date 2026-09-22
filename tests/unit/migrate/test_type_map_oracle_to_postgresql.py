"""Tests para el mapeo de tipos Oracle → PostgreSQL."""

from __future__ import annotations

from util_bbdd.migrate._compat.type_map_oracle_to_postgresql import (
    ORACLE_TO_POSTGRESQL,
    resolve_number_type_postgresql,
    resolve_oracle_type_postgresql,
)


class TestResolveOracleTypePostgreSQL:
    def test_varchar2_maps_to_varchar(self) -> None:
        m = resolve_oracle_type_postgresql("VARCHAR2")
        assert m is not None
        assert m.pg_type == "VARCHAR"

    def test_nvarchar2_maps_to_varchar_with_info(self) -> None:
        m = resolve_oracle_type_postgresql("NVARCHAR2")
        assert m is not None
        assert m.pg_type == "VARCHAR"
        assert m.severity == "INFO"
        assert m.warning_msg is not None

    def test_char_maps_to_char(self) -> None:
        m = resolve_oracle_type_postgresql("CHAR")
        assert m is not None
        assert m.pg_type == "CHAR"

    def test_nchar_maps_to_char_with_info(self) -> None:
        m = resolve_oracle_type_postgresql("NCHAR")
        assert m is not None
        assert m.pg_type == "CHAR"
        assert m.severity == "INFO"

    def test_integer_maps_to_integer(self) -> None:
        m = resolve_oracle_type_postgresql("INTEGER")
        assert m is not None
        assert m.pg_type == "INTEGER"

    def test_int_maps_to_integer(self) -> None:
        m = resolve_oracle_type_postgresql("INT")
        assert m is not None
        assert m.pg_type == "INTEGER"

    def test_smallint_maps_to_smallint(self) -> None:
        m = resolve_oracle_type_postgresql("SMALLINT")
        assert m is not None
        assert m.pg_type == "SMALLINT"

    def test_number_no_precision_maps_to_double_precision(self) -> None:
        m = resolve_oracle_type_postgresql("NUMBER")
        assert m is not None
        assert m.pg_type == "DOUBLE PRECISION"
        assert m.severity == "WARNING"
        assert m.requires_ddl_comment is True

    def test_date_maps_to_timestamp_with_warning(self) -> None:
        m = resolve_oracle_type_postgresql("DATE")
        assert m is not None
        assert m.pg_type == "TIMESTAMP"
        assert m.severity == "WARNING"
        assert m.requires_ddl_comment is True

    def test_timestamp_maps_to_timestamp(self) -> None:
        m = resolve_oracle_type_postgresql("TIMESTAMP")
        assert m is not None
        assert m.pg_type == "TIMESTAMP"

    def test_timestamp_with_tz_maps_to_timestamptz(self) -> None:
        m = resolve_oracle_type_postgresql("TIMESTAMP WITH TIME ZONE")
        assert m is not None
        assert m.pg_type == "TIMESTAMPTZ"
        assert m.severity == "INFO"

    def test_timestamp_with_local_tz_maps_to_timestamp_with_warning(self) -> None:
        m = resolve_oracle_type_postgresql("TIMESTAMP WITH LOCAL TIME ZONE")
        assert m is not None
        assert m.pg_type == "TIMESTAMP"
        assert m.severity == "WARNING"

    def test_clob_maps_to_text(self) -> None:
        m = resolve_oracle_type_postgresql("CLOB")
        assert m is not None
        assert m.pg_type == "TEXT"

    def test_nclob_maps_to_text(self) -> None:
        m = resolve_oracle_type_postgresql("NCLOB")
        assert m is not None
        assert m.pg_type == "TEXT"

    def test_blob_maps_to_bytea(self) -> None:
        m = resolve_oracle_type_postgresql("BLOB")
        assert m is not None
        assert m.pg_type == "BYTEA"

    def test_long_raw_maps_to_bytea(self) -> None:
        m = resolve_oracle_type_postgresql("LONG RAW")
        assert m is not None
        assert m.pg_type == "BYTEA"

    def test_raw_maps_to_bytea(self) -> None:
        m = resolve_oracle_type_postgresql("RAW")
        assert m is not None
        assert m.pg_type == "BYTEA"

    def test_long_maps_to_text_with_info(self) -> None:
        m = resolve_oracle_type_postgresql("LONG")
        assert m is not None
        assert m.pg_type == "TEXT"
        assert m.severity == "INFO"

    def test_xmltype_maps_to_xml(self) -> None:
        m = resolve_oracle_type_postgresql("XMLTYPE")
        assert m is not None
        assert m.pg_type == "XML"
        assert len(m.proposals) == 2

    def test_bfile_maps_to_text_with_warning(self) -> None:
        m = resolve_oracle_type_postgresql("BFILE")
        assert m is not None
        assert m.pg_type == "TEXT"
        assert m.severity == "WARNING"
        assert len(m.proposals) >= 1

    def test_rowid_empty_type_for_omit(self) -> None:
        m = resolve_oracle_type_postgresql("ROWID")
        assert m is not None
        assert m.pg_type == ""
        assert m.severity == "ERROR"

    def test_urowid_empty_type_for_omit(self) -> None:
        m = resolve_oracle_type_postgresql("UROWID")
        assert m is not None
        assert m.pg_type == ""
        assert m.severity == "ERROR"

    def test_interval_year_to_month_maps_to_interval_natively(self) -> None:
        m = resolve_oracle_type_postgresql("INTERVAL YEAR TO MONTH")
        assert m is not None
        assert m.pg_type == "INTERVAL"
        assert m.severity == "INFO"
        # PostgreSQL soporta INTERVAL nativo — sin proposals ni workarounds
        assert len(m.proposals) == 0

    def test_interval_day_to_second_maps_to_interval_natively(self) -> None:
        m = resolve_oracle_type_postgresql("INTERVAL DAY TO SECOND")
        assert m is not None
        assert m.pg_type == "INTERVAL"
        assert m.severity == "INFO"
        assert len(m.proposals) == 0

    def test_float_maps_to_double_precision(self) -> None:
        m = resolve_oracle_type_postgresql("FLOAT")
        assert m is not None
        assert m.pg_type == "DOUBLE PRECISION"

    def test_binary_double_maps_to_double_precision(self) -> None:
        m = resolve_oracle_type_postgresql("BINARY_DOUBLE")
        assert m is not None
        assert m.pg_type == "DOUBLE PRECISION"

    def test_binary_float_maps_to_real(self) -> None:
        m = resolve_oracle_type_postgresql("BINARY_FLOAT")
        assert m is not None
        assert m.pg_type == "REAL"

    def test_case_insensitive_lookup(self) -> None:
        m = resolve_oracle_type_postgresql("varchar2")
        assert m is not None
        assert m.pg_type == "VARCHAR"

    def test_unknown_type_returns_none(self) -> None:
        assert resolve_oracle_type_postgresql("COMPLETAMENTE_DESCONOCIDO") is None

    def test_all_entries_have_oracle_base(self) -> None:
        for key, mapping in ORACLE_TO_POSTGRESQL.items():
            assert mapping.oracle_base == key

    def test_decimal_maps_to_numeric(self) -> None:
        m = resolve_oracle_type_postgresql("DECIMAL")
        assert m is not None
        assert m.pg_type == "NUMERIC"

    def test_numeric_maps_to_numeric(self) -> None:
        m = resolve_oracle_type_postgresql("NUMERIC")
        assert m is not None
        assert m.pg_type == "NUMERIC"


class TestResolveNumberTypePostgreSQL:
    def test_no_precision_returns_double_precision_with_comment(self) -> None:
        t, comment = resolve_number_type_postgresql(None, None)
        assert t == "DOUBLE PRECISION"
        assert comment is not None
        assert "DOUBLE PRECISION" in comment

    def test_no_precision_custom_fallback(self) -> None:
        t, comment = resolve_number_type_postgresql(None, None, fallback="NUMERIC(38,10)")
        assert t == "NUMERIC(38,10)"
        assert comment is not None

    def test_number_1_0_returns_smallint(self) -> None:
        t, comment = resolve_number_type_postgresql(1, 0)
        assert t == "SMALLINT"
        assert comment is None

    def test_number_4_0_returns_smallint(self) -> None:
        t, comment = resolve_number_type_postgresql(4, 0)
        assert t == "SMALLINT"
        assert comment is None

    def test_number_5_0_returns_integer(self) -> None:
        t, comment = resolve_number_type_postgresql(5, 0)
        assert t == "INTEGER"
        assert comment is None

    def test_number_9_0_returns_integer(self) -> None:
        t, comment = resolve_number_type_postgresql(9, 0)
        assert t == "INTEGER"
        assert comment is None

    def test_number_10_0_returns_bigint(self) -> None:
        t, comment = resolve_number_type_postgresql(10, 0)
        assert t == "BIGINT"
        assert comment is None

    def test_number_18_0_returns_bigint(self) -> None:
        t, comment = resolve_number_type_postgresql(18, 0)
        assert t == "BIGINT"
        assert comment is None

    def test_number_19_0_returns_numeric(self) -> None:
        t, comment = resolve_number_type_postgresql(19, 0)
        assert t == "NUMERIC(19,0)"
        assert comment is None

    def test_number_15_2_returns_numeric(self) -> None:
        t, comment = resolve_number_type_postgresql(15, 2)
        assert t == "NUMERIC(15,2)"
        assert comment is None

    def test_scale_none_treated_as_zero(self) -> None:
        t, _ = resolve_number_type_postgresql(9, None)
        assert t == "INTEGER"

    def test_precision_with_positive_scale(self) -> None:
        t, comment = resolve_number_type_postgresql(10, 4)
        assert t == "NUMERIC(10,4)"
        assert comment is None

    def test_number_2_0_returns_smallint(self) -> None:
        t, comment = resolve_number_type_postgresql(2, 0)
        assert t == "SMALLINT"
        assert comment is None
