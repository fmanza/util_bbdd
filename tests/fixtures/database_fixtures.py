"""Database and data fixtures shared across tests."""

import gc
import json

from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import StaticPool


SQLITE_SCHEMA_SQL = """
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

SQLITE_SEED_DATA = [
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


@pytest.fixture
def conn_params_mysql() -> dict[str, Any]:
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
    return {
        "host": "localhost",
        "port": 5432,
        "user": "postgres",
        "password": "password",
        "database": "test_db",
    }


@pytest.fixture
def conn_params_oracle() -> dict[str, Any]:
    return {
        "user": "sys",
        "password": "password",
        "host": "localhost",
        "port": 1521,
        "service_name": "XE",
    }


@pytest.fixture
def sample_insert_data() -> list[dict[str, Any]]:
    return [
        {"id": 1, "nombre": "Alice", "email": "alice@example.com", "activo": True},
        {"id": 2, "nombre": "Bob", "email": "bob@example.com", "activo": True},
        {"id": 3, "nombre": "Charlie", "email": "charlie@example.com", "activo": False},
    ]


@pytest.fixture
def sample_update_data() -> dict[str, dict[str, Any]]:
    return {
        "where": {"id": 1},
        "set": {"nombre": "Alice Updated", "email": "alice.updated@example.com"},
    }


@pytest.fixture
def tmp_audit_file(tmp_path):
    audit_file = tmp_path / "audit.csv"
    return str(audit_file)


@pytest.fixture
def temp_sql_file(tmp_path):
    sql_file = tmp_path / "queries.sql"
    sql_file.write_text(
        """
    SELECT * FROM usuarios WHERE id = :id;
    INSERT INTO usuarios (nombre, email) VALUES (:nombre, :email);
    SELECT COUNT(*) FROM usuarios;
    """
    )
    return sql_file


@pytest.fixture
def temp_json_queries_file(tmp_path):
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


@pytest.fixture
def temp_queries_file(tmp_path):
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


@pytest.fixture(scope="function")
def sqlite_db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test_e2e.db")


@pytest.fixture(scope="function")
def sqlite_engine(sqlite_db_path: str) -> Generator[Engine, None, None]:
    engine = create_engine(
        f"sqlite:///{sqlite_db_path}",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    yield engine
    try:
        engine.dispose()
    finally:
        gc.collect()


@pytest.fixture(scope="function")
def sqlite_engine_with_schema(sqlite_engine: Engine) -> Generator[Engine, None, None]:
    with sqlite_engine.connect() as conn:
        for statement in SQLITE_SCHEMA_SQL.split(";"):
            if statement.strip():
                conn.execute(text(statement))
        conn.commit()

        for query, params_list in SQLITE_SEED_DATA:
            for params in params_list:
                conn.execute(text(query), params)
        conn.commit()

    yield sqlite_engine
    try:
        sqlite_engine.dispose()
    finally:
        gc.collect()
