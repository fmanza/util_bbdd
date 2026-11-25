"""Idioma del sitio HTML de ``DatabaseDocumentation`` (plantillas Jinja2 y ``HtmlGenerator``) (5.10.0)."""

from __future__ import annotations

import re

from pathlib import Path

import pytest

from _leftovers import spanish_hits

from util_bbdd import SyncDatabaseManager
from util_bbdd._core.i18n import Translator
from util_bbdd.doc import DatabaseDocumentation
from util_bbdd.doc.infrastructure.renderers.shared.template_engine import TemplateEngine, js_string, routine_label

#: Recomendaciones de ``EngineReadinessAdvisor`` (módulo ``connection``): fuera del alcance de la i18n de resultados.
ADVISOR_TEXT = ("PRAGMA",)
TEMPLATES_ROOT = Path(__file__).resolve().parents[3] / "src" / "util_bbdd" / "doc" / "templates"

SCHEMA = """
CREATE TABLE customers (id INTEGER PRIMARY KEY, name VARCHAR(80) NOT NULL, email VARCHAR(120) UNIQUE);
CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id), total NUMERIC(10,2));
CREATE INDEX ix_orders_customer ON orders(customer_id);
CREATE VIEW v_orders AS SELECT o.id, c.name FROM orders o JOIN customers c ON c.id = o.customer_id;
CREATE TRIGGER trg_orders AFTER INSERT ON orders BEGIN UPDATE orders SET total = total WHERE id = NEW.id; END;
INSERT INTO customers VALUES (1, 'Ann', 'ann@example.com');
INSERT INTO orders VALUES (1, 1, 20.25);
"""

#: Todas las secciones de ``docs/api/database_documentation.md`` salvo ``grafo`` (no depende de Graphviz).
IMPRIMIR = {
    "tablas": {
        "imprimir_tablas": True,
        "ddl": True,
        "columnas": True,
        "pk": True,
        "fk": True,
        "unicas": True,
        "indices": True,
    },
    "vistas": {"imprimir_vistas": True, "ddl": True, "columnas": True},
    "rutinas": {"imprimir_procedures": True, "imprimir_function": True},
    "info_database": {"imprimir_info_database": True, "version": True, "charset_collation": True},
    "columnas_charset": {"charset_collation": True},
    "almacenamiento": {"imprimir_almacenamiento": True},
    "condiciones_motor": {"imprimir_condiciones_motor": True},
    "grafo": {"enabled": False},
}


@pytest.fixture(scope="module")
def sites(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Sitio HTML generado en ``es`` y en ``en`` sobre la misma base SQLite."""
    root = tmp_path_factory.mktemp("doc_html_locale")
    db = root / "shop.db"
    import sqlite3

    with sqlite3.connect(db) as raw:
        raw.executescript(SCHEMA)
    result: dict[str, Path] = {}
    for locale in ("es", "en"):
        manager = SyncDatabaseManager(db_type="sqlite", conn_params={"database": str(db)}, use_pool=False)
        try:
            DatabaseDocumentation(
                manager,
                directorio_salida=root / locale,
                fichero_salida=Path("doc"),
                imprimir=IMPRIMIR,
                formatos=["html"],
                locale=locale,  # type: ignore[arg-type]
            ).generate()
        finally:
            manager.close()
        result[locale] = root / locale / "doc" / "HTML"
    return result


def _pages(site: Path) -> list[Path]:
    return sorted(path for path in site.rglob("*.html") if path.is_file())


def _visible(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_english_site_has_lang_and_no_spanish(sites: dict[str, Path]) -> None:
    pages = _pages(sites["en"])
    assert len(pages) > 8
    hits = {page.name: spanish_hits(_visible(page), ADVISOR_TEXT) for page in pages}
    assert {name: found for name, found in hits.items() if found} == {}
    for page in pages:
        text = _visible(page)
        assert '<html lang="en">' in text
        assert "'es'" not in text  # localeCompare usa el idioma de salida


def test_spanish_is_the_default_and_keeps_its_texts(sites: dict[str, Path]) -> None:
    index = _visible(sites["es"] / "index.html")
    assert '<html lang="es">' in index
    assert "Índice de documentación - " in index
    assert "Contraer panel lateral" in index
    collection = _visible(sites["es"] / "collections" / "tables_all.html")
    assert "localeCompare(b, 'es'," in collection
    assert "'Página ' + currentPage" in collection
    table = _visible(sites["es"] / "tables" / "orders.html")
    assert "<h1>Tabla: orders</h1>" in table
    assert "Relaciones (Claves Foráneas)" in table


def test_english_key_texts(sites: dict[str, Path]) -> None:
    index = _visible(sites["en"] / "index.html")
    assert "Documentation index - " in index
    assert "Collapse side panel" in index
    collection = _visible(sites["en"] / "collections" / "tables_all.html")
    assert "localeCompare(b, 'en'," in collection
    assert "'Page ' + currentPage" in collection
    assert '<sheet name="Data"' in collection
    table = _visible(sites["en"] / "tables" / "orders.html")
    assert "<h1>Table: orders</h1>" in table
    assert "Relationships (Foreign Keys)" in table
    assert "'DDL copied'" in table


def test_css_classes_do_not_depend_on_locale(sites: dict[str, Path]) -> None:
    """``header_key`` (clases de cabecera, p. ej. ``is-comment-column``) da las mismas clases en los dos idiomas."""
    es_pages = {page.relative_to(sites["es"]) for page in _pages(sites["es"])}
    en_pages = {page.relative_to(sites["en"]) for page in _pages(sites["en"])}
    assert es_pages == en_pages
    class_attr = re.compile(r'class="([^"]*)"')
    for rel in sorted(es_pages):
        es_classes = class_attr.findall(_visible(sites["es"] / rel))
        en_classes = class_attr.findall(_visible(sites["en"] / rel))
        assert es_classes == en_classes, rel
    collection = _visible(sites["en"] / "collections" / "views_all.html")
    assert "is-comment-column" in collection
    assert "Open detail" in collection


def test_template_engine_helpers_follow_the_translator() -> None:
    assert routine_label("function") == "Función"
    assert routine_label("function", Translator("en")) == "Function"
    assert routine_label("", Translator("en")) == "Routine"
    assert js_string("Página") == "Página"
    assert js_string("it's <b>") == "it\\'s \\u003Cb\\u003E"

    engine = TemplateEngine(TEMPLATES_ROOT, translator=Translator("en"), header_aliases={"Comment": "Comentario"})
    assert engine.environment.globals["lang"] == "en"
    assert engine.environment.filters["header_key"]("Comment") == "comentario"
    assert engine.environment.filters["routine_label"]("PROCEDURE") == "Procedure"
