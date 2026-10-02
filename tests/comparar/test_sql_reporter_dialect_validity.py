"""Validez del SQL de nivelación por dialecto y escape de literales; contador del diagrama Markdown.

Cubre los hallazgos B2, B3, B6 y S1 de la auditoría de ``comparar/`` (2026-10-02).
"""

from __future__ import annotations

import sqlite3

from typing import TYPE_CHECKING

import pytest

from util_bbdd.comparar.models import ColumnDiff, CommentDiff, ForeignKeyDiff, IndexDiff, SchemaDiff, TableDiff
from util_bbdd.comparar.reporters import MarkdownDiffReporter, SqlDiffReporter

if TYPE_CHECKING:
    from pathlib import Path


def _diff(*table_diffs: TableDiff) -> SchemaDiff:
    return SchemaDiff(source_label="src", target_label="tgt", table_diffs=table_diffs)


def _render(dialect: str, diff: SchemaDiff, tmp_path: Path) -> str:
    out = tmp_path / f"{dialect}.sql"
    SqlDiffReporter(dialect=dialect).render(diff, out)
    return out.read_text(encoding="utf-8")


def _statements(script: str) -> list[str]:
    return [line for line in script.splitlines() if line and not line.startswith("--")]


# ---------------------------------------------------------------------------
# B2 — SQLite: los avisos no pueden ir dentro de ALTER TABLE
# ---------------------------------------------------------------------------


class TestSqliteScriptIsExecutable:
    def test_script_with_unsupported_changes_runs_in_sqlite(self, tmp_path: Path) -> None:
        diff = _diff(
            TableDiff(
                "t",
                "modified",
                column_diffs=(
                    ColumnDiff("c", "type", "INTEGER", "TEXT"),
                    ColumnDiff("c", "nullable", "False", "True"),
                    ColumnDiff("c", "default", "0", ""),
                ),
                index_diffs=(IndexDiff("ix_c", "t", "added", source_columns="c"),),
                fk_diffs=(
                    ForeignKeyDiff("fk_old", "t", "removed"),
                    ForeignKeyDiff("fk_new", "t", "added", source_columns="c", source_referred_table="r"),
                ),
            ),
        )
        script = _render("sqlite", diff, tmp_path)

        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE r (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE t (c TEXT)")
        conn.executescript(script)  # antes: "ALTER TABLE t -- ⚠ …;" se comía el ";" → error de sintaxis

        assert conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'").fetchall() == [("ix_c",)]
        assert all(not s.startswith("ALTER TABLE") for s in _statements(script))

    def test_dropped_table_fk_warning_is_standalone_comment(self, tmp_path: Path) -> None:
        diff = _diff(TableDiff("t", "removed", fk_diffs=(ForeignKeyDiff("fk", "t", "removed"),)))

        script = _render("sqlite", diff, tmp_path)

        assert "ALTER TABLE t --" not in script
        sqlite3.connect(":memory:").executescript(script)


# ---------------------------------------------------------------------------
# B3 — SQL Server: sin SET/DROP NOT NULL ni SET/DROP DEFAULT
# ---------------------------------------------------------------------------


class TestSqlServerSyntax:
    def test_nullable_change_uses_alter_column_with_type(self, tmp_path: Path) -> None:
        diff = _diff(TableDiff("t", "modified", column_diffs=(ColumnDiff("c", "nullable", "False", "True"),)))

        script = _render("sqlserver", diff, tmp_path)

        assert "SET NOT NULL" not in script
        assert "ALTER TABLE t ALTER COLUMN c <TIPO> NOT NULL;" in script
        assert "-- ⚠ SQL Server: ALTER COLUMN exige el tipo" in script

    def test_default_change_drops_constraint_and_adds_named_default(self, tmp_path: Path) -> None:
        diff = _diff(
            TableDiff(
                "t",
                "modified",
                column_diffs=(ColumnDiff("a", "default", "0", "1"), ColumnDiff("b", "default", "", "'x'")),
            ),
        )

        script = _render("sqlserver", diff, tmp_path)

        assert "SET DEFAULT" not in script
        assert "DROP DEFAULT" not in script
        # Una variable por bloque: varias declaraciones en el mismo lote no colisionan
        assert "DECLARE @df_1 nvarchar(max)" in script
        assert "DECLARE @df_2 nvarchar(max)" in script
        assert "COLUMNPROPERTY(OBJECT_ID(N't'), N'a', 'ColumnId')" in script
        assert "ALTER TABLE t ADD CONSTRAINT [DF_t_a] DEFAULT 0 FOR a;" in script
        assert "DF_t_b" not in script  # el origen no tiene DEFAULT: solo se elimina

    def test_default_counter_restarts_on_each_render(self, tmp_path: Path) -> None:
        reporter = SqlDiffReporter(dialect="sqlserver")
        diff = _diff(TableDiff("t", "modified", column_diffs=(ColumnDiff("a", "default", "0", "1"),)))
        reporter.render(diff, tmp_path / "1.sql")
        reporter.render(diff, tmp_path / "2.sql")

        assert "@df_1" in (tmp_path / "2.sql").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# S1 — escape de comentarios en MariaDB/MySQL
# ---------------------------------------------------------------------------


class TestCommentEscaping:
    @pytest.mark.parametrize("dialect", ["mariadb", "mysql"])
    def test_trailing_backslash_does_not_leave_literal_open(self, dialect: str, tmp_path: Path) -> None:
        diff = _diff(TableDiff("t", "modified", comment_diffs=(CommentDiff("t", None, "ruta C:\\", ""),)))

        script = _render(dialect, diff, tmp_path)

        assert "ALTER TABLE t COMMENT = 'ruta C:\\\\';" in script

    def test_quote_injection_is_neutralised(self, tmp_path: Path) -> None:
        payload = "x\\'; DROP TABLE t; -- "
        diff = _diff(TableDiff("t", "modified", comment_diffs=(CommentDiff("t", None, payload, ""),)))

        script = _render("mariadb", diff, tmp_path)

        assert "COMMENT = 'x\\\\''; DROP TABLE t; -- ';" in script

    def test_postgresql_keeps_backslash_as_is(self, tmp_path: Path) -> None:
        diff = _diff(TableDiff("t", "modified", comment_diffs=(CommentDiff("t", None, "C:\\", ""),)))

        script = _render("postgresql", diff, tmp_path)

        assert "COMMENT ON TABLE t IS 'C:\\';" in script


# ---------------------------------------------------------------------------
# B6 — Mermaid: "(n cols)" cuenta las columnas con diferencias
# ---------------------------------------------------------------------------


def test_markdown_mermaid_counts_column_diffs(tmp_path: Path) -> None:
    cols = tuple(ColumnDiff(f"c{i}", "type", "A", "B") for i in range(5))
    out = tmp_path / "diff.md"

    MarkdownDiffReporter().render(_diff(TableDiff("t", "modified", column_diffs=cols)), out)

    assert 'M_t["t\\n(5 cols)"]' in out.read_text(encoding="utf-8")
