"""Configuracion central de pytest para util_bbdd."""

import importlib.metadata
import logging
import sys
import tomllib

from pathlib import Path

import pytest

from packaging.requirements import Requirement

pytest_plugins = [
    "fixtures.database_fixtures",
    "fixtures.mock_factories",
]

SCOPE_MARKERS = {"unit", "integration", "contract", "e2e"}

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


@pytest.fixture(scope="session", autouse=True)
def setup_logging():
    """Configure basic logging for tests."""
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("test").setLevel(logging.INFO)


def _resolve_scope_marker(node_path: str, marker_names: set[str]) -> str | None:
    """Return the expected scope marker for a collected test item."""
    if "tests/integration/" in node_path:
        return "integration"
    if "tests/contract/" in node_path:
        return "contract"
    if "tests/" in node_path and not marker_names.intersection({"integration", "contract", "e2e"}):
        return "unit"
    return None


def _apply_scope_marker(item: pytest.Item, node_path: str) -> None:
    """Assign a scope marker inferred from the test path when needed."""
    marker_names = {marker.name for marker in item.iter_markers()}
    scope_marker = _resolve_scope_marker(node_path, marker_names)
    if scope_marker and scope_marker not in marker_names:
        item.add_marker(getattr(pytest.mark, scope_marker))


def _validate_scope_marker(item: pytest.Item, node_path: str) -> None:
    """Ensure every collected test has at least one scope marker."""
    final_markers = {marker.name for marker in item.iter_markers()}
    if "tests/" in node_path and not final_markers.intersection(SCOPE_MARKERS):
        raise pytest.UsageError(f"Test sin marker de alcance (unit/integration/contract/e2e): {item.nodeid}")


def pytest_collection_modifyitems(config, items):
    """Assign markers by folder structure to avoid ambiguous classification."""
    for item in items:
        node_path = str(item.fspath).replace("\\", "/")
        _apply_scope_marker(item, node_path)
        _validate_scope_marker(item, node_path)


def _missing_dev_dependencies() -> list[str]:
    """Distribuciones del extra ``dev`` de ``pyproject.toml`` que no están instaladas.

    Config-review 2026-10-02e: sin ``sqlglot`` (extra ``dev``) nueve módulos de tests se saltan enteros al importarse y
    cuentan como un salto cada uno; los recuentos de ``pytest`` (y los errores de mypy) dejaban de ser comparables entre
    entornos sin que nada lo indicara. Se lee el extra del propio ``pyproject.toml`` para no mantener otra lista.
    """
    try:
        with (PROJECT_ROOT / "pyproject.toml").open("rb") as fh:
            dev = tomllib.load(fh)["project"]["optional-dependencies"]["dev"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return []
    missing: list[str] = []
    for spec in dev:
        name = Requirement(spec).name
        try:
            importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            missing.append(name)
    return missing


def pytest_report_header(config: pytest.Config) -> str | None:
    """Cabecera de pytest: aviso si faltan dependencias del extra ``dev``."""
    missing = _missing_dev_dependencies()
    if not missing:
        return None
    return f'AVISO: faltan dependencias del extra dev ({", ".join(missing)}); instala con pip install -e ".[dev]"'


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    """Junto a los recuentos: si faltan dependencias de ``dev``, los recuentos no son los de referencia."""
    missing = _missing_dev_dependencies()
    if missing:
        terminalreporter.write_line(
            f"AVISO: faltan dependencias del extra dev ({', '.join(missing)}): hay módulos de tests que se saltan "
            'enteros y estos recuentos no son comparables con los de referencia. pip install -e ".[dev]"',
            yellow=True,
        )
