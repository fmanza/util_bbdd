"""Verificador unificado de condiciones de ejecución por motor de base de datos.

Extiende el patrón ``MySQLVariableValidator`` a todos los motores soportados
y emite un informe consolidado en una única llamada al LOG.

Uso típico (desde BulkCrud.__init__ o llamada explícita)::

    from util_bbdd.connection import EngineReadinessAdvisor

    advisor = EngineReadinessAdvisor()
    # Solo checks estáticos (sin conexión):
    advisor.report("postgresql", conn_params)
    # Checks estáticos + dinámicos (con conexión activa):
    with engine.connect() as conn:
        advisor.report("postgresql", conn_params, connection=conn)
"""

from __future__ import annotations

import logging

from typing import Any

from ._advisory import AdvisoryFinding

logger: logging.Logger = logging.getLogger(__name__)

_LEVEL_ORDER: dict[str, int] = {"OK": 0, "INFO": 1, "WARNING": 2, "CRITICAL": 3}
_LEVEL_ICONS: dict[str, str] = {"OK": "✅  OK  ", "INFO": "ℹ️  INFO", "WARNING": "⚠️  WARN", "CRITICAL": "🔴  CRIT"}


class EngineReadinessAdvisor:
    """Verifica y reporta las condiciones de ejecución de un motor de BD.

    Soporta: postgresql, mariadb, mysql, oracle, mssql/sqlserver, sqlite.
    Para mariadb/mysql delega en ``MySQLVariableValidator`` (checks dinámicos)
    y añade checks estáticos de pool config.

    El método ``report()`` emite **una única** llamada al logger con el bloque
    completo de hallazgos y recomendaciones.
    """

    def check(
        self,
        db_type: str,
        conn_params: dict[str, Any],
        *,
        connection: Any = None,
    ) -> list[AdvisoryFinding]:
        """Ejecuta todos los checks disponibles y retorna los hallazgos.

        Args:
            db_type: Dialecto SQLAlchemy (``postgresql``, ``mysql``, ``mariadb``,
                     ``oracle``, ``mssql``, ``sqlite``).
            conn_params: Parámetros de conexión/pool (ya saneados).
            connection: Conexión SQLAlchemy activa para checks dinámicos (opcional).

        Returns:
            Lista de hallazgos ordenados por severidad descendente.
        """
        engine = db_type.lower().strip()
        findings: list[AdvisoryFinding] = []

        try:
            if engine in {"mysql", "mariadb"}:
                findings.extend(self._check_mysql(conn_params, connection=connection))
            elif engine == "postgresql":
                findings.extend(self._check_postgresql(conn_params, connection=connection))
            elif engine in {"mssql", "sqlserver"}:
                findings.extend(self._check_sqlserver(conn_params, connection=connection))
            elif engine == "oracle":
                findings.extend(self._check_oracle(conn_params, connection=connection))
            elif engine == "sqlite":
                findings.extend(self._check_sqlite(conn_params, connection=connection))
            else:
                logger.debug(f"EngineReadinessAdvisor: motor '{db_type}' sin checks específicos")
        except Exception as exc:
            logger.debug(f"EngineReadinessAdvisor: error en checks para '{db_type}': {exc}")

        findings.sort(key=lambda f: _LEVEL_ORDER.get(f.level, 0), reverse=True)
        return findings

    def report(
        self,
        db_type: str,
        conn_params: dict[str, Any],
        *,
        connection: Any = None,
    ) -> None:
        """Emite el informe de condiciones de ejecución en una única llamada al logger.

        El nivel de log es ``warning`` si hay WARNING o CRITICAL, ``info`` en caso contrario.

        Args:
            db_type: Dialecto SQLAlchemy.
            conn_params: Parámetros de conexión/pool.
            connection: Conexión activa para checks dinámicos (opcional).
        """
        findings = self.check(db_type, conn_params, connection=connection)
        if not findings:
            return

        host: str = str(conn_params.get("host", ""))
        port: str = str(conn_params.get("port", ""))
        host_str: str = f"{host}:{port}" if host else ""

        header = f"  ENGINE READINESS REPORT  ·  {db_type}"
        if host_str:
            header = f"{header}  ·  {host_str}"

        width = max(60, len(header) + 4)
        border = "═" * width

        lines: list[str] = [f"╔{border}╗", f"║{header.center(width)}║", f"╚{border}╝"]

        for f in findings:
            icon = _LEVEL_ICONS.get(f.level, f.level)
            param_col = f"{f.param}={f.current}"[:38].ljust(40)
            rec = f"  → {f.recommendation}" if f.recommendation else ""
            lines.append(f"  [{icon}]  {param_col}{rec}")

        counts = {lvl: sum(1 for f in findings if f.level == lvl) for lvl in ("CRITICAL", "WARNING", "INFO", "OK")}
        summary_parts = [f"{v} {k}" for k, v in counts.items() if v > 0]
        lines.append(f"{'─' * width}")
        lines.append(f"  Resumen: {' · '.join(summary_parts)}")

        worst_lvl = _LEVEL_ORDER.get(findings[0].level, 0) if findings else 0
        block = "\n".join(lines)

        if worst_lvl >= _LEVEL_ORDER["WARNING"]:
            logger.warning(block)
        else:
            logger.info(block)

    # ─── Adaptadores por motor ────────────────────────────────────────────────

    def _check_mysql(self, conn_params: dict[str, Any], *, connection: Any) -> list[AdvisoryFinding]:
        findings: list[AdvisoryFinding] = []

        # Checks estáticos de pool/config
        pool_size: int = int(conn_params.get("pool_size", 5))
        autocommit: bool = bool(conn_params.get("autocommit", False))
        write_timeout: int = int(conn_params.get("write_timeout", 60))
        read_timeout: int = int(conn_params.get("read_timeout", 30))

        if autocommit:
            findings.append(
                AdvisoryFinding(
                    level="WARNING",
                    param="autocommit",
                    current="True",
                    recommendation="autocommit=True confirma cada INSERT individualmente; usar transacciones para bulk",
                )
            )
        else:
            findings.append(AdvisoryFinding(level="OK", param="autocommit", current="False", recommendation=""))

        if pool_size < 5:
            findings.append(
                AdvisoryFinding(
                    level="WARNING",
                    param="pool_size",
                    current=str(pool_size),
                    recommendation="Mínimo 5 para cargas concurrentes",
                )
            )
        else:
            findings.append(AdvisoryFinding(level="OK", param="pool_size", current=str(pool_size), recommendation=""))

        if write_timeout < 30:
            findings.append(
                AdvisoryFinding(
                    level="WARNING",
                    param="write_timeout",
                    current=f"{write_timeout}s",
                    recommendation="Recomendado ≥60 s en cargas masivas para evitar 'Lost connection'",
                )
            )
        else:
            findings.append(
                AdvisoryFinding(level="OK", param="write_timeout", current=f"{write_timeout}s", recommendation="")
            )

        if read_timeout < 30:
            findings.append(
                AdvisoryFinding(
                    level="WARNING",
                    param="read_timeout",
                    current=f"{read_timeout}s",
                    recommendation="Recomendado ≥30 s",
                )
            )
        else:
            findings.append(
                AdvisoryFinding(level="OK", param="read_timeout", current=f"{read_timeout}s", recommendation="")
            )

        pool_timeout: int = int(conn_params.get("pool_timeout", 30))
        if pool_timeout < 10:
            findings.append(
                AdvisoryFinding(
                    level="WARNING",
                    param="pool_timeout",
                    current=f"{pool_timeout}s",
                    recommendation="Recomendado ≥10 s para evitar timeouts en picos de carga",
                )
            )

        # Checks dinámicos: delegar en MySQLVariableValidator existente
        if connection is not None:
            findings.extend(self._check_mysql_dynamic(connection))

        return findings

    def _check_mysql_dynamic(self, connection: Any) -> list[AdvisoryFinding]:
        """Usa MySQLVariableValidator para leer variables del servidor."""
        findings: list[AdvisoryFinding] = []
        try:
            from .mariadb._config import MySQLOptimalConfig
            from .mariadb._variables import MySQLVariableValidator

            validator = MySQLVariableValidator(connection)
            current = validator.read_variables()
            if not current:
                return findings

            recommended = MySQLOptimalConfig.production()
            thresholds = {
                "innodb_buffer_pool_size": recommended.innodb_buffer_pool_size,
                "max_allowed_packet": recommended.max_allowed_packet,
            }

            for var, min_val in thresholds.items():
                actual = current.get(var)
                if actual is None:
                    continue
                actual_fmt = validator.format_bytes(actual)
                rec_fmt = validator.format_bytes(min_val)
                if actual < min_val:
                    findings.append(
                        AdvisoryFinding(
                            level="WARNING",
                            param=var,
                            current=actual_fmt,
                            recommendation=f"Recomendado ≥{rec_fmt}; "
                            f"SET GLOBAL {var} = {min_val}; (requiere SUPER o SYSTEM_VARIABLES_ADMIN)",
                        )
                    )
                else:
                    findings.append(AdvisoryFinding(level="OK", param=var, current=actual_fmt, recommendation=""))
        except Exception as exc:
            logger.debug(f"_check_mysql_dynamic: {type(exc).__name__}: {exc}")
        return findings

    def _check_postgresql(self, conn_params: dict[str, Any], *, connection: Any) -> list[AdvisoryFinding]:
        try:
            from .postgresql._variables import PostgreSQLVariableValidator

            v = PostgreSQLVariableValidator()
            findings = v.check_static(conn_params)
            if connection is not None:
                findings.extend(v.check_dynamic(connection, conn_params))
            return findings
        except Exception as exc:
            logger.debug(f"_check_postgresql: {type(exc).__name__}: {exc}")
            return []

    def _check_sqlserver(self, conn_params: dict[str, Any], *, connection: Any) -> list[AdvisoryFinding]:
        try:
            from .sqlserver._variables import SQLServerVariableValidator

            v = SQLServerVariableValidator()
            findings = v.check_static(conn_params)
            if connection is not None:
                findings.extend(v.check_dynamic(connection, conn_params))
            return findings
        except Exception as exc:
            logger.debug(f"_check_sqlserver: {type(exc).__name__}: {exc}")
            return []

    def _check_oracle(self, conn_params: dict[str, Any], *, connection: Any) -> list[AdvisoryFinding]:
        try:
            from .oracle._variables import OracleVariableValidator

            v = OracleVariableValidator()
            findings = v.check_static(conn_params)
            if connection is not None:
                findings.extend(v.check_dynamic(connection, conn_params))
            return findings
        except Exception as exc:
            logger.debug(f"_check_oracle: {type(exc).__name__}: {exc}")
            return []

    def _check_sqlite(self, conn_params: dict[str, Any], *, connection: Any) -> list[AdvisoryFinding]:
        try:
            from .sqlite._variables import SQLiteVariableValidator

            v = SQLiteVariableValidator()
            findings = v.check_static(conn_params)
            if connection is not None:
                findings.extend(v.check_dynamic(connection, conn_params))
            return findings
        except Exception as exc:
            logger.debug(f"_check_sqlite: {type(exc).__name__}: {exc}")
            return []


__all__: list[str] = ["AdvisoryFinding", "EngineReadinessAdvisor"]
