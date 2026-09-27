"""Validador read-only de parámetros SQL Server para optimización de bulk operations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .._advisory import AdvisoryFinding


class SQLServerVariableValidator:
    """Validador de parámetros SQL Server (read-only).

    Los checks estáticos evalúan conn_params sin conexión.
    Los checks dinámicos consultan ``sys.configurations`` y ``sys.databases``
    (permisos: VIEW SERVER STATE o VIEW DATABASE STATE, no requiere sysadmin).
    """

    def check_static(self, conn_params: dict[str, Any]) -> list[AdvisoryFinding]:
        """Evalúa conn_params y pool config sin conexión."""
        findings: list[AdvisoryFinding] = []
        pool_size: int = int(conn_params.get("pool_size", 5))
        max_overflow: int = int(conn_params.get("max_overflow", 10))
        pool_timeout: int = int(conn_params.get("pool_timeout", 30))
        use_mars: bool = bool(conn_params.get("use_mars", True))
        driver: str = str(conn_params.get("sql_server_driver", "pymssql")).lower()

        if not use_mars:
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

        if pool_size < 5:
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

        if max_overflow < 5:
            findings.append(
                AdvisoryFinding(
                    level="WARNING",
                    param="max_overflow",
                    current=str(max_overflow),
                    recommendation="Recomendado ≥5 para absorber picos de conexión",
                )
            )

        if pool_timeout < 10:
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
        """Checks dinámicos vía sys.configurations y sys.databases."""
        findings: list[AdvisoryFinding] = []

        # fill factor: 0 = 100% (óptimo para carga inicial); bajo puede ralentizar INSERT
        fill_factor = self._read_config_int(connection, "fill factor (%)")
        if fill_factor is not None:
            if 0 < fill_factor < 70:
                findings.append(
                    AdvisoryFinding(
                        level="INFO",
                        param="fill_factor",
                        current=f"{fill_factor}%",
                        recommendation="fill factor=0 (100%) es óptimo para carga inicial masiva",
                    )
                )

        # recovery model de la base de datos activa
        database: str = str(conn_params.get("database", ""))
        if database:
            recovery = self._read_recovery_model(connection, database)
            if recovery is not None:
                recovery_name = {1: "FULL", 2: "BULK_LOGGED", 3: "SIMPLE"}.get(recovery, str(recovery))
                if recovery == 1:  # FULL
                    findings.append(
                        AdvisoryFinding(
                            level="INFO",
                            param="recovery_model",
                            current=recovery_name,
                            recommendation="Para carga masiva sin replicación: "
                            "ALTER DATABASE ... SET RECOVERY BULK_LOGGED durante la carga",
                        )
                    )
                else:
                    findings.append(
                        AdvisoryFinding(
                            level="OK",
                            param="recovery_model",
                            current=recovery_name,
                            recommendation="",
                        )
                    )

        return findings

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
