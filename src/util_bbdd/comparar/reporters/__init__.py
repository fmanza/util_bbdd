"""Reporters de SchemaDiff en múltiples formatos documentales.

Formatos disponibles:
- ``HtmlDiffReporter``     → ``.html`` con diagrama Mermaid y estilos embebidos.
- ``ExcelDiffReporter``    → ``.xlsx`` con hojas por categoría y color por estado.
- ``WordDiffReporter``     → ``.docx`` con tablas formateadas y DDL en bloques.
- ``MarkdownDiffReporter`` → ``.md`` con diagrama Mermaid y tablas GFM.

Todos implementan ``DiffReporterProtocol``::

    def render(self, diff: SchemaDiff, output: Path) -> Path: ...

Para uso orquestado usa ``SchemaDiffReporter`` (facade)::

    from util_bbdd.comparar import SchemaDiffReporter
    paths = SchemaDiffReporter().render_all(diff, output_dir=Path("./reports"))
"""

from .excel_reporter import ExcelDiffReporter
from .facade import SchemaDiffReporter
from .html_reporter import HtmlDiffReporter
from .markdown_reporter import MarkdownDiffReporter
from .word_reporter import WordDiffReporter

__all__: list[str] = [
    "ExcelDiffReporter",
    "HtmlDiffReporter",
    "MarkdownDiffReporter",
    "SchemaDiffReporter",
    "WordDiffReporter",
]
