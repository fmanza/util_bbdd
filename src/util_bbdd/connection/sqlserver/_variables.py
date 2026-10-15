"""Validador read-only de parámetros SQL Server para optimización de bulk operations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .._advisory import AdvisoryFinding, ConnParamReader


class SQLServerVariableValidator:
    """Validador de parámetros SQL Server (read-only).

    Los checks estáticos evalúan conn_params sin conexión.
    Los checks dinámicos consultan ``sys.configurations`` y ``sys.databases``
    (permisos: VIEW SERVER STATE o VIEW DATABASE STATE, no requiere sysadmin).
    """

    def check_static(self, conn_params: dict[str, Any]) -> list[AdvisoryFinding]:
        """Evalúa conn_params y pool config sin conexión."""
        # T-07: tipo validado; un valor inválido da su CRITICAL y solo se omite su check (antes se perdía todo).
        reader = ConnParamReader(conn_params, "sqlserver")
        pool_size = reader.as_int("pool_size", 5)
        max_overflow = reader.as_int("max_overflow", 10)
        pool_timeout = reader.as_int("pool_timeout", 30)
        use_mars = reader.as_bool("use_mars", True)
        driver: str = str(conn_params.get("sql_server_driver", "pymssql")).lower()
        findings: list[AdvisoryFinding] = reader.invalid

        if use_mars is None:
            pass
        elif not use_mars:
            findings.append(
                AdvisoryFinding(
                    level="WARNING",
                    param="use_mars",
                    current="False",
                    recommendation="Activar use_mars=True (Multiple Active Result Sets) para múltiples cursores activos",
                )
            )
        else:
            findings.append(AdvisoryFinding(level="OK", param="use_mars", current="True", recommendation=""))

        if pool_size is None:
            pass
        elif pool_size < 5:
            findings.append(
                AdvisoryFinding(
                    level="WARNING",
                    param="pool_size",
                    current=str(pool_size),
                    recommendation="Mínimo 5 para cargas concurrentes; recomendado 10–20",
                )
            )
        else:
            findings.append(AdvisoryFinding(level="OK", param="pool_size", current=str(pool_size), recommendation=""))

        if max_overflow is not None and max_overflow < 5:
            findings.append(
                AdvisoryFinding(
                    level="WARNING",
                    param="max_overflow",
                    current=str(max_overflow),
                    recommendation="Recomendado ≥5 para absorber picos de conexión",
                )
            )

        if pool_timeout is not None and pool_timeout < 10:
            findings.append(
                AdvisoryFinding(
                    level="WARNING",
                    param="pool_timeout",
                    current=f"{pool_timeout}s",
                    recommendation="Recomendado ≥10 s para evitar timeouts en picos de carga",
                )
            )

        if driver == "pymssql":
            findings.append(
                AdvisoryFinding(
                    level="INFO",
                    param="sql_server_driver",
                    current="pymssql",
                    recommendation="pyodbc + ODBC Driver 17/18 es ~15× más rápido en INSERT/UPDATE masivo "
                    "(ver docs/guides/benchmarks.md)",
                )
            )
        else:
            findings.append(AdvisoryFinding(level="OK", param="sql_server_driver", current=driver, recommendation=""))

        return findings

    def check_dynamic(self, connection: Any, conn_params: dict[str, Any]) -> list[AdvisoryFinding]:
        """Checks dinámicos vía sys.configurations y sys.databases (uno por helper; T-06, Sonar S3776)."""
        database: str = str(conn_params.get("database", ""))
        checks = (
            self._maxdop_finding(self._read_config_int(connection, "max degree of parallelism")),
            self._cost_threshold_finding(self._read_config_int(connection, "cost threshold for parallelism")),
            self._fill_factor_finding(self._read_config_int(connection, "fill factor (%)")),
            self._recovery_model_finding(self._read_recovery_model(connection, database) if database else None),
        )
        return [finding for finding in checks if finding is not None]

    @staticmethod
    def _maxdop_finding(maxdop: int | None) -> AdvisoryFinding | None:
        """max_degree_of_parallelism (MAXDOP): 0 = ilimitado; recomendado nCPU/2 para OLTP bulk."""
        if maxdop is None:
            return None
        if maxdop == 0:
            return AdvisoryFinding(
                level="INFO",
                param="max_degree_of_parallelism",
                current="0 (ilimitado)",
                recommendation="Para OLTP bulk: ajustar a nCPU/2 (máximo 8) con EXEC sp_configure "
                "'max degree of parallelism', <n>; RECONFIGURE; (o ALTER DATABASE SCOPED CONFIGURATION "
                "SET MAXDOP = <n>;); evita overhead de paralelismo en queries pequeñas",
            )
        if maxdop > 8:
            return AdvisoryFinding(
                level="INFO",
                param="max_degree_of_parallelism",
                current=str(maxdop),
                recommendation="Valor alto; puede saturar CPU en bulk. Considerar nCPU/2 para balance OLTP/bulk",
            )
        return AdvisoryFinding(level="OK", param="max_degree_of_parallelism", current=str(maxdop), recommendation="")

    @staticmethod
    def _cost_threshold_finding(cost_threshold: int | None) -> AdvisoryFinding | None:
        """cost threshold for parallelism. T-03: el INFO saltaba por debajo de 10 con el texto «recomendado 50–100» (20
        salía OK); el umbral pasa a 50, como el texto."""
        if cost_threshold is None:
            return None
        if cost_threshold < 50:
            return AdvisoryFinding(
                level="INFO",
                param="cost_threshold_for_parallelism",
                current=str(cost_threshold),
                recommendation="Valor bajo (<50; por defecto 5) puede activar paralelismo en queries pequeñas "
                "con overhead; recomendado 50–100 para OLTP bulk",
            )
        return AdvisoryFinding(
            level="OK", param="cost_threshold_for_parallelism", current=str(cost_threshold), recommendation=""
        )

    @staticmethod
    def _fill_factor_finding(fill_factor: int | None) -> AdvisoryFinding | None:
        """fill factor: 0 = 100% (óptimo para carga inicial); bajo puede ralentizar INSERT."""
        if fill_factor is None or not 0 < fill_factor < 70:
            return None
        return AdvisoryFinding(
            level="INFO",
            param="fill_factor",
            current=f"{fill_factor}%",
            recommendation="fill factor=0 (100%) es óptimo para carga inicial masiva",
        )

    @staticmethod
    def _recovery_model_finding(recovery: int | None) -> AdvisoryFinding | None:
        """recovery model de la base de datos activa (1 FULL, 2 BULK_LOGGED, 3 SIMPLE)."""
        if recovery is None:
            return None
        recovery_name = {1: "FULL", 2: "BULK_LOGGED", 3: "SIMPLE"}.get(recovery, str(recovery))
        if recovery == 1:  # FULL
            return AdvisoryFinding(
                level="INFO",
                param="recovery_model",
                current=recovery_name,
                recommendation="Para carga masiva sin replicación: "
                "ALTER DATABASE ... SET RECOVERY BULK_LOGGED durante la carga",
            )
        return AdvisoryFinding(level="OK", param="recovery_model", current=recovery_name, recommendation="")

    def _read_config_int(self, connection: Any, config_name: str) -> int | None:
        try:
            sql = text("SELECT CAST(value_in_use AS INT) FROM sys.configurations WHERE name = :n")
            row = connection.execute(sql, {"n": config_name}).fetchone()
            if row:
                return int(row[0])
        except (SQLAlchemyError, ValueError, TypeError):
            pass
        return None

    def _read_recovery_model(self, connection: Any, database: str) -> int | None:
        try:
            sql = text("SELECT recovery_model FROM sys.databases WHERE name = :db")
            row = connection.execute(sql, {"db": database}).fetchone()
            if row:
                return int(row[0])
        except (SQLAlchemyError, ValueError, TypeError):
            pass
        return None


__all__: list[str] = ["SQLServerVariableValidator"]
