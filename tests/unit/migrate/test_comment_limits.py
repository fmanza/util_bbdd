"""C1 (auditoría 0.21.0): comentarios recortados al límite del motor destino, con aviso ``COMMENT``."""

from __future__ import annotations

from util_bbdd.migrate.emitters._comment_limits import (
    MYSQL_COLUMN_COMMENT,
    MYSQL_TABLE_COMMENT,
    ORACLE_COMMENT,
    SQLSERVER_COMMENT,
    fit_comment,
)
from util_bbdd.migrate.emitters.mysql import MySQLDDLEmitter
from util_bbdd.migrate.emitters.oracle import OracleDDLEmitter
from util_bbdd.migrate.emitters.postgresql import PostgreSQLDDLEmitter
from util_bbdd.migrate.emitters.sqlserver import SQLServerDDLEmitter
from util_bbdd.migrate.ir.models import CanonicalColumn, CanonicalTable, MigrationWarning


def _table(comment: str, column_comment: str) -> CanonicalTable:
    col = CanonicalColumn(
        name="c",
        original_name="c",
        source_type="text",
        target_type="VARCHAR(10)",
        nullable=True,
        default=None,
        comment=column_comment,
        ordinal=1,
    )
    return CanonicalTable("t", "t", "s", [col], [], [], [], comment, [])


class TestFitComment:
    def test_text_that_fits_is_unchanged_and_has_no_warning(self) -> None:
        warnings: list[MigrationWarning] = []
        assert fit_comment(warnings, "t", "c", "corto", MYSQL_COLUMN_COMMENT, "MySQL") == "corto"
        assert warnings == []

    def test_chars_limit(self) -> None:
        warnings: list[MigrationWarning] = []
        assert fit_comment(warnings, "t", "c", "x" * 1500, MYSQL_COLUMN_COMMENT, "MySQL") == "x" * 1024
        [warning] = warnings
        assert warning.category == "COMMENT" and warning.severity == "WARNING" and warning.column == "c"
        assert "1500 a 1024" in warning.message

    def test_oracle_bytes_never_split_a_character(self) -> None:
        text = "ñ" * 2500  # 5000 bytes
        fitted = fit_comment([], "t", None, text, ORACLE_COMMENT, "Oracle")
        assert fitted == "ñ" * 2000 and len(fitted.encode("utf-8")) == 4000

    def test_sqlserver_counts_utf16_units(self) -> None:
        text = "😀" * 2000  # fuera del plano básico: 2 unidades UTF-16 cada uno → 4000 unidades
        fitted = fit_comment([], "t", None, text, SQLSERVER_COMMENT, "SQL Server")
        assert len(fitted.encode("utf-16-le")) // 2 <= 3750 and fitted == "😀" * 1875

    def test_warning_is_not_duplicated(self) -> None:
        warnings: list[MigrationWarning] = []
        for _ in range(2):
            fit_comment(warnings, "t", None, "x" * 3000, MYSQL_TABLE_COMMENT, "MySQL")
        assert len(warnings) == 1


class TestEmitters:
    def test_mysql_table_and_column_comments_are_truncated(self) -> None:
        table = _table("t" * 3000, "c" * 1500)
        [ddl] = MySQLDDLEmitter("utf8mb4", "utf8mb4_0900_ai_ci").emit_statements([table])
        assert f"COMMENT='{'t' * 2048}'" in ddl and f"COMMENT '{'c' * 1024}'" in ddl
        assert {w.column for w in table.warnings + table.columns[0].warnings if w.category == "COMMENT"} == {None, "c"}

    def test_oracle_and_sqlserver_are_truncated(self) -> None:
        oracle = "\n".join(OracleDDLEmitter().emit_statements([_table("t" * 5000, "c" * 5000)]))
        assert f"IS '{'t' * 4000}'" in oracle and f"IS '{'c' * 4000}'" in oracle
        sqlserver = "\n".join(SQLServerDDLEmitter().emit_statements([_table("t" * 5000, "c" * 5000)]))
        assert f"N'{'t' * 3750}'" in sqlserver and "t" * 3751 not in sqlserver

    def test_postgresql_keeps_the_whole_comment(self) -> None:
        table = _table("t" * 5000, "c" * 5000)
        ddl = "\n".join(PostgreSQLDDLEmitter().emit_statements([table]))
        assert "t" * 5000 in ddl and not any(w.category == "COMMENT" for w in table.warnings)
