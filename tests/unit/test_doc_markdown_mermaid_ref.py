"""``markdown.mermaid_js_ref`` (5.4.0, G50 de util_bbdd_web): Mermaid ya publicado, referenciado sin copiarlo."""

from __future__ import annotations

import json
import logging
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
    "grafo": {"enabled": True},
}
LOCAL = "assets/javascripts/mermaid.min.js"


@pytest.fixture
def sqlite_db(tmp_path: Path) -> Path:
    db = tmp_path / "ventas.db"
    with sqlite3.connect(db) as connection:
        connection.executescript(
            "CREATE TABLE clientes (id INTEGER PRIMARY KEY);"
            "CREATE TABLE pedidos (id INTEGER PRIMARY KEY, cliente_id INTEGER REFERENCES clientes(id));"
        )
    return db


def _generate(db: Path, out: Path, markdown: dict[str, Any]) -> Path:
    with SyncDatabaseManager("sqlite", {"database": str(db)}, use_pool=False) as manager:
        result = DatabaseDocumentation(
            manager, out, Path("demo"), imprimir={**IMPRIMIR, "markdown": markdown}, formatos=["markdown"]
        ).generate()
    return result.outputs["markdown"]


def _config(root: Path) -> dict[str, Any]:
    return dict(yaml.unsafe_load((root / "mkdocs.yml").read_text(encoding="utf-8")))  # !!python/name lo exige


def _manifest_files(root: Path) -> dict[str, str]:
    return dict(json.loads((root / "manifest.json").read_text(encoding="utf-8"))["files"])


def test_relative_ref_is_referenced_without_copying(sqlite_db: Path, tmp_path: Path) -> None:
    root = _generate(sqlite_db, tmp_path / "out", {"mermaid_js_ref": LOCAL})

    config = _config(root)
    assert config["extra_javascript"] == [LOCAL]
    assert config["theme"] == {"name": "material", "font": False}  # sitio sin Internet: sin Google Fonts
    assert not (root / "docs/assets").exists()
    assert not any(name.startswith("docs/assets/") for name in _manifest_files(root))


def test_https_ref_keeps_theme_fonts(sqlite_db: Path, tmp_path: Path) -> None:
    url = "https://cdn.example.org/mermaid@12.2.0/dist/mermaid.min.js?v=1&x='a'"
    root = _generate(sqlite_db, tmp_path / "out", {"mermaid_js_ref": url})

    config = _config(root)
    assert config["extra_javascript"] == [url]
    assert config["theme"] == {"name": "material"}
    assert not (root / "docs/assets").exists()


def test_ref_is_written_as_yaml_string(sqlite_db: Path, tmp_path: Path) -> None:
    # Comillas y «#» no rompen el YAML ni añaden claves (se escribe con json.dumps; «:» ya se rechaza en las rutas)
    ref = 'js/m"x"#y\'z.js'
    root = _generate(sqlite_db, tmp_path / "out", {"mermaid_js_ref": ref})

    assert _config(root)["extra_javascript"] == [ref]


@pytest.mark.parametrize(
    "ref",
    [
        "../mermaid.min.js",
        "assets/../../x.js",
        "./mermaid.min.js",
        "assets//mermaid.min.js",
        "assets/",
        "/abs/mermaid.min.js",
        "C:\\x\\mermaid.min.js",
        "C:/x/mermaid.min.js",
        "javascript:alert(1)",
        "data:text/javascript,alert(1)",
        "http://cdn.example.org/mermaid.min.js",
        "//cdn.example.org/mermaid.min.js",
        "https:///mermaid.min.js",
        "file:///etc/passwd",
        "assets/mermaid min.js",
        "assets/mermaid\n.js",
    ],
)
def test_invalid_ref_fails_before_generating(sqlite_db: Path, tmp_path: Path, ref: str) -> None:
    with (
        SyncDatabaseManager("sqlite", {"database": str(sqlite_db)}, use_pool=False) as manager,
        pytest.raises(DocumentationConfigError, match="mermaid_js_ref"),
    ):
        DatabaseDocumentation(
            manager, tmp_path / "out", imprimir={**IMPRIMIR, "markdown": {"mermaid_js_ref": ref}}, formatos=["markdown"]
        )

    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("ref", ["", "   ", None])
def test_empty_ref_means_no_ref(sqlite_db: Path, tmp_path: Path, ref: str | None) -> None:
    root = _generate(sqlite_db, tmp_path / "out", {"mermaid_js_ref": ref})

    assert "extra_javascript" not in _config(root)


def test_ref_and_copy_are_exclusive(sqlite_db: Path, tmp_path: Path) -> None:
    mermaid = tmp_path / "mermaid.min.js"
    mermaid.write_text("window.mermaid = {};\n", encoding="utf-8")
    with (
        SyncDatabaseManager("sqlite", {"database": str(sqlite_db)}, use_pool=False) as manager,
        pytest.raises(DocumentationConfigError, match="excluyentes"),
    ):
        DatabaseDocumentation(
            manager,
            tmp_path / "out",
            imprimir={**IMPRIMIR, "markdown": {"mermaid_js": str(mermaid), "mermaid_js_ref": LOCAL}},
            formatos=["markdown"],
        )


def test_ref_is_ignored_for_other_formats(sqlite_db: Path, tmp_path: Path) -> None:
    # Como mermaid_js: solo se valida si se genera Markdown
    with SyncDatabaseManager("sqlite", {"database": str(sqlite_db)}, use_pool=False) as manager:
        DatabaseDocumentation(
            manager, tmp_path / "out", imprimir={**IMPRIMIR, "markdown": {"mermaid_js_ref": "../x"}}, formatos=["excel"]
        )


def test_switching_from_copy_to_ref_keeps_the_copied_file(sqlite_db: Path, tmp_path: Path) -> None:
    # T2: la copia de la generación anterior está en manifest.json; al pasar a referenciarla en la misma ruta no se
    # borra como huérfana (si no, el sitio perdería Mermaid)
    mermaid = tmp_path / "mermaid.min.js"
    mermaid.write_text("window.mermaid = {};\n", encoding="utf-8")
    root = _generate(sqlite_db, tmp_path / "out", {"mermaid_js": str(mermaid)})
    assert f"docs/{LOCAL}" in _manifest_files(root)

    root = _generate(sqlite_db, tmp_path / "out", {"mermaid_js_ref": LOCAL})

    assert (root / "docs" / LOCAL).read_bytes() == mermaid.read_bytes()
    assert f"docs/{LOCAL}" not in _manifest_files(root)  # ahora es un fichero ajeno: no se vuelve a tocar
    assert _config(root)["extra_javascript"] == [LOCAL]


def test_switching_to_https_ref_removes_the_old_copy(sqlite_db: Path, tmp_path: Path) -> None:
    mermaid = tmp_path / "mermaid.min.js"
    mermaid.write_text("window.mermaid = {};\n", encoding="utf-8")
    _generate(sqlite_db, tmp_path / "out", {"mermaid_js": str(mermaid)})

    root = _generate(sqlite_db, tmp_path / "out", {"mermaid_js_ref": "https://cdn.example.org/mermaid.min.js"})

    assert not (root / "docs" / LOCAL).exists()


def test_ref_without_mkdocs_yml_only_warns(sqlite_db: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        root = _generate(sqlite_db, tmp_path / "out", {"mermaid_js_ref": LOCAL, "mkdocs_yml": False})

    assert not (root / "mkdocs.yml").exists()
    assert "mermaid_js_ref no tiene efecto" in caplog.text
