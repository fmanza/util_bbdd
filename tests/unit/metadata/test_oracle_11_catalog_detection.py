"""Oracle 11g version detection and catalog variant selection tests."""

from __future__ import annotations

from util_bbdd.metadata.oracle.catalog import Oracle11Catalog, OracleCatalog


class TestOracleVersionDetection:
    """Tests for Oracle catalog version detection and variant selection."""

    def test_oracle_catalog_for_server_version_12_or_higher_returns_oracle_catalog(self) -> None:
        """OracleCatalog.for_server_version(12+) returns OracleCatalog (12c+ features)."""
        oracle = OracleCatalog()

        # Test 12c
        result_12c = oracle.for_server_version((12, 0, 0, 0, 0))
        assert isinstance(result_12c, OracleCatalog)
        assert not isinstance(result_12c, Oracle11Catalog)

        # Test 19c
        result_19c = oracle.for_server_version((19, 0, 0, 0, 0))
        assert isinstance(result_19c, OracleCatalog)
        assert not isinstance(result_19c, Oracle11Catalog)

        # Test 23c
        result_23c = oracle.for_server_version((23, 0, 0, 0, 0))
        assert isinstance(result_23c, OracleCatalog)
        assert not isinstance(result_23c, Oracle11Catalog)

    def test_oracle_catalog_for_server_version_11_returns_oracle11_catalog(self) -> None:
        """OracleCatalog.for_server_version(11.x) returns Oracle11Catalog (no IDENTITY support)."""
        oracle = OracleCatalog()

        # Test 11.2.0.4.0
        result = oracle.for_server_version((11, 2, 0, 4, 0))
        assert isinstance(result, Oracle11Catalog)
        assert type(result) is Oracle11Catalog

    def test_oracle11_catalog_for_server_version_11_returns_oracle11_catalog(self) -> None:
        """Oracle11Catalog.for_server_version(11.x) returns Oracle11Catalog."""
        oracle11 = Oracle11Catalog()

        # Test 11.2
        result = oracle11.for_server_version((11, 2, 0, 4, 0))
        assert isinstance(result, Oracle11Catalog)
        assert type(result) is Oracle11Catalog

    def test_oracle11_catalog_for_server_version_12_or_higher_returns_oracle_catalog(self) -> None:
        """Oracle11Catalog.for_server_version(12+) returns OracleCatalog (supports IDENTITY)."""
        oracle11 = Oracle11Catalog()

        # Test upgrade from 11 to 12
        result = oracle11.for_server_version((12, 0, 0, 0, 0))
        assert isinstance(result, OracleCatalog)
        assert not isinstance(result, Oracle11Catalog)

    def test_oracle_catalog_server_version_sql_query_exists(self) -> None:
        """OracleCatalog.server_version_sql() returns valid SQL for version detection."""
        oracle = OracleCatalog()
        sql = oracle.server_version_sql()

        assert sql is not None
        assert "product_component_version" in sql.lower()
        assert "Oracle Database" in sql
        assert "version" in sql.lower()
        assert "SELECT" in sql

    def test_oracle11_catalog_inherits_server_version_sql(self) -> None:
        """Oracle11Catalog inherits server_version_sql() from OracleCatalog."""
        oracle11 = Oracle11Catalog()
        sql = oracle11.server_version_sql()

        # Should be identical to OracleCatalog's implementation
        oracle = OracleCatalog()
        expected_sql = oracle.server_version_sql()

        assert sql == expected_sql

    def test_oracle11_catalog_has_different_sql_than_oracle_catalog(self) -> None:
        """Oracle11Catalog._sql differs from OracleCatalog._sql (omits IDENTITY)."""
        oracle = OracleCatalog()
        oracle11 = Oracle11Catalog()

        # The _sql dictionaries should be different (11g version omits ALL_TAB_IDENTITY_COLS)
        assert oracle._sql != oracle11._sql

        # Oracle 11g should NOT have IDENTITY-related SQL; OracleCatalog might or might not
        # Just verify that Oracle11Catalog is using _SQL_11G
        from util_bbdd.metadata.oracle.catalog import _SQL, _SQL_11G

        assert oracle._sql is _SQL
        assert oracle11._sql is _SQL_11G

        # The difference is that IDENTITY is in _SQL but Kind.IDENTITY not in _SQL_11G
        from util_bbdd.metadata.model import Kind

        assert Kind.IDENTITY in _SQL
        assert Kind.IDENTITY not in _SQL_11G


class TestOracleVersionParsing:
    """Tests for parsing Oracle version strings into tuples."""

    def test_version_tuple_parsing_11_2_0_4_0(self) -> None:
        """Version string '11.2.0.4.0' parses to tuple (11, 2, 0, 4, 0)."""
        version_str = "11.2.0.4.0"
        version_tuple = tuple(int(x) for x in version_str.split("."))
        assert version_tuple == (11, 2, 0, 4, 0)

    def test_version_tuple_parsing_19_0_0_0_0(self) -> None:
        """Version string '19.0.0.0.0' parses to tuple (19, 0, 0, 0, 0)."""
        version_str = "19.0.0.0.0"
        version_tuple = tuple(int(x) for x in version_str.split("."))
        assert version_tuple == (19, 0, 0, 0, 0)

    def test_version_comparison_11_less_than_12(self) -> None:
        """Version tuple (11, 2, 0, 4, 0) < (12, 0, 0, 0, 0)."""
        v11 = (11, 2, 0, 4, 0)
        v12 = (12, 0, 0, 0, 0)
        assert v11 < v12

    def test_version_comparison_19_greater_than_12(self) -> None:
        """Version tuple (19, 0, 0, 0, 0) > (12, 0, 0, 0, 0)."""
        v12 = (12, 0, 0, 0, 0)
        v19 = (19, 0, 0, 0, 0)
        assert v19 > v12


__all__: list[str] = ["TestOracleVersionDetection", "TestOracleVersionParsing"]
