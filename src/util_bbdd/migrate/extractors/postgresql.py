"""Extractor de metadatos PostgreSQL hacia IR canónico (desde el snapshot de ``metadata/``, C3 de ADR-003).

El IR conserva las convenciones de ``information_schema.columns`` que esperan los transformers ``postgresql_to_*``:
``source_type`` en mayúsculas (``CHARACTER VARYING``, ``TIMESTAMP WITHOUT TIME ZONE``, ``ARRAY``, ``USER-DEFINED``;
dominios por su tipo base), ``char_length`` = longitud declarada (bits en ``bit(n)``) y ``NUMERIC_PRECISION`` /
``NUMERIC_SCALE`` también en enteros y coma flotante.

``auto_increment`` marca las columnas ``serial`` (default ``nextval(...)``) y las ``GENERATED … AS IDENTITY``.
Las vistas materializadas no se migran.
"""

from __future__ import annotations

from typing import ClassVar

from ...metadata.model import ColumnMeta
from ..ir.models import CanonicalColumn
from ._snapshot import SnapshotSchemaExtractor

#: NUMERIC_PRECISION / NUMERIC_SCALE de information_schema para los tipos sin modificadores.
_NUMERIC_PS: dict[str, tuple[int, int | None]] = {
    "smallint": (16, 0),
    "integer": (32, 0),
    "bigint": (64, 0),
    "real": (24, None),
    "double precision": (53, None),
}


class PostgreSQLSchemaExtractor(SnapshotSchemaExtractor):
    """Extrae el esquema PostgreSQL hacia el IR canónico.

    Args:
        source: Manager de util_bbdd o ``MetadataSource`` de PostgreSQL. ``schema`` es el ``TABLE_SCHEMA``
            (``'public'``); la base de datos es la de la conexión.
    """

    engine: ClassVar[str] = "postgresql"

    def _column(self, col: ColumnMeta) -> CanonicalColumn:
        precision, scale = _NUMERIC_PS.get(col.base_type, (col.precision, col.scale))
        serial = bool(col.default and col.default.lower().startswith("nextval("))
        return self._canonical_column(
            col,
            col.base_type.upper(),
            precision=precision,
            scale=scale,
            auto_increment=serial or col.identity is not None,
        )


__all__: list[str] = ["PostgreSQLSchemaExtractor"]
