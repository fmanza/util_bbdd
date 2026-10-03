"""Catálogo de SQLite para ``MetadataSource``: PRAGMA como funciones tabla unidas a ``sqlite_master`` (ADR-003).

Una consulta por tipo de objeto en lugar de un ``PRAGMA`` por tabla: ``pragma_table_xinfo``, ``pragma_index_list``,
``pragma_index_xinfo`` y ``pragma_foreign_key_list`` se usan como funciones tabla (SQLite 3.16+,
https://www.sqlite.org/pragma.html#pragfunc) unidas a ``sqlite_master``.

Límites de SQLite (no se inventan valores):

- solo el schema ``main`` (``sqlite_master`` de otro schema no admite bind); con otro schema el snapshot está vacío;
- los PRAGMA no dan nombres de constraint (``PrimaryKeyMeta.name`` y ``ForeignKeyMeta.name`` vacíos), ni las ``CHECK``
  (``Kind.CHECKS`` vacío), ni la expresión de las columnas calculadas o de los índices funcionales (``<expresión>``);
- sin routines.

Identidad: la columna ``INTEGER PRIMARY KEY`` única (alias de ``rowid``), con o sin ``AUTOINCREMENT``.
"""

from __future__ import annotations

import re

from collections.abc import Sequence
from typing import Any

from ..contracts import CatalogQuery
from ..model import (
    ColumnMeta,
    DatabaseMeta,
    ForeignKeyMeta,
    IdentityMeta,
    IndexMeta,
    Kind,
    PrimaryKeyMeta,
    TableMeta,
    UniqueMeta,
    ViewMeta,
)

EXPRESSION = "<expresión>"
_USER = "m.name NOT LIKE 'sqlite~_%' ESCAPE '~' AND :schema = 'main'"
_ROWID_ALIAS = (
    "c.pk = 1 AND upper(c.type) = 'INTEGER' AND (SELECT count(*) FROM pragma_table_info(m.name) k WHERE k.pk > 0) = 1"
)
_MODIFIERS = re.compile(r"\(\s*(\d+)\s*(?:,\s*(\d+)\s*)?\)")

_SQL: dict[Kind, str] = {
    Kind.TABLES: f"SELECT m.name FROM sqlite_master m WHERE m.type = 'table' AND {_USER}{{filter}} ORDER BY m.name",
    Kind.VIEWS: f"SELECT m.name, m.sql FROM sqlite_master m WHERE m.type = 'view' AND {_USER}{{filter}} ORDER BY m.name",
    Kind.COLUMNS: (
        f'SELECT m.name, c.name, c.cid, c.type, c."notnull", c.dflt_value, c.hidden, CASE WHEN {_ROWID_ALIAS} '
        "THEN 1 ELSE 0 END "
        "FROM sqlite_master m JOIN pragma_table_xinfo(m.name) c "
        f"WHERE m.type IN ('table', 'view') AND {_USER}{{filter}} ORDER BY m.name, c.cid"
    ),
    Kind.PRIMARY_KEYS: (
        "SELECT m.name, c.name, c.pk FROM sqlite_master m JOIN pragma_table_info(m.name) c "
        f"WHERE m.type = 'table' AND c.pk > 0 AND {_USER}{{filter}} ORDER BY m.name, c.pk"
    ),
    Kind.UNIQUES: (
        "SELECT m.name, il.name, ii.name, ii.seqno FROM sqlite_master m "
        "JOIN pragma_index_list(m.name) il JOIN pragma_index_info(il.name) ii "
        f"WHERE m.type = 'table' AND il.origin = 'u' AND {_USER}{{filter}} ORDER BY m.name, il.name, ii.seqno"
    ),
    Kind.FOREIGN_KEYS: (
        'SELECT m.name, f.id, f.seq, f."table", f."from", f."to", f.on_delete, f.on_update '
        "FROM sqlite_master m JOIN pragma_foreign_key_list(m.name) f "
        f"WHERE m.type = 'table' AND {_USER}{{filter}} ORDER BY m.name, f.id, f.seq"
    ),
    Kind.INDEXES: (
        'SELECT m.name, il.name, il."unique", il.origin, il.partial, ii.seqno, ii.name FROM sqlite_master m '
        "JOIN pragma_index_list(m.name) il JOIN pragma_index_xinfo(il.name) ii "
        f"WHERE m.type = 'table' AND ii.key = 1 AND {_USER}{{filter}} ORDER BY m.name, il.name, ii.seqno"
    ),
    Kind.IDENTITY: (
        "SELECT m.name, c.name FROM sqlite_master m JOIN pragma_table_info(m.name) c "
        f"WHERE m.type = 'table' AND {_ROWID_ALIAS} AND {_USER}{{filter}} ORDER BY m.name"
    ),
    Kind.DATABASE: "SELECT sqlite_version(), (SELECT encoding FROM pragma_encoding)",
}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _modifiers(declared: str) -> tuple[int | None, int | None]:
    match = _MODIFIERS.search(declared)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2)) if match.group(2) else None


class SQLiteCatalog:
    """:class:`~util_bbdd.metadata.contracts.CatalogDialect` de SQLite (3.16+; solo el schema ``main``)."""

    name = "sqlite"
    sqlalchemy_names = frozenset({"sqlite"})

    def current_schema_sql(self) -> str:
        return "SELECT 'main'"

    def normalize_name(self, name: str) -> str:
        return name[1:-1] if len(name) > 1 and name[0] == name[-1] and name[0] in '"`' else name

    def query(self, kind: Kind, *, filtered: bool = False) -> CatalogQuery | None:
        sql = _SQL.get(kind)
        if sql is None:
            return None
        filterable = "{filter}" in sql
        fragment = " AND m.name IN (:tables)" if filtered and filterable else ""
        return CatalogQuery(sql.replace("{filter}", fragment), filterable=filterable)

    def parse(self, kind: Kind, rows: Sequence[Sequence[Any]], schema: str) -> tuple[Any, ...]:
        return tuple(getattr(self, f"_parse_{kind.value}")(rows, schema))

    # ── parseo por tipo ──────────────────────────────────────────────────────
    @staticmethod
    def _parse_tables(rows: Sequence[Sequence[Any]], schema: str) -> list[TableMeta]:
        return [TableMeta(str(r[0])) for r in rows]

    @staticmethod
    def _parse_views(rows: Sequence[Sequence[Any]], schema: str) -> list[ViewMeta]:
        return [ViewMeta(str(r[0]), _text(r[1])) for r in rows]

    @staticmethod
    def _parse_columns(rows: Sequence[Sequence[Any]], schema: str) -> list[ColumnMeta]:
        out = []
        for r in rows:
            declared = str(r[3] or "")
            base = declared.split("(")[0].strip().lower()
            first, second = _modifiers(declared)
            numeric = base in ("numeric", "decimal")
            out.append(
                ColumnMeta(
                    table=str(r[0]),
                    name=str(r[1]),
                    ordinal=int(r[2]) + 1,
                    data_type=declared,
                    base_type=base,
                    nullable=not bool(r[4]),
                    length=first if first is not None and not numeric else None,
                    precision=first if numeric else None,
                    scale=second if numeric else None,
                    default=_text(r[5]),
                    identity="by default" if int(r[7]) else None,
                    generated=EXPRESSION if int(r[6] or 0) in (2, 3) else None,
                )
            )
        return out

    @staticmethod
    def _parse_primary_keys(rows: Sequence[Sequence[Any]], schema: str) -> list[PrimaryKeyMeta]:
        columns: dict[str, list[str]] = {}
        for r in rows:
            columns.setdefault(str(r[0]), []).append(str(r[1]))
        return [PrimaryKeyMeta(table, "", tuple(cols)) for table, cols in columns.items()]

    @staticmethod
    def _parse_uniques(rows: Sequence[Sequence[Any]], schema: str) -> list[UniqueMeta]:
        groups: dict[tuple[str, str], list[str]] = {}
        for r in rows:
            groups.setdefault((str(r[0]), str(r[1])), []).append(str(r[2]))
        return [UniqueMeta(t, n, tuple(cols)) for (t, n), cols in groups.items()]

    @staticmethod
    def _parse_foreign_keys(rows: Sequence[Sequence[Any]], schema: str) -> list[ForeignKeyMeta]:
        groups: dict[tuple[str, int], list[Sequence[Any]]] = {}
        for r in rows:
            groups.setdefault((str(r[0]), int(r[1])), []).append(r)
        return [
            ForeignKeyMeta(
                table=table,
                name="",
                columns=tuple(str(r[4]) for r in g),
                ref_schema=schema,
                ref_table=str(g[0][3]),
                ref_columns=tuple(str(r[5] or "") for r in g),  # vacío si referencia la PK implícitamente
                on_delete=str(g[0][6] or "NO ACTION"),
                on_update=str(g[0][7] or "NO ACTION"),
            )
            for (table, _), g in groups.items()
        ]

    @staticmethod
    def _parse_indexes(rows: Sequence[Sequence[Any]], schema: str) -> list[IndexMeta]:
        groups: dict[tuple[str, str], list[Sequence[Any]]] = {}
        for r in rows:
            groups.setdefault((str(r[0]), str(r[1])), []).append(r)
        return [
            IndexMeta(
                table=t,
                name=n,
                columns=tuple(str(r[6]) if r[6] is not None else EXPRESSION for r in g),
                unique=bool(g[0][2]),
                primary=str(g[0][3]) == "pk",
                predicate=EXPRESSION if int(g[0][4] or 0) else None,
            )
            for (t, n), g in groups.items()
        ]

    @staticmethod
    def _parse_identity(rows: Sequence[Sequence[Any]], schema: str) -> list[IdentityMeta]:
        return [IdentityMeta(str(r[0]), str(r[1]), "identity") for r in rows]

    @staticmethod
    def _parse_database(rows: Sequence[Sequence[Any]], schema: str) -> list[DatabaseMeta]:
        return [DatabaseMeta(f"SQLite {r[0]}", _text(r[1])) for r in rows]


__all__: list[str] = ["EXPRESSION", "SQLiteCatalog"]
