"""Catálogo de PostgreSQL para ``MetadataSource``: una consulta ``pg_catalog`` por schema y tipo de objeto (ADR-003).

Solo ``pg_catalog``: las vistas de ``information_schema`` sobre constraints cuestan ≈ 95 ms por consulta en función del
catálogo **entero** de la base (baseline de la sesión 2026-10-03-metadata-centralization), mientras que la lectura de
las FK de un schema de 5000 tablas por ``pg_catalog`` cuesta ≈ 90 ms.

Los comentarios se unen con ``pg_description`` (no ``obj_description()`` por fila) y la secuencia de las columnas
``serial``/identidad sale de ``pg_depend`` (no ``pg_get_serial_sequence()`` por columna). Todas las consultas usan
``:schema`` y, las que admiten filtro, ``:tables``.
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

_FK_RULES = {"a": "NO ACTION", "r": "RESTRICT", "c": "CASCADE", "n": "SET NULL", "d": "SET DEFAULT"}
_PARAM_MODES = {"i": "IN", "o": "OUT", "b": "INOUT", "v": "VARIADIC", "t": "TABLE"}
_IDENTITY = {"a": "always", "d": "by default"}

_TABLE_FILTER = " AND c.relname IN (:tables)"
_DESCRIPTION = (
    "LEFT JOIN pg_catalog.pg_description d ON d.objoid = c.oid AND d.classoid = 'pg_catalog.pg_class'::regclass "
    "AND d.objsubid = 0"
)


def _constraints_sql(contype: str) -> str:
    """Constraints de un tipo con sus columnas en orden (``conkey``)."""
    return (
        "SELECT c.relname, con.conname, "
        "ARRAY(SELECT a.attname FROM unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord) "
        "JOIN pg_catalog.pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum ORDER BY k.ord) "
        "FROM pg_catalog.pg_constraint con "
        "JOIN pg_catalog.pg_class c ON c.oid = con.conrelid "
        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        f"WHERE n.nspname = :schema AND con.contype = '{contype}'"
    )


_SQL: dict[Kind, tuple[str, bool]] = {
    Kind.TABLES: (
        f"SELECT c.relname, d.description FROM pg_catalog.pg_class c "
        f"JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace {_DESCRIPTION} "
        f"WHERE n.nspname = :schema AND c.relkind IN ('r', 'p'){{filter}} ORDER BY c.relname",
        True,
    ),
    Kind.VIEWS: (
        f"SELECT c.relname, pg_catalog.pg_get_viewdef(c.oid), d.description, c.relkind = 'm' "
        f"FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace {_DESCRIPTION} "
        f"WHERE n.nspname = :schema AND c.relkind IN ('v', 'm'){{filter}} ORDER BY c.relname",
        True,
    ),
    Kind.COLUMNS: (
        "SELECT c.relname, a.attname, a.attnum, pg_catalog.format_type(a.atttypid, a.atttypmod), "
        "COALESCE(bt.typname, t.typname), a.attnotnull, a.atttypid, a.atttypmod, "
        "pg_catalog.pg_get_expr(ad.adbin, ad.adrelid), cd.description, "
        "CASE WHEN a.attcollation <> t.typcollation THEN co.collname END, a.attidentity, a.attgenerated "
        "FROM pg_catalog.pg_attribute a "
        "JOIN pg_catalog.pg_class c ON c.oid = a.attrelid "
        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        "JOIN pg_catalog.pg_type t ON t.oid = a.atttypid "
        "LEFT JOIN pg_catalog.pg_type bt ON t.typtype = 'd' AND bt.oid = t.typbasetype "
        "LEFT JOIN pg_catalog.pg_attrdef ad ON ad.adrelid = a.attrelid AND ad.adnum = a.attnum "
        "LEFT JOIN pg_catalog.pg_collation co ON co.oid = a.attcollation "
        "LEFT JOIN pg_catalog.pg_description cd ON cd.objoid = c.oid "
        "AND cd.classoid = 'pg_catalog.pg_class'::regclass AND cd.objsubid = a.attnum "
        "WHERE n.nspname = :schema AND c.relkind IN ('r', 'p', 'v', 'm', 'f') AND a.attnum > 0 "
        "AND NOT a.attisdropped{filter} ORDER BY c.relname, a.attnum",
        True,
    ),
    Kind.PRIMARY_KEYS: (_constraints_sql("p") + "{filter} ORDER BY c.relname", True),
    Kind.UNIQUES: (_constraints_sql("u") + "{filter} ORDER BY c.relname, con.conname", True),
    Kind.CHECKS: (
        "SELECT c.relname, con.conname, pg_catalog.pg_get_constraintdef(con.oid) "
        "FROM pg_catalog.pg_constraint con JOIN pg_catalog.pg_class c ON c.oid = con.conrelid "
        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = :schema AND con.contype = 'c'{filter} ORDER BY c.relname, con.conname",
        True,
    ),
    Kind.FOREIGN_KEYS: (
        "SELECT c.relname, con.conname, "
        "ARRAY(SELECT a.attname FROM unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord) "
        "JOIN pg_catalog.pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum ORDER BY k.ord), "
        "rn.nspname, rc.relname, "
        "ARRAY(SELECT a.attname FROM unnest(con.confkey) WITH ORDINALITY AS k(attnum, ord) "
        "JOIN pg_catalog.pg_attribute a ON a.attrelid = con.confrelid AND a.attnum = k.attnum ORDER BY k.ord), "
        "con.confdeltype, con.confupdtype "
        "FROM pg_catalog.pg_constraint con "
        "JOIN pg_catalog.pg_class c ON c.oid = con.conrelid "
        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        "JOIN pg_catalog.pg_class rc ON rc.oid = con.confrelid "
        "JOIN pg_catalog.pg_namespace rn ON rn.oid = rc.relnamespace "
        "WHERE n.nspname = :schema AND con.contype = 'f'{filter} ORDER BY c.relname, con.conname",
        True,
    ),
    Kind.INDEXES: (
        "SELECT c.relname, ic.relname, i.indisunique, i.indisprimary, am.amname, "
        "pg_catalog.pg_get_expr(i.indpred, i.indrelid), "
        "ARRAY(SELECT pg_catalog.pg_get_indexdef(i.indexrelid, k, true) "
        "FROM generate_series(1, i.indnkeyatts) AS k ORDER BY k) "
        "FROM pg_catalog.pg_index i "
        "JOIN pg_catalog.pg_class ic ON ic.oid = i.indexrelid "
        "JOIN pg_catalog.pg_class c ON c.oid = i.indrelid "
        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        "JOIN pg_catalog.pg_am am ON am.oid = ic.relam "
        "WHERE n.nspname = :schema{filter} ORDER BY c.relname, ic.relname",
        True,
    ),
    Kind.IDENTITY: (
        "SELECT c.relname, a.attname, a.attidentity, sn.nspname, s.relname "
        "FROM pg_catalog.pg_depend dep "
        "JOIN pg_catalog.pg_class s ON s.oid = dep.objid AND s.relkind = 'S' "
        "JOIN pg_catalog.pg_namespace sn ON sn.oid = s.relnamespace "
        "JOIN pg_catalog.pg_class c ON c.oid = dep.refobjid "
        "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
        "JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid AND a.attnum = dep.refobjsubid "
        "WHERE dep.classid = 'pg_catalog.pg_class'::regclass AND dep.refclassid = 'pg_catalog.pg_class'::regclass "
        "AND dep.deptype IN ('a', 'i') AND n.nspname = :schema{filter} ORDER BY c.relname, a.attnum",
        True,
    ),
    Kind.ROUTINES: (
        "SELECT p.proname, p.prokind, pg_catalog.pg_get_function_identity_arguments(p.oid), "
        "CASE WHEN p.prokind = 'f' THEN pg_catalog.pg_get_function_result(p.oid) END, "
        "pg_catalog.pg_get_functiondef(p.oid), d.description, l.lanname "
        "FROM pg_catalog.pg_proc p "
        "JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace "
        "JOIN pg_catalog.pg_language l ON l.oid = p.prolang "
        "LEFT JOIN pg_catalog.pg_description d ON d.objoid = p.oid "
        "AND d.classoid = 'pg_catalog.pg_proc'::regclass AND d.objsubid = 0 "
        # Sin agregados ni funciones ventana: pg_get_functiondef falla con ellos (hotfix de v0.30.0)
        "WHERE n.nspname = :schema AND p.prokind IN ('f', 'p') ORDER BY p.proname, p.oid",
        False,
    ),
    Kind.ROUTINE_PARAMETERS: (
        "SELECT p.proname, pg_catalog.pg_get_function_identity_arguments(p.oid), arg.ord, arg.name, arg.mode, "
        "pg_catalog.format_type(arg.typ, NULL), "
        "CASE WHEN COALESCE(arg.mode, 'i') IN ('i', 'b', 'v') "
        "THEN pg_catalog.pg_get_function_arg_default(p.oid, arg.ord::int) END "
        "FROM pg_catalog.pg_proc p "
        "JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace "
        "CROSS JOIN LATERAL unnest(COALESCE(p.proallargtypes, p.proargtypes::oid[]), p.proargmodes, p.proargnames) "
        "WITH ORDINALITY AS arg(typ, mode, name, ord) "
        "WHERE n.nspname = :schema AND p.prokind IN ('f', 'p') ORDER BY p.proname, p.oid, arg.ord",
        False,
    ),
    Kind.DATABASE: (
        "SELECT pg_catalog.version(), pg_catalog.pg_encoding_to_char(db.encoding), db.datcollate "
        "FROM pg_catalog.pg_database db WHERE db.datname = pg_catalog.current_database()",
        False,
    ),
}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text != "" else None


def _char(value: Any) -> str:
    """Columna ``"char"`` de ``pg_catalog`` como texto (``asyncpg`` la devuelve como ``bytes``); ``""`` si es nula."""
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        return value.decode("ascii", errors="replace")
    return str(value)


def _names(value: Any) -> tuple[str, ...]:
    """Array de PostgreSQL (lista en psycopg; texto ``{a,b}`` en drivers que no lo convierten)."""
    if value is None:
        return ()
    if isinstance(value, str):
        inner = value.strip("{}")
        return tuple(part.strip('"') for part in inner.split(",")) if inner else ()
    return tuple(str(v) for v in value)


def _type_modifiers(type_oid: int, typmod: int) -> tuple[int | None, int | None, int | None]:
    """(longitud, precisión, escala) declaradas a partir de ``atttypmod``."""
    if typmod is None or typmod < 0:
        return None, None, None
    if type_oid in (1042, 1043):  # bpchar, varchar
        return typmod - 4, None, None
    if type_oid == 1700:  # numeric
        mod = typmod - 4
        return None, (mod >> 16) & 0xFFFF, mod & 0xFFFF
    return None, None, None


class PostgreSQLCatalog:
    """:class:`~util_bbdd.metadata.contracts.CatalogDialect` de PostgreSQL."""

    name = "postgresql"
    sqlalchemy_names = frozenset({"postgresql"})

    def current_schema_sql(self) -> str:
        return "SELECT pg_catalog.current_schema()"

    def normalize_name(self, name: str) -> str:
        """PostgreSQL guarda en minúsculas los nombres sin comillas, pero el catálogo se consulta con el nombre exacto."""
        return name[1:-1] if len(name) > 1 and name[0] == name[-1] == '"' else name

    def query(self, kind: Kind, *, filtered: bool = False) -> CatalogQuery | None:
        entry = _SQL.get(kind)
        if entry is None:
            return None
        sql, filterable = entry
        use_filter = filtered and filterable
        return CatalogQuery(sql.replace("{filter}", _TABLE_FILTER if use_filter else ""), filterable=filterable)

    def parse(self, kind: Kind, rows: Sequence[Sequence[Any]], schema: str) -> tuple[Any, ...]:
        return tuple(getattr(self, f"_parse_{kind.value}")(rows, schema))

    # ── parseo por tipo ──────────────────────────────────────────────────────
    @staticmethod
    def _parse_tables(rows: Sequence[Sequence[Any]], schema: str) -> list[TableMeta]:
        return [TableMeta(str(r[0]), _text(r[1])) for r in rows]

    @staticmethod
    def _parse_views(rows: Sequence[Sequence[Any]], schema: str) -> list[ViewMeta]:
        return [ViewMeta(str(r[0]), _text(r[1]), _text(r[2]), bool(r[3])) for r in rows]

    @staticmethod
    def _parse_columns(rows: Sequence[Sequence[Any]], schema: str) -> list[ColumnMeta]:
        out = []
        for r in rows:
            length, precision, scale = _type_modifiers(int(r[6]), int(r[7]) if r[7] is not None else -1)
            out.append(
                ColumnMeta(
                    table=str(r[0]),
                    name=str(r[1]),
                    ordinal=int(r[2]),
                    data_type=str(r[3]),
                    base_type=str(r[4]),
                    nullable=not bool(r[5]),
                    length=length,
                    precision=precision,
                    scale=scale,
                    default=None if _char(r[12]) == "s" else _text(r[8]),
                    comment=_text(r[9]),
                    collation=_text(r[10]),
                    identity=_IDENTITY.get(_char(r[11])),
                    generated=_text(r[8]) if _char(r[12]) == "s" else None,
                )
            )
        return out

    @staticmethod
    def _parse_primary_keys(rows: Sequence[Sequence[Any]], schema: str) -> list[PrimaryKeyMeta]:
        return [PrimaryKeyMeta(str(r[0]), str(r[1]), _names(r[2])) for r in rows]

    @staticmethod
    def _parse_uniques(rows: Sequence[Sequence[Any]], schema: str) -> list[UniqueMeta]:
        return [UniqueMeta(str(r[0]), str(r[1]), _names(r[2])) for r in rows]

    @staticmethod
    def _parse_checks(rows: Sequence[Sequence[Any]], schema: str) -> list[CheckMeta]:
        return [CheckMeta(str(r[0]), str(r[1]), str(r[2])) for r in rows]

    @staticmethod
    def _parse_foreign_keys(rows: Sequence[Sequence[Any]], schema: str) -> list[ForeignKeyMeta]:
        return [
            ForeignKeyMeta(
                table=str(r[0]),
                name=str(r[1]),
                columns=_names(r[2]),
                ref_schema=str(r[3]),
                ref_table=str(r[4]),
                ref_columns=_names(r[5]),
                on_delete=_FK_RULES.get(_char(r[6]), "NO ACTION"),
                on_update=_FK_RULES.get(_char(r[7]), "NO ACTION"),
            )
            for r in rows
        ]

    @staticmethod
    def _parse_indexes(rows: Sequence[Sequence[Any]], schema: str) -> list[IndexMeta]:
        return [
            IndexMeta(
                table=str(r[0]),
                name=str(r[1]),
                columns=_names(r[6]),
                unique=bool(r[2]),
                primary=bool(r[3]),
                method=_text(r[4]),
                predicate=_text(r[5]),
            )
            for r in rows
        ]

    @staticmethod
    def _parse_identity(rows: Sequence[Sequence[Any]], schema: str) -> list[IdentityMeta]:
        return [
            IdentityMeta(
                table=str(r[0]),
                column=str(r[1]),
                kind="identity" if _char(r[2]) in _IDENTITY else "sequence",
                sequence=str(r[4]),
                sequence_schema=str(r[3]),
            )
            for r in rows
        ]

    @staticmethod
    def _parse_routines(rows: Sequence[Sequence[Any]], schema: str) -> list[RoutineMeta]:
        return [
            RoutineMeta(
                name=str(r[0]),
                routine_type="PROCEDURE" if _char(r[1]) == "p" else "FUNCTION",
                signature=str(r[2] or ""),
                return_type=_text(r[3]),
                definition=_text(r[4]),
                comment=_text(r[5]),
                language=_text(r[6]),
            )
            for r in rows
        ]

    @staticmethod
    def _parse_routine_parameters(rows: Sequence[Sequence[Any]], schema: str) -> list[RoutineParameterMeta]:
        return [
            RoutineParameterMeta(
                routine=RoutineKey(str(r[0]), str(r[1] or "")),
                ordinal=int(r[2]),
                name=_text(r[3]),
                mode=_PARAM_MODES.get(_char(r[4]) or "i", "IN"),
                data_type=str(r[5]),
                default=_text(r[6]),
            )
            for r in rows
        ]

    @staticmethod
    def _parse_database(rows: Sequence[Sequence[Any]], schema: str) -> list[DatabaseMeta]:
        return [DatabaseMeta(str(r[0]), _text(r[1]), _text(r[2])) for r in rows]


__all__: list[str] = ["PostgreSQLCatalog"]
