"""Reporter de SchemaDiff en formato HTML usando Jinja2."""

from __future__ import annotations

import logging

from pathlib import Path
from typing import ClassVar

from jinja2 import Environment, FileSystemLoader, Template, select_autoescape

from util_bbdd.comparar.reporters._base import DiffSummary

from ..models import SchemaDiff
from ._base import STATUS_ES, build_diff_summary

logger: logging.Logger = logging.getLogger(__name__)


class HtmlDiffReporter:
    """Genera un reporte HTML auto-contenido del SchemaDiff con diagrama Mermaid.

    Implementa ``DiffReporterProtocol``.

    El HTML generado incluye:
    - Tarjetas de resumen (tablas añadidas/eliminadas/modificadas).
    - Diagrama Mermaid (requiere JS desde CDN en el navegador).
    - Secciones detalladas por tabla, vista y rutina.
    - Definiciones DDL ocultables vía ``<details>``.

    Args:
        template_file: Ruta alternativa a la plantilla Jinja2.
            Si es ``None`` se usa la plantilla embebida ``diff_report.html.j2``.
    """

    _TEMPLATES_DIR: ClassVar[Path] = Path(__file__).parent / "templates"

    def __init__(self, template_file: Path | None = None) -> None:
        self._template_file: Path = template_file or (self._TEMPLATES_DIR / "diff_report.html.j2")

    def render(self, diff: SchemaDiff, output: Path) -> Path:
        """Genera el fichero HTML en la ruta indicada.

        Args:
            diff: Resultado de la comparación de esquemas.
            output: Ruta completa del fichero ``.html`` a generar.

        Returns:
            La ruta del fichero generado.
        """
        output.parent.mkdir(parents=True, exist_ok=True)
        summary: DiffSummary = build_diff_summary(diff)

        env = Environment(
            loader=FileSystemLoader(str(self._template_file.parent)),
            autoescape=select_autoescape(["html", "j2"]),
        )
        template: Template = env.get_template(self._template_file.name)

        added_tables: list[str] = [t.table_name for t in diff.table_diffs if t.status == "added"]
        removed_tables: list[str] = [t.table_name for t in diff.table_diffs if t.status == "removed"]
        modified_tables: list[str] = [t.table_name for t in diff.table_diffs if t.status == "modified"]

        html_content: str = template.render(
            diff=diff,
            summary=summary,
            status_es=STATUS_ES,
            added_tables=added_tables,
            removed_tables=removed_tables,
            modified_tables=modified_tables,
        )

        output.write_text(html_content, encoding="utf-8")
        logger.info("HTML diff report generado: %s", output)
        return output
