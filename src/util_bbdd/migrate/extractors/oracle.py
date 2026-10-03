"""Extractor de metadatos Oracle hacia IR canónico (desde el snapshot de ``metadata/``, C3 de ADR-003).

El IR conserva las convenciones de ``ALL_TAB_COLS`` que esperan los transformers ``oracle_to_*``: ``source_type`` es
``DATA_TYPE`` (``VARCHAR2``, ``NUMBER``, ``TIMESTAMP(6) WITH TIME ZONE``, ``INTERVAL DAY(2) TO SECOND(6)``), la
escala de ``TIMESTAMP(n)`` es ``n`` y la de los intervalos su precisión de segundos.

Desde C3:

- ``char_length`` de los tipos de texto es la longitud en caracteres (``VARCHAR2(30 CHAR)`` → 30); antes era
  ``DATA_LENGTH`` en bytes (120 con AL32UTF8) y el destino recibía columnas cuatro veces más largas.
- Las columnas identidad son ``auto_increment`` sin default (antes: default ``"OWNER"."ISEQ$$_n".nextval``, que no
  existe en el destino).
- Las columnas virtuales no se emiten como ``DEFAULT <expresión>`` (igual que las calculadas del resto de motores).
- Las columnas ``DESC`` de los índices se leen por su nombre y los índices sobre expresiones no se migran (aviso
  ``INDEX_EXPRESSION_SKIPPED``); antes salían con columnas ocultas ``SYS_NC…$``.
- Los miembros de package conservan su tipo (``FUNCTION``/``PROCEDURE``).
"""

from __future__ import annotations

import re

from typing import ClassVar

from ...metadata.model import ColumnMeta, RoutineMeta
from ..ir.models import CanonicalColumn, CanonicalRoutine, MigrationWarning
from ._snapshot import SnapshotSchemaExtractor

#: DATA_TYPE sin modificadores en ALL_TAB_COLS (en el resto, como TIMESTAMP(6), DATA_TYPE ya los lleva).
_PLAIN_DATA_TYPES = frozenset({"VARCHAR2", "NVARCHAR2", "CHAR", "NCHAR", "NUMBER", "FLOAT", "RAW", "UROWID"})
_NUMBERS = re.compile(r"\((\d+)\)")


def _modifiers(data_type: str) -> list[int]:
    return [int(n) for n in _NUMBERS.findall(data_type)]


def _package_member_warning(name: str) -> MigrationWarning:
    return MigrationWarning(
        table=name,
        column=None,
        category="ROUTINE",
        target_type="(package member)",
        code="ROUTINE_PACKAGE_MEMBER",
        message=f"'{name}' es un ORACLE PACKAGE; no tiene equivalente directo — migración manual requerida.",
        severity="WARNING",
    )


class OracleSchemaExtractor(SnapshotSchemaExtractor):
    """Extrae el esquema Oracle hacia el IR canónico.

    Args:
        source: Manager de util_bbdd o ``MetadataSource`` de Oracle. ``schema`` es el owner.
    """

    engine: ClassVar[str] = "oracle"
    _INCLUDE_PRIMARY_INDEX: ClassVar[bool] = True
    _ROUTINE_SOURCE: ClassVar[str] = "ALL_SOURCE"

    def _column(self, col: ColumnMeta) -> CanonicalColumn:
        base = col.base_type
        source_type = base if base in _PLAIN_DATA_TYPES else col.data_type
        modifiers = _modifiers(col.data_type)
        length, precision, scale = col.length, col.precision, col.scale
        if base in ("RAW", "UROWID") and modifiers:
            length = modifiers[0]
        elif base.startswith("TIMESTAMP"):
            scale = modifiers[0] if modifiers else 6
        elif base == "INTERVAL YEAR TO MONTH":
            precision, scale = (modifiers[0] if modifiers else 2), 0
        elif base == "INTERVAL DAY TO SECOND":
            precision = modifiers[0] if modifiers else 2
            scale = modifiers[1] if len(modifiers) > 1 else 6
        identity = col.identity is not None
        return self._canonical_column(
            col,
            source_type,
            char_length=length,
            precision=precision,
            scale=scale,
            default=None if identity else col.default,
            auto_increment=identity,
        )

    def _routine(self, schema: str, routine: RoutineMeta) -> CanonicalRoutine | None:
        """Rutinas sueltas con su código; packages y sus miembros como inventario sin código (no se emiten)."""
        if routine.routine_type == "PACKAGE" or "." in routine.name:
            package, _, member = routine.name.partition(".")
            name = member or package
            return CanonicalRoutine(
                name=name,
                original_name=name,
                schema=schema,
                routine_type=routine.routine_type if member else "PROCEDURE",
                body="",
                return_type=routine.return_type or "",
                comment="",
                warnings=[_package_member_warning(name)],
                is_package_member=True,
                package_name=package,
            )
        return super()._routine(schema, routine)


__all__: list[str] = ["OracleSchemaExtractor"]
