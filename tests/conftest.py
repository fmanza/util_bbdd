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


# =====================================================================
# FIXTURES PARA QUERY REGISTRY Y RESOLVER (PR 0+)
# =====================================================================


@pytest.fixture
def temp_queries_file(tmp_path):
    """Crea un archivo temporal de queries para testing (PR 0+).

    Proporciona queries normalizadas para múltiples motores para tests
    de QueryRegistry, QueryResolver y Executores.

    Returns:
        Path al archivo JSON temporal con estructura de queries

    Ejemplo:
        def test_registry(temp_queries_file):
            registry = QueryRegistry(temp_queries_file)
            assert "mariadb" in registry.get_all_db_types()
    """

    queries = {
        "mariadb": {
            "obtener_tablas": (
                "SELECT table_name, table_comment "
                "FROM information_schema.tables "
                "WHERE table_schema = '{database}' "
                "ORDER BY table_name"
            ),
            "columnas_tabla": (
                "SELECT column_name, column_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_schema = '{database}' AND table_name = '{tabla}' "
                "ORDER BY ordinal_position"
            ),
            "indices": (
                "SELECT INDEX_NAME, COLUMN_NAME, NON_UNIQUE "
                "FROM INFORMATION_SCHEMA.STATISTICS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '{tabla}'"
            ),
            "obtener_vistas": (
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = '{database}' AND table_type = 'VIEW'"
            ),
        },
        "oracle": {
            "obtener_tablas": (
                "SELECT t.table_name, c.comments AS table_comment "
                "FROM all_tables t LEFT JOIN all_tab_comments c "
                "ON t.owner = c.owner AND t.table_name = c.table_name "
                "WHERE t.owner = '{esquema}' "
                "ORDER BY t.table_name"
            ),
            "columnas_tabla": (
                "SELECT c.column_name, c.data_type, c.nullable "
                "FROM all_tab_columns c "
                "WHERE c.owner = '{esquema}' AND c.table_name = '{tabla}' "
                "ORDER BY c.column_id"
            ),
        },
        "postgresql": {
            "obtener_tablas": (
                "SELECT c.relname AS table_name, obj_description(c.oid) AS table_comment "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = '{database}' AND c.relkind = 'r' "
                "ORDER BY c.relname"
            ),
        },
    }

    file_path = tmp_path / "test_queries.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(queries, f)

    return file_path


@pytest.fixture
def temp_database_types_file(tmp_path):
    """Crea un archivo temporal de tipos de BD para testing (PR 0+).

    Proporciona definiciones de tipos de bases de datos para tests
    de validadores y DatabaseTypeValidator.

    Returns:
        Path al archivo JSON temporal con database_types

    Ejemplo:
        def test_validators(temp_database_types_file):
            validator = DatabaseTypeValidator(temp_database_types_file)
            info = validator.get_db_type_info("mariadb")
    """

    db_types = {
        "database_types": {
            "mariadb": {
                "name": "MariaDB",
                "description": "MariaDB database system",
                "version_range": "5.5.0+",
                "default_port": 3306,
                "drivers": ["mariadb", "mysql"],
                "supported_features": ["Transacciones ACID", "Triggers", "Procedimientos"],
                "connection_params": {
                    "required": ["host", "user", "password", "database"],
                    "optional": ["port", "charset"],
                },
            },
            "oracle": {
                "name": "Oracle Database",
                "description": "Oracle database system",
                "version_range": "11g R2+",
                "default_port": 1521,
                "drivers": ["cx_Oracle", "oracledb"],
                "supported_features": ["PL/SQL", "Transacciones ACID"],
                "connection_params": {
                    "required": ["host", "user", "password", "service_name"],
                    "optional": ["port", "schema"],
                },
            },
            "postgresql": {
                "name": "PostgreSQL",
                "description": "PostgreSQL database system",
                "version_range": "10.0+",
                "default_port": 5432,
                "drivers": ["psycopg2", "psycopg"],
                "supported_features": ["Transacciones ACID", "JSON support"],
                "connection_params": {
                    "required": ["host", "user", "password", "database"],
                    "optional": ["port"],
                },
            },
        }
    }

    file_path = tmp_path / "test_database_types.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(db_types, f)

    return file_path


@pytest.fixture
def mock_async_connection():
    """Mock de una conexión async a base de datos (PR 0+).

    Returns:
        AsyncMock configurado como una conexión BD async

    Ejemplo:
        async def test_async_executor(mock_async_connection):
            executor = AsyncQueryExecutor(async_provider, ...)
            # usar mock_async_connection
    """
    from unittest.mock import AsyncMock

    conn = AsyncMock()
    cursor = AsyncMock()
    cursor.fetchall = AsyncMock(return_value=[])
    cursor.fetchone = AsyncMock(return_value=None)
    cursor.execute = AsyncMock()
    conn.cursor = AsyncMock(return_value=cursor)
    conn.close = AsyncMock()
    return conn
