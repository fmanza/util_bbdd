"""Emisor DDL para MySQL.

Hereda de ``MariaDBDDLEmitter``: MySQL 8 acepta el mismo DDL (backticks, ``ENGINE``, ``DEFAULT CHARSET``,
``COLLATE``, ``CREATE OR REPLACE VIEW``, FKs inline y ``ALTER TABLE`` para ciclos). Diferencias:

- La collation la fija ``MigrationPlanner`` (``utf8mb4_0900_ai_ci`` por defecto; ``utf8mb4_uca1400_ai_ci`` no
  existe en MySQL).
- Los enteros se emiten sin ancho de visualización (``INT`` en vez de ``INT(11)``): MySQL 8.0.17+ lo declara
  obsoleto y avisa en cada columna. Se conserva ``TINYINT(1)``, el convenio de booleano que MySQL mantiene.
"""

from __future__ import annotations

import re

from ..ir.models import CanonicalColumn
from .mariadb import MariaDBDDLEmitter, _bt

_INT_DISPLAY_WIDTH: re.Pattern[str] = re.compile(
    r"^(TINYINT|SMALLINT|MEDIUMINT|INTEGER|INT|BIGINT)\s*\(\s*(\d+)\s*\)",
    re.IGNORECASE,
)


def strip_int_display_width(column_type: str) -> str:
    """Quita el ancho de visualización de un tipo entero MySQL (``INT(11) UNSIGNED`` → ``INT UNSIGNED``).

    ``TINYINT(1)`` se mantiene; el resto de tipos no cambia.

    Args:
        column_type: Tipo de columna MySQL tal como lo da el catálogo (``COLUMN_TYPE``).
    """
    match = _INT_DISPLAY_WIDTH.match(column_type)
    if match is None:
        return column_type
    if match.group(1).upper() == "TINYINT" and match.group(2) == "1":
        return column_type
    return match.group(1) + column_type[match.end() :]


class MySQLDDLEmitter(MariaDBDDLEmitter):
    """Genera DDL MySQL desde IR canónico.

    Args:
        charset: CHARACTER SET para tablas (obligatorio).
        collation: COLLATE para tablas (obligatorio; válida en MySQL).
        engine: Motor de almacenamiento (default: InnoDB).
    """

    def _emit_column(self, col: CanonicalColumn, table_name: str) -> str:
        line = super()._emit_column(col, table_name)
        if col.omit:
            return line
        prefix = f"  {_bt(col.name)} "
        if not line.startswith(prefix):
            return line
        return prefix + strip_int_display_width(line[len(prefix) :])


__all__: list[str] = [
    "MySQLDDLEmitter",
    "strip_int_display_width",
]
