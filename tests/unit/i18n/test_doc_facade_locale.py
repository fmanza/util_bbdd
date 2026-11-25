"""``DatabaseDocumentation(locale=...)``: validación, cabeceras por idioma y propagación del ``Translator`` (5.10.0)."""

from __future__ import annotations

import json

from pathlib import Path
from typing import Any

import pytest

import util_bbdd.doc.database_documentation as database_documentation_module

from util_bbdd._core.exceptions import DocumentationConfigError
from util_bbdd._core.i18n import Translator
from util_bbdd.doc import DatabaseDocumentation
from util_bbdd.doc.application.use_cases.engine_conditions import EngineConditionsSectionBuilder
from util_bbdd.doc.infrastructure.renderers.registry import build_default_renderer_registry

_DATA = Path(database_documentation_module.__file__).parent / "data"


class _Manager:
    db_type = "postgresql"
    database = "demo"
    conn_params: dict[str, Any] = {}


@pytest.mark.parametrize("locale", ["fr", "EN", None])
def test_unsupported_locale_is_a_config_error(tmp_path: Path, locale: object) -> None:
    with pytest.raises(DocumentationConfigError, match="Idioma no soportado"):
        DatabaseDocumentation(_Manager(), tmp_path, formatos=["excel"], locale=locale)  # type: ignore[arg-type]


def test_default_headers_follow_the_locale(tmp_path: Path) -> None:
    en = DatabaseDocumentation(_Manager(), tmp_path, formatos=["excel"], locale="en")
    es = DatabaseDocumentation(_Manager(), tmp_path, formatos=["excel"])

    assert en._settings.headers["COLUMNAS"][:3] == ["Field", "Type", "Null"]
    assert es._settings.headers["COLUMNAS"][:3] == ["Campo", "Tipo", "Nulo"]


def test_explicit_headers_file_wins_in_any_locale(tmp_path: Path) -> None:
    custom = tmp_path / "headers.json"
    custom.write_text(json.dumps({"headers": {"COLUMNAS": {"base": ["Mi campo"]}}}), encoding="utf-8")

    doc = DatabaseDocumentation(_Manager(), tmp_path, formatos=["excel"], headers_file=custom, locale="en")

    assert doc._settings.headers["COLUMNAS"] == ["Mi campo"]


def test_english_headers_file_has_the_same_sections_and_columns_as_spanish() -> None:
    es = json.loads((_DATA / "headers_config.json").read_text(encoding="utf-8"))["headers"]
    en = json.loads((_DATA / "headers_config.en.json").read_text(encoding="utf-8"))["headers"]

    assert {section: len(cfg["base"]) for section, cfg in es.items()} == {
        section: len(cfg["base"]) for section, cfg in en.items()
    }


def test_registry_passes_the_translator_to_every_renderer() -> None:
    translator = Translator("en")
    registry = build_default_renderer_registry(translator=translator)
    for output_format in ("word", "excel", "html", "markdown"):
        registration = registry.get(output_format)
        assert registration is not None
        renderer: Any = registration.factory(database="demo", headers={}, table_style="Table Grid")
        assert renderer._tr is translator, output_format


def test_engine_conditions_section_follows_the_translator() -> None:
    english = EngineConditionsSectionBuilder(None, Translator("en")).build(None)
    spanish = EngineConditionsSectionBuilder().build(None)

    assert english.headers == ("Level", "Parameter", "Current value", "Recommendation")
    assert english.notices == ("Engine-condition checks are not available for this source.",)
    assert spanish.notices == (EngineConditionsSectionBuilder.NOTICE_UNAVAILABLE,)
    assert spanish.headers == EngineConditionsSectionBuilder.DEFAULT_HEADERS
