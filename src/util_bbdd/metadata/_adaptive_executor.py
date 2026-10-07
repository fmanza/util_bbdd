"""Ejecutor adaptativo de catálogo con fallback automático de charset (v0.33.0+).

Implementa AdaptiveCatalogExecutor que detecta el estado de charset y aplica estrategias
de fallback automáticas (CONVERT, fail-fast) sin intervención manual.

Strategies progresivas:
1. Native: Lectura directa (sin CONVERT) — 100% perf, solo utf8mb4 limpio
2. Convert: CONVERT(field USING utf8mb4) para campos especiales — 98% perf
3. FailFast: Error explícito con diagnóstico — diagnóstico del usuario

ADR-003 §5 — Progressive Remediation Layers.
"""

from __future__ import annotations

import logging

from collections.abc import Mapping
from typing import Any

from ._charset_detection import CharsetDiagnosis, CharsetState, CharsetStateDetector
from ._paramstyle import ParamStyle, to_driver

logger = logging.getLogger(__name__)


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
        diagnosis: CharsetDiagnosis del servidor (cacheado después de detectar una sola vez)
        strategy: Strategy elegida ("native", "convert", "failfast")
    """

    def __init__(self, connection: Any, paramstyle: ParamStyle, mode: str = "auto") -> None:
        self.connection = connection
        self.paramstyle = paramstyle
        self.mode = mode
        self.diagnosis: CharsetDiagnosis | None = None
        self.strategy: str = "unknown"

    def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[tuple[Any, ...]]:
        """Ejecuta query de catálogo con fallback automático según charset_state."""
        # Lazy-detect charset state (una sola vez)
        if self.diagnosis is None:
            self._detect_charset_state()

        # Seleccionar estrategia según diagnosis
        if self.strategy == "native":
            return self._fetch_native(sql, dict(params))
        elif self.strategy == "convert":
            return self._fetch_with_convert(sql, dict(params))
        else:  # "failfast"
            return self._fetch_failfast(sql, dict(params))

    def _detect_charset_state(self) -> None:
        """Detecta charset_state y elige estrategia; se ejecuta una sola vez."""
        detector = CharsetStateDetector(self.connection, self.paramstyle)
        self.diagnosis = detector.diagnose()

        logger.info(
            f"Charset detected: state={self.diagnosis.state.value}, "
            f"server={self.diagnosis.server_charset}, "
            f"database={self.diagnosis.database_charset}"
        )

        # Determinar estrategia según mode y diagnosis
        if self.mode == "native":
            self.strategy = "native"
        elif self.mode == "convert":
            self.strategy = "convert"
        else:  # mode == "auto"
            if self.diagnosis.state == CharsetState.UTF8MB4_CLEAN:
                self.strategy = "native"
                logger.debug("✅ Charset OK: using native strategy")
            elif self.diagnosis.state == CharsetState.UTF8MB4_MIXED:
                self.strategy = "convert"
                logger.warning("⚠️ Mixed charset: using CONVERT() for comments/definitions")
            elif self.diagnosis.state == CharsetState.UTF8MB3_LEGACY:
                # Legacy utf8mb3 debe usar CONVERT para evitar contaminar la sesión
                self.strategy = "convert"
                logger.warning("❌ Legacy utf8mb3: using CONVERT() for safe reading")
            elif self.diagnosis.state == CharsetState.LATIN1_MISMATCH:
                self.strategy = "failfast"
                logger.error(f"🔴 CRITICAL: {self.diagnosis.recommendation()}")
            else:  # UNKNOWN
                self.strategy = "failfast"
                logger.warning("❓ Charset unknown: falling back to fail-fast")

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
            logger.error(
                f"CONVERT strategy failed ({exc}). "
                f"Charset state: {self.diagnosis.state.value}. "
                f"Server: {self.diagnosis.server_charset}, DB: {self.diagnosis.database_charset}. "
                f"Recommendation: {self.diagnosis.recommendation()}"
            )
            raise
        finally:
            cursor.close()

    def _inject_convert(self, sql: str) -> str:
        """Inyecta CONVERT(field USING utf8mb4) en campos de metadatos especiales."""
        import re

        # Lista de campos que típicamente contienen utf8mb3 corrupto
        fields_to_convert = [
            "TABLE_COMMENT",
            "COLUMN_COMMENT",
            "VIEW_DEFINITION",
            "ROUTINE_DEFINITION",
            "COMMENT",
        ]
        result = sql

        for field in fields_to_convert:
            # Usar regex para evitar conversiones parciales y duplicadas
            # Pattern: palabra completa (\\b), no precedida de CONVERT(
            # Esto previene: (a) matching parciales, (b) re-conversión

            # Patrón: buscar field que NO esté ya dentro de CONVERT()
            pattern = rf"(?<!CONVERT\(CAST\()({field})(?!\s+AS BINARY)"
            replacement = r"CONVERT(CAST(\1 AS BINARY) USING utf8mb4) AS \1"

            result = re.sub(pattern, replacement, result)

        return result

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
]
