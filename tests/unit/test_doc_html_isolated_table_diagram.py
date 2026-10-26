"""El sitio HTML dibuja también las tablas sin relaciones, como Word (util_bbdd_web G38, 4.1.0).

``pipe_level_graphs_ext`` devuelve un diagrama por nivel y sentido; una tabla sin FK no tiene niveles y el HTML
omitía la sección «Diagrama de relaciones» sin aviso, mientras Word dibujaba la tabla sola.
"""

from __future__ import annotations

import sqlite3

from pathlib import Path

import pytest

pytest.importorskip("graphviz")

from util_bbdd import SyncDatabaseManager  # noqa: E402
from util_bbdd.doc import DatabaseDocumentation  # noqa: E402

pytestmark = pytest.mark.unit

IMPRIMIR = {"tablas": {"imprimir_tablas": True, "columnas": True}, "grafo": {"enabled": True}}


@pytest.fixture
def sqlite_db(tmp_path: Path) -> Path:
    path = tmp_path / "demo.db"
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id));
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
        """
    )
    con.close()
    return path


def test_table_without_relations_has_its_diagram_in_html(sqlite_db: Path, tmp_path: Path) -> None:
    with SyncDatabaseManager("sqlite", {"database": str(sqlite_db)}, use_pool=False) as manager:
        result = DatabaseDocumentation(
            manager,
            directorio_salida=tmp_path / "out",
            fichero_salida=Path("demo"),
            imprimir=IMPRIMIR,
            formatos=["html"],
        ).generate()

    tables_dir = result.outputs["html"] / "tables"
    settings_page = next(tables_dir.glob("settings*.html")).read_text(encoding="utf-8")
    orders_page = next(tables_dir.glob("orders*.html")).read_text(encoding="utf-8")

    assert "Sin relaciones" in settings_page
    assert "<svg" in settings_page and ">settings<" in settings_page  # el nodo de la tabla, dibujado
    assert "Sin relaciones" not in orders_page  # con relaciones, los grupos de siempre
    assert "Salida" in orders_page or "Entrada" in orders_page
    assert list((result.outputs["html"] / "graphs").glob("graphviz_ext_settings*_isolated_*.svg"))
    assert '<span class="diagram-tab-meta">1/1</span>' in settings_page


def test_pipe_level_graphs_reports_the_isolated_table(sqlite_db: Path) -> None:
    from util_bbdd.analysis.graphviz_ext import GraphvizRelationshipGraphExt

    with SyncDatabaseManager("sqlite", {"database": str(sqlite_db)}, use_pool=False) as manager:
        generator = GraphvizRelationshipGraphExt(manager)
        isolated = generator.pipe_level_graphs_ext("settings", format="svg")
        related = generator.pipe_level_graphs_ext("orders", format="svg")

    assert (isolated["outgoing"], isolated["incoming"]) == ([], [])
    assert [item["title"] for item in isolated["isolated"]] == ["Tabla sin relaciones"]
    assert b"<svg" in isolated["isolated"][0]["bytes"]
    assert related["isolated"] == []


def test_level_graphs_on_disk_include_the_isolated_table(sqlite_db: Path, tmp_path: Path) -> None:
    from util_bbdd.analysis.graphviz_ext import GraphvizRelationshipGraphExt

    with SyncDatabaseManager("sqlite", {"database": str(sqlite_db)}, use_pool=False) as manager:
        written = GraphvizRelationshipGraphExt(manager).generate_graphviz_level_graphs_ext("settings", tmp_path)

    assert [item["path"].is_file() for item in written["isolated"]] == [True]
