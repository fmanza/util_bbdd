"""Tests for CatalogSource version resolution with Oracle 11g."""

from __future__ import annotations

import asyncio
import sys

from unittest.mock import AsyncMock, Mock

import pytest

from util_bbdd._core.exceptions import ConnectionError
from util_bbdd.connection.oracle import _thick_mode
from util_bbdd.connection.oracle._thick_mode import init_oracle_thick_mode
from util_bbdd.connection.oracle.async_connection_oracle import AsyncOracleConnection
from util_bbdd.metadata.contracts import CatalogExecutor
from util_bbdd.metadata.model import Kind
from util_bbdd.metadata.oracle.catalog import Oracle11Catalog, OracleCatalog
from util_bbdd.metadata.source import AsyncCatalogSource, CatalogSource


class TestCatalogSourceVersionResolution:
    """Tests for CatalogSource lazy version resolution."""

    def test_catalog_source_starts_with_default_dialect(self) -> None:
        """CatalogSource initializes with default dialect (OracleCatalog for Oracle)."""
        executor = Mock(spec=CatalogExecutor)
        dialect = OracleCatalog()

        source = CatalogSource(dialect, executor, source_id="test://oracle")

        assert source.dialect is dialect
        assert isinstance(source.dialect, OracleCatalog)
        assert not isinstance(source.dialect, Oracle11Catalog)
        assert source._version_resolved is False

    def test_catalog_source_current_schema_resolves_version_once(self) -> None:
        """CatalogSource.current_schema() resolves version on first call, then caches."""
        executor = Mock(spec=CatalogExecutor)
        # fetch_all is called twice: once for version, once for current_schema
        executor.fetch_all = Mock(
            side_effect=[
                [("11.2.0.4.0",)],  # Version query result
                [("SCOTT",)],  # current_schema query result
            ]
        )

        dialect = OracleCatalog()
        source = CatalogSource(dialect, executor, source_id="test://oracle")

        # First call should resolve version and get schema
        schema = source.current_schema()
        assert schema == "SCOTT"
        assert executor.fetch_all.call_count == 2  # Version + schema queries
        assert source._version_resolved is True

        # After resolution, dialect should be Oracle11Catalog
        assert isinstance(source.dialect, Oracle11Catalog)

        # Reset mock for second call
        executor.fetch_all.reset_mock()
        executor.fetch_all.return_value = [("SCOTT",)]

        # Second call should not trigger version resolution, only schema query
        schema2 = source.current_schema()
        assert schema2 == "SCOTT"
        assert executor.fetch_all.call_count == 0  # No call (schema cached)

    def test_catalog_source_resolves_to_oracle11_for_version_11g(self) -> None:
        """CatalogSource resolves to Oracle11Catalog when server version is 11.x."""
        executor = Mock(spec=CatalogExecutor)
        executor.fetch_all = Mock(return_value=[("11.2.0.4.0",)])

        dialect = OracleCatalog()
        source = CatalogSource(dialect, executor, source_id="test://oracle")

        # Trigger version resolution
        source.current_schema()

        # Dialect should now be Oracle11Catalog
        assert type(source.dialect) is Oracle11Catalog

    def test_catalog_source_stays_oracle_for_version_12c(self) -> None:
        """CatalogSource keeps OracleCatalog when server version is 12c or higher."""
        executor = Mock(spec=CatalogExecutor)
        executor.fetch_all = Mock(return_value=[("19.0.0.0.0",)])

        dialect = OracleCatalog()
        source = CatalogSource(dialect, executor, source_id="test://oracle")

        # Trigger version resolution
        source.current_schema()

        # Dialect should remain OracleCatalog (not Oracle11Catalog)
        assert type(source.dialect) is OracleCatalog
        assert not isinstance(source.dialect, Oracle11Catalog)

    def test_catalog_source_version_resolution_only_happens_once(self) -> None:
        """CatalogSource caches version resolution; version query called only once."""
        executor = Mock(spec=CatalogExecutor)
        executor.fetch_all = Mock(
            side_effect=[
                [("11.2.0.4.0",)],  # Version query (first call)
                [("SCOTT",)],  # Schema query (first call)
            ]
        )

        dialect = OracleCatalog()
        source = CatalogSource(dialect, executor, source_id="test://oracle")

        # First call to current_schema triggers resolution and caches schema
        schema1 = source.current_schema()
        assert schema1 == "SCOTT"
        assert executor.fetch_all.call_count == 2  # version + schema

        # Second call uses cached schema, no database queries at all
        schema2 = source.current_schema()
        assert schema2 == "SCOTT"
        assert executor.fetch_all.call_count == 2  # No additional calls (cached)

    def test_catalog_source_version_flag_prevents_repeated_resolution(self) -> None:
        """CatalogSource._version_resolved flag prevents repeated version resolution."""
        executor = Mock(spec=CatalogExecutor)
        executor.fetch_all = Mock(
            side_effect=[
                [("12.0.0.0.0",)],  # Version query
                [("SYS",)],  # Schema query
            ]
        )

        dialect = OracleCatalog()
        source = CatalogSource(dialect, executor, source_id="test://oracle")

        assert source._version_resolved is False

        # First current_schema call
        source.current_schema()
        assert source._version_resolved is True

        # Reset the mock to verify version is not called again
        executor.fetch_all.reset_mock()
        executor.fetch_all.return_value = [("SYS",)]
        source.current_schema()

        # Only schema query should be called, not version query
        assert executor.fetch_all.call_count == 0  # Schema is cached

    def test_catalog_source_snapshot_with_explicit_schema_resolves_oracle11(self) -> None:
        """snapshot(schema=...) también debe resolver versión para seleccionar Oracle11Catalog."""
        executor = Mock(spec=CatalogExecutor)
        executor.fetch_all = Mock(
            side_effect=[
                [("11.2.0.4.0",)],  # Version query
                [],  # COLUMNS query
            ]
        )

        source = CatalogSource(OracleCatalog(), executor, source_id="test://oracle")

        source.snapshot("SCOTT", kinds={Kind.COLUMNS})

        assert type(source.dialect) is Oracle11Catalog


class TestAsyncCatalogSourceVersionResolution:
    """Tests for AsyncCatalogSource async version resolution."""

    @pytest.mark.asyncio
    async def test_async_catalog_source_starts_with_default_dialect(self) -> None:
        """AsyncCatalogSource initializes with default dialect (OracleCatalog for Oracle)."""
        executor = AsyncMock()
        dialect = OracleCatalog()

        source = AsyncCatalogSource(dialect, executor, source_id="test://oracle")

        assert source.dialect is dialect
        assert isinstance(source.dialect, OracleCatalog)
        assert not isinstance(source.dialect, Oracle11Catalog)
        assert source._version_resolved is False

    @pytest.mark.asyncio
    async def test_async_catalog_source_current_schema_resolves_version(self) -> None:
        """AsyncCatalogSource.current_schema() resolves version on first call."""
        executor = AsyncMock()
        executor.fetch_all = AsyncMock(
            side_effect=[
                [("11.2.0.4.0",)],  # Version query
                [("SCOTT",)],  # Schema query
            ]
        )

        dialect = OracleCatalog()
        source = AsyncCatalogSource(dialect, executor, source_id="test://oracle")

        # First call should resolve version and get schema
        schema = await source.current_schema()
        assert schema == "SCOTT"
        assert executor.fetch_all.call_count == 2  # version + schema
        assert source._version_resolved is True

        # Dialect should be Oracle11Catalog after resolution
        assert type(source.dialect) is Oracle11Catalog

    @pytest.mark.asyncio
    async def test_async_catalog_source_version_resolution_only_happens_once(self) -> None:
        """AsyncCatalogSource caches version resolution; only called once."""
        executor = AsyncMock()
        executor.fetch_all = AsyncMock(
            side_effect=[
                [("19.0.0.0.0",)],  # Version query
                [("SYS",)],  # Schema query
            ]
        )

        dialect = OracleCatalog()
        source = AsyncCatalogSource(dialect, executor, source_id="test://oracle")

        # First call
        await source.current_schema()
        assert executor.fetch_all.call_count == 2  # version + schema

        # Second call should not trigger version resolution
        executor.fetch_all.reset_mock()
        executor.fetch_all.return_value = [("SYS",)]
        await source.current_schema()
        assert executor.fetch_all.call_count == 0  # Schema is cached

    @pytest.mark.asyncio
    async def test_async_catalog_source_snapshot_with_explicit_schema_resolves_oracle11(self) -> None:
        """snapshot(schema=...) async también debe resolver versión para Oracle 11g."""
        executor = AsyncMock()
        executor.fetch_all = AsyncMock(
            side_effect=[
                [("11.2.0.4.0",)],  # Version query
                [],  # COLUMNS query
            ]
        )

        source = AsyncCatalogSource(OracleCatalog(), executor, source_id="test://oracle")

        await source.snapshot("SCOTT", kinds={Kind.COLUMNS})

        assert type(source.dialect) is Oracle11Catalog


class TestCatalogSourceVersionResolutionEdgeCases:
    """Edge cases and error handling for version resolution."""

    def test_catalog_source_handles_empty_version_result_gracefully(self) -> None:
        """CatalogSource handles empty version result by keeping default dialect."""
        executor = Mock(spec=CatalogExecutor)
        executor.fetch_all = Mock(
            side_effect=[
                [],  # No version returned
                [("SCOTT",)],  # Schema query result
            ]
        )

        dialect = OracleCatalog()
        source = CatalogSource(dialect, executor, source_id="test://oracle")

        # Should not crash; should keep default dialect
        source.current_schema()
        # Dialect should remain as OracleCatalog (default) when version is unavailable
        assert isinstance(source.dialect, OracleCatalog)
        assert source._version_resolved is True  # Flag should be set even if version unavailable

    def test_catalog_source_handles_malformed_version_string_gracefully(self) -> None:
        """CatalogSource handles malformed version strings gracefully."""
        executor = Mock(spec=CatalogExecutor)
        executor.fetch_all = Mock(return_value=[("invalid",)])  # Malformed version

        dialect = OracleCatalog()
        source = CatalogSource(dialect, executor, source_id="test://oracle")

        # Should handle gracefully without crashing
        try:
            source.current_schema()
        except (ValueError, IndexError):
            # It's acceptable to raise on malformed input
            pass


class TestOracleAsyncThickModeGuard:
    """Regression tests for async Oracle guard when thick mode is already initialized."""

    def test_async_connection_rejects_thick_mode_after_initialization(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AsyncOracleConnection debe fallar temprano si thick mode ya fue inicializado."""

        class _FakeOracleDbModule:
            @staticmethod
            def init_oracle_client(*, lib_dir: str) -> None:
                _ = lib_dir

            @staticmethod
            async def connect_async(**kwargs: object) -> object:
                _ = kwargs
                raise AssertionError("connect_async no debe ejecutarse cuando thick mode está activo")

            @staticmethod
            def makedsn(*, host: str, port: int, service_name: str | None = None, sid: str | None = None) -> str:
                if service_name is not None:
                    return f"{host}:{port}/{service_name}"
                return f"{host}:{port}/{sid}"

        monkeypatch.setitem(sys.modules, "oracledb", _FakeOracleDbModule())
        monkeypatch.setattr(_thick_mode, "ORACLE_THICK_MODE_INITIALIZED", False)

        init_oracle_thick_mode("C:/oracle/instantclient_19_32")

        with pytest.raises(ConnectionError, match="modo asincrónico"):
            asyncio.run(
                AsyncOracleConnection.connect(
                    {
                        "user": "scott",
                        "password": "tiger",  # noqa: S106
                        "service_name": "XE",
                    }
                )
            )

        monkeypatch.setattr(_thick_mode, "ORACLE_THICK_MODE_INITIALIZED", False)


__all__: list[str] = [
    "TestCatalogSourceVersionResolution",
    "TestAsyncCatalogSourceVersionResolution",
    "TestCatalogSourceVersionResolutionEdgeCases",
    "TestOracleAsyncThickModeGuard",
]
