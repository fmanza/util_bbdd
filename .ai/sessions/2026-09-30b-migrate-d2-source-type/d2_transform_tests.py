"""D2: adapta tests/ al corte de ``oracle_type``.  ``python d2_transform_tests.py [--apply]``.

- ``MigrationWarning(..., oracle_type=X)`` → ``category=…`` (+ ``source_type=X`` si X es un tipo).
- ``CanonicalColumn(..., oracle_type=X)`` → ``source_type=X``.
- ``a.oracle_type <op> literal(es)`` → ``a.category`` (literal normalizado) o ``a.source_type`` según el literal.
- ``a.oracle_type`` sin comparación → ``a.source_type`` salvo que ``a`` parezca un aviso (se lista para revisión).
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys

APPLY = "--apply" in sys.argv
ROOT = pathlib.Path("tests")
CATEGORY = {
    "IDENTIFIER": "IDENTIFIER",
    "IDENTIFIER_CASE_COLLISION": "IDENTIFIER_CASE_COLLISION",
    "FOREIGN KEY": "FOREIGN_KEY",
    "FOREIGN_KEY": "FOREIGN_KEY",
    "INDEX": "INDEX",
    "AUTO_INCREMENT": "AUTO_INCREMENT",
    "VIEW": "VIEW",
    "VIEW_DEFINITION": "VIEW",
    "USER": "VIEW",
    "PROCEDURE": "ROUTINE",
    "FUNCTION": "ROUTINE",
    "PACKAGE": "ROUTINE",
    "PACKAGE BODY": "ROUTINE",
    "ROUTINE": "ROUTINE",
    "TYPE": "TYPE",
    "DEFAULT": "DEFAULT",
}
WARNING_LIKE = re.compile(r"(^|[._])(w|warn|warning|warnings|aviso|avisos|collision\w*|x)(\b|\[)")
review: list[str] = []


def literals(node: ast.expr) -> list[ast.Constant] | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)) and all(
        isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts
    ):
        return list(node.elts)  # type: ignore[arg-type]
    return None


def process(path: pathlib.Path) -> int:
    text = path.read_text(encoding="utf-8")
    if "oracle_type" not in text:
        return 0
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    def pos(lineno: int, col: int) -> int:
        return offsets[lineno - 1] + len(lines[lineno - 1].encode("utf-8")[:col].decode("utf-8"))

    def span(node: ast.AST) -> tuple[int, int]:
        return pos(node.lineno, node.col_offset), pos(node.end_lineno, node.end_col_offset)  # type: ignore[attr-defined]

    edits: list[tuple[int, int, str]] = []
    handled_attrs: set[int] = set()
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            callee = ast.unparse(node.func).split(".")[-1]
            for kw in node.keywords:
                if kw.arg != "oracle_type":
                    continue
                start, end = span(kw)
                value_src = text[slice(*span(kw.value))]
                if callee == "MigrationWarning":
                    if isinstance(kw.value, ast.Constant) and kw.value.value in CATEGORY:
                        new = f'category="{CATEGORY[kw.value.value]}"'
                    else:
                        new = f'category="TYPE", source_type={value_src}'
                else:  # CanonicalColumn o helpers de test con parámetro oracle_type
                    new = f"source_type={value_src}"
                edits.append((start, end, new))
        elif isinstance(node, ast.Compare):
            left = node.left
            if isinstance(left, ast.Attribute) and left.attr == "oracle_type" and len(node.comparators) == 1:
                lits = literals(node.comparators[0])
                if lits is None:
                    continue
                handled_attrs.add(id(left))
                end = pos(left.end_lineno, left.end_col_offset)
                if all(c.value in CATEGORY for c in lits):
                    edits.append((end - len("oracle_type"), end, "category"))
                    for c in lits:
                        if CATEGORY[c.value] != c.value:
                            s, e = span(c)
                            edits.append((s, e, f'"{CATEGORY[c.value]}"'))
                else:
                    edits.append((end - len("oracle_type"), end, "source_type"))
        elif isinstance(node, ast.arg) and node.arg == "oracle_type":
            review.append(f"{path}:{node.lineno}: parámetro oracle_type (helper de test)")
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "oracle_type" and id(node) not in handled_attrs:
            owner = ast.unparse(node.value)
            end = pos(node.end_lineno, node.end_col_offset)
            if WARNING_LIKE.search(owner):
                review.append(f"{path}:{node.lineno}: lectura {owner}.oracle_type (¿aviso?)")
                continue
            edits.append((end - len("oracle_type"), end, "source_type"))
    edits.sort()
    kept: list[tuple[int, int, str]] = []
    for edit in edits:
        if kept and edit[0] >= kept[-1][0] and edit[1] <= kept[-1][1]:
            continue
        kept.append(edit)
    for start, end, new in reversed(kept):
        text = text[:start] + new + text[end:]
    if APPLY:
        path.write_text(text, encoding="utf-8", newline="")
    return len(kept)


total = sum(process(p) for p in sorted(ROOT.rglob("*.py")))
print(f"ediciones: {total} ({'aplicadas' if APPLY else 'simulación'})")
print(f"para revisar a mano: {len(review)}")
for item in review:
    print("  " + item)
