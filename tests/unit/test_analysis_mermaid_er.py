"""Diagramas ``erDiagram`` de ``MermaidRelationshipGraph`` (condición C2, 5.3.0): sin Graphviz y deterministas.

Sintaxis validada con Mermaid 11.17.2 y 12.2.0 (SPIKE_C3 de la sesión ``2026-11-05-doc-markdown``).
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys

from pathlib import Path
from typing import Any, cast

import pytest

from _catalog_fakes import FakeCatalogManager, FkRow, build_catalog

from util_bbdd.analysis import MermaidErResult, MermaidRelationshipGraph
from util_bbdd.managers import SyncDatabaseManager
from util_bbdd.metadata.model import ColumnMeta, Kind

pytestmark = pytest.mark.unit

ColumnSpec = tuple[str, str, bool]  # (nombre, tipo, admite nulos)


def _manager(
    columns: dict[str, list[ColumnSpec]],
    fks: dict[str, list[FkRow]],
    pks: dict[str, tuple[str, ...]],
    uniques: dict[str, list[tuple[str, ...]]] | None = None,
) -> SyncDatabaseManager:
    data: dict[Kind, tuple[Any, ...]] = build_catalog(
        tables=list(columns), fk_by_table=fks, pk_by_table=pks, uniques_by_table=uniques or {}
    )
    data[Kind.COLUMNS] = tuple(
        ColumnMeta(table, name, i, data_type, data_type, nullable)
        for table, specs in columns.items()
        for i, (name, data_type, nullable) in enumerate(specs, 1)
    )
    return cast(SyncDatabaseManager, FakeCatalogManager(data=data))


def _ventas(**kwargs: Any) -> MermaidRelationshipGraph:
    manager = _manager(
        columns={
            "clientes": [("id", "INTEGER", False), ("nombre", "VARCHAR(80)", True)],
            "pedidos": [
                ("id", "INTEGER", False),
                ("cliente_id", "INTEGER", False),
                ("vendedor_id", "INTEGER", True),
                ("numero", "VARCHAR(20)", False),
                ("total", "DECIMAL(10,2)", True),
            ],
            "facturas": [("id", "INTEGER", False), ("pedido_id", "INTEGER", False)],
        },
        fks={
            "pedidos": [
                ("fk_ped_cli", "cliente_id", "clientes", "id"),
                ("fk_ped_vend", "vendedor_id", "clientes", "id"),
            ],
            "facturas": [("fk_fac_ped", "pedido_id", "pedidos", "id")],
        },
        pks={"clientes": ("id",), "pedidos": ("id",), "facturas": ("id",)},
        uniques={"pedidos": [("numero",)], "facturas": [("pedido_id",)]},
    )
    return MermaidRelationshipGraph(manager, **kwargs)


def test_render_er_relations_mode() -> None:
    result = _ventas(show_constraint_name=True).render_er("pedidos")

    assert isinstance(result, MermaidErResult)
    assert result.warnings == ()
    assert result.blocks == (
        "erDiagram\n"
        '    e1["pedidos"] {\n'
        "        INTEGER id PK\n"
        "        INTEGER cliente_id FK\n"
        "        INTEGER vendedor_id FK\n"
        "    }\n"
        '    e2["clientes"] {\n'
        "        INTEGER id PK\n"
        "    }\n"
        '    e3["facturas"] {\n'
        "        INTEGER id PK\n"
        "        INTEGER pedido_id FK, UK\n"
        "    }\n"
        '    e2 ||..o{ e1 : "fk_ped_cli"\n'
        '    e2 |o..o{ e1 : "fk_ped_vend"\n'
        '    e1 ||..o| e3 : "fk_fac_ped"',
    )


def test_compact_and_all_modes() -> None:
    compact = _ventas(column_mode="compact").render_er("pedidos").blocks[0]
    assert "{" not in compact.split("\n", 1)[1].replace("o{", "")
    assert '    e1["pedidos"]\n' in compact

    full = _ventas(column_mode="all", max_columns=4).render_er("pedidos").blocks[0]
    assert "        VARCHAR(20) numero UK" in full
    assert "DECIMAL(10_2) total" not in full  # quinta columna: fuera por max_columns=4
    assert '    e2 ||..o{ e1 : ""' in full  # sin show_constraint_name, etiqueta vacía


def test_identifying_relation_keeps_graphviz_cardinality() -> None:
    """FK dentro de la PK hija → línea continua. La cardinalidad es la heredada de Graphviz (deuda F3: ``M:N``)."""
    manager = _manager(
        columns={
            "pedidos": [("id", "INTEGER", False)],
            "lineas": [("pedido_id", "INTEGER", False), ("n", "INT", False)],
        },
        fks={"lineas": [("fk_lin_ped", "pedido_id", "pedidos", "id")]},
        pks={"pedidos": ("id",), "lineas": ("pedido_id", "n")},
    )
    block = MermaidRelationshipGraph(manager).render_er("lineas").blocks[0]

    assert '    e2 }o--o{ e1 : ""' in block
    assert "        INTEGER pedido_id PK, FK" in block


def test_composite_fk_is_one_line_and_self_reference() -> None:
    manager = _manager(
        columns={
            "cab": [("a", "INT", False), ("b", "INT", False)],
            "det": [("a", "INT", False), ("b", "INT", False), ("id", "INT", False), ("padre_id", "INT", True)],
        },
        fks={
            "det": [
                ("fk_det_cab", "a", "cab", "a"),
                ("fk_det_cab", "b", "cab", "b"),
                ("fk_arbol", "padre_id", "det", "id"),
            ]
        },
        pks={"cab": ("a", "b"), "det": ("id",)},
    )
    block = MermaidRelationshipGraph(manager, show_constraint_name=True).render_er("det").blocks[0]

    assert block.count("fk_det_cab") == 1
    assert '    e1 |o..o{ e1 : "fk_arbol"' in block


def test_split_by_max_subnodes_repeats_root() -> None:
    children = {f"h{i}": [("id", "INT", False), ("p_id", "INT", False)] for i in range(5)}
    manager = _manager(
        columns={"p": [("id", "INT", False)], **children},
        fks={t: [(f"fk_{t}", "p_id", "p", "id")] for t in children},
        pks={"p": ("id",), **dict.fromkeys(children, ("id",))},
    )
    result = MermaidRelationshipGraph(manager).render_er("p", max_subnodes=2)

    assert len(result.blocks) == 3
    assert all(block.startswith('erDiagram\n    e1["p"]') for block in result.blocks)
    assert result.warnings == ()


def test_size_guards_drop_columns_then_split() -> None:
    children = {f"h{i}": [("id", "INT", False), ("p_id", "INT", False)] for i in range(6)}
    manager = _manager(
        columns={"p": [("id", "INT", False)], **children},
        fks={t: [(f"fk_{t}", "p_id", "p", "id")] for t in children},
        pks={"p": ("id",), **dict.fromkeys(children, ("id",))},
    )

    by_entities = MermaidRelationshipGraph(manager, max_entities=4).render_er("p")
    assert len(by_entities.blocks) == 2
    assert all(block.count('["') <= 4 for block in by_entities.blocks)
    assert by_entities.warnings == ("Diagrama partido: superaba 4 entidades o 50000 caracteres.",)

    plain_size = len(MermaidRelationshipGraph(manager, column_mode="compact").render_er("p").blocks[0])
    by_chars = MermaidRelationshipGraph(manager, max_chars=plain_size).render_er("p")
    assert len(by_chars.blocks) == 1
    assert "INT" not in by_chars.blocks[0]
    assert by_chars.warnings == (f"Diagrama sin columnas: con ellas superaba {plain_size} caracteres.",)


def test_hostile_names_are_escaped_and_normalized() -> None:
    manager = _manager(
        columns={
            '50% "x"\n%%{init}%%': [("PK", "double precision", False)],
            "hija": [("id", "INT", False), ("p", "INT", True)],
        },
        fks={"hija": [("fk[1]", "p", '50% "x"\n%%{init}%%', "PK")]},
        pks={'50% "x"\n%%{init}%%': ("PK",), "hija": ("id",)},
    )
    block = MermaidRelationshipGraph(manager, show_constraint_name=True).render_er("hija").blocks[0]

    assert '["50#37; #quot;x#quot; #37;#37;{init}#37;#37;"]' in block
    assert '        double_precision PK_ PK "PK"' in block
    assert ': "fk#91;1#93;"' in block
    assert "%%" not in block and "\n%" not in block


def test_table_without_relations_has_no_blocks() -> None:
    manager = _manager(columns={"suelta": [("id", "INT", False)]}, fks={}, pks={"suelta": ("id",)})

    result = MermaidRelationshipGraph(manager).render_er("suelta")

    assert result.blocks == ()
    assert result.document.root_table == "suelta"


def test_invalid_column_mode() -> None:
    with pytest.raises(ValueError, match="Modo de columnas no soportado"):
        _ventas(column_mode="todo")


_SCRIPT = f"""
import sys
sys.modules["graphviz"] = None  # como si el extra «analysis» no estuviera instalado
sys.path.insert(0, {str(Path(__file__).parent)!r})
from test_analysis_mermaid_er import _ventas
result = _ventas(column_mode="all", show_constraint_name=True).render_er("pedidos", max_depth=2)
print("graphviz" in sys.modules and sys.modules["graphviz"] is not None)
print(result.blocks)
"""


def test_works_without_graphviz_and_same_output_with_any_hash_seed() -> None:
    outputs = set()
    for seed in ("1", "2", "3", "4"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        result = subprocess.run(
            [sys.executable, "-c", _SCRIPT], env=env, capture_output=True, text=True, check=True, timeout=60
        )
        outputs.add(result.stdout.strip())

    assert len(outputs) == 1
    assert outputs.pop().startswith("False\n")


def test_sqlite_end_to_end(tmp_path: Path) -> None:
    db = tmp_path / "ventas.db"
    with sqlite3.connect(db) as connection:
        connection.executescript(
            """
            CREATE TABLE clientes (id INTEGER PRIMARY KEY, nombre TEXT);
            CREATE TABLE pedidos (
                id INTEGER PRIMARY KEY,
                cliente_id INTEGER NOT NULL REFERENCES clientes(id),
                vendedor_id INTEGER REFERENCES clientes(id)
            );
            """
        )
    with SyncDatabaseManager("sqlite", {"database": str(db)}) as manager:
        result = MermaidRelationshipGraph(manager).render_er("pedidos")

    block = result.blocks[0]
    # FK sin nombre en SQLite: una línea por FK (no se funden) y cada una con su nulabilidad
    assert '    e2 ||..o{ e1 : ""' in block
    assert '    e2 |o..o{ e1 : ""' in block
