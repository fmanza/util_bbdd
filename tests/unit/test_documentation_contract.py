"""Contrato de documentación: sin consumo de API legacy."""

from __future__ import annotations

import ast

from pathlib import Path


def _load_database_documentation_tree() -> ast.AST:
    source = Path("src/util_bbdd/doc/database_documentation.py").read_text(encoding="utf-8")
    return ast.parse(source)


def test_database_documentation_does_not_use_legacy_execute_api() -> None:
    tree = _load_database_documentation_tree()
    legacy_call_targets = {"execute_query", "execute_custom_query"}
    detected_legacy_calls: list[str] = []
    detected_fetch_one_keyword = False

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        called_name: str | None = None
        if isinstance(node.func, ast.Name):
            called_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            called_name = node.func.attr

        if called_name in legacy_call_targets:
            detected_legacy_calls.append(called_name)

        if any(keyword.arg == "fetch_one" for keyword in node.keywords):
            detected_fetch_one_keyword = True

    assert not detected_legacy_calls
    assert detected_fetch_one_keyword is False


def test_database_documentation_does_not_depend_on_db_queries_attribute() -> None:
    tree = _load_database_documentation_tree()
    db_queries_accesses = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "db_queries"
    ]
    assert db_queries_accesses == []
