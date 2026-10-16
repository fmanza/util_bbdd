"""Test de humo de ``docs/examples/``: los ejemplos que solo usan SQLite se ejecutan sin error.

Los ejemplos se publican por snippet (``--8<--``) y nadie los ejecutaba: un cambio de API que los rompa debe fallar
aquí y no en la documentación publicada. Los que necesitan un servidor (``migrate_*``, ``dump_data_export``, ``bulk_insert_csv``,
``mysql_variables_example``, ``update_auto_increment_example``) quedan fuera.

Cada ejemplo corre en un proceso aparte con ``tmp_path`` como directorio de trabajo: algunos escriben ficheros
(bases SQLite, informes, grafos) en el directorio actual.
"""

from __future__ import annotations

import os
import subprocess
import sys

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.slow, pytest.mark.sqlite]

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "docs" / "examples"

SQLITE_EXAMPLES: tuple[str, ...] = (
    "async_concurrent_queries",
    "benchmark_commit_cadence",
    "database_documentation_generation",
    "diff_reporters",
    "example_connect_introspect",
    "exception_handling",
    "graph_generation",
    "parallel_bulk_insert",
    "query_execution_example",
    "schema_comparison",
    "validators_pattern",
)


@pytest.mark.parametrize("name", SQLITE_EXAMPLES)
def test_sqlite_example_runs(name: str, tmp_path: Path) -> None:
    script = EXAMPLES_DIR / f"{name}.py"
    if not script.exists():
        pytest.skip(f"{script} no está en el árbol")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    assert completed.returncode == 0, f"{name}.py terminó con {completed.returncode}:\n{output[-3000:]}"
    assert "Traceback" not in output, f"{name}.py imprimió una traza:\n{output[-3000:]}"
