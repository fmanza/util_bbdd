"""Módulo de comparación de esquemas de base de datos.

Compara dos esquemas usando ``sqlalchemy.engine.Inspector`` y devuelve un
modelo tipado de diferencias (``SchemaDiff``).

Ejemplo básico::

    from sqlalchemy import create_engine, inspect
    from util_bbdd.factory import SQLAlchemyEngineFactory
    from util_bbdd.comparar import SchemaComparator

    engine_a = SQLAlchemyEngineFactory.create_engine("mariadb", params_a, "DB_A")
    engine_b = SQLAlchemyEngineFactory.create_engine("mariadb", params_b, "DB_B")

    diff = SchemaComparator().compare(inspect(engine_a), inspect(engine_b))
"""

from .comparator import SchemaComparator
from .contracts import DiffReporterProtocol, SchemaComparatorProtocol
from .models import (
    ColumnDiff,
    CommentDiff,
    ForeignKeyDiff,
    IndexDiff,
    RoutineDiff,
    SchemaDiff,
    TableDiff,
    ViewDiff,
)
from .reporters import (
    ExcelDiffReporter,
    HtmlDiffReporter,
    MarkdownDiffReporter,
    SchemaDiffReporter,
    WordDiffReporter,
)

__all__: list[str] = [
    "ColumnDiff",
    "CommentDiff",
    "DiffReporterProtocol",
    "ExcelDiffReporter",
    "ForeignKeyDiff",
    "HtmlDiffReporter",
    "IndexDiff",
    "MarkdownDiffReporter",
    "RoutineDiff",
    "SchemaComparator",
    "SchemaComparatorProtocol",
    "SchemaDiff",
    "SchemaDiffReporter",
    "TableDiff",
    "ViewDiff",
    "WordDiffReporter",
]
