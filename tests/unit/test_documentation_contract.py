"""Contrato de documentación: sin consumo de API legacy."""

from __future__ import annotations

import ast

from pathlib import Path
from typing import cast


def _load_database_documentation_tree() -> ast.Module:
    source = Path("src/util_bbdd/doc/database_documentation.py").read_text(encoding="utf-8")
    return cast(ast.Module, ast.parse(source))


def _load_module_tree(module_path: str) -> ast.Module:
    source = Path(module_path).read_text(encoding="utf-8")
    return cast(ast.Module, ast.parse(source))


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


def test_documentation_runtime_modules_do_not_expose_top_level_functions() -> None:
    module_paths = [
        "src/util_bbdd/doc/_documentation_runtime_headers.py",
        "src/util_bbdd/doc/_documentation_runtime_metadata.py",
        "src/util_bbdd/doc/_documentation_runtime_output.py",
    ]

    for module_path in module_paths:
        tree = _load_module_tree(module_path)
        top_level_functions = [
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        assert top_level_functions == [], f"{module_path} expone funciones top-level: {top_level_functions}"


def test_documentation_runtime_facade_module_is_removed() -> None:
    assert not Path("src/util_bbdd/doc/_documentation_runtime.py").exists()
