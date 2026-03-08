"""
Fixtures para tests E2E/Integración con bases de datos REALES (sin mocks).
Proporciona engines, conexiones y datos para tests de crud, validación y flujos completos.
"""

import gc
import json
import os
import tempfile
import time

from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import StaticPool

from util_bbdd import AsyncDatabaseManager

# =====================================================================
# CONSTANTES
# =====================================================================

SQL_QUERIES_JSON = {
    "sqlite": {
        "obtener_tablas": "SELECT name FROM sqlite_master WHERE type='table'",
        "columnas_tabla": "PRAGMA table_info({tabla})",
        "get_all_users": "SELECT * FROM users",
        "get_user_by_id": "SELECT * FROM users WHERE id = :user_id",
        "insert_user": "INSERT INTO users (nombre, email, edad) VALUES (:nombre, :email, :edad)",
        "update_user": "UPDATE users SET email = :email, edad = :edad WHERE id = :user_id",
        "delete_user": "DELETE FROM users WHERE id = :user_id",
        "get_user_count": "SELECT COUNT(*) as total FROM users",
    },
    "postgresql": {
        "obtener_tablas": "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public'",
        "columnas_tabla": "SELECT * FROM information_schema.columns WHERE table_name = :{tabla}",
        "get_all_users": "SELECT * FROM users",
        "get_user_by_id": "SELECT * FROM users WHERE id = :user_id",
        "insert_user": "INSERT INTO users (nombre, email, edad) VALUES (:nombre, :email, :edad)",
        "update_user": "UPDATE users SET email = :email, edad = :edad WHERE id = :user_id",
        "delete_user": "DELETE FROM users WHERE id = :user_id",
        "get_user_count": "SELECT COUNT(*) as total FROM users",
    },
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    edad INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    total DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

SEED_DATA = [
    (
        "INSERT INTO users (nombre, email, edad) VALUES (:nombre, :email, :edad)",
        [
            {"nombre": "Alice Johnson", "email": "alice@example.com", "edad": 30},
            {"nombre": "Bob Smith", "email": "bob@example.com", "edad": 25},
            {"nombre": "Charlie Brown", "email": "charlie@example.com", "edad": 35},
        ],
    ),
    (
        "INSERT INTO orders (user_id, total) VALUES (:user_id, :total)",
        [
            {"user_id": 1, "total": 100.50},
            {"user_id": 1, "total": 250.75},
            {"user_id": 2, "total": 50.00},
        ],
    ),
]


# =====================================================================
# FIXTURES: SQLite (LOCAL, SIN SERVIDOR)
# =====================================================================


@pytest.fixture(scope="function")
def sqlite_db_path() -> Generator[str, None, None]:
    """Proporciona una BD SQLite temporal para cada test."""

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_e2e.db")
        yield db_path

        # Cleanup mejorado: Dar tiempo para que se liberen conexiones
        gc.collect()  # Forzar garbage collection
        time.sleep(0.1)  # Pequeña pausa para liberar handles


@pytest.fixture(scope="function")
def sqlite_engine(sqlite_db_path: str) -> Generator[Engine, None, None]:
    """Engine SQLite REAL sin mocks ni pooling."""
    engine = create_engine(
        f"sqlite:///{sqlite_db_path}", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    yield engine

    # Cleanup mejorado: Cerrar todas las conexiones y pool
    try:
        # Desconectar todas las conexiones activas
        engine.dispose()

        # Forzar garbage collection para liberar handles del SO
        import gc

        gc.collect()
    except Exception:
        pass  # Ignorar errores en cleanup


@pytest.fixture(scope="function")
def sqlite_engine_with_schema(sqlite_engine: Engine) -> Generator[Engine, None, None]:
    """Engine SQLite populate con schema y datos de prueba."""
    # Crear tablas
    with sqlite_engine.connect() as conn:
        for statement in SCHEMA_SQL.split(";"):
            if statement.strip():
                conn.execute(text(statement))
        conn.commit()

        # Seed data
        for query, params_list in SEED_DATA:
            for params in params_list:
                conn.execute(text(query), params)
        conn.commit()

    yield sqlite_engine

    # Cleanup mejorado: Cerrar todas las conexiones
    try:
        # Cerrar el pool explícitamente
        sqlite_engine.dispose()

        # Libertar la conexión de la instancia si existe
        if hasattr(sqlite_engine, "raw_connection"):
            try:
                sqlite_engine.raw_connection.close()
            except Exception:
                pass

        import gc

        gc.collect()
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture(scope="function")
def sql_queries_json_path(sqlite_db_path: str) -> Generator[str, None, None]:
    """Proporciona la ruta a sql_queries.json temporal."""
    json_dir = os.path.dirname(sqlite_db_path)
    json_path = os.path.join(json_dir, "sql_queries.json")

    with open(json_path, "w") as f:
        json.dump(SQL_QUERIES_JSON, f)

    yield json_path


@pytest.fixture(scope="function")
def sqlite_connection_config(sqlite_db_path: str, sql_queries_json_path: str) -> dict[str, Any]:
    """Configuración para DatabaseManager con SQLite real."""
    return {
        "db_type": "sqlite",
        "conn_params": {"database": sqlite_db_path},
        "queries_file": Path(sql_queries_json_path),
        "use_pool": False,  # Simplificar para tests E2E
    }


# =====================================================================
# FIXTURES: AsyncDatabaseManager (ASYNC E2E TESTS)
# =====================================================================


@pytest_asyncio.fixture
async def async_manager_with_schema(
    sqlite_engine_with_schema: Engine, sqlite_db_path: str, sql_queries_json_path: str
) -> AsyncDatabaseManager:
    """Proporciona un AsyncDatabaseManager configurado con schema."""
    from util_bbdd.query_registry import QueryRegistry
    from util_bbdd.query_resolver import QueryResolver

    manager = AsyncDatabaseManager(
        db_type="sqlite",
        conn_params={"database": sqlite_db_path},
        use_pool=False,
    )

    # Inicializar el manager (se crea query_executor vacío)
    await manager.ainit()

    # Registrar queries manualmente en el executor
    registry = QueryRegistry(Path(sql_queries_json_path))
    resolver = QueryResolver(registry)

    manager.query_executor.registry = registry
    manager.query_executor.resolver = resolver

    yield manager

    # Cleanup
    try:
        await manager.aclose()
    except Exception:
        pass
    finally:
        gc.collect()
        time.sleep(0.1)


# =====================================================================
# FIXTURES: PostgreSQL (OPCIONAL, SI DISPONIBLE)
# =====================================================================


@pytest.fixture(scope="session")
def postgresql_available() -> bool:
    """Detecta si PostgreSQL está disponible para tests."""
    try:
        from sqlalchemy import create_engine

        engine = create_engine(
            "postgresql+psycopg://postgres:postgres@localhost:5432/util_bbdd_test", connect_args={"timeout": 1}
        )
        with engine.connect():
            pass
        engine.dispose()
        return True
    except Exception:
        return False


@pytest.fixture(scope="function")
def postgresql_engine(postgresql_available: bool) -> Generator[Engine, None, None]:
    """Engine PostgreSQL REAL si disponible, skip si no."""
    if not postgresql_available:
        pytest.skip("PostgreSQL no disponible")

    engine = create_engine("postgresql+psycopg://postgres:postgres@localhost:5432/util_bbdd_test", echo=False)

    # Limpiar BD anterior
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()

    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def postgresql_engine_with_schema(postgresql_engine: Engine) -> Generator[Engine, None, None]:
    """Engine PostgreSQL con schema y datos."""
    schema_sql_pg = SCHEMA_SQL.replace("AUTOINCREMENT", "")

    with postgresql_engine.connect() as conn:
        for statement in schema_sql_pg.split(";"):
            if statement.strip():
                conn.execute(text(statement))
        conn.commit()

        for query, params_list in SEED_DATA:
            for params in params_list:
                conn.execute(text(query), params)
        conn.commit()

    yield postgresql_engine


@pytest.fixture(scope="function")
def postgresql_connection_config(sql_queries_json_path: str) -> dict[str, Any]:
    """Configuración para DatabaseManager con PostgreSQL real."""
    return {
        "db_type": "postgresql",
        "conn_params": {
            "host": "localhost",
            "user": "postgres",
            "password": "postgres",
            "database": "util_bbdd_test",
            "port": 5432,
        },
        "queries_file": Path(sql_queries_json_path),
        "use_pool": False,
    }


# =====================================================================
# MARCADORES PYTEST
# =====================================================================


def pytest_configure(config):
    """Registra marcadores personalizados."""
    config.addinivalue_line("markers", "e2e: Tests E2E/Integración con bases de datos reales (sin mocks)")
    config.addinivalue_line("markers", "sqlite: Tests específicos de SQLite")
    config.addinivalue_line("markers", "postgresql: Tests específicos de PostgreSQL (requiere servidor)")
