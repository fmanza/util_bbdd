"""Validador read-only de parámetros SQLite para optimización de bulk operations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .._advisory import AdvisoryFinding, ConnParamReader

_IN_MEMORY: frozenset[str] = frozenset({":memory:", ""})

# Whitelist de PRAGMAs válidos (F-01: prevenir inyección SQL)
_VALID_PRAGMA_NAMES: frozenset[str] = frozenset(
    {
        "journal_mode",
        "synchronous",
        "cache_size",
        "temp_store",
        "page_size",
    }
)

# Valores de PRAGMA synchronous
_SYNC_NAMES: dict[int, str] = {0: "OFF", 1: "NORMAL", 2: "FULL", 3: "EXTRA"}


class SQLiteVariableValidator:
    """Validador de parámetros SQLite (read-only).

    Los checks estáticos evalúan conn_params sin conexión.
    Los checks dinámicos ejecutan ``PRAGMA <name>`` (sin permisos especiales).
    Los checks de WAL y synchronous se omiten en bases de datos ``:memory:``.
    """

    def check_static(self, conn_params: dict[str, Any]) -> list[AdvisoryFinding]:
        """Evalúa conn_params sin conexión al servidor."""
        # T-07: tipo validado; un timeout inválido da su CRITICAL y solo se omite su check (antes se perdía todo).
        reader = ConnParamReader(conn_params, "sqlite")
        database: str = str(conn_params.get("database", "") or "")
        timeout = reader.as_float("timeout", 5.0)
        findings: list[AdvisoryFinding] = reader.invalid
        is_memory: bool = database.strip() in _IN_MEMORY

        if is_memory:
            findings.append(
                AdvisoryFinding(
                    level="INFO",
                    param="database",
                    current=":memory:",
                    recommendation="Base de datos en memoria: sin persistencia; datos se pierden al cerrar",
                )
            )
        else:
            findings.append(AdvisoryFinding(level="OK", param="database", current=database, recommendation=""))

        if timeout is not None:
            if timeout < 5.0:
                findings.append(
                    AdvisoryFinding(
                        level="WARNING",
                        param="timeout",
                        current=f"{timeout}s",
                        recommendation="Riesgo de 'database is locked' bajo escritura concurrente; recomendado ≥5 s",
                    )
                )
            else:
                findings.append(AdvisoryFinding(level="OK", param="timeout", current=f"{timeout}s", recommendation=""))

        return findings

    def check_dynamic(self, connection: Any, conn_params: dict[str, Any]) -> list[AdvisoryFinding]:
        """Checks dinámicos vía PRAGMA; omite WAL/sync en :memory:."""
        database: str = str(conn_params.get("database", "") or "")
        if database.strip() in _IN_MEMORY:
            return []  # PRAGMAs de persistencia no aplican

        findings: list[AdvisoryFinding] = []
        findings.extend(self._check_journal_mode(connection))
        findings.extend(self._check_synchronous(connection))
        findings.extend(self._check_cache_size(connection))
        findings.extend(self._check_temp_store(connection))
        return findings

    def _check_journal_mode(self, connection: Any) -> list[AdvisoryFinding]:
        findings: list[AdvisoryFinding] = []
        journal_mode = self._pragma_str(connection, "journal_mode")
        if journal_mode is None:
            return findings

        if journal_mode.lower() != "wal":
            findings.append(
                AdvisoryFinding(
                    level="WARNING",
                    param="journal_mode",
                    current=journal_mode,
                    recommendation="PRAGMA journal_mode=WAL mejora escritura concurrente y rendimiento",
                )
            )
            return findings

        findings.append(AdvisoryFinding(level="OK", param="journal_mode", current="wal", recommendation=""))
        return findings

    def _check_synchronous(self, connection: Any) -> list[AdvisoryFinding]:
        findings: list[AdvisoryFinding] = []
        sync_val = self._pragma_int(connection, "synchronous")
        if sync_val is None:
            return findings

        sync_name = _SYNC_NAMES.get(sync_val, str(sync_val))
        if sync_val >= 2:  # FULL o EXTRA
            findings.append(
                AdvisoryFinding(
                    level="INFO",
                    param="synchronous",
                    current=sync_name,
                    recommendation="PRAGMA synchronous=NORMAL reduce fsync en carga masiva sin riesgo de corrupción",
                )
            )
            return findings

        findings.append(AdvisoryFinding(level="OK", param="synchronous", current=sync_name, recommendation=""))
        return findings

    def _check_cache_size(self, connection: Any) -> list[AdvisoryFinding]:
        findings: list[AdvisoryFinding] = []
        cache_size = self._pragma_int(connection, "cache_size")
        if cache_size is None:
            return findings

        # cache_size negativo = KiB; positivo = páginas (4 KB típico)
        cache_kb = abs(cache_size) if cache_size < 0 else cache_size * 4
        if cache_kb < 8_192:  # < 8 MB
            findings.append(
                AdvisoryFinding(
                    level="INFO",
                    param="cache_size",
                    current=f"{cache_size} ({cache_kb} KB)",
                    recommendation="PRAGMA cache_size=-65536 establece 64 MB de caché de páginas",
                )
            )
        return findings

    def _check_temp_store(self, connection: Any) -> list[AdvisoryFinding]:
        findings: list[AdvisoryFinding] = []
        temp_store = self._pragma_int(connection, "temp_store")
        if temp_store is not None and temp_store == 1:  # FILE
            findings.append(
                AdvisoryFinding(
                    level="INFO",
                    param="temp_store",
                    current="FILE",
                    recommendation="PRAGMA temp_store=MEMORY acelera operaciones con tablas temporales",
                )
            )
        return findings

    def _pragma_str(self, connection: Any, name: str) -> str | None:
        if name not in _VALID_PRAGMA_NAMES:
            return None
        try:
            row = connection.execute(text(f"PRAGMA {name}")).fetchone()
            if row:
                return str(row[0]).strip()
        except SQLAlchemyError:
            pass
        return None

    def _pragma_int(self, connection: Any, name: str) -> int | None:
        if name not in _VALID_PRAGMA_NAMES:
            return None
        try:
            row = connection.execute(text(f"PRAGMA {name}")).fetchone()
            if row:
                return int(row[0])
        except (SQLAlchemyError, ValueError, TypeError):
            pass
        return None


__all__: list[str] = ["SQLiteVariableValidator"]
