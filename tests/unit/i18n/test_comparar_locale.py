"""Idioma de los informes de ``SchemaDiffReporter`` (5.10.0): ``es`` por defecto, ``en`` sin texto en español."""

from __future__ import annotations

import re

from pathlib import Path
from unittest.mock import MagicMock

import openpyxl
import pytest
import sqlalchemy as sa

from _leftovers import spanish_hits, spanish_hits_in, visible_text
from sqlalchemy.exc import OperationalError

from util_bbdd import SchemaComparator
from util_bbdd._core.i18n import Translator
from util_bbdd.comparar import SchemaDiffReporter
from util_bbdd.comparar.models import (
    ColumnDiff,
    CommentDiff,
    ForeignKeyDiff,
    IndexDiff,
    RoutineDiff,
    SchemaDiff,
    TableDiff,
    ViewDiff,
)
from util_bbdd.comparar.reporters import SqlDiffReporter
from util_bbdd.comparar.reporters._base import STATUS_ES, localized_summary, status_labels

pytestmark = pytest.mark.unit

#: Dialectos del script SQL: cada uno tiene sus propios avisos ``--``.
DIALECTS = ("generic", "mariadb", "postgresql", "sqlserver", "oracle", "sqlite")


def _synthetic_diff(summary: str = "") -> SchemaDiff:
    """Un ejemplo de cada diferencia (datos en inglés y sin tildes)."""
    return SchemaDiff(
        source_label="prod",
        target_label="staging",
        summary=summary,
        table_diffs=(
            TableDiff(
                table_name="users",
                status="modified",
                column_diffs=(
                    ColumnDiff("email", "type", "VARCHAR(100)", "VARCHAR(255)"),
                    ColumnDiff("deleted_at", "existence", "exists", "missing"),
                    ColumnDiff("legacy", "existence", "missing", "exists"),
                    ColumnDiff("odd", "existence", "weird", "other"),
                    ColumnDiff("name", "nullable", "NO", "YES"),
                    ColumnDiff("status", "default", "NONE", "'a'"),
                    ColumnDiff("code", "default", "'x'", "NONE"),
                    ColumnDiff("id", "primary_key", "True", "False"),
                    ColumnDiff("age", "collation", "a", "b"),  # type: ignore[arg-type],
                ),
                index_diffs=(
                    IndexDiff("idx_email", "users", "modified", "email", "email,created_at", True, False),
                    IndexDiff("idx_empty", "users", "added", "", ""),
                ),
                fk_diffs=(
                    ForeignKeyDiff("fk_users_company", "users", "added", target_columns="company_id"),
                    ForeignKeyDiff("fk_users_team", "users", "removed", target_columns="team_id"),
                ),
                comment_diffs=(
                    CommentDiff("users", "email", "User email", "Mail"),
                    CommentDiff("users", None, "Users", "People"),
                ),
            ),
            TableDiff(table_name="orders_archive", status="added"),
            TableDiff(
                table_name="legacy_log",
                status="removed",
                fk_diffs=(ForeignKeyDiff("fk_log_user", "legacy_log", "removed"),),
            ),
            TableDiff(table_name="empty_mod", status="modified"),
        ),
        view_diffs=(
            ViewDiff("v_active_users", "modified", "SELECT 1", "SELECT 2"),
            ViewDiff("v_new", "added"),
            ViewDiff("v_nodef", "modified", "", "SELECT 3"),
            ViewDiff("v_old", "removed"),
        ),
        routine_diffs=(
            RoutineDiff("sp_cleanup", "PROCEDURE", "modified", "BEGIN SELECT 1; END", "BEGIN SELECT 2; END"),
            RoutineDiff("sp_new", "PROCEDURE", "added"),
            RoutineDiff("fn_nodef", "FUNCTION", "modified"),
            RoutineDiff("sp_old", "PROCEDURE", "removed"),
        ),
    )


def _real_diff(tmp_path: Path) -> SchemaDiff:
    """Comparación real de dos SQLite (``summary`` escrito por ``SchemaComparator``)."""
    engines = []
    for name, ddl in (
        ("a", "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT); CREATE TABLE extra (id INTEGER PRIMARY KEY);"),
        ("b", "CREATE TABLE users (id INTEGER PRIMARY KEY); CREATE TABLE legacy (id INTEGER PRIMARY KEY);"),
    ):
        engine = sa.create_engine(f"sqlite:///{tmp_path / name}.db")
        raw = engine.raw_connection()
        raw.executescript(ddl)  # type: ignore[attr-defined]
        raw.commit()
        raw.close()
        engines.append(engine)
    return SchemaComparator().compare(sa.inspect(engines[0]), sa.inspect(engines[1]))


def _without_code(text: str) -> str:
    """Quita ``<script>`` y ``<style>`` (comentarios de código, no texto visible) de un HTML."""
    return re.sub(r"<(script|style)\b.*?</\1>", "", text, flags=re.S)


def test_rejects_unsupported_locale() -> None:
    with pytest.raises(ValueError, match="Idioma no soportado"):
        SchemaDiffReporter(locale="fr")  # type: ignore[arg-type]


def test_all_formats_in_english_have_no_spanish(tmp_path: Path) -> None:
    paths = SchemaDiffReporter(locale="en").render_all(_synthetic_diff(), tmp_path, raise_on_error=True)

    assert len(paths) == 5
    office = [p for p in paths if p.suffix in {".xlsx", ".docx", ".md", ".sql"}]
    assert spanish_hits_in(office) == {}
    html = next(p for p in paths if p.suffix == ".html")
    assert spanish_hits(_without_code(visible_text(html))) == []
    assert '<html lang="en">' in html.read_text(encoding="utf-8")


def test_english_with_a_real_comparator_summary(tmp_path: Path) -> None:
    diff = _real_diff(tmp_path)
    assert diff.summary.startswith("Tablas:")  # el comparador lo escribe en español

    paths = SchemaDiffReporter(locale="en").render_all(diff, tmp_path / "out", raise_on_error=True)

    markdown = next(p for p in paths if p.suffix == ".md").read_text(encoding="utf-8")
    assert "> Tables: 1 added, 1 removed, 1 modified" in markdown
    office = [p for p in paths if p.suffix != ".html"]
    assert spanish_hits_in(office) == {}


@pytest.mark.parametrize("dialect", DIALECTS)
def test_sql_comments_in_english_for_every_dialect(tmp_path: Path, dialect: str) -> None:
    output = SqlDiffReporter(dialect, translator=Translator("en")).render(_synthetic_diff(), tmp_path / "d.sql")

    script = output.read_text(encoding="utf-8")
    assert spanish_hits(script) == []
    assert "-- Schema alignment script" in script


@pytest.mark.parametrize("dialect", DIALECTS)
def test_sql_with_source_inspector_in_english(tmp_path: Path, dialect: str) -> None:
    inspector = MagicMock()
    inspector.get_columns.return_value = [{"name": "id", "type": "INTEGER", "nullable": False, "default": None}]
    inspector.get_pk_constraint.return_value = {"constrained_columns": ["id"], "name": None}
    inspector.get_foreign_keys.return_value = []
    inspector.get_indexes.return_value = []

    reporter = SqlDiffReporter(dialect, source_inspector=inspector, translator=Translator("en"))
    script = reporter.render(_synthetic_diff(), tmp_path / "d.sql").read_text(encoding="utf-8")

    assert "with source Inspector metadata" in script
    assert spanish_hits(script) == []


def test_sql_placeholder_for_new_table_when_inspector_fails(tmp_path: Path) -> None:
    inspector = MagicMock()
    inspector.get_columns.side_effect = OperationalError("connection lost", None, None)
    diff = SchemaDiff("a", "b", table_diffs=(TableDiff(table_name="broken", status="added"),))

    reporter = SqlDiffReporter("sqlite", source_inspector=inspector, translator=Translator("en"))
    script = reporter.render(diff, tmp_path / "d.sql").read_text(encoding="utf-8")

    assert "-- ⚠ NEW TABLE: broken" in script
    assert "-- Cause: Inspector.get_columns() failed" in script
    assert spanish_hits(script) == []


def test_spanish_is_the_default(tmp_path: Path) -> None:
    paths = SchemaDiffReporter().render_all(_synthetic_diff("Resumen libre"), tmp_path, raise_on_error=True)

    by_suffix = {p.suffix: p for p in paths}
    markdown = by_suffix[".md"].read_text(encoding="utf-8")
    assert markdown.startswith("# Reporte de diferencias de esquema")
    assert "> Resumen libre" in markdown
    assert "<details><summary>Ver definiciones</summary>" in markdown
    assert '<html lang="es">' in by_suffix[".html"].read_text(encoding="utf-8")
    assert "-- Script de nivelación de esquemas" in by_suffix[".sql"].read_text(encoding="utf-8")
    assert openpyxl.load_workbook(by_suffix[".xlsx"]).sheetnames[:3] == ["Resumen", "Tablas", "Columnas"]


def test_key_texts_in_each_language(tmp_path: Path) -> None:
    diff = _synthetic_diff()
    es_paths = SchemaDiffReporter(locale="es").render_all(diff, tmp_path / "es", formats=["excel", "html"])
    en_paths = SchemaDiffReporter(locale="en").render_all(diff, tmp_path / "en", formats=["excel", "html"])

    assert openpyxl.load_workbook(es_paths[0]).sheetnames == [
        "Resumen",
        "Tablas",
        "Columnas",
        "Indices",
        "ForeignKeys",
        "Vistas",
        "Rutinas",
    ]
    assert openpyxl.load_workbook(en_paths[0]).sheetnames == [
        "Summary",
        "Tables",
        "Columns",
        "Indexes",
        "ForeignKeys",
        "Views",
        "Routines",
    ]
    es_html = es_paths[1].read_text(encoding="utf-8")
    en_html = en_paths[1].read_text(encoding="utf-8")
    assert 'data-filter="tables-added">Tablas añadidas</button>' in es_html
    assert 'data-filter="tables-added">Tables added</button>' in en_html  # misma categoría, otra etiqueta
    assert "Página anterior" not in en_html


def test_user_written_summary_is_kept_as_is() -> None:
    diff = _synthetic_diff("Custom note")

    assert localized_summary(diff, Translator("en")) == "Custom note"
    assert localized_summary(SchemaDiff("a", "b"), Translator("en")) == ""


def test_status_constant_keeps_spanish_values() -> None:
    assert status_labels() == STATUS_ES
    assert status_labels(Translator("en")) == {"added": "Added", "removed": "Removed", "modified": "Modified"}
