"""Motor ``mysql`` (PyMySQL/aiomysql): configuración, conexión, pool y factorías, sin servidor real."""

from __future__ import annotations

import asyncio
import inspect

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from util_bbdd._core.exceptions import ConnectionError, DriverError, PoolTimeoutError, ValidationError
from util_bbdd._drivers.driver_validator import DriverValidator
from util_bbdd.connection.config import MySQLConnectionConfig, MySQLPoolConfig
from util_bbdd.connection.factory import ConnectionFactory
from util_bbdd.connection.mysql.async_connection_mysql import AsyncMySQLConnection, build_aiomysql_connect_kwargs
from util_bbdd.connection.mysql.connection_mysql import MySQLConnection, build_pymysql_connect_kwargs
from util_bbdd.connection.mysql.pool_connection_mysql import PoolConnection
from util_bbdd.connection.params import ConnectionParamsManager
from util_bbdd.connection.protocols import ConnectionPoolProtocol
from util_bbdd.factory.async_sqlalchemy_engine_factory import AsyncSQLAlchemyEngineFactory
from util_bbdd.factory.pool_factory import PoolFactory
from util_bbdd.factory.sqlalchemy_engine_factory import SQLAlchemyEngineFactory

BASE: dict[str, Any] = {"host": "db", "user": "app", "password": "pw", "database": "sales"}


class TestMySQLConnectionConfig:
    def test_defaults(self) -> None:
        kwargs = MySQLConnectionConfig.from_params(BASE).to_driver_kwargs()
        assert kwargs == {
            **BASE,
            "port": 3306,
            "autocommit": False,
            "connect_timeout": 10,
            "read_timeout": 30,
            "write_timeout": 60,
        }

    def test_missing_required_raises(self) -> None:
        with pytest.raises(ValueError, match="mysql: database"):
            MySQLConnectionConfig.from_params({**BASE, "database": ""})

    def test_local_infile_and_client_flag_are_not_forwarded(self) -> None:
        params = {**BASE, "local_infile": True, "client_flag": 65536, "init_command": "SET x=1"}
        kwargs = MySQLConnectionConfig.from_params(params).to_driver_kwargs()
        assert not {"local_infile", "client_flag", "init_command"} & set(kwargs)

    def test_ssl_and_optional_values(self) -> None:
        params = {**BASE, "charset": "utf8mb4", "ssl_ca": "/ca.pem", "ssl_verify_cert": "true", "port": "3307"}
        kwargs = MySQLConnectionConfig.from_params(params).to_driver_kwargs()
        assert kwargs["charset"] == "utf8mb4"
        assert kwargs["ssl_ca"] == "/ca.pem"
        assert kwargs["ssl_verify_cert"] is True
        assert kwargs["port"] == 3307
        assert "ssl_verify_identity" not in kwargs

    def test_pool_config_defaults_and_values(self) -> None:
        assert MySQLPoolConfig.from_params(BASE).to_driver_kwargs() == {
            **MySQLConnectionConfig.from_params(BASE).to_driver_kwargs(),
            "pool_size": 5,
            "max_overflow": 10,
            "pool_timeout": 30,
            "pool_recycle": 3600,
        }
        config = MySQLPoolConfig.from_params({**BASE, "pool_size": 2, "max_overflow": 0})
        assert (config.pool_size, config.max_overflow) == (2, 0)

    def test_params_manager_resolves_mysql(self) -> None:
        assert isinstance(ConnectionParamsManager.get_connection_config("mysql", BASE), MySQLConnectionConfig)
        assert isinstance(ConnectionParamsManager.get_pool_config("mysql", BASE), MySQLPoolConfig)
        prepared = ConnectionParamsManager.prepare_and_validate("mysql", dict(BASE))
        assert prepared["port"] == 3306


class TestDriverKwargs:
    def test_pymysql_groups_tls_in_ssl(self) -> None:
        kwargs = build_pymysql_connect_kwargs({**BASE, "ssl_ca": "/ca", "ssl_key": "/k", "ssl_verify_cert": True})
        # La verificación va dentro de ``ssl``: como kwarg suelto PyMySQL rehacía ``ssl`` con ca=None.
        assert kwargs["ssl"] == {"ca": "/ca", "key": "/k", "verify_mode": True}
        assert "ssl_verify_cert" not in kwargs
        assert "ssl_ca" not in kwargs

    def test_pymysql_without_tls_has_no_ssl(self) -> None:
        assert "ssl" not in build_pymysql_connect_kwargs(dict(BASE))

    def test_aiomysql_renames_database_and_drops_unsupported(self) -> None:
        def fake_connect(host=None, user=None, password="", db=None, port=3306, connect_timeout=None):  # noqa: ANN001, ANN202
            return None

        kwargs = build_aiomysql_connect_kwargs(
            {**BASE, "port": 3306, "read_timeout": 30, "connect_timeout": 5, "ssl_ca": "/ca"},
            fake_connect,
        )
        assert kwargs == {
            "host": "db",
            "user": "app",
            "password": "pw",
            "db": "sales",
            "port": 3306,
            "connect_timeout": 5,
        }

    def test_aiomysql_kwargs_match_real_signature(self) -> None:
        aiomysql = pytest.importorskip("aiomysql")
        kwargs = build_aiomysql_connect_kwargs(
            MySQLConnectionConfig.from_params(BASE).to_driver_kwargs(), aiomysql.connect
        )
        assert set(kwargs) <= set(inspect.signature(aiomysql.connect).parameters)
        assert kwargs["db"] == "sales"


class TestMySQLConnection:
    def test_connect_uses_pymysql(self) -> None:
        with patch("pymysql.connect", return_value="conn") as connect:
            assert MySQLConnection.connect({**BASE, "pool_size": 5}) == "conn"
        called = connect.call_args.kwargs
        assert called["database"] == "sales"
        assert "pool_size" not in called

    def test_connect_error_is_tagged_mysql(self) -> None:
        with patch("pymysql.connect", side_effect=OSError("refused")):
            with pytest.raises(ConnectionError) as exc_info:
                MySQLConnection.connect(dict(BASE))
        assert exc_info.value.db_type == "mysql"

    def test_async_connect_uses_aiomysql_contract(self) -> None:
        aiomysql = pytest.importorskip("aiomysql")
        connect = AsyncMock(return_value="aconn")
        connect.__signature__ = inspect.signature(aiomysql.connect)  # el mapeo filtra por la firma real
        with patch("aiomysql.connect", new=connect):
            assert asyncio.run(AsyncMySQLConnection.connect(dict(BASE))) == "aconn"
        called = connect.call_args.kwargs
        assert called["db"] == "sales"
        assert "database" not in called and "read_timeout" not in called


class TestMySQLPool:
    def _pool(self, **extra: Any) -> PoolConnection:
        return PoolConnection({**BASE, **extra})

    def test_satisfies_pool_protocol(self) -> None:
        with patch("pymysql.connect", return_value=MagicMock()):
            pool = self._pool()
            assert isinstance(pool, ConnectionPoolProtocol)
            pool.close()

    def test_get_and_return_connection_reuses_driver_connection(self) -> None:
        with patch("pymysql.connect", side_effect=lambda **_: MagicMock()) as connect:
            pool = self._pool(pool_size=1, max_overflow=0)
            first = pool.get_connection()
            pool.close_connection(first)
            second = pool.get_connection()
            pool.close_connection(second)
            pool.close()
        assert connect.call_count == 1

    def test_exhausted_pool_raises_pool_timeout(self) -> None:
        with patch("pymysql.connect", side_effect=lambda **_: MagicMock()):
            pool = self._pool(pool_size=1, max_overflow=0, pool_timeout=0)
            held = pool.get_connection()
            with pytest.raises(PoolTimeoutError):
                pool.get_connection()
            pool.close_connection(held)
            pool.close()

    def test_closed_pool_rejects_connections(self) -> None:
        with patch("pymysql.connect", return_value=MagicMock()):
            pool = self._pool()
            pool.close()
            pool.close()  # idempotente
            with pytest.raises(RuntimeError, match="cerrado"):
                pool.get_connection()


class TestFactoriesAndValidation:
    def test_connection_factory_dispatches_mysql(self) -> None:
        with patch("util_bbdd.connection.mysql.connection_mysql.MySQLConnection.connect", return_value="c") as connect:
            assert ConnectionFactory.create_connection("mysql", dict(BASE)) == "c"
        connect.assert_called_once()

    def test_pool_factory_dispatches_mysql(self) -> None:
        with patch("pymysql.connect", return_value=MagicMock()):
            pool = PoolFactory.create_pool("mysql", dict(BASE))
            assert type(pool).__module__.endswith("pool_connection_mysql")
            pool.close()

    def test_async_builders_register_mysql(self) -> None:
        with patch(
            "util_bbdd.connection.mysql.async_connection_mysql.AsyncMySQLConnection.connect",
            new=AsyncMock(return_value="ac"),
        ):
            ConnectionFactory._async_connection_builders.pop("mysql", None)
            assert asyncio.run(ConnectionFactory.create_async_connection("mysql", dict(BASE))) == "ac"
        ConnectionFactory._async_connection_builders.pop("mysql", None)

    def test_async_pool_factory_registers_mysql(self) -> None:
        with patch(
            "util_bbdd.connection.mysql.async_pool_connection_mysql.AsyncMySQLPool.create",
            new=AsyncMock(return_value="ap"),
        ):
            PoolFactory._async_pool_builders.pop("mysql", None)
            assert asyncio.run(PoolFactory.create_async_pool("mysql", dict(BASE))) == "ap"
        PoolFactory._async_pool_builders.pop("mysql", None)

    def test_driver_validator_returns_pymysql(self) -> None:
        assert DriverValidator.check_driver_availability("mysql", {}) == "pymysql"

    def test_driver_validator_missing_pymysql(self) -> None:
        with patch("util_bbdd._drivers.driver_validator.importlib.util.find_spec", return_value=None):
            with pytest.raises(DriverError, match="MySQL"):
                DriverValidator.check_driver_availability("mysql", {})


class TestEngineUrls:
    PARAMS: dict[str, Any] = {"host": "db", "user": "app@corp", "password": "p@ss:w/rd", "port": 3307}

    def test_sync_url_is_pymysql_and_escapes_credentials(self) -> None:
        url = SQLAlchemyEngineFactory._build_mysql_connection_string(self.PARAMS, "sales")
        assert url.startswith("mysql+pymysql://app%40corp:p%40ss%3Aw%2Frd@db:3307/sales")
        assert "p@ss" not in SQLAlchemyEngineFactory._sanitize_conn_str(url)

    def test_async_url_is_aiomysql(self) -> None:
        url = AsyncSQLAlchemyEngineFactory._build_mysql_connection_string({**self.PARAMS, "database": "sales"}, None)
        assert url.startswith("mysql+aiomysql://") and url.endswith("/sales")
        with pytest.raises(ValidationError, match="database"):
            AsyncSQLAlchemyEngineFactory._build_mysql_connection_string({**self.PARAMS}, None)

    def test_url_requires_password(self) -> None:
        with pytest.raises(ValidationError, match="contraseña"):
            SQLAlchemyEngineFactory._build_mysql_connection_string({**self.PARAMS, "password": ""}, "sales")
