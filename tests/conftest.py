"""Configuracion central de pytest para util_bbdd."""

import logging

import pytest

from fixtures.database_fixtures import (  # noqa: F401
    conn_params_mysql,
    conn_params_oracle,
    conn_params_postgresql,
    sample_insert_data,
    sample_update_data,
    sqlite_db_path,
    sqlite_engine,
    sqlite_engine_with_schema,
    temp_database_types_file,
    temp_json_queries_file,
    temp_queries_file,
    temp_sql_file,
    tmp_audit_file,
)
from fixtures.mock_factories import (  # noqa: F401
    mock_async_connection,
    mock_connection,
    mock_cursor,
    mock_engine,
    mock_mariadb_engine,
    mock_mysql_engine,
    mock_oracle_engine,
    mock_postgresql_engine,
    mock_session,
    mock_sqlite_engine,
    mock_sqlserver_engine,
)


@pytest.fixture(scope="session", autouse=True)
def setup_logging():
    """Configure basic logging for tests."""
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("test").setLevel(logging.INFO)


def pytest_collection_modifyitems(config, items):
    """Assign markers by folder structure to avoid ambiguous classification."""
    scope_markers = {"unit", "integration", "contract", "e2e"}
    for item in items:
        marker_names = {marker.name for marker in item.iter_markers()}
        node_path = str(item.fspath).replace("\\", "/")

        if "tests/integration/" in node_path:
            if "integration" not in marker_names:
                item.add_marker(pytest.mark.integration)
            continue

        if "tests/contract/" in node_path:
            if "contract" not in marker_names:
                item.add_marker(pytest.mark.contract)
            continue

        if "tests/" in node_path and not marker_names.intersection({"integration", "contract", "e2e"}):
            if "unit" not in marker_names:
                item.add_marker(pytest.mark.unit)

        final_markers = {marker.name for marker in item.iter_markers()}
        if "tests/" in node_path and not final_markers.intersection(scope_markers):
            raise pytest.UsageError(
                f"Test sin marker de alcance (unit/integration/contract/e2e): {item.nodeid}"
            )
