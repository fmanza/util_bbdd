"""Idioma de la documentación Word y Excel y de los textos comunes de ``doc`` (leyenda, almacenamiento…) (5.10.0)."""

from __future__ import annotations

import logging

from pathlib import Path
from typing import Any, cast

import docx
import openpyxl
import pytest
import sqlalchemy as sa

from _leftovers import spanish_hits_in, visible_text

from util_bbdd import SyncDatabaseManager
from util_bbdd._core.exceptions import DatabaseException
from util_bbdd._core.i18n import Locale, Translator
from util_bbdd.doc import DatabaseDocumentation
from util_bbdd.doc.infrastructure.renderers.shared.diagram_legend import (
    build_diagram_legend_payload,
    build_diagram_legend_rows,
    build_diagram_reading_aids,
    build_hidden_levels_help,
)
from util_bbdd.doc.infrastructure.renderers.shared.diagram_summary import (
    build_diagram_summary_line,
    build_diagram_summary_payload,
)
from util_bbdd.doc.infrastructure.renderers.word_generator import WordGenerator
from util_bbdd.doc.infrastructure.runtime.headers_runtime import DocumentationHeadersRuntime
from util_bbdd.doc.infrastructure.storage.engines import parse_temp_data_file_path_rows
from util_bbdd.doc.infrastructure.storage.runtime import StorageInventoryRuntime

#: Recomendaciones de ``EngineReadinessAdvisor`` (módulo ``connection``): fuera del alcance de la i18n de resultados.
ADVISOR_TEXT = ("PRAGMA",)

_DDL = """
CREATE TABLE customers (id INTEGER PRIMARY KEY, name VARCHAR(80) NOT NULL, email VARCHAR(120) UNIQUE);
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    total NUMERIC(10,2)
);
CREATE INDEX ix_orders_customer ON orders(customer_id);
CREATE VIEW v_orders AS SELECT o.id, c.name, o.total FROM orders o JOIN customers c ON c.id = o.customer_id;
CREATE TRIGGER trg_orders AFTER INSERT ON orders BEGIN UPDATE orders SET total = total WHERE id = NEW.id; END;
INSERT INTO customers VALUES (1, 'Ann', 'ann@example.com');
"""

#: ``imprimir`` con todas las secciones (como en ``docs/api/database_documentation.md``) salvo el grafo (Graphviz).
_IMPRIMIR: dict[str, Any] = {
    "tablas": {"imprimir_tablas": True, "ddl": True, "columnas": True, "pk": True, "fk": True, "unicas": True,
               "indices": True},
    "vistas": {"imprimir_vistas": True, "ddl": True, "columnas": True},
    "rutinas": {"imprimir_procedures": True, "imprimir_function": True},
    "info_database": {"imprimir_info_database": True, "version": True, "charset_collation": True},
    "columnas_charset": {"charset_collation": True},
    "almacenamiento": {"imprimir_almacenamiento": True},
    "condiciones_motor": {"imprimir_condiciones_motor": True},
    "grafo": {"enabled": False},
}  # fmt: skip


def _generate(tmp_path: Path, locale: Locale | None) -> tuple[Path, Path]:
    """Genera Word y Excel sobre un SQLite y devuelve ``(docx, xlsx)``."""
    db = tmp_path / "shop.db"
    raw = sa.create_engine(f"sqlite:///{db}").raw_connection()
    raw.executescript(_DDL)  # type: ignore[attr-defined]
    raw.commit()
    raw.close()
    manager = SyncDatabaseManager(db_type="sqlite", conn_params={"database": str(db)}, use_pool=False)
    kwargs: dict[str, Any] = {} if locale is None else {"locale": locale}
    try:
        DatabaseDocumentation(
            manager, tmp_path / "out", fichero_salida=Path("doc"), imprimir=_IMPRIMIR, formatos=["word", "excel"],
            **kwargs,
        ).generate()  # fmt: skip
    finally:
        manager.close()
    return next((tmp_path / "out").rglob("*.docx")), next((tmp_path / "out").rglob("*.xlsx"))


# ── Word y Excel completos ───────────────────────────────────────────────────


def test_word_and_excel_in_english_have_no_spanish(tmp_path: Path) -> None:
    word, excel = _generate(tmp_path, "en")

    assert spanish_hits_in([word, excel], ignore=ADVISOR_TEXT) == {}
    sheets = openpyxl.load_workbook(excel).sheetnames
    assert sheets == [
        "Documentation",
        "Columns",
        "Procedures",
        "Functions",
        "Storage",
        "Engine conditions",
        "Charset & Collation",
        "Database",
    ]
    text = visible_text(word)
    for expected in ("Database Documentation - ", "Inventory summary", "Relationships (Foreign Keys)", "Indexes"):
        assert expected in text


def test_word_and_excel_default_to_spanish(tmp_path: Path) -> None:
    word, excel = _generate(tmp_path, None)

    assert openpyxl.load_workbook(excel).sheetnames[:2] == ["Documentación", "Columnas"]
    headings = [p.text for p in docx.Document(str(word)).paragraphs]
    assert "Resumen de inventario" in headings
    assert "Relaciones (Claves Foráneas)" in headings
    assert "Condiciones del motor" in headings


# ── textos comunes a varios formatos ─────────────────────────────────────────


def test_diagram_legend_and_summary_follow_the_translator() -> None:
    en = Translator("en")

    assert build_diagram_legend_payload(en)["title"] == "Visual legend"
    assert build_diagram_legend_payload()["title"] == "Leyenda visual"
    assert build_diagram_legend_rows(translator=en)[0][:2] == ["Direction", "Outgoing"]
    assert build_hidden_levels_help("incoming", 2, translator=en).startswith("Hidden incoming: 2 level(s) of")
    assert build_hidden_levels_help("incoming", 2).startswith("Entrada oculta: 2 nivel(es) de tablas padre")
    aids = build_diagram_reading_aids(
        visible_outgoing_levels=1, visible_incoming_levels=2, hidden_outgoing_levels=1, hidden_incoming_levels=0,
        translator=en,
    )  # fmt: skip
    assert aids[0].startswith("Outgoing: Outgoing relationships")
    summary = build_diagram_summary_payload(
        max_depth=2, total_outgoing_levels=3, total_incoming_levels=1, visible_outgoing_levels=2,
        visible_incoming_levels=1, hidden_outgoing_levels=1, hidden_incoming_levels=0, translator=en,
    )  # fmt: skip
    assert summary["title"] == "Level summary"
    assert build_diagram_summary_line(summary, en) == (
        "Levels per direction: 2 | Outgoing (tables it points to): 2 of 3 | Incoming (tables pointing to it): 1 of 1"
    )
    assert build_diagram_summary_line(summary).startswith("Niveles por sentido: 2 | Salientes")


def test_default_headers_fallback_follows_the_locale() -> None:
    assert DocumentationHeadersRuntime.default_headers("en", "UNIQUE") == ["Constraint Name", "Field"]
    assert WordGenerator("demo", {}, translator=Translator("en")).headers["UNIQUE"] == ["Constraint Name", "Field"]
    assert WordGenerator("demo", {}).headers["UNIQUE"] == ["Nombre Restricción", "Campo"]


class _OracleManager:
    """``user_tablespaces`` → (USERS, TEMP); las consultas por tablespace fallan en ``BAD``."""

    def __init__(self) -> None:
        self.conn_params: dict[str, Any] = {"tablespace": "BAD"}

    def get_storage_rows(self, query_name: str, **params: Any) -> list[tuple[Any, ...]]:
        if query_name == "user_tablespaces":
            return [("USERS", "TEMP")]
        if params.get("tablespace") == "BAD":
            raise DatabaseException("ORA-00942")
        return [(params["tablespace"], "/u01/data.dbf", 100.5, "AVAILABLE", "DATA", "YES", 2048)]


@pytest.mark.parametrize(
    ("locale", "title", "header", "size", "message"),
    [
        ("en", "Physical files", "Size (MB)", "100.50", "OK (2 tablespace(s) queried). With partial issues: BAD"),
        ("es", "Ficheros físicos", "Tamaño (MB)", "100,50", "OK (2 tablespace(s) consultado(s)). Con incidencias"),
    ],
)
def test_storage_report_follows_the_translator(
    locale: Locale, title: str, header: str, size: str, message: str
) -> None:
    report = StorageInventoryRuntime(
        db_manager=cast(Any, _OracleManager()),
        logger=logging.getLogger(__name__),
        db_type="oracle",
        database="demo",
        print_config={},
        translator=Translator(locale),
    ).get_storage_inventory_report()

    files = report["sections"][0]
    assert files["title"] == title
    assert files["headers"][2] == header
    assert files["numeric_columns"] == [2, 6]  # las columnas de tamaño no dependen del idioma
    assert files["rows"][0][2] == size
    assert files["message"].startswith(message)


def test_innodb_temp_rows_translate_autoextend() -> None:
    raw = "ibtmp1:12M:autoextend:max:5G"
    assert parse_temp_data_file_path_rows("v", raw, Translator("en"))[0][3] == "Yes"
    assert parse_temp_data_file_path_rows("v", raw)[0][3] == "Si"
