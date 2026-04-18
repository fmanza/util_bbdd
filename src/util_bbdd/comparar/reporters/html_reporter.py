"""Reporter de SchemaDiff en formato HTML con filtrado interactivo y búsqueda de texto.

Usa Jinja2 como motor de plantillas con autoescape activado.
La plantilla por defecto reside en ``reporters/templates/diff_report.html.j2``.
"""

from __future__ import annotations

import logging

from pathlib import Path
from typing import ClassVar

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..models import SchemaDiff
from ._base import STATUS_ES, DdlNormalizer, DiffSummary, build_diff_summary, escape_mermaid_label

# Directorio de plantillas embebidas (junto a este módulo)
_TEMPLATES_DIR: Path = Path(__file__).parent / "templates"
_DEFAULT_TEMPLATE: str = "diff_report.html.j2"


class HtmlDiffReporter:
    """Genera un reporte HTML auto-contenido del SchemaDiff con filtrado y búsqueda.

    Implementa ``DiffReporterProtocol``.

    El HTML generado incluye:
    - Barra de controles: 5 filtros de categoría + input de búsqueda de texto.
    - Tarjetas de resumen con contadores por categoría.
    - Diagrama Mermaid con subgrafos por estado (requiere CDN en el navegador).
    - Secciones detalladas por tabla, vista y rutina con DDL colapsable.

    La plantilla Jinja2 se ubica en ``reporters/templates/diff_report.html.j2``.
    Puede sustituirse pasando un directorio alternativo en el constructor.

    Args:
        template_dir: Directorio que contiene la plantilla Jinja2.
            Si es ``None`` se usa el directorio ``templates/`` incluido en el paquete.
        template_name: Nombre del fichero de plantilla dentro de ``template_dir``.
    """

    # Categorías de filtro: (id CSS/JS, etiqueta visible)
    _FILTER_CATS: ClassVar[list[tuple[str, str]]] = [
        ("tables-added", "Tablas añadidas"),
        ("tables-removed", "Tablas eliminadas"),
        ("tables-modified", "Tablas modificadas"),
        ("views", "Vistas con diff"),
        ("routines", "Rutinas con diff"),
    ]

    # Mapa de status de tabla → categoría de filtro
    _STATUS_TO_CAT: ClassVar[dict[str, str]] = {
        "added": "tables-added",
        "removed": "tables-removed",
        "modified": "tables-modified",
    }

    def __init__(
        self,
        template_dir: Path | None = None,
        template_name: str = _DEFAULT_TEMPLATE,
    ) -> None:
        self.logger: logging.Logger = logging.getLogger(__name__)
        templates_path: Path = template_dir if template_dir is not None else _TEMPLATES_DIR
        self._env: Environment = Environment(
            loader=FileSystemLoader(str(templates_path)),
            autoescape=select_autoescape(["html", "j2"]),
            keep_trailing_newline=True,
        )
        self._env.filters["escape_mermaid"] = lambda s: escape_mermaid_label(str(s or ""))
        self._env.filters["normalize_view_ddl"] = lambda s: DdlNormalizer.normalize_view_ddl(str(s or ""))
        self._env.filters["normalize_routine_ddl"] = lambda s: DdlNormalizer.normalize_routine_ddl(str(s or ""))
        self._template_name: str = template_name

    # ------------------------------------------------------------------
    # Contrato público
    # ------------------------------------------------------------------

    def render(self, diff: SchemaDiff, output: Path) -> Path:
        """Genera el fichero ``.html`` en la ruta indicada.

        Args:
            diff: Resultado de la comparación de esquemas.
            output: Ruta completa del fichero ``.html`` a generar.

        Returns:
            La ruta del fichero generado.
        """
        output.parent.mkdir(parents=True, exist_ok=True)
        summary = build_diff_summary(diff)
        ctx = self._build_context(diff, summary)
        template = self._env.get_template(self._template_name)
        content = template.render(ctx)
        output.write_text(content, encoding="utf-8")
        self.logger.info("HTML diff report generado: %s", output)
        return output

    # ------------------------------------------------------------------
    # Construcción del contexto de plantilla
    # ------------------------------------------------------------------

    def _build_context(self, diff: SchemaDiff, summary: DiffSummary) -> dict:
        """Construye el dict de contexto que se pasa a la plantilla Jinja2."""
        return {
            "diff": diff,
            "summary": summary,
            "status_es": STATUS_ES,
            "status_to_cat": self._STATUS_TO_CAT,
            "filter_cats": self._FILTER_CATS,
        }
