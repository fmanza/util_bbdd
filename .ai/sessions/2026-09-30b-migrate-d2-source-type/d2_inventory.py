"""D2: inventario detallado de MigrationWarning(...) y de usos de ``oracle_type`` (src o tests) por AST."""

import ast
import pathlib
import sys

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "src/util_bbdd/migrate")
LITERAL = {"IDENTIFIER", "IDENTIFIER_CASE_COLLISION", "FOREIGN KEY", "INDEX", "AUTO_INCREMENT", "VIEW",
           "VIEW_DEFINITION", "USER"}

for path in sorted(ROOT.rglob("*.py")):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "MigrationWarning":
            kw = {k.arg: k.value for k in node.keywords}
            if "oracle_type" not in kw:
                print(f"POSICIONAL {path}:{node.lineno}")
                continue
            expr = ast.unparse(kw["oracle_type"])
            if isinstance(kw["oracle_type"], ast.Constant) and kw["oracle_type"].value in LITERAL:
                continue
            target = ast.unparse(kw.get("target_type", ast.Constant("")))[:40]
            msg = ast.unparse(kw.get("message", ast.Constant("")))[:110].replace("\n", " ")
            print(f"{path.relative_to(ROOT)}:{node.lineno}  oracle_type={expr[:40]:40s} target={target:40s} msg={msg}")
