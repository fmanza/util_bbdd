"""Mock fixture factories shared across unit tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest


def _build_engine_mock(dialect_name: str, driver_name: str, with_compile: bool = False) -> MagicMock:
    engine = MagicMock()
    engine.dialect.name = dialect_name
    engine.url.drivername = driver_name
    engine.connect.return_value.__enter__ = MagicMock()
    engine.connect.return_value.__exit__ = MagicMock()
    if with_compile:
        engine.dialect.compile = MagicMock(return_value=MagicMock())
    return engine


@pytest.fixture
def mock_mysql_engine() -> MagicMock:
    return _build_engine_mock("mysql", "mysql+pymysql")


@pytest.fixture
def mock_engine() -> MagicMock:
    # Compatibility alias used by legacy tests.
    return _build_engine_mock("mysql", "mysql+pymysql", with_compile=True)


@pytest.fixture
def mock_postgresql_engine() -> MagicMock:
    return _build_engine_mock("postgresql", "postgresql+psycopg", with_compile=True)


@pytest.fixture
def mock_oracle_engine() -> MagicMock:
    return _build_engine_mock("oracle", "oracle+oracledb", with_compile=True)


@pytest.fixture
def mock_sqlite_engine() -> MagicMock:
    return _build_engine_mock("sqlite", "sqlite")


@pytest.fixture
def mock_mariadb_engine() -> MagicMock:
    return _build_engine_mock("mysql", "mysql+pymysql")


@pytest.fixture
def mock_sqlserver_engine() -> MagicMock:
    return _build_engine_mock("mssql", "mssql+pyodbc")


@pytest.fixture
def mock_connection() -> MagicMock:
    conn = MagicMock()
    conn.execute = MagicMock()
    conn.begin = MagicMock()
    conn.commit = MagicMock()
    conn.rollback = MagicMock()
    conn.close = MagicMock()
    return conn


@pytest.fixture
def mock_cursor() -> MagicMock:
    cursor = MagicMock()
    cursor.execute = MagicMock()
    cursor.fetchone = MagicMock(return_value=None)
    cursor.fetchall = MagicMock(return_value=[])
    cursor.rowcount = 0
    cursor.close = MagicMock()
    return cursor


@pytest.fixture
def mock_session() -> MagicMock:
    session = MagicMock()
    session.query = MagicMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    session.execute = MagicMock()
    return session


@pytest.fixture
def mock_async_connection() -> AsyncMock:
    conn = AsyncMock()
    cursor = AsyncMock()
    cursor.fetchall = AsyncMock(return_value=[])
    cursor.fetchone = AsyncMock(return_value=None)
    cursor.execute = AsyncMock()
    conn.cursor = AsyncMock(return_value=cursor)
    conn.close = AsyncMock()
    return conn
