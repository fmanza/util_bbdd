#!/usr/bin/env python3
"""Regenerate the layers-and-imports figure used in docs/architecture.md.

Measures the real imports between the top-level packages of src/util_bbdd with ``ast``, checks that every arrow
drawn in the figure exists in the code (and that no measured arrow is missing), and rewrites:

    docs/assets/diagrams/arquitectura-capas.svg
    docs/assets/css/arquitectura-capas.css
    docs/assets/diagrams/arquitectura-capas-tabla.txt   (layer table, included by docs/architecture.md)

The layout and the layer of each package (``LAYER``; the level is derived from it) are placed by hand below, and so is any
flagged finding (an amber arrow with a numbered badge; there are none today). If the check fails the figure no longer
matches the code: fix the drawing (or the code) and run the script again. Nothing is written while the check fails.

``measure()``, ``LAYER``, ``LEVEL`` and ``EXCLUDED`` are also used by tests/unit/test_architecture_import_rules.py, which
enforces Regla #6 (no cycles, imports only to strictly lower layers); keep their names and shapes.

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
OUT_TABLE = ROOT / "docs" / "assets" / "diagrams" / "arquitectura-capas-tabla.txt"
PKG = "util_bbdd"

# Regla #6 (architecture.instructions.md): a package imports only from packages in strictly lower layers. Packages in the
# same layer are independent of each other. The layers are assigned by role, not by the depth the graph happens to have.
# models.py and async_utils.py are root modules that count as Foundation: they import nothing from the library.
LAYER = {
    "_core": 1, "core": 1, "models": 1, "async_utils": 1,
    "_drivers": 2, "progress": 2,
    "results": 3, "validators": 3, "audit": 3,
    "connection": 4, "query": 4,
    "executors": 5, "factory": 5, "metadata": 5,
    "bulk": 6, "comparar": 6, "migrate": 6, "managers": 6, "analysis": 6,
    "dump": 7, "doc": 7,
}  # fmt: skip

# Each layer belongs to one level of .ai/architecture.md: 1 Foundation, 2 Services, 3 Domain (Especialización).
LEVEL_OF_LAYER = {1: 1, 2: 1, 3: 2, 4: 2, 5: 2, 6: 3, 7: 3}
LEVEL_LABEL = {1: "FOUNDATION", 2: "SERVICIOS", 3: "ESPECIALIZACIÓN"}
LEVEL = {name: LEVEL_OF_LAYER[layer] for name, layer in LAYER.items()}

# Every arrow drawn between packages. Arrows into Foundation from levels 2 and 3 are collapsed into one.
DRAWN = {
    ("dump", "bulk"), ("doc", "analysis"), ("analysis", "metadata"), ("doc", "metadata"), ("dump", "metadata"),
    ("bulk", "connection"), ("dump", "connection"), ("bulk", "metadata"), ("comparar", "metadata"), ("migrate", "metadata"),
    ("metadata", "results"), ("executors", "query"), ("executors", "results"),
    ("query", "validators"), ("factory", "connection"), ("_drivers", "_core"), ("progress", "_core"),
    ("bulk", "audit"), ("doc", "audit"), ("dump", "audit"), ("migrate", "audit"),
} | {("managers", t) for t in ("connection", "factory", "executors", "metadata", "query", "results")}  # fmt: skip

# Top-level modules deliberately left out of the figure.
# docs_build_plugin: MkDocs plugin (documentation ZIP); not part of the runtime library.
# exceptions: public re-export of _core.exceptions (API 1.0), a facade like __init__.py; nothing in the library imports it.
EXCLUDED = {"docs_build_plugin", "exceptions"}


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
        f"package not placed in any layer (add it to LAYER and draw it): {n}" for n in sorted(names - set(LAYER))
    ]
    problems += [f"package drawn but no longer in src/: {n}" for n in sorted(set(LAYER) - names)]
    measured = {pair: e for pair, e in edges.items() if pair[0] in LAYER and pair[1] in LAYER}
    problems += [f"drawn but not found in the code: {s} -> {t}" for s, t in sorted(DRAWN - set(measured))]
    for s, t in sorted(set(measured) - DRAWN):
        if not (LEVEL[t] == 1 and LEVEL[s] > 1):  # those are the collapsed arrow into Foundation
            problems.append(f"found in the code but not drawn: {s} -> {t}")
    against_layers = sorted(pair for pair in measured if LAYER[pair[0]] <= LAYER[pair[1]])
    if against_layers:
        problems.append(f"imports that do not go to a strictly lower layer (Regla #6): {against_layers}")
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
    bulk_connection_lazy: bool  # the bulk -> connection arrow is drawn dotted only while every such import is lazy
    bulk_connection_where: str  # first bulk -> connection import, "path:line"


def _facts(edges: dict[tuple[str, str], Edge]) -> _Facts:
    to_foundation = {s for (s, t) in edges if s in LEVEL and t in LEVEL and LEVEL[t] == 1 and LEVEL[s] > 1}
    _bc = edges[("bulk", "connection")]
    return _Facts(
        to_foundation=len(to_foundation),
        factory_to_connection=edges[("factory", "connection")].total,
        # Measured, not assumed: since ad4b08e (EngineReadinessAdvisor.report_once) bulk/crud.py imports connection at
        # module level, and the old hard-coded "lazy" lookup made the script fail with KeyError.
        bulk_connection_lazy=_bc.module == 0 and _bc.lazy > 0,
        bulk_connection_where=_bc.first.get("module") or _bc.first.get("lazy") or "?",
    )


NODE_W, NODE_H = 112, 50
COLS = [30, 168, 306, 444, 582, 720, 858]
Y3, Y2A, Y2B, Y1 = 58, 256, 354, 526  # top of the node rows: level 3, level 2 (two rows), level 1
ARIA = (
    "Los tres niveles de util_bbdd y sus capas con los imports reales: cada paquete importa solo de capas inferiores."
)


def _layer_range(level: int) -> str:
    """The layers that make up a level, as the note of its band (for example ``capas 6–7``)."""
    layers = sorted({LAYER[name] for name in LAYER if LEVEL[name] == level})
    return f"capas {layers[0]}–{layers[-1]}"


def _display(name: str) -> str:
    """``name/`` for a package, ``name.py`` for a root module."""
    return f"{name}/" if (SRC / name).is_dir() else f"{name}.py"


def render_layer_table() -> str:
    """Markdown table of the layers, highest first (the order of the figure), for docs/architecture.md."""
    rows = ["| Capa | Nivel | Paquetes |", "|---|---|---|"]
    for layer in sorted(set(LAYER.values()), reverse=True):
        level = LEVEL_OF_LAYER[layer]
        packages = ", ".join(f"`{_display(name)}`" for name in sorted(n for n, lay in LAYER.items() if lay == layer))
        rows.append(f"| {layer} | N{level} · {LEVEL_LABEL[level].capitalize()} | {packages} |")
    return "\n".join(rows) + "\n"


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
    s.parts.append("<defs>" + _marker("arq-h", "arq-head") + _marker("arq-h-warn", "arq-head-warn") + "</defs>")

    # bands
    for cls, y, h in (("3", 12, 126), ("2", 214, 210), ("1", 476, 124)):
        s.parts.append(
            f'<rect class="arq-band arq-band-{cls}" x="8" y="{y}" width="984" height="{h}" rx="10" fill="none" stroke="currentColor" stroke-opacity=".25"/>'
        )
    for level, y in ((3, 36), (2, 238), (1, 500)):
        s.parts.append(
            f'<text class="arq-band-label" x="30" y="{y}" font-size="11" font-weight="600" letter-spacing="1.3" fill="currentColor">NIVEL {level} · {LEVEL_LABEL[level]}</text>'
        )
        s.text(970, y, _layer_range(level), "arq-band-note", "end")

    # edges (before the nodes so the node fill covers any overlap)
    s.edge(f"M{c[1]} 83 H{c[0] + NODE_W}")  # dump -> bulk
    s.edge(f"M{c[3] + NODE_W} 83 H{c[4]}")  # doc -> analysis
    s.edge(f"M86 {Y3 + NODE_H} V{Y2A}", "lazy" if f.bulk_connection_lazy else "")  # bulk -> connection
    s.edge(f"M180 {Y3 + NODE_H} V{Y2A + 6} H{c[0] + NODE_W}")  # dump -> connection (EngineReadinessAdvisor)
    s.edge(f"M736 {Y3 + NODE_H} V214")  # managers -> level 2 band
    s.edge(f"M900 {Y3 + NODE_H} V196 H822 V{Y2A}")  # migrate -> metadata (the other importers share the summary note)
    for d in ("M796 306 L900 354", "M876 306 L812 354", "M940 306 V354"):
        s.edge(d)  # metadata -> results, executors -> {query, results}
    s.edge("M720 379 H694")  # query -> validators
    s.edge("M210 281 H142")  # factory -> connection
    s.edge("M500 424 V476")  # levels 2 and 3 -> Foundation
    s.edge("M190 551 H162")  # _drivers -> _core
    s.edge("M576 526 V512 H96 V526")  # progress -> _core (over the tops of _drivers and core)
    audit_users = sorted(src for src, dst in DRAWN if dst == "audit")
    if audit_users:  # level 3 band -> audit (one arrow, the importers are named in the label)
        s.edge(f"M362 138 V{Y2B}")

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
    s.node(c[2], Y2B, "audit/", "eventos y CSV")
    s.node(c[4], Y2B, "validators/", "params de query")
    s.node(c[5], Y2B, "query/", "registry")
    s.node(c[6], Y2B, "results/", "Row / Rows")
    s.node(30, Y1, "_core/", "excepciones, tipos", 132)
    s.node(190, Y1, "_drivers/", "detecta drivers", 132)
    s.node(350, Y1, "core/", "capacidades", 132)
    s.node(510, Y1, "progress/", "progreso, cancelar", 132)
    s.node(690, Y1, "models.py", "modelos compartidos", 132, " arq-shared")
    s.node(838, Y1, "async_utils.py", "maybe_await", 132, " arq-shared")

    # labels, badges and counters
    s.text(190, 172, f"bulk/: {'import perezoso' if f.bulk_connection_lazy else 'import de módulo'}")
    s.text(190, 188, f.bulk_connection_where)
    s.text(728, 160, "importa connection, factory, executors,", anchor="end")
    s.text(728, 176, "metadata, query y results (6 de 7)", anchor="end")
    s.text(892, 152, "analysis/, bulk/, comparar/,", anchor="end")
    s.text(892, 168, "doc/ y dump/ también", anchor="end")
    s.text(892, 184, "importan de metadata/", anchor="end")
    s.text(176, 275, f"×{f.factory_to_connection}", anchor="middle")
    s.text(512, 447, f"{f.to_foundation} paquetes importan de Foundation")
    s.text(512, 463, "Foundation no importa hacia arriba (0 imports)")
    s.text(690, 516, "módulos raíz compartidos")
    if audit_users:
        names = [f"{name}/" for name in audit_users]
        joined = names[0] if len(names) == 1 else f"{', '.join(names[:-1])} y {names[-1]}"
        s.text(372, 324, joined)
        s.text(372, 340, "importan de audit/" if len(names) > 1 else "importa de audit/")

    # legend
    legend = [(30, "", "arq-h", "import de módulo")]
    if f.bulk_connection_lazy:  # the only arrow that can be drawn dotted
        legend.append((230, "lazy", "arq-h", "import perezoso (dentro de una función)"))
    for x, kind, head, label in legend:
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
  --arq-badge-ink: #fff;
  margin: 1.5em 0;
}
[data-md-color-scheme="slate"] .arq-figure { --arq-amber: #f0a03c; --arq-badge-ink: #101418; }
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
.arq .arq-head { fill: var(--arq-line); }
.arq .arq-head-warn { fill: var(--arq-amber); }
.arq .arq-badge-warn { fill: var(--arq-amber); }
.arq .arq-badge-num { fill: var(--arq-badge-ink); font: 700 11px var(--arq-sans); }
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
    outputs = ((OUT_SVG, render_svg(facts)), (OUT_CSS, CSS_HEAD + CSS_RULES), (OUT_TABLE, render_layer_table()))
    for path, content in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"[gen_arquitectura_capas] wrote {path.relative_to(ROOT).as_posix()}")
    print(f"[gen_arquitectura_capas] measured {n_files} files; {facts.to_foundation} packages import from Foundation.")
    print(
        "[gen_arquitectura_capas] Update the figcaption in docs/architecture.md if the version, date or file count changed."
    )


if __name__ == "__main__":
    main()
