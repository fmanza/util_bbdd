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
        """🔴 Server latin1 pero BD utf8mb4 (inverse critical mismatch)."""
        conn = mock.MagicMock()
        cursor_mock = mock.MagicMock()
        conn.cursor.return_value = cursor_mock

        # Mock de resultados: latin1_mismatch inverso (usuario reportó en GitHub)
        fetch_results = [
            ("latin1",),  # @@character_set_server ← MISMATCH INVERSO
            ("utf8mb4",),  # @@character_set_database
            ("utf8mb4",),  # @@character_set_client
            ("utf8mb4",),  # @@character_set_connection
            ("utf8mb4_unicode_ci",),  # @@collation_connection
        ]
        cursor_mock.fetchone.side_effect = fetch_results + [(None,)] * 10
        cursor_mock.execute.return_value = None

        detector = CharsetStateDetector(conn, "named")
        diagnosis = detector.diagnose()

        assert diagnosis.state == CharsetState.LATIN1_MISMATCH
        assert diagnosis.server_charset == "latin1"
        assert diagnosis.database_charset == "utf8mb4"
        assert diagnosis.requires_remediation() is True
        assert "ALTER DATABASE" in diagnosis.recommendation()

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

    def test_adaptive_mode_failfast_on_mismatch(self) -> None:
        """🔴 Modo 'auto' con latin1_mismatch → failfast."""
        conn = mock.MagicMock()
        cursor_mock = mock.MagicMock()
        conn.cursor.return_value = cursor_mock

        # Mock detección de charset: latin1_mismatch
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
        assert executor.strategy == "failfast"

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
