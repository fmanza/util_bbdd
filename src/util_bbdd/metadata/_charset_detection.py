"""Detección automática de estado de charset en servidores MariaDB.

Implementa CharsetStateDetector para diagnosticar problemas de charset sin intervención manual,
habilitando la estrategia adaptativa de fallback (v0.33.0+).

Estados posibles:
- `utf8mb4_clean`: ✅ Sesión y BD en utf8mb4, sin corrupción
- `utf8mb4_mixed`: ⚠️ Sesión en utf8mb4 pero metadatos en utf8mb3 (post-upgrade)
- `utf8mb3_legacy`: ❌ Sesión y BD en utf8mb3 (ancient, necesita fallback latin1)
- `latin1_mismatch`: 🔴 Sesión en latin1 pero BD en utf8mb4 (SET NAMES utf8mb4 no ejecutado)
- `unknown`: ❓ No se pudo determinar (fallback a fail-fast)

ADR-003 §5 — Charset detection y adaptive remediation.
"""

from __future__ import annotations

import logging

from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CharsetState(Enum):
    """Estados posibles de charset en el servidor."""

    UTF8MB4_CLEAN = "utf8mb4_clean"  # ✅ Server y DB coherentes en utf8mb4
    UTF8MB4_MIXED = "utf8mb4_mixed"  # ⚠️ Server utf8mb4 con metadatos utf8mb3
    UTF8MB3_LEGACY = "utf8mb3_legacy"  # ❌ Server y DB en utf8mb3
    LATIN1_MISMATCH = "latin1_mismatch"  # 🔴 Sesión latin1 pero BD utf8mb4 (sin SET NAMES)
    UNKNOWN = "unknown"  # ❓ No determinable


@dataclass(frozen=True)
class CharsetDiagnosis:
    """Diagnóstico de charset del servidor."""

    state: CharsetState
    server_charset: str | None
    database_charset: str | None
    client_charset: str | None
    connection_charset: str | None
    collation_connection: str | None
    can_read_comments: bool
    can_convert_utf8mb4: bool
    info_schema_charset: str | None

    def is_healthy(self) -> bool:
        """¿El servidor está en buen estado para lectura utf8mb4?"""
        return self.state == CharsetState.UTF8MB4_CLEAN

    def requires_remediation(self) -> bool:
        """¿Requiere intervención manual?"""
        return self.state in (CharsetState.LATIN1_MISMATCH, CharsetState.UTF8MB3_LEGACY)

    def recommendation(self) -> str:
        """Acción recomendada."""
        if self.state == CharsetState.UTF8MB4_CLEAN:
            return "✅ OK: No action needed"
        elif self.state == CharsetState.UTF8MB4_MIXED:
            return "⚠️ MIXED: Using CONVERT() for comment/definition fields (98% perf)"
        elif self.state == CharsetState.UTF8MB3_LEGACY:
            return "❌ LEGACY: Downgrading to latin1 for metadata reading (85% perf)"
        elif self.state == CharsetState.LATIN1_MISMATCH:
            return "🔴 MISMATCH: ALTER DATABASE schema CHARACTER SET utf8mb4 REQUIRED"
        else:
            return "❓ UNKNOWN: Falling back to fail-fast strategy"


class CharsetStateDetector:
    """Detecta el estado de charset de un servidor MariaDB sin lanzar excepciones.

    Implementa detección de 4 estados comunes + fallback a unknown para casos no controlados.
    Todos los métodos están diseñados para no lanzar excepciones; devuelven valores seguros.

    Args:
        connection: Conexión DB-API 2.0 abierta (mariadb, pymysql, etc.).
        paramstyle: `paramstyle` del driver (p.ej. "named", "qmark", "format").

    Example:
        >>> detector = CharsetStateDetector(conn, "named")
        >>> diagnosis = detector.diagnose()
        >>> if not diagnosis.is_healthy():
        ...     logger.warning(f"Charset issue: {diagnosis.recommendation()}")
    """

    def __init__(self, connection: Any, paramstyle: str) -> None:
        self.connection = connection
        self.paramstyle = paramstyle

    def _fetch_one(self, sql: str, params: dict[str, Any] | None = None) -> Any:
        """Ejecuta query simple, retorna primer valor o None en caso de error."""
        if params is None:
            params = {}
        try:
            cursor = self.connection.cursor()
            try:
                # Traducir SQL de catálogo al paramstyle del driver
                driver_sql = self._translate_sql(sql, params)
                if isinstance(driver_sql, tuple):
                    cursor.execute(driver_sql[0], driver_sql[1])
                else:
                    cursor.execute(driver_sql)
                row = cursor.fetchone()
                return row[0] if row else None
            finally:
                cursor.close()
        except Exception as exc:
            logger.debug(f"_fetch_one() failed: {exc}")
            return None

    def _translate_sql(self, sql: str, params: dict[str, Any]) -> str | tuple[str, Any]:
        """Traduce SQL con :nombre a paramstyle del driver (naive; paramstyle='named' es pass-through)."""
        # En v0.33.0 usamos paramstyle='named' (heredado de paramstyle de driver)
        # La traducción completa requiere _paramstyle.to_driver(), pero aquí es simple
        if self.paramstyle == "named":
            return sql
        elif self.paramstyle == "format":
            # :schema → %s; params → list en orden
            import re

            placeholders = sorted(re.findall(r":(\w+)", sql), reverse=True)
            translated_sql = sql
            for name in placeholders:
                translated_sql = translated_sql.replace(f":{name}", "%s", 1)
            args = [params.get(name) for name in sorted(params.keys())]
            return translated_sql, tuple(args)
        elif self.paramstyle == "qmark":
            import re

            names_ordered = re.findall(r":(\w+)", sql)
            if not names_ordered:
                return sql
            translated_sql = re.sub(r":\w+", "?", sql)
            args = [params.get(n) for n in names_ordered]
            return translated_sql, tuple(args)
        else:
            return sql

    def diagnose(self) -> CharsetDiagnosis:
        """Realiza diagnóstico completo de charset sin excepciones."""
        server_charset = self._fetch_one("SELECT @@character_set_server")
        database_charset = self._fetch_one("SELECT @@character_set_database")
        client_charset = self._fetch_one("SELECT @@character_set_client")
        connection_charset = self._fetch_one("SELECT @@character_set_connection")
        collation_connection = self._fetch_one("SELECT @@collation_connection")

        # Normalizar valores (MariaDB puede devolver bytes)
        server_charset = str(server_charset).lower() if server_charset else None
        database_charset = str(database_charset).lower() if database_charset else None
        client_charset = str(client_charset).lower() if client_charset else None
        connection_charset = str(connection_charset).lower() if connection_charset else None

        # Pruebas especializadas
        can_read_comments = self._test_read_comments()
        can_convert_utf8mb4 = self._test_convert_utf8mb4()
        info_schema_charset = self._test_info_schema_charset()

        # connection_charset es el encoding real de la sesión activa (lo que importa para leer datos)
        state = self._determine_state(
            server_charset, database_charset, info_schema_charset, can_read_comments, connection_charset
        )

        return CharsetDiagnosis(
            state=state,
            server_charset=server_charset,
            database_charset=database_charset,
            client_charset=client_charset,
            connection_charset=connection_charset,
            collation_connection=collation_connection,
            can_read_comments=can_read_comments,
            can_convert_utf8mb4=can_convert_utf8mb4,
            info_schema_charset=info_schema_charset,
        )

    def _test_read_comments(self) -> bool:
        """¿Se pueden leer comentarios de tabla sin error?"""
        # _fetch_one() captura excepciones internamente; retorna None si falla
        result = self._fetch_one(
            "SELECT TABLE_COMMENT FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() LIMIT 1"
        )
        return result is not None

    def _test_convert_utf8mb4(self) -> bool:
        """¿La función CONVERT() está disponible y funciona?"""
        try:
            result = self._fetch_one("SELECT CONVERT('test' USING utf8mb4)")
            return result is not None
        except Exception as exc:
            logger.debug(f"_test_convert_utf8mb4 failed: {exc}")
            return False

    def _test_info_schema_charset(self) -> str | None:
        """¿En qué charset tiene configurado la BD actual? (detección post-upgrade)."""
        try:
            # SCHEMATA.DEFAULT_CHARACTER_SET_NAME es compatible con MariaDB y MySQL
            charset: str | None = self._fetch_one(
                "SELECT DEFAULT_CHARACTER_SET_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = DATABASE()"
            )
            return charset
        except Exception as exc:
            logger.debug(f"_test_info_schema_charset failed: {exc}")
            return None

    @staticmethod
    def _determine_state(
        server_charset: str | None,
        database_charset: str | None,
        info_schema_charset: str | None,
        can_read_comments: bool,
        connection_charset: str | None = None,
    ) -> CharsetState:
        """Lógica de diagnóstico para determinar estado."""

        # Prioritario: la sesión activa usa utf8mb4 y la BD también → el global del servidor no importa: el charset
        # de los datos lo fija la BD/tabla, y si la lectura nativa falla (SystemError) el ejecutor cae a CONVERT.
        if connection_charset == "utf8mb4" and database_charset == "utf8mb4":
            if info_schema_charset is not None and info_schema_charset not in ("utf8mb4",):
                return CharsetState.UTF8MB4_MIXED
            if can_read_comments:
                return CharsetState.UTF8MB4_CLEAN
            return CharsetState.UTF8MB4_MIXED

        # MISMATCH real: la sesión usa latin1 pero la BD es utf8mb4 (sin SET NAMES utf8mb4)
        if database_charset == "utf8mb4" and (connection_charset or "").startswith("latin"):
            return CharsetState.LATIN1_MISMATCH

        # Caso 1a: Server utf8mb4 pero DB latin1 (fallback sin connection_charset)
        if server_charset == "utf8mb4" and database_charset == "latin1":
            return CharsetState.LATIN1_MISMATCH

        # Caso 2: Server utf8mb4 pero información_schema tiene utf8mb3 (MIXED POST-UPGRADE)
        if server_charset == "utf8mb4" and info_schema_charset != "utf8mb4" and database_charset == "utf8mb4":
            return CharsetState.UTF8MB4_MIXED

        # Caso 3: Ambos en utf8mb4 y sin errores de lectura (LIMPIO)
        if server_charset == "utf8mb4" and database_charset == "utf8mb4" and can_read_comments:
            return CharsetState.UTF8MB4_CLEAN

        # Caso 4: Ambos en utf8mb3 (LEGACY)
        if (server_charset or "").startswith("utf8") and "utf8mb4" not in (server_charset or ""):
            return CharsetState.UTF8MB3_LEGACY

        # Fallback: No determinable
        return CharsetState.UNKNOWN


__all__ = [
    "CharsetDiagnosis",
    "CharsetState",
    "CharsetStateDetector",
]
