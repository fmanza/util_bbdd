"""
Configuración central de pytest para util_bbdd.
Proporciona fixtures, mocks de BD, y marcadores para la suite de tests.
"""

import json
import logging

from typing import Any
from unittest.mock import MagicMock

import pytest

# =====================================================================
# LOGGING Y CONFIGURACIÓN
# =====================================================================


@pytest.fixture(scope="session", autouse=True)
def setup_logging():
    """Configura logging para los tests."""
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("test").setLevel(logging.INFO)


# =====================================================================
# FIXTURES DE MOCKS PARA BASES DE DATOS
# =====================================================================


@pytest.fixture
def mock_mysql_engine():
    """Mock para engine de MySQL/MariaDB."""
    engine = MagicMock()
    engine.dialect.name = "mysql"
    engine.url.drivername = "mysql+pymysql"
    engine.connect.return_value.__enter__ = MagicMock()
    engine.connect.return_value.__exit__ = MagicMock()
    return engine


@pytest.fixture
def mock_engine():
    """Alias para compatibilidad: Mock de SQLAlchemy engine para MySQL"""
    engine = MagicMock()
    engine.dialect.name = "mysql"
    engine.url.drivername = "mysql+pymysql"
    engine.connect.return_value.__enter__ = MagicMock()
    engine.connect.return_value.__exit__ = MagicMock()
    engine.dialect.compile = MagicMock(return_value=MagicMock())
    return engine


@pytest.fixture
def mock_postgresql_engine():
    """Mock para engine de PostgreSQL."""
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    engine.url.drivername = "postgresql+psycopg"
    engine.connect.return_value.__enter__ = MagicMock()
    engine.connect.return_value.__exit__ = MagicMock()
    engine.dialect.compile = MagicMock(return_value=MagicMock())
    return engine


@pytest.fixture
def mock_oracle_engine():
    """Mock para engine de Oracle."""
    engine = MagicMock()
    engine.dialect.name = "oracle"
    engine.url.drivername = "oracle+oracledb"
    engine.connect.return_value.__enter__ = MagicMock()
    engine.connect.return_value.__exit__ = MagicMock()
    engine.dialect.compile = MagicMock(return_value=MagicMock())
    return engine


@pytest.fixture
def mock_sqlite_engine():
    """Mock para engine de SQLite."""
    engine = MagicMock()
    engine.dialect.name = "sqlite"
    engine.url.drivername = "sqlite"
    engine.connect.return_value.__enter__ = MagicMock()
    engine.connect.return_value.__exit__ = MagicMock()
    return engine


@pytest.fixture
def mock_mariadb_engine():
    """Mock para engine de MariaDB."""
    engine = MagicMock()
    engine.dialect.name = "mysql"  # MariaDB usa dialecto mysql
    engine.url.drivername = "mysql+pymysql"
    engine.connect.return_value.__enter__ = MagicMock()
    engine.connect.return_value.__exit__ = MagicMock()
    return engine


@pytest.fixture
def mock_sqlserver_engine():
    """Mock para engine de SQL Server."""
    engine = MagicMock()
    engine.dialect.name = "mssql"
    engine.url.drivername = "mssql+pyodbc"
    engine.connect.return_value.__enter__ = MagicMock()
    engine.connect.return_value.__exit__ = MagicMock()
    return engine


# =====================================================================
# FIXTURES DE CONEXIONES
# =====================================================================


@pytest.fixture
def mock_connection():
    """Mock de conexión genérica a BD."""
    conn = MagicMock()
    conn.execute = MagicMock()
    conn.begin = MagicMock()
    conn.commit = MagicMock()
    conn.rollback = MagicMock()
    conn.close = MagicMock()
    return conn


@pytest.fixture
def mock_cursor():
    """Mock de cursor para ejecutar queries."""
    cursor = MagicMock()
    cursor.execute = MagicMock()
    cursor.fetchone = MagicMock(return_value=None)
    cursor.fetchall = MagicMock(return_value=[])
    cursor.rowcount = 0
    cursor.close = MagicMock()
    return cursor


@pytest.fixture
def mock_session():
    """Mock de sesión SQLAlchemy."""
    session = MagicMock()
    session.query = MagicMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    session.execute = MagicMock()
    return session


# =====================================================================
# FIXTURES DE CONFIGURACIÓN
# =====================================================================


@pytest.fixture
def conn_params_mysql() -> dict[str, Any]:
    """Parámetros de conexión para MySQL."""
    return {
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "password",
        "database": "test_db",
        "charset": "utf8mb4",
    }


@pytest.fixture
def conn_params_postgresql() -> dict[str, Any]:
    """Parámetros de conexión para PostgreSQL."""
    return {
        "host": "localhost",
        "port": 5432,
        "user": "postgres",
        "password": "password",
        "database": "test_db",
    }


@pytest.fixture
def conn_params_oracle() -> dict[str, Any]:
    """Parámetros de conexión para Oracle."""
    return {
        "user": "sys",
        "password": "password",
        "host": "localhost",
        "port": 1521,
        "service_name": "XE",
    }


# =====================================================================
# FIXTURES DE DATOS DE PRUEBA
# =====================================================================


@pytest.fixture
def sample_insert_data():
    """Datos de ejemplo para INSERT."""
    return [
        {"id": 1, "nombre": "Alice", "email": "alice@example.com", "activo": True},
        {"id": 2, "nombre": "Bob", "email": "bob@example.com", "activo": True},
        {"id": 3, "nombre": "Charlie", "email": "charlie@example.com", "activo": False},
    ]


@pytest.fixture
def sample_update_data():
    """Datos de ejemplo para UPDATE."""
    return {
        "where": {"id": 1},
        "set": {"nombre": "Alice Updated", "email": "alice.updated@example.com"},
    }


# =====================================================================
# FIXTURES PARA FILESYSTEM
# =====================================================================


@pytest.fixture
def tmp_audit_file(tmp_path):
    """Archivo CSV temporal para auditoría"""
    audit_file = tmp_path / "audit.csv"
    return str(audit_file)


@pytest.fixture
def temp_sql_file(tmp_path):
    """Crea un archivo SQL temporal para tests."""
    sql_file = tmp_path / "queries.sql"
    sql_file.write_text("""
    SELECT * FROM usuarios WHERE id = :id;
    INSERT INTO usuarios (nombre, email) VALUES (:nombre, :email);
    SELECT COUNT(*) FROM usuarios;
    """)
    return sql_file


@pytest.fixture
def temp_json_queries_file(tmp_path):
    """Crea archivo JSON con queries para tests."""
    queries_file = tmp_path / "queries.json"
    queries_data = {
        "mysql": {
            "obtener_usuario": "SELECT * FROM usuarios WHERE id = %(id)s",
            "listar_usuarios": "SELECT * FROM usuarios",
        },
        "postgresql": {
            "obtener_usuario": "SELECT * FROM usuarios WHERE id = %s",
            "listar_usuarios": "SELECT * FROM usuarios",
        },
    }
    queries_file.write_text(json.dumps(queries_data, indent=2))
    return queries_file


# =====================================================================
# MARKERS PARA CATEGORIZACIÓN DE TESTS
# =====================================================================


def pytest_configure(config):
    """Registra markers personalizados."""
    config.addinivalue_line("markers", "unit: tests de unidad (sin dependencias externas)")
    config.addinivalue_line("markers", "service: tests de servicio (lógica de negocio)")
    config.addinivalue_line("markers", "integration: tests de integración (BD mockeada)")
    config.addinivalue_line("markers", "slow: tests lentos")


def pytest_collection_modifyitems(config, items):
    """Asigna markers automáticos según el nombre del archivo."""
    for item in items:
        # Asignar marker 'unit' por defecto
        if not any(marker.name in ["service", "integration"] for marker in item.iter_markers()):
            item.add_marker(pytest.mark.unit)
