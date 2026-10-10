"""Comprobador de imports y métodos de los puntos de entrada en bloques de código de docs.

Recorre cada .md por líneas (no regex de fences): abre un bloque con ``` o ~~~ (con o sin
sangría), lo cierra con un fence del mismo carácter y longitud >= la de apertura.
Bloques python/py/pycon/python3 o sin lenguaje.

1. Imports de util_bbdd: el módulo se importa y cada nombre se resuelve (atributo o submódulo).
2. Métodos: variables ligadas a un punto de entrada (x = Clase(...), with Clase(...) as x,
   x = await Clase.create(...)) y llamadas x.m(...) / x.attr -> existe en la clase.
   Además, nombres convencionales (manager, mgr, db, sync_mgr, async_mgr...) contra los managers.

Uso: python doc_check.py lista.txt [salida.txt]
"""

from __future__ import annotations

import ast
import importlib
import re
import sys
import textwrap
from pathlib import Path

CODE_LANGS = {"", "python", "py", "pycon", "python3", "py3"}
IMPORT_FROM = re.compile(r"^\s*from\s+(util_bbdd[\w.]*)\s+import\s+(.+)$")
IMPORT_PLAIN = re.compile(r"^\s*import\s+(util_bbdd[\w.]*)")
CONVENTIONAL = re.compile(r"\b(manager|mgr|db|sync_mgr|async_mgr|sync_manager|async_manager|db_manager)\.(\w+)\s*\(")

ENTRY_POINTS = {
    "SyncDatabaseManager": "util_bbdd",
    "AsyncDatabaseManager": "util_bbdd",
    "BulkCrud": "util_bbdd",
    "DumpOrchestrator": "util_bbdd",
    "MigrationPlanner": "util_bbdd",
    "SchemaComparator": "util_bbdd",
}


def blocks(text: str):
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"^(\s*)(`{3,}|~{3,})\s*([\w+-]*)", lines[i])
        if not m:
            i += 1
            continue
        indent, fence, lang = m.group(1), m.group(2), m.group(3).lower()
        start = i + 1
        j = start
        body = []
        while j < len(lines):
            c = re.match(r"^\s*(`{3,}|~{3,})\s*$", lines[j])
            if c and c.group(1)[0] == fence[0] and len(c.group(1)) >= len(fence):
                break
            body.append(lines[j][len(indent):] if lines[j].startswith(indent) else lines[j].lstrip())
            j += 1
        yield start + 1, lang, body
        i = j + 1


def strip_pycon(body: list[str]) -> list[str]:
    if not any(b.lstrip().startswith((">>>", "...")) for b in body):
        return body
    out = []
    for b in body:
        s = b.lstrip()
        if s.startswith(">>> ") or s == ">>>":
            out.append(s[4:])
        elif s.startswith("... ") or s == "...":
            out.append(s[4:])
    return out


def resolve_entry(name: str):
    mod = importlib.import_module(ENTRY_POINTS[name])
    return getattr(mod, name)


def check_import(mod: str, names: list[str]) -> list[str]:
    errs = []
    try:
        m = importlib.import_module(mod)
    except Exception as e:  # noqa: BLE001
        return [f"no se importa {mod}: {type(e).__name__}: {e}"]
    for n in names:
        if n == "*":
            continue
        if hasattr(m, n):
            continue
        try:
            importlib.import_module(f"{mod}.{n}")
        except Exception:  # noqa: BLE001
            errs.append(f"{mod} no tiene {n}")
    return errs


def parse_names(raw: str) -> list[str]:
    raw = raw.split("#")[0].strip().strip("()").strip("\\").strip()
    out = []
    for part in raw.split(","):
        part = part.strip().strip("()")
        if not part:
            continue
        out.append(part.split(" as ")[0].strip())
    return out


def analyse(src: str) -> tuple[list[tuple[str, list[str]]], dict[str, str], list[tuple[str, str, int]], bool]:
    """Devuelve imports, vars->clase, accesos (var, attr, línea), parse_ok."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return [], {}, [], False
    imports: list[tuple[str, list[str]]] = []
    binds: dict[str, str] = {}
    access: list[tuple[str, str, int]] = []

    def entry_of(call: ast.AST) -> str | None:
        if isinstance(call, ast.Await):
            call = call.value
        if not isinstance(call, ast.Call):
            return None
        f = call.func
        if isinstance(f, ast.Name) and f.id in ENTRY_POINTS:
            return f.id
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in ENTRY_POINTS:
            return f.value.id  # Clase.create(...)
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("util_bbdd"):
            imports.append((node.module, [a.name for a in node.names]))
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("util_bbdd"):
                    imports.append((a.name, []))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            e = entry_of(node.value) if node.value is not None else None
            if e:
                for t in targets:
                    if isinstance(t, ast.Name):
                        binds[t.id] = e
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for it in node.items:
                e = entry_of(it.context_expr)
                if e and isinstance(it.optional_vars, ast.Name):
                    binds[it.optional_vars.id] = e
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in binds:
            access.append((node.value.id, node.attr, node.lineno))
    return imports, binds, access, True


def main() -> int:
    lst = Path(sys.argv[1]).read_text(encoding="utf-8").split()
    out_lines: list[str] = []
    n_imp = n_meth = 0
    problems = 0
    unparsed = 0
    n_incl = 0
    n_allowed = 0
    allow_file = Path(__file__).with_name("doc_check_allow.txt")
    allow = {
        ln.strip() for ln in allow_file.read_text(encoding="utf-8").splitlines() if ln.strip() and ln[0] != "#"
    }
    from util_bbdd import AsyncDatabaseManager, SyncDatabaseManager

    for f in lst:
        p = Path(f)
        if not p.exists():
            out_lines.append(f"{f}: (borrada o movida; se omite)")
            continue
        text = p.read_text(encoding="utf-8")
        for start, lang, body in blocks(text):
            if lang not in CODE_LANGS:
                continue
            body = strip_pycon(body)
            inc = [re.match(r'^\s*--8<--\s+"([^"]+\.py)"', b) for b in body]
            if any(inc):
                n_incl += 1
                expanded = []
                for b, m in zip(body, inc):
                    expanded.extend(
                        Path("docs", m.group(1)).read_text(encoding="utf-8").splitlines() if m else [b]
                    )
                body = expanded
                start = 1
                f_report = f"{f} -> docs/{[m for m in inc if m][0].group(1)}"
            else:
                f_report = f
            src = textwrap.dedent("\n".join(body))
            imports, binds, access, ok = analyse(src)
            if not ok:
                if "util_bbdd" in src or CONVENTIONAL.search(src):
                    unparsed += 1
                    out_lines.append(f"{f_report}:{start}: (aviso) bloque no parseable; comprobación por líneas")
                # por líneas
                for k, line in enumerate(body):
                    m = IMPORT_FROM.match(line)
                    if m and not m.group(2).strip().startswith("("):
                        imports.append((m.group(1), parse_names(m.group(2))))
                    elif (m2 := IMPORT_PLAIN.match(line)):
                        imports.append((m2.group(1), []))
            for mod, names in imports:
                n_imp += 1
                for e in check_import(mod, names):
                    if f"{f}:{start}" in allow:
                        n_allowed += 1
                        continue
                    problems += 1
                    out_lines.append(f"{f_report}:{start}: IMPORT {e}")
            for var, attr, ln in access:
                n_meth += 1
                cls = resolve_entry(binds[var])
                if not hasattr(cls, attr):
                    problems += 1
                    out_lines.append(f"{f_report}:{start + ln - 1}: METODO {binds[var]}.{attr} no existe ({var})")
            bound = set(binds)
            for k, line in enumerate(src.splitlines()):
                for m in CONVENTIONAL.finditer(line):
                    if m.group(1) in bound:
                        continue
                    n_meth += 1
                    a = m.group(2)
                    if not (hasattr(SyncDatabaseManager, a) or hasattr(AsyncDatabaseManager, a)):
                        problems += 1
                        out_lines.append(f"{f_report}:{start + k}: METODO {m.group(1)}.{a} no existe en los managers")
    out_lines.append(
        f"páginas: {len(lst)}; inclusiones .py: {n_incl}; imports comprobados: {n_imp}; accesos a métodos: {n_meth}; "
        f"bloques no parseables con util_bbdd: {unparsed}; excepciones registradas: {n_allowed}; problemas: {problems}"
    )
    report = "\n".join(out_lines)
    print(report)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(report + "\n", encoding="utf-8")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
