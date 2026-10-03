"""Inventario estático de la extracción de metadatos (prototipo de la guarda del grupo G).

Recorre ``src/util_bbdd`` con ``ast`` y lista, por fichero y línea:

- cadenas de código (no docstrings) con SQL de catálogo,
- llamadas a ``inspect(...)`` y a métodos de ``Inspector`` (``get_columns``, ``get_multi_*``…) sobre objetos que no
  son managers,
- imports de ``metadata`` desde otros paquetes.

    python scan_catalog.py [--json salida.json]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4] / "src" / "util_bbdd"

CATALOG_RE = re.compile(
    r"information_schema|\b(all|user|dba)_(tables|tab_\w+|cons_\w+|constraints|indexes|ind_\w+|views|objects|source|"
    r"procedures|arguments|sequences|triggers|synonyms|users|col_comments|mviews|types|tab_identity_cols|db_links|"
    r"dependencies|part_\w+|segments|tablespaces)\b|dbms_metadata|pg_catalog|\bpg_get_\w+|\bpg_(class|attribute|"
    r"constraint|index|namespace|proc|depend|description|type|tables|views|sequences?|settings|roles|database|"
    r"tablespace|stat\w*)\b|sqlite_(master|schema|temp_master|sequence)|\bpragma\b|\bsys\.\w+|object_definition|"
    r"objectproperty|svv_\w+|pg_table_def|^\s*show\s+(create|full|index|keys|columns|tables|procedure|function|"
    r"variables|table|triggers|status|grants|databases)",
    re.IGNORECASE | re.MULTILINE,
)
SQL_HINT = re.compile(r"\b(select|from|where|show|pragma|exec)\b", re.IGNORECASE)
INSPECTOR_METHODS = {
    "get_columns", "get_pk_constraint", "get_foreign_keys", "get_indexes", "get_unique_constraints",
    "get_check_constraints", "get_table_names", "get_view_names", "get_view_definition", "get_table_comment",
    "get_sequence_names", "get_schema_names", "has_table", "get_temp_table_names", "get_multi_columns",
    "get_multi_pk_constraint", "get_multi_foreign_keys", "get_multi_indexes", "get_multi_unique_constraints",
    "get_multi_table_comment", "get_multi_check_constraints", "get_sorted_table_and_fkc_names", "get_table_options",
}  # fmt: skip


def _docstring_nodes(tree: ast.AST) -> set[int]:
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
        return "".join(v.value if isinstance(v, ast.Constant) else "{…}" for v in node.values)
    return None


def scan(root: Path = ROOT) -> dict[str, list[dict[str, object]]]:
    out: dict[str, list[dict[str, object]]] = {"catalog_sql": [], "inspector": [], "metadata_imports": []}
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root.parent).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docs = _docstring_nodes(tree)
        in_metadata = rel.startswith("util_bbdd/metadata/")
        seen_lines: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr) or (isinstance(node, ast.Constant) and id(node) not in docs):
                s = _string_of(node)
                if s and node.lineno not in seen_lines and CATALOG_RE.search(s) and SQL_HINT.search(s):
                    # Mensajes de log/excepción: frase sin estructura SQL
                    if not re.search(r"\bselect\b.+\bfrom\b|^\s*(select|show|pragma|exec)\b|\bfrom\s+\S+|\bjoin\b", s, re.I | re.S):
                        continue
                    seen_lines.add(node.lineno)
                    out["catalog_sql"].append(
                        {"file": rel, "line": node.lineno, "in_metadata": in_metadata,
                         "match": CATALOG_RE.search(s).group(0), "sql": " ".join(s.split())[:140]}  # type: ignore[union-attr]
                    )  # fmt: skip
            if isinstance(node, ast.Call):
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
                if name == "inspect" or (
                    name in INSPECTOR_METHODS
                    and isinstance(f, ast.Attribute)
                    and re.search(r"insp|inspector", ast.unparse(f.value), re.I)
                ):
                    out["inspector"].append(
                        {"file": rel, "line": node.lineno, "in_metadata": in_metadata, "call": ast.unparse(node)[:100]}
                    )
            if isinstance(node, ast.ImportFrom) and not in_metadata:
                mod = node.module or ""
                if "metadata" in mod.split("."):
                    out["metadata_imports"].append(
                        {"file": rel, "line": node.lineno, "module": mod, "names": [a.name for a in node.names]}
                    )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    res = scan()
    if a.json:
        a.json.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for key, items in res.items():
        outside = [i for i in items if not i.get("in_metadata")]
        print(f"## {key}: {len(items)} (fuera de metadata/: {len(outside)})")
        for i in outside:
            print(f"  {i['file']}:{i['line']}  {i.get('match') or i.get('call') or i.get('module')}  {i.get('sql', '')[:90]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
