"""Idioma de los informes de ``dump`` y de la auditoría (``AuditManager``) (5.10.0)."""

from __future__ import annotations

import json

from pathlib import Path

import openpyxl
import pytest
import sqlalchemy as sa

from _leftovers import spanish_hits, spanish_hits_in, visible_text

from util_bbdd import DumpOrchestrator
from util_bbdd._core.i18n import Translator
from util_bbdd.audit.readiness import ReadinessRows, ReadinessSheetWriter
from util_bbdd.bulk import AuditManager
from util_bbdd.dump import DumpConfig
from util_bbdd.dump.reporters import DumpReporter

#: Recomendaciones de ``EngineReadinessAdvisor`` (módulo ``connection``): fuera del alcance de la i18n de resultados.
ADVISOR_TEXT = ("PRAGMA",)


def _engines(tmp_path: Path) -> tuple[sa.Engine, sa.Engine]:
    ddl = "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT); CREATE TABLE orders (id INTEGER PRIMARY KEY);"
    engines = []
    for name, extra in (("src", "CREATE TABLE legacy (id INTEGER PRIMARY KEY);"), ("dst", "")):
        engine = sa.create_engine(f"sqlite:///{tmp_path / name}.db")
        raw = engine.raw_connection()
        raw.executescript(ddl + extra + ("INSERT INTO customers VALUES (1, 'Ann');" if name == "src" else ""))  # type: ignore[attr-defined]
        raw.commit()
        raw.close()
        engines.append(engine)
    return engines[0], engines[1]


# ── dump ─────────────────────────────────────────────────────────────────────


def test_dump_config_rejects_unsupported_locale(tmp_path: Path) -> None:
    src, dst = _engines(tmp_path)
    with pytest.raises(ValueError, match="Idioma no soportado"):
        DumpConfig(source_engine=src, target_engine=dst, locale="fr")  # type: ignore[arg-type]


def test_dump_report_in_english_has_no_spanish(tmp_path: Path) -> None:
    src, dst = _engines(tmp_path)
    result = DumpOrchestrator(DumpConfig(source_engine=src, target_engine=dst, output_dir=tmp_path, locale="en")).run()

    assert result.report is not None
    sheets = openpyxl.load_workbook(result.report).sheetnames
    assert sheets[:3] == ["Table Audit", "Missing Tables", "Missing Columns"]
    assert "Engine conditions" in sheets
    assert spanish_hits_in([Path(result.report)], ignore=ADVISOR_TEXT) == {}


def test_dump_report_defaults_to_spanish(tmp_path: Path) -> None:
    src, dst = _engines(tmp_path)
    result = DumpOrchestrator(DumpConfig(source_engine=src, target_engine=dst, output_dir=tmp_path)).run()

    assert openpyxl.load_workbook(result.report).sheetnames[:3] == [
        "Auditoría Tablas",
        "Tablas Faltantes",
        "Columnas Inexistentes",
    ]


def test_every_optional_dump_sheet_is_translated(tmp_path: Path) -> None:
    """Las hojas opcionales con datos vacíos o de error también salen en inglés."""
    path = DumpReporter(tmp_path, Translator("en")).generate(
        table_results=[],
        missing_tables=["legacy"],
        constraint_results=[],
        cycles=[],
        index_results=[],
        pk_sync_results=[],
        constraint_reactivation_error="",
        engine_readiness=[("Engine", None)],
    )
    assert openpyxl.load_workbook(path).sheetnames == [
        "Table Audit",
        "Missing Tables",
        "Missing Columns",
        "Indexes",
        "PK Sequences",
        "Reactivation Errors",
        "Engine conditions",
    ]
    assert spanish_hits(visible_text(path)) == []


# ── auditoría (AuditManager) ─────────────────────────────────────────────────


def _audit(tmp_path: Path, locale: str) -> AuditManager:
    manager = AuditManager(tmp_path / "audit.csv", locale=locale)  # type: ignore[arg-type]
    manager.registrar_operacion("orders", "sqlite", "INSERT", 1234567, 12.3456)
    manager.registrar_operacion("customers", "sqlite", "UPDATE", 10, 0.5)
    return manager


def test_audit_manager_rejects_unsupported_locale(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Idioma no soportado"):
        AuditManager(tmp_path / "audit.csv", locale="de")  # type: ignore[arg-type]


def test_audit_html_in_english_uses_english_texts_and_separators(tmp_path: Path) -> None:
    html = _audit(tmp_path, "en").exportar_resumen_html(tmp_path / "audit.html").read_text(encoding="utf-8")

    assert '<html lang="en">' in html
    assert "Audit Report" in html and "1,234,577" in html and "12.85" in html
    assert spanish_hits(html) == []


def test_audit_html_in_spanish_uses_spanish_separators(tmp_path: Path) -> None:
    """Corrección de 5.10.0: antes el HTML en español salía con separadores ingleses (``1,234,577`` y ``12.85``)."""
    html = _audit(tmp_path, "es").exportar_resumen_html(tmp_path / "audit.html").read_text(encoding="utf-8")

    assert '<html lang="es">' in html
    assert "Reporte de Auditoría" in html and "1.234.577" in html and "12,85" in html and "6,4230" in html


def test_audit_excel_sheet_names_follow_the_locale(tmp_path: Path) -> None:
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'e.db'}")
    manager = _audit(tmp_path, "en")
    sheets = openpyxl.load_workbook(manager.exportar_resumen_excel(engine=engine)).sheetnames

    assert "Global_summary" in sheets and sheets[-1] == "Engine_conditions"


def test_audit_json_is_not_translated(tmp_path: Path) -> None:
    """El JSON es para máquinas: mismas claves en cualquier idioma."""
    keys_en = json.loads(_audit(tmp_path / "en", "en").exportar_resumen_json().read_text(encoding="utf-8")).keys()
    keys_es = json.loads(_audit(tmp_path / "es", "es").exportar_resumen_json().read_text(encoding="utf-8")).keys()
    assert keys_en == keys_es and "estadisticas" in keys_en


# ── condiciones del motor (compartido por bulk, dump y doc) ─────────────────


def test_readiness_rows_follow_the_translator() -> None:
    assert ReadinessRows.from_report(None, Translator("en")).notices == (
        "The conditions of this engine could not be checked.",
    )
    assert ReadinessRows.from_report(None).notices == (ReadinessRows.NOTICE_UNAVAILABLE,)


def test_readiness_sheet_in_english(tmp_path: Path) -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    assert sheet is not None
    ReadinessSheetWriter(Translator("en")).write(sheet, [("Engine", None)])
    text = "\n".join(str(cell.value) for row in sheet.iter_rows() for cell in row if cell.value is not None)

    assert "Engine conditions" in text
    assert spanish_hits(text) == []
