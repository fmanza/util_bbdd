"""Tests de regresión para SQLAlchemyEngineFactory (sync) [SVC-03].

AUDIT_CODE 2026-09-22: asimetrías sync/async — el factory async ya validaba
database/user vacíos y normalizaba rutas SQLite con separadores Windows; el
factory sync no. `SyncDatabaseManager.get_sqlalchemy_engine()` puede llamar a
`create_engine(..., database="")` de verdad (`self.database` por defecto es
`conn_params.get("database", "")`), por lo que este no es un caso teórico.
"""

from __future__ import annotations

import pytest

from util_bbdd import ValidationError
from util_bbdd.factory.sqlalchemy_engine_factory import SQLAlchemyEngineFactory


class TestMariaDBBuilderValidation:
    def test_requires_database(self) -> None:
        with pytest.raises(ValidationError, match="database"):
            SQLAlchemyEngineFactory._build_mariadb_connection_string(
                {"host": "localhost", "user": "root", "password": "pw"},
                database="",
            )

    def test_succeeds_with_database(self) -> None:
        conn_str = SQLAlchemyEngineFactory._build_mariadb_connection_string(
            {"host": "localhost", "user": "root", "password": "pw"},
            database="mydb",
        )
        assert conn_str == "mariadb+mariadbconnector://root:pw@localhost:3306/mydb"


class TestOracleBuilderValidation:
    def test_requires_user(self) -> None:
        with pytest.raises(ValidationError, match="usuario"):
            SQLAlchemyEngineFactory._build_oracle_connection_string(
                {"password": "pw", "service_name": "ORCL"},
                database="",
            )

    def test_requires_password(self) -> None:
        with pytest.raises(ValidationError, match="contraseña"):
            SQLAlchemyEngineFactory._build_oracle_connection_string(
                {"user": "hr", "service_name": "ORCL"},
                database="",
            )

    def test_requires_service_name_or_database(self) -> None:
        with pytest.raises(ValidationError, match="service_name"):
            SQLAlchemyEngineFactory._build_oracle_connection_string(
                {"user": "hr", "password": "pw"},
                database="",
            )

    def test_uses_database_as_service_name_fallback(self) -> None:
        conn_str = SQLAlchemyEngineFactory._build_oracle_connection_string(
            {"user": "hr", "password": "pw"},
            database="ORCL",
        )
        assert "service_name=ORCL" in conn_str


class TestPostgreSQLBuilderValidation:
    def test_requires_database(self) -> None:
        with pytest.raises(ValidationError, match="database"):
            SQLAlchemyEngineFactory._build_postgresql_connection_string(
                {"host": "localhost", "user": "postgres", "password": "pw"},
                database="",
            )

    def test_succeeds_with_database(self) -> None:
        conn_str = SQLAlchemyEngineFactory._build_postgresql_connection_string(
            {"host": "localhost", "user": "postgres", "password": "pw"},
            database="mydb",
        )
        assert conn_str == "postgresql+psycopg://postgres:pw@localhost:5432/mydb"


class TestSQLiteBuilderWindowsPathNormalization:
    def test_windows_absolute_path_backslashes_normalized(self) -> None:
        conn_str = SQLAlchemyEngineFactory._build_sqlite_connection_string({"database": r"C:\Users\test\app.db"})
        assert conn_str == "sqlite:///C:/Users/test/app.db"
        assert "\\" not in conn_str

    def test_windows_relative_path_backslashes_normalized(self) -> None:
        conn_str = SQLAlchemyEngineFactory._build_sqlite_connection_string({"database": r"data\app.db"})
        assert conn_str == "sqlite:///data/app.db"

    def test_memory_unaffected(self) -> None:
        conn_str = SQLAlchemyEngineFactory._build_sqlite_connection_string({"database": ":memory:"})
        assert conn_str == "sqlite:///:memory:"

    def test_unix_absolute_path_unaffected(self) -> None:
        conn_str = SQLAlchemyEngineFactory._build_sqlite_connection_string({"database": "/var/data/app.db"})
        assert conn_str == "sqlite:////var/data/app.db"

    def test_requires_database(self) -> None:
        with pytest.raises(ValidationError):
            SQLAlchemyEngineFactory._build_sqlite_connection_string({"database": ""})
