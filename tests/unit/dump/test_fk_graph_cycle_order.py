"""Ciclos de FK en orden estable entre procesos (G47 de util_bbdd_web, U-10.2, 5.2.0).

``bfs_component`` recorría los vecinos desde un ``set``: el orden de las tablas de un ciclo de 3+ tablas dependía de
``PYTHONHASHSEED``, así que ``plan().cycles`` cambiaba entre la vista previa y el volcado (subprocesos distintos).
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

from util_bbdd.dump._fk_graph import bfs_component, find_cycle_components

pytestmark = pytest.mark.unit

# Estrella de 4 tablas en ciclo: el centro con FK a tres hojas que a su vez lo referencian.
TABLES = ["centro", "hoja_c", "hoja_a", "hoja_b"]
DEPENDENTS: dict[str, set[str]] = {
    "centro": {"hoja_c", "hoja_a", "hoja_b"},
    "hoja_a": {"centro"},
    "hoja_b": {"centro"},
    "hoja_c": {"centro"},
}

_SCRIPT = f"""
from util_bbdd.dump._fk_graph import find_cycle_components
print(find_cycle_components({TABLES!r}, {DEPENDENTS!r}))
"""


def test_neighbours_are_visited_in_sorted_order() -> None:
    adj = {"centro": {"hoja_c", "hoja_a", "hoja_b"}, "hoja_a": {"centro"}, "hoja_b": {"centro"}, "hoja_c": {"centro"}}

    assert bfs_component("centro", adj, set()) == ["centro", "hoja_a", "hoja_b", "hoja_c"]


def test_star_cycle_in_this_process() -> None:
    assert find_cycle_components(TABLES, DEPENDENTS) == [["centro", "hoja_a", "hoja_b", "hoja_c"]]


def test_star_cycle_is_the_same_with_any_hash_seed() -> None:
    outputs = set()
    for seed in ("1", "2", "3", "4", "5", "6"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        result = subprocess.run(
            [sys.executable, "-c", _SCRIPT], env=env, capture_output=True, text=True, check=True, timeout=60
        )
        outputs.add(result.stdout.strip())

    assert outputs == {"[['centro', 'hoja_a', 'hoja_b', 'hoja_c']]"}
