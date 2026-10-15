"""Unit tests para EngineReadinessAdvisor y validadores por motor."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from util_bbdd.connection._advisory import AdvisoryFinding
from util_bbdd.connection.performance_advisor import EngineReadinessAdvisor

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _levels(findings: list[AdvisoryFinding]) -> list[str]:
    return [f.level for f in findings]


def _params(findings: list[AdvisoryFinding]) -> list[str]:
    return [f.param for f in findings]


def _find(findings: list[AdvisoryFinding], param: str) -> AdvisoryFinding | None:
    return next((f for f in findings if f.param == param), None)


# ─── AdvisoryFinding ──────────────────────────────────────────────────────────


class TestAdvisoryFinding:
    def test_frozen(self) -> None:
        f = AdvisoryFinding(level="OK", param="pool_size", current="10", recommendation="")
        with pytest.raises(AttributeError):
            f.level = "WARNING"  # type: ignore[misc]

    def test_fields(self) -> None:
        f = AdvisoryFinding(level="CRITICAL", param="max_connections", current="5", recommendation="ampliar")
        assert f.level == "CRITICAL"
        assert f.param == "max_connections"
        assert f.current == "5"
        assert f.recommendation == "ampliar"


# ─── PostgreSQL static checks ─────────────────────────────────────────────────


class TestPostgreSQLStaticChecks:
    def setup_method(self) -> None:
        self.advisor = EngineReadinessAdvisor()

    def _check(self, conn_params: dict) -> list[AdvisoryFinding]:
        return self.advisor.check("postgresql", conn_params)

    def test_pool_size_ok(self) -> None:
        findings = self._check({"pool_size": 10})
        f = _find(findings, "pool_size")
        assert f is not None and f.level == "OK"

    def test_pool_size_warning(self) -> None:
        findings = self._check({"pool_size": 2})
        f = _find(findings, "pool_size")
        assert f is not None and f.level == "WARNING"

    def test_pool_size_large_info(self) -> None:
        findings = self._check({"pool_size": 25})
        f = _find(findings, "pool_size")
        assert f is not None and f.level == "INFO"

    def test_keepalives_false_warning(self) -> None:
        findings = self._check({"pool_size": 10, "keepalives": False})
        f = _find(findings, "keepalives")
        assert f is not None and f.level == "WARNING"

    def test_keepalives_true_ok(self) -> None:
        findings = self._check({"pool_size": 10, "keepalives": True})
        f = _find(findings, "keepalives")
        assert f is not None and f.level == "OK"

    def test_sslmode_none_info(self) -> None:
        findings = self._check({"pool_size": 10})
        f = _find(findings, "sslmode")
        assert f is not None and f.level == "INFO"

    def test_sslmode_require_ok(self) -> None:
        findings = self._check({"pool_size": 10, "sslmode": "require"})
        f = _find(findings, "sslmode")
        assert f is not None and f.level == "OK"

    def test_pool_timeout_low_warning(self) -> None:
        findings = self._check({"pool_size": 10, "pool_timeout": 5})
        f = _find(findings, "pool_timeout")
        assert f is not None and f.level == "WARNING"

    def test_findings_sorted_worst_first(self) -> None:
        findings = self._check({"pool_size": 2, "keepalives": False})
        levels = _levels(findings)
        order = {"CRITICAL": 3, "WARNING": 2, "INFO": 1, "OK": 0}
        for i in range(len(levels) - 1):
            assert order[levels[i]] >= order[levels[i + 1]]


# ─── PostgreSQL dynamic checks ────────────────────────────────────────────────


class TestPostgreSQLDynamicChecks:
    def setup_method(self) -> None:
        self.advisor = EngineReadinessAdvisor()

    def _make_conn(self, responses: dict[str, str]) -> MagicMock:
        """Mock de conexión SQLAlchemy que responde SHOW <param> con el valor dado."""
        conn = MagicMock()

        def fake_execute(stmt, *args, **kwargs):
            sql_str = str(stmt)
            for param, value in responses.items():
                if param in sql_str.upper() or param.lower() in sql_str.lower():
                    row_mock = MagicMock()
                    row_mock.__getitem__ = lambda self, idx, v=value: v
                    row_mock[0] = value
                    result_mock = MagicMock()
                    result_mock.fetchone.return_value = (value,)
                    return result_mock
            result_mock = MagicMock()
            result_mock.fetchone.return_value = None
            return result_mock

        conn.execute.side_effect = fake_execute
        return conn

    def test_work_mem_low_warning(self) -> None:
        conn = self._make_conn({"work_mem": "4MB"})
        findings = self.advisor.check("postgresql", {"pool_size": 10}, connection=conn)
        f = _find(findings, "work_mem")
        assert f is not None and f.level == "WARNING"

    def test_work_mem_medium_info(self) -> None:
        conn = self._make_conn({"work_mem": "32MB"})
        findings = self.advisor.check("postgresql", {"pool_size": 10}, connection=conn)
        f = _find(findings, "work_mem")
        assert f is not None and f.level == "INFO"

    def test_work_mem_high_ok(self) -> None:
        conn = self._make_conn({"work_mem": "128MB"})
        findings = self.advisor.check("postgresql", {"pool_size": 10}, connection=conn)
        f = _find(findings, "work_mem")
        assert f is not None and f.level == "OK"

    def test_max_connections_critical(self) -> None:
        conn = self._make_conn({"max_connections": "10"})
        findings = self.advisor.check("postgresql", {"pool_size": 8, "max_overflow": 5}, connection=conn)
        f = _find(findings, "max_connections")
        assert f is not None and f.level == "CRITICAL"

    def test_max_connections_warning_over_80pct(self) -> None:
        conn = self._make_conn({"max_connections": "100"})
        findings = self.advisor.check("postgresql", {"pool_size": 70, "max_overflow": 15}, connection=conn)
        f = _find(findings, "max_connections")
        assert f is not None and f.level == "WARNING"

    def test_max_connections_ok(self) -> None:
        conn = self._make_conn({"max_connections": "200"})
        findings = self.advisor.check("postgresql", {"pool_size": 10, "max_overflow": 5}, connection=conn)
        f = _find(findings, "max_connections")
        assert f is not None and f.level == "OK"

    def test_dynamic_exception_does_not_raise(self) -> None:
        conn = MagicMock()
        conn.execute.side_effect = RuntimeError("conn failed")
        # No debe propagar — devuelve solo checks estáticos
        findings = self.advisor.check("postgresql", {"pool_size": 10}, connection=conn)
        assert isinstance(findings, list)

    def test_shared_buffers_low_warning(self) -> None:
        conn = self._make_conn({"shared_buffers": "128MB"})
        findings = self.advisor.check("postgresql", {"pool_size": 10}, connection=conn)
        f = _find(findings, "shared_buffers")
        assert f is not None and f.level == "WARNING"

    def test_shared_buffers_medium_info(self) -> None:
        conn = self._make_conn({"shared_buffers": "512MB"})
        findings = self.advisor.check("postgresql", {"pool_size": 10}, connection=conn)
        f = _find(findings, "shared_buffers")
        assert f is not None and f.level == "INFO"

    def test_shared_buffers_high_ok(self) -> None:
        conn = self._make_conn({"shared_buffers": "2GB"})
        findings = self.advisor.check("postgresql", {"pool_size": 10}, connection=conn)
        f = _find(findings, "shared_buffers")
        assert f is not None and f.level == "OK"

    def test_effective_cache_size_low_warning(self) -> None:
        conn = self._make_conn({"effective_cache_size": "256MB"})
        findings = self.advisor.check("postgresql", {"pool_size": 10}, connection=conn)
        f = _find(findings, "effective_cache_size")
        assert f is not None and f.level == "WARNING"

    def test_effective_cache_size_medium_info(self) -> None:
        conn = self._make_conn({"effective_cache_size": "2GB"})
        findings = self.advisor.check("postgresql", {"pool_size": 10}, connection=conn)
        f = _find(findings, "effective_cache_size")
        assert f is not None and f.level == "INFO"

    def test_effective_cache_size_high_ok(self) -> None:
        conn = self._make_conn({"effective_cache_size": "8GB"})
        findings = self.advisor.check("postgresql", {"pool_size": 10}, connection=conn)
        f = _find(findings, "effective_cache_size")
        assert f is not None and f.level == "OK"

    def test_random_page_cost_high_info(self) -> None:
        conn = self._make_conn({"random_page_cost": "4.0"})
        findings = self.advisor.check("postgresql", {"pool_size": 10}, connection=conn)
        f = _find(findings, "random_page_cost")
        assert f is not None and f.level == "INFO"

    def test_random_page_cost_low_ok(self) -> None:
        conn = self._make_conn({"random_page_cost": "1.1"})
        findings = self.advisor.check("postgresql", {"pool_size": 10}, connection=conn)
        f = _find(findings, "random_page_cost")
        assert f is not None and f.level == "OK"


# ─── SQLite static checks ─────────────────────────────────────────────────────


class TestSQLiteStaticChecks:
    def setup_method(self) -> None:
        self.advisor = EngineReadinessAdvisor()

    def _check(self, conn_params: dict) -> list[AdvisoryFinding]:
        return self.advisor.check("sqlite", conn_params)

    def test_memory_db_info(self) -> None:
        findings = self._check({"database": ":memory:"})
        f = _find(findings, "database")
        assert f is not None and f.level == "INFO"

    def test_file_db_ok(self) -> None:
        findings = self._check({"database": "mydb.sqlite"})
        f = _find(findings, "database")
        assert f is not None and f.level == "OK"

    def test_timeout_low_warning(self) -> None:
        findings = self._check({"database": "db.sqlite", "timeout": 2.0})
        f = _find(findings, "timeout")
        assert f is not None and f.level == "WARNING"

    def test_timeout_ok(self) -> None:
        findings = self._check({"database": "db.sqlite", "timeout": 10.0})
        f = _find(findings, "timeout")
        assert f is not None and f.level == "OK"


# ─── SQLite dynamic checks ────────────────────────────────────────────────────


class TestSQLiteDynamicChecks:
    def setup_method(self) -> None:
        self.advisor = EngineReadinessAdvisor()

    def _make_conn(self, pragmas: dict[str, object]) -> MagicMock:
        conn = MagicMock()

        def fake_execute(stmt, *args, **kwargs):
            sql_str = str(stmt).lower()
            for pragma, value in pragmas.items():
                if f"pragma {pragma}" in sql_str:
                    result = MagicMock()
                    result.fetchone.return_value = (value,)
                    return result
            result = MagicMock()
            result.fetchone.return_value = None
            return result

        conn.execute.side_effect = fake_execute
        return conn

    def test_journal_mode_delete_warning(self) -> None:
        conn = self._make_conn({"journal_mode": "delete"})
        findings = self.advisor.check("sqlite", {"database": "test.db"}, connection=conn)
        f = _find(findings, "journal_mode")
        assert f is not None and f.level == "WARNING"

    def test_journal_mode_wal_ok(self) -> None:
        conn = self._make_conn({"journal_mode": "wal"})
        findings = self.advisor.check("sqlite", {"database": "test.db"}, connection=conn)
        f = _find(findings, "journal_mode")
        assert f is not None and f.level == "OK"

    def test_synchronous_full_info(self) -> None:
        conn = self._make_conn({"journal_mode": "wal", "synchronous": 2})
        findings = self.advisor.check("sqlite", {"database": "test.db"}, connection=conn)
        f = _find(findings, "synchronous")
        assert f is not None and f.level == "INFO"

    def test_memory_db_skips_wal_check(self) -> None:
        conn = self._make_conn({"journal_mode": "memory"})
        findings = self.advisor.check("sqlite", {"database": ":memory:"}, connection=conn)
        # En :memory: no se emite hallazgo de journal_mode
        assert _find(findings, "journal_mode") is None


# ─── SQL Server static checks ─────────────────────────────────────────────────


class TestSQLServerStaticChecks:
    def setup_method(self) -> None:
        self.advisor = EngineReadinessAdvisor()

    def _check(self, conn_params: dict) -> list[AdvisoryFinding]:
        return self.advisor.check("mssql", conn_params)

    def test_use_mars_false_warning(self) -> None:
        findings = self._check({"use_mars": False, "pool_size": 10})
        f = _find(findings, "use_mars")
        assert f is not None and f.level == "WARNING"

    def test_use_mars_true_ok(self) -> None:
        findings = self._check({"use_mars": True, "pool_size": 10})
        f = _find(findings, "use_mars")
        assert f is not None and f.level == "OK"

    def test_pool_size_low_warning(self) -> None:
        findings = self._check({"pool_size": 2})
        f = _find(findings, "pool_size")
        assert f is not None and f.level == "WARNING"

    def test_pymssql_info(self) -> None:
        findings = self._check({"pool_size": 10, "sql_server_driver": "pymssql"})
        f = _find(findings, "sql_server_driver")
        assert f is not None and f.level == "INFO"

    def test_pyodbc_ok(self) -> None:
        findings = self._check({"pool_size": 10, "sql_server_driver": "pyodbc"})
        f = _find(findings, "sql_server_driver")
        assert f is not None and f.level == "OK"

    def test_max_overflow_low_warning(self) -> None:
        findings = self._check({"pool_size": 10, "max_overflow": 2})
        f = _find(findings, "max_overflow")
        assert f is not None and f.level == "WARNING"


# ─── Oracle static checks ─────────────────────────────────────────────────────


class TestOracleStaticChecks:
    def setup_method(self) -> None:
        self.advisor = EngineReadinessAdvisor()

    def _check(self, conn_params: dict) -> list[AdvisoryFinding]:
        return self.advisor.check("oracle", conn_params)

    def test_pool_size_low_warning(self) -> None:
        findings = self._check({"pool_size": 2})
        f = _find(findings, "pool_size")
        assert f is not None and f.level == "WARNING"

    def test_pool_size_ok(self) -> None:
        findings = self._check({"pool_size": 10})
        f = _find(findings, "pool_size")
        assert f is not None and f.level == "OK"

    def test_max_lifetime_low_warning(self) -> None:
        findings = self._check({"pool_size": 10, "max_lifetime": 100})
        f = _find(findings, "max_lifetime")
        assert f is not None and f.level == "WARNING"

    def test_max_lifetime_ok(self) -> None:
        findings = self._check({"pool_size": 10, "max_lifetime": 3600})
        f = _find(findings, "max_lifetime")
        assert f is not None and f.level == "OK"

    def test_arraysize_info_always_present(self) -> None:
        findings = self._check({"pool_size": 10})
        f = _find(findings, "arraysize/prefetchrows")
        assert f is not None and f.level == "INFO"


# ─── MySQL/MariaDB static checks ──────────────────────────────────────────────


class TestMySQLStaticChecks:
    def setup_method(self) -> None:
        self.advisor = EngineReadinessAdvisor()

    def _check(self, engine: str, conn_params: dict) -> list[AdvisoryFinding]:
        return self.advisor.check(engine, conn_params)

    @pytest.mark.parametrize("engine", ["mysql", "mariadb"])
    def test_autocommit_warning(self, engine: str) -> None:
        findings = self._check(engine, {"autocommit": True, "pool_size": 10})
        f = _find(findings, "autocommit")
        assert f is not None and f.level == "WARNING"

    @pytest.mark.parametrize("engine", ["mysql", "mariadb"])
    def test_autocommit_ok(self, engine: str) -> None:
        findings = self._check(engine, {"autocommit": False, "pool_size": 10})
        f = _find(findings, "autocommit")
        assert f is not None and f.level == "OK"

    @pytest.mark.parametrize("engine", ["mysql", "mariadb"])
    def test_write_timeout_low_warning(self, engine: str) -> None:
        findings = self._check(engine, {"pool_size": 10, "write_timeout": 10})
        f = _find(findings, "write_timeout")
        assert f is not None and f.level == "WARNING"

    @pytest.mark.parametrize("engine", ["mysql", "mariadb"])
    def test_pool_size_low_warning(self, engine: str) -> None:
        findings = self._check(engine, {"pool_size": 1})
        f = _find(findings, "pool_size")
        assert f is not None and f.level == "WARNING"


# ─── EngineReadinessAdvisor.report ────────────────────────────────────────────


class TestEngineReadinessAdvisorReport:
    def setup_method(self) -> None:
        self.advisor = EngineReadinessAdvisor()

    def test_report_emits_single_log_call_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        with caplog.at_level(logging.WARNING, logger="util_bbdd.connection.performance_advisor"):
            self.advisor.report("postgresql", {"pool_size": 2, "keepalives": False})

        warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warning_records) == 1

    def test_report_emits_single_log_call_info(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        with caplog.at_level(logging.INFO, logger="util_bbdd.connection.performance_advisor"):
            self.advisor.report("postgresql", {"pool_size": 10, "keepalives": True, "sslmode": "require"})

        info_records = [r for r in caplog.records if r.levelname in ("INFO", "WARNING")]
        assert len(info_records) == 1

    def test_report_block_contains_engine_name(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        with caplog.at_level(logging.INFO, logger="util_bbdd.connection.performance_advisor"):
            self.advisor.report("sqlite", {"database": ":memory:"})

        assert any("sqlite" in r.message for r in caplog.records)

    def test_report_unknown_engine_no_crash(self) -> None:
        self.advisor.report("hsqldb", {"pool_size": 3})

    def test_report_with_connection_exception_no_crash(self) -> None:
        conn = MagicMock()
        conn.execute.side_effect = Exception("boom")
        self.advisor.report("postgresql", {"pool_size": 10}, connection=conn)

    def test_check_returns_list(self) -> None:
        findings = self.advisor.check("oracle", {"pool_size": 10})
        assert isinstance(findings, list)
        assert all(isinstance(f, AdvisoryFinding) for f in findings)


# ─── MySQL/MariaDB OK findings (F-05/F-06) ────────────────────────────────────


class TestMySQLOKFindings:
    def setup_method(self) -> None:
        self.advisor = EngineReadinessAdvisor()

    @pytest.mark.parametrize("engine", ["mysql", "mariadb"])
    def test_write_timeout_ok(self, engine: str) -> None:
        findings = self.advisor.check(engine, {"pool_size": 10, "write_timeout": 60})
        f = _find(findings, "write_timeout")
        assert f is not None and f.level == "OK"

    @pytest.mark.parametrize("engine", ["mysql", "mariadb"])
    def test_read_timeout_ok(self, engine: str) -> None:
        findings = self.advisor.check(engine, {"pool_size": 10, "read_timeout": 30})
        f = _find(findings, "read_timeout")
        assert f is not None and f.level == "OK"

    @pytest.mark.parametrize("engine", ["mysql", "mariadb"])
    def test_pool_timeout_low_warning(self, engine: str) -> None:
        findings = self.advisor.check(engine, {"pool_size": 10, "pool_timeout": 5})
        f = _find(findings, "pool_timeout")
        assert f is not None and f.level == "WARNING"


# ─── Oracle dynamic checks (F-08) ─────────────────────────────────────────────


class TestOracleDynamicChecks:
    def setup_method(self) -> None:
        self.advisor = EngineReadinessAdvisor()

    def _make_conn(self, v_params: dict[str, str], *, has_permission: bool = True) -> MagicMock:
        conn = MagicMock()

        def fake_execute(stmt, params=None, **kwargs):
            sql_str = str(stmt).lower()
            if "rownum = 1" in sql_str:
                if not has_permission:
                    from sqlalchemy.exc import SQLAlchemyError

                    raise SQLAlchemyError("permission denied")
                result = MagicMock()
                result.fetchone.return_value = (1,)
                return result
            if "v$parameter" in sql_str and params and "n" in params:
                name = params["n"]
                value = v_params.get(name)
                result = MagicMock()
                result.fetchone.return_value = (value,) if value is not None else None
                return result
            result = MagicMock()
            result.fetchone.return_value = None
            return result

        conn.execute.side_effect = fake_execute
        return conn

    def test_no_permission_emits_info(self) -> None:
        conn = self._make_conn({}, has_permission=False)
        findings = self.advisor.check("oracle", {"pool_size": 10}, connection=conn)
        f = _find(findings, "v$parameter")
        assert f is not None and f.level == "INFO"

    def test_pga_low_warning(self) -> None:
        conn = self._make_conn({"pga_aggregate_target": str(64 * 1_048_576)})
        findings = self.advisor.check("oracle", {"pool_size": 10}, connection=conn)
        f = _find(findings, "pga_aggregate_target")
        assert f is not None and f.level == "WARNING"

    def test_pga_ok(self) -> None:
        conn = self._make_conn({"pga_aggregate_target": str(512 * 1_048_576)})
        findings = self.advisor.check("oracle", {"pool_size": 10}, connection=conn)
        f = _find(findings, "pga_aggregate_target")
        assert f is not None and f.level == "OK"

    def test_cursor_sharing_force_warning(self) -> None:
        conn = self._make_conn({"cursor_sharing": "FORCE"})
        findings = self.advisor.check("oracle", {"pool_size": 10}, connection=conn)
        f = _find(findings, "cursor_sharing")
        assert f is not None and f.level == "WARNING"

    def test_exception_does_not_raise(self) -> None:
        conn = MagicMock()
        conn.execute.side_effect = RuntimeError("boom")
        findings = self.advisor.check("oracle", {"pool_size": 10}, connection=conn)
        assert isinstance(findings, list)


# ─── SQL Server dynamic checks (F-08) ─────────────────────────────────────────


class TestSQLServerDynamicChecks:
    def setup_method(self) -> None:
        self.advisor = EngineReadinessAdvisor()

    def _make_conn(self, configs: dict[str, object] = None, recovery: int | None = None) -> MagicMock:
        configs = configs or {}
        conn = MagicMock()

        def fake_execute(stmt, params=None, **kwargs):
            sql_str = str(stmt).lower()
            if "sys.configurations" in sql_str and params and "n" in params:
                value = configs.get(params["n"])
                result = MagicMock()
                result.fetchone.return_value = (value,) if value is not None else None
                return result
            if "sys.databases" in sql_str:
                result = MagicMock()
                result.fetchone.return_value = (recovery,) if recovery is not None else None
                return result
            result = MagicMock()
            result.fetchone.return_value = None
            return result

        conn.execute.side_effect = fake_execute
        return conn

    def test_recovery_full_info(self) -> None:
        conn = self._make_conn(recovery=1)
        findings = self.advisor.check("mssql", {"pool_size": 10, "database": "mydb"}, connection=conn)
        f = _find(findings, "recovery_model")
        assert f is not None and f.level == "INFO"

    def test_recovery_simple_ok(self) -> None:
        conn = self._make_conn(recovery=3)
        findings = self.advisor.check("mssql", {"pool_size": 10, "database": "mydb"}, connection=conn)
        f = _find(findings, "recovery_model")
        assert f is not None and f.level == "OK"

    def test_fill_factor_low_info(self) -> None:
        conn = self._make_conn({"fill factor (%)": 50})
        findings = self.advisor.check("mssql", {"pool_size": 10, "database": "mydb"}, connection=conn)
        f = _find(findings, "fill_factor")
        assert f is not None and f.level == "INFO"

    def test_exception_does_not_raise(self) -> None:
        conn = MagicMock()
        conn.execute.side_effect = RuntimeError("boom")
        findings = self.advisor.check("mssql", {"pool_size": 10}, connection=conn)
        assert isinstance(findings, list)

    def test_maxdop_zero_info(self) -> None:
        conn = self._make_conn({"max degree of parallelism": 0})
        findings = self.advisor.check("mssql", {"pool_size": 10}, connection=conn)
        f = _find(findings, "max_degree_of_parallelism")
        assert f is not None and f.level == "INFO"
        # Hotfix A-04 (audit-code 2026-10-15b): recomendaba «SET MAXDOP», que no existe como sentencia.
        assert "sp_configure 'max degree of parallelism'" in f.recommendation
        assert "con SET MAXDOP" not in f.recommendation

    def test_maxdop_medium_ok(self) -> None:
        conn = self._make_conn({"max degree of parallelism": 4})
        findings = self.advisor.check("mssql", {"pool_size": 10}, connection=conn)
        f = _find(findings, "max_degree_of_parallelism")
        assert f is not None and f.level == "OK"

    def test_maxdop_high_info(self) -> None:
        conn = self._make_conn({"max degree of parallelism": 16})
        findings = self.advisor.check("mssql", {"pool_size": 10}, connection=conn)
        f = _find(findings, "max_degree_of_parallelism")
        assert f is not None and f.level == "INFO"

    def test_cost_threshold_low_info(self) -> None:
        conn = self._make_conn({"cost threshold for parallelism": 5})
        findings = self.advisor.check("mssql", {"pool_size": 10}, connection=conn)
        f = _find(findings, "cost_threshold_for_parallelism")
        assert f is not None and f.level == "INFO"

    def test_cost_threshold_medium_ok(self) -> None:
        conn = self._make_conn({"cost threshold for parallelism": 50})
        findings = self.advisor.check("mssql", {"pool_size": 10}, connection=conn)
        f = _find(findings, "cost_threshold_for_parallelism")
        assert f is not None and f.level == "OK"


# ─── Oracle dynamic checks (F-08) — checks de v$parameter ───────────────────────


class TestOracleDynamicChecksPhase3:
    def setup_method(self) -> None:
        self.advisor = EngineReadinessAdvisor()

    def _make_oracle_conn(self, params: dict[str, int]) -> MagicMock:
        conn = MagicMock()

        def fake_execute(stmt, params_dict=None, **kwargs):
            sql_str = str(stmt).lower()
            if "v$parameter" in sql_str and params_dict and "n" in params_dict:
                param_name = params_dict["n"]
                value = params[param_name] if param_name in params else None
                result = MagicMock()
                result.fetchone.return_value = (value,) if value is not None else None
                return result
            result = MagicMock()
            result.fetchone.return_value = None
            return result

        conn.execute.side_effect = fake_execute
        return conn

    def test_undo_retention_low_info(self) -> None:
        conn = self._make_oracle_conn({"undo_retention": 300})
        findings = self.advisor.check("oracle", {"pool_size": 10}, connection=conn)
        f = _find(findings, "undo_retention")
        assert f is not None and f.level == "INFO"

    def test_undo_retention_high_ok(self) -> None:
        conn = self._make_oracle_conn({"undo_retention": 3600})
        findings = self.advisor.check("oracle", {"pool_size": 10}, connection=conn)
        f = _find(findings, "undo_retention")
        assert f is not None and f.level == "OK"


# ─── MySQL dynamic checks (F-08) — delegar en MySQLVariableValidator ──────────


class TestMySQLDynamicChecks:
    def setup_method(self) -> None:
        self.advisor = EngineReadinessAdvisor()

    def _make_mysql_conn(self, variables: dict[str, int]) -> MagicMock:
        conn = MagicMock()

        def fake_execute(stmt, *args, **kwargs):
            sql_str = str(stmt).lower()
            for var_name, value in variables.items():
                if var_name in sql_str:
                    result = MagicMock()
                    result.fetchall.return_value = [(var_name, str(value))]
                    return result
            result = MagicMock()
            result.fetchall.return_value = []
            return result

        conn.execute.side_effect = fake_execute
        return conn

    @pytest.mark.parametrize("engine", ["mysql", "mariadb"])
    def test_innodb_buffer_pool_low_warning(self, engine: str) -> None:
        conn = self._make_mysql_conn({"innodb_buffer_pool_size": 64 * 1_048_576})
        findings = self.advisor.check(engine, {"pool_size": 10}, connection=conn)
        f = _find(findings, "innodb_buffer_pool_size")
        assert f is not None and f.level == "WARNING"

    @pytest.mark.parametrize("engine", ["mysql", "mariadb"])
    def test_innodb_buffer_pool_ok(self, engine: str) -> None:
        conn = self._make_mysql_conn({"innodb_buffer_pool_size": 2 * 1_073_741_824})
        findings = self.advisor.check(engine, {"pool_size": 10}, connection=conn)
        f = _find(findings, "innodb_buffer_pool_size")
        assert f is not None and f.level == "OK"

    @pytest.mark.parametrize("engine", ["mysql", "mariadb"])
    def test_innodb_flush_log_zero_critical(self, engine: str) -> None:
        conn = self._make_mysql_conn({"innodb_flush_log_at_trx_commit": 0})
        findings = self.advisor.check(engine, {"pool_size": 10}, connection=conn)
        f = _find(findings, "innodb_flush_log_at_trx_commit")
        assert f is not None and f.level == "CRITICAL"

    @pytest.mark.parametrize("engine", ["mysql", "mariadb"])
    def test_innodb_flush_log_one_warning(self, engine: str) -> None:
        conn = self._make_mysql_conn({"innodb_flush_log_at_trx_commit": 1})
        findings = self.advisor.check(engine, {"pool_size": 10}, connection=conn)
        f = _find(findings, "innodb_flush_log_at_trx_commit")
        assert f is not None and f.level == "WARNING"

    @pytest.mark.parametrize("engine", ["mysql", "mariadb"])
    def test_innodb_flush_log_two_ok(self, engine: str) -> None:
        conn = self._make_mysql_conn({"innodb_flush_log_at_trx_commit": 2})
        findings = self.advisor.check(engine, {"pool_size": 10}, connection=conn)
        f = _find(findings, "innodb_flush_log_at_trx_commit")
        assert f is not None and f.level == "OK"

    @pytest.mark.parametrize("engine", ["mysql", "mariadb"])
    def test_innodb_log_file_size_low_info(self, engine: str) -> None:
        conn = self._make_mysql_conn({"innodb_log_file_size": 256 * 1_048_576})
        findings = self.advisor.check(engine, {"pool_size": 10}, connection=conn)
        f = _find(findings, "innodb_log_file_size")
        assert f is not None and f.level == "INFO"
        # Hotfix A-04: en MySQL 8.0.30+ lo dinámico es innodb_redo_log_capacity, no innodb_log_file_size.
        assert "innodb_redo_log_capacity" in f.recommendation
        assert "dinámico en MySQL 8.0.30+" not in f.recommendation

    @pytest.mark.parametrize("engine", ["mysql", "mariadb"])
    def test_innodb_log_file_size_high_ok(self, engine: str) -> None:
        conn = self._make_mysql_conn({"innodb_log_file_size": 1 * 1_073_741_824})
        findings = self.advisor.check(engine, {"pool_size": 10}, connection=conn)
        f = _find(findings, "innodb_log_file_size")
        assert f is not None and f.level == "OK"

    @pytest.mark.parametrize("engine", ["mysql", "mariadb"])
    def test_innodb_write_io_threads_low_info(self, engine: str) -> None:
        conn = self._make_mysql_conn({"innodb_write_io_threads": 2})
        findings = self.advisor.check(engine, {"pool_size": 10}, connection=conn)
        f = _find(findings, "innodb_write_io_threads")
        assert f is not None and f.level == "INFO"
        # Hotfix A-04: no es dinámica en MySQL; SET GLOBAL falla con «read only variable».
        assert "SET GLOBAL" not in f.recommendation
        assert "my.cnf" in f.recommendation

    @pytest.mark.parametrize("engine", ["mysql", "mariadb"])
    def test_innodb_write_io_threads_high_ok(self, engine: str) -> None:
        conn = self._make_mysql_conn({"innodb_write_io_threads": 8})
        findings = self.advisor.check(engine, {"pool_size": 10}, connection=conn)
        f = _find(findings, "innodb_write_io_threads")
        assert f is not None and f.level == "OK"

    @pytest.mark.parametrize("engine", ["mysql", "mariadb"])
    def test_exception_does_not_raise(self, engine: str) -> None:
        conn = MagicMock()
        conn.execute.side_effect = RuntimeError("boom")
        findings = self.advisor.check(engine, {"pool_size": 10}, connection=conn)
        assert isinstance(findings, list)


# ─── F-09: exception-does-not-raise cubre todos los motores ──────────────────


class TestExceptionResilienceAllEngines:
    def setup_method(self) -> None:
        self.advisor = EngineReadinessAdvisor()

    @pytest.mark.parametrize("engine", ["postgresql", "sqlite", "mssql", "oracle", "mysql", "mariadb"])
    def test_broken_connection_never_raises(self, engine: str) -> None:
        conn = MagicMock()
        conn.execute.side_effect = Exception("boom")
        findings = self.advisor.check(engine, {"pool_size": 10, "database": "test"}, connection=conn)
        assert isinstance(findings, list)


# ─── Hotfix v0.40.1 (H1): sin valores por defecto presentados como leídos ─────


class TestMySQLStaticChecksOnlyKnownValues:
    """``report_once`` solo conoce host/port/database y el pool del Engine: ``autocommit`` y los timeouts del driver no.

    Antes se rellenaban con los valores por defecto (``False``, 60 s, 30 s) y el informe los daba por buenos aunque la
    conexión usara otros (p. ej. ``write_timeout=5``). Ahora un parámetro ausente no se informa.
    """

    @pytest.mark.parametrize("engine", ["mysql", "mariadb"])
    def test_absent_params_are_not_reported(self, engine: str) -> None:
        findings = EngineReadinessAdvisor().check(engine, {"host": "db", "port": 3306, "database": "app"})
        reported = {f.param for f in findings}
        assert reported.isdisjoint({"autocommit", "pool_size", "write_timeout", "read_timeout", "pool_timeout"})

    def test_engine_params_without_driver_timeouts_are_not_reported(self) -> None:
        from sqlalchemy import create_engine

        engine = create_engine("mysql+pymysql://u:p@db:3306/app", pool_size=7)
        try:
            conn_params = EngineReadinessAdvisor._conn_params_from_engine(engine)
            reported = {f.param: f.current for f in EngineReadinessAdvisor().check("mysql", conn_params)}
        finally:
            engine.dispose()
        assert reported == {"pool_size": "7"}


# ─── Validación de parámetros: casting de int/bool correcto ──────────────────


class TestParameterValidationFixes:
    """Tests para verificar que las correcciones de casting int/bool funcionan correctamente."""

    def setup_method(self) -> None:
        self.advisor = EngineReadinessAdvisor()

    def test_autocommit_string_false_ok(self) -> None:
        """autocommit='false' string debe interpretarse como False (OK), no True (WARNING)."""
        findings = self.advisor.check("mysql", {"autocommit": "false"})
        f = _find(findings, "autocommit")
        assert f is not None and f.level == "OK"

    def test_autocommit_string_true_warning(self) -> None:
        """autocommit='true' string debe interpretarse como True (WARNING)."""
        findings = self.advisor.check("mysql", {"autocommit": "true"})
        f = _find(findings, "autocommit")
        assert f is not None and f.level == "WARNING"

    def test_autocommit_string_1_warning(self) -> None:
        """autocommit='1' string debe interpretarse como True (WARNING)."""
        findings = self.advisor.check("mysql", {"autocommit": "1"})
        f = _find(findings, "autocommit")
        assert f is not None and f.level == "WARNING"

    def test_autocommit_string_0_ok(self) -> None:
        """autocommit='0' string debe interpretarse como False (OK)."""
        findings = self.advisor.check("mysql", {"autocommit": "0"})
        f = _find(findings, "autocommit")
        assert f is not None and f.level == "OK"

    def test_autocommit_invalid_critical(self) -> None:
        """autocommit con valor inválido debe reportar CRITICAL, no crash."""
        findings = self.advisor.check("mysql", {"autocommit": "invalid_value"})
        f = _find(findings, "autocommit")
        assert f is not None and f.level == "CRITICAL"

    def test_pool_size_non_integer_critical(self) -> None:
        """pool_size no-numérico debe reportar CRITICAL, no crash."""
        findings = self.advisor.check("mysql", {"pool_size": "not_an_integer"})
        f = _find(findings, "pool_size")
        assert f is not None and f.level == "CRITICAL"

    def test_write_timeout_non_integer_critical(self) -> None:
        """write_timeout no-numérico debe reportar CRITICAL, no crash."""
        findings = self.advisor.check("mysql", {"write_timeout": "bad_value"})
        f = _find(findings, "write_timeout")
        assert f is not None and f.level == "CRITICAL"

    def test_pool_timeout_non_integer_critical(self) -> None:
        """pool_timeout no-numérico debe reportar CRITICAL, no crash."""
        findings = self.advisor.check("mysql", {"pool_timeout": "invalid"})
        # pool_timeout invalido interrumpe checks, retorna sin más hallazgos
        critical_findings = [f for f in findings if f.level == "CRITICAL"]
        assert len(critical_findings) > 0

    def test_credentials_redacted_in_log(self, caplog: pytest.LogCaptureFixture) -> None:
        """Las credenciales no deben filtrarse en logs."""
        import logging

        with caplog.at_level(logging.INFO, logger="util_bbdd.connection.performance_advisor"):
            self.advisor.report(
                "mysql",
                {
                    "host": "localhost",
                    "port": 3306,
                    "password": "secret_password_123",
                    "pool_size": 5,
                },
            )
        # Verificar que la contraseña no aparece en el log
        log_text = caplog.text
        assert "secret_password_123" not in log_text
