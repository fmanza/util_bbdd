"""Mapa de trazabilidad de la documentación Markdown (5.3.0, grupo D de la sesión ``2026-11-05-doc-markdown``)."""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess

from pathlib import Path
from typing import Any

import pytest

from util_bbdd.doc.database_documentation import DatabaseDocumentation
from util_bbdd.doc.infrastructure.renderers.markdown._trace import (
    TraceEntry,
    TraceMap,
    code_span,
    reference,
)
from util_bbdd.exceptions import DocumentationConfigError
from util_bbdd.managers import SyncDatabaseManager

pytestmark = pytest.mark.unit

TOML = """
# Mapa de prueba
version = 1

[tables."PEDIDOS"]                       # en mayúsculas: casa con «pedidos» (sin ambigüedad)
code = ["src/ventas/pedidos.py#Pedido", "src/ventas/service.py"]
functional = ["docs/functional/ventas.md#alta"]
requirements = ["REQ-012", "https://jira.example.com/browse/VEN-7"]
tags = ["ventas", "<b>núcleo</b>"]
notes = "Cabecera *de* pedido"

[tables."PEDIDOS".columns."CLIENTE_ID"]
code = ["src/ventas/pedidos.py#Pedido.cliente_id"]

[tables."PEDIDOS".columns."no_existe"]
code = ["x.py"]

[tables.clientes]
requirements = ["REQ-012"]
code = ["javascript:alert(1)", "a`b|c"]

[tables.borrada]
code = ["viejo.py"]

[views.v_pedidos]
technical = ["docs/api/ventas.md"]
"""

SCHEMA = """
CREATE TABLE clientes (id INTEGER PRIMARY KEY);
CREATE TABLE pedidos (id INTEGER PRIMARY KEY, cliente_id INTEGER NOT NULL REFERENCES clientes(id));
CREATE TABLE lineas (id INTEGER PRIMARY KEY, pedido_id INTEGER REFERENCES pedidos(id));
CREATE VIEW v_pedidos AS SELECT id FROM pedidos;
"""

IMPRIMIR: dict[str, Any] = {
    "tablas": {"imprimir_tablas": True, "columnas": True},
    "vistas": {"imprimir_vistas": True},
}


@pytest.fixture
def sqlite_db(tmp_path: Path) -> Path:
    db = tmp_path / "ventas.db"
    with sqlite3.connect(db) as connection:
        connection.executescript(SCHEMA)
    return db


@pytest.fixture
def toml_map(tmp_path: Path) -> Path:
    path = tmp_path / "traza.toml"
    path.write_text(TOML, encoding="utf-8")
    return path


def _generate(db: Path, out: Path, trace_map: Path | None, name: str = "demo") -> Path:
    markdown: dict[str, Any] = {} if trace_map is None else {"trace_map": str(trace_map)}
    with SyncDatabaseManager("sqlite", {"database": str(db)}, use_pool=False) as manager:
        result = DatabaseDocumentation(
            manager, out, Path(name), imprimir={**IMPRIMIR, "markdown": markdown}, formatos=["markdown"]
        ).generate()
    return result.outputs["markdown"]


# --- Carga y validación ---


def test_toml_and_json_give_the_same_map(toml_map: Path, tmp_path: Path) -> None:
    import tomllib

    json_map = tmp_path / "traza.json"
    json_map.write_text(json.dumps(tomllib.loads(TOML)), encoding="utf-8")

    assert TraceMap.load(toml_map) == TraceMap.load(json_map)
    pedidos = TraceMap.load(toml_map).sections["tables"]["PEDIDOS"]
    assert pedidos.refs["code"] == ("src/ventas/pedidos.py#Pedido", "src/ventas/service.py")
    assert set(pedidos.columns) == {"CLIENTE_ID", "no_existe"}


@pytest.mark.parametrize(
    ("content", "suffix", "messages"),
    [
        ('[tablas.x]\ncode = ["a"]', ".toml", ["secciones desconocidas: tablas"]),
        ('[tables.x]\nrequirement = ["a"]\ncode = "a"', ".toml", ["campos desconocidos requirement", "tables.x.code"]),
        ('[views.v.columns.c]\ncode = ["a"]', ".toml", ["views.v: campos desconocidos columns"]),
        ("version = 2", ".toml", ["version 2 no soportada"]),
        ("[tables", ".toml", ["no se puede leer"]),
        ('{"tables": []}', ".json", ["«tables» debe ser una tabla/objeto"]),
        ("tables: {}", ".yaml", [".toml o .json"]),
    ],
)
def test_invalid_maps_report_every_error(tmp_path: Path, content: str, suffix: str, messages: list[str]) -> None:
    path = tmp_path / f"mapa{suffix}"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(DocumentationConfigError) as raised:
        TraceMap.load(path)

    for message in messages:
        assert message in str(raised.value)


def test_invalid_map_fails_when_building_the_documentation(sqlite_db: Path, tmp_path: Path) -> None:
    bad = tmp_path / "mal.toml"
    bad.write_text('[tables.x]\nrequirement = ["REQ-1"]', encoding="utf-8")

    with (
        SyncDatabaseManager("sqlite", {"database": str(sqlite_db)}, use_pool=False) as manager,
        pytest.raises(DocumentationConfigError, match="requirement"),
    ):
        DatabaseDocumentation(
            manager, tmp_path / "out", imprimir={**IMPRIMIR, "markdown": {"trace_map": str(bad)}}, formatos=["markdown"]
        )
    assert not (tmp_path / "out").exists()


def test_matching_exact_case_insensitive_ambiguous_and_duplicated() -> None:
    entry = TraceEntry(refs={"code": ("x.py",)})
    trace_map = TraceMap({"tables": {"foo": entry, "BAR": entry, "Baz": entry, "baz": entry, "qux": entry}})

    matched, unmatched = trace_map.match("tables", ["Foo", "FOO", "bar", "Baz", "otra"])

    assert set(matched) == {"bar", "Baz"}
    assert [(u.key, u.reason.split(":")[0]) for u in unmatched] == [
        ("baz", "duplicada"),
        ("foo", "ambiguo"),
        ("qux", "no se documenta ningún objeto con ese nombre"),
    ]


# --- Render ---


@pytest.mark.parametrize(
    ("ref", "expected"),
    [
        (
            "https://jira.example.com/browse/VEN-7",
            "[https://jira.example.com/browse/VEN-7](https://jira.example.com/browse/VEN-7)",
        ),
        ("https://x.org/a b(c)", "`https://x.org/a b(c)`"),  # con espacio no es una URL válida: código
        ("javascript:alert(1)", "`javascript:alert(1)`"),
        ("data:text/html,<b>x</b>", "`data:text/html,<b>x</b>`"),
        ("../../etc/passwd", "`../../etc/passwd`"),
    ],
)
def test_reference_only_links_http_urls(ref: str, expected: str) -> None:
    assert reference(ref) == expected


def test_code_span_with_backticks_and_pipes() -> None:
    assert code_span("a`b") == "``a`b``"
    assert code_span("`x`") == "`` `x` ``"
    assert code_span("a|b", in_table=True) == "`a\\|b`"


# --- Salida ---


def test_pages_front_matter_catalog_and_traceability(sqlite_db: Path, toml_map: Path, tmp_path: Path) -> None:
    root = _generate(sqlite_db, tmp_path / "out", toml_map)
    docs = root / "docs"

    page = (docs / "tables/pedidos.md").read_text(encoding="utf-8")
    assert "## Trazabilidad" in page
    assert "| Código | `src/ventas/pedidos.py#Pedido`, `src/ventas/service.py` |" in page
    assert "[https://jira.example.com/browse/VEN-7](https://jira.example.com/browse/VEN-7)" in page
    assert "**Etiquetas:** ventas, &lt;b&gt;núcleo&lt;/b&gt;" in page
    assert "**Notas:** Cabecera \\*de\\* pedido" in page
    assert "### Columna [cliente_id](#col-cliente-id)" in page

    front = json.loads(page.split("\n")[1])
    assert front["trace"]["requirements"] == ["REQ-012", "https://jira.example.com/browse/VEN-7"]
    assert front["trace"]["columns"] == {"cliente_id": {"code": ["src/ventas/pedidos.py#Pedido.cliente_id"]}}

    clientes = (docs / "tables/clientes.md").read_text(encoding="utf-8")
    assert "`javascript:alert(1)`" in clientes
    assert "](javascript:" not in clientes
    assert "``a`b\\|c``" in clientes

    catalog = {o["id"]: o for o in json.loads((docs / "catalog.json").read_text(encoding="utf-8"))["objects"]}
    assert catalog["table:main.pedidos"]["trace"] == front["trace"]
    assert catalog["table:main.pedidos"]["hash"] == front["hash"]
    assert "trace" not in catalog["table:main.lineas"]

    trace = (docs / "traceability.md").read_text(encoding="utf-8")
    assert "| Tablas | 3 | 2 | 67 |" in trace
    assert "| Vistas | 1 | 1 | 100 |" in trace
    assert "**Tablas** (1): [lineas](tables/lineas.md)" in trace
    assert "| `REQ-012` | [clientes](tables/clientes.md), [pedidos](tables/pedidos.md) |" in trace
    assert (
        "| `src/ventas/pedidos.py` | [pedidos](tables/pedidos.md), [pedidos.cliente_id](tables/pedidos.md) |" in trace
    )
    assert "| tables | borrada | no se documenta ningún objeto con ese nombre |" in trace
    assert "| columns | pedidos.no_existe | la tabla no tiene ninguna columna con ese nombre |" in trace

    assert "- [Trazabilidad](traceability.md)" in (docs / "llms.txt").read_text(encoding="utf-8")
    assert '  { "Trazabilidad" = "traceability.md" },' in (root / "zensical.toml").read_text(encoding="utf-8")


def test_trace_does_not_change_hash_and_without_map_nothing_changes(
    sqlite_db: Path, toml_map: Path, tmp_path: Path
) -> None:
    with_map = _generate(sqlite_db, tmp_path / "a", toml_map) / "docs"
    without = _generate(sqlite_db, tmp_path / "b", None) / "docs"

    hashes = [
        {o["id"]: o["hash"] for o in json.loads((d / "catalog.json").read_text(encoding="utf-8"))["objects"]}
        for d in (with_map, without)
    ]
    assert hashes[0] == hashes[1]
    assert not (without / "traceability.md").exists()
    assert "## Trazabilidad" not in (without / "tables/pedidos.md").read_text(encoding="utf-8")
    assert "Trazabilidad" not in (without / "llms.txt").read_text(encoding="utf-8")


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("zensical") is None, reason="zensical no está instalado")
def test_zensical_strict_build_with_trace_map(sqlite_db: Path, toml_map: Path, tmp_path: Path) -> None:
    root = _generate(sqlite_db, tmp_path / "out", toml_map)
    result = subprocess.run(
        ["zensical", "build", "--strict"], cwd=root, capture_output=True, text=True, timeout=300, check=False
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (root / "site" / "traceability" / "index.html").exists()


def test_trace_output_is_deterministic(sqlite_db: Path, toml_map: Path, tmp_path: Path) -> None:
    first = _generate(sqlite_db, tmp_path / "a", toml_map) / "docs"
    second = _generate(sqlite_db, tmp_path / "b", toml_map) / "docs"

    for name in ("traceability.md", "tables/pedidos.md", "catalog.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
