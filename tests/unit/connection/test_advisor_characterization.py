"""Caracterización de ``EngineReadinessAdvisor.check``: la salida de todos los motores fijada en un fichero dorado.

F0 de T-06 (sesión ``2026-10-16-refactor-advisor-strategy``): protege el refactor de los validadores (Strategy) frente a
cambios en los hallazgos (nivel, parámetro, valor, recomendación y orden). Una matriz de motores × ``conn_params`` ×
respuestas del servidor (conexión falsa que responde según el SQL de cada validador) se compara con
``data/advisor_characterization.json``.

Un cambio de comportamiento **deliberado** (un ``fix:``) regenera el fichero y se revisa el diff:

    UTIL_BBDD_REGEN_ADVISOR_GOLDEN=1 python -m pytest tests/unit/connection/test_advisor_characterization.py
"""

from __future__ import annotations

import json
import logging
import os
import re

from pathlib import Path
from typing import Any

import pytest

from sqlalchemy.exc import OperationalError

from util_bbdd.connection.performance_advisor import EngineReadinessAdvisor

pytestmark = pytest.mark.unit

GOLDEN: Path = Path(__file__).parent / "data" / "advisor_characterization.json"
REGENERATE: bool = os.environ.get("UTIL_BBDD_REGEN_ADVISOR_GOLDEN") == "1"

ENGINES: tuple[str, ...] = ("mysql", "mariadb", "postgresql", "sqlserver", "mssql", "oracle", "sqlite", "hsqldb")

#: ``conn_params`` comunes a todos los motores (cada validador solo lee las claves que conoce).
PARAMS: dict[str, dict[str, Any]] = {
    "vacio": {},
    "buenos": {
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
        "write_timeout": 60,
        "read_timeout": 60,
        "autocommit": False,
        "keepalives": True,
        "sslmode": "require",
        "use_mars": False,
        "sql_server_driver": "pyodbc",
        "max_lifetime": 1800,
        "database": "datos.db",
        "timeout": 30,
    },
    "bajos": {
        "pool_size": 1,
        "max_overflow": 0,
        "pool_timeout": 5,
        "write_timeout": 10,
        "read_timeout": 10,
        "autocommit": True,
        "keepalives": False,
        "sslmode": "disable",
        "use_mars": True,
        "sql_server_driver": "pymssql",
        "max_lifetime": 100_000,
        "database": "datos.db",
        "timeout": 1,
    },
    "texto": {
        "pool_size": "10",
        "max_overflow": "20",
        "pool_timeout": "30",
        "write_timeout": "60",
        "read_timeout": "60",
        "autocommit": "false",
        "keepalives": "false",
        "use_mars": "false",
        "max_lifetime": "1800",
        "database": "datos.db",
        "timeout": "30",
    },
    "invalidos": {
        "pool_size": "abc",
        "max_overflow": "x",
        "pool_timeout": "lento",
        "write_timeout": "y",
        "read_timeout": "z",
        "autocommit": "quizá",
        "keepalives": "talvez",
        "use_mars": "puede",
        "max_lifetime": "nunca",
        "database": "datos.db",
        "timeout": "w",
    },
}

#: Respuestas del servidor por motor: nombre del parámetro → valor. ``None`` = sin conexión (solo estáticos).
SERVER: dict[str, dict[str, Any]] = {
    "tipicos": {
        # MySQL/MariaDB (SHOW VARIABLES)
        "max_allowed_packet": 67_108_864,
        "innodb_buffer_pool_size": 134_217_728,
        "innodb_flush_log_at_trx_commit": 1,
        "innodb_log_file_size": 50_331_648,
        "innodb_write_io_threads": 4,
        # PostgreSQL (SHOW)
        "work_mem": "4MB",
        "maintenance_work_mem": "64MB",
        "synchronous_commit": "on",
        "max_connections": "100",
        "wal_level": "replica",
        "shared_buffers": "128MB",
        "effective_cache_size": "4GB",
        "random_page_cost": "4",
        # SQL Server (sys.configurations, sys.databases)
        "max degree of parallelism": 0,
        "cost threshold for parallelism": 5,
        "fill factor (%)": 0,
        "__recovery_model__": 1,
        # Oracle (V$PARAMETER)
        "pga_aggregate_target": "209715200",
        "sga_target": "838860800",
        "cursor_sharing": "EXACT",
        "db_writer_processes": "1",
        "undo_retention": "900",
        # SQLite (PRAGMA)
        "journal_mode": "delete",
        "synchronous": 2,
        "cache_size": -2000,
        "temp_store": 0,
    },
    "optimos": {
        "max_allowed_packet": 1_073_741_824,
        "innodb_buffer_pool_size": 8_589_934_592,
        "innodb_flush_log_at_trx_commit": 2,
        "innodb_log_file_size": 2_147_483_648,
        "innodb_write_io_threads": 16,
        "work_mem": "64MB",
        "maintenance_work_mem": "1GB",
        "synchronous_commit": "off",
        "max_connections": "500",
        "wal_level": "minimal",
        "shared_buffers": "2GB",
        "effective_cache_size": "8GB",
        "random_page_cost": "1.1",
        "max degree of parallelism": 4,
        "cost threshold for parallelism": 50,
        "fill factor (%)": 100,
        "__recovery_model__": 3,
        "pga_aggregate_target": "2147483648",
        "sga_target": "8589934592",
        "cursor_sharing": "FORCE",
        "db_writer_processes": "4",
        "undo_retention": "3600",
        "journal_mode": "wal",
        "synchronous": 1,
        "cache_size": -65536,
        "temp_store": 2,
    },
    "bajos": {
        "max_allowed_packet": 4_194_304,
        "innodb_buffer_pool_size": 8_388_608,
        "innodb_flush_log_at_trx_commit": 0,
        "innodb_log_file_size": 5_242_880,
        "innodb_write_io_threads": 1,
        "work_mem": "1MB",
        "maintenance_work_mem": "16MB",
        "synchronous_commit": "local",
        "max_connections": "10",
        "wal_level": "logical",
        "shared_buffers": "32MB",
        "effective_cache_size": "256MB",
        "random_page_cost": "10",
        "max degree of parallelism": 16,
        "cost threshold for parallelism": 1,
        "fill factor (%)": 50,
        "__recovery_model__": 2,
        "pga_aggregate_target": "10485760",
        "sga_target": "104857600",
        "cursor_sharing": "SIMILAR",
        "db_writer_processes": "0",
        "undo_retention": "60",
        "journal_mode": "off",
        "synchronous": 0,
        "cache_size": 100,
        "temp_store": 1,
    },
}


class _Result:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self._rows)


class FakeServerConnection:
    """Conexión falsa que responde al SQL de los validadores con ``values``; ``fail`` lanza en cada consulta."""

    def __init__(self, values: dict[str, Any] | None, *, fail: bool = False, v_parameter: bool = True) -> None:
        self.values: dict[str, Any] = values or {}
        self.fail = fail
        self.v_parameter = v_parameter

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _Result:
        sql = " ".join(str(statement).split())
        if self.fail:
            raise OperationalError(sql, params, Exception("servidor caído"))
        lower = sql.lower()
        if match := re.match(r"show variables where variable_name = '([a-z_]+)'", lower):
            name = match.group(1)
            return _Result([(name, str(self.values[name]))] if name in self.values else [])
        if match := re.match(r"show ([a-z_]+)$", lower):
            return self._one(match.group(1))
        if match := re.match(r"pragma ([a-z_]+)$", lower):
            return self._one(match.group(1))
        if "sys.configurations" in lower:
            return self._one((params or {}).get("n", ""))
        if "sys.databases" in lower:
            return self._one("__recovery_model__")
        if "v$parameter" in lower:
            if not self.v_parameter:
                raise OperationalError(sql, params, Exception("ORA-00942"))
            if "rownum = 1" in lower:
                return _Result([(1,)])
            return self._one((params or {}).get("n", ""))
        raise AssertionError(f"SQL no previsto en la caracterización: {sql}")

    def _one(self, name: str) -> _Result:
        return _Result([(self.values[name],)] if name in self.values else [])


def _connections() -> dict[str, FakeServerConnection | None]:
    connections: dict[str, FakeServerConnection | None] = {"sin_conexion": None}
    connections |= {name: FakeServerConnection(values) for name, values in SERVER.items()}
    connections["servidor_caido"] = FakeServerConnection(None, fail=True)
    connections["sin_permiso_v_parameter"] = FakeServerConnection(SERVER["tipicos"], v_parameter=False)
    # 2.2.1 (R-2): MySQL 8.0.30+ con innodb_redo_log_capacity (100 MB, el valor por defecto) además de log_file_size.
    connections["mysql_8030"] = FakeServerConnection({**SERVER["tipicos"], "innodb_redo_log_capacity": 104_857_600})
    return connections


def _cases() -> list[tuple[str, str, str, str]]:
    return [
        (f"{engine}|{params}|{server}", engine, params, server)
        for engine in ENGINES
        for params in PARAMS
        for server in _connections()
        # sin_permiso_v_parameter solo cambia algo en Oracle, y mysql_8030 en MySQL/MariaDB
        if server != "sin_permiso_v_parameter" or engine == "oracle"
        if server != "mysql_8030" or engine in {"mysql", "mariadb"}
    ]


def _run(engine: str, params: str, server: str) -> list[list[str]]:
    findings = EngineReadinessAdvisor().check(engine, dict(PARAMS[params]), connection=_connections()[server])
    return [[f.level, f.param, f.current, f.recommendation] for f in findings]


def _golden() -> dict[str, list[list[str]]]:
    loaded: dict[str, list[list[str]]] = json.loads(GOLDEN.read_text(encoding="utf-8"))
    return loaded


@pytest.mark.skipif(not REGENERATE, reason="solo con UTIL_BBDD_REGEN_ADVISOR_GOLDEN=1")
def test_regenerate_golden() -> None:
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    data = {case_id: _run(engine, params, server) for case_id, engine, params, server in _cases()}
    GOLDEN.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


@pytest.mark.skipif(REGENERATE, reason="regenerando el fichero dorado")
@pytest.mark.parametrize(("case_id", "engine", "params", "server"), _cases(), ids=[case[0] for case in _cases()])
def test_findings_match_golden(
    case_id: str, engine: str, params: str, server: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="util_bbdd.connection")

    assert _run(engine, params, server) == _golden()[case_id]
    # El advisor se traga las excepciones: un SQL que la conexión falsa no conoce no debe pasar inadvertido.
    assert "SQL no previsto" not in caplog.text
    # T-08: lo esperable (servidor caído, sin permiso, valores raros) lo capturan los validadores; la red de seguridad
    # del advisor (WARNING «error interno») solo salta con un error de programación.
    assert "error interno" not in caplog.text


@pytest.mark.skipif(REGENERATE, reason="regenerando el fichero dorado")
def test_golden_has_exactly_the_cases_of_the_matrix() -> None:
    assert sorted(_golden()) == sorted(case[0] for case in _cases())


# T-07 (fix, 2026-10-16): casos con nombre de lo que cambió al validar el tipo de conn_params.
def _levels(engine: str, params: dict[str, Any], server: str = "sin_conexion") -> dict[str, str]:
    findings = EngineReadinessAdvisor().check(engine, params, connection=_connections()[server])
    return {f.param: f.level for f in findings}


@pytest.mark.parametrize(("engine", "param"), [("postgresql", "keepalives"), ("sqlserver", "use_mars")])
def test_false_as_text_is_false(engine: str, param: str) -> None:
    # Antes bool("false") daba True y el check salía OK.
    assert _levels(engine, {param: "false"})[param] == "WARNING"


@pytest.mark.parametrize("engine", ["postgresql", "sqlserver", "oracle", "sqlite"])
def test_an_invalid_value_is_critical_and_keeps_the_other_findings(engine: str) -> None:
    # Antes int("abc") perdía todos los hallazgos del motor (lista vacía).
    levels = _levels(engine, {"pool_size": "abc", "timeout": "abc"}, "tipicos")

    assert "CRITICAL" in levels.values()
    assert any(level != "CRITICAL" for level in levels.values())


def test_mysql_invalid_autocommit_keeps_the_dynamic_checks() -> None:
    # Antes un autocommit inválido cortaba los checks (también los dinámicos).
    levels = _levels("mysql", {"autocommit": "quizá"}, "tipicos")

    assert levels["autocommit"] == "CRITICAL"
    assert "innodb_buffer_pool_size" in levels


# T-08 (fix, 2026-10-16): un error de programación en un validador ya no queda oculto en DEBUG.
def test_an_internal_error_in_a_validator_is_a_warning_with_traceback(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from util_bbdd.connection.postgresql._variables import PostgreSQLVariableValidator

    def broken(self: PostgreSQLVariableValidator, conn_params: dict[str, Any]) -> list[Any]:
        raise TypeError("error de programación")

    monkeypatch.setattr(PostgreSQLVariableValidator, "check_static", broken)
    caplog.set_level(logging.DEBUG, logger="util_bbdd.connection")

    findings = EngineReadinessAdvisor().check("postgresql", {"pool_size": 10})  # sigue sin lanzar

    assert findings == []
    (record,) = [r for r in caplog.records if "error interno" in r.getMessage()]
    assert record.levelno == logging.WARNING
    assert record.exc_info is not None


def test_mysql_dynamic_only_swallows_server_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    from util_bbdd.connection.mariadb._variables import MySQLVariableValidator

    def broken(self: MySQLVariableValidator) -> dict[str, int]:
        raise TypeError("error de programación")

    monkeypatch.setattr(MySQLVariableValidator, "read_variables", broken)

    # Antes check_dynamic se lo tragaba en DEBUG; ahora sube a la red de seguridad del advisor (WARNING).
    with pytest.raises(TypeError):
        from util_bbdd.connection.mariadb._readiness import MySQLReadinessValidator

        MySQLReadinessValidator().check_dynamic(_connections()["tipicos"], {})


def test_an_internal_error_in_the_dynamic_checks_keeps_the_static_findings(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Antes, en PostgreSQL, SQL Server, Oracle y SQLite un fallo en los dinámicos perdía también los estáticos.
    from util_bbdd.connection.postgresql._variables import PostgreSQLVariableValidator

    def broken(self: PostgreSQLVariableValidator, connection: Any, conn_params: dict[str, Any]) -> list[Any]:
        raise TypeError("error de programación")

    monkeypatch.setattr(PostgreSQLVariableValidator, "check_dynamic", broken)

    findings = EngineReadinessAdvisor().check("postgresql", {"pool_size": 10}, connection=_connections()["tipicos"])

    assert "pool_size" in {f.param for f in findings}
    assert "error interno en los checks dinámicos de 'postgresql'" in caplog.text


# 2.2.1 (R-2): el redo log se evalúa con la variable que manda en el servidor.
def test_mysql_8030_reports_redo_log_capacity_and_not_the_ignored_log_file_size() -> None:
    levels = _levels("mysql", {}, "mysql_8030")

    assert levels["innodb_redo_log_capacity"] == "INFO"  # 100 MB < 512 MB
    assert "innodb_log_file_size" not in levels


def test_redo_log_capacity_of_at_least_512_mb_is_ok() -> None:
    connection = FakeServerConnection({**SERVER["tipicos"], "innodb_redo_log_capacity": 2_147_483_648})
    findings = EngineReadinessAdvisor().check("mysql", {}, connection=connection)

    assert {f.param: f.level for f in findings}["innodb_redo_log_capacity"] == "OK"


def test_without_redo_log_capacity_log_file_size_is_still_checked() -> None:
    # MariaDB y MySQL < 8.0.30 no tienen innodb_redo_log_capacity.
    levels = _levels("mariadb", {}, "tipicos")

    assert levels["innodb_log_file_size"] == "INFO"
    assert "innodb_redo_log_capacity" not in levels


@pytest.mark.parametrize(
    ("engine", "pool_size", "level"),
    [
        ("postgresql", 2, "WARNING"),
        ("postgresql", 10, "OK"),
        ("postgresql", 50, "INFO"),
        ("sqlserver", 2, "WARNING"),
        ("sqlserver", 10, "OK"),
        ("oracle", 2, "WARNING"),
        ("oracle", 10, "OK"),
    ],
)
def test_pool_size_gives_exactly_one_finding(engine: str, pool_size: int, level: str) -> None:
    # Las ramas WARNING/INFO/OK de pool_size son excluyentes: un pool pequeño no da además OK.
    findings = EngineReadinessAdvisor().check(engine, {"pool_size": pool_size}, connection=None)

    assert [f.level for f in findings if f.param == "pool_size"] == [level]
