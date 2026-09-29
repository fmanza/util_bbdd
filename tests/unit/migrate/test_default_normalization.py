"""H4: los defaults del motor origen se normalizan antes de traducirse al destino.

Cada emitter solo reconocía la sintaxis de un dialecto (Oracle o MariaDB); los casts de PostgreSQL
(``'x'::character varying``), los paréntesis de SQL Server (``((0))``, ``(N'x')``) o ``SYSDATE`` de Oracle llegaban
tal cual y el DDL no era válido en el destino.
"""

from __future__ import annotations

import pytest

from util_bbdd.migrate import MariaDBDDLEmitter, MySQLDDLEmitter, OracleDDLEmitter
from util_bbdd.migrate._compat.default_normalizer import normalize_default
from util_bbdd.migrate.ir.models import CanonicalColumn, CanonicalTable


@pytest.mark.parametrize(
    ("source", "raw", "expected"),
    [
        # PostgreSQL
        ("postgresql", "'n/a'::character varying", "'n/a'"),
        ("postgresql", "'2020-01-01'::date", "'2020-01-01'"),
        ("postgresql", "'-1'::integer", "-1"),
        ("postgresql", "(0)::numeric", "0"),
        ("postgresql", "now()", "CURRENT_TIMESTAMP"),
        ("postgresql", "CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP"),
        ("postgresql", "LOCALTIMESTAMP", "CURRENT_TIMESTAMP"),
        ("postgresql", "CURRENT_DATE", "CURRENT_DATE"),
        ("postgresql", "true", "1"),
        ("postgresql", "false", "0"),
        ("postgresql", "NULL::character varying", "NULL"),
        ("postgresql", "nextval('t_id_seq'::regclass)", "nextval('t_id_seq'::regclass)"),
        ("postgresql", "gen_random_uuid()", "gen_random_uuid()"),
        # SQL Server
        ("sqlserver", "((0))", "0"),
        ("sqlserver", "((1.5))", "1.5"),
        ("sqlserver", "(N'x')", "'x'"),
        ("sqlserver", "('it''s')", "'it''s'"),
        ("sqlserver", "(getdate())", "CURRENT_TIMESTAMP"),
        ("sqlserver", "(sysdatetime())", "CURRENT_TIMESTAMP"),
        ("sqlserver", "(NULL)", "NULL"),
        ("sqlserver", "(newid())", "newid()"),
        # Oracle
        ("oracle", "SYSDATE", "CURRENT_TIMESTAMP"),
        ("oracle", "sysdate ", "CURRENT_TIMESTAMP"),
        ("oracle", "SYSTIMESTAMP", "CURRENT_TIMESTAMP"),
        ("oracle", "'x'", "'x'"),
        ("oracle", "MY_SEQ.NEXTVAL", "MY_SEQ.NEXTVAL"),
        # MariaDB / MySQL
        ("mariadb", "current_timestamp()", "CURRENT_TIMESTAMP"),
        ("mariadb", "current_timestamp(6)", "CURRENT_TIMESTAMP(6)"),
        ("mariadb", "curdate()", "CURRENT_DATE"),
        ("mariadb", "'x'", "'x'"),
        ("mariadb", "NULL", "NULL"),
        ("mysql", "CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP"),
        ("mysql", "'sin nombre'", "'sin nombre'"),
        # Comunes
        ("postgresql", None, None),
        ("sqlserver", "  ", None),
    ],
)
def test_normalize_default(source: str, raw: str | None, expected: str | None) -> None:
    assert normalize_default(source, raw) == expected


def _table(target_type: str, default: str, nullable: bool = False) -> CanonicalTable:
    return CanonicalTable(
        name="t",
        original_name="t",
        schema="s",
        columns=[CanonicalColumn("c", "c", target_type, target_type, nullable, default, "", 1)],
        primary_key=[],
        indexes=[],
        foreign_keys=[],
        comment="",
        warnings=[],
    )


class TestOracleEmitterDefaults:
    def test_default_goes_before_not_null(self) -> None:
        ddl = OracleDDLEmitter().emit([_table("VARCHAR2(10)", "'x'")])
        assert "DEFAULT 'x' NOT NULL" in ddl

    def test_quoted_literal_is_not_quoted_again(self) -> None:
        ddl = OracleDDLEmitter().emit([_table("VARCHAR2(20)", "'sin nombre'", nullable=True)])
        assert "DEFAULT 'sin nombre'" in ddl
        assert "'''" not in ddl


@pytest.mark.parametrize("emitter_cls", [MariaDBDDLEmitter, MySQLDDLEmitter])
class TestMySQLFamilyTimestampPrecision:
    def test_current_timestamp_gets_column_precision(self, emitter_cls: type) -> None:
        ddl = emitter_cls(charset="utf8mb4", collation="utf8mb4_bin").emit([_table("DATETIME(6)", "CURRENT_TIMESTAMP")])
        assert "DEFAULT CURRENT_TIMESTAMP(6)" in ddl

    def test_current_timestamp_without_precision_is_unchanged(self, emitter_cls: type) -> None:
        ddl = emitter_cls(charset="utf8mb4", collation="utf8mb4_bin").emit([_table("DATETIME", "CURRENT_TIMESTAMP")])
        assert "DEFAULT CURRENT_TIMESTAMP\n" in ddl or "DEFAULT CURRENT_TIMESTAMP" in ddl.splitlines()[1]
        assert "CURRENT_TIMESTAMP(" not in ddl


@pytest.mark.parametrize(("default", "expected"), [("1", "DEFAULT TRUE"), ("0", "DEFAULT FALSE")])
def test_postgresql_boolean_default_uses_boolean_literal(default: str, expected: str) -> None:
    """``BIT DEFAULT 1`` de SQL Server llega como ``1``: PostgreSQL no acepta un entero como default de BOOLEAN."""
    from util_bbdd.migrate import PostgreSQLDDLEmitter

    ddl = PostgreSQLDDLEmitter().emit([_table("BOOLEAN", default, nullable=True)])
    assert expected in ddl
