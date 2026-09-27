"""Validador read-only de parámetros Oracle para optimización de bulk operations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .._advisory import AdvisoryFinding, fmt_bytes as _fmt_bytes

# Mínimos recomendados para carga masiva
_WARN_PGA_BYTES: int = 256 * 1_048_576  # 256 MB
_WARN_SGA_BYTES: int = 512 * 1_048_576  # 512 MB


class OracleVariableValidator:
    """Validador de parámetros Oracle (read-only).

    Los checks estáticos evalúan conn_params sin conexión.
    Los checks dinámicos consultan ``v$parameter`` (requiere SELECT ANY DICTIONARY
    o SELECT_CATALOG_ROLE); si los permisos faltan se emite un hallazgo INFO.
    """

    def check_static(self, conn_params: dict[str, Any]) -> list[AdvisoryFinding]:
        """Evalúa conn_params y pool config sin conexión."""
        findings: list[AdvisoryFinding] = []
        pool_size: int = int(conn_params.get("pool_size", 5))
        max_lifetime: int = int(conn_params.get("max_lifetime", 3600))

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

        if max_lifetime < 600:
            findings.append(
                AdvisoryFinding(
                    level="WARNING",
                    param="max_lifetime",
                    current=f"{max_lifetime}s",
                    recommendation="Reconexiones frecuentes impactan rendimiento; recomendado ≥3600 s",
                )
            )
        else:
            findings.append(
                AdvisoryFinding(
                    level="OK",
                    param="max_lifetime",
                    current=f"{max_lifetime}s",
                    recommendation="",
                )
            )

        # arraysize y prefetchrows son parámetros de cursor, no de conexión
        findings.append(
            AdvisoryFinding(
                level="INFO",
                param="arraysize/prefetchrows",
                current="(parámetros de cursor, no verificables en conn_params)",
                recommendation="Ajustar arraysize≥1000 y prefetchrows≥500 en el cursor oracledb para reducir round-trips",
            )
        )

        return findings

    def check_dynamic(self, connection: Any, conn_params: dict[str, Any]) -> list[AdvisoryFinding]:
        """Checks dinámicos vía v$parameter; requiere SELECT ANY DICTIONARY."""
        _ = conn_params  # Se acepta por compatibilidad con la API; no se usa en el chequeo dinámico.
        findings: list[AdvisoryFinding] = []

        # Verificar si hay acceso a v$parameter
        if not self._can_read_v_parameter(connection):
            findings.append(
                AdvisoryFinding(
                    level="INFO",
                    param="v$parameter",
                    current="sin permiso",
                    recommendation="Otorgar SELECT ANY DICTIONARY o SELECT_CATALOG_ROLE para checks dinámicos",
                )
            )
            return findings

        pga = self._read_bytes_param(connection, "pga_aggregate_target")
        if pga is not None and pga > 0:
            if pga < _WARN_PGA_BYTES:
                findings.append(
                    AdvisoryFinding(
                        level="WARNING",
                        param="pga_aggregate_target",
                        current=_fmt_bytes(pga),
                        recommendation="Recomendado ≥256 MB para sort/hash en carga masiva",
                    )
                )
            else:
                findings.append(
                    AdvisoryFinding(
                        level="OK",
                        param="pga_aggregate_target",
                        current=_fmt_bytes(pga),
                        recommendation="",
                    )
                )

        sga = self._read_bytes_param(connection, "sga_target")
        if sga is not None and sga > 0:
            if sga < _WARN_SGA_BYTES:
                findings.append(
                    AdvisoryFinding(
                        level="WARNING",
                        param="sga_target",
                        current=_fmt_bytes(sga),
                        recommendation="Recomendado ≥512 MB; buffer cache insuficiente para cargas grandes",
                    )
                )
            else:
                findings.append(
                    AdvisoryFinding(
                        level="OK",
                        param="sga_target",
                        current=_fmt_bytes(sga),
                        recommendation="",
                    )
                )

        cursor_sharing = self._read_str_param(connection, "cursor_sharing")
        if cursor_sharing is not None and cursor_sharing.upper() == "FORCE":
            findings.append(
                AdvisoryFinding(
                    level="WARNING",
                    param="cursor_sharing",
                    current=cursor_sharing,
                    recommendation="cursor_sharing=FORCE puede invalidar bind variables; recomendado EXACT",
                )
            )

        db_writers = self._read_int_param(connection, "db_writer_processes")
        if db_writers is not None and db_writers == 1:
            findings.append(
                AdvisoryFinding(
                    level="INFO",
                    param="db_writer_processes",
                    current="1",
                    recommendation="En servidores con ≥4 CPUs, aumentar db_writer_processes a nCPUs/8",
                )
            )

        return findings

    def _can_read_v_parameter(self, connection: Any) -> bool:
        try:
            connection.execute(text("SELECT 1 FROM v$parameter WHERE ROWNUM = 1"))
            return True
        except SQLAlchemyError:
            return False

    def _read_bytes_param(self, connection: Any, name: str) -> int | None:
        try:
            sql = text("SELECT value FROM v$parameter WHERE name = :n")
            row = connection.execute(sql, {"n": name}).fetchone()
            if row and row[0] is not None:
                return int(row[0])
        except (SQLAlchemyError, ValueError, TypeError):
            pass
        return None

    def _read_str_param(self, connection: Any, name: str) -> str | None:
        try:
            sql = text("SELECT value FROM v$parameter WHERE name = :n")
            row = connection.execute(sql, {"n": name}).fetchone()
            if row and row[0] is not None:
                return str(row[0]).strip()
        except (SQLAlchemyError, ValueError, TypeError):
            pass
        return None

    def _read_int_param(self, connection: Any, name: str) -> int | None:
        val = self._read_str_param(connection, name)
        if val is not None:
            try:
                return int(val)
            except (ValueError, TypeError):
                pass
        return None


__all__: list[str] = ["OracleVariableValidator"]
