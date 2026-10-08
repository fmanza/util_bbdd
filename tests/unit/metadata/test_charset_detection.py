"""Tests para CharsetStateDetector y AdaptiveCatalogExecutor (v0.33.0+).

Verifica que la detección automática de charset funciona correctamente y que el fallback
se aplica apropiadamente para diferentes estados de charset.
"""

from __future__ import annotations

from unittest import mock

import pytest

from util_bbdd.metadata._adaptive_executor import AdaptiveCatalogExecutor
from util_bbdd.metadata._charset_detection import (
    CharsetDiagnosis,
    CharsetState,
    CharsetStateDetector,
)


class TestCharsetStateDetector:
    """Tests para CharsetStateDetector.diagnose()."""

    def test_diagnose_utf8mb4_clean(self) -> None:
        """✅ Servidor y BD en utf8mb4 limpio."""
        conn = mock.MagicMock()
        cursor_mock = mock.MagicMock()
        conn.cursor.return_value = cursor_mock

        # Mock de resultados: utf8mb4_clean
        fetch_results = [
            ("utf8mb4",),  # @@character_set_server
            ("utf8mb4",),  # @@character_set_database
            ("utf8mb4",),  # @@character_set_client
            ("utf8mb4",),  # @@character_set_connection
            ("utf8mb4_unicode_ci",),  # @@collation_connection
            (True,),  # can_read_comments (_test_read_comments devuelve True)
            (True,),  # can_convert_utf8mb4 (_test_convert_utf8mb4 devuelve True)
            ("utf8mb4",),  # info_schema_charset (_test_info_schema_charset devuelve utf8mb4)
        ]
        cursor_mock.fetchone.side_effect = fetch_results + [(None,)] * 10
        cursor_mock.execute.return_value = None

        detector = CharsetStateDetector(conn, "named")
        diagnosis = detector.diagnose()

        assert diagnosis.state == CharsetState.UTF8MB4_CLEAN
        assert diagnosis.server_charset == "utf8mb4"
        assert diagnosis.database_charset == "utf8mb4"
        assert diagnosis.is_healthy() is True
        assert diagnosis.requires_remediation() is False

    def test_diagnose_utf8mb3_legacy(self) -> None:
        """❌ Servidor y BD en utf8mb3 (legacy)."""
        conn = mock.MagicMock()
        cursor_mock = mock.MagicMock()
        conn.cursor.return_value = cursor_mock

        # Mock de resultados: utf8mb3_legacy
        fetch_results = [
            ("utf8",),  # @@character_set_server (utf8 = utf8mb3 en MariaDB)
            ("utf8",),  # @@character_set_database
            ("utf8",),  # @@character_set_client
            ("utf8",),  # @@character_set_connection
            ("utf8_general_ci",),  # @@collation_connection
        ]
        cursor_mock.fetchone.side_effect = fetch_results + [(None,)] * 10
        cursor_mock.execute.return_value = None

        detector = CharsetStateDetector(conn, "named")
        diagnosis = detector.diagnose()

        assert diagnosis.state == CharsetState.UTF8MB3_LEGACY
        assert diagnosis.server_charset == "utf8"
        assert diagnosis.requires_remediation() is True

    def test_diagnose_latin1_mismatch(self) -> None:
        """🔴 Server utf8mb4 pero BD en latin1 (critical mismatch)."""
        conn = mock.MagicMock()
        cursor_mock = mock.MagicMock()
        conn.cursor.return_value = cursor_mock

        # Mock de resultados: latin1_mismatch
        fetch_results = [
            ("utf8mb4",),  # @@character_set_server
            ("latin1",),  # @@character_set_database ← MISMATCH
            ("utf8mb4",),  # @@character_set_client
            ("utf8mb4",),  # @@character_set_connection
            ("utf8mb4_unicode_ci",),  # @@collation_connection
        ]
        cursor_mock.fetchone.side_effect = fetch_results + [(None,)] * 10
        cursor_mock.execute.return_value = None

        detector = CharsetStateDetector(conn, "named")
        diagnosis = detector.diagnose()

        assert diagnosis.state == CharsetState.LATIN1_MISMATCH
        assert diagnosis.database_charset == "latin1"
        assert diagnosis.requires_remediation() is True
        assert "ALTER DATABASE" in diagnosis.recommendation()

    def test_diagnose_latin1_mismatch_inverse(self) -> None:
        """✅ Server latin1 pero sesión y BD en utf8mb4 → UTF8MB4_CLEAN (escenario de producción válido)."""
        conn = mock.MagicMock()
        cursor_mock = mock.MagicMock()
        conn.cursor.return_value = cursor_mock

        # server global=latin1 pero SET NAMES utf8mb4 ejecutado → sesión y BD son utf8mb4
        fetch_results = [
            ("latin1",),  # @@character_set_server ← global del servidor, no indica problema
            ("utf8mb4",),  # @@character_set_database
            ("utf8mb4",),  # @@character_set_client ← SET NAMES ejecutado
            ("utf8mb4",),  # @@character_set_connection ← lo que importa para leer datos
            ("utf8mb4_unicode_ci",),  # @@collation_connection
            ("Table comment",),  # _test_read_comments ← non-None → can_read_comments=True
            ("test",),  # _test_convert_utf8mb4 ← non-None → True
            (None,),  # _test_info_schema_charset ← None es aceptable
        ]
        cursor_mock.fetchone.side_effect = fetch_results + [(None,)] * 10
        cursor_mock.execute.return_value = None

        detector = CharsetStateDetector(conn, "named")
        diagnosis = detector.diagnose()

        assert diagnosis.state == CharsetState.UTF8MB4_CLEAN
        assert diagnosis.server_charset == "latin1"
        assert diagnosis.database_charset == "utf8mb4"
        assert diagnosis.is_healthy() is True
        assert diagnosis.requires_remediation() is False

    def test_diagnose_utf8mb4_mixed(self) -> None:
        """⚠️ Server utf8mb4 pero información_schema tiene utf8mb3 (post-upgrade)."""
        conn = mock.MagicMock()
        cursor_mock = mock.MagicMock()
        conn.cursor.return_value = cursor_mock

        # Mock de resultados: utf8mb4_mixed
        # Servidor y BD en utf8mb4, pero información_schema en utf8mb3 (post-upgrade artifact)
        fetch_results = [
            ("utf8mb4",),  # @@character_set_server
            ("utf8mb4",),  # @@character_set_database
            ("utf8mb4",),  # @@character_set_client
            ("utf8mb4",),  # @@character_set_connection
            ("utf8mb4_unicode_ci",),  # @@collation_connection
            (True,),  # can_read_comments
            (True,),  # can_convert_utf8mb4
            ("utf8",),  # info_schema_charset (utf8 = utf8mb3 in MySQL/MariaDB)
        ]
        cursor_mock.fetchone.side_effect = fetch_results + [(None,)] * 10
        cursor_mock.execute.return_value = None

        detector = CharsetStateDetector(conn, "named")
        diagnosis = detector.diagnose()

        # Debería detectar definitivamente UTF8MB4_MIXED
        assert diagnosis.state == CharsetState.UTF8MB4_MIXED
        assert diagnosis.server_charset == "utf8mb4"
        assert diagnosis.database_charset == "utf8mb4"
        # UTF8MB4_MIXED se remedia automáticamente con CONVERT, no requiere intervención manual
        assert diagnosis.requires_remediation() is False

    def test_recommendation_messages(self) -> None:
        """Verificar que los mensajes de recomendación son claros."""
        # UTF8MB4_CLEAN
        diagnosis_clean = CharsetDiagnosis(
            state=CharsetState.UTF8MB4_CLEAN,
            server_charset="utf8mb4",
            database_charset="utf8mb4",
            client_charset="utf8mb4",
            connection_charset="utf8mb4",
            collation_connection="utf8mb4_unicode_ci",
            can_read_comments=True,
            can_convert_utf8mb4=True,
            info_schema_charset="utf8mb4",
        )
        assert "OK" in diagnosis_clean.recommendation()

        # LATIN1_MISMATCH
        diagnosis_mismatch = CharsetDiagnosis(
            state=CharsetState.LATIN1_MISMATCH,
            server_charset="utf8mb4",
            database_charset="latin1",
            client_charset="utf8mb4",
            connection_charset="utf8mb4",
            collation_connection="utf8mb4_unicode_ci",
            can_read_comments=False,
            can_convert_utf8mb4=True,
            info_schema_charset=None,
        )
        assert "ALTER DATABASE" in diagnosis_mismatch.recommendation()
        assert diagnosis_mismatch.requires_remediation() is True


class TestAdaptiveCatalogExecutor:
    """Tests para AdaptiveCatalogExecutor con diferentes modos."""

    def test_adaptive_mode_auto_detects_utf8mb4_clean(self) -> None:
        """✅ Modo 'auto' detecta utf8mb4_clean y usa native."""
        conn = mock.MagicMock()
        cursor_mock = mock.MagicMock()
        conn.cursor.return_value = cursor_mock

        # Mock detección de charset
        fetch_results = [
            ("utf8mb4",),  # @@character_set_server
            ("utf8mb4",),  # @@character_set_database
            ("utf8mb4",),  # @@character_set_client
            ("utf8mb4",),  # @@character_set_connection
            ("utf8mb4_unicode_ci",),  # @@collation_connection
            (True,),  # can_read_comments
            (True,),  # can_convert_utf8mb4
            ("utf8mb4",),  # info_schema_charset
        ]
        cursor_mock.fetchone.side_effect = fetch_results + [(("col1",),)] * 10
        cursor_mock.fetchall.return_value = [(("col1",),)]
        cursor_mock.execute.return_value = None

        executor = AdaptiveCatalogExecutor(conn, "named", mode="auto")
        # Trigger detección
        executor._detect_charset_state()

        assert executor.diagnosis is not None
        assert executor.diagnosis.state == CharsetState.UTF8MB4_CLEAN
        assert executor.strategy == "native"

    def test_adaptive_mode_convert_on_legacy(self) -> None:
        """❌ Modo 'auto' con utf8mb3_legacy → convert."""
        conn = mock.MagicMock()
        cursor_mock = mock.MagicMock()
        conn.cursor.return_value = cursor_mock

        # Mock detección de charset: utf8mb3_legacy
        fetch_results = [
            ("utf8",),  # @@character_set_server
            ("utf8",),  # @@character_set_database
            ("utf8",),  # @@character_set_client
            ("utf8",),  # @@character_set_connection
            ("utf8_general_ci",),  # @@collation_connection
            (True,),  # can_read_comments
            (False,),  # can_convert_utf8mb4
            (None,),  # info_schema_charset
        ]
        cursor_mock.fetchone.side_effect = fetch_results + [(("col1",),)] * 10
        cursor_mock.fetchall.return_value = [(("col1",),)]
        cursor_mock.execute.return_value = None

        executor = AdaptiveCatalogExecutor(conn, "named", mode="auto")
        executor._detect_charset_state()

        assert executor.diagnosis is not None
        assert executor.diagnosis.state == CharsetState.UTF8MB3_LEGACY
        assert executor.strategy == "convert"

    def test_adaptive_mode_convert_on_mismatch(self) -> None:
        """🔴 Modo 'auto' con latin1_mismatch → convert (graceful degradation, no failfast)."""
        conn = mock.MagicMock()
        cursor_mock = mock.MagicMock()
        conn.cursor.return_value = cursor_mock

        # latin1_mismatch: server utf8mb4 pero DB latin1
        fetch_results = [
            ("utf8mb4",),  # @@character_set_server
            ("latin1",),  # @@character_set_database ← MISMATCH
            ("utf8mb4",),  # @@character_set_client
            ("utf8mb4",),  # @@character_set_connection
            ("utf8mb4_unicode_ci",),  # @@collation_connection
            (False,),  # can_read_comments
            (True,),  # can_convert_utf8mb4
            (None,),  # info_schema_charset
        ]
        cursor_mock.fetchone.side_effect = fetch_results + [(("col1",),)] * 10
        cursor_mock.fetchall.return_value = [(("col1",),)]
        cursor_mock.execute.return_value = None

        executor = AdaptiveCatalogExecutor(conn, "named", mode="auto")
        executor._detect_charset_state()

        assert executor.diagnosis is not None
        assert executor.diagnosis.state == CharsetState.LATIN1_MISMATCH
        assert executor.strategy == "convert"

    def test_mode_native_explicit(self) -> None:
        """Modo 'native' fuerza estrategia nativa sin detección."""
        conn = mock.MagicMock()
        cursor_mock = mock.MagicMock()
        conn.cursor.return_value = cursor_mock

        # Resultados de detección (ignorados porque mode='native')
        fetch_results = [("utf8mb3",)] * 8
        cursor_mock.fetchone.side_effect = fetch_results + [(("col1",),)] * 10
        cursor_mock.fetchall.return_value = [(("col1",),)]
        cursor_mock.execute.return_value = None

        executor = AdaptiveCatalogExecutor(conn, "named", mode="native")
        executor._detect_charset_state()

        # Aunque detección diga utf8mb3_legacy, modo native lo ignora
        assert executor.strategy == "native"

    def test_mode_convert_explicit(self) -> None:
        """Modo 'convert' fuerza estrategia CONVERT sin importar detección."""
        conn = mock.MagicMock()
        cursor_mock = mock.MagicMock()
        conn.cursor.return_value = cursor_mock

        fetch_results = [("utf8mb4",)] * 8
        cursor_mock.fetchone.side_effect = fetch_results + [(("col1",),)] * 10
        cursor_mock.fetchall.return_value = [(("col1",),)]
        cursor_mock.execute.return_value = None

        executor = AdaptiveCatalogExecutor(conn, "named", mode="convert")
        executor._detect_charset_state()

        assert executor.strategy == "convert"

    def test_inject_convert_in_sql(self) -> None:
        """Verifica que _inject_convert() reemplaza campos especiales."""
        conn = mock.MagicMock()
        executor = AdaptiveCatalogExecutor(conn, "named", mode="convert")

        sql = "SELECT TABLE_COMMENT, COLUMN_COMMENT FROM information_schema.TABLES"
        converted = executor._inject_convert(sql)

        assert "CONVERT(CAST(TABLE_COMMENT AS BINARY) USING utf8mb4)" in converted
        assert "CONVERT(CAST(COLUMN_COMMENT AS BINARY) USING utf8mb4)" in converted

    def test_inject_convert_idempotent(self) -> None:
        """Verifica que _inject_convert() no duplica conversiones."""
        conn = mock.MagicMock()
        executor = AdaptiveCatalogExecutor(conn, "named", mode="convert")

        sql = "SELECT CONVERT(CAST(TABLE_COMMENT AS BINARY) USING utf8mb4) FROM t"
        converted = executor._inject_convert(sql)

        # No debe duplicar CONVERT si ya existe
        assert converted.count("CONVERT") == 1

    def test_inject_convert_comment_not_matched_inside_column_comment(self) -> None:
        """Regresión: COMMENT no debe matchear dentro del alias COLUMN_COMMENT."""
        conn = mock.MagicMock()
        executor = AdaptiveCatalogExecutor(conn, "named", mode="convert")

        sql = "SELECT COLUMN_COMMENT FROM information_schema.COLUMNS"
        converted = executor._inject_convert(sql)

        # COMMENT no debe convertirse por separado dentro de COLUMN_COMMENT. Sin alias AS (v0.35.4): los callers
        # leen por índice y el alias hacía inválido el SQL en WHERE/ORDER BY.
        assert "COLUMN_CONVERT" not in converted
        assert (
            converted == "SELECT CONVERT(CAST(COLUMN_COMMENT AS BINARY) USING utf8mb4) FROM information_schema.COLUMNS"
        )

    def test_inject_convert_upgrades_existing_convert_wrapper(self) -> None:
        """Regresión: CONVERT(field USING utf8mb4) debe ser actualizado a CAST+BINARY."""
        conn = mock.MagicMock()
        executor = AdaptiveCatalogExecutor(conn, "named", mode="convert")

        sql = "SELECT TABLE_NAME, CONVERT(COLUMN_COMMENT USING utf8mb4), CASE WHEN COLLATION_NAME <> x THEN 1 END"
        converted = executor._inject_convert(sql)

        # Debe actualizar la forma simple a CAST+BINARY sin anidar CONVERT dentro de CONVERT (y sin alias AS)
        assert "CONVERT(CAST(COLUMN_COMMENT AS BINARY) USING utf8mb4)," in converted
        # No debe producir formas dobles que generan SQL inválido
        assert "AS COLUMN_COMMENT" not in converted
        assert converted.count("CONVERT(") == 1
        # No debe quedar la forma simple
        assert "CONVERT(COLUMN_COMMENT USING utf8mb4)" not in converted


class TestCharsetDetectionFixes:
    """Tests para los fixes B, C, D aplicados en v0.35.3."""

    # --- Fix C: SCHEMATA query ---

    def test_info_schema_charset_query_uses_schemata(self) -> None:
        """Fix C: _test_info_schema_charset() consulta SCHEMATA no TABLES."""
        conn = mock.MagicMock()
        cursor_mock = mock.MagicMock()
        conn.cursor.return_value = cursor_mock
        cursor_mock.fetchone.return_value = ("utf8mb4",)

        detector = CharsetStateDetector(conn, "named")
        result = detector._test_info_schema_charset()

        assert result == "utf8mb4"
        executed_sql = cursor_mock.execute.call_args[0][0]
        assert "SCHEMATA" in executed_sql
        assert "DEFAULT_CHARACTER_SET_NAME" in executed_sql
        assert "CHARACTER_SET_NAME" not in executed_sql.replace("DEFAULT_CHARACTER_SET_NAME", "")

    def test_info_schema_charset_returns_none_on_error(self) -> None:
        """Fix C: retorna None si la query falla (sin propagar excepción)."""
        conn = mock.MagicMock()
        conn.cursor.side_effect = Exception("DB error")

        detector = CharsetStateDetector(conn, "named")
        result = detector._test_info_schema_charset()

        assert result is None

    # --- Fix D: connection_charset en _determine_state ---

    def test_diagnose_production_latin1_server_utf8mb4_connection_is_clean(self) -> None:
        """Fix D: server=latin1 global pero connection=utf8mb4 y db=utf8mb4 → UTF8MB4_CLEAN.

        Escenario de producción: servidor con character_set_server=latin1 heredado,
        pero SET NAMES utf8mb4 ejecutado vía init_command → sesión y BD alineadas.
        """
        conn = mock.MagicMock()
        cursor_mock = mock.MagicMock()
        conn.cursor.return_value = cursor_mock

        fetch_results = [
            ("latin1",),  # @@character_set_server ← global del servidor (irrelevante)
            ("utf8mb4",),  # @@character_set_database
            ("utf8mb4",),  # @@character_set_client ← SET NAMES ejecutado
            ("utf8mb4",),  # @@character_set_connection ← lo que importa
            ("utf8mb4_unicode_ci",),
            (True,),  # can_read_comments
            (True,),  # can_convert_utf8mb4
            (None,),  # info_schema_charset
        ]
        cursor_mock.fetchone.side_effect = fetch_results + [(None,)] * 10
        cursor_mock.execute.return_value = None

        detector = CharsetStateDetector(conn, "named")
        diagnosis = detector.diagnose()

        assert diagnosis.state == CharsetState.UTF8MB4_CLEAN
        assert diagnosis.is_healthy() is True
        assert diagnosis.requires_remediation() is False

    def test_diagnose_real_latin1_connection_mismatch(self) -> None:
        """Fix D: connection=latin1, db=utf8mb4 → LATIN1_MISMATCH real (sin SET NAMES)."""
        conn = mock.MagicMock()
        cursor_mock = mock.MagicMock()
        conn.cursor.return_value = cursor_mock

        fetch_results = [
            ("latin1",),  # @@character_set_server
            ("utf8mb4",),  # @@character_set_database
            ("latin1",),  # @@character_set_client ← sin SET NAMES
            ("latin1",),  # @@character_set_connection ← mismatch real
            ("latin1_swedish_ci",),
            (False,),  # can_read_comments (falla sin utf8mb4)
            (True,),
            (None,),
        ]
        cursor_mock.fetchone.side_effect = fetch_results + [(None,)] * 10
        cursor_mock.execute.return_value = None

        detector = CharsetStateDetector(conn, "named")
        diagnosis = detector.diagnose()

        assert diagnosis.state == CharsetState.LATIN1_MISMATCH
        assert diagnosis.requires_remediation() is True
        assert "ALTER DATABASE" in diagnosis.recommendation()

    def test_determine_state_connection_charset_takes_priority_over_server(self) -> None:
        """Fix D: connection_charset=utf8mb4 + db=utf8mb4 → CLEAN aunque server=latin1."""
        state = CharsetStateDetector._determine_state(
            server_charset="latin1",
            database_charset="utf8mb4",
            info_schema_charset=None,
            can_read_comments=True,
            connection_charset="utf8mb4",
        )
        assert state == CharsetState.UTF8MB4_CLEAN

    def test_determine_state_connection_none_all_unknown(self) -> None:
        """H14: si todas las queries de detección fallan (None), retorna UNKNOWN."""
        state = CharsetStateDetector._determine_state(
            server_charset=None,
            database_charset=None,
            info_schema_charset=None,
            can_read_comments=False,
            connection_charset=None,
        )
        assert state == CharsetState.UNKNOWN

    def test_determine_state_connection_none_server_utf8mb4_db_utf8mb4(self) -> None:
        """H14: connection=None con server y DB utf8mb4 → MIXED (can_read_comments no verificable)."""
        state = CharsetStateDetector._determine_state(
            server_charset="utf8mb4",
            database_charset="utf8mb4",
            info_schema_charset=None,
            can_read_comments=False,  # no verificable sin conexión
            connection_charset=None,
        )
        # Sin connection_charset confirmado, la rama de CLEAN no se activa
        assert state == CharsetState.UTF8MB4_MIXED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
