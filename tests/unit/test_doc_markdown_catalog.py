"""``catalog.json`` (ADR-006), ``llms.txt``/``llms-full.txt`` y ``mkdocs.yml`` de la documentación Markdown (5.3.0, grupo C)."""

from __future__ import annotations

import hashlib
import json
import sqlite3

from pathlib import Path
from typing import Any

import pytest
import yaml

from util_bbdd.doc.database_documentation import DatabaseDocumentation
from util_bbdd.exceptions import DocumentationConfigError
from util_bbdd.managers import SyncDatabaseManager

pytestmark = pytest.mark.unit

IMPRIMIR: dict[str, Any] = {
    "tablas": {"imprimir_tablas": True, "columnas": True, "fk": True},
    "vistas": {"imprimir_vistas": True, "columnas": True},
    "grafo": {"enabled": True},
}

SCHEMA = """
CREATE TABLE clientes (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL DEFAULT 'anónimo', codigo TEXT UNIQUE);
CREATE TABLE pedidos (
    id INTEGER PRIMARY KEY,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE
);
CREATE INDEX ix_pedidos_cliente ON pedidos (cliente_id);
CREATE VIEW v_pedidos AS SELECT id FROM pedidos;
"""


@pytest.fixture
def sqlite_db(tmp_path: Path) -> Path:
    db = tmp_path / "ventas.db"
    with sqlite3.connect(db) as connection:
        connection.executescript(SCHEMA)
    return db


def _generate(db: Path, out: Path, imprimir: dict[str, Any] | None = None, name: str = "demo") -> Path:
    with SyncDatabaseManager("sqlite", {"database": str(db)}, use_pool=False) as manager:
        result = DatabaseDocumentation(
            manager, out, Path(name), imprimir=imprimir or IMPRIMIR, formatos=["markdown"]
        ).generate()
    return result.outputs["markdown"]


def _front_matter(page: Path) -> dict[str, Any]:
    return dict(json.loads(page.read_text(encoding="utf-8").split("\n")[1]))


# --- catalog.json ---


def test_catalog_content(sqlite_db: Path, tmp_path: Path) -> None:
    root = _generate(sqlite_db, tmp_path / "out")
    catalog = json.loads((root / "docs/catalog.json").read_text(encoding="utf-8"))

    assert (catalog["format"], catalog["format_version"], catalog["engine"]) == ("util_bbdd.doc.catalog", 1, "sqlite")
    assert catalog["selection"] == {"tables": True, "views": True, "procedures": False, "functions": False}
    assert [o["id"] for o in catalog["objects"]] == [
        "table:main.clientes",
        "table:main.pedidos",
        "view:main.v_pedidos",
    ]
    clientes, pedidos, vista = catalog["objects"]
    nombre = next(c for c in clientes["columns"] if c["name"] == "nombre")
    assert (nombre["nullable"], nombre["default"]) == (False, "'anónimo'")
    assert clientes["fk_in"] == ["table:main.pedidos"]
    assert pedidos["fk_out"][0] | {"name": ""} == {
        "name": "",
        "columns": ["cliente_id"],
        "ref": "table:main.clientes",
        "ref_columns": ["id"],
        "on_delete": "CASCADE",
        "on_update": "NO ACTION",
    }
    assert {"name": "ix_pedidos_cliente", "columns": ["cliente_id"]}.items() <= pedidos["indexes"][0].items()
    assert pedidos["path"] == "tables/pedidos.md"
    assert vista["definition_hash"].startswith("sha256:")
    # Mismo id y hash que el front matter de la página
    front = _front_matter(root / "docs" / pedidos["path"])
    assert (front["id"], front["hash"]) == (pedidos["id"], pedidos["hash"])


def test_catalog_is_deterministic_and_optional(sqlite_db: Path, tmp_path: Path) -> None:
    first = (_generate(sqlite_db, tmp_path / "a") / "docs/catalog.json").read_bytes()
    second = (_generate(sqlite_db, tmp_path / "b") / "docs/catalog.json").read_bytes()
    assert first == second

    root = _generate(sqlite_db, tmp_path / "c", {**IMPRIMIR, "markdown": {"catalog_json": False}})
    assert not (root / "docs/catalog.json").exists()
    assert "docs/catalog.json" not in json.loads((root / "manifest.json").read_text(encoding="utf-8"))["files"]
    assert "catalog.json" not in (root / "docs/llms.txt").read_text(encoding="utf-8")


# --- llms.txt / llms-full.txt ---


def test_llms_txt_structure(sqlite_db: Path, tmp_path: Path) -> None:
    root = _generate(sqlite_db, tmp_path / "out")
    lines = (root / "docs/llms.txt").read_text(encoding="utf-8").split("\n")

    assert lines[0].startswith("# Documentación de la base de datos ")
    assert lines[2].startswith("> Schema main (sqlite): 2 tablas, 1 vistas, 0 rutinas.")
    assert "## Tablas" in lines and "## Vistas" in lines and "## Rutinas" not in lines
    assert "- [pedidos](tables/pedidos.md)" in lines
    assert "- [v\\_pedidos](views/v-pedidos.md)" not in lines and "- [v_pedidos](views/v-pedidos.md)" in lines
    assert lines[lines.index("## Optional") + 2].startswith("- [Catálogo JSON](catalog.json)")


def test_llms_full_txt_streams_every_page(sqlite_db: Path, tmp_path: Path) -> None:
    root = _generate(sqlite_db, tmp_path / "out")
    full = (root / "docs/llms-full.txt").read_bytes()
    text = full.decode("utf-8")

    assert text.startswith("# Documentación de la Base de Datos - ")
    markers = [line for line in text.split("\n") if line.startswith("<!-- ")]
    assert markers == [
        "<!-- table:main.clientes · tables/clientes.md -->",
        "<!-- table:main.pedidos · tables/pedidos.md -->",
        "<!-- view:main.v_pedidos · views/v-pedidos.md -->",
    ]
    assert '"hash":' not in text  # sin front matter
    assert "```mermaid" in text
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"]["docs/llms-full.txt"] == f"sha256:{hashlib.sha256(full).hexdigest()}"


# --- mkdocs.yml y Mermaid local ---


def test_mkdocs_yml_with_hostile_site_name_and_local_mermaid(sqlite_db: Path, tmp_path: Path) -> None:
    mermaid = tmp_path / "mermaid.min.js"
    mermaid.write_text("window.mermaid = {};\n", encoding="utf-8")
    site_name = 'Ventas "prod": a\nb: !!python/object x'
    root = _generate(
        sqlite_db, tmp_path / "out", {**IMPRIMIR, "markdown": {"site_name": site_name, "mermaid_js": str(mermaid)}}
    )

    config = yaml.unsafe_load((root / "mkdocs.yml").read_text(encoding="utf-8"))  # el tag !!python/name lo exige
    assert config["site_name"] == site_name
    assert config["docs_dir"] == "docs"
    assert config["extra_javascript"] == ["assets/javascripts/mermaid.min.js"]
    assert (root / "docs/assets/javascripts/mermaid.min.js").read_bytes() == mermaid.read_bytes()
    # nav corta (portada e índices) y, con Mermaid local (sitio sin Internet), sin Google Fonts
    assert config["nav"] == [{"Inicio": "index.md"}, {"Tablas": "tables/index.md"}, {"Vistas": "views/index.md"}]
    assert config["theme"] == {"name": "material", "font": False}


def test_mkdocs_yml_without_local_mermaid_keeps_theme_fonts(sqlite_db: Path, tmp_path: Path) -> None:
    root = _generate(sqlite_db, tmp_path / "out")
    config = yaml.unsafe_load((root / "mkdocs.yml").read_text(encoding="utf-8"))

    assert config["theme"] == {"name": "material"}
    assert "extra_javascript" not in config


def test_missing_mermaid_js_fails_before_generating(sqlite_db: Path, tmp_path: Path) -> None:
    with (
        SyncDatabaseManager("sqlite", {"database": str(sqlite_db)}, use_pool=False) as manager,
        pytest.raises(DocumentationConfigError, match="mermaid_js"),
    ):
        DatabaseDocumentation(
            manager,
            tmp_path / "out",
            imprimir={**IMPRIMIR, "markdown": {"mermaid_js": str(tmp_path / "no-existe.js")}},
            formatos=["markdown"],
        )

    assert not (tmp_path / "out").exists()
