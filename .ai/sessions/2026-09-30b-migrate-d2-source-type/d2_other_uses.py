"""D2: usos de ``oracle_type`` que no son el keyword de MigrationWarning(...): lecturas y otros keywords/params."""

import ast
import collections
import pathlib
import sys

roots = [pathlib.Path(p) for p in (sys.argv[1:] or ["src/util_bbdd"])]
reads: collections.Counter[str] = collections.Counter()
kw_calls: collections.Counter[str] = collections.Counter()
params: collections.Counter[str] = collections.Counter()
names: collections.Counter[str] = collections.Counter()
for root in roots:
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel = path.as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "oracle_type":
                reads[f"{rel} :: {ast.unparse(node.value)}"] += 1
            elif isinstance(node, ast.Call):
                callee = ast.unparse(node.func)
                for k in node.keywords:
                    if k.arg == "oracle_type" and callee != "MigrationWarning":
                        kw_calls[f"{rel} :: {callee}"] += 1
            elif isinstance(node, ast.arg) and node.arg == "oracle_type":
                params[rel] += 1
            elif isinstance(node, ast.Name) and node.id == "oracle_type":
                names[rel] += 1
print("== lecturas .oracle_type (fichero :: objeto)")
for k, n in sorted(reads.items()):
    print(f"  {n:3d} {k}")
print("== keyword oracle_type= en otras llamadas")
for k, n in sorted(kw_calls.items()):
    print(f"  {n:3d} {k}")
print("== parámetros llamados oracle_type")
for k, n in sorted(params.items()):
    print(f"  {n:3d} {k}")
print("== variables/nombres oracle_type")
for k, n in sorted(names.items()):
    print(f"  {n:3d} {k}")
