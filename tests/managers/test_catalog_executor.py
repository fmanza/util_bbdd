"""Tests para ManagerCatalogExecutor y AsyncManagerCatalogExecutor con reintento."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from util_bbdd._core.exceptions import DatabaseException, MetadataError
from util_bbdd.managers._catalog_executor import (
    AsyncManagerCatalogExecutor,
    ManagerCatalogExecutor,
)


class TestManagerCatalogExecutorRetry:
    """Tests del reintento en ManagerCatalogExecutor (sync)."""

    def test_fetch_all_retries_on_system_error(self):
        """Verifica que reintentan tras SystemError."""
        provider = Mock(return_value=Mock())
        releaser = Mock()
        executor = ManagerCatalogExecutor(provider, releaser)

        with patch("util_bbdd.managers._catalog_executor.driver_paramstyle") as mock_style:
            mock_style.return_value = "qmark"
            with patch("util_bbdd.managers._catalog_executor.DbapiCatalogExecutor") as mock_dbapi_class:
                mock_dbapi = Mock()
                mock_dbapi_class.return_value = mock_dbapi
                mock_dbapi.fetch_all.side_effect = [
                    SystemError("cursor error"),
                    [(1, 2, 3)],  # Success on second attempt
                ]

                with patch("time.sleep"):
                    result = executor.fetch_all("SELECT * FROM test", {})

                assert result == [(1, 2, 3)]
                assert mock_dbapi.fetch_all.call_count == 2
                assert releaser.call_count == 2

    def test_fetch_all_fails_after_max_retries(self):
        """Verifica que falla tras agotar reintentos."""
        provider = Mock(return_value=Mock())
        releaser = Mock()
        executor = ManagerCatalogExecutor(provider, releaser)

        with patch("util_bbdd.managers._catalog_executor.driver_paramstyle") as mock_style:
            mock_style.return_value = "qmark"
            with patch("util_bbdd.managers._catalog_executor.DbapiCatalogExecutor") as mock_dbapi_class:
                mock_dbapi = Mock()
                mock_dbapi_class.return_value = mock_dbapi
                mock_dbapi.fetch_all.side_effect = SystemError("persistent error")

                with patch("time.sleep"):
                    with pytest.raises(MetadataError) as exc:
                        executor.fetch_all("SELECT * FROM test", {})

                    assert "SystemError del driver mariadb" in str(exc.value)

                assert mock_dbapi.fetch_all.call_count == 3
                assert releaser.call_count == 3

    def test_fetch_all_no_retry_on_database_exception(self):
        """Verifica que DatabaseException no se reintentan."""
        provider = Mock(return_value=Mock())
        releaser = Mock()
        executor = ManagerCatalogExecutor(provider, releaser)

        with patch("util_bbdd.managers._catalog_executor.driver_paramstyle") as mock_style:
            mock_style.return_value = "qmark"
            with patch("util_bbdd.managers._catalog_executor.DbapiCatalogExecutor") as mock_dbapi_class:
                mock_dbapi = Mock()
                mock_dbapi_class.return_value = mock_dbapi
                mock_dbapi.fetch_all.side_effect = DatabaseException("db error")

                with pytest.raises(DatabaseException):
                    executor.fetch_all("SELECT * FROM test", {})

                assert mock_dbapi.fetch_all.call_count == 1


class TestAsyncManagerCatalogExecutorRetry:
    """Tests del reintento en AsyncManagerCatalogExecutor (async)."""

    @pytest.mark.asyncio
    async def test_fetch_all_retries_on_system_error(self):
        """Verifica que reintentan tras SystemError (async)."""
        provider = AsyncMock()
        releaser = AsyncMock()
        executor = AsyncManagerCatalogExecutor(provider, releaser)

        with patch("util_bbdd.managers._catalog_executor.driver_paramstyle") as mock_style:
            mock_style.return_value = "dollar"
            with patch("util_bbdd.managers._catalog_executor.to_driver") as mock_to_driver:
                mock_to_driver.return_value = ("SELECT $1", [])
                mock_conn = Mock()
                provider.return_value = mock_conn
                mock_conn.fetch = AsyncMock(
                    side_effect=[
                        SystemError("cursor error"),
                        [(1, 2, 3)],
                    ]
                )

                with patch("asyncio.sleep", new_callable=AsyncMock):
                    result = await executor.fetch_all("SELECT * FROM test", {})

                assert result == [(1, 2, 3)]
                assert provider.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_all_fails_after_max_retries_async(self):
        """Verifica que falla tras agotar reintentos (async)."""
        provider = AsyncMock()
        releaser = AsyncMock()
        executor = AsyncManagerCatalogExecutor(provider, releaser)

        with patch("util_bbdd.managers._catalog_executor.driver_paramstyle") as mock_style:
            mock_style.return_value = "dollar"
            with patch("util_bbdd.managers._catalog_executor.to_driver") as mock_to_driver:
                mock_to_driver.return_value = ("SELECT $1", [])
                mock_conn = Mock()
                provider.return_value = mock_conn
                mock_conn.fetch = AsyncMock(side_effect=SystemError("persistent error"))

                with patch("asyncio.sleep", new_callable=AsyncMock):
                    with pytest.raises(MetadataError) as exc:
                        await executor.fetch_all("SELECT * FROM test", {})

                    assert "SystemError del driver mariadb" in str(exc.value)

                # max_retries=2 → 3 intentos totales (1 inicial + 2 reintentos)
                assert provider.call_count == 3
                assert releaser.call_count == 3


class TestManagerCatalogExecutorAdaptive:
    """Verifica que ManagerCatalogExecutor usa AdaptiveCatalogExecutor para MariaDB/MySQL."""

    @staticmethod
    def _mariadb_conn() -> object:
        """Conexión cuyo módulo parece 'mariadb' para activar la ruta adaptativa."""

        class _Conn:
            pass

        _Conn.__module__ = "mariadb"
        return _Conn()

    @staticmethod
    def _pymysql_conn() -> object:
        class _Conn:
            pass

        _Conn.__module__ = "pymysql"
        return _Conn()

    def test_mariadb_uses_adaptive_executor(self) -> None:
        """Driver mariadb activa AdaptiveCatalogExecutor en lugar de DbapiCatalogExecutor."""
        conn = self._mariadb_conn()
        executor = ManagerCatalogExecutor(Mock(return_value=conn), Mock())

        with patch("util_bbdd.managers._catalog_executor.driver_paramstyle", return_value="qmark"):
            with patch("util_bbdd.managers._catalog_executor.AdaptiveCatalogExecutor") as cls:
                instance = Mock()
                instance.fetch_all.return_value = [(1, 2)]
                cls.return_value = instance

                result = executor.fetch_all("SELECT 1", {})

        assert result == [(1, 2)]
        cls.assert_called_once()
        instance.fetch_all.assert_called_once()

    def test_pymysql_uses_adaptive_executor(self) -> None:
        """Driver pymysql también activa AdaptiveCatalogExecutor."""
        conn = self._pymysql_conn()
        executor = ManagerCatalogExecutor(Mock(return_value=conn), Mock())

        with patch("util_bbdd.managers._catalog_executor.driver_paramstyle", return_value="pyformat"):
            with patch("util_bbdd.managers._catalog_executor.AdaptiveCatalogExecutor") as cls:
                instance = Mock()
                instance.fetch_all.return_value = [(3, 4)]
                cls.return_value = instance

                result = executor.fetch_all("SELECT 1", {})

        assert result == [(3, 4)]
        cls.assert_called_once()

    def test_non_mariadb_uses_dbapi_executor(self) -> None:
        """Drivers que no son MariaDB/MySQL siguen usando DbapiCatalogExecutor."""
        provider = Mock(return_value=Mock())  # tipo: unittest.mock → no adaptativo
        executor = ManagerCatalogExecutor(provider, Mock())

        with patch("util_bbdd.managers._catalog_executor.driver_paramstyle", return_value="pyformat"):
            with patch("util_bbdd.managers._catalog_executor.DbapiCatalogExecutor") as cls:
                instance = Mock()
                instance.fetch_all.return_value = [(5, 6)]
                cls.return_value = instance

                result = executor.fetch_all("SELECT 1", {})

        assert result == [(5, 6)]
        cls.assert_called_once()

    def test_adaptive_executor_cached_across_calls(self) -> None:
        """AdaptiveCatalogExecutor se crea una sola vez; las llamadas posteriores reusan la instancia."""
        conn = self._mariadb_conn()
        executor = ManagerCatalogExecutor(Mock(return_value=conn), Mock())

        with patch("util_bbdd.managers._catalog_executor.driver_paramstyle", return_value="qmark"):
            with patch("util_bbdd.managers._catalog_executor.AdaptiveCatalogExecutor") as cls:
                instance = Mock()
                instance.fetch_all.return_value = [(1,)]
                cls.return_value = instance

                executor.fetch_all("SELECT 1", {})
                executor.fetch_all("SELECT 2", {})

        cls.assert_called_once()  # instanciado solo una vez
        assert instance.fetch_all.call_count == 2  # dos consultas ejecutadas
