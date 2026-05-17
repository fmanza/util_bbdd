"""Tests para el mapeo de tipos Oracle → MariaDB."""

from __future__ import annotations

from util_bbdd.migrate._compat.type_map import resolve_number_type, resolve_oracle_type


class TestResolveOracleType:
    def test_varchar2_resolves(self) -> None:
        m = resolve_oracle_type("VARCHAR2")
        assert m is not None
        assert m.mariadb_type == "VARCHAR"

    def test_case_insensitive(self) -> None:
        assert resolve_oracle_type("varchar2") is not None
        assert resolve_oracle_type("Varchar2") is not None

    def test_unknown_type_returns_none(self) -> None:
        assert resolve_oracle_type("NONEXISTENT_TYPE_XYZ") is None

    def test_clob_maps_to_longtext(self) -> None:
        m = resolve_oracle_type("CLOB")
        assert m is not None
        assert m.mariadb_type == "LONGTEXT"

    def test_blob_maps_to_longblob(self) -> None:
        m = resolve_oracle_type("BLOB")
        assert m is not None
        assert m.mariadb_type == "LONGBLOB"

    def test_date_has_warning(self) -> None:
        m = resolve_oracle_type("DATE")
        assert m is not None
        assert m.warning_msg is not None
        assert "hora" in m.warning_msg.lower() or "datetime" in m.warning_msg.lower()

    def test_rowid_has_empty_target(self) -> None:
        m = resolve_oracle_type("ROWID")
        assert m is not None
        assert m.mariadb_type == ""

    def test_number_has_fallback(self) -> None:
        m = resolve_oracle_type("NUMBER")
        assert m is not None
        assert m.mariadb_type == "DOUBLE"

    def test_interval_year_to_month_has_proposals(self) -> None:
        m = resolve_oracle_type("INTERVAL YEAR TO MONTH")
        assert m is not None
        assert len(m.proposals) >= 1

    def test_xmltype_maps_to_longtext(self) -> None:
        m = resolve_oracle_type("XMLTYPE")
        assert m is not None
        assert "LONGTEXT" in m.mariadb_type

    def test_timestamp_with_tz_requires_comment(self) -> None:
        m = resolve_oracle_type("TIMESTAMP WITH TIME ZONE")
        assert m is not None
        assert m.requires_ddl_comment is True

    def test_bfile_has_ddl_comment(self) -> None:
        m = resolve_oracle_type("BFILE")
        assert m is not None
        assert m.ddl_comment is not None
        assert "AVISO" in m.ddl_comment


class TestResolveNumberType:
    def test_no_precision_returns_double(self) -> None:
        mariadb_type, comment = resolve_number_type(None, None, "DOUBLE")
        assert mariadb_type == "DOUBLE"
        assert comment is not None

    def test_precision_2_returns_tinyint(self) -> None:
        mariadb_type, comment = resolve_number_type(2, 0)
        assert mariadb_type == "TINYINT"
        assert comment is None

    def test_precision_3_returns_smallint(self) -> None:
        mariadb_type, comment = resolve_number_type(3, 0)
        assert mariadb_type == "SMALLINT"
        assert comment is None

    def test_precision_4_returns_smallint(self) -> None:
        mariadb_type, _ = resolve_number_type(4, 0)
        assert mariadb_type == "SMALLINT"

    def test_precision_9_returns_int(self) -> None:
        mariadb_type, _ = resolve_number_type(9, 0)
        assert mariadb_type == "INT"

    def test_precision_18_returns_bigint(self) -> None:
        mariadb_type, _ = resolve_number_type(18, 0)
        assert mariadb_type == "BIGINT"

    def test_precision_above_18_returns_decimal(self) -> None:
        mariadb_type, _ = resolve_number_type(20, 0)
        assert "DECIMAL" in mariadb_type
        assert "20" in mariadb_type

    def test_precision_with_scale_returns_decimal(self) -> None:
        mariadb_type, comment = resolve_number_type(10, 2)
        assert mariadb_type == "DECIMAL(10,2)"
        assert comment is None

    def test_custom_fallback(self) -> None:
        mariadb_type, _ = resolve_number_type(None, None, "DECIMAL(18,4)")
        assert mariadb_type == "DECIMAL(18,4)"

    def test_none_scale_treated_as_zero(self) -> None:
        # precision=4, scale=None → scale se trata como 0 → SMALLINT (p<=4)
        mariadb_type, _ = resolve_number_type(4, None)
        assert mariadb_type == "SMALLINT"
