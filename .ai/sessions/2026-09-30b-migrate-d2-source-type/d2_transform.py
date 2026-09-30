"""D2: transforma src/util_bbdd/migrate (sin ir/models.py, que se edita a mano).

1. ``MigrationWarning(..., oracle_type=X, ...)`` → ``category="…"`` (+ ``source_type=…`` si hay tipo del origen).
2. ``col/column/pk_col.oracle_type`` → ``.source_type``.
3. ``CanonicalColumn(..., oracle_type=X)`` → ``source_type=X``.
No toca ``mapping.oracle_type`` (tipo Oracle de destino del mapa de tipos) ni metadata/oracle ni los parámetros de
los mapas de tipos. Falla si encuentra un caso sin clasificar.
"""

from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path("src/util_bbdd/migrate")
SKIP = {ROOT / "ir" / "models.py"}
LITERAL_CATEGORY = {
    "IDENTIFIER": "IDENTIFIER",
    "IDENTIFIER_CASE_COLLISION": "IDENTIFIER_CASE_COLLISION",
    "FOREIGN KEY": "FOREIGN_KEY",
    "INDEX": "INDEX",
    "AUTO_INCREMENT": "AUTO_INCREMENT",
    "VIEW": "VIEW",
    "VIEW_DEFINITION": "VIEW",
    "USER": "VIEW",
}
IR_OBJECTS = {"col", "column", "pk_col"}
TYPE_FSTRING_PREFIXES = ("f'VARCHAR(", "f'VARBINARY(", "f'CHARACTER VARYING(", "f'{ss_base}(")


def classify(node: ast.expr, path: pathlib.Path) -> tuple[str, str | None]:
    src = ast.unparse(node)
    if isinstance(node, ast.Constant) and node.value in LITERAL_CATEGORY:
        return LITERAL_CATEGORY[node.value], None
    if src.startswith("f'SEQUENCE("):
        return "AUTO_INCREMENT", None
    if src == "pk_col.oracle_type":
        return "AUTO_INCREMENT", "pk_col.source_type"
    if src in ("routine_type", "routine.routine_type", "raw_type"):
        return "ROUTINE", None
    if src in ("oracle_token", "label"):
        return "VIEW", None
    if src == "source_type":
        return ("DEFAULT", "source_type") if path.name == "_default_fallback.py" else ("TYPE", "source_type")
    if src == "col.oracle_type":
        return "TYPE", "col.source_type"
    if src.startswith(TYPE_FSTRING_PREFIXES):
        return "TYPE", src
    raise SystemExit(f"SIN CLASIFICAR {path}:{node.lineno}: {src}")


def transform(path: pathlib.Path) -> int:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    def pos(lineno: int, col: int) -> int:
        # col_offset es en bytes UTF-8: convertir a índice de carácter en la línea
        line = lines[lineno - 1]
        return offsets[lineno - 1] + len(line.encode("utf-8")[:col].decode("utf-8"))

    edits: list[tuple[int, int, str]] = []
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            callee = ast.unparse(node.func)
            for kw in node.keywords:
                if kw.arg != "oracle_type":
                    continue
                start, end = pos(kw.lineno, kw.col_offset), pos(kw.end_lineno, kw.end_col_offset)
                if callee == "MigrationWarning":
                    category, source = classify(kw.value, path)
                    new = f'category="{category}"' + (f", source_type={source}" if source else "")
                    # la expresión de tipo puede contener lecturas col.oracle_type: se renombran aquí mismo
                    new = new.replace("col.oracle_type", "col.source_type")
                elif callee == "CanonicalColumn":
                    new = "source_type=" + text[pos(kw.value.lineno, kw.value.col_offset) : end]
                else:
                    raise SystemExit(f"keyword oracle_type= en {callee} {path}:{kw.lineno}")
                edits.append((start, end, new))
        elif isinstance(node, ast.Attribute) and node.attr == "oracle_type":
            owner = ast.unparse(node.value)
            if owner == "mapping":
                continue
            if owner not in IR_OBJECTS:
                raise SystemExit(f"lectura sin clasificar {path}:{node.lineno}: {owner}.oracle_type")
            end = pos(node.end_lineno, node.end_col_offset)
            edits.append((end - len("oracle_type"), end, "source_type"))
    # quitar ediciones contenidas en otra (lecturas dentro de un keyword ya reescrito)
    edits.sort()
    kept: list[tuple[int, int, str]] = []
    for edit in edits:
        if kept and edit[0] >= kept[-1][0] and edit[1] <= kept[-1][1]:
            continue
        kept.append(edit)
    for start, end, new in reversed(kept):
        text = text[:start] + new + text[end:]
    path.write_text(text, encoding="utf-8", newline="")
    return len(kept)


if __name__ == "__main__":
    total = 0
    for path in sorted(ROOT.rglob("*.py")):
        if path in SKIP:
            continue
        if "oracle_type" in path.read_text(encoding="utf-8"):
            n = transform(path)
            total += n
            print(f"{n:3d}  {path.as_posix()}")
    print("total", total)
    sys.exit(0)
