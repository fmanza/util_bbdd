"""Tests para los mapas de tipos SQL Server → Oracle / MariaDB / PostgreSQL."""

from __future__ import annotations

from util_bbdd.migrate._compat.type_map_sqlserver_to_mariadb import (
    SQLSERVER_TO_MARIADB,
    resolve_sqlserver_type_mariadb,
)
from util_bbdd.migrate._compat.type_map_sqlserver_to_oracle import (
    SQLSERVER_TO_ORACLE,
    resolve_sqlserver_type_oracle,
)
from util_bbdd.migrate._compat.type_map_sqlserver_to_postgresql import (
    SQLSERVER_TO_POSTGRESQL,
    resolve_sqlserver_type_postgresql,
)


# ─── SQL Server → Oracle ──────────────────────────────────────────────────────


class TestResolveSSTypeOracle:
    def test_int_maps_to_number10(self) -> None:
        m = resolve_sqlserver_type_oracle("INT")
        assert m is not None
        assert m.oracle_type == "NUMBER(10,0)"

    def test_bigint_maps_to_number19(self) -> None:
        assert resolve_sqlserver_type_oracle("BIGINT").oracle_type == "NUMBER(19,0)"  # type: ignore[union-attr]

    def test_smallint_maps_to_number5(self) -> None:
        assert resolve_sqlserver_type_oracle("SMALLINT").oracle_type == "NUMBER(5,0)"  # type: ignore[union-attr]

    def test_tinyint_maps_to_number3(self) -> None:
        m = resolve_sqlserver_type_oracle("TINYINT")
        assert m is not None
        assert m.oracle_type == "NUMBER(3,0)"

    def test_bit_maps_to_number1(self) -> None:
        assert resolve_sqlserver_type_oracle("BIT").oracle_type == "NUMBER(1,0)"  # type: ignore[union-attr]

    def test_decimal_maps_to_number(self) -> None:
        m = resolve_sqlserver_type_oracle("DECIMAL")
        assert m is not None
        assert m.oracle_type == "NUMBER"

    def test_float_maps_to_binary_double(self) -> None:
        assert resolve_sqlserver_type_oracle("FLOAT").oracle_type == "BINARY_DOUBLE"  # type: ignore[union-attr]

    def test_real_maps_to_binary_float(self) -> None:
        assert resolve_sqlserver_type_oracle("REAL").oracle_type == "BINARY_FLOAT"  # type: ignore[union-attr]

    def test_money_maps_to_number19_4(self) -> None:
        assert resolve_sqlserver_type_oracle("MONEY").oracle_type == "NUMBER(19,4)"  # type: ignore[union-attr]

    def test_varchar_maps_to_varchar2(self) -> None:
        assert resolve_sqlserver_type_oracle("VARCHAR").oracle_type == "VARCHAR2"  # type: ignore[union-attr]

    def test_nvarchar_maps_to_nvarchar2(self) -> None:
        assert resolve_sqlserver_type_oracle("NVARCHAR").oracle_type == "NVARCHAR2"  # type: ignore[union-attr]

    def test_text_maps_to_clob_with_warning(self) -> None:
        m = resolve_sqlserver_type_oracle("TEXT")
        assert m is not None
        assert m.oracle_type == "CLOB"
        assert m.warning_msg is not None

    def test_datetime_maps_to_date(self) -> None:
        assert resolve_sqlserver_type_oracle("DATETIME").oracle_type == "DATE"  # type: ignore[union-attr]

    def test_datetime2_maps_to_timestamp(self) -> None:
        assert resolve_sqlserver_type_oracle("DATETIME2").oracle_type == "TIMESTAMP"  # type: ignore[union-attr]

    def test_datetimeoffset_maps_to_timestamp_tz(self) -> None:
        m = resolve_sqlserver_type_oracle("DATETIMEOFFSET")
        assert m is not None
        assert "TIME ZONE" in m.oracle_type

    def test_uniqueidentifier_maps_to_char36(self) -> None:
        assert resolve_sqlserver_type_oracle("UNIQUEIDENTIFIER").oracle_type == "CHAR(36)"  # type: ignore[union-attr]

    def test_geography_has_error_severity(self) -> None:
        m = resolve_sqlserver_type_oracle("GEOGRAPHY")
        assert m is not None
        assert m.severity == "ERROR"

    def test_unknown_type_returns_none(self) -> None:
        assert resolve_sqlserver_type_oracle("CURSOR") is None

    def test_case_insensitive(self) -> None:
        assert resolve_sqlserver_type_oracle("int") is not None
        assert resolve_sqlserver_type_oracle("DateTime2") is not None

    def test_all_types_have_source_base_matching_key(self) -> None:
        for key, mapping in SQLSERVER_TO_ORACLE.items():
            assert mapping.source_base == key


# ─── SQL Server → MariaDB ─────────────────────────────────────────────────────


class TestResolveSSTypeMariaDB:
    def test_int_maps_to_int(self) -> None:
        assert resolve_sqlserver_type_mariadb("INT").mariadb_type == "INT"  # type: ignore[union-attr]

    def test_bigint_maps_to_bigint(self) -> None:
        assert resolve_sqlserver_type_mariadb("BIGINT").mariadb_type == "BIGINT"  # type: ignore[union-attr]

    def test_tinyint_maps_to_smallint_with_warning(self) -> None:
        m = resolve_sqlserver_type_mariadb("TINYINT")
        assert m is not None
        assert m.mariadb_type == "SMALLINT"
        assert m.warning_msg is not None
        assert m.severity == "WARNING"

    def test_bit_maps_to_tinyint1(self) -> None:
        assert resolve_sqlserver_type_mariadb("BIT").mariadb_type == "TINYINT(1)"  # type: ignore[union-attr]

    def test_float_maps_to_double(self) -> None:
        assert resolve_sqlserver_type_mariadb("FLOAT").mariadb_type == "DOUBLE"  # type: ignore[union-attr]

    def test_money_maps_to_decimal19_4(self) -> None:
        assert resolve_sqlserver_type_mariadb("MONEY").mariadb_type == "DECIMAL(19,4)"  # type: ignore[union-attr]

    def test_varchar_maps_to_varchar(self) -> None:
        assert resolve_sqlserver_type_mariadb("VARCHAR").mariadb_type == "VARCHAR"  # type: ignore[union-attr]

    def test_nvarchar_maps_to_varchar(self) -> None:
        assert resolve_sqlserver_type_mariadb("NVARCHAR").mariadb_type == "VARCHAR"  # type: ignore[union-attr]

    def test_text_maps_to_longtext_with_warning(self) -> None:
        m = resolve_sqlserver_type_mariadb("TEXT")
        assert m is not None
        assert m.mariadb_type == "LONGTEXT"
        assert m.severity == "WARNING"

    def test_datetime_maps_to_datetime(self) -> None:
        assert resolve_sqlserver_type_mariadb("DATETIME").mariadb_type == "DATETIME"  # type: ignore[union-attr]

    def test_datetime2_maps_to_datetime6(self) -> None:
        assert resolve_sqlserver_type_mariadb("DATETIME2").mariadb_type == "DATETIME(6)"  # type: ignore[union-attr]

    def test_datetimeoffset_maps_to_varchar35_with_warning(self) -> None:
        m = resolve_sqlserver_type_mariadb("DATETIMEOFFSET")
        assert m is not None
        assert m.mariadb_type == "VARCHAR(35)"
        assert m.severity == "WARNING"

    def test_uniqueidentifier_maps_to_char36(self) -> None:
        assert resolve_sqlserver_type_mariadb("UNIQUEIDENTIFIER").mariadb_type == "CHAR(36)"  # type: ignore[union-attr]

    def test_varbinary_maps_to_varbinary(self) -> None:
        assert resolve_sqlserver_type_mariadb("VARBINARY").mariadb_type == "VARBINARY"  # type: ignore[union-attr]

    def test_image_maps_to_longblob_with_warning(self) -> None:
        m = resolve_sqlserver_type_mariadb("IMAGE")
        assert m is not None
        assert m.mariadb_type == "LONGBLOB"

    def test_geography_has_error_severity(self) -> None:
        m = resolve_sqlserver_type_mariadb("GEOGRAPHY")
        assert m is not None
        assert m.severity == "ERROR"

    def test_unknown_returns_none(self) -> None:
        assert resolve_sqlserver_type_mariadb("CURSOR") is None

    def test_all_types_have_source_base_matching_key(self) -> None:
        for key, mapping in SQLSERVER_TO_MARIADB.items():
            assert mapping.source_base == key


# ─── SQL Server → PostgreSQL ──────────────────────────────────────────────────


class TestResolveSSTypePostgreSQL:
    def test_int_maps_to_integer(self) -> None:
        assert resolve_sqlserver_type_postgresql("INT").pg_type == "INTEGER"  # type: ignore[union-attr]

    def test_bigint_maps_to_bigint(self) -> None:
        assert resolve_sqlserver_type_postgresql("BIGINT").pg_type == "BIGINT"  # type: ignore[union-attr]

    def test_tinyint_maps_to_smallint(self) -> None:
        assert resolve_sqlserver_type_postgresql("TINYINT").pg_type == "SMALLINT"  # type: ignore[union-attr]

    def test_bit_maps_to_boolean(self) -> None:
        assert resolve_sqlserver_type_postgresql("BIT").pg_type == "BOOLEAN"  # type: ignore[union-attr]

    def test_float_maps_to_double_precision(self) -> None:
        assert resolve_sqlserver_type_postgresql("FLOAT").pg_type == "DOUBLE PRECISION"  # type: ignore[union-attr]

    def test_real_maps_to_real(self) -> None:
        assert resolve_sqlserver_type_postgresql("REAL").pg_type == "REAL"  # type: ignore[union-attr]

    def test_money_maps_to_numeric19_4(self) -> None:
        assert resolve_sqlserver_type_postgresql("MONEY").pg_type == "NUMERIC(19,4)"  # type: ignore[union-attr]

    def test_varchar_maps_to_varchar(self) -> None:
        assert resolve_sqlserver_type_postgresql("VARCHAR").pg_type == "VARCHAR"  # type: ignore[union-attr]

    def test_nvarchar_maps_to_varchar(self) -> None:
        assert resolve_sqlserver_type_postgresql("NVARCHAR").pg_type == "VARCHAR"  # type: ignore[union-attr]

    def test_nchar_maps_to_char(self) -> None:
        assert resolve_sqlserver_type_postgresql("NCHAR").pg_type == "CHAR"  # type: ignore[union-attr]

    def test_text_maps_to_text(self) -> None:
        assert resolve_sqlserver_type_postgresql("TEXT").pg_type == "TEXT"  # type: ignore[union-attr]

    def test_datetime_maps_to_timestamp(self) -> None:
        assert resolve_sqlserver_type_postgresql("DATETIME").pg_type == "TIMESTAMP"  # type: ignore[union-attr]

    def test_datetime2_maps_to_timestamp6(self) -> None:
        assert resolve_sqlserver_type_postgresql("DATETIME2").pg_type == "TIMESTAMP(6)"  # type: ignore[union-attr]

    def test_datetimeoffset_maps_to_timestamptz(self) -> None:
        assert resolve_sqlserver_type_postgresql("DATETIMEOFFSET").pg_type == "TIMESTAMPTZ"  # type: ignore[union-attr]

    def test_uniqueidentifier_maps_to_uuid(self) -> None:
        assert resolve_sqlserver_type_postgresql("UNIQUEIDENTIFIER").pg_type == "UUID"  # type: ignore[union-attr]

    def test_xml_maps_to_xml(self) -> None:
        assert resolve_sqlserver_type_postgresql("XML").pg_type == "XML"  # type: ignore[union-attr]

    def test_varbinary_maps_to_bytea(self) -> None:
        assert resolve_sqlserver_type_postgresql("VARBINARY").pg_type == "BYTEA"  # type: ignore[union-attr]

    def test_geography_has_error_severity(self) -> None:
        m = resolve_sqlserver_type_postgresql("GEOGRAPHY")
        assert m is not None
        assert m.severity == "ERROR"

    def test_unknown_returns_none(self) -> None:
        assert resolve_sqlserver_type_postgresql("ROWVERSION") is None

    def test_all_types_have_source_base_matching_key(self) -> None:
        for key, mapping in SQLSERVER_TO_POSTGRESQL.items():
            assert mapping.source_base == key
