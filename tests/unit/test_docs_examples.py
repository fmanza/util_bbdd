"""Test de humo de ``docs/examples/``: los ejemplos se ejecutan sin error.

Los ejemplos se publican por snippet (``--8<--``) y nadie los ejecutaba: un cambio de API que los rompa debe fallar
aquí y no en la documentación publicada.

- Los que solo usan SQLite se ejecutan completos.
- Los que necesitan un servidor leen la conexión de ``UTIL_BBDD_EXAMPLE_*``: aquí se ejecutan sin ella (cargan sus
  imports y explican cómo configurarla). Contra servidores reales los ejecuta
  ``tests/integration/test_docs_examples_engines.py``.

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

SERVER_EXAMPLES: tuple[str, ...] = (
    "bulk_insert_csv",
    "dump_data_export",
    "migrate_mariadb_source",
    "migrate_oracle_mariadb",
    "migrate_postgresql_source",
    "migrate_sqlserver_source",
    "mysql_variables_example",
    "update_auto_increment_example",
)


def _run(name: str, cwd: Path, env: dict[str, str]) -> str:
    script = EXAMPLES_DIR / f"{name}.py"
    if not script.exists():
        pytest.skip(f"{script} no está en el árbol")
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        env={**env, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    assert completed.returncode == 0, f"{name}.py terminó con {completed.returncode}:\n{output[-3000:]}"
    assert "Traceback" not in output, f"{name}.py imprimió una traza:\n{output[-3000:]}"
    return output


@pytest.mark.parametrize("name", SQLITE_EXAMPLES)
def test_sqlite_example_runs(name: str, tmp_path: Path) -> None:
    _run(name, tmp_path, dict(os.environ))


@pytest.mark.parametrize("name", SERVER_EXAMPLES)
def test_server_example_without_connection_explains_how_to_configure_it(name: str, tmp_path: Path) -> None:
    env = {key: value for key, value in os.environ.items() if not key.startswith("UTIL_BBDD_EXAMPLE_")}
    output = _run(name, tmp_path, env)
    assert "Define UTIL_BBDD_EXAMPLE_" in output
