"""Tests del idioma de los resultados (``_core/i18n.py``, 5.10.0): catálogos, paridad es/en y separadores numéricos."""

from __future__ import annotations

import json
import string

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

import pytest

from util_bbdd._core.i18n import CATALOG_ROOT, DEFAULT_LOCALE, SUPPORTED_LOCALES, Translator, validate_locale

_ROOT = CATALOG_ROOT


def _catalog_files(locale: str) -> dict[str, dict[str, str]]:
    return {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in sorted((_ROOT / locale).glob("*.json"))}


def _placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


# ── Catálogos ────────────────────────────────────────────────────────────────


def test_every_locale_has_the_same_files_and_keys() -> None:
    reference = _catalog_files(DEFAULT_LOCALE)
    for locale in SUPPORTED_LOCALES:
        catalog = _catalog_files(locale)
        assert catalog.keys() == reference.keys(), locale
        for namespace, messages in reference.items():
            missing = messages.keys() - catalog[namespace].keys()
            extra = catalog[namespace].keys() - messages.keys()
            assert not missing and not extra, f"{locale}/{namespace}.json: faltan {missing}, sobran {extra}"


def test_placeholders_match_between_locales() -> None:
    reference = _catalog_files(DEFAULT_LOCALE)
    for locale in SUPPORTED_LOCALES:
        for namespace, messages in _catalog_files(locale).items():
            for key, text in messages.items():
                assert _placeholders(text) == _placeholders(reference[namespace][key]), f"{locale}/{namespace}.{key}"


def test_catalog_texts_are_non_empty_strings() -> None:
    for locale in SUPPORTED_LOCALES:
        for namespace, messages in _catalog_files(locale).items():
            for key, text in messages.items():
                assert isinstance(text, str) and text != "", f"{locale}/{namespace}.{key}"


def test_catalogs_are_packaged(tmp_path: Path) -> None:
    """El glob de ``package-data`` cubre los catálogos (sin él, el wheel saldría sin ellos)."""
    pyproject = (Path(__file__).parents[2] / "pyproject.toml").read_text(encoding="utf-8")
    assert '"data/i18n/**/*.json"' in pyproject


# ── Translator ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("value", ["fr", "ES", "", None, 1])
def test_unsupported_locale_is_rejected(value: object) -> None:
    with pytest.raises(ValueError, match="Idioma no soportado"):
        validate_locale(value)
    with pytest.raises(ValueError):
        Translator(value)  # type: ignore[arg-type]


def test_default_locale_is_spanish() -> None:
    assert Translator().locale == "es"


def test_missing_key_raises_key_error() -> None:
    with pytest.raises(KeyError, match="no.existe"):
        Translator("en").t("no.existe")


@pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
def test_every_text_formats_with_its_placeholders(locale: str) -> None:
    """Cada texto se formatea con sus marcadores (detecta llaves sueltas que ``format_map`` no admite)."""
    tr = Translator(locale)  # type: ignore[arg-type]
    for namespace, messages in _catalog_files(locale).items():
        for key, text in messages.items():
            params = dict.fromkeys(_placeholders(text), "§")
            rendered = tr.t(f"{namespace}.{key}", **params)
            assert all(f"{{{name}}}" not in rendered for name in params), f"{namespace}.{key}"


# ── Números ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("locale", "value", "expected"),
    [
        ("es", 1234567, "1.234.567"),
        ("en", 1234567, "1,234,567"),
        ("es", 0, "0"),
        ("es", -1234, "-1.234"),
        ("en", -1234, "-1,234"),
        ("es", 10**12, "1.000.000.000.000"),
    ],
)
def test_format_int(locale: str, value: int, expected: str) -> None:
    assert Translator(locale).format_int(value) == expected  # type: ignore[arg-type]


def test_format_int_without_grouping() -> None:
    assert Translator("es").format_int(1234567, grouping=False) == "1234567"


@pytest.mark.parametrize(
    ("locale", "value", "digits", "grouping", "expected"),
    [
        ("es", 1.5, 2, False, "1,50"),
        ("en", 1.5, 2, False, "1.50"),
        ("es", 1234.5, 2, False, "1234,50"),
        ("es", 1234.5, 2, True, "1.234,50"),
        ("en", 1234.5, 2, True, "1,234.50"),
        ("es", 12.3456, 4, False, "12,3456"),
        ("es", -0.5, 1, False, "-0,5"),
        ("en", Decimal("2.345"), 1, False, "2.3"),
        ("es", 3, 2, False, "3,00"),
        ("es", 7.0, 0, False, "7"),
    ],
)
def test_format_decimal(locale: str, value: float, digits: int, grouping: bool, expected: str) -> None:
    assert Translator(locale).format_decimal(value, digits, grouping=grouping) == expected  # type: ignore[arg-type]


@pytest.mark.parametrize("value", ["1.5", None, True, b"1"])
def test_number_formatters_reject_non_numbers(value: object) -> None:
    tr = Translator("es")
    with pytest.raises(TypeError):
        tr.format_decimal(value, 2)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        tr.format_int(value)  # type: ignore[arg-type]


def test_format_int_rejects_floats() -> None:
    with pytest.raises(TypeError):
        Translator("es").format_int(1.0)  # type: ignore[arg-type]


def test_translators_do_not_interfere_across_threads() -> None:
    """Sin ``locale.setlocale``: dos idiomas a la vez no se pisan los separadores."""

    def run(locale: str) -> set[str]:
        tr = Translator(locale)  # type: ignore[arg-type]
        return {tr.format_decimal(1234.5, 2, grouping=True) for _ in range(500)}

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(run, ["es", "en"] * 8))
    assert all(r == {"1.234,50"} for r in results[0::2])
    assert all(r == {"1,234.50"} for r in results[1::2])
