"""Tests para el mapeo de tipos Oracle → SQL Server."""

from __future__ import annotations

from util_bbdd.migrate._compat.type_map_sqlserver import (
    ORACLE_TO_SQLSERVER,
    resolve_number_type_sqlserver,
    resolve_oracle_type_sqlserver,
)


class TestResolveOracleTypeSQLServer:
    def test_varchar2_maps_to_nvarchar(self) -> None:
        m = resolve_oracle_type_sqlserver("VARCHAR2")
        assert m is not None
        assert m.sqlserver_type == "NVARCHAR"

    def test_nvarchar2_maps_to_nvarchar(self) -> None:
        m = resolve_oracle_type_sqlserver("NVARCHAR2")
        assert m is not None
        assert m.sqlserver_type == "NVARCHAR"

    def test_char_maps_to_nchar(self) -> None:
        m = resolve_oracle_type_sqlserver("CHAR")
        assert m is not None
        assert m.sqlserver_type == "NCHAR"

    def test_integer_maps_to_int(self) -> None:
        m = resolve_oracle_type_sqlserver("INTEGER")
        assert m is not None
        assert m.sqlserver_type == "INT"

    def test_number_no_precision_maps_to_float(self) -> None:
        m = resolve_oracle_type_sqlserver("NUMBER")
        assert m is not None
        assert m.sqlserver_type == "FLOAT"
        assert m.severity == "WARNING"
        assert m.requires_ddl_comment is True

    def test_date_maps_to_datetime2_with_warning(self) -> None:
        m = resolve_oracle_type_sqlserver("DATE")
        assert m is not None
        assert m.sqlserver_type == "DATETIME2"
        assert m.severity == "WARNING"
        assert m.requires_ddl_comment is True

    def test_timestamp_maps_to_datetime2(self) -> None:
        m = resolve_oracle_type_sqlserver("TIMESTAMP")
        assert m is not None
        assert m.sqlserver_type == "DATETIME2"

    def test_timestamp_with_tz_maps_to_datetimeoffset(self) -> None:
        m = resolve_oracle_type_sqlserver("TIMESTAMP WITH TIME ZONE")
        assert m is not None
        assert m.sqlserver_type == "DATETIMEOFFSET"

    def test_clob_maps_to_nvarchar_max(self) -> None:
        m = resolve_oracle_type_sqlserver("CLOB")
        assert m is not None
        assert m.sqlserver_type == "NVARCHAR(MAX)"

    def test_blob_maps_to_varbinary_max(self) -> None:
        m = resolve_oracle_type_sqlserver("BLOB")
        assert m is not None
        assert m.sqlserver_type == "VARBINARY(MAX)"

    def test_xmltype_maps_to_xml(self) -> None:
        m = resolve_oracle_type_sqlserver("XMLTYPE")
        assert m is not None
        assert m.sqlserver_type == "XML"
        assert len(m.proposals) == 2

    def test_rowid_empty_type_for_omit(self) -> None:
        m = resolve_oracle_type_sqlserver("ROWID")
        assert m is not None
        assert m.sqlserver_type == ""
        assert m.severity == "ERROR"

    def test_urowid_empty_type_for_omit(self) -> None:
        m = resolve_oracle_type_sqlserver("UROWID")
        assert m is not None
        assert m.sqlserver_type == ""
        assert m.severity == "ERROR"

    def test_case_insensitive_lookup(self) -> None:
        m = resolve_oracle_type_sqlserver("varchar2")
        assert m is not None
        assert m.sqlserver_type == "NVARCHAR"

    def test_unknown_type_returns_none(self) -> None:
        assert resolve_oracle_type_sqlserver("COMPLETAMENTE_DESCONOCIDO") is None

    def test_binary_double_maps_to_float53(self) -> None:
        m = resolve_oracle_type_sqlserver("BINARY_DOUBLE")
        assert m is not None
        assert m.sqlserver_type == "FLOAT(53)"

    def test_all_entries_have_oracle_base(self) -> None:
        for key, mapping in ORACLE_TO_SQLSERVER.items():
            assert mapping.oracle_base == key

    def test_interval_year_to_month_has_proposals(self) -> None:
        m = resolve_oracle_type_sqlserver("INTERVAL YEAR TO MONTH")
        assert m is not None
        assert len(m.proposals) >= 2
        assert m.severity == "WARNING"


class TestResolveNumberTypeSQLServer:
    def test_no_precision_returns_float_with_comment(self) -> None:
        t, comment = resolve_number_type_sqlserver(None, None)
        assert t == "FLOAT"
        assert comment is not None
        assert "FLOAT" in comment

    def test_no_precision_custom_fallback(self) -> None:
        t, comment = resolve_number_type_sqlserver(None, None, fallback="NUMERIC(38,10)")
        assert t == "NUMERIC(38,10)"
        assert comment is not None

    def test_number_1_0_returns_tinyint_with_unsigned_warning(self) -> None:
        """CMP-01 (AUDIT_CODE 2026-09-22): NUMBER(1,0) Oracle es con signo (-9..9), TINYINT
        SQL Server es unsigned (0-255); sin aviso, un valor negativo desborda silenciosamente."""
        t, comment = resolve_number_type_sqlserver(1, 0)
        assert t == "TINYINT"
        assert comment is not None
        assert "unsigned" in comment
        assert "negativos" in comment

    def test_number_2_0_returns_tinyint_with_unsigned_warning(self) -> None:
        t, comment = resolve_number_type_sqlserver(2, 0)
        assert t == "TINYINT"
        assert comment is not None
        assert "unsigned" in comment
        assert "negativos" in comment

    def test_number_3_0_returns_smallint(self) -> None:
        t, comment = resolve_number_type_sqlserver(3, 0)
        assert t == "SMALLINT"
        assert comment is None

    def test_number_4_0_returns_smallint(self) -> None:
        t, comment = resolve_number_type_sqlserver(4, 0)
        assert t == "SMALLINT"
        assert comment is None

    def test_number_5_0_returns_int(self) -> None:
        t, comment = resolve_number_type_sqlserver(5, 0)
        assert t == "INT"
        assert comment is None

    def test_number_9_0_returns_int(self) -> None:
        t, comment = resolve_number_type_sqlserver(9, 0)
        assert t == "INT"
        assert comment is None

    def test_number_10_0_returns_bigint(self) -> None:
        t, comment = resolve_number_type_sqlserver(10, 0)
        assert t == "BIGINT"
        assert comment is None

    def test_number_18_0_returns_bigint(self) -> None:
        t, comment = resolve_number_type_sqlserver(18, 0)
        assert t == "BIGINT"
        assert comment is None

    def test_number_19_0_returns_numeric(self) -> None:
        t, comment = resolve_number_type_sqlserver(19, 0)
        assert t == "NUMERIC(19,0)"
        assert comment is None

    def test_number_15_2_returns_numeric(self) -> None:
        t, comment = resolve_number_type_sqlserver(15, 2)
        assert t == "NUMERIC(15,2)"
        assert comment is None

    def test_scale_none_treated_as_zero(self) -> None:
        t, _ = resolve_number_type_sqlserver(9, None)
        assert t == "INT"

    def test_precision_with_positive_scale(self) -> None:
        t, comment = resolve_number_type_sqlserver(10, 4)
        assert t == "NUMERIC(10,4)"
        assert comment is None
