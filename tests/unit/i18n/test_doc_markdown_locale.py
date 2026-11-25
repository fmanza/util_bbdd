"""Idioma de la documentación Markdown (``DatabaseDocumentation(locale=...)``, catálogo ``doc_md``, 5.10.0)."""

from __future__ import annotations

import json
import sqlite3

from pathlib import Path
from typing import Any

import pytest

from _leftovers import spanish_hits, spanish_hits_in

from util_bbdd._core.i18n import Translator
from util_bbdd.doc.database_documentation import DatabaseDocumentation
from util_bbdd.doc.infrastructure.renderers.markdown._changes import Changes, changes_page
from util_bbdd.doc.infrastructure.renderers.markdown._site_pages import IndexEntry, index_pages
from util_bbdd.doc.infrastructure.renderers.markdown._trace import TraceEntry, TraceMap, traceability_page
from util_bbdd.managers import SyncDatabaseManager

pytestmark = pytest.mark.unit

SCHEMA = """
CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE);
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    total NUMERIC
);
CREATE INDEX ix_orders_customer ON orders (customer_id);
CREATE TABLE items (id INTEGER PRIMARY KEY, order_id INTEGER REFERENCES orders(id), sku TEXT);
CREATE VIEW v_orders AS SELECT o.id, c.name FROM orders o JOIN customers c ON c.id = o.customer_id;
"""

TRACE_MAP = """
[tables.orders]
code = ["src/sales/orders.py#Order"]
requirements = ["REQ-12"]
tags = ["sales"]
notes = "Order header"

[tables.orders.columns.customer_id]
code = ["src/sales/orders.py#Order.customer_id"]

[tables.ghost]
code = ["src/ghost.py"]
"""

IMPRIMIR: dict[str, Any] = {
    "tablas": {"imprimir_tablas": True, "ddl": True, "columnas": True, "pk": True, "fk": True, "indices": True},
    "vistas": {"imprimir_vistas": True, "columnas": True},
    "info_database": {"imprimir_info_database": True},
    "grafo": {"enabled": True, "max_depth": 2},
}

#: Recomendaciones de ``EngineReadinessAdvisor`` (módulo ``connection``): fuera del alcance de la i18n de resultados.
ADVISOR_TEXT = ("PRAGMA",)
#: Ficheros para máquinas: no se traducen (se comprueba aparte que son iguales en los dos idiomas).
MACHINE_FILES = {"catalog.json", "changes.json", "manifest.json"}


@pytest.fixture
def sqlite_db(tmp_path: Path) -> Path:
    db = tmp_path / "sales.db"
    with sqlite3.connect(db) as connection:
        connection.executescript(SCHEMA)
    return db


@pytest.fixture
def trace_map(tmp_path: Path) -> Path:
    path = tmp_path / "trace.toml"
    path.write_text(TRACE_MAP, encoding="utf-8")
    return path


def _generate(db: Path, out: Path, markdown: dict[str, Any], **kwargs: Any) -> Path:
    imprimir = {**IMPRIMIR, "markdown": markdown}
    with SyncDatabaseManager("sqlite", {"database": str(db)}, use_pool=False) as manager:
        result = DatabaseDocumentation(
            manager, out, Path("demo"), imprimir=imprimir, formatos=["markdown"], **kwargs
        ).generate()
    return Path(result.outputs["markdown"])


def _human_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in {".md", ".txt", ".toml"})


def _front_matters(root: Path) -> dict[str, str]:
    """Front matter (línea JSON entre ``---``) de cada página de objeto."""
    result: dict[str, str] = {}
    for page in sorted((root / "docs").rglob("*.md")):
        lines = page.read_text(encoding="utf-8").splitlines()
        if lines and lines[0] == "---":
            result[page.relative_to(root).as_posix()] = lines[1]
    return result


def test_english_markdown_has_no_spanish(sqlite_db: Path, trace_map: Path, tmp_path: Path) -> None:
    root = _generate(sqlite_db, tmp_path / "en", {"trace_map": str(trace_map)}, locale="en")

    files = _human_files(root)
    assert {"README.md", "index.md", "traceability.md", "llms.txt", "llms-full.txt", "zensical.toml"} <= {
        p.name for p in files
    }
    assert spanish_hits_in(files, ignore=ADVISOR_TEXT) == {}


def test_english_markdown_key_texts(sqlite_db: Path, trace_map: Path, tmp_path: Path) -> None:
    root = _generate(sqlite_db, tmp_path / "en", {"trace_map": str(trace_map)}, locale="en")
    docs = root / "docs"

    assert (docs / "index.md").read_text(encoding="utf-8").startswith("# Database Documentation - ")
    orders = (docs / "tables" / "orders.md").read_text(encoding="utf-8")
    assert "# Table: orders" in orders
    assert "## Relationships (Foreign Keys)" in orders
    assert "## Indexes" in orders
    assert "| Constraint Name | Column | Referenced Table |" in orders
    assert "## Traceability" in orders
    assert "**Tags:** sales" in orders
    customers = (docs / "tables" / "customers.md").read_text(encoding="utf-8")
    assert "**Referenced by:**" in customers
    assert "# View: v_orders" in (docs / "views" / "v-orders.md").read_text(encoding="utf-8")
    traceability = (docs / "traceability.md").read_text(encoding="utf-8")
    assert "## Coverage" in traceability
    assert "no documented object has that name" in traceability
    toml = (root / "zensical.toml").read_text(encoding="utf-8")
    assert '{ "Home" = "index.md" }' in toml
    assert '{ "Traceability" = "traceability.md" }' in toml
    assert "# Database documentation" in (root / "README.md").read_text(encoding="utf-8")
    # Las anclas de columna y las rutas no dependen del idioma
    assert '<a id="col-customer-id"></a>' in orders
    assert "[customer_id](#col-customer-id)" in orders


def test_spanish_is_the_default(sqlite_db: Path, trace_map: Path, tmp_path: Path) -> None:
    root = _generate(sqlite_db, tmp_path / "es", {"trace_map": str(trace_map)})
    docs = root / "docs"

    assert (docs / "index.md").read_text(encoding="utf-8").startswith("# Documentación de la Base de Datos - ")
    orders = (docs / "tables" / "orders.md").read_text(encoding="utf-8")
    assert "# Tabla: orders" in orders
    assert "## Relaciones (Claves Foráneas)" in orders
    traceability = (docs / "traceability.md").read_text(encoding="utf-8")
    assert "no se documenta ningún objeto con ese nombre" in traceability
    assert '{ "Inicio" = "index.md" }' in (root / "zensical.toml").read_text(encoding="utf-8")


def _bare(text: str) -> str:
    """Texto sin marcas de Markdown (escapes y código) para comparar el título del manifiesto con el H1."""
    return text.replace("\\", "").replace("`", "")


def test_machine_data_does_not_depend_on_the_locale(sqlite_db: Path, trace_map: Path, tmp_path: Path) -> None:
    markdown = {"trace_map": str(trace_map)}
    es = _generate(sqlite_db, tmp_path / "es", markdown, locale="es")
    en = _generate(sqlite_db, tmp_path / "en", markdown, locale="en")

    catalog_es = json.loads((es / "docs" / "catalog.json").read_text(encoding="utf-8"))
    catalog_en = json.loads((en / "docs" / "catalog.json").read_text(encoding="utf-8"))
    assert catalog_es == catalog_en
    assert _front_matters(es) == _front_matters(en)
    assert _front_matters(es)  # hay front matter que comparar
    # Mismos ficheros (rutas y slugs) y mismas páginas en manifest.json; el título de cada página es su H1, en el idioma
    # de la generación (contrato de 5.4.0), y lo demás (path, section, role…) no cambia
    manifest_es = json.loads((es / "manifest.json").read_text(encoding="utf-8"))
    manifest_en = json.loads((en / "manifest.json").read_text(encoding="utf-8"))
    assert sorted(manifest_es["files"]) == sorted(manifest_en["files"])
    strip = [{k: v for k, v in page.items() if k != "title"} for page in manifest_es["pages"]]
    assert strip == [{k: v for k, v in page.items() if k != "title"} for page in manifest_en["pages"]]
    for page in manifest_en["pages"]:
        h1 = next(
            line
            for line in (en / "docs" / page["path"]).read_text(encoding="utf-8").splitlines()
            if line.startswith("# ")
        )
        assert _bare(page["title"]) == _bare(h1[2:]), page["path"]
    assert spanish_hits("\n".join(page["title"] for page in manifest_en["pages"])) == []


def test_previous_generation_in_another_locale_has_no_false_changes(sqlite_db: Path, tmp_path: Path) -> None:
    previous = _generate(sqlite_db, tmp_path / "es", {}, locale="es")
    root = _generate(sqlite_db, tmp_path / "en", {"previous": str(previous)}, locale="en")

    diff = json.loads((root / "docs" / "changes.json").read_text(encoding="utf-8"))
    assert diff["table_diffs"] == []
    assert diff["view_diffs"] == []
    assert diff["routine_diffs"] == []
    changes = (root / "docs" / "changes.md").read_text(encoding="utf-8")
    assert "# Schema changes" in changes
    assert "No schema changes." in changes
    assert spanish_hits(changes) == []


def test_previous_generation_in_another_locale_reports_real_changes(sqlite_db: Path, tmp_path: Path) -> None:
    previous = _generate(sqlite_db, tmp_path / "en", {}, locale="en")
    with sqlite3.connect(sqlite_db) as connection:
        connection.executescript("ALTER TABLE customers ADD COLUMN vip INTEGER; CREATE TABLE extra (id INTEGER);")
    root = _generate(sqlite_db, tmp_path / "es", {"previous": str(previous)}, locale="es")

    diff = json.loads((root / "docs" / "changes.json").read_text(encoding="utf-8"))
    assert [(t["table_name"], t["status"]) for t in diff["table_diffs"]] == [
        ("customers", "modified"),
        ("extra", "added"),
    ]
    changes = (root / "docs" / "changes.md").read_text(encoding="utf-8")
    assert "## Tabla [extra](tables/extra.md): añadida" in changes
    assert "| `vip` | existencia | `missing` | `exists` |" in changes


# --- Funciones de página (sin base de datos) ---


def test_index_pages_translate_labels_but_not_file_names() -> None:
    entries = [IndexEntry("alpha", "alpha.md", ""), IndexEntry("beta", "beta.md", ""), IndexEntry("#x", "x.md", "")]

    pages = index_pages("Tables", entries, 1, Translator("en"))

    assert set(pages) == {"index.md", "index-a.md", "index-b.md", "index-otros.md"}
    assert pages["index.md"][2] == "[Home](../index.md)"
    assert "| [OTHER](index-otros.md) | 1 |" in pages["index.md"]
    assert pages["index-a.md"][0] == "# Tables: A"
    assert pages["index-a.md"][2] == "[Index of tables](index.md)"
    assert index_pages("Tablas", entries, 1)["index-otros.md"][0] == "# Tablas: OTROS"


def test_traceability_reasons_are_stored_in_spanish_and_shown_in_the_page_locale() -> None:
    entry = TraceEntry(refs={"code": ("x.py",)})
    _, unmatched = TraceMap({"tables": {"ghost": entry}}).match("tables", ["real"])

    assert unmatched[0].reason == "no se documenta ningún objeto con ese nombre"
    english = "\n".join(traceability_page([], unmatched, Translator("en")))
    assert "| tables | ghost | no documented object has that name |" in english
    assert spanish_hits(english) == []


def test_changes_page_without_labels_uses_the_diff_labels() -> None:
    from util_bbdd.comparar.models import SchemaDiff

    page = changes_page(Changes(SchemaDiff(source_label="A", target_label="B")), {}, Translator("en"))

    assert page[:6] == ["# Schema changes", "", "|  |  |", "|---|---|", "| Previous | A |", "| Current | B |"]
