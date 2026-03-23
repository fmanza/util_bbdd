"""Configuracion central de pytest para util_bbdd."""

import logging
import sys

from pathlib import Path

import pytest

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
