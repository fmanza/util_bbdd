"""Tests para los mapas de tipos PostgreSQL → Oracle / MariaDB / SQL Server."""

from __future__ import annotations

from util_bbdd.migrate._compat.type_map_postgresql_to_mariadb import (
    POSTGRESQL_TO_MARIADB,
    resolve_postgresql_type_mariadb,
)
from util_bbdd.migrate._compat.type_map_postgresql_to_oracle import (
    POSTGRESQL_TO_ORACLE,
    resolve_postgresql_type_oracle,
)
from util_bbdd.migrate._compat.type_map_postgresql_to_sqlserver import (
    POSTGRESQL_TO_SQLSERVER,
    resolve_postgresql_type_sqlserver,
)

# ─── PostgreSQL → Oracle ──────────────────────────────────────────────────────


class TestResolvePostgreSQLTypeOracle:
    def test_integer_maps_to_number10(self) -> None:
        m = resolve_postgresql_type_oracle("INTEGER")
        assert m is not None
        assert m.oracle_type == "NUMBER(10,0)"

    def test_bigint_maps_to_number19(self) -> None:
        assert resolve_postgresql_type_oracle("BIGINT").oracle_type == "NUMBER(19,0)"  # type: ignore[union-attr]

    def test_smallint_maps_to_number5(self) -> None:
        assert resolve_postgresql_type_oracle("SMALLINT").oracle_type == "NUMBER(5,0)"  # type: ignore[union-attr]

    def test_numeric_maps_to_number(self) -> None:
        m = resolve_postgresql_type_oracle("NUMERIC")
        assert m is not None
        assert m.oracle_type == "NUMBER"

    def test_real_maps_to_binary_float(self) -> None:
        assert resolve_postgresql_type_oracle("REAL").oracle_type == "BINARY_FLOAT"  # type: ignore[union-attr]

    def test_double_precision_maps_to_binary_double(self) -> None:
        assert resolve_postgresql_type_oracle("DOUBLE PRECISION").oracle_type == "BINARY_DOUBLE"  # type: ignore[union-attr]

    def test_character_varying_maps_to_varchar2(self) -> None:
        m = resolve_postgresql_type_oracle("CHARACTER VARYING")
        assert m is not None
        assert m.oracle_type == "VARCHAR2"

    def test_character_maps_to_char(self) -> None:
        assert resolve_postgresql_type_oracle("CHARACTER").oracle_type == "CHAR"  # type: ignore[union-attr]

    def test_text_maps_to_clob_with_warning(self) -> None:
        m = resolve_postgresql_type_oracle("TEXT")
        assert m is not None
        assert m.oracle_type == "CLOB"
        assert m.warning_msg is not None

    def test_boolean_maps_to_number1_with_warning(self) -> None:
        m = resolve_postgresql_type_oracle("BOOLEAN")
        assert m is not None
        assert m.oracle_type == "NUMBER(1,0)"
        assert m.warning_msg is not None

    def test_date_maps_to_date(self) -> None:
        assert resolve_postgresql_type_oracle("DATE").oracle_type == "DATE"  # type: ignore[union-attr]

    def test_timestamp_without_tz_maps_to_timestamp(self) -> None:
        m = resolve_postgresql_type_oracle("TIMESTAMP WITHOUT TIME ZONE")
        assert m is not None
        assert m.oracle_type == "TIMESTAMP"

    def test_timestamp_with_tz_maps_to_timestamp_tz(self) -> None:
        m = resolve_postgresql_type_oracle("TIMESTAMP WITH TIME ZONE")
        assert m is not None
        assert "TIME ZONE" in m.oracle_type

    def test_time_without_tz_maps_to_varchar15(self) -> None:
        m = resolve_postgresql_type_oracle("TIME WITHOUT TIME ZONE")
        assert m is not None
        assert m.oracle_type == "VARCHAR2(15)"

    def test_uuid_maps_to_char36(self) -> None:
        assert resolve_postgresql_type_oracle("UUID").oracle_type == "CHAR(36)"  # type: ignore[union-attr]

    def test_bytea_maps_to_blob(self) -> None:
        assert resolve_postgresql_type_oracle("BYTEA").oracle_type == "BLOB"  # type: ignore[union-attr]

    def test_json_maps_to_clob_with_warning(self) -> None:
        m = resolve_postgresql_type_oracle("JSON")
        assert m is not None
        assert m.oracle_type == "CLOB"
        assert m.warning_msg is not None

    def test_jsonb_maps_to_clob_with_warning(self) -> None:
        m = resolve_postgresql_type_oracle("JSONB")
        assert m is not None
        assert m.oracle_type == "CLOB"

    def test_xml_maps_to_clob_with_warning(self) -> None:
        m = resolve_postgresql_type_oracle("XML")
        assert m is not None
        assert m.oracle_type == "CLOB"

    def test_unknown_type_returns_none(self) -> None:
        assert resolve_postgresql_type_oracle("NONEXISTENT_TYPE_XYZ") is None

    def test_case_insensitive(self) -> None:
        m_lower = resolve_postgresql_type_oracle("integer")
        m_upper = resolve_postgresql_type_oracle("INTEGER")
        assert m_lower == m_upper

    def test_inet_maps_to_varchar45(self) -> None:
        m = resolve_postgresql_type_oracle("INET")
        assert m is not None
        assert "45" in m.oracle_type

    def test_tsvector_is_error_severity(self) -> None:
        m = resolve_postgresql_type_oracle("TSVECTOR")
        assert m is not None
        assert m.severity == "ERROR"

    def test_multiword_key_lookup(self) -> None:
        # Verifica que claves multi-palabra funcionan correctamente
        assert resolve_postgresql_type_oracle("TIME WITH TIME ZONE") is not None
        assert resolve_postgresql_type_oracle("TIMESTAMP WITH TIME ZONE") is not None
        assert resolve_postgresql_type_oracle("BIT VARYING") is not None


# ─── PostgreSQL → MariaDB ─────────────────────────────────────────────────────


class TestResolvePostgreSQLTypeMariaDB:
    def test_integer_maps_to_int(self) -> None:
        assert resolve_postgresql_type_mariadb("INTEGER").mariadb_type == "INT"  # type: ignore[union-attr]

    def test_bigint_maps_to_bigint(self) -> None:
        assert resolve_postgresql_type_mariadb("BIGINT").mariadb_type == "BIGINT"  # type: ignore[union-attr]

    def test_smallint_maps_to_smallint(self) -> None:
        assert resolve_postgresql_type_mariadb("SMALLINT").mariadb_type == "SMALLINT"  # type: ignore[union-attr]

    def test_numeric_maps_to_decimal(self) -> None:
        assert resolve_postgresql_type_mariadb("NUMERIC").mariadb_type == "DECIMAL"  # type: ignore[union-attr]

    def test_real_maps_to_float(self) -> None:
        assert resolve_postgresql_type_mariadb("REAL").mariadb_type == "FLOAT"  # type: ignore[union-attr]

    def test_double_precision_maps_to_double(self) -> None:
        assert resolve_postgresql_type_mariadb("DOUBLE PRECISION").mariadb_type == "DOUBLE"  # type: ignore[union-attr]

    def test_character_varying_maps_to_varchar(self) -> None:
        assert resolve_postgresql_type_mariadb("CHARACTER VARYING").mariadb_type == "VARCHAR"  # type: ignore[union-attr]

    def test_text_maps_to_longtext(self) -> None:
        assert resolve_postgresql_type_mariadb("TEXT").mariadb_type == "LONGTEXT"  # type: ignore[union-attr]

    def test_boolean_maps_to_tinyint1(self) -> None:
        assert resolve_postgresql_type_mariadb("BOOLEAN").mariadb_type == "TINYINT(1)"  # type: ignore[union-attr]

    def test_date_maps_to_date(self) -> None:
        assert resolve_postgresql_type_mariadb("DATE").mariadb_type == "DATE"  # type: ignore[union-attr]

    def test_timestamp_without_tz_maps_to_datetime6(self) -> None:
        m = resolve_postgresql_type_mariadb("TIMESTAMP WITHOUT TIME ZONE")
        assert m is not None
        assert m.mariadb_type == "DATETIME(6)"

    def test_timestamp_with_tz_maps_to_datetime6_with_warning(self) -> None:
        m = resolve_postgresql_type_mariadb("TIMESTAMP WITH TIME ZONE")
        assert m is not None
        assert m.mariadb_type == "DATETIME(6)"
        assert m.warning_msg is not None

    def test_uuid_maps_to_char36(self) -> None:
        assert resolve_postgresql_type_mariadb("UUID").mariadb_type == "CHAR(36)"  # type: ignore[union-attr]

    def test_bytea_maps_to_longblob(self) -> None:
        assert resolve_postgresql_type_mariadb("BYTEA").mariadb_type == "LONGBLOB"  # type: ignore[union-attr]

    def test_json_maps_to_longtext_with_warning(self) -> None:
        m = resolve_postgresql_type_mariadb("JSON")
        assert m is not None
        assert m.mariadb_type == "LONGTEXT"
        assert m.warning_msg is not None

    def test_bit_maps_to_bit(self) -> None:
        assert resolve_postgresql_type_mariadb("BIT").mariadb_type == "BIT"  # type: ignore[union-attr]

    def test_unknown_type_returns_none(self) -> None:
        assert resolve_postgresql_type_mariadb("NONEXISTENT_XYZ") is None

    def test_case_insensitive(self) -> None:
        assert resolve_postgresql_type_mariadb("boolean") == resolve_postgresql_type_mariadb("BOOLEAN")

    def test_tsvector_is_error_severity(self) -> None:
        m = resolve_postgresql_type_mariadb("TSVECTOR")
        assert m is not None
        assert m.severity == "ERROR"

    def test_multiword_key_lookup(self) -> None:
        assert resolve_postgresql_type_mariadb("TIME WITHOUT TIME ZONE") is not None
        assert resolve_postgresql_type_mariadb("TIME WITH TIME ZONE") is not None


# ─── PostgreSQL → SQL Server ──────────────────────────────────────────────────


class TestResolvePostgreSQLTypeSQLServer:
    def test_integer_maps_to_int(self) -> None:
        assert resolve_postgresql_type_sqlserver("INTEGER").ss_type == "INT"  # type: ignore[union-attr]

    def test_bigint_maps_to_bigint(self) -> None:
        assert resolve_postgresql_type_sqlserver("BIGINT").ss_type == "BIGINT"  # type: ignore[union-attr]

    def test_smallint_maps_to_smallint(self) -> None:
        assert resolve_postgresql_type_sqlserver("SMALLINT").ss_type == "SMALLINT"  # type: ignore[union-attr]

    def test_numeric_maps_to_numeric(self) -> None:
        assert resolve_postgresql_type_sqlserver("NUMERIC").ss_type == "NUMERIC"  # type: ignore[union-attr]

    def test_real_maps_to_real(self) -> None:
        assert resolve_postgresql_type_sqlserver("REAL").ss_type == "REAL"  # type: ignore[union-attr]

    def test_double_precision_maps_to_float(self) -> None:
        assert resolve_postgresql_type_sqlserver("DOUBLE PRECISION").ss_type == "FLOAT"  # type: ignore[union-attr]

    def test_character_varying_maps_to_nvarchar(self) -> None:
        assert resolve_postgresql_type_sqlserver("CHARACTER VARYING").ss_type == "NVARCHAR"  # type: ignore[union-attr]

    def test_text_maps_to_nvarchar_max(self) -> None:
        assert resolve_postgresql_type_sqlserver("TEXT").ss_type == "NVARCHAR(MAX)"  # type: ignore[union-attr]

    def test_boolean_maps_to_bit(self) -> None:
        assert resolve_postgresql_type_sqlserver("BOOLEAN").ss_type == "BIT"  # type: ignore[union-attr]

    def test_date_maps_to_date(self) -> None:
        assert resolve_postgresql_type_sqlserver("DATE").ss_type == "DATE"  # type: ignore[union-attr]

    def test_timestamp_without_tz_maps_to_datetime2(self) -> None:
        m = resolve_postgresql_type_sqlserver("TIMESTAMP WITHOUT TIME ZONE")
        assert m is not None
        assert m.ss_type == "DATETIME2(6)"

    def test_timestamp_with_tz_maps_to_datetimeoffset(self) -> None:
        m = resolve_postgresql_type_sqlserver("TIMESTAMP WITH TIME ZONE")
        assert m is not None
        assert m.ss_type == "DATETIMEOFFSET(6)"

    def test_uuid_maps_to_uniqueidentifier(self) -> None:
        assert resolve_postgresql_type_sqlserver("UUID").ss_type == "UNIQUEIDENTIFIER"  # type: ignore[union-attr]

    def test_bytea_maps_to_varbinary_max(self) -> None:
        assert resolve_postgresql_type_sqlserver("BYTEA").ss_type == "VARBINARY(MAX)"  # type: ignore[union-attr]

    def test_xml_maps_to_xml_native(self) -> None:
        m = resolve_postgresql_type_sqlserver("XML")
        assert m is not None
        assert m.ss_type == "XML"

    def test_json_maps_to_nvarchar_max_with_warning(self) -> None:
        m = resolve_postgresql_type_sqlserver("JSON")
        assert m is not None
        assert m.ss_type == "NVARCHAR(MAX)"
        assert m.warning_msg is not None

    def test_money_maps_to_money(self) -> None:
        assert resolve_postgresql_type_sqlserver("MONEY").ss_type == "MONEY"  # type: ignore[union-attr]

    def test_unknown_type_returns_none(self) -> None:
        assert resolve_postgresql_type_sqlserver("NONEXISTENT_XYZ") is None

    def test_case_insensitive(self) -> None:
        assert resolve_postgresql_type_sqlserver("integer") == resolve_postgresql_type_sqlserver("INTEGER")

    def test_tsvector_is_error_severity(self) -> None:
        m = resolve_postgresql_type_sqlserver("TSVECTOR")
        assert m is not None
        assert m.severity == "ERROR"

    def test_multiword_key_lookup(self) -> None:
        assert resolve_postgresql_type_sqlserver("CHARACTER VARYING") is not None
        assert resolve_postgresql_type_sqlserver("TIMESTAMP WITH TIME ZONE") is not None
        assert resolve_postgresql_type_sqlserver("BIT VARYING") is not None


# ── Coverage de dicts ─────────────────────────────────────────────────────────


class TestDictCoverage:
    """Verifica que los dicts tienen los tipos clave cubiertos."""

    def test_oracle_dict_covers_core_types(self) -> None:
        core = {
            "INTEGER",
            "BIGINT",
            "CHARACTER VARYING",
            "TEXT",
            "BOOLEAN",
            "NUMERIC",
            "DATE",
            "TIMESTAMP WITHOUT TIME ZONE",
            "UUID",
            "BYTEA",
        }
        for t in core:
            assert t in POSTGRESQL_TO_ORACLE, f"Falta {t!r} en POSTGRESQL_TO_ORACLE"

    def test_mariadb_dict_covers_core_types(self) -> None:
        core = {
            "INTEGER",
            "BIGINT",
            "CHARACTER VARYING",
            "TEXT",
            "BOOLEAN",
            "NUMERIC",
            "DATE",
            "TIMESTAMP WITHOUT TIME ZONE",
            "UUID",
            "BYTEA",
        }
        for t in core:
            assert t in POSTGRESQL_TO_MARIADB, f"Falta {t!r} en POSTGRESQL_TO_MARIADB"

    def test_sqlserver_dict_covers_core_types(self) -> None:
        core = {
            "INTEGER",
            "BIGINT",
            "CHARACTER VARYING",
            "TEXT",
            "BOOLEAN",
            "NUMERIC",
            "DATE",
            "TIMESTAMP WITHOUT TIME ZONE",
            "UUID",
            "BYTEA",
        }
        for t in core:
            assert t in POSTGRESQL_TO_SQLSERVER, f"Falta {t!r} en POSTGRESQL_TO_SQLSERVER"
