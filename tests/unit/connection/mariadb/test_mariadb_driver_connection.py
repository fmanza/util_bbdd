"""Motor ``mariadb`` (mariadb.Connection/ConnectionPool): configuración y validación.

Tests unitarios para MariaDBConnectionConfig y MariaDBPoolConfig sin servidor real.
"""

from __future__ import annotations

from typing import Any

from util_bbdd.connection.config import MariaDBConnectionConfig, MariaDBPoolConfig

BASE: dict[str, Any] = {"host": "db", "user": "app", "password": "pw", "database": "sales"}


class TestMariaDBConnectionConfig:
    """Validar que MariaDBConnectionConfig incluye charset por defecto."""

    def test_defaults_include_charset_utf8mb4(self) -> None:
        """Charset debe ser utf8mb4 por defecto para evitar UnicodeDecodeError (H-32 hotfix)."""
        kwargs = MariaDBConnectionConfig.from_params(BASE).to_driver_kwargs()
        assert kwargs["charset"] == "utf8mb4"

    def test_explicit_charset_is_preserved(self) -> None:
        """Si el usuario especifica charset, debe respetarse."""
        params = {**BASE, "charset": "latin1"}
        kwargs = MariaDBConnectionConfig.from_params(params).to_driver_kwargs()
        assert kwargs["charset"] == "latin1"

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
    """Validar que MariaDBPoolConfig excluye charset al preparar parámetros para ConnectionPool."""

    def test_pool_kwargs_include_charset(self) -> None:
        """Pool kwargs debe incluir 'charset': mariadb.ConnectionPool() lo acepta y pasa a conexiones.

        El charset se configura por defecto a 'utf8mb4' en MariaDBConnectionConfig
        (ver H-32 hotfix para UnicodeDecodeError), y debe propagarse a través de
        MariaDBPoolConfig para asegurar encoding consistente en todas las conexiones
        del pool.
        """
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
        3. mariadb.ConnectionPool() recibe charset para configurar encoding en conexiones
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
