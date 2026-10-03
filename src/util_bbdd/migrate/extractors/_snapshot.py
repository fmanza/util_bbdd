"""Extracción del IR de ``migrate`` desde el snapshot de ``metadata/`` (grupo C3 de ADR-003).

Los extractores ya no tienen SQL propio: leen el schema con una :class:`~util_bbdd.metadata.MetadataSource` (la del
manager, ``manager.metadata_source``, o una que se les pase) y traducen el modelo neutro a ``CanonicalTable``,
``CanonicalView`` y ``CanonicalRoutine``. Cada motor solo aporta cómo se escribe una columna en el IR (los
transformers mapean tipos con las convenciones de ``information_schema`` de su motor origen: ``CHARACTER VARYING``,
``NUMERIC_PRECISION`` de los enteros…) y sus particularidades de vistas, índices y routines.

Cada extractor descarta lo que la fuente tuviera en caché del schema en su primera lectura: un plan se hace siempre con
el catálogo actual, como cuando cada extractor leía con sus propias consultas.
"""

from __future__ import annotations

import re

from typing import Any, ClassVar

from ...metadata.model import ColumnMeta, IndexMeta, Kind, RoutineMeta, SchemaSnapshot, ViewMeta
from ..ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalRoutine,
    CanonicalTable,
    CanonicalView,
    MigrationWarning,
)

TABLE_KINDS: frozenset[Kind] = frozenset(
    {Kind.TABLES, Kind.COLUMNS, Kind.PRIMARY_KEYS, Kind.FOREIGN_KEYS, Kind.INDEXES}
)
VIEW_KINDS: frozenset[Kind] = frozenset({Kind.VIEWS, Kind.COLUMNS})
ROUTINE_KINDS: frozenset[Kind] = frozenset({Kind.ROUTINES})

_QUOTED = re.compile(r'^"([^"]+)"$')


def metadata_source(source: Any) -> Any:
    """La ``MetadataSource`` de un manager (``metadata_source``) o la propia fuente si ya lo es."""
    inner = getattr(source, "metadata_source", None)
    if inner is not None and callable(getattr(inner, "snapshot", None)):
        return inner
    if callable(getattr(source, "snapshot", None)):
        return source
    raise TypeError(
        f"{type(source).__name__} no ofrece metadatos por lotes: pasa un manager de util_bbdd o una MetadataSource"
    )


def no_body_warning(name: str, where: str = "") -> MigrationWarning:
    suffix = f" en {where}" if where else ""
    return MigrationWarning(
        table=name,
        column=None,
        category="ROUTINE",
        target_type="(no body)",
        code="ROUTINE_NO_BODY",
        message=f"Body de '{name}' no disponible{suffix}; emitir stub.",
        severity="WARNING",
    )


class SnapshotSchemaExtractor:
    """Base de los extractores: snapshot → IR. Las subclases definen :meth:`_column` y, si hace falta, el resto.

    Args:
        source: Manager de util_bbdd (``SyncDatabaseManager``) o ``MetadataSource`` del motor origen.
    """

    #: Motor de las reglas del IR (``CanonicalTable.schema`` y ``is_external`` comparan sin mayúsculas en todos).
    engine: ClassVar[str] = ""
    #: Índices que respaldan la PK: Oracle los incluía en el IR; el resto, no.
    _INCLUDE_PRIMARY_INDEX: ClassVar[bool] = False
    #: Dónde lee el motor el código de las routines (mensaje de ``ROUTINE_NO_BODY``).
    _ROUTINE_SOURCE: ClassVar[str] = ""

    def __init__(self, source: Any) -> None:
        self._source = metadata_source(source)
        self._fresh: set[str] = set()

    # ── lectura ──────────────────────────────────────────────────────────────
    def _snapshot(self, schema: str, kinds: frozenset[Kind]) -> SchemaSnapshot:
        if schema not in self._fresh:
            invalidate = getattr(self._source, "invalidate", None)
            if callable(invalidate):
                invalidate(schema)
            self._fresh.add(schema)
        snapshot: SchemaSnapshot = self._source.snapshot(schema, kinds=kinds)
        return snapshot

    # ── tablas ───────────────────────────────────────────────────────────────
    def extract(self, schema: str) -> list[CanonicalTable]:
        """Extrae todas las tablas del schema como IR canónico (columnas, PK, FK e índices)."""
        snapshot = self._snapshot(schema, TABLE_KINDS)
        tables: list[CanonicalTable] = []
        for table in snapshot.tables():
            pk = snapshot.primary_key(table.name)
            pk_cols = list(pk.columns) if pk else []
            columns = [self._column(c) for c in snapshot.columns(table.name)]
            pk_set = {c.upper() for c in pk_cols}
            for col in columns:
                if col.name.upper() in pk_set:
                    col.is_primary_key = True
            warnings: list[MigrationWarning] = []
            indexes = self._indexes(table.name, snapshot.indexes(table.name), columns, warnings)
            tables.append(
                CanonicalTable(
                    name=table.name,
                    original_name=table.name,
                    schema=schema,
                    columns=columns,
                    primary_key=pk_cols,
                    indexes=indexes,
                    foreign_keys=[
                        CanonicalFK(
                            name=fk.name,
                            original_name=fk.name,
                            columns=list(fk.columns),
                            ref_table=fk.ref_table,
                            ref_columns=list(fk.ref_columns),
                            on_delete=fk.on_delete,
                            on_update=fk.on_update,
                            is_external=(fk.ref_schema or schema).upper() != schema.upper(),
                        )
                        for fk in snapshot.foreign_keys(table.name)
                    ],
                    comment=table.comment or "",
                    warnings=warnings,
                )
            )
        return tables

    def _column(self, col: ColumnMeta) -> CanonicalColumn:
        raise NotImplementedError

    @staticmethod
    def _canonical_column(col: ColumnMeta, source_type: str, **fields: Any) -> CanonicalColumn:
        """``CanonicalColumn`` con lo común a todos los motores; ``fields`` fija longitud, precisión, default…"""
        values: dict[str, Any] = {
            "char_length": col.length,
            "precision": col.precision,
            "scale": col.scale,
            "default": col.default,
            "auto_increment": col.identity is not None,
        }
        values.update(fields)
        return CanonicalColumn(
            name=col.name,
            original_name=col.name,
            source_type=source_type,
            target_type="",  # el transformer lo rellena
            nullable=col.nullable,
            comment=col.comment or "",
            ordinal=col.ordinal,
            **values,
        )

    def _indexes(
        self,
        table: str,
        indexes: tuple[IndexMeta, ...],
        columns: list[CanonicalColumn],
        warnings: list[MigrationWarning],
    ) -> list[CanonicalIndex]:
        """Índices del IR: sin el de la PK (salvo Oracle) ni los de expresiones, que no se traducen (aviso)."""
        names = {c.name for c in columns}
        result: list[CanonicalIndex] = []
        for index in indexes:
            if index.primary and not self._INCLUDE_PRIMARY_INDEX:
                continue
            index_columns = [self._index_column(c) for c in index.columns]
            if any(c not in names for c in index_columns):
                warnings.append(
                    MigrationWarning(
                        table=table,
                        column=None,
                        category="INDEX",
                        target_type="(no migrado)",
                        code="INDEX_EXPRESSION_SKIPPED",
                        message=(
                            f"Índice '{index.name}' sobre expresiones ({', '.join(index.columns)}): no se migra; "
                            "crearlo a mano en el destino."
                        ),
                        severity="WARNING",
                    )
                )
                continue
            result.append(
                CanonicalIndex(name=index.name, original_name=index.name, columns=index_columns, unique=index.unique)
            )
        return result

    @staticmethod
    def _index_column(column: str) -> str:
        """Nombre de columna de un índice (Oracle da las columnas ``DESC`` como la expresión ``"COL"``)."""
        match = _QUOTED.match(column)
        return match.group(1) if match else column

    # ── vistas ───────────────────────────────────────────────────────────────
    def extract_views(self, schema: str) -> list[CanonicalView]:
        """Extrae todas las vistas del schema como IR canónico (definición y nombres de columna)."""
        snapshot = self._snapshot(schema, VIEW_KINDS)
        return [
            self._view(schema, view, [c.name for c in snapshot.columns(view.name)])
            for view in snapshot.views()
            if not view.materialized
        ]

    def _view(self, schema: str, view: ViewMeta, columns: list[str]) -> CanonicalView:
        return CanonicalView(
            name=view.name,
            original_name=view.name,
            schema=schema,
            query=(view.definition or "").strip(),
            columns=columns,
            comment=view.comment or "",
            warnings=[],
        )

    # ── routines ─────────────────────────────────────────────────────────────
    def extract_routines(self, schema: str) -> list[CanonicalRoutine]:
        """Extrae las funciones y procedures del schema como IR canónico (cuerpo = ``CREATE`` completo)."""
        snapshot = self._snapshot(schema, ROUTINE_KINDS)
        return [r for routine in snapshot.routines() if (r := self._routine(schema, routine)) is not None]

    def _routine(self, schema: str, routine: RoutineMeta) -> CanonicalRoutine | None:
        if routine.routine_type not in ("FUNCTION", "PROCEDURE"):
            return None
        body = (routine.definition or "").strip()
        return CanonicalRoutine(
            name=routine.name,
            original_name=routine.name,
            schema=schema,
            routine_type=routine.routine_type,
            body=body,
            return_type=routine.return_type or "",
            comment=routine.comment or "",
            warnings=[] if body else [no_body_warning(routine.name, self._ROUTINE_SOURCE)],
        )


__all__: list[str] = ["SnapshotSchemaExtractor", "metadata_source", "no_body_warning"]
