"""Documentación Markdown de punta a punta con SQLite (5.3.0, grupo B de la sesión ``2026-11-05-doc-markdown``).

Cubre las condiciones del AUDIT_PLAN del grupo: salida determinista byte a byte (BC1), limpieza de huérfanos sin tocar
ficheros ajenos (BC1), cancelación sin dejar la carpeta a medias, diagramas sin Graphviz y ``zensical build --strict``
(BC2, solo si Zensical está instalado).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys

from pathlib import Path
from typing import Any

import pytest

from util_bbdd.doc.database_documentation import DatabaseDocumentation
from util_bbdd.doc.infrastructure.renderers.shared.print_config_manager import PrintConfigManager
from util_bbdd.doc.infrastructure.runtime.output_runtime import DocumentationOutputRuntime
from util_bbdd.exceptions import OperationCancelledError
from util_bbdd.managers import SyncDatabaseManager
from util_bbdd.progress import CancellationToken, ProgressEvent

pytestmark = pytest.mark.unit

IMPRIMIR: dict[str, Any] = {
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
    "grafo": {"enabled": True, "max_depth": 3},
}

SCHEMA = """
CREATE TABLE clientes (id INTEGER PRIMARY KEY, nombre TEXT UNIQUE);
CREATE TABLE pedidos (
    id INTEGER PRIMARY KEY,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    vendedor_id INTEGER REFERENCES clientes(id)
);
CREATE TABLE lineas (pedido_id INTEGER NOT NULL REFERENCES pedidos(id), n INTEGER NOT NULL, PRIMARY KEY (pedido_id, n));
CREATE TABLE "Tabla <b>*rara*</b>" (id INTEGER PRIMARY KEY);
CREATE INDEX ix_pedidos_cliente ON pedidos (cliente_id);
CREATE VIEW v_pedidos AS SELECT id, cliente_id FROM pedidos;
"""


@pytest.fixture
def sqlite_db(tmp_path: Path) -> Path:
    db = tmp_path / "ventas.db"
    with sqlite3.connect(db) as connection:
        connection.executescript(SCHEMA)
    return db


def _generate(db: Path, out: Path, name: str = "demo", **kwargs: Any) -> Path:
    imprimir = kwargs.pop("imprimir", IMPRIMIR)
    with SyncDatabaseManager("sqlite", {"database": str(db)}, use_pool=False) as manager:
        result = DatabaseDocumentation(
            manager, out, Path(name), imprimir=imprimir, formatos=["markdown"], **kwargs
        ).generate()
    return result.outputs["markdown"]


def _tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


# --- Configuración ---


def test_markdown_config_defaults_and_effective_depth() -> None:
    config = PrintConfigManager.normalize({"grafo": {"max_depth": 5}, "markdown": {"index_page_size": "x"}})
    resolved = PrintConfigManager.resolve_for_markdown(config)

    assert config["markdown"] == {
        "max_diagram_depth": 2,
        "index_page_size": 200,
        "front_matter": True,
        "column_anchors": True,
        "catalog_json": True,
        "llms_txt": True,
        "llms_full_txt": True,
        "mkdocs_yml": True,
        "site_name": None,
        "mermaid_js": None,
        "mermaid_js_ref": None,
        "trace_map": None,
        "previous": None,
    }
    assert resolved["diagram_options"]["max_depth"] == 2
    assert resolved["diagram_options"]["configured_max_depth"] == 5
    assert PrintConfigManager.normalize(None)["markdown"] == PrintConfigManager.DEFAULT_MARKDOWN


def test_md_alias_and_error_message() -> None:
    runtime = DocumentationOutputRuntime()

    assert runtime.normalize_output_formats(["MD", "markdown", "word"]) == ["markdown", "word"]
    with pytest.raises(ValueError, match="'markdown'"):
        runtime.normalize_output_formats(["pdf"])


# --- Salida ---


def test_tree_pages_and_manifest(sqlite_db: Path, tmp_path: Path) -> None:
    root = _generate(sqlite_db, tmp_path / "out")
    files = _tree(root)

    assert root == tmp_path / "out" / "demo" / "MARKDOWN"
    assert {
        "manifest.json",
        "docs/index.md",
        "docs/tables/index.md",
        "docs/tables/pedidos.md",
        "docs/tables/tabla-b-rara-b.md",
        "docs/views/v-pedidos.md",
    } <= set(files)
    assert not list((tmp_path / "out" / "demo").glob(".MARKDOWN.tmp-*"))

    page = files["docs/tables/pedidos.md"].decode("utf-8")
    front = json.loads(page.split("\n")[1])
    assert front["id"] == "table:main.pedidos"
    assert front["fk_in"] == ["table:main.lineas"]
    assert [fk["ref"] for fk in front["fk_out"]] == ["table:main.clientes", "table:main.clientes"]
    assert '<a id="col-cliente-id"></a>cliente_id' in page
    assert "[clientes](clientes.md)" in page
    assert "## Índices" in page
    assert "ix_pedidos_cliente" in page  # «_» entre letras sin escapar
    assert "ix\\_pedidos\\_cliente" not in page
    assert '!!! warning "Profundidad limitada a 2 (configurada 3)"' in page
    assert '    e2 ||..o{ e1 : ""' in page  # cliente_id NOT NULL
    assert '    e2 |o..o{ e1 : ""' in page  # vendedor_id nullable
    assert '    e1 ||--o{ e3 : ""' in page  # lineas: identificante, 1:N
    assert page.endswith("\n")
    assert not page.endswith("\n\n")
    assert "\r" not in page

    rara = files["docs/tables/tabla-b-rara-b.md"].decode("utf-8")
    assert "# Tabla: Tabla &lt;b&gt;\\*rara\\*&lt;/b&gt;" in rara
    assert "<b>" not in rara.split("```")[0].split("---")[-1]  # fuera del front matter y del código, sin HTML crudo

    manifest = json.loads(files["manifest.json"])
    assert manifest["format"] == "util_bbdd.doc.markdown"
    assert manifest["engine"] == "sqlite"
    assert set(manifest["files"]) == set(files) - {"manifest.json"}


def test_section_flags_off_like_word(sqlite_db: Path, tmp_path: Path) -> None:
    root = _generate(sqlite_db, tmp_path / "out", imprimir={"tablas": {"imprimir_tablas": True}})
    page = (root / "docs/tables/pedidos.md").read_text(encoding="utf-8")

    assert "## " not in page  # sin DDL, columnas, claves, índices ni diagrama
    assert not (root / "docs/views").exists()
    assert "- [Tablas](tables/index.md)" in (root / "docs/index.md").read_text(encoding="utf-8")


def test_output_is_byte_identical_between_generations(sqlite_db: Path, tmp_path: Path) -> None:
    first = _tree(_generate(sqlite_db, tmp_path / "a"))
    second = _tree(_generate(sqlite_db, tmp_path / "b"))

    first_manifest, second_manifest = json.loads(first.pop("manifest.json")), json.loads(second.pop("manifest.json"))
    assert first == second
    assert first_manifest["files"] == second_manifest["files"]


def test_regeneration_removes_orphans_and_keeps_foreign_files(sqlite_db: Path, tmp_path: Path) -> None:
    root = _generate(sqlite_db, tmp_path / "out")
    (root / "docs" / "mio.md").write_text("# Mío\n", encoding="utf-8")
    (root / "notas.txt").write_text("del usuario\n", encoding="utf-8")
    with sqlite3.connect(sqlite_db) as connection:
        connection.executescript('DROP TABLE "Tabla <b>*rara*</b>"; DROP VIEW v_pedidos;')

    root = _generate(sqlite_db, tmp_path / "out")

    assert not (root / "docs/tables/tabla-b-rara-b.md").exists()
    assert not (root / "docs/tables/index-t.md").exists()
    assert not (root / "docs/views").exists()  # carpeta vacía tras borrar sus ficheros
    assert (root / "docs" / "mio.md").read_text(encoding="utf-8") == "# Mío\n"
    assert (root / "notas.txt").exists()
    assert "docs/mio.md" not in json.loads((root / "manifest.json").read_text(encoding="utf-8"))["files"]


def test_foreign_manifest_deletes_nothing(sqlite_db: Path, tmp_path: Path) -> None:
    root = tmp_path / "out" / "demo" / "MARKDOWN"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "x.md").write_text("x", encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps({"format": "otro", "files": {"docs/x.md": ""}}), encoding="utf-8")
    (root.parent / "fuera.md").write_text("fuera", encoding="utf-8")

    _generate(sqlite_db, tmp_path / "out")
    assert (root / "docs" / "x.md").exists()

    x_hash = f"sha256:{hashlib.sha256(b'x').hexdigest()}"
    (root / "manifest.json").write_text(
        json.dumps({"format": "util_bbdd.doc.markdown", "files": {"../fuera.md": x_hash, "docs/x.md": x_hash}}),
        encoding="utf-8",
    )
    _generate(sqlite_db, tmp_path / "out")
    assert (root.parent / "fuera.md").exists()  # ruta fuera de la carpeta: se ignora
    assert not (root / "docs" / "x.md").exists()  # listada por un manifiesto nuestro, intacta y ya no generada


def test_modified_orphan_is_kept(sqlite_db: Path, tmp_path: Path) -> None:
    """Un fichero generado que el usuario editó no se borra aunque deje de generarse (grupo C, C4)."""
    root = _generate(sqlite_db, tmp_path / "out")
    (root / "mkdocs.yml").write_text("site_name: mío\n", encoding="utf-8")
    llms = (root / "docs" / "llms.txt").read_bytes()

    imprimir = {**IMPRIMIR, "markdown": {"mkdocs_yml": False, "llms_txt": False}}
    root = _generate(sqlite_db, tmp_path / "out", imprimir=imprimir)

    assert (root / "mkdocs.yml").read_text(encoding="utf-8") == "site_name: mío\n"  # editado: se conserva
    assert not (root / "docs" / "llms.txt").exists()  # intacto: se borra
    assert llms  # se había generado


def test_cancel_keeps_previous_version(sqlite_db: Path, tmp_path: Path) -> None:
    root = _generate(sqlite_db, tmp_path / "out")
    before = _tree(root)
    token = CancellationToken()
    events: list[ProgressEvent] = []

    def cancel_after_first_table(event: ProgressEvent) -> None:
        events.append(event)
        if (event.phase, event.current) == ("markdown", 1):
            token.cancel()

    with pytest.raises(OperationCancelledError):
        _generate(sqlite_db, tmp_path / "out", on_progress=cancel_after_first_table, cancel_token=token)

    assert [e.current for e in events if e.phase == "markdown"] == [0, 1]
    assert _tree(root) == before
    assert not list(root.parent.glob(".MARKDOWN.tmp-*"))


_NO_GRAPHVIZ = """
import sys
sys.modules["graphviz"] = None
from pathlib import Path
from util_bbdd.doc.database_documentation import DatabaseDocumentation
from util_bbdd.managers import SyncDatabaseManager
with SyncDatabaseManager("sqlite", {{"database": {db!r}}}, use_pool=False) as m:
    out = DatabaseDocumentation(m, Path({out!r}), Path("demo"), imprimir={imprimir!r}, formatos=["markdown"]).generate()
print("erDiagram" in (out.outputs["markdown"] / "docs/tables/pedidos.md").read_text(encoding="utf-8"))
"""


def test_diagrams_without_graphviz(sqlite_db: Path, tmp_path: Path) -> None:
    script = _NO_GRAPHVIZ.format(db=str(sqlite_db), out=str(tmp_path / "out"), imprimir=IMPRIMIR)
    result = subprocess.run(
        [sys.executable, "-c", script], env=dict(os.environ), capture_output=True, text=True, check=True, timeout=120
    )

    assert result.stdout.strip() == "True"


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("zensical") is None, reason="zensical no está instalado")
def test_zensical_strict_build(sqlite_db: Path, tmp_path: Path) -> None:
    root = _generate(sqlite_db, tmp_path / "out")  # con el mkdocs.yml generado (grupo C)
    result = subprocess.run(
        ["zensical", "build", "--strict"], cwd=root, capture_output=True, text=True, timeout=300, check=False
    )

    assert result.returncode == 0, result.stdout + result.stderr
