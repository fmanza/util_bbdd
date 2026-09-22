"""Unit tests for the standalone Jinja2 template engine."""

from pathlib import Path

from util_bbdd.doc.infrastructure.renderers.shared.template_engine import (
    TemplateEngine,
    header_key,
    routine_label,
    status_class,
)


def _build_engine() -> TemplateEngine:
    templates_root = Path(__file__).resolve().parents[2] / "src" / "util_bbdd" / "doc" / "templates"
    return TemplateEngine(templates_root=templates_root)


def test_template_engine_loads_index_template() -> None:
    engine = _build_engine()

    template = engine.get_template("pages/index.html.j2")

    assert template.name == "pages/index.html.j2"


def test_template_engine_renders_collection_page_with_expected_data() -> None:
    engine = _build_engine()

    rendered = engine.render(
        "pages/collection.html.j2",
        database="SOCYALPRO",
        generated_at="2026-03-18 10:00:00",
        collection_key="tables",
        title="Todas las tablas y columnas",
        headers=["Tabla", "Comentario", "Detalle"],
        rows=[["CORE_USUARIOS", "Usuarios del sistema", "tables/core_usuarios.html"]],
    )

    assert "Todas las tablas y columnas" in rendered
    assert "SOCYALPRO" in rendered
    assert "CORE_USUARIOS" in rendered
    assert "Abrir detalle" in rendered
    assert "exportCsv" in rendered
    assert "XLSX" in rendered
    assert 'data-tooltip="Exportar resultados filtrados a CSV"' in rendered
    assert 'data-tooltip="Ir a página anterior"' in rendered


def test_template_engine_renders_index_page_with_expected_links() -> None:
    engine = _build_engine()

    rendered = engine.render(
        "pages/index.html.j2",
        database="SOCYALPRO",
        generated_at="2026-03-18 10:00:00",
        page_size=15,
        tables=[{"name": "CORE_USUARIOS", "comment": "Usuarios", "path": "tables/core_usuarios.html"}],
        views=[],
        procedures=[],
        functions=[],
        storage=[],
        storage_total_rows=0,
        database_info=[],
        default_content_path="tables/core_usuarios.html",
        inventory_summary=[{"label": "Tablas", "count": 1, "accent": "tables", "collection_key": "tables"}],
        collection_links={"tables": "collections/tables_all.html"},
    )

    assert "Índice de documentación - SOCYALPRO" in rendered
    assert "collections/tables_all.html" in rendered
    assert "CORE_USUARIOS" in rendered


def test_template_engine_autoescapes_html_payloads_in_j2_templates() -> None:
    """DOC-01 (AUDIT_CODE 2026-09-22): select_autoescape() solo miraba ".html"/".xml", pero
    todas las plantillas reales se nombran "*.html.j2", así que el autoescape nunca se activaba
    y un nombre/comentario de tabla con HTML/JS se insertaba sin escapar en el documento generado.
    """
    engine = _build_engine()

    rendered = engine.render(
        "pages/collection.html.j2",
        database="<script>alert(1)</script>",
        generated_at="2026-03-18 10:00:00",
        collection_key="tables",
        title="Todas las tablas y columnas",
        headers=["Tabla", "Comentario", "Detalle"],
        rows=[["<img src=x onerror=alert(2)>", "'; DROP TABLE x; --", "tables/x.html"]],
    )

    assert "<script>alert(1)</script>" not in rendered
    assert "<img src=x onerror=alert(2)>" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert "&lt;img src=x onerror=alert(2)&gt;" in rendered


def test_template_engine_filters_normalize_values() -> None:
    assert header_key("Comentario columna") == "comentario-columna"
    assert status_class("NOT_SUPPORTED") == "not-supported"
    assert routine_label("procedure") == "Procedure"
    assert routine_label("function") == "Función"
