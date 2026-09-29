"""D2: inventario de ``MigrationWarning(...)`` en src/util_bbdd/migrate: qué se pasa en ``oracle_type`` y ``target_type``."""

import ast
import collections
import pathlib

ROOT = pathlib.Path("src/util_bbdd/migrate")
by_oracle: collections.Counter[str] = collections.Counter()
examples: dict[str, set[str]] = collections.defaultdict(set)
pairs: collections.Counter[tuple[str, str]] = collections.Counter()
total = 0
for path in sorted(ROOT.rglob("*.py")):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "MigrationWarning":
            total += 1
            kw = {k.arg: ast.unparse(k.value) for k in node.keywords}
            oracle = kw.get("oracle_type", "<posicional>")
            target = kw.get("target_type", "<posicional>")
            by_oracle[oracle] += 1
            examples[oracle].add(path.relative_to(ROOT).as_posix())
            pairs[(oracle, target[:45])] += 1
print(f"MigrationWarning(...) en src: {total}\n")
print("oracle_type (expresión) -> usos -> ficheros")
for expr, n in by_oracle.most_common():
    files = sorted(examples[expr])
    print(f"  {n:3d}  {expr[:60]:60s}  {', '.join(files)[:110]}")
print("\npares (oracle_type, target_type) más frecuentes")
for (o, t), n in pairs.most_common(40):
    print(f"  {n:3d}  {o[:40]:40s} | {t}")
