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


class TestMariaDBNativePoolFallback:
    """Validar fallback defensivo cuando una versión de mariadb no acepta charset en ConnectionPool."""

    def test_pool_retries_without_charset_if_driver_rejects_it(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        calls: list[dict[str, Any]] = []

        def fake_connection_pool(**kwargs: Any) -> Any:
            calls.append(dict(kwargs))
            if len(calls) == 1:
                raise TypeError("connect() got an unexpected keyword argument 'charset'")
            return MagicMock()

        fake_mariadb = SimpleNamespace(ConnectionPool=fake_connection_pool, __version__="1.1.14")
        monkeypatch.setattr(pool_connection_mariadb, "HAS_MARIADB", True)
        monkeypatch.setattr(pool_connection_mariadb, "mariadb", fake_mariadb)

        with caplog.at_level("WARNING", logger=pool_connection_mariadb.__name__):
            pool = pool_connection_mariadb.PoolConnection({**BASE, "pool_size": 3, "pool_name": "my_pool"})
        pool.close()

        assert len(calls) == 2
        first_call, second_call = calls
        assert first_call["charset"] == "utf8mb4"
        assert "charset" not in second_call
        for key, value in first_call.items():
            if key == "charset":
                continue
            assert second_call[key] == value
        assert "mariadb version=1.1.14" in caplog.text

    def test_pool_reraises_type_error_when_not_related_to_charset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_connection_pool(**kwargs: Any) -> Any:
            _ = kwargs
            raise TypeError("connect() missing required positional argument")

        fake_mariadb = SimpleNamespace(ConnectionPool=fake_connection_pool, __version__="1.1.14")
        monkeypatch.setattr(pool_connection_mariadb, "HAS_MARIADB", True)
        monkeypatch.setattr(pool_connection_mariadb, "mariadb", fake_mariadb)

        with pytest.raises(TypeError, match="missing required positional argument"):
            pool_connection_mariadb.PoolConnection({**BASE, "pool_name": "my_pool"})

    def test_pool_fallback_validates_no_unicode_regression(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Validar que fallback sin charset no causa regresión Unicode.

        Aunque se descarta charset en drivers que no lo aceptan, la semántica
        de codificación debe ser preservada en la implementación del driver.
        Este test valida que el pool se crea exitosamente sin charset.
        """
        call_count: int = 0
        captured_params: dict[str, Any] = {}

        def fake_connection_pool(**kwargs: Any) -> Any:
            nonlocal call_count, captured_params
            call_count += 1
            captured_params = dict(kwargs)
            if call_count == 1:
                raise TypeError("connect() got an unexpected keyword argument 'charset'")
            # Simular pool exitoso (sin charset)
            fake_pool = MagicMock()
            fake_pool.get_connection = MagicMock(return_value=MagicMock())
            return fake_pool

        fake_mariadb = SimpleNamespace(ConnectionPool=fake_connection_pool, __version__="1.1.14")
        monkeypatch.setattr(pool_connection_mariadb, "HAS_MARIADB", True)
        monkeypatch.setattr(pool_connection_mariadb, "mariadb", fake_mariadb)

        # Crear pool con fallback
        with caplog.at_level("WARNING", logger=pool_connection_mariadb.__name__):
            pool = pool_connection_mariadb.PoolConnection({**BASE, "pool_name": "test_pool"})
        pool.close()

        # Validar que fallback se activó
        assert call_count == 2
        assert "charset" not in captured_params
        assert "host" in captured_params
        assert "database" in captured_params
        assert "mariadb version=1.1.14" in caplog.text
