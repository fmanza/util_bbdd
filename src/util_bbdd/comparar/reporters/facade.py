"""Facade de orquestación para generar reportes de SchemaDiff en múltiples formatos."""

from __future__ import annotations

import logging

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.engine import Inspector

from util_bbdd._core.exceptions import SchemaDiffValidationError

from ..contracts import DiffReporterProtocol
from ..models import SchemaDiff
from ._base import build_output_stem
from .excel_reporter import ExcelDiffReporter
from .html_reporter import HtmlDiffReporter
from .markdown_reporter import MarkdownDiffReporter
from .sql_reporter import SqlDiffReporter
from .word_reporter import WordDiffReporter

_EXTENSIONS: dict[str, str] = {
    "html": ".html",
    "excel": ".xlsx",
    "word": ".docx",
    "markdown": ".md",
    "sql": ".sql",
}

_ALL_FORMATS: tuple[str, ...] = ("html", "excel", "word", "markdown", "sql")


class SchemaDiffReporter:
    """Orquesta la generación de reportes de un ``SchemaDiff`` en múltiples formatos.

    Ejemplo básico::

        from pathlib import Path
        from util_bbdd.comparar import SchemaComparator, SchemaDiffReporter

        diff = SchemaComparator().compare(inspect(engine_a), inspect(engine_b))
        reporter = SchemaDiffReporter()

        # Un solo formato
        path = reporter.render(diff, output_dir=Path("./reports"), format="html")

        # Script SQL para MariaDB
        path = reporter.render(diff, output_dir=Path("./reports"), format="sql")

        # Todos los formatos de una vez
        paths = reporter.render_all(diff, output_dir=Path("./reports"))

        # Con plantilla Word corporativa y dialecto SQL
        reporter = SchemaDiffReporter(
            word_template_path=Path("corp_template.docx"),
            sql_dialect="postgresql",
        )
        paths = reporter.render_all(diff, output_dir=Path("./reports"))

    El nombre de fichero se deriva automáticamente de ``diff.source_label`` y
    ``diff.target_label``, sanitizados para ser válidos en el sistema de
    ficheros.  Se puede sobreescribir pasando ``filename`` explícito.

    Args:
        word_template_path: Ruta opcional a una plantilla Word (``.docx`` / ``.dotx``).
            Si se proporciona, el documento Word hereda los estilos y la
            configuración de página de esa plantilla.
        sql_dialect: Motor objetivo para el script SQL.  Controla la sintaxis de
            ``ALTER COLUMN``, ``DROP INDEX`` y ``DROP FOREIGN KEY``.
            Válidos: ``"generic"`` (por defecto), ``"mariadb"``, ``"mysql"``,
            ``"postgresql"``, ``"sqlserver"``, ``"oracle"``, ``"sqlite"``.
        sql_source_inspector: Inspector de SQLAlchemy conectado al esquema origen.
            Cuando se proporciona, el ``SqlDiffReporter`` genera ``CREATE TABLE``
            completo para tablas nuevas y ``ADD COLUMN tipo_real`` para columnas
            añadidas.  Si es ``None`` (por defecto), se emiten placeholders
            ``-- ⚠`` con instrucciones.
        sql_source_schema: Nombre del schema origen para el Inspector.  Normalmente
            ``None`` para el schema por defecto del motor.

    Los reporters individuales también están disponibles directamente::

        from util_bbdd.comparar.reporters import HtmlDiffReporter, SqlDiffReporter
        HtmlDiffReporter().render(diff, output=Path("my_diff.html"))
        SqlDiffReporter(dialect="mariadb").render(diff, output=Path("my_diff.sql"))

        # Con Inspector para SQL completo (CREATE TABLE / ADD COLUMN reales):
        from sqlalchemy import inspect
        reporter = SchemaDiffReporter(
            sql_dialect="postgresql",
            sql_source_inspector=inspect(engine_source),
        )
    """

    def __init__(
        self,
        word_template_path: Path | None = None,
        sql_dialect: str = "generic",
        sql_source_inspector: Inspector | None = None,
        sql_source_schema: str | None = None,
    ) -> None:
        self.logger: logging.Logger = logging.getLogger(__name__)
        self._reporters: dict[str, DiffReporterProtocol] = {
            "html": HtmlDiffReporter(),
            "excel": ExcelDiffReporter(),
            "word": WordDiffReporter(template_path=word_template_path),
            "markdown": MarkdownDiffReporter(),
            "sql": SqlDiffReporter(
                dialect=sql_dialect,
                source_inspector=sql_source_inspector,
                source_schema=sql_source_schema,
            ),
        }

    def render(
        self,
        diff: SchemaDiff,
        output_dir: Path,
        format: str,
        filename: str | None = None,
    ) -> Path:
        """Genera un reporte en el formato indicado.

        Args:
            diff: Resultado de la comparación de esquemas.
            output_dir: Directorio de salida (se crea si no existe).
            format: Formato de salida — uno de ``"html"``, ``"excel"``,
                ``"word"``, ``"markdown"``.
            filename: Nombre de fichero con extensión.  Si es ``None`` se
                deriva automáticamente de los labels de ``diff``.

        Returns:
            Ruta del fichero generado.

        Raises:
            ValueError: Si ``format`` no está soportado.
        """
        fmt: str = format.strip().lower()
        if fmt not in self._reporters:
            raise SchemaDiffValidationError(
                f"Formato '{format}' no soportado. Formatos disponibles: {sorted(self._reporters)}",
                operation="SchemaDiffReporter.render",
                details=f"format={fmt}",
            )
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if filename is None:
            stem: str = build_output_stem(diff)
            ext: str = _EXTENSIONS[fmt]
            filename = f"{stem}{ext}"

        output_path: Path = output_dir / filename
        reporter: DiffReporterProtocol = self._reporters[fmt]
        return reporter.render(diff, output_path)

    def render_all(
        self,
        diff: SchemaDiff,
        output_dir: Path,
        formats: list[str] | None = None,
        raise_on_error: bool = False,
    ) -> list[Path]:
        """Genera reportes en todos los formatos indicados.

        Args:
            diff: Resultado de la comparación de esquemas.
            output_dir: Directorio de salida.
            formats: Lista de formatos a generar.  Si es ``None`` se usan
                todos: ``["html", "excel", "word", "markdown", "sql"]``.
            raise_on_error: Si ``True``, relanza la primera excepción encontrada
                en lugar de omitir el formato fallido y continuar.  Útil para
                pipelines que deben detectar fallos de reporte de forma programática.

        Returns:
            Lista de rutas de ficheros generados (en el orden de ``formats``).

        Raises:
            Exception: Cualquier excepción del reporter cuando ``raise_on_error=True``.
        """
        selected: list[str] = [f.strip().lower() for f in (formats or list(_ALL_FORMATS))]
        paths: list[Path] = []
        for fmt in selected:
            try:
                path: Path = self.render(diff, output_dir=output_dir, format=fmt)
                paths.append(path)
            except Exception:
                if raise_on_error:
                    raise
                self.logger.exception("Error generando reporte '%s' — se omite y continúa", fmt)
        return paths
