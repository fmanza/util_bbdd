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

from ..async_utils import maybe_await

logger = logging.getLogger(__name__)

#: Variables de sesión del diagnóstico, en orden: servidor, BD, cliente, conexión, collation de la conexión.
_VARIABLES_SQL: tuple[str, str, str, str, str] = (
    "SELECT @@character_set_server",
    "SELECT @@character_set_database",
    "SELECT @@character_set_client",
    "SELECT @@character_set_connection",
    "SELECT @@collation_connection",
)
_READ_COMMENTS_SQL = "SELECT TABLE_COMMENT FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() LIMIT 1"
_CONVERT_SQL = "SELECT CONVERT('test' USING utf8mb4)"
_SCHEMATA_SQL = "SELECT DEFAULT_CHARACTER_SET_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = DATABASE()"
#: Todo el diagnóstico en un viaje: las 5 variables, el comentario de una tabla, ``CONVERT`` y el charset del schema.
#: Si falla (p. ej. un comentario que no se puede decodificar, H-32), se repiten las consultas sueltas de arriba para
#: saber qué parte falla.
_DIAGNOSIS_SQL = (
    "SELECT @@character_set_server, @@character_set_database, @@character_set_client, @@character_set_connection, "
    f"@@collation_connection, ({_READ_COMMENTS_SQL}), CONVERT('test' USING utf8mb4), ({_SCHEMATA_SQL})"
)
_DIAGNOSIS_COLUMNS = 8


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
        paramstyle: `paramstyle` del driver. Se conserva por compatibilidad de firma: las consultas de diagnóstico
            son literales y no necesitan traducción.

    Example:
        >>> detector = CharsetStateDetector(conn, "named")
        >>> diagnosis = detector.diagnose()
        >>> if not diagnosis.is_healthy():
        ...     logger.warning(f"Charset issue: {diagnosis.recommendation()}")
    """

    def __init__(self, connection: Any, paramstyle: str) -> None:
        self.connection = connection
        self.paramstyle = paramstyle

    def _fetch_one(self, sql: str) -> Any:
        """Ejecuta una consulta literal (sin parámetros) y devuelve el primer valor, o None si falla."""
        try:
            cursor = self.connection.cursor()
            try:
                cursor.execute(sql)
                row = cursor.fetchone()
                return row[0] if row else None
            finally:
                cursor.close()
        except Exception as exc:
            logger.debug(f"_fetch_one() failed: {exc}")
            return None

    def _fetch_row(self, sql: str) -> tuple[Any, ...] | None:
        """Ejecuta una consulta literal y devuelve su primera fila, o None si falla (al ejecutar o al leer)."""
        try:
            cursor = self.connection.cursor()
            try:
                cursor.execute(sql)
                row = cursor.fetchone()
                return tuple(row) if row is not None else None
            finally:
                cursor.close()
        except Exception as exc:
            logger.debug(f"_fetch_row() failed: {exc}")
            return None

    def diagnose(self) -> CharsetDiagnosis:
        """Realiza diagnóstico completo de charset sin excepciones: una consulta, o las sueltas si esa falla."""
        row = self._fetch_row(_DIAGNOSIS_SQL)
        if row is not None and len(row) == _DIAGNOSIS_COLUMNS:
            return self.diagnosis_from_row(row)
        return self._diagnose_one_by_one()

    @classmethod
    def diagnosis_from_row(cls, row: tuple[Any, ...]) -> CharsetDiagnosis:
        """``CharsetDiagnosis`` desde la fila de ``_DIAGNOSIS_SQL`` (compartido por :meth:`diagnose` y :func:`adiagnose`)."""
        server, database, client, connection, collation, _comment, converted, schema_charset = row
        return cls.build_diagnosis(
            server,
            database,
            client,
            connection,
            collation,
            # La consulta se leyó sin error: los comentarios se pueden leer aunque el schema no tenga tablas (NULL).
            can_read_comments=True,
            can_convert_utf8mb4=converted is not None,
            info_schema_charset=schema_charset,
        )

    def _diagnose_one_by_one(self) -> CharsetDiagnosis:
        """Diagnóstico con una consulta por dato (8 viajes): solo si la consulta combinada falla."""
        server, database, client, connection, collation = (self._fetch_one(sql) for sql in _VARIABLES_SQL)
        return self.build_diagnosis(
            server,
            database,
            client,
            connection,
            collation,
            can_read_comments=self._test_read_comments(),
            can_convert_utf8mb4=self._test_convert_utf8mb4(),
            info_schema_charset=self._test_info_schema_charset(),
        )

    @classmethod
    def build_diagnosis(
        cls,
        server_charset: Any,
        database_charset: Any,
        client_charset: Any,
        connection_charset: Any,
        collation_connection: Any,
        *,
        can_read_comments: bool,
        can_convert_utf8mb4: bool,
        info_schema_charset: str | None,
    ) -> CharsetDiagnosis:
        """``CharsetDiagnosis`` a partir de los valores leídos (compartido por :meth:`diagnose` y :func:`adiagnose`)."""
        # Normalizar valores (MariaDB puede devolver bytes)
        server = str(server_charset).lower() if server_charset else None
        database = str(database_charset).lower() if database_charset else None
        client = str(client_charset).lower() if client_charset else None
        connection = str(connection_charset).lower() if connection_charset else None

        # connection_charset es el encoding real de la sesión activa (lo que importa para leer datos)
        state = cls._determine_state(server, database, info_schema_charset, can_read_comments, connection)

        return CharsetDiagnosis(
            state=state,
            server_charset=server,
            database_charset=database,
            client_charset=client,
            connection_charset=connection,
            collation_connection=collation_connection,
            can_read_comments=can_read_comments,
            can_convert_utf8mb4=can_convert_utf8mb4,
            info_schema_charset=info_schema_charset,
        )

    def _test_read_comments(self) -> bool:
        """¿Se pueden leer comentarios de tabla sin error? Un schema sin tablas (sin filas) cuenta como legible."""
        try:
            cursor = self.connection.cursor()
            try:
                cursor.execute(_READ_COMMENTS_SQL)
                cursor.fetchone()
                return True
            finally:
                cursor.close()
        except Exception as exc:
            logger.debug(f"_test_read_comments() failed: {exc}")
            return False

    def _test_convert_utf8mb4(self) -> bool:
        """¿La función CONVERT() está disponible y funciona?"""
        try:
            result = self._fetch_one(_CONVERT_SQL)
            return result is not None
        except Exception as exc:
            logger.debug(f"_test_convert_utf8mb4 failed: {exc}")
            return False

    def _test_info_schema_charset(self) -> str | None:
        """¿En qué charset tiene configurado la BD actual? (detección post-upgrade)."""
        try:
            # SCHEMATA.DEFAULT_CHARACTER_SET_NAME es compatible con MariaDB y MySQL
            charset: str | None = self._fetch_one(_SCHEMATA_SQL)
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


async def _afetch_one(connection: Any, sql: str) -> Any:
    """Versión async de ``CharsetStateDetector._fetch_one`` (SQL sin parámetros): primer valor o ``None`` si falla."""
    try:
        cursor = await maybe_await(connection.cursor())
        try:
            await maybe_await(cursor.execute(sql))
            row = await maybe_await(cursor.fetchone())
            return row[0] if row else None
        finally:
            await maybe_await(cursor.close())
    except Exception as exc:
        logger.debug(f"_afetch_one() failed: {exc}")
        return None


async def _afetch_row(connection: Any, sql: str) -> tuple[Any, ...] | None:
    """Versión async de ``CharsetStateDetector._fetch_row``: primera fila o ``None`` si falla."""
    try:
        cursor = await maybe_await(connection.cursor())
        try:
            await maybe_await(cursor.execute(sql))
            row = await maybe_await(cursor.fetchone())
            return tuple(row) if row is not None else None
        finally:
            await maybe_await(cursor.close())
    except Exception as exc:
        logger.debug(f"_afetch_row() failed: {exc}")
        return None


async def _aquery_reads(connection: Any, sql: str) -> bool:
    """¿Se ejecuta y lee ``sql`` sin error? (sin filas cuenta como legible)."""
    try:
        cursor = await maybe_await(connection.cursor())
        try:
            await maybe_await(cursor.execute(sql))
            await maybe_await(cursor.fetchone())
            return True
        finally:
            await maybe_await(cursor.close())
    except Exception as exc:
        logger.debug(f"_aquery_reads() failed: {exc}")
        return False


async def adiagnose(connection: Any) -> CharsetDiagnosis:
    """Diagnóstico de charset sobre una conexión async (aiomysql); mismas consultas y reglas que ``diagnose()``."""
    row = await _afetch_row(connection, _DIAGNOSIS_SQL)
    if row is not None and len(row) == _DIAGNOSIS_COLUMNS:
        return CharsetStateDetector.diagnosis_from_row(row)
    server, database, client, conn_charset, collation = [await _afetch_one(connection, sql) for sql in _VARIABLES_SQL]
    return CharsetStateDetector.build_diagnosis(
        server,
        database,
        client,
        conn_charset,
        collation,
        can_read_comments=await _aquery_reads(connection, _READ_COMMENTS_SQL),
        can_convert_utf8mb4=await _afetch_one(connection, _CONVERT_SQL) is not None,
        info_schema_charset=await _afetch_one(connection, _SCHEMATA_SQL),
    )


__all__ = [
    "CharsetDiagnosis",
    "CharsetState",
    "CharsetStateDetector",
    "adiagnose",
]
