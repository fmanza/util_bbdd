"""Orden de creación de las tablas nuevas por sus FKs en ``SqlDiffReporter`` (B8, auditoría de comparar 2026-10-02)."""

from __future__ import annotations

import sqlite3

from contextlib import closing
from typing import TYPE_CHECKING

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine, inspect, text

from util_bbdd.comparar.models import SchemaDiff, TableDiff
from util_bbdd.comparar.reporters import SqlDiffReporter

if TYPE_CHECKING:
    from pathlib import Path


def _script(ddl: list[str], added: list[str], tmp_path: Path) -> str:
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        for stmt in ddl:
            conn.execute(text(stmt))
    diff = SchemaDiff("src", "tgt", table_diffs=tuple(TableDiff(t, "added") for t in added))
    out = tmp_path / "diff.sql"
    SqlDiffReporter(dialect="sqlite", source_inspector=inspect(engine)).render(diff, out)
    return out.read_text(encoding="utf-8")


def _create_order(script: str) -> list[str]:
    prefix = "CREATE TABLE IF NOT EXISTS "
    return [line[len(prefix) :].split(" ")[0] for line in script.splitlines() if line.startswith(prefix)]


def test_referenced_new_tables_are_created_first(tmp_path: Path) -> None:
    ddl = [
        "CREATE TABLE a_lineas (id INTEGER PRIMARY KEY, pedido_id INTEGER REFERENCES b_pedidos(id))",
        "CREATE TABLE b_pedidos (id INTEGER PRIMARY KEY, cliente_id INTEGER REFERENCES c_clientes(id))",
        "CREATE TABLE c_clientes (id INTEGER PRIMARY KEY)",
        "CREATE TABLE d_suelta (id INTEGER PRIMARY KEY)",
    ]

    script = _script(ddl, ["a_lineas", "b_pedidos", "c_clientes", "d_suelta"], tmp_path)

    # Nivel 0 en orden alfabético (c, d), después b y después a
    assert _create_order(script) == ["c_clientes", "d_suelta", "b_pedidos", "a_lineas"]
    with closing(sqlite3.connect(":memory:")) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(script)  # cada FK referencia una tabla ya creada


def test_self_reference_and_existing_tables_do_not_affect_order(tmp_path: Path) -> None:
    ddl = [
        "CREATE TABLE existente (id INTEGER PRIMARY KEY)",
        "CREATE TABLE a (id INTEGER PRIMARY KEY, padre INTEGER REFERENCES a(id), e INTEGER REFERENCES existente(id))",
        "CREATE TABLE b (id INTEGER PRIMARY KEY)",
    ]

    script = _script(ddl, ["a", "b"], tmp_path)

    assert _create_order(script) == ["a", "b"]
    assert "Ciclo" not in script


def test_fk_cycle_keeps_every_table_and_warns(tmp_path: Path) -> None:
    ddl = [
        "CREATE TABLE x (id INTEGER PRIMARY KEY, y_id INTEGER REFERENCES y(id))",
        "CREATE TABLE y (id INTEGER PRIMARY KEY, x_id INTEGER REFERENCES x(id))",
        "CREATE TABLE z (id INTEGER PRIMARY KEY, x_id INTEGER REFERENCES x(id))",
        "CREATE TABLE w (id INTEGER PRIMARY KEY)",
    ]

    script = _script(ddl, ["w", "x", "y", "z"], tmp_path)

    # w no depende de nada; x, y (ciclo) y z (depende del ciclo) van al final en el orden recibido
    assert _create_order(script) == ["w", "x", "y", "z"]
    assert "-- ⚠ Ciclo de FKs entre tablas nuevas: x, y, z." in script


def test_without_inspector_order_is_unchanged(tmp_path: Path) -> None:
    diff = SchemaDiff("src", "tgt", table_diffs=(TableDiff("b", "added"), TableDiff("a", "added")))
    out = tmp_path / "diff.sql"

    SqlDiffReporter(dialect="sqlite").render(diff, out)

    script = out.read_text(encoding="utf-8")
    assert script.index("TABLA NUEVA: b") < script.index("TABLA NUEVA: a")
