"""Manager falso que sirve un ``SchemaSnapshot`` en memoria (``get_schema_metadata``, ADR-003).

Para tests de consumidores (``analysis``, renderers…) que solo leen metadatos por lotes. Los datos se dan en forma
compacta y se convierten a los modelos neutros de ``metadata/``.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from typing import Any

from util_bbdd.metadata.model import (
    ALL_KINDS,
    ColumnMeta,
    ForeignKeyMeta,
    Kind,
    PrimaryKeyMeta,
    SchemaSnapshot,
    TableMeta,
    UniqueMeta,
)

# (restricción, columna, tabla referenciada, columna referenciada); varias filas con el mismo nombre = FK compuesta
FkRow = tuple[str, str, str, str]


def _foreign_keys(table: str, rows: Iterable[FkRow]) -> list[ForeignKeyMeta]:
    grouped: dict[str, list[FkRow]] = {}
    for row in rows:
        grouped.setdefault(row[0], []).append(row)
    return [
        ForeignKeyMeta(table, name, tuple(r[1] for r in rs), "", rs[0][2], tuple(r[3] for r in rs))
        for name, rs in grouped.items()
    ]


def build_catalog(
    *,
    tables: Iterable[str] = (),
    fk_by_table: Mapping[str, Iterable[FkRow]] | None = None,
    columns_by_table: Mapping[str, Iterable[tuple[str, str]]] | None = None,
    pk_by_table: Mapping[str, tuple[str, ...]] | None = None,
    uniques_by_table: Mapping[str, Iterable[tuple[str, ...]]] | None = None,
) -> dict[Kind, tuple[Any, ...]]:
    """Datos de snapshot por tipo a partir de la forma compacta de los tests."""
    return {
        Kind.TABLES: tuple(TableMeta(t) for t in tables),
        Kind.COLUMNS: tuple(
            ColumnMeta(table, name, i, data_type, data_type, True)
            for table, columns in (columns_by_table or {}).items()
            for i, (name, data_type) in enumerate(columns, 1)
        ),
        Kind.PRIMARY_KEYS: tuple(
            PrimaryKeyMeta(table, f"pk_{table}", columns) for table, columns in (pk_by_table or {}).items() if columns
        ),
        Kind.FOREIGN_KEYS: tuple(fk for t, rows in (fk_by_table or {}).items() for fk in _foreign_keys(t, rows)),
        Kind.UNIQUES: tuple(
            UniqueMeta(table, f"uq_{table}_{i}", columns)
            for table, uniques in (uniques_by_table or {}).items()
            for i, columns in enumerate(uniques, 1)
        ),
    }


class FakeCatalogManager:
    """Lo mínimo de un manager para ``analysis``: ``db_type``, contexto y ``get_schema_metadata``.

    ``data_by_context`` permite cambiar de schema con ``context`` (tablas homónimas en schemas distintos).
    """

    def __init__(
        self,
        db_type: str = "postgresql",
        *,
        data: dict[Kind, tuple[Any, ...]] | None = None,
        data_by_context: dict[str, dict[Kind, tuple[Any, ...]]] | None = None,
        context: str = "test_db",
    ) -> None:
        self.db_type = db_type
        self.database = context
        self.context = context
        self.data_by_context = data_by_context or {context: data or {}}
        self.calls: list[frozenset[Kind]] = []

    def get_query_context_database(self) -> str:
        return self.context

    def get_schema_metadata(self, schema: str | None = None, *, kinds: Collection[Kind] = ALL_KINDS) -> SchemaSnapshot:
        self.calls.append(frozenset(kinds))
        data = self.data_by_context[self.context]
        return SchemaSnapshot(self.db_type, schema or self.context, {k: data.get(k, ()) for k in kinds})
