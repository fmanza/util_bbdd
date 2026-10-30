"""Reporter de SchemaDiff en formato HTML con filtrado interactivo y búsqueda de texto.

Usa Jinja2 como motor de plantillas con autoescape activado.
La plantilla por defecto reside en ``reporters/templates/diff_report.html.j2``.
"""

from __future__ import annotations

import logging
import re

from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import urlsplit

from jinja2 import Environment, FileSystemLoader, select_autoescape

from util_bbdd._core.exceptions import SchemaDiffValidationError

if TYPE_CHECKING:
    from util_bbdd.comparar.models import SchemaDiff

from ._base import STATUS_ES, DdlNormalizer, DiffSummary, build_diff_summary, escape_mermaid_label

# Directorio de plantillas embebidas (junto a este módulo)
_TEMPLATES_DIR: Path = Path(__file__).parent / "templates"
_DEFAULT_TEMPLATE: str = "diff_report.html.j2"

#: Mermaid que carga el informe por defecto: versión exacta desde jsDelivr (12.2.0 desde util_bbdd 5.2.0, G45 de
#: util_bbdd_web; antes 10.9.8). La plantilla solo usa ``initialize`` y ``run``, comprobados con esta versión.
MERMAID_VERSION: str = "12.2.0"
MERMAID_CDN_URL: str = f"https://cdn.jsdelivr.net/npm/mermaid@{MERMAID_VERSION}/dist/mermaid.min.js"
#: SRI de ``dist/mermaid.min.js`` del paquete npm ``mermaid@12.2.0`` (tarball verificado con la ``integrity`` del
#: registro). Si el CDN sirve otro contenido, el navegador no ejecuta el script y el informe sigue sin diagramas.
MERMAID_SRI: str = "sha384-8xUhuLNMjW/cI2Dacg3DR4WliYznvIg0LVG1stctThKD/YVrJFI9TNCFxft5NYgp"


class HtmlDiffReporter:
    """Genera un reporte HTML auto-contenido del SchemaDiff con filtrado y búsqueda.

    Implementa ``DiffReporterProtocol``.

    El HTML generado incluye:
    - Barra de controles: 5 filtros de categoría + input de búsqueda de texto.
    - Tarjetas de resumen con contadores por categoría.
    - Diagrama Mermaid con subgrafos por estado. Por defecto Mermaid se carga de jsDelivr con versión fija y SRI
      (``MERMAID_CDN_URL``, ``MERMAID_SRI``). Sin Mermaid (sin red, CSP que lo bloquea o ``mermaid_src=None``) el
      informe funciona igual (pestañas, filtros, búsqueda) y los diagramas se ven como texto.
    - Secciones detalladas por tabla, vista y rutina con DDL colapsable.

    La plantilla Jinja2 se ubica en ``reporters/templates/diff_report.html.j2``.
    Puede sustituirse pasando un directorio alternativo en el constructor.

    Args:
        template_dir: Directorio que contiene la plantilla Jinja2.
            Si es ``None`` se usa el directorio ``templates/`` incluido en el paquete.
        template_name: Nombre del fichero de plantilla dentro de ``template_dir``.
        mermaid_src: De dónde sale Mermaid. ``str``: URL ``http(s)`` o relativa para ``<script src>`` (p. ej. un
            asset propio servido con la CSP de la aplicación). ``Path``: fichero ``mermaid.min.js`` local que se
            incrusta en el HTML (informe autocontenido, sin red; unos 3 MB más). ``None``: sin Mermaid.
        mermaid_integrity: Valor ``integrity`` (SRI) del ``<script src>``. Con la URL por defecto se usa
            ``MERMAID_SRI``; con otra URL, ninguno salvo que se indique.

    Raises:
        SchemaDiffValidationError: ``mermaid_src`` es una URL con un esquema distinto de ``http``/``https`` o un
            fichero que no se puede leer.
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
        *,
        mermaid_src: str | Path | None = MERMAID_CDN_URL,
        mermaid_integrity: str | None = None,
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
        self._mermaid: dict[str, str | None] | None = self._resolve_mermaid(mermaid_src, mermaid_integrity)

    @staticmethod
    def _resolve_mermaid(src: str | Path | None, integrity: str | None) -> dict[str, str | None] | None:
        """Traduce ``mermaid_src`` al contexto de la plantilla: ``src`` + ``integrity``, ``inline`` o ``None``."""
        if src is None:
            return None
        if isinstance(src, Path):
            try:
                code = src.read_text(encoding="utf-8")
            except OSError as exc:
                raise SchemaDiffValidationError(f"No se puede leer mermaid_src '{src}': {exc}") from exc
            # Un "</script" dentro del código cerraría la etiqueta que lo envuelve
            return {"inline": re.sub(r"</(script)", r"<\\/\1", code, flags=re.IGNORECASE)}
        if urlsplit(src).scheme.lower() not in ("", "http", "https"):
            raise SchemaDiffValidationError(f"mermaid_src debe ser una URL http(s) o relativa: {src!r}")
        if integrity is None and src == MERMAID_CDN_URL:
            integrity = MERMAID_SRI
        return {"src": src, "integrity": integrity}

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

    def _build_context(self, diff: SchemaDiff, summary: DiffSummary) -> dict[str, Any]:
        """Construye el dict de contexto que se pasa a la plantilla Jinja2."""
        return {
            "diff": diff,
            "mermaid": self._mermaid,
            "summary": summary,
            "status_es": STATUS_ES,
            "status_to_cat": self._STATUS_TO_CAT,
            "filter_cats": self._FILTER_CATS,
        }
