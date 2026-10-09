"""Ejecutor adaptativo de catálogo con fallback automático de charset (v0.33.0+).

Implementa AdaptiveCatalogExecutor que detecta el estado de charset y aplica estrategias
de fallback automáticas (CONVERT, fail-fast) sin intervención manual.

Strategies progresivas:
1. Native: Lectura directa (sin CONVERT) — 100% perf, solo utf8mb4 limpio
2. Convert: CONVERT(field USING utf8mb4) para campos especiales — 98% perf (utf8mb4_mixed, latin1_mismatch)
3. FailFast: Error explícito con diagnóstico — solo para charset desconocido (unknown)

ADR-003 §5 — Progressive Remediation Layers.
"""

from __future__ import annotations

import logging
import re

from collections.abc import Mapping
from typing import Any

from ._charset_detection import CharsetDiagnosis, CharsetState, CharsetStateDetector
from ._paramstyle import ParamStyle, to_driver

logger = logging.getLogger(__name__)


def select_strategy(diagnosis: CharsetDiagnosis, mode: str = "auto") -> str:
    """Estrategia de lectura del catálogo (``native``, ``convert``, ``failfast``) para un diagnóstico de charset.

    Compartida por :class:`AdaptiveCatalogExecutor` (sync) y el ejecutor async de los managers.
    """
    logger.info(
        f"Charset detected: state={diagnosis.state.value}, "
        f"server={diagnosis.server_charset}, "
        f"database={diagnosis.database_charset}"
    )
    if mode in ("native", "convert"):
        return mode
    if diagnosis.state == CharsetState.UTF8MB4_CLEAN:
        logger.debug("✅ Charset OK: using native strategy")
        return "native"
    if diagnosis.state == CharsetState.UTF8MB4_MIXED:
        logger.warning("⚠️ Mixed charset: using CONVERT() for comments/definitions")
        return "convert"
    if diagnosis.state == CharsetState.UTF8MB3_LEGACY:
        # Legacy utf8mb3 debe usar CONVERT para evitar contaminar la sesión
        logger.warning("❌ Legacy utf8mb3: using CONVERT() for safe reading")
        return "convert"
    if diagnosis.state == CharsetState.LATIN1_MISMATCH:
        logger.warning(f"⚠️ latin1_mismatch: usando CONVERT() para lectura de metadatos. {diagnosis.recommendation()}")
        return "convert"
    logger.warning("❓ Charset unknown: falling back to fail-fast")
    return "failfast"


def inject_convert(sql: str) -> str:
    """Inyecta CONVERT(CAST(field AS BINARY) USING utf8mb4) en campos de metadatos especiales.

    Dos fases por campo:
    1. Actualiza la forma simple CONVERT(field USING charset) al equivalente CAST+BINARY.
    2. Envuelve referencias sueltas al campo que no estén ya en ningún CONVERT.
    """
    fields_to_convert = [
        "TABLE_COMMENT",
        "COLUMN_COMMENT",
        "VIEW_DEFINITION",
        "ROUTINE_DEFINITION",
        "COMMENT",
    ]
    # Sin alias AS \1: los callers acceden por índice (tupla), y AS genera SQL inválido en WHERE/ORDER BY.
    _conv = r"CONVERT(CAST(\1 AS BINARY) USING utf8mb4)"
    result = sql

    for field in fields_to_convert:
        # Fase 1: CONVERT(field USING charset) → CONVERT(CAST(field AS BINARY) USING utf8mb4)
        pattern_wrapped = rf"CONVERT\(\s*\b({field})\b\s+USING\s+\w+\)"
        result = re.sub(pattern_wrapped, _conv, result)

        # Fase 2: field suelto no ya dentro de CAST/CONVERT ni como alias.
        # (?<! AS ) evita re-procesar "AS field" presentes en el SQL original.
        # (?!\s+AS\s+BINARY) evita re-envolver el field dentro de CAST(field AS BINARY).
        # (?!\s+USING) evita re-procesar formas CONVERT(field USING ...) residuales.
        pattern_standalone = rf"(?<! AS )\b({field})\b(?!\s+AS\s+BINARY)(?!\s+USING)"
        result = re.sub(pattern_standalone, _conv, result)

    return result


class AdaptiveCatalogExecutor:
    """Ejecutor de catálogo con fallback automático según estado de charset.

    Envuelve un DbapiCatalogExecutor y aplica strategies de fallback:
    1. Detecta charset_state del servidor (utf8mb4_clean, utf8mb4_mixed, utf8mb3_legacy, etc.)
    2. Selecciona strategy apropiada (native, convert, failfast)
    3. Ejecuta con retry automático en caso de error de charset

    Args:
        connection: Conexión DB-API abierta.
        paramstyle: paramstyle del driver ("named", "format", "qmark", etc.).
        mode: Modo adaptativo ("auto", "native", "convert").
            - "auto" (default): Detecta estado y elige strategy
            - "native": Intenta solo sin CONVERT (falla si hay problemas)
            - "convert": Siempre usa CONVERT() (más lento pero seguro)

    Attributes:
        diagnosis: CharsetDiagnosis del servidor (cacheado después de detectar una sola vez; ``None`` con
            ``mode`` ``native``/``convert``, que no diagnostican)
        strategy: Strategy elegida ("native", "convert", "failfast")
    """

    def __init__(self, connection: Any, paramstyle: ParamStyle, mode: str = "auto") -> None:
        self.connection = connection
        self.paramstyle: ParamStyle = paramstyle
        self.mode = mode
        self.diagnosis: CharsetDiagnosis | None = None
        self.strategy: str = "unknown"

    def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
        """Ejecuta query de catálogo con fallback automático según charset_state."""
        # Lazy-detect charset state (una sola vez; con mode native/convert no hay diagnóstico)
        if self.strategy == "unknown":
            self._detect_charset_state()

        # Seleccionar estrategia según diagnosis
        if self.strategy == "native":
            return self._fetch_native(sql, dict(params))
        elif self.strategy == "convert":
            return self._fetch_with_convert(sql, dict(params))
        else:  # "failfast"
            return self._fetch_failfast(sql, dict(params))

    def _detect_charset_state(self) -> None:
        """Detecta charset_state y elige estrategia; se ejecuta una sola vez.

        Con ``mode`` ``native`` o ``convert`` la estrategia es el propio modo y no se lanza el diagnóstico.
        """
        if self.mode in ("native", "convert"):
            self.strategy = self.mode  # diagnosis queda en None: no se ha diagnosticado
            return
        detector = CharsetStateDetector(self.connection, self.paramstyle)
        self.diagnosis = detector.diagnose()
        self.strategy = select_strategy(self.diagnosis, self.mode)

    def _fetch_native(self, sql: str, params: dict[str, Any]) -> list[tuple[Any, ...]]:
        """Estrategia 1: Lectura directa sin CONVERT (100% perf, solo utf8mb4 limpio)."""
        driver_sql, args = to_driver(sql, params, self.paramstyle)
        cursor = self.connection.cursor()
        try:
            if args is None:
                cursor.execute(driver_sql)
            else:
                cursor.execute(driver_sql, args)
            return [tuple(row) for row in cursor.fetchall()]
        except SystemError as exc:
            # Si falla en native, intentar convert
            logger.warning(f"Native strategy failed ({exc}), trying CONVERT...")
            self.strategy = "convert"
            return self._fetch_with_convert(sql, params)
        finally:
            cursor.close()

    def _fetch_with_convert(self, sql: str, params: dict[str, Any]) -> list[tuple[Any, ...]]:
        """Estrategia 2: Inyecta CONVERT() en campos especiales (98% perf, utf8mb4_mixed)."""
        # En v0.33.0, se inyecta CONVERT() en campos conocidos que pueden estar en utf8mb3:
        # - TABLE_COMMENT, COLUMN_COMMENT, VIEW_DEFINITION, ROUTINE_DEFINITION
        sql_with_convert = self._inject_convert(sql)
        driver_sql, args = to_driver(sql_with_convert, params, self.paramstyle)
        cursor = self.connection.cursor()
        try:
            if args is None:
                cursor.execute(driver_sql)
            else:
                cursor.execute(driver_sql, args)
            return [tuple(row) for row in cursor.fetchall()]
        except SystemError as exc:
            # Si falla CONVERT, reportar diagnóstico detallado y fallar
            assert self.diagnosis is not None, "diagnosis should be set by _detect_charset_state"
            diagnosis_msg = (
                f"CONVERT strategy failed: {exc}\n"
                f"Diagnosis: {self.diagnosis.state.value}\n"
                f"Server: {self.diagnosis.server_charset}, DB: {self.diagnosis.database_charset}, "
                f"Connection: {self.diagnosis.connection_charset}\n"
                f"Recommendation: {self.diagnosis.recommendation()}"
            )
            logger.error(diagnosis_msg)
            raise SystemError(diagnosis_msg) from exc
        finally:
            cursor.close()

    def _inject_convert(self, sql: str) -> str:
        """Ver :func:`inject_convert`."""
        return inject_convert(sql)

    def _fetch_failfast(self, sql: str, params: dict[str, Any]) -> list[tuple[Any, ...]]:
        """Estrategia 3: Error explícito con diagnóstico detallado (fail-fast v0.32.1)."""
        driver_sql, args = to_driver(sql, params, self.paramstyle)
        cursor = self.connection.cursor()
        try:
            if args is None:
                cursor.execute(driver_sql)
            else:
                cursor.execute(driver_sql, args)
            return [tuple(row) for row in cursor.fetchall()]
        except SystemError as exc:
            # Generar mensaje de diagnóstico detallado
            diagnosis_msg: str
            if self.diagnosis is not None:
                diagnosis_msg = (
                    f"SystemError during metadata reading: {exc}\n"
                    f"Diagnosis: {self.diagnosis.state.value}\n"
                    f"Server charset: {self.diagnosis.server_charset}\n"
                    f"Database charset: {self.diagnosis.database_charset}\n"
                    f"Recommendation: {self.diagnosis.recommendation()}"
                )
            else:
                diagnosis_msg = f"SystemError during metadata reading: {exc}"
            logger.exception(diagnosis_msg)
            raise SystemError(diagnosis_msg) from exc
        finally:
            cursor.close()


__all__ = [
    "AdaptiveCatalogExecutor",
    "inject_convert",
    "select_strategy",
]
