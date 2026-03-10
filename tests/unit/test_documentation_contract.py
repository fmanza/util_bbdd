"""Contrato de documentación: sin consumo de API legacy."""

from __future__ import annotations

from pathlib import Path


def test_database_documentation_does_not_use_legacy_execute_api() -> None:
    source = Path("src/util_bbdd/doc/database_documentation.py").read_text(encoding="utf-8")

    assert "execute_query(" not in source
    assert "execute_custom_query(" not in source
    assert "fetch_one=" not in source


def test_database_documentation_does_not_depend_on_db_queries_attribute() -> None:
    source = Path("src/util_bbdd/doc/database_documentation.py").read_text(encoding="utf-8")
    assert ".db_queries" not in source
