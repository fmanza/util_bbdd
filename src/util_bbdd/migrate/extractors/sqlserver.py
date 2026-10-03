"""Extractor de metadatos SQL Server hacia IR canónico (desde el snapshot de ``metadata/``, C3 de ADR-003).

El IR conserva las convenciones de ``INFORMATION_SCHEMA.COLUMNS`` que esperan los transformers ``sqlserver_to_*``:
``source_type`` es el tipo de sistema en mayúsculas (los tipos alias, por su tipo base; ``rowversion`` →
``TIMESTAMP``), ``char_length`` = ``CHARACTER_MAXIMUM_LENGTH`` (``-1`` en los ``(max)``) y ``NUMERIC_PRECISION`` /
``NUMERIC_SCALE`` también en enteros, ``money`` y coma flotante. Como antes, ``datetime2(n)``/``time(n)`` no llevan
su precisión al IR.

Las vistas llevan la definición sin la cabecera ``CREATE VIEW … AS`` (H7); las cifradas o sin permiso
``VIEW DEFINITION``, un aviso. Las routines CLR no se migran (no tienen código T-SQL).

Desde C3 las columnas ``INCLUDE`` de un índice ya no se leen como sus primeras columnas clave.
"""

from __future__ import annotations

from typing import ClassVar

from ...metadata.model import ColumnMeta, RoutineMeta, ViewMeta
from .._compat.sql_view_header import split_create_view_header
from ..ir.models import CanonicalColumn, CanonicalRoutine, CanonicalView, MigrationWarning
from ._snapshot import SnapshotSchemaExtractor

_MAX = -1
#: CHARACTER_MAXIMUM_LENGTH de los tipos de longitud implícita.
_IMPLICIT_LENGTH: dict[str, int] = {
    "text": 2147483647,
    "ntext": 1073741823,
    "image": 2147483647,
    "xml": _MAX,
    "sql_variant": 0,
}
#: NUMERIC_PRECISION / NUMERIC_SCALE de los tipos numéricos sin modificadores.
_NUMERIC_PS: dict[str, tuple[int, int | None]] = {
    "tinyint": (3, 0),
    "smallint": (5, 0),
    "int": (10, 0),
    "bigint": (19, 0),
    "money": (19, 4),
    "smallmoney": (10, 4),
    "float": (53, None),
    "real": (24, None),
}


class SQLServerSchemaExtractor(SnapshotSchemaExtractor):
    """Extrae el esquema SQL Server hacia el IR canónico.

    Args:
        source: Manager de util_bbdd o ``MetadataSource`` de SQL Server. ``schema`` es el ``TABLE_SCHEMA`` (``'dbo'``);
            la base de datos es la de la conexión.
    """

    engine: ClassVar[str] = "sqlserver"
    _ROUTINE_SOURCE: ClassVar[str] = "sys.sql_modules"

    def _column(self, col: ColumnMeta) -> CanonicalColumn:
        base = col.base_type.lower()
        length = _MAX if col.data_type.lower().endswith("(max)") else _IMPLICIT_LENGTH.get(base, col.length)
        precision, scale = _NUMERIC_PS.get(base, (col.precision, col.scale))
        return self._canonical_column(col, base.upper(), char_length=length, precision=precision, scale=scale)

    def _view(self, schema: str, view: ViewMeta, columns: list[str]) -> CanonicalView:
        split = split_create_view_header(view.definition) if view.definition else None
        warnings: list[MigrationWarning] = []
        if split is None:
            warnings.append(
                MigrationWarning(
                    table=view.name,
                    column=None,
                    category="VIEW",
                    target_type="(no disponible)",
                    code="VIEW_DEFINITION_UNAVAILABLE",
                    message=(
                        f"Vista '{view.name}': definición no disponible (WITH ENCRYPTION o sin permiso "
                        "VIEW DEFINITION); no se emite."
                    ),
                    severity="WARNING",
                )
            )
        elif split.column_list:
            warnings.append(
                MigrationWarning(
                    table=view.name,
                    column=None,
                    category="VIEW",
                    target_type="(columnas de la cabecera)",
                    code="VIEW_HEADER_COLUMNS",
                    message=(
                        f"Vista '{view.name}': la cabecera declara las columnas ({split.column_list}); la vista "
                        "migrada toma los nombres del SELECT. Revisar los alias."
                    ),
                    severity="WARNING",
                )
            )
        return CanonicalView(
            name=view.name,
            original_name=view.name,
            schema=schema,
            query=split.query if split else "",
            columns=columns,
            comment=view.comment or "",
            warnings=warnings,
        )

    def _routine(self, schema: str, routine: RoutineMeta) -> CanonicalRoutine | None:
        if routine.language == "CLR":
            return None
        return super()._routine(schema, routine)


__all__: list[str] = ["SQLServerSchemaExtractor"]
