"""Catálogo de MariaDB y MySQL para ``MetadataSource``: ``information_schema`` por schema y tipo de objeto (ADR-003).

Reglas medidas en el baseline de la sesión 2026-10-03-metadata-centralization:

- ``TABLE_SCHEMA`` siempre constante (con un valor constante, el servidor no recorre el directorio de datos);
- **sin joins entre vistas de** ``information_schema``: ``KEY_COLUMN_USAGE`` ⋈ ``REFERENTIAL_CONSTRAINTS`` era
  cuadrático (5000 tablas: MySQL 15,7 s, MariaDB 4,5 s). Las FK y las routines se leen con dos consultas
  (``CatalogQuery.extra``) que se unen aquí.

Las restricciones ``UNIQUE`` salen de ``STATISTICS`` (en MySQL/MariaDB toda restricción única es un índice único).
``ROUTINE_DEFINITION`` es solo el cuerpo: la definición se reconstruye con :func:`build_create_routine` (parámetros,
``RETURNS`` y características, sin ``DEFINER``), como hacía ``migrate`` desde el hotfix R4 de 0.23.1.

MySQL y MariaDB difieren en dos consultas: los índices funcionales (``STATISTICS.EXPRESSION``, solo MySQL 8.0.13+) y
la tabla de las ``CHECK`` (``CHECK_CONSTRAINTS.TABLE_NAME`` solo en MariaDB).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
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

_EXACT = frozenset({"decimal", "numeric"})
#: DATA_TYPE numéricos: sus defaults literales van sin comillas en MySQL y en MariaDB.
_NUMERIC_DATA_TYPES: frozenset[str] = frozenset(
    {
        "TINYINT",
        "SMALLINT",
        "MEDIUMINT",
        "INT",
        "INTEGER",
        "BIGINT",
        "DECIMAL",
        "NUMERIC",
        "FLOAT",
        "DOUBLE",
        "REAL",
        "BIT",
        "BOOLEAN",
        "BOOL",
        "YEAR",
    }
)
_TEXT = frozenset({"char", "varchar", "binary", "varbinary"})


def build_create_routine(
    name: str,
    routine_type: str,
    parameters: Sequence[tuple[Any, Any, Any]],
    definition: str,
    *,
    returns: str = "",
    comment: str = "",
    deterministic: str = "",
    data_access: str = "",
    security: str = "",
) -> str:
    """``CREATE PROCEDURE|FUNCTION`` ejecutable a partir de ``information_schema`` (hotfix R4, 0.23.1).

    ``ROUTINE_DEFINITION`` es solo el cuerpo (``BEGIN ... END``). Se reconstruyen los parámetros, ``RETURNS`` y las
    características (``DETERMINISTIC``, acceso a datos, ``SQL SECURITY``, ``COMMENT``); MySQL exige las dos primeras para
    crear una función con el binlog activo. Sin ``DEFINER``: el del origen puede no existir en el destino.

    Args:
        parameters: ``(PARAMETER_MODE, PARAMETER_NAME, DTD_IDENTIFIER)`` en orden.
    """

    def quoted(identifier: str) -> str:
        return "`" + identifier.replace("`", "``") + "`"

    args = []
    for mode, param_name, data_type in parameters:
        prefix = f"{str(mode).strip().upper()} " if routine_type == "PROCEDURE" and mode else ""
        args.append(f"{prefix}{quoted(str(param_name))} {str(data_type).strip()}")
    lines = [f"CREATE {routine_type} {quoted(name)}({', '.join(args)})"]
    if routine_type == "FUNCTION" and returns:
        lines.append(f"RETURNS {returns}")
    if comment:
        lines.append("COMMENT '" + comment.replace("\\", "\\\\").replace("'", "''") + "'")
    if deterministic.upper() in ("YES", "NO"):
        lines.append("DETERMINISTIC" if deterministic.upper() == "YES" else "NOT DETERMINISTIC")
    if data_access.upper() in ("CONTAINS SQL", "NO SQL", "READS SQL DATA", "MODIFIES SQL DATA"):
        lines.append(data_access.upper())
    if security.upper() in ("DEFINER", "INVOKER"):
        lines.append(f"SQL SECURITY {security.upper()}")
    lines.append(definition)
    return "\n".join(lines)


_PARAMETERS_SQL = (
    "SELECT SPECIFIC_NAME, ROUTINE_TYPE, ORDINAL_POSITION, PARAMETER_NAME, PARAMETER_MODE, DTD_IDENTIFIER "
    "FROM information_schema.PARAMETERS WHERE SPECIFIC_SCHEMA = :schema AND ORDINAL_POSITION > 0 "
    "ORDER BY SPECIFIC_NAME, ROUTINE_TYPE, ORDINAL_POSITION"
)

# kind → (SQL con {filter}, columna por la que se filtra con :tables o None, consultas extra)
_COMMON: dict[Kind, tuple[str, str | None, tuple[str, ...]]] = {
    # MariaDB: las tablas con SYSTEM VERSIONING tienen TABLE_TYPE = 'SYSTEM VERSIONED' (E1)
    Kind.TABLES: (
        "SELECT TABLE_NAME, TABLE_COMMENT, TABLE_COLLATION FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = :schema AND TABLE_TYPE IN ('BASE TABLE', 'SYSTEM VERSIONED'){filter} ORDER BY TABLE_NAME",
        "TABLE_NAME",
        (),
    ),
    Kind.VIEWS: (
        "SELECT TABLE_NAME, VIEW_DEFINITION FROM information_schema.VIEWS "
        "WHERE TABLE_SCHEMA = :schema{filter} ORDER BY TABLE_NAME",
        "TABLE_NAME",
        (),
    ),
    Kind.COLUMNS: (
        "SELECT TABLE_NAME, COLUMN_NAME, ORDINAL_POSITION, COLUMN_TYPE, DATA_TYPE, IS_NULLABLE, "
        "CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE, COLUMN_DEFAULT, COLUMN_COMMENT, "
        "CASE WHEN COLLATION_NAME <> (SELECT DEFAULT_COLLATION_NAME FROM information_schema.SCHEMATA "
        "WHERE SCHEMA_NAME = :schema) THEN COLLATION_NAME END, EXTRA, GENERATION_EXPRESSION "
        "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = :schema{filter} ORDER BY TABLE_NAME, ORDINAL_POSITION",
        "TABLE_NAME",
        (),
    ),
    Kind.PRIMARY_KEYS: (
        "SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, ORDINAL_POSITION FROM information_schema.KEY_COLUMN_USAGE "
        "WHERE TABLE_SCHEMA = :schema AND CONSTRAINT_NAME = 'PRIMARY'{filter} ORDER BY TABLE_NAME, ORDINAL_POSITION",
        "TABLE_NAME",
        (),
    ),
    Kind.UNIQUES: (
        "SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME, SEQ_IN_INDEX FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA = :schema AND NON_UNIQUE = 0 AND INDEX_NAME <> 'PRIMARY'{filter} "
        "ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX",
        "TABLE_NAME",
        (),
    ),
    Kind.FOREIGN_KEYS: (
        "SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE_SCHEMA, REFERENCED_TABLE_NAME, "
        "REFERENCED_COLUMN_NAME, ORDINAL_POSITION FROM information_schema.KEY_COLUMN_USAGE "
        "WHERE TABLE_SCHEMA = :schema AND REFERENCED_TABLE_NAME IS NOT NULL{filter} "
        "ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION",
        "TABLE_NAME",
        (
            "SELECT TABLE_NAME, CONSTRAINT_NAME, DELETE_RULE, UPDATE_RULE FROM information_schema.REFERENTIAL_CONSTRAINTS "
            "WHERE CONSTRAINT_SCHEMA = :schema{filter}",
        ),
    ),
    Kind.IDENTITY: (
        "SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = :schema AND EXTRA LIKE '%auto_increment%'{filter} ORDER BY TABLE_NAME, COLUMN_NAME",
        "TABLE_NAME",
        (),
    ),
    Kind.ROUTINES: (
        "SELECT ROUTINE_NAME, ROUTINE_TYPE, ROUTINE_DEFINITION, DTD_IDENTIFIER, ROUTINE_COMMENT, IS_DETERMINISTIC, "
        "SQL_DATA_ACCESS, SECURITY_TYPE FROM information_schema.ROUTINES "
        "WHERE ROUTINE_SCHEMA = :schema ORDER BY ROUTINE_NAME, ROUTINE_TYPE",
        None,
        (_PARAMETERS_SQL,),
    ),
    Kind.ROUTINE_PARAMETERS: (_PARAMETERS_SQL, None, ()),
    Kind.DATABASE: (
        "SELECT VERSION(), DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME FROM information_schema.SCHEMATA "
        "WHERE SCHEMA_NAME = :schema",
        None,
        (),
    ),
}

_MARIADB: dict[Kind, tuple[str, str | None, tuple[str, ...]]] = {
    Kind.CHECKS: (
        "SELECT TABLE_NAME, CONSTRAINT_NAME, CHECK_CLAUSE FROM information_schema.CHECK_CONSTRAINTS "
        "WHERE CONSTRAINT_SCHEMA = :schema{filter} ORDER BY TABLE_NAME, CONSTRAINT_NAME",
        "TABLE_NAME",
        (),
    ),
    Kind.INDEXES: (
        "SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, INDEX_TYPE, COLUMN_NAME, NULL, SEQ_IN_INDEX "
        "FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = :schema{filter} "
        "ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX",
        "TABLE_NAME",
        (),
    ),
}

_MYSQL: dict[Kind, tuple[str, str | None, tuple[str, ...]]] = {
    # MySQL no guarda la tabla en CHECK_CONSTRAINTS: TABLE_CONSTRAINTS por separado (sin join entre vistas)
    Kind.CHECKS: (
        "SELECT CONSTRAINT_NAME, CHECK_CLAUSE FROM information_schema.CHECK_CONSTRAINTS "
        "WHERE CONSTRAINT_SCHEMA = :schema ORDER BY CONSTRAINT_NAME",
        None,
        (
            "SELECT TABLE_NAME, CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS "
            "WHERE CONSTRAINT_SCHEMA = :schema AND CONSTRAINT_TYPE = 'CHECK'",
        ),
    ),
    Kind.INDEXES: (
        "SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE, INDEX_TYPE, COLUMN_NAME, EXPRESSION, SEQ_IN_INDEX "
        "FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = :schema{filter} "
        "ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX",
        "TABLE_NAME",
        (),
    ),
}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    text = str(value).strip()
    return text or None


def _grouped(rows: Sequence[Sequence[Any]]) -> dict[tuple[str, str], list[Sequence[Any]]]:
    groups: dict[tuple[str, str], list[Sequence[Any]]] = {}
    for row in rows:
        groups.setdefault((str(row[0]), str(row[1])), []).append(row)
    return groups


def _default(value: Any) -> str | None:
    """MariaDB devuelve ``'NULL'`` (texto) para «sin valor por defecto»; MySQL devuelve ``NULL``."""
    text = _text(value)
    return None if text is None or text == "NULL" else text


def quote_literal_default(default: str | None, data_type: str, extra: str) -> str | None:
    """Entrecomilla un default literal de MySQL (convenio de MariaDB y del resto de motores: ``'x'``).

    MySQL devuelve ``COLUMN_DEFAULT`` sin comillas (``x``) y MariaDB con ellas (``'x'``); las expresiones (``EXTRA``
    contiene ``DEFAULT_GENERATED``) y los defaults de columnas numéricas se dejan tal cual.

    Args:
        default: ``COLUMN_DEFAULT`` tal cual lo devuelve MySQL.
        data_type: ``DATA_TYPE`` de la columna.
        extra: ``EXTRA`` de la columna.

    Returns:
        El default entrecomillado si es un literal de una columna no numérica; si no, sin cambios.
    """
    if default is None or "DEFAULT_GENERATED" in extra.upper():
        return default
    if data_type.strip().upper() in _NUMERIC_DATA_TYPES:
        return default
    if len(default) >= 2 and default.startswith("'") and default.endswith("'"):
        return default
    return "'" + default.replace("'", "''") + "'"


class MariaDBCatalog:
    """:class:`~util_bbdd.metadata.contracts.CatalogDialect` de MariaDB (10.2+)."""

    name = "mariadb"
    sqlalchemy_names = frozenset({"mariadb"})
    _specific = _MARIADB

    def current_schema_sql(self) -> str:
        return "SELECT DATABASE()"

    def normalize_name(self, name: str) -> str:
        """Nombre tal cual (la sensibilidad a mayúsculas depende de ``lower_case_table_names``); sin backticks."""
        return name[1:-1] if len(name) > 1 and name[0] == name[-1] == "`" else name

    def query(self, kind: Kind, *, filtered: bool = False) -> CatalogQuery | None:
        entry = self._specific.get(kind) or _COMMON.get(kind)
        if entry is None:
            return None
        sql, column, extra = entry
        fragment = f" AND {column} IN (:tables)" if filtered and column else ""
        return CatalogQuery(
            sql.replace("{filter}", fragment),
            filterable=column is not None,
            extra=tuple(e.replace("{filter}", fragment) for e in extra),
        )

    def parse(self, kind: Kind, rows: Sequence[Any], schema: str) -> tuple[Any, ...]:
        return tuple(getattr(self, f"_parse_{kind.value}")(rows, schema))

    # ── parseo por tipo ──────────────────────────────────────────────────────
    @staticmethod
    def _parse_tables(rows: Sequence[Sequence[Any]], schema: str) -> list[TableMeta]:
        return [TableMeta(str(r[0]), _text(r[1]), _text(r[2]) if len(r) > 2 else None) for r in rows]

    @staticmethod
    def _parse_views(rows: Sequence[Sequence[Any]], schema: str) -> list[ViewMeta]:
        return [ViewMeta(str(r[0]), _text(r[1])) for r in rows]

    @staticmethod
    def _parse_columns(rows: Sequence[Sequence[Any]], schema: str) -> list[ColumnMeta]:
        out = []
        for r in rows:
            base = str(r[4]).lower()
            extra = str(r[12] or "").lower()
            generated = _text(r[13]) if "generated" in extra else None
            out.append(
                ColumnMeta(
                    table=str(r[0]),
                    name=str(r[1]),
                    ordinal=int(r[2]),
                    data_type=str(_text(r[3])),
                    base_type=base,
                    nullable=str(r[5]).upper() == "YES",
                    length=int(r[6]) if r[6] is not None and (base in _TEXT or "text" in base) else None,
                    precision=int(r[7]) if r[7] is not None and base in _EXACT else None,
                    scale=int(r[8]) if r[8] is not None and base in _EXACT else None,
                    default=None if generated else _default(r[9]),
                    comment=_text(r[10]),
                    collation=_text(r[11]),
                    identity="by default" if "auto_increment" in extra else None,
                    generated=generated,
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
        return [CheckMeta(str(r[0]), str(r[1]), str(_text(r[2]))) for r in rows]

    @staticmethod
    def _parse_foreign_keys(results: Sequence[Any], schema: str) -> list[ForeignKeyMeta]:
        columns, rules = results
        by_name = {(str(r[0]), str(r[1])): (r[2], r[3]) for r in rules}
        out = []
        for (table, name), group in _grouped(columns).items():
            delete_rule, update_rule = by_name.get((table, name), (None, None))
            out.append(
                ForeignKeyMeta(
                    table=table,
                    name=name,
                    columns=tuple(str(r[2]) for r in group),
                    ref_schema=str(group[0][3]),
                    ref_table=str(group[0][4]),
                    ref_columns=tuple(str(r[5]) for r in group),
                    on_delete=_text(delete_rule) or "NO ACTION",
                    on_update=_text(update_rule) or "NO ACTION",
                )
            )
        return out

    @staticmethod
    def _parse_indexes(rows: Sequence[Sequence[Any]], schema: str) -> list[IndexMeta]:
        return [
            IndexMeta(
                table=t,
                name=n,
                columns=tuple(_text(r[5]) or str(r[4]) for r in g),
                unique=int(g[0][2]) == 0,
                primary=n == "PRIMARY",
                method=_text(g[0][3]),
            )
            for (t, n), g in _grouped(rows).items()
        ]

    @staticmethod
    def _parse_identity(rows: Sequence[Sequence[Any]], schema: str) -> list[IdentityMeta]:
        return [IdentityMeta(str(r[0]), str(r[1]), "identity") for r in rows]

    @staticmethod
    def _parse_routines(results: Sequence[Any], schema: str) -> list[RoutineMeta]:
        routines, parameters = results
        params: dict[tuple[str, str], list[tuple[Any, Any, Any]]] = {}
        for p in parameters:
            params.setdefault((str(p[0]), str(p[1]).upper()), []).append((p[4], p[3], p[5]))
        out = []
        for r in routines:
            name, routine_type = str(r[0]), str(r[1]).upper()
            body = _text(r[2])
            returns = _text(r[3]) if routine_type == "FUNCTION" else None
            definition = (
                build_create_routine(
                    name,
                    routine_type,
                    params.get((name, routine_type), []),
                    body,
                    returns=returns or "",
                    comment=_text(r[4]) or "",
                    deterministic=_text(r[5]) or "",
                    data_access=_text(r[6]) or "",
                    security=_text(r[7]) or "",
                )
                if body
                else None
            )
            out.append(
                RoutineMeta(
                    name=name,
                    routine_type=routine_type,
                    return_type=returns,
                    definition=definition,
                    comment=_text(r[4]),
                    language="SQL",
                )
            )
        return out

    @staticmethod
    def _parse_routine_parameters(rows: Sequence[Sequence[Any]], schema: str) -> list[RoutineParameterMeta]:
        return [
            RoutineParameterMeta(
                routine=RoutineKey(str(r[0])),
                ordinal=int(r[2]),
                name=_text(r[3]),
                mode=(_text(r[4]) or "IN").upper(),
                data_type=str(_text(r[5])),
            )
            for r in rows
        ]

    @staticmethod
    def _parse_database(rows: Sequence[Sequence[Any]], schema: str) -> list[DatabaseMeta]:
        return [DatabaseMeta(str(r[0]), _text(r[1]), _text(r[2])) for r in rows]


class MySQLCatalog(MariaDBCatalog):
    """:class:`~util_bbdd.metadata.contracts.CatalogDialect` de MySQL (8.0.16+: ``CHECK_CONSTRAINTS``)."""

    name = "mysql"
    sqlalchemy_names = frozenset({"mysql"})
    _specific = _MYSQL

    @staticmethod
    def _parse_columns(rows: Sequence[Sequence[Any]], schema: str) -> list[ColumnMeta]:
        """Como MariaDB, pero con los defaults literales entre comillas (MySQL los devuelve sin ellas)."""
        return [
            replace(column, default=quote_literal_default(column.default, column.base_type, str(row[12] or "")))
            for column, row in zip(MariaDBCatalog._parse_columns(rows, schema), rows, strict=True)
        ]

    @staticmethod
    def _parse_checks(results: Sequence[Any], schema: str) -> list[CheckMeta]:
        checks, tables = results
        table_of = {str(r[1]): str(r[0]) for r in tables}
        return [CheckMeta(table_of[str(r[0])], str(r[0]), str(_text(r[1]))) for r in checks if str(r[0]) in table_of]


__all__: list[str] = ["MariaDBCatalog", "MySQLCatalog", "build_create_routine", "quote_literal_default"]
