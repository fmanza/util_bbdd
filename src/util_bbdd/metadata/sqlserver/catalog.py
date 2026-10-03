"""Catálogo de SQL Server para ``MetadataSource``: una consulta ``sys.*`` por schema y tipo de objeto (ADR-003).

Solo vistas de catálogo ``sys.*`` (no ``INFORMATION_SCHEMA``: trunca ``VIEW_DEFINITION`` a 4000 caracteres, no tiene
``PARAMETER_DEFAULT`` —H-17— y su coste por consulta crece con el catálogo: 9 ms con 50 tablas, 48 ms con 500 en el
baseline de la sesión 2026-10-03-metadata-centralization). El schema es el de la base de datos de la conexión.

Definiciones de vistas y routines con ``OBJECT_DEFINITION`` (sentencia ``CREATE`` completa; ``NULL`` si está cifrada o
sin permiso ``VIEW DEFINITION``). Comentarios: propiedad extendida ``MS_Description``.
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

_ROUTINE_TYPES = {"P": "PROCEDURE", "PC": "PROCEDURE", "FN": "FUNCTION", "IF": "FUNCTION", "TF": "FUNCTION",
                  "FS": "FUNCTION", "FT": "FUNCTION"}  # fmt: skip
_CLR = frozenset({"PC", "FS", "FT"})
_SIZED = frozenset({"varchar", "char", "varbinary", "binary", "nvarchar", "nchar"})
_EXACT = frozenset({"decimal", "numeric"})
_FRACTIONAL = frozenset({"datetime2", "time", "datetimeoffset"})

_DESCRIPTION = (
    "LEFT JOIN sys.extended_properties ep ON ep.class = 1 AND ep.major_id = {obj}.object_id "
    "AND ep.minor_id = {minor} AND ep.name = 'MS_Description'"
)


def _key_constraints_sql(kind: str) -> str:
    return (
        "SELECT t.name, kc.name, c.name, ic.key_ordinal FROM sys.key_constraints kc "
        "JOIN sys.tables t ON t.object_id = kc.parent_object_id "
        "JOIN sys.schemas s ON s.schema_id = t.schema_id "
        "JOIN sys.index_columns ic ON ic.object_id = kc.parent_object_id AND ic.index_id = kc.unique_index_id "
        "JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id "
        f"WHERE s.name = :schema AND kc.type = '{kind}'{{filter}} ORDER BY t.name, kc.name, ic.key_ordinal"
    )


# kind → (SQL con {filter}, columna por la que se filtra con :tables, o None si no admite filtro)
_SQL: dict[Kind, tuple[str, str | None]] = {
    Kind.TABLES: (
        "SELECT t.name, CAST(ep.value AS NVARCHAR(4000)) FROM sys.tables t "
        "JOIN sys.schemas s ON s.schema_id = t.schema_id "
        + _DESCRIPTION.format(obj="t", minor="0")
        + " WHERE s.name = :schema AND t.is_ms_shipped = 0{filter} ORDER BY t.name",
        "t.name",
    ),
    Kind.VIEWS: (
        "SELECT v.name, OBJECT_DEFINITION(v.object_id), CAST(ep.value AS NVARCHAR(4000)) FROM sys.views v "
        "JOIN sys.schemas s ON s.schema_id = v.schema_id "
        + _DESCRIPTION.format(obj="v", minor="0")
        + " WHERE s.name = :schema AND v.is_ms_shipped = 0{filter} ORDER BY v.name",
        "v.name",
    ),
    Kind.COLUMNS: (
        "SELECT o.name, c.name, c.column_id, TYPE_NAME(c.user_type_id), TYPE_NAME(c.system_type_id), c.max_length, "
        "c.precision, c.scale, c.is_nullable, dc.definition, CAST(ep.value AS NVARCHAR(4000)), "
        "CASE WHEN c.collation_name <> CAST(DATABASEPROPERTYEX(DB_NAME(), 'Collation') AS sysname) "
        "THEN c.collation_name END, c.is_identity, cc.definition "
        "FROM sys.columns c "
        "JOIN sys.objects o ON o.object_id = c.object_id AND o.type IN ('U', 'V') AND o.is_ms_shipped = 0 "
        "JOIN sys.schemas s ON s.schema_id = o.schema_id "
        "LEFT JOIN sys.default_constraints dc ON dc.object_id = c.default_object_id "
        "LEFT JOIN sys.computed_columns cc ON cc.object_id = c.object_id AND cc.column_id = c.column_id "
        + _DESCRIPTION.format(obj="c", minor="c.column_id")
        + " WHERE s.name = :schema{filter} ORDER BY o.name, c.column_id",
        "o.name",
    ),
    Kind.PRIMARY_KEYS: (_key_constraints_sql("PK"), "t.name"),
    Kind.UNIQUES: (_key_constraints_sql("UQ"), "t.name"),
    Kind.CHECKS: (
        "SELECT t.name, ck.name, ck.definition FROM sys.check_constraints ck "
        "JOIN sys.tables t ON t.object_id = ck.parent_object_id "
        "JOIN sys.schemas s ON s.schema_id = t.schema_id "
        "WHERE s.name = :schema{filter} ORDER BY t.name, ck.name",
        "t.name",
    ),
    Kind.FOREIGN_KEYS: (
        "SELECT t.name, fk.name, pc.name, rs.name, rt.name, rc.name, fk.delete_referential_action_desc, "
        "fk.update_referential_action_desc, fkc.constraint_column_id "
        "FROM sys.foreign_keys fk "
        "JOIN sys.tables t ON t.object_id = fk.parent_object_id "
        "JOIN sys.schemas s ON s.schema_id = t.schema_id "
        "JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id "
        "JOIN sys.columns pc ON pc.object_id = fkc.parent_object_id AND pc.column_id = fkc.parent_column_id "
        "JOIN sys.tables rt ON rt.object_id = fk.referenced_object_id "
        "JOIN sys.schemas rs ON rs.schema_id = rt.schema_id "
        "JOIN sys.columns rc ON rc.object_id = fkc.referenced_object_id AND rc.column_id = fkc.referenced_column_id "
        "WHERE s.name = :schema{filter} ORDER BY t.name, fk.name, fkc.constraint_column_id",
        "t.name",
    ),
    Kind.INDEXES: (
        "SELECT t.name, i.name, i.is_unique, i.is_primary_key, i.type_desc, i.filter_definition, c.name, "
        "ic.key_ordinal "
        "FROM sys.indexes i "
        "JOIN sys.tables t ON t.object_id = i.object_id "
        "JOIN sys.schemas s ON s.schema_id = t.schema_id "
        "JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id "
        "AND ic.is_included_column = 0 "
        "JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id "
        "WHERE s.name = :schema AND i.type > 0 AND i.is_hypothetical = 0{filter} "
        "ORDER BY t.name, i.name, ic.key_ordinal",
        "t.name",
    ),
    Kind.IDENTITY: (
        "SELECT t.name, c.name FROM sys.identity_columns c "
        "JOIN sys.tables t ON t.object_id = c.object_id "
        "JOIN sys.schemas s ON s.schema_id = t.schema_id "
        "WHERE s.name = :schema{filter} ORDER BY t.name, c.column_id",
        "t.name",
    ),
    Kind.ROUTINES: (
        "SELECT o.name, o.type, OBJECT_DEFINITION(o.object_id), TYPE_NAME(r.user_type_id), r.max_length, "
        "r.precision, r.scale, CAST(ep.value AS NVARCHAR(4000)) "
        "FROM sys.objects o "
        "JOIN sys.schemas s ON s.schema_id = o.schema_id "
        "LEFT JOIN sys.parameters r ON r.object_id = o.object_id AND r.parameter_id = 0 "
        + _DESCRIPTION.format(obj="o", minor="0")
        + " WHERE s.name = :schema AND o.type IN ('P', 'PC', 'FN', 'IF', 'TF', 'FS', 'FT') AND o.is_ms_shipped = 0 "
        "ORDER BY o.name",
        None,
    ),
    Kind.ROUTINE_PARAMETERS: (
        "SELECT o.name, p.parameter_id, p.name, p.is_output, TYPE_NAME(p.user_type_id), p.max_length, p.precision, "
        "p.scale "
        "FROM sys.parameters p "
        "JOIN sys.objects o ON o.object_id = p.object_id "
        "JOIN sys.schemas s ON s.schema_id = o.schema_id "
        "WHERE s.name = :schema AND o.type IN ('P', 'PC', 'FN', 'IF', 'TF', 'FS', 'FT') AND p.parameter_id > 0 "
        "ORDER BY o.name, p.parameter_id",
        None,
    ),
    Kind.DATABASE: (
        "SELECT @@VERSION, CAST(COLLATIONPROPERTY(CAST(DATABASEPROPERTYEX(DB_NAME(), 'Collation') AS sysname), "
        "'CodePage') AS NVARCHAR(20)), CAST(DATABASEPROPERTYEX(DB_NAME(), 'Collation') AS NVARCHAR(128))",
        None,
    ),
}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _type(
    type_name: str, max_length: Any, precision: Any, scale: Any
) -> tuple[str, int | None, int | None, int | None]:
    """(tipo declarado, longitud, precisión, escala) a partir de ``sys.columns``/``sys.parameters``."""
    name = type_name.lower()
    if name in _SIZED:
        if max_length is None:
            return type_name, None, None, None
        if int(max_length) == -1:
            return f"{type_name}(max)", None, None, None
        length = int(max_length) // 2 if name in ("nvarchar", "nchar") else int(max_length)
        return f"{type_name}({length})", length, None, None
    if name in _EXACT:
        return f"{type_name}({precision},{scale})", None, int(precision), int(scale)
    if name in _FRACTIONAL and scale is not None:
        return f"{type_name}({scale})", None, None, None
    return type_name, None, None, None


def _grouped(rows: Sequence[Sequence[Any]]) -> dict[tuple[str, str], list[Sequence[Any]]]:
    groups: dict[tuple[str, str], list[Sequence[Any]]] = {}
    for row in rows:
        groups.setdefault((str(row[0]), str(row[1])), []).append(row)
    return groups


def _rule(desc: Any) -> str:
    return str(desc or "NO_ACTION").replace("_", " ")


class SQLServerCatalog:
    """:class:`~util_bbdd.metadata.contracts.CatalogDialect` de SQL Server (2012+)."""

    name = "sqlserver"
    sqlalchemy_names = frozenset({"mssql"})

    def current_schema_sql(self) -> str:
        return "SELECT SCHEMA_NAME()"

    def normalize_name(self, name: str) -> str:
        """SQL Server guarda los nombres tal cual se crearon (la comparación depende de la collation)."""
        return name[1:-1] if len(name) > 1 and name[0] == "[" and name[-1] == "]" else name

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
        out = []
        for r in rows:
            data_type, length, precision, scale = _type(str(r[3]), r[5], r[6], r[7])
            computed = _text(r[13])
            out.append(
                ColumnMeta(
                    table=str(r[0]),
                    name=str(r[1]),
                    ordinal=int(r[2]),
                    data_type=data_type,
                    base_type=str(r[4]),
                    nullable=bool(r[8]),
                    length=length,
                    precision=precision,
                    scale=scale,
                    default=_text(r[9]),
                    comment=_text(r[10]),
                    collation=_text(r[11]),
                    identity="by default" if bool(r[12]) else None,  # IDENTITY admite IDENTITY_INSERT
                    generated=computed,
                )
            )
        return out

    @staticmethod
    def _parse_primary_keys(rows: Sequence[Sequence[Any]], schema: str) -> list[PrimaryKeyMeta]:
        return [PrimaryKeyMeta(t, n, tuple(str(r[2]) for r in g)) for (t, n), g in _grouped(rows).items()]

    @staticmethod
    def _parse_uniques(rows: Sequence[Sequence[Any]], schema: str) -> list[UniqueMeta]:
        return [UniqueMeta(t, n, tuple(str(r[2]) for r in g)) for (t, n), g in _grouped(rows).items()]

    @staticmethod
    def _parse_checks(rows: Sequence[Sequence[Any]], schema: str) -> list[CheckMeta]:
        return [CheckMeta(str(r[0]), str(r[1]), str(r[2])) for r in rows]

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
                on_delete=_rule(g[0][6]),
                on_update=_rule(g[0][7]),
            )
            for (t, n), g in _grouped(rows).items()
        ]

    @staticmethod
    def _parse_indexes(rows: Sequence[Sequence[Any]], schema: str) -> list[IndexMeta]:
        return [
            IndexMeta(
                table=t,
                name=n,
                columns=tuple(str(r[6]) for r in g),
                unique=bool(g[0][2]),
                primary=bool(g[0][3]),
                method=_text(g[0][4]),
                predicate=_text(g[0][5]),
            )
            for (t, n), g in _grouped(rows).items()
        ]

    @staticmethod
    def _parse_identity(rows: Sequence[Sequence[Any]], schema: str) -> list[IdentityMeta]:
        return [IdentityMeta(str(r[0]), str(r[1]), "identity") for r in rows]

    @staticmethod
    def _parse_routines(rows: Sequence[Sequence[Any]], schema: str) -> list[RoutineMeta]:
        out = []
        for r in rows:
            code = str(r[1]).strip()
            return_type = _type(str(r[3]), r[4], r[5], r[6])[0] if r[3] is not None else None
            if code in ("IF", "TF", "FT"):
                return_type = "TABLE"
            out.append(
                RoutineMeta(
                    name=str(r[0]),
                    routine_type=_ROUTINE_TYPES[code],
                    return_type=return_type,
                    definition=_text(r[2]),
                    comment=_text(r[7]),
                    language="CLR" if code in _CLR else "TSQL",
                )
            )
        return out

    @staticmethod
    def _parse_routine_parameters(rows: Sequence[Sequence[Any]], schema: str) -> list[RoutineParameterMeta]:
        return [
            RoutineParameterMeta(
                routine=RoutineKey(str(r[0])),
                ordinal=int(r[1]),
                name=_text(r[2]),
                mode="INOUT" if bool(r[3]) else "IN",  # OUTPUT en T-SQL es de entrada y salida
                data_type=_type(str(r[4]), r[5], r[6], r[7])[0],
            )
            for r in rows
        ]

    @staticmethod
    def _parse_database(rows: Sequence[Sequence[Any]], schema: str) -> list[DatabaseMeta]:
        return [DatabaseMeta(str(r[0]).strip(), _text(r[1]), _text(r[2])) for r in rows]


__all__: list[str] = ["SQLServerCatalog"]
