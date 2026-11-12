"""``manifest.json`` → ``pages`` (5.4.0, G51 de util_bbdd_web): índice de todas las páginas de la documentación Markdown."""

from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3

from pathlib import Path
from typing import Any

import pytest

from util_bbdd.doc.database_documentation import DatabaseDocumentation
from util_bbdd.managers import SyncDatabaseManager

pytestmark = pytest.mark.unit

IMPRIMIR: dict[str, Any] = {
    "tablas": {"imprimir_tablas": True, "columnas": True, "fk": True},
    "vistas": {"imprimir_vistas": True, "columnas": True},
    "info_database": {"imprimir_info_database": True},
    "grafo": {"enabled": True},
}

# Nombres con caracteres que md_text escapa (_ al borde, |, *, <, &) y dos tablas en la «a» para paginar
TABLES = ["ACM_AGENDA", "acm_otra", "_raro_", "b|c*d", "<e&f>"]
SCHEMA = (
    "\n".join(f'CREATE TABLE "{name}" (id INTEGER PRIMARY KEY);' for name in TABLES)
    + '\nCREATE VIEW "v_x" AS SELECT id FROM "ACM_AGENDA";'
)


@pytest.fixture
def sqlite_db(tmp_path: Path) -> Path:
    db = tmp_path / "ventas.db"
    with sqlite3.connect(db) as connection:
        connection.executescript(SCHEMA)
    return db


def _generate(db: Path, out: Path, imprimir: dict[str, Any] | None = None) -> Path:
    with SyncDatabaseManager("sqlite", {"database": str(db)}, use_pool=False) as manager:
        result = DatabaseDocumentation(
            manager, out, Path("demo"), imprimir=imprimir or IMPRIMIR, formatos=["markdown"]
        ).generate()
    return result.outputs["markdown"]


def _manifest(root: Path) -> dict[str, Any]:
    return dict(json.loads((root / "manifest.json").read_text(encoding="utf-8")))


def _h1(page: Path) -> str:
    """H1 de la página sin los escapes de ``md_text`` (solo para comparar en el test)."""
    line = next(line for line in page.read_text(encoding="utf-8").splitlines() if line.startswith("# "))
    return html.unescape(re.sub(r"\\(.)", r"\1", line[2:]))


def test_pages_list_every_markdown_page_once(sqlite_db: Path, tmp_path: Path) -> None:
    root = _generate(sqlite_db, tmp_path / "out", {**IMPRIMIR, "markdown": {"index_page_size": 1}})
    manifest = _manifest(root)

    assert manifest["format"] == "util_bbdd.doc.markdown"
    assert manifest["format_version"] == 2
    paths = [page["path"] for page in manifest["pages"]]
    assert len(paths) == len(set(paths))
    # Páginas del sitio: los .md de docs/ (README.md, desde 5.5.0, queda en la raíz y no es una página)
    markdown_files = {
        name.removeprefix("docs/") for name in manifest["files"] if name.startswith("docs/") and name.endswith(".md")
    }
    assert set(paths) == markdown_files
    assert "README.md" in manifest["files"]


def test_titles_are_plain_text_and_match_the_h1(sqlite_db: Path, tmp_path: Path) -> None:
    # T5: el título es el del H1 sin escapes ni entidades (ACM_AGENDA, no ACM\_AGENDA)
    root = _generate(sqlite_db, tmp_path / "out")
    pages = _manifest(root)["pages"]

    objects = {page["title"] for page in pages if page["role"] == "object"}
    assert objects == {*(f"Tabla: {name}" for name in TABLES), "Vista: v_x"}
    for page in pages:
        assert page["title"] == _h1(root / "docs" / page["path"]), page["path"]
    for title in objects:  # la portada lleva el nombre de la BD, que en SQLite es su ruta (con «\» en Windows)
        assert "\\" not in title
        assert "&amp;" not in title
        assert "&lt;" not in title


def test_order_sections_roles_and_letters(sqlite_db: Path, tmp_path: Path) -> None:
    root = _generate(sqlite_db, tmp_path / "out", {**IMPRIMIR, "markdown": {"index_page_size": 1}})
    pages = _manifest(root)["pages"]

    assert [(page["section"], page["role"]) for page in pages][:2] == [("home", "home"), ("tables", "index")]
    sections = [page["section"] for page in pages]
    assert sections == sorted(sections, key=["home", "tables", "views", "database"].index)
    tables = [page for page in pages if page["section"] == "tables"]
    roles = [page["role"] for page in tables]
    assert roles == sorted(roles, key=["index", "letter", "object"].index)
    letters = [(page["path"], page["letter"], page["title"]) for page in tables if page["role"] == "letter"]
    assert ("tables/index-a.md", "a", "Tablas: A (1 de 2)") in letters
    assert ("tables/index-a-2.md", "a", "Tablas: A (2 de 2)") in letters
    assert next(page for page in pages if page["path"] == "database/info.md") == {
        "path": "database/info.md",
        "title": "Información de la Base de Datos",
        "section": "database",
        "role": "page",
    }


def test_object_ids_match_the_catalog_even_without_it(sqlite_db: Path, tmp_path: Path) -> None:
    root = _generate(sqlite_db, tmp_path / "with")
    catalog = json.loads((root / "docs/catalog.json").read_text(encoding="utf-8"))
    expected = {obj["path"]: (obj["id"], obj["kind"]) for obj in catalog["objects"]}

    objects = {p["path"]: (p["id"], p["kind"]) for p in _manifest(root)["pages"] if p["role"] == "object"}
    assert objects == expected
    assert all("letter" not in p for p in _manifest(root)["pages"] if p["role"] == "object")

    bare = _generate(
        sqlite_db, tmp_path / "without", {**IMPRIMIR, "markdown": {"catalog_json": False, "front_matter": False}}
    )
    bare_objects = {p["path"]: (p["id"], p["kind"]) for p in _manifest(bare)["pages"] if p["role"] == "object"}
    assert bare_objects == expected


def test_pages_are_deterministic(sqlite_db: Path, tmp_path: Path) -> None:
    first = _manifest(_generate(sqlite_db, tmp_path / "a"))["pages"]
    second = _manifest(_generate(sqlite_db, tmp_path / "b"))["pages"]

    assert first == second


def test_traceability_and_changes_pages(sqlite_db: Path, tmp_path: Path) -> None:
    trace = tmp_path / "trace.toml"
    trace.write_text('[tables.ACM_AGENDA]\nrequirements = ["REQ-1"]\n', encoding="utf-8")
    root = _generate(sqlite_db, tmp_path / "out")
    root = _generate(
        sqlite_db, tmp_path / "out", {**IMPRIMIR, "markdown": {"trace_map": str(trace), "previous": str(root)}}
    )

    tail = [(p["path"], p["title"], p["section"], p["role"]) for p in _manifest(root)["pages"]][-2:]
    assert tail == [
        ("traceability.md", "Trazabilidad", "traceability", "page"),
        ("changes.md", "Cambios de esquema", "changes", "page"),
    ]


def test_regenerating_over_a_v1_manifest_still_removes_orphans(sqlite_db: Path, tmp_path: Path) -> None:
    # T6: el manifiesto 5.3.0 (format_version 1, sin pages) se sigue leyendo para limpiar lo que ya no se genera
    root = _generate(sqlite_db, tmp_path / "out")
    orphan = root / "docs" / "tables" / "vieja.md"
    orphan.write_text("# Tabla: vieja\n", encoding="utf-8")
    manifest = _manifest(root)
    del manifest["pages"]
    manifest["format_version"] = 1
    manifest["files"]["docs/tables/vieja.md"] = f"sha256:{hashlib.sha256(orphan.read_bytes()).hexdigest()}"
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    root = _generate(sqlite_db, tmp_path / "out")

    assert not orphan.exists()
    assert _manifest(root)["format_version"] == 2
