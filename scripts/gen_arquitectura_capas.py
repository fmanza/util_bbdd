#!/usr/bin/env python3
"""Regenerate the layers-and-imports figure used in docs/architecture.md.

Measures the real imports between the top-level packages of src/util_bbdd with ``ast``, checks that every arrow
drawn in the figure exists in the code (and that no measured arrow is missing), and rewrites:

    docs/assets/diagrams/arquitectura-capas.svg
    docs/assets/css/arquitectura-capas.css

The layout, the level of each package and the three flagged findings are placed by hand below. If the check fails
the figure no longer matches the code: fix the drawing (or the code) and run the script again. Nothing is written
while the check fails.

Usage:
    python scripts/gen_arquitectura_capas.py
    python scripts/gen_arquitectura_capas.py --edges     # print the measured import table and exit
"""

from __future__ import annotations

import argparse
import ast
import sys

from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "util_bbdd"
OUT_SVG = ROOT / "docs" / "assets" / "diagrams" / "arquitectura-capas.svg"
OUT_CSS = ROOT / "docs" / "assets" / "css" / "arquitectura-capas.css"
PKG = "util_bbdd"

# Levels according to .ai/architecture.md. models.py and async_utils.py have no level there; they are drawn with
# Foundation because they import nothing from the library.
LEVEL = {
    "_core": 1, "_drivers": 1, "core": 1, "models": 1, "async_utils": 1,
    "connection": 2, "factory": 2, "query": 2, "validators": 2, "executors": 2, "metadata": 2, "results": 2,
    "managers": 3, "bulk": 3, "comparar": 3, "dump": 3, "migrate": 3, "analysis": 3, "doc": 3,
}  # fmt: skip

# Every arrow drawn between packages. Arrows into Foundation from levels 2 and 3 are collapsed into one.
DRAWN = {
    ("dump", "bulk"), ("doc", "analysis"), ("analysis", "managers"), ("doc", "managers"),
    ("bulk", "connection"), ("metadata", "managers"), ("migrate", "metadata"),
    ("metadata", "query"), ("metadata", "results"), ("executors", "query"), ("executors", "results"),
    ("query", "validators"), ("factory", "connection"), ("connection", "factory"), ("_drivers", "_core"),
} | {("managers", t) for t in ("connection", "factory", "executors", "metadata", "query", "results")}  # fmt: skip

# Top-level modules deliberately left out of the figure.
EXCLUDED = {"docs_build_plugin"}  # MkDocs plugin (documentation ZIP); not part of the runtime library


# --------------------------------------------------------------------------------------------------------------------
# Measurement
# --------------------------------------------------------------------------------------------------------------------


@dataclass
class Edge:
    """Imports from one top-level package to another, split by where the import statement lives."""

    module: int = 0  # module level
    lazy: int = 0  # inside a function
    typing: int = 0  # under ``if TYPE_CHECKING``
    first: dict[str, str] = field(default_factory=dict)  # kind -> "relative/path.py:line" of the first one seen

    @property
    def total(self) -> int:
        return self.module + self.lazy + self.typing


class _ImportVisitor(ast.NodeVisitor):
    def __init__(self, path: Path, top_names: set[str]) -> None:
        self.path = path
        self.top_names = top_names
        self.context: list[str] = []
        self.hits: list[tuple[str, str, int]] = []  # (target package, kind, line)

    def _kind(self) -> str:
        if "TC" in self.context:
            return "typing"
        if "FN" in self.context:
            return "lazy"
        return "module"

    def _add(self, target: str, node: ast.stmt) -> None:
        self.hits.append((target, self._kind(), node.lineno))

    def _add_names(self, node: ast.ImportFrom) -> None:
        # ``from util_bbdd import x``: x is a package/module of its own, or a re-export of the root __init__
        for alias in node.names:
            self._add(alias.name if alias.name in self.top_names else "__init__", node)

    def visit_If(self, node: ast.If) -> None:
        if "TYPE_CHECKING" not in ast.unparse(node.test):
            self.generic_visit(node)
            return
        self.context.append("TC")
        for child in node.body:
            self.visit(child)
        self.context.pop()
        for child in node.orelse:
            self.visit(child)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.context.append("FN")
        self.generic_visit(node)
        self.context.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == PKG or alias.name.startswith(PKG + "."):
                parts = alias.name.split(".")
                self._add(parts[1] if len(parts) > 1 else "__init__", node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        if node.level == 0:
            if module != PKG and not module.startswith(PKG + "."):
                return
            parts = module.split(".")
            if len(parts) == 1:
                self._add_names(node)
            else:
                self._add(parts[1], node)
            return
        base = list(self.path.relative_to(SRC).parts[:-1])  # package that contains this file
        base = base[: max(0, len(base) - (node.level - 1))]
        full = base + (module.split(".") if module else [])
        if full:
            self._add(full[0], node)
        else:
            self._add_names(node)


def _top_of(path: Path) -> str:
    rel = path.relative_to(SRC)
    return rel.parts[0] if len(rel.parts) > 1 else rel.stem


def top_level_names() -> set[str]:
    packages = {p.name for p in SRC.iterdir() if p.is_dir() and not p.name.startswith("__") and any(p.rglob("*.py"))}
    return packages | {p.stem for p in SRC.glob("*.py") if p.stem != "__init__"}


def measure() -> tuple[dict[tuple[str, str], Edge], int]:
    """Return the import edges between top-level packages and the number of files parsed."""
    top_names = top_level_names()
    edges: dict[tuple[str, str], Edge] = {}
    files = sorted(SRC.rglob("*.py"))
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            sys.exit(f"[gen_arquitectura_capas] ERROR: cannot parse {path}: {exc}")
        source = _top_of(path)
        visitor = _ImportVisitor(path, top_names)
        visitor.visit(tree)
        for target, kind, line in visitor.hits:
            if target == source:
                continue
            edge = edges.setdefault((source, target), Edge())
            setattr(edge, kind, getattr(edge, kind) + 1)
            edge.first.setdefault(kind, f"{path.relative_to(SRC).as_posix()}:{line}")
    return edges, len(files)


def verify(edges: dict[tuple[str, str], Edge]) -> list[str]:
    """Compare what the figure claims with what was measured; return one message per mismatch."""
    problems: list[str] = []
    names = top_level_names() - EXCLUDED
    problems += [
        f"package not placed in any level (add it to LEVEL and draw it): {n}" for n in sorted(names - set(LEVEL))
    ]
    problems += [f"package drawn but no longer in src/: {n}" for n in sorted(set(LEVEL) - names)]
    measured = {pair: e for pair, e in edges.items() if pair[0] in LEVEL and pair[1] in LEVEL}
    problems += [f"drawn but not found in the code: {s} -> {t}" for s, t in sorted(DRAWN - set(measured))]
    for s, t in sorted(set(measured) - DRAWN):
        if not (LEVEL[t] == 1 and LEVEL[s] > 1):  # those are the collapsed arrow into Foundation
            problems.append(f"found in the code but not drawn: {s} -> {t}")
    upward = sorted(pair for pair in measured if LEVEL[pair[0]] < LEVEL[pair[1]])
    if upward != [("metadata", "managers")]:
        problems.append(f"upward imports differ from the single type-only one drawn (badge 2): {upward}")
    up = measured.get(("metadata", "managers"))
    if up is not None and (up.module or up.lazy):
        problems.append("metadata -> managers is no longer type-only (the figure says 'solo tipado')")
    back = measured.get(("connection", "factory"))
    if back is not None and (back.total, back.module) != (1, 1):
        problems.append(f"connection -> factory is no longer a single module-level import (found {back.total})")
    return problems


def print_edges(edges: dict[tuple[str, str], Edge]) -> None:
    print(f"{'from':<14}{'-> to':<16}{'module':>7}{'lazy':>6}{'typing':>8}")
    for (s, t), e in sorted(edges.items()):
        print(f"{s:<14}-> {t:<13}{e.module:>7}{e.lazy:>6}{e.typing:>8}")


# --------------------------------------------------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------------------------------------------------


class _Facts(NamedTuple):
    to_foundation: int  # packages of levels 2 and 3 that import from Foundation
    factory_to_connection: int
    connection_to_factory: int
    cycle_file: str  # the file whose import closes the cycle
    lazy_where: str  # bulk -> connection lazy import, "path:line"


def _facts(edges: dict[tuple[str, str], Edge]) -> _Facts:
    to_foundation = {s for (s, t) in edges if s in LEVEL and t in LEVEL and LEVEL[t] == 1 and LEVEL[s] > 1}
    back = edges[("connection", "factory")]
    return _Facts(
        to_foundation=len(to_foundation),
        factory_to_connection=edges[("factory", "connection")].total,
        connection_to_factory=back.total,
        cycle_file=back.first["module"].rsplit(":", 1)[0],
        lazy_where=edges[("bulk", "connection")].first["lazy"],
    )


NODE_W, NODE_H = 112, 50
COLS = [30, 168, 306, 444, 582, 720, 858]
Y3, Y2A, Y2B, Y1 = 58, 256, 354, 526  # top of the node rows: level 3, level 2 (two rows), level 1
ARIA = (
    "Los tres niveles de util_bbdd con sus imports reales: connection y factory se importan mutuamente, "
    "metadata importa managers solo para tipado y analysis y doc importan el manager concreto."
)


def _marker(marker_id: str, cls: str) -> str:
    return (
        f'<marker id="{marker_id}" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="9" markerHeight="9" '
        f'markerUnits="userSpaceOnUse" orient="auto"><path class="{cls}" d="M0 0L10 5L0 10z" fill="currentColor"/></marker>'
    )


class _Svg:
    """Accumulates SVG elements, one per line and never a blank line (a blank line would split the HTML block in Markdown)."""

    def __init__(self) -> None:
        self.parts: list[str] = []

    def node(self, x: int, y: int, name: str, sub: str, w: int = NODE_W, extra: str = "") -> None:
        cx = x + w / 2
        self.parts.append(
            f'<g class="arq-node{extra}"><rect x="{x}" y="{y}" width="{w}" height="{NODE_H}" rx="6" fill="none" stroke="currentColor"/>'
            f'<text class="arq-name" x="{cx:g}" y="{y + 21}" text-anchor="middle" font-family="ui-monospace,Consolas,monospace" font-size="13" fill="currentColor">{name}</text>'
            f'<text class="arq-sub" x="{cx:g}" y="{y + 38}" text-anchor="middle" font-family="system-ui,sans-serif" font-size="11.5" fill="currentColor">{sub}</text></g>'
        )

    def edge(self, d: str, kind: str = "", head: str = "arq-h") -> None:
        self.parts.append(
            f'<path class="arq-edge {kind}" d="{d}" fill="none" stroke="currentColor" stroke-width="1.4" marker-end="url(#{head})"/>'
        )

    def text(self, x: int, y: int, s: str, cls: str = "arq-lbl", anchor: str = "start") -> None:
        self.parts.append(
            f'<text class="{cls}" x="{x}" y="{y}" text-anchor="{anchor}" font-family="system-ui,sans-serif" font-size="11.5" fill="currentColor">{s}</text>'
        )

    def badge(self, x: int, y: int, n: int, kind: str) -> None:
        self.parts.append(
            f'<g class="arq-badge"><circle class="arq-badge-{kind}" cx="{x}" cy="{y}" r="8.5" fill="currentColor"/>'
            f'<text class="arq-badge-num" x="{x}" y="{y + 4}" text-anchor="middle" font-family="system-ui,sans-serif" font-size="11" font-weight="700" fill="#fff">{n}</text></g>'
        )


def render_svg(f: _Facts) -> str:
    c, s = COLS, _Svg()
    s.parts.append(
        f'<svg class="arq" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 648" role="img" aria-label="{ARIA}" font-family="system-ui,sans-serif">'
    )
    s.parts.append(
        "<defs>"
        + _marker("arq-h", "arq-head")
        + _marker("arq-h-warn", "arq-head-warn")
        + _marker("arq-h-cycle", "arq-head-cycle")
        + "</defs>"
    )

    # bands
    for cls, y, h in (("3", 12, 126), ("2", 214, 210), ("1", 476, 124)):
        s.parts.append(
            f'<rect class="arq-band arq-band-{cls}" x="8" y="{y}" width="984" height="{h}" rx="10" fill="none" stroke="currentColor" stroke-opacity=".25"/>'
        )
    for y, label, note in (
        (36, "NIVEL 3 · ESPECIALIZACIÓN", "puede importar de N2 y N1"),
        (238, "NIVEL 2 · SERVICIOS", "solo de N1"),
        (500, "NIVEL 1 · FOUNDATION", "no importa de otros niveles"),
    ):
        s.parts.append(
            f'<text class="arq-band-label" x="30" y="{y}" font-size="11" font-weight="600" letter-spacing="1.3" fill="currentColor">{label}</text>'
        )
        s.text(970, y, note, "arq-band-note", "end")

    # edges (before the nodes so the node fill covers any overlap)
    s.edge(f"M{c[1]} 83 H{c[0] + NODE_W}")  # dump -> bulk
    s.edge(f"M{c[3] + NODE_W} 83 H{c[4]}")  # doc -> analysis
    s.edge(f"M{c[4] + NODE_W} 83 H{c[5]}", "warn", "arq-h-warn")  # analysis -> managers
    s.edge(f"M{c[3] + 56} {Y3} V44 H{c[5] + 56} V{Y3}", "warn", "arq-h-warn")  # doc -> managers (arc)
    s.edge(f"M86 {Y3 + NODE_H} V{Y2A}", "lazy")  # bulk -> connection (lazy)
    s.edge(f"M736 {Y3 + NODE_H} V214")  # managers -> level 2 band
    s.edge(f"M780 {Y2A} V{Y3 + NODE_H}", "warn", "arq-h-warn")  # metadata -> managers (type-only)
    s.edge(f"M900 {Y3 + NODE_H} V196 H822 V{Y2A}")  # migrate -> metadata
    for d in ("M752 306 V354", "M796 306 L900 354", "M876 306 L812 354", "M940 306 V354"):
        s.edge(d)  # {metadata, executors} -> {query, results}
    s.edge("M720 379 H694")  # query -> validators
    s.edge("M210 274 H142")  # factory -> connection
    s.edge("M142 294 H210", "cycle", "arq-h-cycle")  # connection -> factory (closes the cycle)
    s.edge("M500 424 V476")  # levels 2 and 3 -> Foundation
    s.edge("M190 551 H162")  # _drivers -> _core

    # nodes
    s.node(c[0], Y3, "bulk/", "recibe Engine")
    s.node(c[1], Y3, "dump/", "recibe Engine")
    s.node(c[2], Y3, "comparar/", "recibe Inspector")
    s.node(c[3], Y3, "doc/", "docs de la BD")
    s.node(c[4], Y3, "analysis/", "grafos de tablas")
    s.node(c[5], Y3, "managers/", "API pública")
    s.node(c[6], Y3, "migrate/", "migración DDL")
    s.node(30, Y2A, "connection/", "por motor")
    s.node(210, Y2A, "factory/", "Engine y pools")
    s.node(c[5], Y2A, "metadata/", "introspección")
    s.node(c[6], Y2A, "executors/", "sync / async")
    s.node(c[4], Y2B, "validators/", "params de query")
    s.node(c[5], Y2B, "query/", "registry")
    s.node(c[6], Y2B, "results/", "Row / Rows")
    s.node(30, Y1, "_core/", "excepciones, tipos", 132)
    s.node(190, Y1, "_drivers/", "detecta drivers", 132)
    s.node(350, Y1, "core/", "capacidades", 132)
    s.node(690, Y1, "models.py", "modelos compartidos", 132, " arq-shared")
    s.node(838, Y1, "async_utils.py", "maybe_await", 132, " arq-shared")

    # labels, badges and counters
    s.text(96, 180, f"import perezoso · {f.lazy_where}")
    s.text(728, 160, "importa connection, factory, executors,", anchor="end")
    s.text(728, 176, "metadata, query y results (6 de 7)", anchor="end")
    s.text(796, 186, "solo tipado")
    s.text(176, 268, f"×{f.factory_to_connection}", anchor="middle")
    s.text(176, 314, f"×{f.connection_to_factory}", "arq-lbl arq-lbl-cycle", "middle")
    s.text(30, 344, "un solo import cierra el ciclo:", "arq-lbl arq-lbl-cycle")
    s.parts.append(
        f'<text class="arq-lbl arq-lbl-cycle arq-lbl-mono" x="30" y="360" font-family="ui-monospace,Consolas,monospace" font-size="11" fill="currentColor">{f.cycle_file}</text>'
    )
    s.text(512, 447, f"{f.to_foundation} paquetes importan de Foundation")
    s.text(512, 463, "Foundation no importa hacia arriba (0 imports)")
    s.text(690, 516, "compartidos · sin nivel asignado")
    s.badge(176, 294, 1, "cycle")
    s.badge(780, 178, 2, "warn")
    s.badge(707, 68, 3, "warn")
    s.badge(638, 44, 3, "warn")

    # legend
    for x, kind, head, label in (
        (30, "", "arq-h", "import de módulo"),
        (230, "lazy", "arq-h", "import perezoso (dentro de una función)"),
        (540, "warn", "arq-h-warn", "contra una regla de nivel"),
        (770, "cycle", "arq-h-cycle", "ciclo"),
    ):
        s.edge(f"M{x} 620 H{x + 34}", kind, head)
        s.text(x + 44, 624, label)
    s.parts.append("</svg>")

    svg = "\n".join(s.parts) + "\n"
    if "\n\n" in svg:
        raise ValueError("the SVG must not contain blank lines: they would end the HTML block inside Markdown")
    return svg


CSS_HEAD = """/* Diagrama de capas e imports (docs/architecture.md). Tokens ligados a las variables de Material. */
.arq-figure {
  --arq-sans: var(--md-text-font-family, system-ui, sans-serif);
  --arq-mono: var(--md-code-font-family, ui-monospace, monospace);
  --arq-ink: var(--md-default-fg-color);
  --arq-muted: var(--md-default-fg-color--light);
  --arq-node: var(--md-default-bg-color);
  --arq-node-line: var(--md-default-fg-color--light);
  --arq-line: var(--md-default-fg-color);
  --arq-band-3: color-mix(in srgb, var(--md-default-fg-color) 3%, var(--md-default-bg-color));
  --arq-band-2: color-mix(in srgb, var(--md-default-fg-color) 6%, var(--md-default-bg-color));
  --arq-band-1: color-mix(in srgb, var(--md-default-fg-color) 10%, var(--md-default-bg-color));
  --arq-band-line: var(--md-default-fg-color--lightest);
  --arq-amber: #a45500;
  --arq-red: #c0261a;
  --arq-badge-ink: #fff;
  margin: 1.5em 0;
}
[data-md-color-scheme="slate"] .arq-figure { --arq-amber: #f0a03c; --arq-red: #ff8078; --arq-badge-ink: #101418; }
.arq-figure .arq-scroll { overflow-x: auto; }
.arq-figure svg.arq { min-width: 640px; }
.arq-figure figcaption { font-size: .8rem; color: var(--md-default-fg-color--light); margin-top: .5rem; }
"""

CSS_RULES = """.arq { display: block; width: 100%; height: auto; color: var(--arq-ink); font-family: var(--arq-sans); }
.arq .arq-band { stroke: var(--arq-band-line); stroke-opacity: 1; stroke-width: 1; }
.arq .arq-band-3 { fill: var(--arq-band-3); }
.arq .arq-band-2 { fill: var(--arq-band-2); }
.arq .arq-band-1 { fill: var(--arq-band-1); }
.arq .arq-band-label { fill: var(--arq-muted); font: 600 11px var(--arq-sans); letter-spacing: .12em; }
.arq .arq-band-note, .arq .arq-lbl, .arq .arq-sub { fill: var(--arq-muted); font: 400 11.5px var(--arq-sans); }
.arq .arq-node rect { fill: var(--arq-node); stroke: var(--arq-node-line); stroke-width: 1.2; }
.arq .arq-shared rect { stroke-dasharray: 4 3; }
.arq .arq-name { fill: var(--arq-ink); font: 500 13px var(--arq-mono); }
.arq .arq-edge { fill: none; stroke: var(--arq-line); stroke-width: 1.4; }
.arq .arq-edge.lazy { stroke-dasharray: 2 4; stroke-linecap: round; }
.arq .arq-edge.warn { stroke: var(--arq-amber); stroke-width: 1.8; stroke-dasharray: 6 4; }
.arq .arq-edge.cycle { stroke: var(--arq-red); stroke-width: 2.4; }
.arq .arq-head { fill: var(--arq-line); }
.arq .arq-head-warn { fill: var(--arq-amber); }
.arq .arq-head-cycle { fill: var(--arq-red); }
.arq .arq-badge-warn { fill: var(--arq-amber); }
.arq .arq-badge-cycle { fill: var(--arq-red); }
.arq .arq-badge-num { fill: var(--arq-badge-ink); font: 700 11px var(--arq-sans); }
.arq .arq-lbl-cycle { fill: var(--arq-red); }
.arq .arq-lbl-mono { font: 400 11px var(--arq-mono); }
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate the layers-and-imports figure for docs/architecture.md.")
    parser.add_argument("--edges", action="store_true", help="Print the measured import table and exit")
    args = parser.parse_args()

    edges, n_files = measure()
    if args.edges:
        print_edges(edges)
        return

    problems = verify(edges)
    if problems:
        print("[gen_arquitectura_capas] The figure no longer matches the code; nothing was written:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print("Run with --edges to see the measured table.", file=sys.stderr)
        sys.exit(1)

    facts = _facts(edges)
    for path, content in ((OUT_SVG, render_svg(facts)), (OUT_CSS, CSS_HEAD + CSS_RULES)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"[gen_arquitectura_capas] wrote {path.relative_to(ROOT).as_posix()}")
    print(f"[gen_arquitectura_capas] measured {n_files} files; {facts.to_foundation} packages import from Foundation.")
    print(
        "[gen_arquitectura_capas] Update the figcaption in docs/architecture.md if the version, date or file count changed."
    )


if __name__ == "__main__":
    main()
