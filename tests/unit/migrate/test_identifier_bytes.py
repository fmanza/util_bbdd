"""A6 (fix 2026-09-29): el límite de identificadores de PostgreSQL (63) y Oracle (30) se mide en bytes UTF-8.

Antes se contaban caracteres: ``"zzvw_" + "ñ" * 29 + "a"`` (35 caracteres, 64 bytes) pasaba sin truncar y PostgreSQL
lo recortaba en silencio a 63 bytes; dos nombres que solo diferían al final colisionaban («relation already exists»).
MariaDB, MySQL y SQL Server cuentan caracteres y no cambian.
"""

from __future__ import annotations

from util_bbdd.migrate._compat.identifier_rules import (
    MAX_MARIADB_IDENTIFIER_LENGTH,
    MAX_ORACLE_IDENTIFIER_LENGTH,
    MAX_POSTGRESQL_IDENTIFIER_LENGTH,
    MAX_SQLSERVER_IDENTIFIER_LENGTH,
    ByteLimit,
    check_identifier,
    truncate_identifier,
)
from util_bbdd.migrate.transformers.mariadb_to_postgresql import MariaDBToPostgreSQLTransformer
from util_bbdd.migrate.transformers.sqlserver_to_oracle import SQLServerToOracleTransformer

LONG_A = "zzvw_" + "ñ" * 29 + "a"
LONG_B = "zzvw_" + "ñ" * 29 + "b"


def test_postgresql_and_oracle_limits_are_bytes() -> None:
    assert isinstance(MAX_POSTGRESQL_IDENTIFIER_LENGTH, ByteLimit)
    assert isinstance(MAX_ORACLE_IDENTIFIER_LENGTH, ByteLimit)
    assert not isinstance(MAX_MARIADB_IDENTIFIER_LENGTH, ByteLimit)
    assert not isinstance(MAX_SQLSERVER_IDENTIFIER_LENGTH, ByteLimit)
    assert MAX_POSTGRESQL_IDENTIFIER_LENGTH == 63 and MAX_ORACLE_IDENTIFIER_LENGTH == 30


def test_names_over_63_bytes_are_truncated_and_stay_distinct() -> None:
    a, truncated_a = truncate_identifier(LONG_A, MAX_POSTGRESQL_IDENTIFIER_LENGTH)
    b, truncated_b = truncate_identifier(LONG_B, MAX_POSTGRESQL_IDENTIFIER_LENGTH)
    assert truncated_a and truncated_b and a != b
    assert len(a.encode("utf-8")) <= 63 and len(b.encode("utf-8")) <= 63


def test_cut_never_splits_a_multibyte_character() -> None:
    name, _ = truncate_identifier("ñ" * 40, MAX_ORACLE_IDENTIFIER_LENGTH)
    name.encode("utf-8")  # no lanza: UTF-8 válido
    assert len(name.encode("utf-8")) <= 30 and name.startswith("ñ") and "�" not in name


def test_ascii_names_behave_as_before() -> None:
    assert truncate_identifier("a" * 63, MAX_POSTGRESQL_IDENTIFIER_LENGTH) == ("a" * 63, False)
    name, truncated = truncate_identifier("a" * 64, MAX_POSTGRESQL_IDENTIFIER_LENGTH)
    assert truncated and len(name) == 63


def test_character_limited_engines_do_not_change() -> None:
    assert truncate_identifier(LONG_A, MAX_MARIADB_IDENTIFIER_LENGTH) == (LONG_A, False)
    assert truncate_identifier(LONG_A, MAX_SQLSERVER_IDENTIFIER_LENGTH) == (LONG_A, False)


def test_warning_reports_bytes() -> None:
    _, message = check_identifier(LONG_A, MAX_POSTGRESQL_IDENTIFIER_LENGTH)
    assert message is not None and "64 bytes" in message


def test_transformers_keep_the_byte_limit() -> None:
    assert isinstance(MariaDBToPostgreSQLTransformer.MAX_IDENTIFIER_LENGTH, ByteLimit)
    assert isinstance(SQLServerToOracleTransformer.MAX_IDENTIFIER_LENGTH, ByteLimit)
