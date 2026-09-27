"""Validador read-only de parámetros PostgreSQL para optimización de bulk operations."""

from __future__ import annotations

from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .._advisory import AdvisoryFinding, fmt_bytes as _fmt_bytes

# Umbrales de memoria para checks dinámicos
_WARN_WORK_MEM: int = 16 * 1_048_576  # 16 MB
_INFO_WORK_MEM: int = 64 * 1_048_576  # 64 MB
_WARN_MAINT_MEM: int = 64 * 1_048_576  # 64 MB
_INFO_MAINT_MEM: int = 256 * 1_048_576  # 256 MB

# Whitelist de parámetros válidos para SHOW (F-01: prevenir inyección SQL)
_VALID_SHOW_PARAMS: frozenset[str] = frozenset(
    {
        "work_mem",
        "maintenance_work_mem",
        "synchronous_commit",
        "max_connections",
        "wal_level",
    }
)


def _parse_pg_memory(value: str) -> int:
    """Convierte valor de memoria PostgreSQL ('4MB', '1GB', '8192kB') a bytes."""
    v = value.strip()
    if v.endswith("GB"):
        return int(float(v[:-2]) * 1_073_741_824)
    if v.endswith("MB"):
        return int(float(v[:-2]) * 1_048_576)
    if v.endswith("kB"):
        return int(float(v[:-2]) * 1024)
    try:
        return int(v)
    except ValueError:
        return 0


class PostgreSQLVariableValidator:
    """Validador de parámetros PostgreSQL (read-only).

    Los checks estáticos evalúan conn_params sin conexión al servidor.
    Los checks dinámicos ejecutan ``SHOW <param>`` (disponible sin permisos especiales).
    """

    def check_static(self, conn_params: dict[str, Any]) -> list[AdvisoryFinding]:
        """Evalúa conn_params y pool config sin conexión."""
        findings: list[AdvisoryFinding] = []
        pool_size: int = int(conn_params.get("pool_size", 5))
        max_overflow: int = int(conn_params.get("max_overflow", 10))
        pool_timeout: int = int(conn_params.get("pool_timeout", 30))
        keepalives: bool = bool(conn_params.get("keepalives", True))
        sslmode: str | None = conn_params.get("sslmode")

        if pool_size < 5:
            findings.append(
                AdvisoryFinding(
                    level="WARNING",
                    param="pool_size",
                    current=str(pool_size),
                    recommendation="Mínimo 5 para cargas concurrentes; recomendado 10–20",
                )
            )
        elif pool_size > 20:
            findings.append(
                AdvisoryFinding(
                    level="INFO",
                    param="pool_size",
                    current=str(pool_size),
                    recommendation=f"Verificar pool_size({pool_size})+max_overflow({max_overflow}) ≤ max_connections del servidor",
                )
            )
        else:
            findings.append(AdvisoryFinding(level="OK", param="pool_size", current=str(pool_size), recommendation=""))

        if not keepalives:
            findings.append(
                AdvisoryFinding(
                    level="WARNING",
                    param="keepalives",
                    current="False",
                    recommendation="Activar keepalives=True; las conexiones mueren silenciosamente bajo NAT/firewall",
                )
            )
        else:
            findings.append(AdvisoryFinding(level="OK", param="keepalives", current="True", recommendation=""))

        if sslmode is None or sslmode == "disable":
            findings.append(
                AdvisoryFinding(
                    level="INFO",
                    param="sslmode",
                    current=str(sslmode),
                    recommendation="Sin cifrado en tránsito; considera sslmode='require' en producción",
                )
            )
        else:
            findings.append(AdvisoryFinding(level="OK", param="sslmode", current=sslmode, recommendation=""))

        if pool_timeout < 10:
            findings.append(
                AdvisoryFinding(
                    level="WARNING",
                    param="pool_timeout",
                    current=f"{pool_timeout}s",
                    recommendation="Recomendado ≥10 s para evitar timeouts en picos de carga",
                )
            )

        return findings

    def check_dynamic(self, connection: Any, conn_params: dict[str, Any]) -> list[AdvisoryFinding]:
        """Checks dinámicos vía SHOW <param>; requiere conexión activa."""
        findings: list[AdvisoryFinding] = []

        self._add_memory_finding(
            findings,
            connection,
            param="work_mem",
            warn_threshold=_WARN_WORK_MEM,
            info_threshold=_INFO_WORK_MEM,
            warn_recommendation="Recomendado ≥16 MB para bulk; SET work_mem = '64MB' en la sesión",
            info_recommendation="Óptimo para cargas masivas: ≥64 MB (SET work_mem = '64MB')",
        )

        self._add_memory_finding(
            findings,
            connection,
            param="maintenance_work_mem",
            warn_threshold=_WARN_MAINT_MEM,
            info_threshold=_INFO_MAINT_MEM,
            warn_recommendation="Recomendado ≥64 MB para CREATE INDEX post-carga masiva",
            info_recommendation="Para re-indexado masivo: ≥256 MB",
        )

        sync = self._show_str(connection, "synchronous_commit")
        if sync == "off":
            findings.append(
                AdvisoryFinding(
                    level="INFO",
                    param="synchronous_commit",
                    current="off",
                    recommendation="Máximo rendimiento pero sin durabilidad garantizada post-crash",
                )
            )

        self._add_max_connections_finding(findings, connection, conn_params)

        return findings

    def _add_memory_finding(
        self,
        findings: list[AdvisoryFinding],
        connection: Any,
        *,
        param: str,
        warn_threshold: int,
        info_threshold: int,
        warn_recommendation: str,
        info_recommendation: str,
    ) -> None:
        value = self._show_memory(connection, param)
        if value is None:
            return

        level: Literal["OK", "INFO", "WARNING", "CRITICAL"]
        if value < warn_threshold:
            level = "WARNING"
            recommendation = warn_recommendation
        elif value < info_threshold:
            level = "INFO"
            recommendation = info_recommendation
        else:
            level = "OK"
            recommendation = ""

        findings.append(
            AdvisoryFinding(level=level, param=param, current=_fmt_bytes(value), recommendation=recommendation)
        )

    def _add_max_connections_finding(
        self,
        findings: list[AdvisoryFinding],
        connection: Any,
        conn_params: dict[str, Any],
    ) -> None:
        max_conn_str = self._show_str(connection, "max_connections")
        if max_conn_str is None:
            return

        try:
            max_conn = int(max_conn_str)
            pool_size = int(conn_params.get("pool_size", 5))
            max_overflow = int(conn_params.get("max_overflow", 10))
        except (ValueError, TypeError):
            return

        total = pool_size + max_overflow
        current = f"servidor={max_conn}, pool({pool_size})+overflow({max_overflow})={total}"
        if total >= max_conn:
            findings.append(
                AdvisoryFinding(
                    level="CRITICAL",
                    param="max_connections",
                    current=current,
                    recommendation="Reducir pool o aumentar max_connections en postgresql.conf",
                )
            )
        elif total > int(max_conn * 0.8):
            findings.append(
                AdvisoryFinding(
                    level="WARNING",
                    param="max_connections",
                    current=current,
                    recommendation="Usando >80% de max_connections; riesgo de rechazo en picos",
                )
            )
        else:
            findings.append(
                AdvisoryFinding(
                    level="OK",
                    param="max_connections",
                    current=f"servidor={max_conn}, pool_total={total}",
                    recommendation="",
                )
            )

    def _show_memory(self, connection: Any, param: str) -> int | None:
        if param not in _VALID_SHOW_PARAMS:
            return None
        try:
            row = connection.execute(text(f"SHOW {param}")).fetchone()
            if row:
                return _parse_pg_memory(str(row[0]))
        except SQLAlchemyError:
            pass
        return None

    def _show_str(self, connection: Any, param: str) -> str | None:
        if param not in _VALID_SHOW_PARAMS:
            return None
        try:
            row = connection.execute(text(f"SHOW {param}")).fetchone()
            if row:
                return str(row[0]).strip()
        except SQLAlchemyError:
            pass
        return None


__all__: list[str] = ["PostgreSQLVariableValidator"]
