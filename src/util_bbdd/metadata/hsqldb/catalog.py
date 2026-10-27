"""Catálogo de HSQLDB 2.x para ``MetadataSource``: ``INFORMATION_SCHEMA`` estándar + vistas ``SYSTEM_*`` (ADR-003).

Verificado contra HSQLDB 2.7.4 (JDBC con ``jaydebeapi``, ``paramstyle`` ``qmark``) en la sesión
2026-10-03-metadata-centralization. HSQLDB no tiene dialecto de SQLAlchemy: lo usan los managers con
:class:`~util_bbdd.metadata.source.DbapiCatalogExecutor`.

Diferencias con el registry JSON anterior, que fallaba en 9 de 16 consultas con HSQLDB 2.7.4 (H-19): los comentarios
están en ``SYSTEM_TABLES``/``SYSTEM_COLUMNS.REMARKS`` (no en ``TABLES``/``COLUMNS``), los índices en
``SYSTEM_INDEXINFO`` (no hay ``INFORMATION_SCHEMA.INDEXES``) y la definición de las vistas en ``VIEWS.VIEW_DEFINITION``.
HSQLDB guarda los ``NOT NULL`` como ``CHECK`` ``SYS_CT_*``: se descartan (ya están en ``nullable``). La firma de una
routine es su ``SPECIFIC_NAME`` (distingue sobrecargas).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..contracts import CatalogQuery
from ..model import (
    CheckMeta,
    ColumnMeta,
    DatabaseMeta,
    ForeignKeyMeta,
    IdentityMeta,
    IndexMeta,
    Kind,
    PrimaryKeyMeta,
    RoutineKey,
    RoutineMeta,
    RoutineParameterMeta,
    TableMeta,
    UniqueMeta,
    ViewMeta,
)

_IS = "INFORMATION_SCHEMA"
# Columna de filtro por tabla de las consultas sobre TABLE_CONSTRAINTS (alias tc).
_TC_TABLE_NAME = "tc.TABLE_NAME"
_SIZED = frozenset({"CHARACTER", "CHARACTER VARYING", "BINARY", "BINARY VARYING", "BIT", "BIT VARYING"})
_EXACT = frozenset({"NUMERIC", "DECIMAL"})
_IDENTITY = {"ALWAYS": "always", "BY DEFAULT": "by default"}


def _key_constraint_sql(kind: str) -> str:
    return (
        "SELECT tc.TABLE_NAME, tc.CONSTRAINT_NAME, k.COLUMN_NAME, k.ORDINAL_POSITION "
        f"FROM {_IS}.TABLE_CONSTRAINTS tc JOIN {_IS}.KEY_COLUMN_USAGE k "
        "ON k.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA AND k.CONSTRAINT_NAME = tc.CONSTRAINT_NAME "
        f"WHERE tc.TABLE_SCHEMA = :schema AND tc.CONSTRAINT_TYPE = '{kind}'{{filter}} "
        "ORDER BY tc.TABLE_NAME, tc.CONSTRAINT_NAME, k.ORDINAL_POSITION"
    )


# kind → (SQL con {filter}, columna por la que se filtra con :tables, o None si no admite filtro)
_SQL: dict[Kind, tuple[str, str | None]] = {
    Kind.TABLES: (
        f"SELECT t.TABLE_NAME, t.REMARKS FROM {_IS}.SYSTEM_TABLES t "
        "WHERE t.TABLE_SCHEM = :schema AND t.TABLE_TYPE = 'TABLE'{filter} ORDER BY t.TABLE_NAME",
        "t.TABLE_NAME",
    ),
    Kind.VIEWS: (
        f"SELECT v.TABLE_NAME, v.VIEW_DEFINITION, t.REMARKS FROM {_IS}.VIEWS v "
        f"LEFT JOIN {_IS}.SYSTEM_TABLES t ON t.TABLE_SCHEM = v.TABLE_SCHEMA AND t.TABLE_NAME = v.TABLE_NAME "
        "WHERE v.TABLE_SCHEMA = :schema{filter} ORDER BY v.TABLE_NAME",
        "v.TABLE_NAME",
    ),
    Kind.COLUMNS: (
        "SELECT c.TABLE_NAME, c.COLUMN_NAME, c.ORDINAL_POSITION, c.DATA_TYPE, c.IS_NULLABLE, c.COLUMN_DEFAULT, "
        "c.CHARACTER_MAXIMUM_LENGTH, c.NUMERIC_PRECISION, c.NUMERIC_SCALE, sc.REMARKS, c.COLLATION_NAME, "
        "c.IS_IDENTITY, c.IDENTITY_GENERATION, c.IS_GENERATED, c.GENERATION_EXPRESSION "
        f"FROM {_IS}.COLUMNS c LEFT JOIN {_IS}.SYSTEM_COLUMNS sc ON sc.TABLE_SCHEM = c.TABLE_SCHEMA "
        "AND sc.TABLE_NAME = c.TABLE_NAME AND sc.COLUMN_NAME = c.COLUMN_NAME "
        "WHERE c.TABLE_SCHEMA = :schema{filter} ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION",
        "c.TABLE_NAME",
    ),
    Kind.PRIMARY_KEYS: (_key_constraint_sql("PRIMARY KEY"), _TC_TABLE_NAME),
    Kind.UNIQUES: (_key_constraint_sql("UNIQUE"), _TC_TABLE_NAME),
    Kind.CHECKS: (
        "SELECT tc.TABLE_NAME, tc.CONSTRAINT_NAME, ck.CHECK_CLAUSE "
        f"FROM {_IS}.TABLE_CONSTRAINTS tc JOIN {_IS}.CHECK_CONSTRAINTS ck "
        "ON ck.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA AND ck.CONSTRAINT_NAME = tc.CONSTRAINT_NAME "
        "WHERE tc.TABLE_SCHEMA = :schema AND tc.CONSTRAINT_TYPE = 'CHECK'{filter} "
        "ORDER BY tc.TABLE_NAME, tc.CONSTRAINT_NAME",
        _TC_TABLE_NAME,
    ),
    Kind.FOREIGN_KEYS: (
        "SELECT k.TABLE_NAME, k.CONSTRAINT_NAME, k.COLUMN_NAME, u.TABLE_SCHEMA, u.TABLE_NAME, u.COLUMN_NAME, "
        f"rc.DELETE_RULE, rc.UPDATE_RULE, k.ORDINAL_POSITION FROM {_IS}.KEY_COLUMN_USAGE k "
        f"JOIN {_IS}.REFERENTIAL_CONSTRAINTS rc "
        "ON rc.CONSTRAINT_SCHEMA = k.CONSTRAINT_SCHEMA AND rc.CONSTRAINT_NAME = k.CONSTRAINT_NAME "
        f"JOIN {_IS}.KEY_COLUMN_USAGE u ON u.CONSTRAINT_SCHEMA = rc.UNIQUE_CONSTRAINT_SCHEMA "
        "AND u.CONSTRAINT_NAME = rc.UNIQUE_CONSTRAINT_NAME AND u.ORDINAL_POSITION = k.POSITION_IN_UNIQUE_CONSTRAINT "
        "WHERE k.TABLE_SCHEMA = :schema{filter} ORDER BY k.TABLE_NAME, k.CONSTRAINT_NAME, k.ORDINAL_POSITION",
        "k.TABLE_NAME",
    ),
    Kind.INDEXES: (
        "SELECT i.TABLE_NAME, i.INDEX_NAME, i.NON_UNIQUE, tc.CONSTRAINT_TYPE, i.COLUMN_NAME, i.ORDINAL_POSITION "
        f"FROM {_IS}.SYSTEM_INDEXINFO i LEFT JOIN {_IS}.TABLE_CONSTRAINTS tc ON tc.TABLE_SCHEMA = i.TABLE_SCHEM "
        "AND tc.CONSTRAINT_NAME = i.INDEX_NAME AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY' "
        "WHERE i.TABLE_SCHEM = :schema{filter} ORDER BY i.TABLE_NAME, i.INDEX_NAME, i.ORDINAL_POSITION",
        "i.TABLE_NAME",
    ),
    Kind.IDENTITY: (
        f"SELECT c.TABLE_NAME, c.COLUMN_NAME FROM {_IS}.COLUMNS c "
        "WHERE c.TABLE_SCHEMA = :schema AND c.IS_IDENTITY = 'YES'{filter} ORDER BY c.TABLE_NAME, c.COLUMN_NAME",
        "c.TABLE_NAME",
    ),
    Kind.ROUTINES: (
        "SELECT r.ROUTINE_NAME, r.SPECIFIC_NAME, r.ROUTINE_TYPE, r.DATA_TYPE, r.ROUTINE_DEFINITION, "
        f"r.EXTERNAL_LANGUAGE FROM {_IS}.ROUTINES r WHERE r.ROUTINE_SCHEMA = :schema "
        "ORDER BY r.ROUTINE_NAME, r.SPECIFIC_NAME",
        None,
    ),
    Kind.ROUTINE_PARAMETERS: (
        "SELECT r.ROUTINE_NAME, p.SPECIFIC_NAME, p.ORDINAL_POSITION, p.PARAMETER_NAME, p.PARAMETER_MODE, p.DATA_TYPE "
        f"FROM {_IS}.PARAMETERS p JOIN {_IS}.ROUTINES r "
        "ON r.SPECIFIC_SCHEMA = p.SPECIFIC_SCHEMA AND r.SPECIFIC_NAME = p.SPECIFIC_NAME "
        "WHERE p.SPECIFIC_SCHEMA = :schema ORDER BY p.SPECIFIC_NAME, p.ORDINAL_POSITION",
        None,
    ),
    Kind.DATABASE: (
        f"SELECT DATABASE_VERSION(), s.DEFAULT_CHARACTER_SET_NAME FROM {_IS}.SCHEMATA s WHERE s.SCHEMA_NAME = :schema",
        None,
    ),
}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: Any) -> int | None:
    return int(value) if value is not None else None


def _grouped(rows: Sequence[Sequence[Any]]) -> dict[tuple[str, str], list[Sequence[Any]]]:
    groups: dict[tuple[str, str], list[Sequence[Any]]] = {}
    for row in rows:
        groups.setdefault((str(row[0]), str(row[1])), []).append(row)
    return groups


def _data_type(base: str, length: int | None, precision: int | None, scale: int | None) -> str:
    """Tipo completo: ``base(length)`` en los tipos con tamaño, ``base(p,s)`` en los exactos; si no, ``base``."""
    if base in _SIZED and length is not None:
        return f"{base}({length})"
    if base in _EXACT and precision is not None:
        return f"{base}({precision},{scale or 0})"
    return base


def _column_from_row(r: Sequence[Any]) -> ColumnMeta:
    """``ColumnMeta`` de una fila de ``_SQL[Kind.COLUMNS]``."""
    base = str(r[3])
    length, precision, scale = _int(r[6]), _int(r[7]), _int(r[8])
    exact = base in _EXACT
    generated = _text(r[14]) if str(r[13] or "").upper() == "ALWAYS" else None
    collation = _text(r[10])
    return ColumnMeta(
        table=str(r[0]),
        name=str(r[1]),
        ordinal=int(r[2]),
        data_type=_data_type(base, length, precision, scale),
        base_type=base,
        nullable=str(r[4]).upper() == "YES",
        length=length if base in _SIZED else None,
        precision=precision if exact else None,
        scale=scale if exact else None,
        default=None if generated else _text(r[5]),
        comment=_text(r[9]),
        collation=None if collation == "SQL_TEXT" else collation,  # SQL_TEXT: la de por defecto
        identity=_IDENTITY.get(str(r[12] or "").upper()) if str(r[11]).upper() == "YES" else None,
        generated=generated,
    )


class HSQLDBCatalog:
    """:class:`~util_bbdd.metadata.contracts.CatalogDialect` de HSQLDB 2.x."""

    name = "hsqldb"
    sqlalchemy_names: frozenset[str] = frozenset()

    def current_schema_sql(self) -> str:
        return "VALUES (CURRENT_SCHEMA)"

    def server_version_sql(self) -> str:
        """Versión del servidor como texto (G13 de util_bbdd_web, v4.6.0)."""
        return "VALUES (DATABASE_VERSION())"

    def schema_names_sql(self) -> str:
        """Schemas visibles, una fila por schema con su nombre tal como lo guarda el catálogo (G17, v4.6.0)."""
        return "SELECT schema_name FROM information_schema.schemata ORDER BY schema_name"

    def normalize_name(self, name: str) -> str:
        """HSQLDB guarda en mayúsculas los nombres sin comillas (como Oracle)."""
        if len(name) > 1 and name[0] == name[-1] == '"':
            return name[1:-1]
        return name.upper() if name == name.lower() else name

    def query(self, kind: Kind, *, filtered: bool = False) -> CatalogQuery | None:
        entry = _SQL.get(kind)
        if entry is None:
            return None
        sql, column = entry
        fragment = f" AND {column} IN (:tables)" if filtered and column else ""
        return CatalogQuery(sql.replace("{filter}", fragment), filterable=column is not None)

    def parse(self, kind: Kind, rows: Sequence[Sequence[Any]], schema: str) -> tuple[Any, ...]:
        return tuple(getattr(self, f"_parse_{kind.value}")(rows, schema))

    # ── parseo por tipo ──────────────────────────────────────────────────────
    @staticmethod
    def _parse_tables(rows: Sequence[Sequence[Any]], schema: str) -> list[TableMeta]:
        return [TableMeta(str(r[0]), _text(r[1])) for r in rows]

    @staticmethod
    def _parse_views(rows: Sequence[Sequence[Any]], schema: str) -> list[ViewMeta]:
        return [ViewMeta(str(r[0]), _text(r[1]), _text(r[2])) for r in rows]

    @staticmethod
    def _parse_columns(rows: Sequence[Sequence[Any]], schema: str) -> list[ColumnMeta]:
        return [_column_from_row(r) for r in rows]

    @staticmethod
    def _parse_primary_keys(rows: Sequence[Sequence[Any]], schema: str) -> list[PrimaryKeyMeta]:
        return [PrimaryKeyMeta(t, n, tuple(str(r[2]) for r in g)) for (t, n), g in _grouped(rows).items()]

    @staticmethod
    def _parse_uniques(rows: Sequence[Sequence[Any]], schema: str) -> list[UniqueMeta]:
        return [UniqueMeta(t, n, tuple(str(r[2]) for r in g)) for (t, n), g in _grouped(rows).items()]

    @staticmethod
    def _parse_checks(rows: Sequence[Sequence[Any]], schema: str) -> list[CheckMeta]:
        """Sin los ``NOT NULL`` que HSQLDB guarda como ``CHECK`` ``SYS_CT_*`` (ya están en ``nullable``)."""
        return [
            CheckMeta(str(r[0]), str(r[1]), str(r[2]))
            for r in rows
            if not (str(r[1]).startswith("SYS_CT_") and str(r[2]).upper().endswith("IS NOT NULL"))
        ]

    @staticmethod
    def _parse_foreign_keys(rows: Sequence[Sequence[Any]], schema: str) -> list[ForeignKeyMeta]:
        return [
            ForeignKeyMeta(
                table=t,
                name=n,
                columns=tuple(str(r[2]) for r in g),
                ref_schema=str(g[0][3]),
                ref_table=str(g[0][4]),
                ref_columns=tuple(str(r[5]) for r in g),
                on_delete=_text(g[0][6]) or "NO ACTION",
                on_update=_text(g[0][7]) or "NO ACTION",
            )
            for (t, n), g in _grouped(rows).items()
        ]

    @staticmethod
    def _parse_indexes(rows: Sequence[Sequence[Any]], schema: str) -> list[IndexMeta]:
        return [
            IndexMeta(
                table=t,
                name=n,
                columns=tuple(str(r[4]) for r in g),
                unique=not bool(g[0][2]),
                primary=g[0][3] is not None,
            )
            for (t, n), g in _grouped(rows).items()
        ]

    @staticmethod
    def _parse_identity(rows: Sequence[Sequence[Any]], schema: str) -> list[IdentityMeta]:
        return [IdentityMeta(str(r[0]), str(r[1]), "identity") for r in rows]

    @staticmethod
    def _parse_routines(rows: Sequence[Sequence[Any]], schema: str) -> list[RoutineMeta]:
        return [
            RoutineMeta(
                name=str(r[0]),
                routine_type=str(r[2]).upper(),
                signature=str(r[1]),
                return_type=_text(r[3]),
                definition=_text(r[4]),
                language=_text(r[5]) or "SQL",
            )
            for r in rows
        ]

    @staticmethod
    def _parse_routine_parameters(rows: Sequence[Sequence[Any]], schema: str) -> list[RoutineParameterMeta]:
        return [
            RoutineParameterMeta(
                routine=RoutineKey(str(r[0]), str(r[1])),
                ordinal=int(r[2]),
                name=_text(r[3]),
                mode=(_text(r[4]) or "IN").upper(),
                data_type=str(r[5]),
            )
            for r in rows
        ]

    @staticmethod
    def _parse_database(rows: Sequence[Sequence[Any]], schema: str) -> list[DatabaseMeta]:
        return [DatabaseMeta(f"HSQLDB {r[0]}", _text(r[1])) for r in rows]


__all__: list[str] = ["HSQLDBCatalog"]
