"""Catálogo de Oracle para ``MetadataSource``: una consulta ``ALL_*`` por owner y tipo de objeto (ADR-003).

Todas las consultas filtran por ``OWNER = :schema`` con bind variables. Con literales (como el registry JSON), cada
tabla era un texto SQL nuevo y Oracle hacía un *hard parse* por consulta: 749 ms por tabla frente a 113 ms con binds
(H-12, sesión 2026-10-03-metadata-centralization). ``USER_*`` no mejora a ``ALL_*`` filtrado (medido) y sirve también
cuando el owner no es el usuario conectado.

Oracle no tiene arrays: constraints e índices devuelven una fila por columna y el parseo las agrupa. Las routines son las
sueltas (``CREATE OR REPLACE`` + su código de ``ALL_SOURCE``, como ``comparar``) y los miembros de package
(``PKG.PROC``, ``overload`` como firma, sin definición propia), igual que la consulta ``obtener_rutinas`` del registry.

Oracle 12c+ usa ``ALL_TAB_IDENTITY_COLS`` (columnas identity). Oracle 11g (11.2) no tiene esa vista ni columnas
identity (se usaban secuencia + trigger): :class:`Oracle11Catalog` lee las columnas sin ella y no tiene
``Kind.IDENTITY``. ``CatalogSource`` elige la variante por la versión del servidor (``for_server_version``).
"""

from __future__ import annotations

import re

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

_NO_ACTION = "NO ACTION"
# Columna de filtro por tabla de las consultas sobre all_constraints (alias con).
_CON_TABLE_NAME = "con.table_name"
_PARAM_MODES = {"IN": "IN", "OUT": "OUT", "IN/OUT": "INOUT"}
_IDENTITY = {"ALWAYS": "always", "BY DEFAULT": "by default"}
_NOT_NULL_CHECK = re.compile(r'^\s*"[^"]+"\s+IS\s+NOT\s+NULL\s*$', re.IGNORECASE)
_TEXT_TYPES = frozenset({"VARCHAR2", "NVARCHAR2", "CHAR", "NCHAR"})
_MODIFIERS = re.compile(r"\(\d+\)")  # TIMESTAMP(6) WITH TIME ZONE → TIMESTAMP WITH TIME ZONE

# kind → (SQL con {filter}, columna por la que se filtra con :tables, o None si no admite filtro)
_SQL: dict[Kind, tuple[str, str | None]] = {
    Kind.TABLES: (
        "SELECT t.table_name, c.comments FROM all_tables t "
        "LEFT JOIN all_tab_comments c ON c.owner = t.owner AND c.table_name = t.table_name "
        "WHERE t.owner = :schema AND t.nested = 'NO' AND t.secondary = 'N' AND t.dropped = 'NO' "
        "AND (t.iot_type IS NULL OR t.iot_type = 'IOT'){filter} ORDER BY t.table_name",
        "t.table_name",
    ),
    Kind.VIEWS: (
        "SELECT v.view_name, v.text, c.comments FROM all_views v "
        "LEFT JOIN all_tab_comments c ON c.owner = v.owner AND c.table_name = v.view_name "
        "WHERE v.owner = :schema{filter} ORDER BY v.view_name",
        "v.view_name",
    ),
    Kind.COLUMNS: (
        "SELECT c.table_name, c.column_name, c.column_id, c.data_type, c.data_length, c.char_length, c.char_used, "
        "c.data_precision, c.data_scale, c.nullable, c.data_default, cc.comments, c.virtual_column, "
        "ic.generation_type "
        "FROM all_tab_cols c "
        "LEFT JOIN all_col_comments cc "
        "ON cc.owner = c.owner AND cc.table_name = c.table_name AND cc.column_name = c.column_name "
        "LEFT JOIN all_tab_identity_cols ic "
        "ON ic.owner = c.owner AND ic.table_name = c.table_name AND ic.column_name = c.column_name "
        "WHERE c.owner = :schema AND c.hidden_column = 'NO' AND c.table_name NOT LIKE 'BIN$%'{filter} "
        "ORDER BY c.table_name, c.column_id",
        "c.table_name",
    ),
    Kind.PRIMARY_KEYS: (
        "SELECT con.table_name, con.constraint_name, cc.column_name, cc.position FROM all_constraints con "
        "JOIN all_cons_columns cc ON cc.owner = con.owner AND cc.constraint_name = con.constraint_name "
        "AND cc.table_name = con.table_name "
        "WHERE con.owner = :schema AND con.constraint_type = 'P' AND con.table_name NOT LIKE 'BIN$%'{filter} "
        "ORDER BY con.table_name, con.constraint_name, cc.position",
        _CON_TABLE_NAME,
    ),
    Kind.UNIQUES: (
        "SELECT con.table_name, con.constraint_name, cc.column_name, cc.position FROM all_constraints con "
        "JOIN all_cons_columns cc ON cc.owner = con.owner AND cc.constraint_name = con.constraint_name "
        "AND cc.table_name = con.table_name "
        "WHERE con.owner = :schema AND con.constraint_type = 'U' AND con.table_name NOT LIKE 'BIN$%'{filter} "
        "ORDER BY con.table_name, con.constraint_name, cc.position",
        _CON_TABLE_NAME,
    ),
    Kind.CHECKS: (
        "SELECT con.table_name, con.constraint_name, con.search_condition, con.generated FROM all_constraints con "
        "WHERE con.owner = :schema AND con.constraint_type = 'C' AND con.table_name NOT LIKE 'BIN$%'{filter} "
        "ORDER BY con.table_name, con.constraint_name",
        _CON_TABLE_NAME,
    ),
    Kind.FOREIGN_KEYS: (
        "SELECT con.table_name, con.constraint_name, cc.column_name, rcon.owner, rcon.table_name, rcc.column_name, "
        "con.delete_rule, cc.position "
        "FROM all_constraints con "
        "JOIN all_cons_columns cc ON cc.owner = con.owner AND cc.constraint_name = con.constraint_name "
        "JOIN all_constraints rcon ON rcon.owner = con.r_owner AND rcon.constraint_name = con.r_constraint_name "
        "JOIN all_cons_columns rcc ON rcc.owner = rcon.owner AND rcc.constraint_name = rcon.constraint_name "
        "AND rcc.position = cc.position "
        "WHERE con.owner = :schema AND con.constraint_type = 'R' AND con.table_name NOT LIKE 'BIN$%'{filter} "
        "ORDER BY con.table_name, con.constraint_name, cc.position",
        _CON_TABLE_NAME,
    ),
    Kind.INDEXES: (
        "SELECT i.table_name, i.index_name, i.uniqueness, i.index_type, ic.column_name, ie.column_expression, "
        "ic.column_position, CASE WHEN pk.constraint_name IS NULL THEN 0 ELSE 1 END "
        "FROM all_indexes i "
        "JOIN all_ind_columns ic ON ic.index_owner = i.owner AND ic.index_name = i.index_name "
        "LEFT JOIN all_ind_expressions ie ON ie.index_owner = ic.index_owner AND ie.index_name = ic.index_name "
        "AND ie.column_position = ic.column_position "
        "LEFT JOIN all_constraints pk ON pk.index_owner = i.owner AND pk.index_name = i.index_name "
        "AND pk.constraint_type = 'P' "
        "WHERE i.table_owner = :schema AND i.index_type <> 'LOB' AND i.table_name NOT LIKE 'BIN$%'{filter} "
        "ORDER BY i.table_name, i.index_name, ic.column_position",
        "i.table_name",
    ),
    Kind.IDENTITY: (
        "SELECT table_name, column_name, generation_type, sequence_name FROM all_tab_identity_cols "
        "WHERE owner = :schema{filter} ORDER BY table_name, column_name",
        "table_name",
    ),
    Kind.ROUTINES: (
        # Sueltas: una fila por línea de código. Miembros de package: una fila sin código.
        "SELECT o.object_name, o.object_type, s.line, s.text, r.data_type, NULL AS overload "
        "FROM all_objects o "
        "LEFT JOIN all_source s ON s.owner = o.owner AND s.name = o.object_name AND s.type = o.object_type "
        "LEFT JOIN all_arguments r ON r.owner = o.owner AND r.object_name = o.object_name "
        "AND r.package_name IS NULL AND r.position = 0 AND r.data_level = 0 "
        "WHERE o.owner = :schema AND o.object_type IN ('PROCEDURE', 'FUNCTION') "
        "UNION ALL "
        "SELECT p.object_name || '.' || p.procedure_name, "
        "CASE WHEN r.position IS NULL THEN 'PROCEDURE' ELSE 'FUNCTION' END, NULL, NULL, r.data_type, p.overload "
        "FROM all_procedures p "
        "LEFT JOIN all_arguments r ON r.owner = p.owner AND r.package_name = p.object_name "
        "AND r.object_name = p.procedure_name AND NVL(r.overload, '0') = NVL(p.overload, '0') "
        "AND r.position = 0 AND r.data_level = 0 "
        "WHERE p.owner = :schema AND p.object_type = 'PACKAGE' AND p.procedure_name IS NOT NULL "
        "UNION ALL "
        # Los packages también, sin código: inventario para migrate (sus miembros no tienen equivalente directo)
        "SELECT o.object_name, 'PACKAGE', NULL, NULL, NULL, NULL FROM all_objects o "
        "WHERE o.owner = :schema AND o.object_type = 'PACKAGE' "
        "ORDER BY 1, 6, 3",
        None,
    ),
    Kind.ROUTINE_PARAMETERS: (
        "SELECT a.object_name, a.package_name, a.overload, a.position, a.argument_name, a.in_out, a.data_type "
        "FROM all_arguments a "
        "WHERE a.owner = :schema AND a.data_level = 0 AND a.position > 0 AND a.argument_name IS NOT NULL "
        "ORDER BY a.package_name NULLS FIRST, a.object_name, a.overload, a.position",
        None,
    ),
    Kind.DATABASE: (
        "SELECT (SELECT banner FROM v$version WHERE ROWNUM = 1), "
        "(SELECT value FROM nls_database_parameters WHERE parameter = 'NLS_CHARACTERSET'), "
        "(SELECT value FROM nls_database_parameters WHERE parameter = 'NLS_SORT') FROM dual",
        None,
    ),
}


# Oracle 11g: sin ALL_TAB_IDENTITY_COLS (columnas sin identity) ni Kind.IDENTITY
_SQL_11G: dict[Kind, tuple[str, str | None]] = {kind: entry for kind, entry in _SQL.items() if kind != Kind.IDENTITY}
_SQL_11G[Kind.COLUMNS] = (
    "SELECT c.table_name, c.column_name, c.column_id, c.data_type, c.data_length, c.char_length, c.char_used, "
    "c.data_precision, c.data_scale, c.nullable, c.data_default, cc.comments, c.virtual_column, "
    "NULL AS generation_type "
    "FROM all_tab_cols c "
    "LEFT JOIN all_col_comments cc "
    "ON cc.owner = c.owner AND cc.table_name = c.table_name AND cc.column_name = c.column_name "
    "WHERE c.owner = :schema AND c.hidden_column = 'NO' AND c.table_name NOT LIKE 'BIN$%'{filter} "
    "ORDER BY c.table_name, c.column_id",
    "c.table_name",
)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: Any) -> int | None:
    return int(value) if value is not None else None


def _data_type(
    data_type: str, data_length: int | None, char_length: int | None, char_used: str | None, precision: int | None,
    scale: int | None,
) -> str:  # fmt: skip
    """Tipo como se declara (``VARCHAR2(30 CHAR)``, ``NUMBER(12,2)``, ``NUMBER``) a partir de ``ALL_TAB_COLS``."""
    if data_type in _TEXT_TYPES and char_length:
        suffix = " CHAR" if char_used == "C" and data_type in ("VARCHAR2", "CHAR") else ""
        return f"{data_type}({char_length}{suffix})"
    if data_type == "NUMBER":
        return _number_type(precision, scale)
    if data_type == "FLOAT" and precision is not None:
        return f"FLOAT({precision})"
    if data_type in ("RAW", "UROWID") and data_length:
        return f"{data_type}({data_length})"
    return data_type


def _number_type(precision: int | None, scale: int | None) -> str:
    """``NUMBER``, ``NUMBER(*,s)``, ``NUMBER(p)`` o ``NUMBER(p,s)``: escala 0 o nula no se escribe tras la precisión."""
    if precision is None:
        return "NUMBER" if scale is None else f"NUMBER(*,{scale})"
    if not scale:
        return f"NUMBER({precision})"
    return f"NUMBER({precision},{scale})"


def _grouped(rows: Sequence[Sequence[Any]]) -> dict[tuple[str, str], list[Sequence[Any]]]:
    """Filas por ``(tabla, constraint/índice)`` conservando el orden (columnas en orden de posición)."""
    groups: dict[tuple[str, str], list[Sequence[Any]]] = {}
    for row in rows:
        groups.setdefault((str(row[0]), str(row[1])), []).append(row)
    return groups


class OracleCatalog:
    """:class:`~util_bbdd.metadata.contracts.VersionedCatalogDialect` de Oracle (12c+; 11g con :class:`Oracle11Catalog`)."""

    name = "oracle"
    sqlalchemy_names = frozenset({"oracle"})
    _sql: dict[Kind, tuple[str, str | None]] = _SQL

    def server_version_sql(self) -> str:
        """Versión de la base de datos (``11.2.0.4.0``, ``19.0.0.0.0``); ``PRODUCT_COMPONENT_VERSION`` es pública.

        ``Oracle%Database%`` y no ``Oracle Database%``: en 23.26 el producto es ``Oracle AI Database 26ai Free``.
        """
        return "SELECT version FROM product_component_version WHERE product LIKE 'Oracle%Database%' AND ROWNUM = 1"

    def for_server_version(self, version: tuple[int, ...]) -> OracleCatalog:
        """:class:`Oracle11Catalog` antes de la 12 (sin ``ALL_TAB_IDENTITY_COLS``); si no, ``self``."""
        return Oracle11Catalog() if version and version < (12,) else self

    def current_schema_sql(self) -> str:
        return "SELECT SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') FROM dual"

    def schema_names_sql(self) -> str:
        """Schemas visibles, una fila por schema con su nombre tal como lo guarda el catálogo (G17, v4.6.0)."""
        return "SELECT username FROM all_users ORDER BY username"

    def normalize_name(self, name: str) -> str:
        """Sin comillas, Oracle guarda los nombres en mayúsculas: ``scott`` → ``SCOTT``; ``"Mixto"`` → ``Mixto``."""
        if len(name) > 1 and name[0] == name[-1] == '"':
            return name[1:-1]
        return name.upper() if name == name.lower() else name

    def query(self, kind: Kind, *, filtered: bool = False) -> CatalogQuery | None:
        entry = self._sql.get(kind)
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
            data_type = str(r[3])
            precision, scale = _int(r[7]), _int(r[8])
            virtual = str(r[12] or "") == "YES"
            default = _text(r[10])
            out.append(
                ColumnMeta(
                    table=str(r[0]),
                    name=str(r[1]),
                    ordinal=int(r[2]),
                    data_type=_data_type(data_type, _int(r[4]), _int(r[5]), _text(r[6]), precision, scale),
                    base_type=_MODIFIERS.sub("", data_type),
                    nullable=str(r[9]) == "Y",
                    length=_int(r[5]) if data_type in _TEXT_TYPES else None,
                    precision=precision if data_type in ("NUMBER", "FLOAT") else None,
                    scale=scale if data_type == "NUMBER" else None,
                    default=None if virtual else default,
                    comment=_text(r[11]),
                    identity=_IDENTITY.get(str(r[13] or "").replace(" ON NULL", "")),
                    generated=default if virtual else None,
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
        """Sin los ``NOT NULL`` que Oracle guarda como CHECK con nombre generado (ya están en ``nullable``)."""
        return [
            CheckMeta(str(r[0]), str(r[1]), str(r[2]).strip())
            for r in rows
            if not (str(r[3]) == "GENERATED NAME" and _NOT_NULL_CHECK.match(str(r[2] or "")))
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
                on_delete=str(g[0][6]) if g[0][6] else _NO_ACTION,
                on_update=_NO_ACTION,  # Oracle no tiene ON UPDATE
            )
            for (t, n), g in _grouped(rows).items()
        ]

    @staticmethod
    def _parse_indexes(rows: Sequence[Sequence[Any]], schema: str) -> list[IndexMeta]:
        return [
            IndexMeta(
                table=t,
                name=n,
                columns=tuple(_text(r[5]) or str(r[4]) for r in g),
                unique=str(g[0][2]) == "UNIQUE",
                primary=bool(int(g[0][7] or 0)),
                method=_text(g[0][3]),
            )
            for (t, n), g in _grouped(rows).items()
        ]

    @staticmethod
    def _parse_identity(rows: Sequence[Sequence[Any]], schema: str) -> list[IdentityMeta]:
        return [IdentityMeta(str(r[0]), str(r[1]), "identity", _text(r[3]), schema) for r in rows]

    @staticmethod
    def _parse_routines(rows: Sequence[Sequence[Any]], schema: str) -> list[RoutineMeta]:
        lines: dict[tuple[str, str, str], list[str]] = {}
        return_types: dict[tuple[str, str, str], Any] = {}  # orden de aparición = orden de las routines
        for r in rows:
            key = (str(r[0]), str(r[1]), str(r[5] or ""))
            return_types.setdefault(key, r[4])
            if r[3] is not None:
                lines.setdefault(key, []).append(str(r[3]))
        out = []
        for (name, kind, overload), return_type in return_types.items():
            code = "".join(lines.get((name, kind, overload), [])).rstrip()
            out.append(
                RoutineMeta(
                    name=name,
                    routine_type=kind,
                    signature=overload,
                    return_type=_text(return_type),
                    definition=f"CREATE OR REPLACE {code}" if code else None,
                    language="PLSQL",
                )
            )
        return out

    @staticmethod
    def _parse_routine_parameters(rows: Sequence[Sequence[Any]], schema: str) -> list[RoutineParameterMeta]:
        return [
            RoutineParameterMeta(
                routine=RoutineKey(f"{r[1]}.{r[0]}" if r[1] else str(r[0]), str(r[2] or "")),
                ordinal=int(r[3]),
                name=_text(r[4]),
                mode=_PARAM_MODES.get(str(r[5] or "IN"), "IN"),
                data_type=str(r[6] or ""),
            )
            for r in rows
        ]

    @staticmethod
    def _parse_database(rows: Sequence[Sequence[Any]], schema: str) -> list[DatabaseMeta]:
        return [DatabaseMeta(str(r[0]), _text(r[1]), _text(r[2])) for r in rows]


class Oracle11Catalog(OracleCatalog):
    """Oracle 11g (11.2): mismas consultas sin ``ALL_TAB_IDENTITY_COLS`` (12c+); ``identity`` de las columnas vacía."""

    _sql = _SQL_11G

    def for_server_version(self, version: tuple[int, ...]) -> OracleCatalog:
        return self if version and version < (12,) else OracleCatalog()


__all__: list[str] = ["Oracle11Catalog", "OracleCatalog"]
