"""Guarda automática de la Regla #6: jerarquía de dependencias entre los paquetes de ``src/util_bbdd``.

Regla #6 (``.github/instructions/architecture.instructions.md``):

- Un paquete importa solo de paquetes de capas estrictamente inferiores; los de una misma capa son independientes.
- Cada capa pertenece a un nivel (Foundation, Servicios, Especialización) y no hay ciclos entre paquetes.

La medición y la tabla de capas (``LAYER``, de la que se deriva ``LEVEL``) son las de
``scripts/gen_arquitectura_capas.py``, que también dibuja la figura de ``docs/architecture.md``: las capas se declaran
en un único sitio.

Un import perezoso (dentro de una función) cuenta como dependencia igual que uno de módulo: aplazarlo no rompe el
ciclo. Un import bajo ``TYPE_CHECKING`` no crea ciclo en ejecución, pero tampoco puede ir a una capa igual o superior.
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
    assert spec is not None
    assert spec.loader is not None
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


def _against_layers(pairs: set[tuple[str, str]], layer: dict[str, int]) -> list[tuple[str, str]]:
    """Pares que no van a una capa estrictamente inferior (suben o se quedan en la misma capa)."""
    return sorted(pair for pair in pairs if layer[pair[0]] <= layer[pair[1]])


def _describe(pairs: list[tuple[str, str]], edges: dict[tuple[str, str], Any], layer: dict[str, int]) -> str:
    return "\n".join(f"  {s} (capa {layer[s]}) -> {t} (capa {layer[t]}) en {_where(edges[(s, t)])}" for s, t in pairs)


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


def test_layer_checker_flags_upward_and_same_layer_imports() -> None:
    layer = {"a": 1, "b": 2, "c": 2}
    assert _against_layers({("b", "a")}, layer) == []  # hacia abajo
    assert _against_layers({("a", "b")}, layer) == [("a", "b")]  # hacia arriba
    assert _against_layers({("b", "c")}, layer) == [("b", "c")]  # misma capa


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


def test_imports_only_go_to_lower_layers(script: ModuleType, edges: dict[tuple[str, str], Any]) -> None:
    layer: dict[str, int] = script.LAYER
    placed = {pair for pair in edges if pair[0] in layer and pair[1] in layer}
    against = _against_layers(placed, layer)

    assert not against, (
        "Regla #6: import que no va a una capa estrictamente inferior (los paquetes de una misma capa son "
        "independientes entre sí; cuentan los imports de módulo, los perezosos y los de TYPE_CHECKING):\n"
        + _describe(against, edges, layer)
    )


def test_layer_table_is_consistent(script: ModuleType) -> None:
    layer: dict[str, int] = script.LAYER
    level_of_layer: dict[int, int] = script.LEVEL_OF_LAYER
    used = sorted(set(layer.values()))

    assert used == list(range(1, len(used) + 1)), f"Capas no contiguas: {used}"
    assert set(level_of_layer) == set(used), (
        "Cada capa usada necesita un nivel en LEVEL_OF_LAYER (y no debe sobrar ninguna)"
    )
    levels = [level_of_layer[n] for n in used]
    assert levels == sorted(levels), "Un nivel no puede quedar por debajo de una capa de un nivel inferior"
    assert all(script.LEVEL[name] == level_of_layer[n] for name, n in layer.items()), "LEVEL debe derivarse de LAYER"


def test_every_top_level_package_has_a_layer(script: ModuleType) -> None:
    unplaced = sorted(script.top_level_names() - script.EXCLUDED - set(script.LAYER))
    assert not unplaced, (
        f"Sin capa asignada: {unplaced}. Sin capa, la guarda de imports no los vigila: añádelos a LAYER en "
        "scripts/gen_arquitectura_capas.py y a la tabla de capas de .ai/architecture.md."
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
