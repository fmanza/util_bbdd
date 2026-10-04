"""Guarda de la Regla #1 (``architecture.instructions.md``): la lectura del catálogo vive solo en ``metadata/``.

Escanea ``src/util_bbdd`` con ``ast`` (cadenas de código, no docstrings ni comentarios) y falla si fuera de
``metadata/`` aparece:

- SQL de catálogo (``information_schema``, ``ALL_*``, ``pg_catalog``, ``sys.*``, ``sqlite_master``, ``PRAGMA`` de
  esquema, ``SHOW CREATE``…),
- reflexión de SQLAlchemy (``inspect(…)`` o métodos de ``Inspector``),
- un import de un subpaquete de motor (``metadata.<motor>``): los consumidores no ramifican por motor.

``EXCEPTIONS`` son permanentes (configuración del servidor o de la sesión y SQL **emitido**, que no leen el diccionario
de datos). ``PENDING`` es un trinquete: lo que había el 2026-10-03 (sesión ``2026-10-03-metadata-centralization``,
ADR-003); cada grupo del plan lo reduce y el test falla si una entrada ya no hace falta, para que la lista solo baje.
"""

from __future__ import annotations

import ast
import re

from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "util_bbdd"

CATALOG_RE = re.compile(
    r"information_schema|\b(all|user|dba)_(tables|tab_\w+|cons_\w+|constraints|indexes|ind_\w+|views|objects|source|"
    r"procedures|arguments|sequences|triggers|synonyms|users|col_comments|mviews|types|tab_identity_cols|"
    r"dependencies|part_\w+|segments|tablespaces)\b|dbms_metadata|pg_catalog|\bpg_get_\w+|\bpg_(class|attribute|"
    r"constraint|index|namespace|proc|depend|description|type|tables|views|sequences?|settings|roles|database|"
    r"tablespace|stat\w*)\b|sqlite_(master|schema|temp_master|sequence)|\bpragma\b|\bsys\.\w+|object_definition|"
    r"objectproperty|svv_\w+|pg_table_def|^\s*show\s+(create|full|index|keys|columns|tables|procedure|function|"
    r"variables|table|triggers|status|grants|databases)",
    re.IGNORECASE | re.MULTILINE,
)
SQL_SHAPE_RE = re.compile(r"\bselect\b.+\bfrom\b|^\s*(select|show|pragma|exec)\b|\bfrom\s+\S+|\bjoin\b", re.I | re.S)
INSPECTOR_METHODS = frozenset(
    {
        "get_columns", "get_pk_constraint", "get_foreign_keys", "get_indexes", "get_unique_constraints",
        "get_check_constraints", "get_table_names", "get_view_names", "get_view_definition", "get_table_comment",
        "get_sequence_names", "get_schema_names", "get_temp_table_names", "get_multi_columns",
        "get_multi_pk_constraint", "get_multi_foreign_keys", "get_multi_indexes", "get_multi_unique_constraints",
        "get_multi_table_comment", "get_multi_check_constraints", "get_sorted_table_and_fkc_names", "reflect_table",
    }
)  # fmt: skip
ENGINE_PACKAGES = ("mariadb", "mysql", "oracle", "postgresql", "sqlite", "sqlserver")

# Permanentes: no leen el diccionario de datos.
EXCEPTIONS: dict[str, str] = {
    "connection/mariadb/_variables.py": "configuración del servidor (EngineReadinessAdvisor)",
    "connection/sqlite/_variables.py": "configuración de la conexión (PRAGMA de sesión)",
    "connection/sqlserver/_variables.py": "configuración del servidor (EngineReadinessAdvisor)",
    "connection/sqlite/connection_sqlite.py": "PRAGMA foreign_keys de la conexión",
    "connection/sqlite/pool_connection_sqlite.py": "PRAGMA foreign_keys de la conexión",
    "connection/sqlite/async_connection_sqlite.py": "PRAGMA foreign_keys de la conexión",
    "comparar/reporters/sql_reporter.py": "SQL emitido en el script de nivelación (lo ejecuta el destino)",
    "migrate/emitters/sqlserver.py": "DDL emitido (sp_addextendedproperty)",
}

# Trinquete (2026-10-03): fuera de metadata/ con SQL de catálogo o Inspector. Solo puede bajar.
PENDING_CATALOG: frozenset[str] = frozenset(
    {
        "comparar/reporters/sql_reporter.py",
    }
)

# Trinquete (2026-10-03): consumidores que importan metadata.<motor>. Solo puede bajar.
PENDING_ENGINE_IMPORTS: frozenset[str] = frozenset()


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                ids.add(id(first.value))
    return ids


def _string_of(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in node.values)
    return None


def _scan() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """``(catálogo/Inspector, imports de motor)``: ``{ruta relativa a util_bbdd: [motivo:línea, …]}`` fuera de metadata/."""
    catalog: dict[str, list[str]] = {}
    engine_imports: dict[str, list[str]] = {}
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        if rel.startswith("metadata/"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docs = _docstring_ids(tree)
        for node in ast.walk(tree):
            text = _string_of(node) if id(node) not in docs else None
            if text and CATALOG_RE.search(text) and SQL_SHAPE_RE.search(text):
                catalog.setdefault(rel, []).append(f"SQL:{node.lineno}")  # type: ignore[attr-defined]
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
                if name == "inspect" or (
                    name in INSPECTOR_METHODS
                    and isinstance(func, ast.Attribute)
                    and re.search(r"insp", ast.unparse(func.value), re.I)
                ):
                    catalog.setdefault(rel, []).append(f"Inspector:{node.lineno}")
            if isinstance(node, ast.ImportFrom):
                parts = (node.module or "").split(".")
                if "metadata" in parts:
                    tail = parts[parts.index("metadata") + 1 :]
                    names = {alias.name for alias in node.names}
                    if (tail and tail[0] in ENGINE_PACKAGES) or (not tail and names & set(ENGINE_PACKAGES)):
                        engine_imports.setdefault(rel, []).append(f"import:{node.lineno}")
    return catalog, engine_imports


@pytest.fixture(scope="module")
def scan() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    return _scan()


def test_catalog_sql_and_inspector_only_in_metadata(scan: tuple[dict[str, list[str]], dict[str, list[str]]]) -> None:
    catalog, _ = scan
    new = {f: hits for f, hits in catalog.items() if f not in EXCEPTIONS and f not in PENDING_CATALOG}
    assert not new, (
        f"SQL de catálogo o Inspector fuera de metadata/ (Regla #1). Muévelo a metadata/ y léelo desde allí: {new}"
    )


def test_consumers_do_not_import_engine_packages(scan: tuple[dict[str, list[str]], dict[str, list[str]]]) -> None:
    _, engine_imports = scan
    new = {f: hits for f, hits in engine_imports.items() if f not in PENDING_ENGINE_IMPORTS}
    assert not new, f"Import de metadata.<motor> fuera de metadata/ (Regla #2): usa la API de metadata/. {new}"


def test_pending_lists_only_shrink(scan: tuple[dict[str, list[str]], dict[str, list[str]]]) -> None:
    catalog, engine_imports = scan
    stale = sorted(f for f in PENDING_CATALOG if f not in catalog and f not in EXCEPTIONS) + sorted(
        f for f in PENDING_ENGINE_IMPORTS if f not in engine_imports
    )
    assert not stale, f"Entradas pendientes ya resueltas: quítalas de PENDING_* (trinquete). {stale}"


def test_exceptions_are_documented() -> None:
    assert all(reason.strip() for reason in EXCEPTIONS.values())
    assert all((SRC / f).is_file() for f in EXCEPTIONS)
