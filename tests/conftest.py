"""
Configuración global y fixtures para tests de util_bbdd.
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_engine():
    """Mock de SQLAlchemy engine para MySQL"""
    engine = MagicMock()
    engine.dialect.name = "mysql"
    engine.connect.return_value.__enter__ = MagicMock()
    engine.connect.return_value.__exit__ = MagicMock()
    engine.dialect.compile = MagicMock(return_value=MagicMock())
    return engine


@pytest.fixture
def mock_oracle_engine():
    """Mock de SQLAlchemy engine para Oracle"""
    engine = MagicMock()
    engine.dialect.name = "oracle"
    engine.connect.return_value.__enter__ = MagicMock()
    engine.connect.return_value.__exit__ = MagicMock()
    engine.dialect.compile = MagicMock(return_value=MagicMock())
    return engine


@pytest.fixture
def mock_postgresql_engine():
    """Mock de SQLAlchemy engine para PostgreSQL"""
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    engine.connect.return_value.__enter__ = MagicMock()
    engine.connect.return_value.__exit__ = MagicMock()
    engine.dialect.compile = MagicMock(return_value=MagicMock())
    return engine


@pytest.fixture
def tmp_audit_file(tmp_path):
    """Archivo CSV temporal para auditoría"""
    audit_file = tmp_path / "audit.csv"
    return str(audit_file)
