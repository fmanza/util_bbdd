"""Tests para charset.py — validación de charset y collation en MariaDB."""

from __future__ import annotations

import pytest

from util_bbdd.migrate.charset import (
    CHARSET_COLLATION_MAP,
    VALID_CHARSETS,
    validate_charset,
    validate_charset_collation_pair,
    validate_collation,
)


class TestValidateCharset:
    def test_lowercase_accepted(self) -> None:
        assert validate_charset("utf8mb4") == "utf8mb4"

    def test_uppercase_normalised(self) -> None:
        assert validate_charset("UTF8MB4") == "utf8mb4"

    def test_invalid_charset_raises(self) -> None:
        with pytest.raises(ValueError, match="charset"):
            validate_charset("nonexistent_charset_xyz")


class TestValidateCollation:
    def test_valid_collation_returned(self) -> None:
        assert validate_collation("utf8mb4_unicode_ci") == "utf8mb4_unicode_ci"

    def test_invalid_collation_raises(self) -> None:
        with pytest.raises(ValueError, match="collation"):
            validate_collation("totally_fake_collation_xyz")


class TestValidateCharsetCollationPair:
    # ── charsets con mapa explícito ────────────────────────────────────────────

    def test_utf8mb4_unicode_ci_valid(self) -> None:
        """utf8mb4 + utf8mb4_unicode_ci es un par válido en CHARSET_COLLATION_MAP."""
        validate_charset_collation_pair("utf8mb4", "utf8mb4_unicode_ci")  # no debe lanzar

    def test_utf8mb4_wrong_collation_raises(self) -> None:
        """utf8mb4 + latin1_general_ci no es compatible."""
        with pytest.raises(ValueError):
            validate_charset_collation_pair("utf8mb4", "latin1_general_ci")

    # ── charsets SIN mapa explícito → fallback de prefijo ────────────────────

    def test_unmapped_charset_compatible_collation_passes(self) -> None:
        """TEST-09: latin2 + latin2_general_ci (prefijo correcto) → no debe lanzar."""
        # Verificar que latin2 existe como charset válido pero no tiene mapa explícito
        assert "latin2" in VALID_CHARSETS
        assert "latin2" not in CHARSET_COLLATION_MAP
        validate_charset_collation_pair("latin2", "latin2_general_ci")  # no debe lanzar

    def test_unmapped_charset_wrong_collation_raises(self) -> None:
        """TEST-09: latin2 + utf8mb4_unicode_ci (prefijo incorrecto) → debe lanzar ValueError."""
        assert "latin2" in VALID_CHARSETS
        assert "latin2" not in CHARSET_COLLATION_MAP
        with pytest.raises(ValueError, match="latin2"):
            validate_charset_collation_pair("latin2", "utf8mb4_unicode_ci")

    def test_cp1250_wrong_collation_raises(self) -> None:
        """TEST-09: cp1250 + utf8mb4_unicode_ci no es compatible."""
        assert "cp1250" in VALID_CHARSETS
        assert "cp1250" not in CHARSET_COLLATION_MAP
        with pytest.raises(ValueError):
            validate_charset_collation_pair("cp1250", "utf8mb4_unicode_ci")

    def test_cp1250_valid_prefix_collation_passes(self) -> None:
        """cp1250 + cp1250_general_ci debe pasar (prefijo correcto)."""
        assert "cp1250" not in CHARSET_COLLATION_MAP
        validate_charset_collation_pair("cp1250", "cp1250_general_ci")  # no debe lanzar
