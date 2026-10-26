"""Validación de la plantilla Word (``imprimir["plantilla_word"]``) antes de generar (util_bbdd_web G41, 4.1.0)."""

from __future__ import annotations

import zipfile

from pathlib import Path
from typing import ClassVar

from docx import Document as load_document
from docx.enum.style import WD_STYLE_TYPE
from docx.opc.exceptions import PackageNotFoundError

from ...._core.exceptions import DocumentationConfigError


class WordTemplateValidator:
    """Comprueba que una plantilla Word se puede abrir y tiene los estilos de párrafo que usa ``WordGenerator``.

    ``WordGenerator`` aplica estilos por nombre (``add_heading`` usa ``Title`` y ``Heading 1``-``3``; el DDL,
    ``No Spacing``). Word solo guarda en un ``.docx`` los estilos que se han usado, así que una plantilla corporativa
    habitual no los tiene todos, y python-docx lanzaba ``KeyError`` a mitad del documento: llegaba como
    ``DocumentationRenderError`` y se perdían también los formatos que faltaban. Ahora el error sale al construir
    ``DatabaseDocumentation``, antes de leer la base de datos. Los estilos de tabla no se exigen: ``table_style`` ya
    cae en ``Table Grid`` con un aviso si la plantilla no lo tiene.

    Example:
        >>> WordTemplateValidator.missing_styles(Path("corporativa.docx"))
        ['Heading 3', 'No Spacing']
    """

    #: Estilos de párrafo que ``WordGenerator`` aplica por nombre.
    REQUIRED_STYLES: ClassVar[tuple[str, ...]] = ("Title", "Heading 1", "Heading 2", "Heading 3", "No Spacing")

    @classmethod
    def missing_styles(cls, template_path: Path) -> list[str]:
        """Estilos de :attr:`REQUIRED_STYLES` que no están en la plantilla, en ese orden.

        Args:
            template_path: Ruta del ``.docx`` o ``.dotx``.

        Raises:
            DocumentationConfigError: El fichero no es un documento Word que python-docx pueda abrir.
        """
        try:
            document = load_document(str(template_path))
        except (PackageNotFoundError, zipfile.BadZipFile, KeyError, ValueError) as error:
            raise DocumentationConfigError(
                f"La plantilla Word no es un documento .docx válido: {template_path} ({error})",
                operation="DOCUMENTATION",
            ) from error
        present: set[str] = {
            str(style.name) for style in document.styles if style.type == WD_STYLE_TYPE.PARAGRAPH and style.name
        }
        return [name for name in cls.REQUIRED_STYLES if name not in present]

    @classmethod
    def check(cls, template_path: Path) -> None:
        """Lanza ``DocumentationConfigError`` si a la plantilla le falta algún estilo de :attr:`REQUIRED_STYLES`.

        Args:
            template_path: Ruta del ``.docx`` o ``.dotx`` (ya se ha comprobado que existe).

        Raises:
            DocumentationConfigError: La plantilla no se puede abrir o le faltan estilos (los nombra todos).
        """
        missing: list[str] = cls.missing_styles(template_path)
        if missing:
            raise DocumentationConfigError(
                f"A la plantilla Word {template_path.name} le faltan estilos que usa la documentación: "
                f"{', '.join(missing)}. Añádalos a la plantilla (basta con aplicarlos una vez y guardar)",
                operation="DOCUMENTATION",
            )
