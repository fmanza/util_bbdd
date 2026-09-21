"""Guarda automática de la Regla #6: jerarquía de dependencias entre los paquetes de ``src/util_bbdd``.

Regla #6 (``.github/instructions/architecture.instructions.md``):

- Un paquete importa de su mismo nivel o de niveles inferiores; nunca de uno superior.
- Dentro de un nivel, un import solo es válido si va en un único sentido: sin ciclos entre paquetes.

La medición y la tabla de niveles (``LEVEL``) son las de ``scripts/gen_arquitectura_capas.py``, que también dibuja la
figura de ``docs/architecture.md``: los niveles se declaran en un único sitio.

Un import perezoso (dentro de una función) cuenta como dependencia igual que uno de módulo: aplazarlo no rompe el
ciclo. Un import bajo ``TYPE_CHECKING`` no crea ciclo en ejecución, pero tampoco puede subir de nivel.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys

from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "gen_arquitectura_capas.py"

# Imports que suben de nivel bajo ``TYPE_CHECKING`` y se aceptan como deuda (marca 1 de docs/architecture.md).
# Debe coincidir con lo medido: si el import desaparece, hay que quitarlo de aquí.
TYPING_ONLY_UPWARD = {("metadata", "managers")}

# Importa cada paquete como primer import de un intérprete con la raíz ``util_bbdd`` sin inicializar. Se vacía
# ``sys.modules`` de ``util_bbdd`` entre paquetes para que cada uno parta de cero sin pagar un intérprete por paquete.
_ISOLATED_IMPORT_PROBE = """
import importlib, json, sys, types
from pathlib import Path

src, names = Path(sys.argv[1]), json.loads(sys.argv[2])
failures = {}
for name in names:
    for loaded in [m for m in sys.modules if m == "util_bbdd" or m.startswith("util_bbdd.")]:
        del sys.modules[loaded]
    root = types.ModuleType("util_bbdd")
    root.__path__ = [str(src / "util_bbdd")]
    sys.modules["util_bbdd"] = root
    try:
        importlib.import_module(f"util_bbdd.{name}")
    except ImportError as exc:
        missing = getattr(exc, "name", None) or ""
        if missing == "util_bbdd" or missing.startswith("util_bbdd."):
            failures[name] = f"{type(exc).__name__}: {exc}"
        # Un módulo de terceros ausente (dependencia opcional) no es un fallo de imports internos.
    except Exception as exc:
        failures[name] = f"{type(exc).__name__}: {exc}"
print(json.dumps(failures))
"""


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gen_arquitectura_capas", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # los @dataclass del script resuelven sus anotaciones vía sys.modules
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def _cycles(pairs: set[tuple[str, str]]) -> list[list[str]]:
    """Componentes fuertemente conexas de más de un nodo (algoritmo de Tarjan)."""
    graph: dict[str, set[str]] = {}
    for source, target in pairs:
        graph.setdefault(source, set()).add(target)
        graph.setdefault(target, set())

    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    found: list[list[str]] = []

    def visit(node: str) -> None:
        index[node] = low[node] = len(index)
        stack.append(node)
        on_stack.add(node)
        for following in graph[node]:
            if following not in index:
                visit(following)
                low[node] = min(low[node], low[following])
            elif following in on_stack:
                low[node] = min(low[node], index[following])
        if low[node] == index[node]:
            component: list[str] = []
            while True:
                member = stack.pop()
                on_stack.discard(member)
                component.append(member)
                if member == node:
                    break
            if len(component) > 1:
                found.append(sorted(component))

    for node in sorted(graph):
        if node not in index:
            visit(node)
    return sorted(found)


def _where(edge: Any) -> str:
    """Primer import (módulo, si no perezoso, si no de tipado) que originó la arista, como ``ruta:línea``."""
    return edge.first.get("module") or edge.first.get("lazy") or edge.first.get("typing", "?")


@pytest.fixture(scope="module")
def script() -> ModuleType:
    if not SCRIPT.exists():
        pytest.skip("scripts/gen_arquitectura_capas.py no está en el árbol (¿tests ejecutados sin scripts/?)")
    return _load_script()


@pytest.fixture(scope="module")
def edges(script: ModuleType) -> dict[tuple[str, str], Any]:
    measured, _ = script.measure()
    return measured


# ---------------------------------------------------------------------------
# El detector de ciclos: si falla aquí, las guardas de abajo no son de fiar
# ---------------------------------------------------------------------------


def test_cycle_detector_finds_a_two_package_cycle() -> None:
    assert _cycles({("a", "b"), ("b", "a")}) == [["a", "b"]]


def test_cycle_detector_finds_an_indirect_cycle() -> None:
    assert _cycles({("a", "b"), ("b", "c"), ("c", "a"), ("c", "d")}) == [["a", "b", "c"]]


def test_cycle_detector_ignores_acyclic_graphs() -> None:
    assert _cycles({("a", "b"), ("b", "c"), ("a", "c")}) == []


# ---------------------------------------------------------------------------
# Regla #6 sobre el código real
# ---------------------------------------------------------------------------


def test_no_import_cycles_between_packages(edges: dict[tuple[str, str], Any]) -> None:
    runtime = {pair: edge for pair, edge in edges.items() if edge.module or edge.lazy}
    cycles = _cycles(set(runtime))
    detail = "\n".join(
        f"  {' <-> '.join(cycle)}: "
        + ", ".join(f"{s} -> {t} ({_where(runtime[(s, t)])})" for s, t in sorted(runtime) if s in cycle and t in cycle)
        for cycle in cycles
    )
    assert not cycles, (
        "Regla #6: ciclo de imports entre paquetes (los imports perezosos también cuentan). "
        f"Rompe el ciclo quitando el import que va contra la jerarquía:\n{detail}"
    )


def test_no_upward_imports(script: ModuleType, edges: dict[tuple[str, str], Any]) -> None:
    level: dict[str, int] = script.LEVEL
    upward = {
        pair: edge
        for pair, edge in edges.items()
        if pair[0] in level and pair[1] in level and level[pair[0]] < level[pair[1]]
    }

    at_runtime = sorted(pair for pair, edge in upward.items() if edge.module or edge.lazy)
    assert not at_runtime, "Regla #6: import que sube de nivel:\n" + "\n".join(
        f"  {s} (N{level[s]}) -> {t} (N{level[t]}) en {_where(upward[(s, t)])}" for s, t in at_runtime
    )

    typing_only = {pair for pair in upward if pair not in at_runtime}
    new = sorted(typing_only - TYPING_ONLY_UPWARD)
    assert not new, "Regla #6: import ascendente nuevo bajo TYPE_CHECKING:\n" + "\n".join(
        f"  {s} (N{level[s]}) -> {t} (N{level[t]}) en {_where(upward[(s, t)])}" for s, t in new
    )
    stale = sorted(TYPING_ONLY_UPWARD - typing_only)
    assert not stale, (
        f"La excepción {stale} ya no existe: quítala de TYPING_ONLY_UPWARD y retira su marca en "
        "docs/architecture.md y scripts/gen_arquitectura_capas.py."
    )


def test_every_top_level_package_has_a_level(script: ModuleType) -> None:
    unplaced = sorted(script.top_level_names() - script.EXCLUDED - set(script.LEVEL))
    assert not unplaced, (
        f"Sin nivel asignado: {unplaced}. Sin nivel, la guarda de imports ascendentes no los vigila: añádelos a "
        "LEVEL en scripts/gen_arquitectura_capas.py y a las listas de niveles de .ai/architecture.md y "
        ".github/instructions/architecture.instructions.md."
    )


@pytest.mark.slow
def test_each_package_imports_cleanly_as_the_first_import(script: ModuleType) -> None:
    """Un ciclo latente solo se manifiesta con cierto orden de imports; aquí cada paquete va primero."""
    names = sorted(script.top_level_names() - script.EXCLUDED)
    result = subprocess.run(
        [sys.executable, "-c", _ISOLATED_IMPORT_PROBE, str(PROJECT_ROOT / "src"), json.dumps(names)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, f"El intérprete de prueba falló:\n{result.stderr[-2000:]}"
    failures: dict[str, str] = json.loads(result.stdout.strip().splitlines()[-1])
    assert not failures, (
        "Paquetes que no se importan como primer import (import circular o dependiente del orden):\n"
        + ("\n".join(f"  util_bbdd.{name}: {error}" for name, error in sorted(failures.items())))
    )
