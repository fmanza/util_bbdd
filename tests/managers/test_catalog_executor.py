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

    def test_fetch_all_gracefully_handles_ora_00942_oracle_pre12c(self):
        """Verifica que ORA-00942 (Oracle pre-12c, no IDENTITY support) retorna lista vacía."""
        provider = Mock(return_value=Mock())
        releaser = Mock()
        executor = ManagerCatalogExecutor(provider, releaser)

        with patch("util_bbdd.managers._catalog_executor.driver_paramstyle") as mock_style:
            mock_style.return_value = "named"
            with patch("util_bbdd.managers._catalog_executor.DbapiCatalogExecutor") as mock_dbapi_class:
                mock_dbapi = Mock()
                mock_dbapi_class.return_value = mock_dbapi
                # Simulate Oracle ORA-00942: table or view does not exist (all_tab_identity_cols)
                mock_dbapi.fetch_all.side_effect = Exception("ORA-00942: table or view does not exist")

                with patch("util_bbdd.managers._catalog_executor.logger") as mock_logger:
                    result = executor.fetch_all("SELECT * FROM all_tab_identity_cols WHERE owner = :schema", {})

                # Should return empty list (graceful fallback)
                assert result == []
                # Should log a warning explaining the issue
                assert mock_logger.warning.called
                warning_msg = mock_logger.warning.call_args[0][0]
                assert "ORA-00942" in warning_msg
                assert "Oracle version pre-12c" in warning_msg
                assert "IDENTITY metadata" in warning_msg
                # Connection should be released once
                assert releaser.call_count == 1


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
                assert releaser.call_count == 2
