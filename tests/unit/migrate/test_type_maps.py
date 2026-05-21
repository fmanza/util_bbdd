"""Tests unitarios para migrate/_compat/type_map_*.

Cubre todas las funciones de resolución de tipos entre motores.
Son tests de función pura — sin base de datos real.
"""

from __future__ import annotations

import pytest

# ── Oracle → MariaDB ─────────────────────────────────────────────────────────
from util_bbdd.migrate._compat.type_map import (
    ORACLE_TO_MARIADB,
    TypeMapping,
    resolve_number_type,
    resolve_oracle_type,
)

# ── MariaDB → * ───────────────────────────────────────────────────────────────
from util_bbdd.migrate._compat.type_map_mariadb_to_oracle import (
    MARIADB_TO_ORACLE,
)
from util_bbdd.migrate._compat.type_map_mariadb_to_postgresql import (
    MARIADB_TO_POSTGRESQL,
)
from util_bbdd.migrate._compat.type_map_mariadb_to_sqlserver import (
    MARIADB_TO_SQLSERVER,
)

# ── Oracle → PostgreSQL ───────────────────────────────────────────────────────
from util_bbdd.migrate._compat.type_map_postgresql import (
    ORACLE_TO_POSTGRESQL,
    resolve_number_type_postgresql,
    resolve_oracle_type_postgresql,
)

# ── PostgreSQL → * ────────────────────────────────────────────────────────────
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

# ── Oracle → SQL Server ───────────────────────────────────────────────────────
from util_bbdd.migrate._compat.type_map_sqlserver import (
    ORACLE_TO_SQLSERVER,
)

# ── SQL Server → * ────────────────────────────────────────────────────────────
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

# ─────────────────────────────────────────────────────────────────────────────
# Oracle → MariaDB
# ─────────────────────────────────────────────────────────────────────────────


class TestResolveOracleTypeMariaDB:
    def test_varchar2_maps_to_varchar(self) -> None:
        result = resolve_oracle_type("VARCHAR2")
        assert result is not None
        assert result.mariadb_type == "VARCHAR"

    def test_clob_maps_to_longtext(self) -> None:
        result = resolve_oracle_type("CLOB")
        assert result is not None
        assert result.mariadb_type == "LONGTEXT"

    def test_blob_maps_to_longblob(self) -> None:
        result = resolve_oracle_type("BLOB")
        assert result is not None
        assert result.mariadb_type == "LONGBLOB"

    def test_date_maps_to_datetime_with_warning(self) -> None:
        result = resolve_oracle_type("DATE")
        assert result is not None
        assert result.mariadb_type == "DATETIME"
        assert result.warning_msg is not None
        assert result.requires_ddl_comment is True

    def test_timestamp_tz_has_warning_severity(self) -> None:
        result = resolve_oracle_type("TIMESTAMP WITH TIME ZONE")
        assert result is not None
        assert result.severity == "WARNING"
        assert result.requires_ddl_comment is True

    def test_rowid_maps_to_empty_with_error_severity(self) -> None:
        result = resolve_oracle_type("ROWID")
        assert result is not None
        assert result.mariadb_type == ""
        assert result.severity == "ERROR"

    def test_urowid_error_severity(self) -> None:
        result = resolve_oracle_type("UROWID")
        assert result is not None
        assert result.severity == "ERROR"

    def test_unknown_type_returns_none(self) -> None:
        assert resolve_oracle_type("NOT_A_REAL_TYPE") is None

    def test_case_insensitive_lookup(self) -> None:
        upper = resolve_oracle_type("VARCHAR2")
        lower = resolve_oracle_type("varchar2")
        mixed = resolve_oracle_type("Varchar2")
        assert upper == lower == mixed

    def test_empty_string_returns_none(self) -> None:
        assert resolve_oracle_type("") is None

    def test_all_keys_resolve(self) -> None:
        for key in ORACLE_TO_MARIADB:
            result = resolve_oracle_type(key)
            assert result is not None, f"Clave '{key}' no resuelve"

    def test_result_is_typemapping(self) -> None:
        result = resolve_oracle_type("INTEGER")
        assert isinstance(result, TypeMapping)


class TestResolveNumberTypeMariaDB:
    def test_none_precision_returns_fallback_double(self) -> None:
        mariadb_type, comment = resolve_number_type(None, None)
        assert mariadb_type == "DOUBLE"
        assert comment is not None
        assert "DOUBLE" in comment

    def test_scale_positive_returns_decimal(self) -> None:
        mariadb_type, comment = resolve_number_type(10, 2)
        assert mariadb_type == "DECIMAL(10,2)"
        assert comment is None

    def test_precision_2_scale_0_returns_tinyint(self) -> None:
        mariadb_type, comment = resolve_number_type(2, 0)
        assert mariadb_type == "TINYINT"

    def test_precision_4_scale_0_returns_smallint(self) -> None:
        mariadb_type, comment = resolve_number_type(4, 0)
        assert mariadb_type == "SMALLINT"

    def test_precision_9_scale_0_returns_int(self) -> None:
        mariadb_type, comment = resolve_number_type(9, 0)
        assert mariadb_type == "INT"

    def test_precision_18_scale_0_returns_bigint(self) -> None:
        mariadb_type, comment = resolve_number_type(18, 0)
        assert mariadb_type == "BIGINT"

    def test_precision_38_scale_0_returns_decimal(self) -> None:
        mariadb_type, comment = resolve_number_type(38, 0)
        assert mariadb_type == "DECIMAL(38,0)"

    def test_custom_fallback_used(self) -> None:
        mariadb_type, _ = resolve_number_type(None, None, fallback="DECIMAL")
        assert mariadb_type == "DECIMAL"

    def test_none_scale_treated_as_zero(self) -> None:
        # precision=10, scale=None → effective_scale=0 → precision > 9 → BIGINT
        mariadb_type, _ = resolve_number_type(10, None)
        assert mariadb_type == "BIGINT"


# ─────────────────────────────────────────────────────────────────────────────
# Oracle → PostgreSQL
# ─────────────────────────────────────────────────────────────────────────────


class TestResolveOracleTypePostgreSQL:
    def test_varchar2_maps_to_varchar(self) -> None:
        result = resolve_oracle_type_postgresql("VARCHAR2")
        assert result is not None
        assert result.pg_type == "VARCHAR"

    def test_clob_maps_to_text(self) -> None:
        result = resolve_oracle_type_postgresql("CLOB")
        assert result is not None
        assert result.pg_type == "TEXT"

    def test_blob_maps_to_bytea(self) -> None:
        result = resolve_oracle_type_postgresql("BLOB")
        assert result is not None
        assert result.pg_type == "BYTEA"

    def test_date_maps_to_timestamp_with_warning(self) -> None:
        result = resolve_oracle_type_postgresql("DATE")
        assert result is not None
        assert result.pg_type == "TIMESTAMP"
        assert result.warning_msg is not None

    def test_timestamp_tz_maps_to_timestamptz(self) -> None:
        result = resolve_oracle_type_postgresql("TIMESTAMP WITH TIME ZONE")
        assert result is not None
        assert result.pg_type == "TIMESTAMPTZ"

    def test_interval_year_to_month_maps_to_interval(self) -> None:
        result = resolve_oracle_type_postgresql("INTERVAL YEAR TO MONTH")
        assert result is not None
        assert result.pg_type == "INTERVAL"

    def test_xmltype_maps_to_xml(self) -> None:
        result = resolve_oracle_type_postgresql("XMLTYPE")
        assert result is not None
        assert result.pg_type == "XML"

    def test_rowid_error_severity(self) -> None:
        result = resolve_oracle_type_postgresql("ROWID")
        assert result is not None
        assert result.severity == "ERROR"
        assert result.pg_type == ""

    def test_unknown_type_returns_none(self) -> None:
        assert resolve_oracle_type_postgresql("NOT_REAL") is None

    def test_case_insensitive(self) -> None:
        assert resolve_oracle_type_postgresql("clob") == resolve_oracle_type_postgresql("CLOB")

    def test_all_keys_resolve(self) -> None:
        for key in ORACLE_TO_POSTGRESQL:
            result = resolve_oracle_type_postgresql(key)
            assert result is not None, f"Clave '{key}' no resuelve"


class TestResolveNumberTypePostgreSQL:
    def test_none_precision_returns_double_precision(self) -> None:
        pg_type, comment = resolve_number_type_postgresql(None, None)
        assert pg_type == "DOUBLE PRECISION"
        assert comment is not None

    def test_scale_positive_returns_numeric(self) -> None:
        pg_type, comment = resolve_number_type_postgresql(10, 2)
        assert pg_type == "NUMERIC(10,2)"
        assert comment is None

    def test_precision_4_scale_0_returns_smallint(self) -> None:
        pg_type, _ = resolve_number_type_postgresql(4, 0)
        assert pg_type == "SMALLINT"

    def test_precision_9_scale_0_returns_integer(self) -> None:
        pg_type, _ = resolve_number_type_postgresql(9, 0)
        assert pg_type == "INTEGER"

    def test_precision_18_scale_0_returns_bigint(self) -> None:
        pg_type, _ = resolve_number_type_postgresql(18, 0)
        assert pg_type == "BIGINT"

    def test_precision_38_scale_0_returns_numeric(self) -> None:
        pg_type, _ = resolve_number_type_postgresql(38, 0)
        assert pg_type == "NUMERIC(38,0)"


# ─────────────────────────────────────────────────────────────────────────────
# SQL Server → MariaDB
# ─────────────────────────────────────────────────────────────────────────────


class TestResolveSSToMariaDB:
    def test_int_maps_to_int(self) -> None:
        result = resolve_sqlserver_type_mariadb("INT")
        assert result is not None
        assert result.mariadb_type == "INT"

    def test_nvarchar_maps_to_varchar(self) -> None:
        result = resolve_sqlserver_type_mariadb("NVARCHAR")
        assert result is not None
        assert result.mariadb_type == "VARCHAR"

    def test_unknown_returns_none(self) -> None:
        assert resolve_sqlserver_type_mariadb("UNKNOWN_SS_TYPE") is None

    def test_case_insensitive(self) -> None:
        assert resolve_sqlserver_type_mariadb("int") == resolve_sqlserver_type_mariadb("INT")

    def test_all_keys_resolve(self) -> None:
        for key in SQLSERVER_TO_MARIADB:
            result = resolve_sqlserver_type_mariadb(key)
            assert result is not None, f"Clave '{key}' no resuelve"


# ─────────────────────────────────────────────────────────────────────────────
# SQL Server → Oracle
# ─────────────────────────────────────────────────────────────────────────────


class TestResolveSSToOracle:
    def test_int_maps_to_number(self) -> None:
        result = resolve_sqlserver_type_oracle("INT")
        assert result is not None
        assert "NUMBER" in result.oracle_type

    def test_unknown_returns_none(self) -> None:
        assert resolve_sqlserver_type_oracle("NOT_REAL_SS_TYPE") is None

    def test_all_keys_resolve(self) -> None:
        for key in SQLSERVER_TO_ORACLE:
            result = resolve_sqlserver_type_oracle(key)
            assert result is not None, f"Clave '{key}' no resuelve"


# ─────────────────────────────────────────────────────────────────────────────
# SQL Server → PostgreSQL
# ─────────────────────────────────────────────────────────────────────────────


class TestResolveSSToPostgreSQL:
    def test_int_maps_to_integer(self) -> None:
        result = resolve_sqlserver_type_postgresql("INT")
        assert result is not None
        assert result.pg_type == "INTEGER"

    def test_unknown_returns_none(self) -> None:
        assert resolve_sqlserver_type_postgresql("FAKE_TYPE") is None

    def test_all_keys_resolve(self) -> None:
        for key in SQLSERVER_TO_POSTGRESQL:
            result = resolve_sqlserver_type_postgresql(key)
            assert result is not None, f"Clave '{key}' no resuelve"


# ─────────────────────────────────────────────────────────────────────────────
# PostgreSQL → MariaDB
# ─────────────────────────────────────────────────────────────────────────────


class TestResolvePGToMariaDB:
    def test_integer_maps_to_int(self) -> None:
        result = resolve_postgresql_type_mariadb("INTEGER")
        assert result is not None
        assert result.mariadb_type == "INT"

    def test_text_maps_correctly(self) -> None:
        result = resolve_postgresql_type_mariadb("TEXT")
        assert result is not None
        assert result.mariadb_type in ("LONGTEXT", "TEXT", "MEDIUMTEXT")

    def test_unknown_returns_none(self) -> None:
        assert resolve_postgresql_type_mariadb("NOT_PG_TYPE") is None

    def test_case_insensitive(self) -> None:
        assert resolve_postgresql_type_mariadb("integer") == resolve_postgresql_type_mariadb("INTEGER")

    def test_all_keys_resolve(self) -> None:
        for key in POSTGRESQL_TO_MARIADB:
            result = resolve_postgresql_type_mariadb(key)
            assert result is not None, f"Clave '{key}' no resuelve"


# ─────────────────────────────────────────────────────────────────────────────
# PostgreSQL → Oracle
# ─────────────────────────────────────────────────────────────────────────────


class TestResolvePGToOracle:
    def test_integer_maps_to_number(self) -> None:
        result = resolve_postgresql_type_oracle("INTEGER")
        assert result is not None
        assert "NUMBER" in result.oracle_type

    def test_text_maps_to_clob(self) -> None:
        result = resolve_postgresql_type_oracle("TEXT")
        assert result is not None
        assert "CLOB" in result.oracle_type

    def test_unknown_returns_none(self) -> None:
        assert resolve_postgresql_type_oracle("NOT_PG_TYPE") is None

    def test_all_keys_resolve(self) -> None:
        for key in POSTGRESQL_TO_ORACLE:
            result = resolve_postgresql_type_oracle(key)
            assert result is not None, f"Clave '{key}' no resuelve"


# ─────────────────────────────────────────────────────────────────────────────
# PostgreSQL → SQL Server
# ─────────────────────────────────────────────────────────────────────────────


class TestResolvePGToSQLServer:
    def test_integer_maps_to_int(self) -> None:
        result = resolve_postgresql_type_sqlserver("INTEGER")
        assert result is not None
        assert result.ss_type == "INT"

    def test_unknown_returns_none(self) -> None:
        assert resolve_postgresql_type_sqlserver("FAKE_PG_TYPE") is None

    def test_all_keys_resolve(self) -> None:
        for key in POSTGRESQL_TO_SQLSERVER:
            result = resolve_postgresql_type_sqlserver(key)
            assert result is not None, f"Clave '{key}' no resuelve"


# ─────────────────────────────────────────────────────────────────────────────
# Completitud y consistencia de diccionarios
# ─────────────────────────────────────────────────────────────────────────────


class TestTypeMapsCompleteness:
    """Valida invariantes estructurales de los mapeos."""

    @pytest.mark.parametrize(
        "mapping_dict, dest_field",
        [
            (ORACLE_TO_MARIADB, "mariadb_type"),
            (ORACLE_TO_POSTGRESQL, "pg_type"),
            (ORACLE_TO_SQLSERVER, "sqlserver_type"),
            (SQLSERVER_TO_MARIADB, "mariadb_type"),
            (SQLSERVER_TO_ORACLE, "oracle_type"),
            (SQLSERVER_TO_POSTGRESQL, "pg_type"),
            (POSTGRESQL_TO_MARIADB, "mariadb_type"),
            (POSTGRESQL_TO_ORACLE, "oracle_type"),
            (POSTGRESQL_TO_SQLSERVER, "ss_type"),
            (MARIADB_TO_ORACLE, "oracle_type"),
            (MARIADB_TO_POSTGRESQL, "pg_type"),
            (MARIADB_TO_SQLSERVER, "sqlserver_type"),
        ],
    )
    def test_no_null_destination_type(self, mapping_dict: dict, dest_field: str) -> None:
        for key, entry in mapping_dict.items():
            dest = getattr(entry, dest_field, None)
            assert dest is not None, f"Clave '{key}': {dest_field} es None"

    @pytest.mark.parametrize(
        "mapping_dict",
        [
            ORACLE_TO_MARIADB,
            ORACLE_TO_POSTGRESQL,
            ORACLE_TO_SQLSERVER,
            SQLSERVER_TO_MARIADB,
            SQLSERVER_TO_ORACLE,
            SQLSERVER_TO_POSTGRESQL,
            POSTGRESQL_TO_MARIADB,
            POSTGRESQL_TO_ORACLE,
            POSTGRESQL_TO_SQLSERVER,
            MARIADB_TO_ORACLE,
            MARIADB_TO_POSTGRESQL,
            MARIADB_TO_SQLSERVER,
        ],
    )
    def test_keys_are_uppercase(self, mapping_dict: dict) -> None:
        for key in mapping_dict:
            assert key == key.upper(), f"Clave '{key}' no está en MAYÚSCULAS"

    @pytest.mark.parametrize(
        "mapping_dict",
        [
            ORACLE_TO_MARIADB,
            ORACLE_TO_POSTGRESQL,
            ORACLE_TO_SQLSERVER,
            SQLSERVER_TO_MARIADB,
            SQLSERVER_TO_ORACLE,
            SQLSERVER_TO_POSTGRESQL,
            POSTGRESQL_TO_MARIADB,
            POSTGRESQL_TO_ORACLE,
            POSTGRESQL_TO_SQLSERVER,
            MARIADB_TO_ORACLE,
            MARIADB_TO_POSTGRESQL,
            MARIADB_TO_SQLSERVER,
        ],
    )
    def test_valid_severity_levels(self, mapping_dict: dict) -> None:
        valid = {"INFO", "WARNING", "ERROR"}
        for key, entry in mapping_dict.items():
            assert entry.severity in valid, f"Clave '{key}': severity '{entry.severity}' no válida"

    @pytest.mark.parametrize(
        "mapping_dict",
        [
            ORACLE_TO_MARIADB,
            ORACLE_TO_POSTGRESQL,
            ORACLE_TO_SQLSERVER,
            SQLSERVER_TO_MARIADB,
            SQLSERVER_TO_ORACLE,
            SQLSERVER_TO_POSTGRESQL,
            POSTGRESQL_TO_MARIADB,
            POSTGRESQL_TO_ORACLE,
            POSTGRESQL_TO_SQLSERVER,
            MARIADB_TO_ORACLE,
            MARIADB_TO_POSTGRESQL,
            MARIADB_TO_SQLSERVER,
        ],
    )
    def test_ddl_comment_present_when_required(self, mapping_dict: dict) -> None:
        for key, entry in mapping_dict.items():
            if entry.requires_ddl_comment:
                assert entry.ddl_comment is not None, (
                    f"Clave '{key}': requires_ddl_comment=True pero ddl_comment es None"
                )
