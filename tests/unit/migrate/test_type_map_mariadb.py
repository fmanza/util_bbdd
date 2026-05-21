"""Tests para los mapas de tipos MariaDB → Oracle / SQL Server / PostgreSQL."""

from __future__ import annotations

from util_bbdd.migrate._compat.type_map_mariadb_to_oracle import (
    MARIADB_TO_ORACLE,
    resolve_mariadb_type_oracle,
)
from util_bbdd.migrate._compat.type_map_mariadb_to_postgresql import (
    MARIADB_TO_POSTGRESQL,
    resolve_mariadb_type_postgresql,
)
from util_bbdd.migrate._compat.type_map_mariadb_to_sqlserver import (
    MARIADB_TO_SQLSERVER,
    resolve_mariadb_type_sqlserver,
)

# ─── MariaDB → Oracle ─────────────────────────────────────────────────────────


class TestResolveMariadbTypeOracle:
    def test_int_maps_to_number(self) -> None:
        m = resolve_mariadb_type_oracle("INT")
        assert m is not None
        assert "NUMBER" in m.oracle_type

    def test_bigint_maps_to_number19(self) -> None:
        m = resolve_mariadb_type_oracle("BIGINT")
        assert m is not None
        assert m.oracle_type == "NUMBER(19,0)"

    def test_varchar_maps_to_varchar2(self) -> None:
        m = resolve_mariadb_type_oracle("VARCHAR")
        assert m is not None
        assert m.oracle_type == "VARCHAR2"

    def test_text_maps_to_clob(self) -> None:
        m = resolve_mariadb_type_oracle("TEXT")
        assert m is not None
        assert m.oracle_type == "CLOB"

    def test_longtext_maps_to_clob(self) -> None:
        assert resolve_mariadb_type_oracle("LONGTEXT").oracle_type == "CLOB"  # type: ignore[union-attr]

    def test_blob_maps_to_blob(self) -> None:
        assert resolve_mariadb_type_oracle("BLOB").oracle_type == "BLOB"  # type: ignore[union-attr]

    def test_datetime_maps_to_date(self) -> None:
        assert resolve_mariadb_type_oracle("DATETIME").oracle_type == "DATE"  # type: ignore[union-attr]

    def test_timestamp_maps_to_timestamp(self) -> None:
        m = resolve_mariadb_type_oracle("TIMESTAMP")
        assert m is not None
        assert m.oracle_type == "TIMESTAMP"
        assert m.warning_msg is not None

    def test_date_has_info_warning(self) -> None:
        m = resolve_mariadb_type_oracle("DATE")
        assert m is not None
        assert m.severity == "INFO"

    def test_time_has_warning(self) -> None:
        m = resolve_mariadb_type_oracle("TIME")
        assert m is not None
        assert m.severity == "WARNING"
        assert len(m.proposals) > 0

    def test_json_maps_to_clob_with_warning(self) -> None:
        m = resolve_mariadb_type_oracle("JSON")
        assert m is not None
        assert m.oracle_type == "CLOB"
        assert m.severity == "WARNING"

    def test_enum_has_warning(self) -> None:
        m = resolve_mariadb_type_oracle("ENUM")
        assert m is not None
        assert m.severity == "WARNING"
        assert m.requires_ddl_comment

    def test_bool_maps_to_number1(self) -> None:
        m = resolve_mariadb_type_oracle("BOOL")
        assert m is not None
        assert m.oracle_type == "NUMBER(1,0)"

    def test_tinyint_maps_to_number3(self) -> None:
        assert resolve_mariadb_type_oracle("TINYINT").oracle_type == "NUMBER(3,0)"  # type: ignore[union-attr]

    def test_decimal_maps_to_number(self) -> None:
        m = resolve_mariadb_type_oracle("DECIMAL")
        assert m is not None
        assert m.oracle_type == "NUMBER"  # params resueltos dinámicamente

    def test_geometry_has_error_severity(self) -> None:
        m = resolve_mariadb_type_oracle("GEOMETRY")
        assert m is not None
        assert m.severity == "ERROR"

    def test_unknown_type_returns_none(self) -> None:
        assert resolve_mariadb_type_oracle("UNKNOWNTYPE") is None

    def test_case_insensitive(self) -> None:
        assert resolve_mariadb_type_oracle("varchar") == resolve_mariadb_type_oracle("VARCHAR")

    def test_all_keys_resolvable(self) -> None:
        for key in MARIADB_TO_ORACLE:
            assert resolve_mariadb_type_oracle(key) is not None

    def test_uuid_maps_to_char36(self) -> None:
        m = resolve_mariadb_type_oracle("UUID")
        assert m is not None
        assert m.oracle_type == "CHAR(36)"


# ─── MariaDB → SQL Server ─────────────────────────────────────────────────────


class TestResolveMariadbTypeSQLServer:
    def test_int_maps_to_int(self) -> None:
        m = resolve_mariadb_type_sqlserver("INT")
        assert m is not None
        assert m.sqlserver_type == "INT"

    def test_bigint_maps_to_bigint(self) -> None:
        assert resolve_mariadb_type_sqlserver("BIGINT").sqlserver_type == "BIGINT"  # type: ignore[union-attr]

    def test_varchar_maps_to_nvarchar(self) -> None:
        m = resolve_mariadb_type_sqlserver("VARCHAR")
        assert m is not None
        assert m.sqlserver_type == "NVARCHAR"

    def test_char_maps_to_nchar(self) -> None:
        assert resolve_mariadb_type_sqlserver("CHAR").sqlserver_type == "NCHAR"  # type: ignore[union-attr]

    def test_text_maps_to_nvarchar_max(self) -> None:
        assert resolve_mariadb_type_sqlserver("TEXT").sqlserver_type == "NVARCHAR(MAX)"  # type: ignore[union-attr]

    def test_datetime_maps_to_datetime2(self) -> None:
        assert resolve_mariadb_type_sqlserver("DATETIME").sqlserver_type == "DATETIME2"  # type: ignore[union-attr]

    def test_bool_maps_to_bit(self) -> None:
        assert resolve_mariadb_type_sqlserver("BOOL").sqlserver_type == "BIT"  # type: ignore[union-attr]

    def test_tinyint_has_warning(self) -> None:
        m = resolve_mariadb_type_sqlserver("TINYINT")
        assert m is not None
        assert m.severity == "WARNING"  # signed vs unsigned

    def test_blob_maps_to_varbinary_max(self) -> None:
        assert resolve_mariadb_type_sqlserver("BLOB").sqlserver_type == "VARBINARY(MAX)"  # type: ignore[union-attr]

    def test_json_has_warning(self) -> None:
        m = resolve_mariadb_type_sqlserver("JSON")
        assert m is not None
        assert m.severity == "WARNING"

    def test_uuid_maps_to_uniqueidentifier(self) -> None:
        assert resolve_mariadb_type_sqlserver("UUID").sqlserver_type == "UNIQUEIDENTIFIER"  # type: ignore[union-attr]

    def test_mediumint_maps_to_int(self) -> None:
        assert resolve_mariadb_type_sqlserver("MEDIUMINT").sqlserver_type == "INT"  # type: ignore[union-attr]

    def test_unknown_returns_none(self) -> None:
        assert resolve_mariadb_type_sqlserver("UNKNOWNTYPE") is None

    def test_all_keys_resolvable(self) -> None:
        for key in MARIADB_TO_SQLSERVER:
            assert resolve_mariadb_type_sqlserver(key) is not None


# ─── MariaDB → PostgreSQL ─────────────────────────────────────────────────────


class TestResolveMariadbTypePostgreSQL:
    def test_int_maps_to_integer(self) -> None:
        m = resolve_mariadb_type_postgresql("INT")
        assert m is not None
        assert m.pg_type == "INTEGER"

    def test_bigint_maps_to_bigint(self) -> None:
        assert resolve_mariadb_type_postgresql("BIGINT").pg_type == "BIGINT"  # type: ignore[union-attr]

    def test_varchar_maps_to_varchar(self) -> None:
        assert resolve_mariadb_type_postgresql("VARCHAR").pg_type == "VARCHAR"  # type: ignore[union-attr]

    def test_text_maps_to_text(self) -> None:
        assert resolve_mariadb_type_postgresql("TEXT").pg_type == "TEXT"  # type: ignore[union-attr]

    def test_datetime_maps_to_timestamp(self) -> None:
        assert resolve_mariadb_type_postgresql("DATETIME").pg_type == "TIMESTAMP"  # type: ignore[union-attr]

    def test_timestamp_maps_to_timestamptz(self) -> None:
        assert resolve_mariadb_type_postgresql("TIMESTAMP").pg_type == "TIMESTAMPTZ"  # type: ignore[union-attr]

    def test_bool_maps_to_boolean(self) -> None:
        assert resolve_mariadb_type_postgresql("BOOL").pg_type == "BOOLEAN"  # type: ignore[union-attr]

    def test_json_maps_to_jsonb(self) -> None:
        m = resolve_mariadb_type_postgresql("JSON")
        assert m is not None
        assert m.pg_type == "JSONB"

    def test_blob_maps_to_bytea(self) -> None:
        assert resolve_mariadb_type_postgresql("BLOB").pg_type == "BYTEA"  # type: ignore[union-attr]

    def test_decimal_maps_to_numeric(self) -> None:
        assert resolve_mariadb_type_postgresql("DECIMAL").pg_type == "NUMERIC"  # type: ignore[union-attr]

    def test_enum_maps_to_text_with_warning(self) -> None:
        m = resolve_mariadb_type_postgresql("ENUM")
        assert m is not None
        assert m.pg_type == "TEXT"
        assert m.severity == "WARNING"

    def test_uuid_maps_to_uuid(self) -> None:
        assert resolve_mariadb_type_postgresql("UUID").pg_type == "UUID"  # type: ignore[union-attr]

    def test_unknown_returns_none(self) -> None:
        assert resolve_mariadb_type_postgresql("UNKNOWNTYPE") is None

    def test_all_keys_resolvable(self) -> None:
        for key in MARIADB_TO_POSTGRESQL:
            assert resolve_mariadb_type_postgresql(key) is not None

    def test_tinyint_maps_to_smallint(self) -> None:
        assert resolve_mariadb_type_postgresql("TINYINT").pg_type == "SMALLINT"  # type: ignore[union-attr]

    def test_double_maps_to_double_precision(self) -> None:
        assert resolve_mariadb_type_postgresql("DOUBLE").pg_type == "DOUBLE PRECISION"  # type: ignore[union-attr]
