"""Cambios de esquema respecto de una generación anterior (5.3.0, grupo E de la sesión ``2026-11-05-doc-markdown``).

Se compara el ``catalog.json`` de la generación anterior con la actual, sin conexión a la base de datos.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess

from pathlib import Path
from typing import Any

import pytest

from util_bbdd.comparar.models import SchemaDiff
from util_bbdd.doc.database_documentation import DatabaseDocumentation
from util_bbdd.exceptions import DocumentationConfigError
from util_bbdd.managers import SyncDatabaseManager

pytestmark = pytest.mark.unit

IMPRIMIR: dict[str, Any] = {
    "tablas": {"imprimir_tablas": True, "columnas": True},
    "vistas": {"imprimir_vistas": True},
}

BEFORE = """
CREATE TABLE clientes (id INTEGER PRIMARY KEY, nombre TEXT, alta TEXT DEFAULT 'x');
CREATE TABLE pedidos (id INTEGER PRIMARY KEY, cliente_id INTEGER REFERENCES clientes(id));
CREATE TABLE "vieja <b>" (id INTEGER PRIMARY KEY);
CREATE VIEW v_pedidos AS SELECT id FROM pedidos;
"""

AFTER = """
DROP TABLE "vieja <b>";
ALTER TABLE clientes ADD COLUMN email TEXT;
CREATE TABLE nueva (id INTEGER PRIMARY KEY);
CREATE INDEX ix_pedidos_cliente ON pedidos (cliente_id);
DROP VIEW v_pedidos;
CREATE VIEW v_pedidos AS SELECT id, cliente_id FROM pedidos;
"""


@pytest.fixture
def sqlite_db(tmp_path: Path) -> Path:
    db = tmp_path / "ventas.db"
    with sqlite3.connect(db) as connection:
        connection.executescript(BEFORE)
    return db


def _generate(db: Path, out: Path, name: str, markdown: dict[str, Any] | None = None, **imprimir: Any) -> Path:
    config = {**IMPRIMIR, **imprimir, "markdown": markdown or {}}
    with SyncDatabaseManager("sqlite", {"database": str(db)}, use_pool=False) as manager:
        result = DatabaseDocumentation(manager, out, Path(name), imprimir=config, formatos=["markdown"]).generate()
    return result.outputs["markdown"]


def _alter(db: Path, script: str) -> None:
    with sqlite3.connect(db) as connection:
        connection.executescript(script)


def test_changes_between_two_generations(sqlite_db: Path, tmp_path: Path) -> None:
    first = _generate(sqlite_db, tmp_path / "out", "v1")
    _alter(sqlite_db, AFTER)
    second = _generate(sqlite_db, tmp_path / "out", "v2", {"previous": str(first)})

    diff = SchemaDiff.from_dict(json.loads((second / "docs/changes.json").read_text(encoding="utf-8")))
    tables = {t.table_name: t for t in diff.table_diffs}
    assert {name: t.status for name, t in tables.items()} == {
        "clientes": "modified",
        "nueva": "added",
        "pedidos": "modified",
        "vieja <b>": "removed",
    }
    assert [(c.column_name, c.attribute, c.source_value, c.target_value) for c in tables["clientes"].column_diffs] == [
        ("email", "existence", "missing", "exists")
    ]
    assert [(i.index_name, i.status) for i in tables["pedidos"].index_diffs] == [("ix_pedidos_cliente", "added")]
    assert [(v.view_name, v.status) for v in diff.view_diffs] == [("v_pedidos", "modified")]

    page = (second / "docs/changes.md").read_text(encoding="utf-8")
    assert "# Cambios de esquema" in page
    assert "| Tablas | 1 | 1 | 2 |" in page
    assert "## Tabla [nueva](tables/nueva.md): añadida" in page
    assert "## Tabla vieja &lt;b&gt;: eliminada" in page  # eliminada: sin enlace y escapada
    assert "| `email` | existencia | `missing` | `exists` |" in page
    assert "## Vista [v_pedidos](views/v-pedidos.md): modificada" in page

    manifest = json.loads((second / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["previous"]["catalog_sha256"].startswith("sha256:")
    assert manifest["previous"]["generated_at"]
    assert "- [Cambios](changes.md)" in (second / "docs/llms.txt").read_text(encoding="utf-8")
    assert '  - "Cambios": changes.md' in (second / "mkdocs.yml").read_text(encoding="utf-8")


@pytest.mark.parametrize("target", ["root", "docs", "file"])
def test_previous_accepts_folder_docs_or_file(sqlite_db: Path, tmp_path: Path, target: str) -> None:
    first = _generate(sqlite_db, tmp_path / "out", "v1")
    previous = {"root": first, "docs": first / "docs", "file": first / "docs/catalog.json"}[target]

    second = _generate(sqlite_db, tmp_path / "out", "v2", {"previous": str(previous)})

    page = (second / "docs/changes.md").read_text(encoding="utf-8")
    assert "Sin cambios de esquema." in page
    assert (
        SchemaDiff.from_dict(json.loads((second / "docs/changes.json").read_text(encoding="utf-8"))).table_diffs == ()
    )


def test_previous_can_be_the_folder_being_regenerated(sqlite_db: Path, tmp_path: Path) -> None:
    """Uso con ``fichero_salida`` fijo (versionado con git): el catálogo anterior se lee antes de publicar."""
    first = _generate(sqlite_db, tmp_path / "out", "docs_bd")
    _alter(sqlite_db, AFTER)
    second = _generate(sqlite_db, tmp_path / "out", "docs_bd", {"previous": str(first)})

    assert second == first
    diff = SchemaDiff.from_dict(json.loads((second / "docs/changes.json").read_text(encoding="utf-8")))
    assert ("nueva", "added") in [(t.table_name, t.status) for t in diff.table_diffs]


def test_unchanged_schema_and_determinism(sqlite_db: Path, tmp_path: Path) -> None:
    first = _generate(sqlite_db, tmp_path / "out", "v1")
    _alter(sqlite_db, AFTER)
    a = _generate(sqlite_db, tmp_path / "out", "a", {"previous": str(first)})
    b = _generate(sqlite_db, tmp_path / "out", "b", {"previous": str(first)})

    for name in ("docs/changes.md", "docs/changes.json"):
        assert (a / name).read_bytes() == (b / name).read_bytes()


def test_selection_change_does_not_report_removals(sqlite_db: Path, tmp_path: Path) -> None:
    first = _generate(sqlite_db, tmp_path / "out", "v1")
    second = _generate(sqlite_db, tmp_path / "out", "v2", {"previous": str(first)}, vistas={"imprimir_vistas": False})

    page = (second / "docs/changes.md").read_text(encoding="utf-8")
    assert "No se comparan los objetos de tipo «views»: no se documentaron en la generación actual." in page
    assert "## Vista" not in page


def test_other_schema_warns_and_other_engine_fails(sqlite_db: Path, tmp_path: Path) -> None:
    first = _generate(sqlite_db, tmp_path / "out", "v1")
    catalog_file = first / "docs/catalog.json"
    catalog = json.loads(catalog_file.read_text(encoding="utf-8"))

    catalog["schema"] = "produccion"
    catalog_file.write_text(json.dumps(catalog), encoding="utf-8")
    page = (_generate(sqlite_db, tmp_path / "out", "v2", {"previous": str(first)}) / "docs/changes.md").read_text(
        encoding="utf-8"
    )
    assert "Los schemas son distintos (produccion → main)" in page

    catalog["engine"] = "oracle"
    catalog_file.write_text(json.dumps(catalog), encoding="utf-8")
    with pytest.raises(DocumentationConfigError, match="otro motor"):
        _generate(sqlite_db, tmp_path / "out", "v3", {"previous": str(first)})


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (None, "no hay catalog.json"),
        ("no es json", "no se puede leer"),
        ('{"format": "otro"}', "no es un catálogo de util_bbdd"),
        ('{"format": "util_bbdd.doc.catalog", "format_version": 9, "objects": []}', "versión 9"),
    ],
)
def test_invalid_previous_fails_when_building(
    sqlite_db: Path, tmp_path: Path, content: str | None, message: str
) -> None:
    folder = tmp_path / "anterior"
    folder.mkdir()
    if content is not None:
        (folder / "catalog.json").write_text(content, encoding="utf-8")

    with (
        SyncDatabaseManager("sqlite", {"database": str(sqlite_db)}, use_pool=False) as manager,
        pytest.raises(DocumentationConfigError, match=message),
    ):
        DatabaseDocumentation(
            manager,
            tmp_path / "out",
            imprimir={**IMPRIMIR, "markdown": {"previous": str(folder)}},
            formatos=["markdown"],
        )
    assert not (tmp_path / "out").exists()


def test_without_previous_there_are_no_changes_files(sqlite_db: Path, tmp_path: Path) -> None:
    root = _generate(sqlite_db, tmp_path / "out", "v1")

    assert not (root / "docs/changes.md").exists()
    assert "previous" not in json.loads((root / "manifest.json").read_text(encoding="utf-8"))


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("zensical") is None, reason="zensical no está instalado")
def test_zensical_strict_build_with_changes(sqlite_db: Path, tmp_path: Path) -> None:
    first = _generate(sqlite_db, tmp_path / "out", "v1")
    _alter(sqlite_db, AFTER)
    second = _generate(sqlite_db, tmp_path / "out", "v2", {"previous": str(first)})

    result = subprocess.run(
        ["zensical", "build", "--strict"], cwd=second, capture_output=True, text=True, timeout=300, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
