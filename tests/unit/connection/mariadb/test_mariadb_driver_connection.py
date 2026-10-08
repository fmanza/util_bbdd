"""Motor ``mariadb`` (mariadb.Connection/ConnectionPool): configuración y validación.

Tests unitarios para MariaDBConnectionConfig y MariaDBPoolConfig sin servidor real.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from util_bbdd.connection.config import MariaDBConnectionConfig, MariaDBPoolConfig
from util_bbdd.connection.mariadb import pool_connection_mariadb

BASE: dict[str, Any] = {"host": "db", "user": "app", "password": "pw", "database": "sales"}


class TestMariaDBConnectionConfig:
    """Validar que MariaDBConnectionConfig incluye charset e init_command por defecto."""

    def test_defaults_include_charset_utf8mb4(self) -> None:
        """Charset debe ser utf8mb4 por defecto para evitar UnicodeDecodeError (H-32 hotfix)."""
        kwargs = MariaDBConnectionConfig.from_params(BASE).to_driver_kwargs()
        assert kwargs["charset"] == "utf8mb4"

    def test_explicit_charset_is_preserved(self) -> None:
        """Si el usuario especifica charset, debe respetarse."""
        params = {**BASE, "charset": "latin1"}
        kwargs = MariaDBConnectionConfig.from_params(params).to_driver_kwargs()
        assert kwargs["charset"] == "latin1"

    def test_defaults_include_init_command(self) -> None:
        """init_command debe incluir SET NAMES por defecto (equivale al comportamiento de PyMySQL)."""
        kwargs = MariaDBConnectionConfig.from_params(BASE).to_driver_kwargs()
        assert kwargs["init_command"] == "SET NAMES utf8mb4"

    def test_explicit_init_command_is_preserved(self) -> None:
        """Si el usuario especifica init_command, debe respetarse."""
        params = {**BASE, "init_command": "SET NAMES latin1"}
        kwargs = MariaDBConnectionConfig.from_params(params).to_driver_kwargs()
        assert kwargs["init_command"] == "SET NAMES latin1"

    def test_defaults_do_not_send_encoding_errors(self) -> None:
        """Ningún driver de MariaDB admite encoding_errors (Connector/Python 1.1.14 lo rechaza): no se envía."""
        kwargs = MariaDBConnectionConfig.from_params(BASE).to_driver_kwargs()
        assert "encoding_errors" not in kwargs

    def test_to_driver_kwargs_includes_connection_params(self) -> None:
        """to_driver_kwargs() debe incluir todos los parámetros de conexión."""
        kwargs = MariaDBConnectionConfig.from_params(BASE).to_driver_kwargs()
        assert kwargs["host"] == "db"
        assert kwargs["user"] == "app"
        assert kwargs["password"] == "pw"
        assert kwargs["database"] == "sales"
        assert kwargs["port"] == 3306
        assert kwargs["autocommit"] is False
        assert kwargs["connect_timeout"] == 10
        assert kwargs["read_timeout"] == 30
        assert kwargs["write_timeout"] == 60


class TestMariaDBPoolConfig:
    """MariaDBPoolConfig: parámetros comunes de pool (sync y async).

    ``charset`` se conserva en la config porque lo usa el pool async (aiomysql); el pool sync lo quita antes de
    ``mariadb.ConnectionPool()``, que no lo admite (ver ``test_mariadb_charset_init_command.py``).
    """

    def test_pool_kwargs_include_charset(self) -> None:
        """La config de pool conserva ``charset`` (lo consume aiomysql)."""
        kwargs = MariaDBPoolConfig.from_params(BASE).to_driver_kwargs()
        assert "charset" in kwargs
        assert kwargs["charset"] == "utf8mb4"  # Default from MariaDBConnectionConfig
        assert "pool_size" in kwargs

    def test_pool_kwargs_include_required_connection_params(self) -> None:
        """Pool kwargs debe incluir parámetros necesarios para crear conexiones dentro del pool."""
        kwargs = MariaDBPoolConfig.from_params(BASE).to_driver_kwargs()
        assert kwargs["host"] == "db"
        assert kwargs["user"] == "app"
        assert kwargs["password"] == "pw"
        assert kwargs["database"] == "sales"
        assert kwargs["port"] == 3306

    def test_pool_kwargs_include_pool_size(self) -> None:
        """Pool kwargs debe incluir pool_size."""
        params = {**BASE, "pool_size": 20}
        kwargs = MariaDBPoolConfig.from_params(params).to_driver_kwargs()
        assert kwargs["pool_size"] == 20

    def test_pool_kwargs_include_pool_name_if_provided(self) -> None:
        """Pool kwargs debe incluir pool_name si se especifica."""
        params = {**BASE, "pool_name": "my_pool"}
        kwargs = MariaDBPoolConfig.from_params(params).to_driver_kwargs()
        assert kwargs.get("pool_name") == "my_pool"

    def test_pool_kwargs_omit_pool_name_if_not_provided(self) -> None:
        """Pool kwargs no debe incluir pool_name si no se especifica."""
        kwargs = MariaDBPoolConfig.from_params(BASE).to_driver_kwargs()
        assert "pool_name" not in kwargs or kwargs.get("pool_name") is None

    def test_pool_kwargs_propagates_charset_from_connection_config(self) -> None:
        """Charset debe propagarse correctamente desde MariaDBConnectionConfig a pool kwargs.

        Verifica que:
        1. Charset por defecto (utf8mb4) se propague al pool
        2. Charset personalizado (ej: latin1) también se propague
        3. Lo consume el pool async (aiomysql); el pool sync lo descarta antes del driver
        """
        # Test 1: User doesn't provide charset (defaults to utf8mb4 in MariaDBConnectionConfig)
        kwargs = MariaDBPoolConfig.from_params(BASE).to_driver_kwargs()
        assert "charset" in kwargs
        assert kwargs["charset"] == "utf8mb4"

        # Test 2: User provides explicit charset - también se propaga al pool
        params = {**BASE, "charset": "latin1"}
        kwargs = MariaDBPoolConfig.from_params(params).to_driver_kwargs()
        assert "charset" in kwargs
        assert kwargs["charset"] == "latin1"

        # Test 3: User provides empty charset - MariaDBConnectionConfig falls back to utf8mb4
        params = {**BASE, "charset": ""}
        kwargs = MariaDBPoolConfig.from_params(params).to_driver_kwargs()
        assert "charset" in kwargs
        assert kwargs["charset"] == "utf8mb4"  # Empty string is treated as falsy, defaults to utf8mb4


class TestMariaDBNativePoolFallback:
    """Validar fallback defensivo cuando el driver rechaza kwargs opcionales en ConnectionPool."""

    def test_pool_reraises_type_error_when_not_related_to_charset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_connection_pool(**kwargs: Any) -> Any:
            _ = kwargs
            raise TypeError("connect() missing required positional argument")

        fake_mariadb = SimpleNamespace(ConnectionPool=fake_connection_pool, __version__="1.1.14")
        monkeypatch.setattr(pool_connection_mariadb, "HAS_MARIADB", True)
        monkeypatch.setattr(pool_connection_mariadb, "mariadb", fake_mariadb)

        with pytest.raises(TypeError, match="missing required positional argument"):
            pool_connection_mariadb.PoolConnection({**BASE, "pool_name": "my_pool"})

    def test_pool_executes_init_command_manually_when_pool_rejects_it(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Fix A: init_command rechazado por el pool se ejecuta manualmente en get_connection()."""
        executed_commands: list[str] = []

        class FakeCursor:
            def execute(self, sql: str) -> None:
                executed_commands.append(sql)

            def close(self) -> None:
                pass

        class FakeConn:
            def cursor(self) -> FakeCursor:
                return FakeCursor()

            def close(self) -> None:
                pass

        fake_conn = FakeConn()

        def fake_connection_pool(**kwargs: Any) -> Any:
            if "init_command" in kwargs:
                raise TypeError("connect() got an unexpected keyword argument 'init_command'")
            pool = MagicMock()
            pool.get_connection.return_value = fake_conn
            return pool

        fake_mariadb = SimpleNamespace(ConnectionPool=fake_connection_pool, __version__="1.1.12")
        monkeypatch.setattr(pool_connection_mariadb, "HAS_MARIADB", True)
        monkeypatch.setattr(pool_connection_mariadb, "mariadb", fake_mariadb)

        pool = pool_connection_mariadb.PoolConnection({**BASE, "pool_name": "test_pool"})
        conn = pool.get_connection()
        pool.close()

        assert conn is fake_conn
        assert len(executed_commands) == 1
        assert "SET NAMES" in executed_commands[0]

    def test_pool_no_pending_init_command_when_pool_accepts_it(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Fix A: si el pool acepta init_command, _pending_init_command es None."""

        def fake_connection_pool(**kwargs: Any) -> Any:
            pool = MagicMock()
            pool.get_connection.return_value = MagicMock()
            return pool

        fake_mariadb = SimpleNamespace(ConnectionPool=fake_connection_pool, __version__="1.1.14")
        monkeypatch.setattr(pool_connection_mariadb, "HAS_MARIADB", True)
        monkeypatch.setattr(pool_connection_mariadb, "mariadb", fake_mariadb)

        pool = pool_connection_mariadb.PoolConnection({**BASE, "pool_name": "test_pool"})
        assert pool._pending_init_command is None
        pool.close()
