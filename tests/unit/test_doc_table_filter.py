"""Filtro de tablas y vistas con frontera, relaciones entrantes y ``README.md`` del Markdown (5.5.0)."""

from __future__ import annotations

import json
import sqlite3

from pathlib import Path
from typing import Any

import pytest

from util_bbdd.doc.database_documentation import DatabaseDocumentation
from util_bbdd.doc.domain.models import DocumentationResult
from util_bbdd.doc.domain.table_filter import TableFilter
from util_bbdd.exceptions import DocumentationConfigError
from util_bbdd.managers import SyncDatabaseManager

pytestmark = pytest.mark.unit

# AUX_PAIS ← MVG_CLIENTE ← MVG_PEDIDO ← COB_LINEA; MVG_PEDIDO_BAK → MVG_PEDIDO (excluida); OTRA, sin relaciones
SCHEMA = """
CREATE TABLE AUX_PAIS (id INTEGER PRIMARY KEY);
CREATE TABLE MVG_CLIENTE (id INTEGER PRIMARY KEY, pais_id INTEGER REFERENCES AUX_PAIS(id));
CREATE TABLE MVG_PEDIDO (id INTEGER PRIMARY KEY, cliente_id INTEGER REFERENCES MVG_CLIENTE(id));
CREATE TABLE COB_LINEA (id INTEGER PRIMARY KEY, pedido_id INTEGER REFERENCES MVG_PEDIDO(id));
CREATE TABLE MVG_PEDIDO_BAK (id INTEGER PRIMARY KEY, pedido_id INTEGER REFERENCES MVG_PEDIDO(id));
CREATE TABLE OTRA (id INTEGER PRIMARY KEY);
CREATE VIEW mvg_v_pedidos AS SELECT id FROM MVG_PEDIDO;
CREATE VIEW cob_v_lineas AS SELECT id FROM COB_LINEA;
"""

IMPRIMIR: dict[str, Any] = {
    "tablas": {"imprimir_tablas": True, "columnas": True, "fk": True},
    "vistas": {"imprimir_vistas": True, "columnas": True},
    "grafo": {"enabled": True},
}
FILTRO: dict[str, Any] = {"incluir": ["mvg_*"], "excluir": ["*_BAK"]}


@pytest.fixture
def sqlite_db(tmp_path: Path) -> Path:
    db = tmp_path / "ventas.db"
    with sqlite3.connect(db) as connection:
        connection.executescript(SCHEMA)
    return db


def _generate(db: Path, out: Path, imprimir: dict[str, Any], formatos: list[str] | None = None) -> DocumentationResult:
    with SyncDatabaseManager("sqlite", {"database": str(db)}, use_pool=False) as manager:
        return DatabaseDocumentation(
            manager, out, Path("demo"), imprimir=imprimir, formatos=formatos or ["markdown"]
        ).generate()


def _json(path: Path) -> dict[str, Any]:
    return dict(json.loads(path.read_text(encoding="utf-8")))


# --- TableFilter -------------------------------------------------------------


def test_filter_matches_case_insensitive_and_exclude_wins() -> None:
    table_filter = TableFilter.from_config({"incluir": "MVG_*", "excluir": ["*_bak"]})

    assert table_filter is not None
    assert table_filter.matches("mvg_pedido")
    assert table_filter.matches("MVG_PEDIDO")
    assert not table_filter.matches("MVG_PEDIDO_BAK")
    assert not table_filter.matches("COB_LINEA")


def test_filter_without_include_keeps_everything_but_excluded() -> None:
    table_filter = TableFilter.from_config({"excluir": ["TMP_?", "*_BAK"]})

    assert table_filter is not None
    assert table_filter.matches("COB_LINEA")
    assert not table_filter.matches("tmp_1")
    assert table_filter.matches("TMP_12")  # ``?`` es un solo carácter


@pytest.mark.parametrize("value", [None, {}, {"incluir": [], "excluir": []}])
def test_filter_without_patterns_is_none(value: Any) -> None:
    assert TableFilter.from_config(value) is None


@pytest.mark.parametrize(
    "value",
    [
        "MVG_*",
        {"incluir": [1]},
        {"incluir": [""]},
        {"excluir": ["a\tb"]},
        {"incluir": ["x" * 129]},
        {"incluir": [f"T{i}" for i in range(101)]},
        {"incluir": {"MVG_*": True}},
    ],
)
def test_filter_rejects_invalid_config(value: Any) -> None:
    with pytest.raises(ValueError, match="filtro"):
        TableFilter.from_config(value)


def test_frontier_is_both_directions_without_excluded_or_selected() -> None:
    table_filter = TableFilter(include=("MVG_*",), exclude=("*_BAK",))
    edges = [
        ("MVG_CLIENTE", "AUX_PAIS"),
        ("MVG_PEDIDO", "MVG_CLIENTE"),
        ("COB_LINEA", "MVG_PEDIDO"),
        ("MVG_PEDIDO_BAK", "MVG_PEDIDO"),
        ("COB_LINEA", "AUX_PAIS"),
    ]

    assert table_filter.frontier_of(["MVG_CLIENTE", "MVG_PEDIDO"], edges) == ["AUX_PAIS", "COB_LINEA"]


def test_invalid_pattern_is_a_config_error_at_construction(sqlite_db: Path, tmp_path: Path) -> None:
    with SyncDatabaseManager("sqlite", {"database": str(sqlite_db)}, use_pool=False) as manager:
        with pytest.raises(DocumentationConfigError, match="filtro.incluir"):
            DatabaseDocumentation(manager, tmp_path, imprimir={**IMPRIMIR, "filtro": {"incluir": [""]}})


# --- Generación ----------------------------------------------------------------


def test_filter_applies_to_markdown_with_frontier(sqlite_db: Path, tmp_path: Path) -> None:
    result = _generate(sqlite_db, tmp_path / "out", {**IMPRIMIR, "filtro": FILTRO})
    root = result.outputs["markdown"]
    docs = root / "docs"

    assert (result.tables, result.views) == (2, 1)
    assert result.frontier == ("AUX_PAIS", "COB_LINEA")
    assert sorted(p.name for p in (docs / "tables").glob("*.md") if not p.name.startswith("index")) == [
        "mvg-cliente.md",
        "mvg-pedido.md",
    ]
    home = (docs / "index.md").read_text(encoding="utf-8")
    assert "## Alcance" in home
    assert "`mvg_*`" in home and "`*_BAK`" in home
    assert "### Tablas de frontera" in home and "- AUX_PAIS" in home and "- COB_LINEA" in home

    pedido = (docs / "tables" / "mvg-pedido.md").read_text(encoding="utf-8")
    assert "[MVG_CLIENTE](mvg-cliente.md)" in pedido  # FK saliente documentada: enlace
    assert "**Referenciada por:**" in pedido
    assert "- COB_LINEA *(frontera, sin ficha)*" in pedido
    assert "- MVG_PEDIDO_BAK *(excluida por el filtro)*" in pedido

    catalog = _json(docs / "catalog.json")
    assert catalog["filter"] == {"include": ["mvg_*"], "exclude": ["*_BAK"]}
    assert catalog["frontier"] == ["AUX_PAIS", "COB_LINEA"]
    assert {o["name"] for o in catalog["objects"]} == {"MVG_CLIENTE", "MVG_PEDIDO", "mvg_v_pedidos"}
    manifest = _json(root / "manifest.json")
    assert manifest["filter"] == {"include": ["mvg_*"], "exclude": ["*_BAK"], "frontier": ["AUX_PAIS", "COB_LINEA"]}


def test_frontier_can_be_disabled(sqlite_db: Path, tmp_path: Path) -> None:
    result = _generate(sqlite_db, tmp_path / "out", {**IMPRIMIR, "filtro": {**FILTRO, "frontera": False}})
    home = (result.outputs["markdown"] / "docs" / "index.md").read_text(encoding="utf-8")

    assert result.frontier == ()
    assert "## Alcance" in home and "Tablas de frontera" not in home


def test_filter_applies_to_every_format(sqlite_db: Path, tmp_path: Path) -> None:
    result = _generate(sqlite_db, tmp_path / "out", {**IMPRIMIR, "grafo": {}, "filtro": FILTRO}, ["html", "excel"])

    pages = sorted(p.stem for p in (result.outputs["html"] / "tables").glob("*.html"))
    assert pages == ["mvg-cliente", "mvg-pedido"]
    assert result.tables == 2


def test_without_filter_output_is_unchanged(sqlite_db: Path, tmp_path: Path) -> None:
    result = _generate(sqlite_db, tmp_path / "out", IMPRIMIR)
    docs = result.outputs["markdown"] / "docs"

    assert result.tables == 6 and result.frontier == ()
    assert "## Alcance" not in (docs / "index.md").read_text(encoding="utf-8")
    catalog = _json(docs / "catalog.json")
    assert "filter" not in catalog and "frontier" not in catalog
    assert "filter" not in _json(result.outputs["markdown"] / "manifest.json")
    pedido = (docs / "tables" / "mvg-pedido.md").read_text(encoding="utf-8")
    assert "- [COB_LINEA](cob-linea.md)" in pedido  # entrante documentada: enlace, sin marca


def test_changes_ignore_objects_left_out_by_either_filter(sqlite_db: Path, tmp_path: Path) -> None:
    first = _generate(sqlite_db, tmp_path / "a", IMPRIMIR).outputs["markdown"]
    imprimir = {**IMPRIMIR, "filtro": FILTRO, "markdown": {"previous": str(first)}}
    docs = _generate(sqlite_db, tmp_path / "b", imprimir).outputs["markdown"] / "docs"

    diff = _json(docs / "changes.json")
    assert [d for d in diff["table_diffs"] if d["status"] == "removed"] == []
    assert [d for d in diff["view_diffs"] if d["status"] == "removed"] == []
    assert "distinto filtro de tablas" in (docs / "changes.md").read_text(encoding="utf-8")


# --- README.md -----------------------------------------------------------------


def test_readme_explains_how_to_view_and_lists_generated_files(sqlite_db: Path, tmp_path: Path) -> None:
    root = _generate(sqlite_db, tmp_path / "out", {**IMPRIMIR, "markdown": {"llms_full_txt": False}}).outputs[
        "markdown"
    ]
    readme = (root / "README.md").read_text(encoding="utf-8")

    assert "zensical serve" in readme and "`zensical.toml`" in readme
    assert "mkdocs" not in readme.lower()  # 5.6.0: solo Zensical
    assert "bierner.markdown-mermaid" in readme
    assert "`docs/catalog.json`" in readme
    assert "llms-full.txt" not in readme
    assert str(tmp_path) not in readme  # sin rutas locales
    assert "README.md" in _json(root / "manifest.json")["files"]


def test_readme_without_site_and_disabled(sqlite_db: Path, tmp_path: Path) -> None:
    root = _generate(sqlite_db, tmp_path / "a", {**IMPRIMIR, "markdown": {"zensical_toml": False}}).outputs["markdown"]
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "zensical" not in readme and "mkdocs.yml" not in readme

    only_yml = {**IMPRIMIR, "markdown": {"zensical_toml": False, "mkdocs_yml": True}}
    root = _generate(sqlite_db, tmp_path / "c", only_yml).outputs["markdown"]
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "zensical serve" in readme and "(la que tiene `mkdocs.yml`)" in readme  # Zensical lee también mkdocs.yml
    assert "en desuso" in readme

    root = _generate(sqlite_db, tmp_path / "b", {**IMPRIMIR, "markdown": {"readme": False}}).outputs["markdown"]
    assert not (root / "README.md").exists()
