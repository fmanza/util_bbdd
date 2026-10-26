"""La plantilla Word se valida al construir ``DatabaseDocumentation`` (util_bbdd_web G41, 4.1.0).

Sin un estilo que ``WordGenerator`` aplica por nombre, python-docx lanzaba ``KeyError`` a mitad del documento y se
perdían todos los formatos. Ahora es un ``DocumentationConfigError`` antes de leer la base de datos.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import docx
import pytest

from util_bbdd.doc import DatabaseDocumentation
from util_bbdd.doc.infrastructure.renderers.word_template import WordTemplateValidator
from util_bbdd.exceptions import DocumentationConfigError

pytestmark = pytest.mark.unit


def _template(tmp_path: Path, *, without: tuple[str, ...] = ()) -> Path:
    document = docx.Document()
    for name in without:
        element = document.styles[name].element
        element.getparent().remove(element)
    path = tmp_path / "plantilla.docx"
    document.save(str(path))
    return path


class _ManagerThatMustNotBeRead:
    db_type = "sqlite"
    database = "demo"
    conn_params: dict[str, Any] = {}

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"La validación no debe consultar la BD ({name})")


def test_default_template_has_every_required_style(tmp_path: Path) -> None:
    assert WordTemplateValidator.missing_styles(_template(tmp_path)) == []


def test_missing_styles_are_all_named(tmp_path: Path) -> None:
    path = _template(tmp_path, without=("Heading 1", "No Spacing"))

    assert WordTemplateValidator.missing_styles(path) == ["Heading 1", "No Spacing"]
    with pytest.raises(DocumentationConfigError, match="Heading 1, No Spacing"):
        WordTemplateValidator.check(path)


def test_a_file_that_is_not_a_docx_is_a_config_error(tmp_path: Path) -> None:
    path = tmp_path / "plantilla.docx"
    path.write_text("no soy un docx", encoding="utf-8")

    with pytest.raises(DocumentationConfigError, match="no es un documento .docx válido"):
        WordTemplateValidator.check(path)


def test_documentation_rejects_the_template_before_reading_the_database(tmp_path: Path) -> None:
    path = _template(tmp_path, without=("Heading 1",))

    with pytest.raises(DocumentationConfigError, match="Heading 1") as raised:
        DatabaseDocumentation(
            _ManagerThatMustNotBeRead(),  # type: ignore[arg-type]
            directorio_salida=tmp_path / "out",
            imprimir={"plantilla_word": path},
            formatos=["word"],
        )

    assert isinstance(raised.value, ValueError)  # DocumentationConfigError también es ValueError


def test_template_is_not_checked_when_word_is_not_requested(tmp_path: Path) -> None:
    path = _template(tmp_path, without=("Heading 1",))

    DatabaseDocumentation(
        _ManagerThatMustNotBeRead(),  # type: ignore[arg-type]
        directorio_salida=tmp_path / "out",
        imprimir={"plantilla_word": path},
        formatos=["excel"],
    )
