"""Hechos puntuales del catálogo y del servidor que necesita ``bulk`` antes de una operación (grupo C5 de ADR-003).

No son metadatos de un schema (eso es :class:`~util_bbdd.metadata.CatalogSource`): son preguntas sobre una tabla o
sobre la sesión —la secuencia de una columna ``serial``, el tipo de una identity de Oracle, el motor de almacenamiento
de MySQL/MariaDB, si una tabla de SQL Server tiene índice clustered, el nivel de compatibilidad, si el usuario puede
crear tablas temporales o desactivar triggers— que se hacen una vez por operación sobre la conexión del llamador
(en su transacción). Aquí vive su SQL para que los consumidores no importen ``metadata.<motor>``.

Todas reciben una ``Connection`` de SQLAlchemy y devuelven ``None``/``False`` cuando el dato no existe.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import text

from .mariadb.tables import (
    fetch_nonunique_index_columns_sql,
    fetch_table_fk_columns_sql,
    fetch_table_storage_engine_sql,
    fetch_unique_index_columns_sql,
)
from .oracle.indexes import (
    fetch_inbound_foreign_keys_sql as _oracle_inbound_fks_sql,
    fetch_secondary_nonunique_indexes_sql as _oracle_secondary_indexes_sql,
    fetch_unique_constraint_columns_sql as _oracle_unique_constraints_sql,
)
from .oracle.tables import fetch_identity_generation_sql
from .postgresql.tables import (
    fetch_can_create_temp_tables_sql,
    fetch_can_disable_triggers_sql,
    fetch_fk_definition_sql,
    fetch_inbound_foreign_keys_sql as _pg_inbound_fks_sql,
    fetch_secondary_nonunique_indexes_sql as _pg_secondary_indexes_sql,
    fetch_unique_indexes_sql as _pg_unique_indexes_sql,
)
from .sqlserver.common import fetch_compatibility_level_sql
from .sqlserver.indexes import (
    fetch_clustered_index_count_sql,
    fetch_inbound_foreign_keys_sql as _mssql_inbound_fks_sql,
    fetch_secondary_nonunique_indexes_sql as _mssql_secondary_indexes_sql,
    fetch_unique_nonclustered_index_columns_sql as _mssql_unique_indexes_sql,
)


def serial_sequence(conn: Any, table_ref: str, column: str) -> str | None:
    """PostgreSQL: secuencia vinculada a una columna ``serial``/identity (``pg_get_serial_sequence``) o ``None``.

    Args:
        table_ref: Tabla citada como identificador SQL (``"Esquema"."Tabla"``): la función la analiza como tal.
    """
    value = conn.execute(text("SELECT pg_get_serial_sequence(:tbl, :col)"), {"tbl": table_ref, "col": column}).scalar()
    return None if value is None else str(value)


def identity_generation(conn: Any, table: str, column: str, owner: str | None = None) -> tuple[Any, Any] | None:
    """Oracle: ``(generation_type, default_on_null)`` de una columna identity, o ``None`` si no lo es.

    Args:
        table: Nombre de la tabla como en el catálogo (mayúsculas si no se creó entre comillas).
        column: Nombre de la columna, ídem.
        owner: Owner como en el catálogo; ``None`` = el del usuario de la sesión (vistas ``USER_*``).
    """
    params = {"tbl": table, "col": column}
    if owner:
        params["owner"] = owner
    row = conn.execute(text(fetch_identity_generation_sql(with_owner=bool(owner))), params).fetchone()
    return None if row is None else (row[0], row[1])


def storage_engine(conn: Any, schema: str | None, table: str) -> str | None:
    """MySQL/MariaDB: motor de almacenamiento de una tabla (``InnoDB``, ``MyISAM``, ``Aria``…); ``schema=None`` = el actual."""
    value = conn.execute(text(fetch_table_storage_engine_sql()), {"schema": schema, "tbl": table}).scalar()
    return None if value is None else str(value)


def clustered_index_count(conn: Any, table: str) -> int:
    """SQL Server: índices clustered de una tabla (0 = heap). ``table`` como lo admite ``OBJECT_ID`` (con esquema)."""
    return int(conn.execute(text(fetch_clustered_index_count_sql()), {"tbl": table}).scalar() or 0)


def compatibility_level(conn: Any) -> Any:
    """SQL Server: nivel de compatibilidad de la base de datos actual (p. ej. ``160``)."""
    return conn.execute(text(fetch_compatibility_level_sql())).scalar()


def can_create_temp_tables(conn: Any) -> bool:
    """PostgreSQL: si el usuario puede crear tablas temporales en la base de datos actual (privilegio ``TEMP``)."""
    return bool(conn.execute(text(fetch_can_create_temp_tables_sql())).scalar())


def can_disable_triggers(conn: Any, schema: str | None, table: str) -> bool:
    """PostgreSQL: si el usuario puede ``ALTER TABLE … DISABLE TRIGGER ALL`` (superusuario o propietario)."""
    return bool(conn.execute(text(fetch_can_disable_triggers_sql()), {"schema": schema, "tbl": table}).scalar())


def secondary_nonunique_indexes(
    conn: Any, schema: str | None, table: str, dialect: str | None = None
) -> list[tuple[str, str | None]]:
    """Índices secundarios no únicos de una tabla que ``bulk`` y ``dump`` pueden desactivar: ``[(nombre, DDL o None)]``.

    - SQL Server: ``NONCLUSTERED`` no únicos, sin PK ni constraint y habilitados (DDL ``None``).
    - Oracle: ``NORMAL`` no únicos que no respaldan una constraint (DDL ``None``).
    - PostgreSQL: no únicos, sin PK ni constraint, con su ``pg_get_indexdef`` para recrearlos.
    - MariaDB/MySQL: BTREE no únicos de columnas completas en orden ascendente, visibles y sin comentario (sin
      prefijos ni expresiones), que no empiezan por las columnas de una FK de la tabla ni por las que referencia una FK
      de otra (InnoDB los necesita). DDL: la cláusula para ``ALTER TABLE … ADD`` (``INDEX `n` (`a`, `b`)``).
    - Resto: ``[]``.

    ``dialect`` (nombre de SQLAlchemy) evita leerlo de la conexión.
    """
    dialect = dialect or conn.dialect.name
    if dialect == "mssql":
        rows = conn.execute(text(_mssql_secondary_indexes_sql()), {"tbl": table, "schema": schema}).fetchall()
        return [(str(r[0]), None) for r in rows]
    if dialect == "oracle":
        params = {"tbl": table, "owner": schema} if schema else {"tbl": table}
        rows = conn.execute(text(_oracle_secondary_indexes_sql(with_owner=bool(schema))), params).fetchall()
        return [(str(r[0]), None) for r in rows]
    if dialect == "postgresql":
        rows = conn.execute(text(_pg_secondary_indexes_sql()), {"tbl": table, "schema": schema}).fetchall()
        return [(str(r[0]), str(r[1])) for r in rows]
    if dialect in ("mysql", "mariadb"):
        return _mysql_secondary_indexes(conn, schema, table)
    return []


def _mysql_secondary_indexes(conn: Any, schema: str | None, table: str) -> list[tuple[str, str | None]]:
    """MariaDB/MySQL: ver :func:`secondary_nonunique_indexes`."""
    prep = conn.dialect.identifier_preparer
    return [
        (name, f"INDEX {prep.quote(name)} ({', '.join(prep.quote(c) for c in cols)})")
        for name, cols in _mysql_simple_indexes(conn, schema, table, fetch_nonunique_index_columns_sql())
    ]


def _mysql_simple_indexes(conn: Any, schema: str | None, table: str, sql: str) -> list[tuple[str, list[str]]]:
    """Índices de ``sql`` (STATISTICS) BTREE de columnas completas, ascendentes, visibles y sin comentario, que no
    empiezan por las columnas de una FK de la tabla ni por las que referencia una FK: ``[(nombre, columnas)]``."""
    params = {"schema": schema, "tbl": table}
    columns: dict[str, list[str]] = {}
    rejected: set[str] = set()
    for row in conn.execute(text(sql), params):
        info = {str(key).upper(): value for key, value in row._mapping.items()}
        name = str(info["INDEX_NAME"])
        simple = (
            info.get("COLUMN_NAME") is not None  # MySQL 8: NULL en los índices funcionales
            and info.get("SUB_PART") is None
            and info.get("EXPRESSION") is None
            and str(info.get("INDEX_TYPE") or "").upper() == "BTREE"
            and str(info.get("COLLATION") or "A").upper() == "A"
            and str(info.get("IS_VISIBLE") or "YES").upper() == "YES"
            and str(info.get("IGNORED") or "NO").upper() == "NO"
            and not str(info.get("INDEX_COMMENT") or "")
        )
        if not simple:
            rejected.add(name)
        columns.setdefault(name, []).append(str(info.get("COLUMN_NAME")))
    fk_prefixes = _mysql_fk_column_lists(conn, params, table)
    out: list[tuple[str, list[str]]] = []
    for name, cols in columns.items():
        lowered = [c.lower() for c in cols]
        if name in rejected or any(lowered[: len(fk)] == fk for fk in fk_prefixes):
            continue
        out.append((name, cols))
    return out


@dataclass(frozen=True)
class UniqueIndexFact:
    """Índice único o PK/UNIQUE de una tabla que ``disable_indexes="all"`` puede desactivar (v3.3.0).

    Attributes:
        name: Índice (SQL Server, PostgreSQL, MariaDB/MySQL) o constraint (Oracle).
        kind: ``"pk"``, ``"unique_constraint"`` o ``"unique_index"`` (sin constraint).
        columns: Columnas de la clave, en orden (sin citar).
        ddl: PostgreSQL: ``pg_get_constraintdef`` (PK/UNIQUE) o ``pg_get_indexdef``; MariaDB/MySQL: cláusula ``ADD``.
        constraint: PostgreSQL: nombre de la constraint que respalda el índice.
    """

    name: str
    kind: Literal["pk", "unique_constraint", "unique_index"]
    columns: tuple[str, ...]
    ddl: str | None = None
    constraint: str | None = None


@dataclass(frozen=True)
class InboundForeignKeyFact:
    """FK de otra tabla (o de la misma) que referencia una PK/UNIQUE/índice único de la tabla (v3.3.0).

    Attributes:
        referenced: Índice (SQL Server) o constraint (Oracle) referenciado; PostgreSQL: ``""`` (se tratan todas).
        schema: Esquema u owner de la tabla hija.
        table: Tabla hija.
        name: Nombre de la FK.
        enabled: Si está activa (SQL Server); Oracle y PostgreSQL solo devuelven las activas.
        validated: Si sus filas están validadas (``is_not_trusted = 0``, ``VALIDATED``, ``convalidated``).
        ddl: PostgreSQL: ``pg_get_constraintdef`` para recrearla.
    """

    referenced: str
    schema: str | None
    table: str
    name: str
    enabled: bool = True
    validated: bool = True
    ddl: str | None = None


def unique_indexes(conn: Any, schema: str | None, table: str, dialect: str | None = None) -> list[UniqueIndexFact]:
    """Índices únicos y PK/UNIQUE de una tabla que ``disable_indexes="all"`` puede desactivar (v3.3.0).

    - SQL Server: NONCLUSTERED únicos habilitados (PK, UNIQUE o unique index); nunca el clustered.
    - Oracle: PK y UNIQUE ``ENABLED`` (sin la PK de una IOT).
    - PostgreSQL: índices únicos válidos, con su constraint PK/UNIQUE si la respaldan.
    - MariaDB/MySQL: índices únicos (sin la PK, que en InnoDB es el clustered) con las reglas de
      :func:`secondary_nonunique_indexes`, sin los que usa o referencia una FK.
    - Resto: ``[]``.
    """
    dialect = dialect or conn.dialect.name
    reader = _UNIQUE_INDEX_READERS.get("mysql" if dialect == "mariadb" else dialect)
    return [] if reader is None else reader(conn, schema, table)


_UniqueKind = Literal["pk", "unique_constraint", "unique_index"]


def _grouped_facts(rows: Any) -> list[UniqueIndexFact]:
    """``[(nombre, tipo, columna), …]`` ordenadas por nombre → un :class:`UniqueIndexFact` por nombre."""
    grouped: dict[str, tuple[_UniqueKind, list[str]]] = {}
    for name, kind, column in rows:
        grouped.setdefault(str(name), (kind, []))[1].append(str(column))
    return [UniqueIndexFact(name, kind, tuple(cols)) for name, (kind, cols) in grouped.items()]


def _mssql_unique_indexes(conn: Any, schema: str | None, table: str) -> list[UniqueIndexFact]:
    def kind(is_pk: Any, is_uq: Any) -> _UniqueKind:
        if is_pk:
            return "pk"
        return "unique_constraint" if is_uq else "unique_index"

    rows = conn.execute(text(_mssql_unique_indexes_sql()), {"tbl": table, "schema": schema})
    return _grouped_facts((name, kind(is_pk, is_uq), column) for name, is_pk, is_uq, column in rows)


def _oracle_unique_indexes(conn: Any, schema: str | None, table: str) -> list[UniqueIndexFact]:
    rows = conn.execute(text(_oracle_unique_constraints_sql()), {"tbl": table, "owner": schema})
    return _grouped_facts((name, "pk" if ctype == "P" else "unique_constraint", column) for name, ctype, column in rows)


def _pg_unique_indexes(conn: Any, schema: str | None, table: str) -> list[UniqueIndexFact]:
    out: list[UniqueIndexFact] = []
    rows = conn.execute(text(_pg_unique_indexes_sql()), {"tbl": table, "schema": schema})
    for index, constraint, contype, indexdef, constraintdef, columns in rows:
        if constraint is None:
            out.append(UniqueIndexFact(str(index), "unique_index", tuple(columns or ()), str(indexdef)))
            continue
        kind: _UniqueKind = "pk" if contype == "p" else "unique_constraint"
        out.append(UniqueIndexFact(str(index), kind, tuple(columns or ()), str(constraintdef), str(constraint)))
    return out


def _mysql_unique_indexes(conn: Any, schema: str | None, table: str) -> list[UniqueIndexFact]:
    prep = conn.dialect.identifier_preparer
    return [
        UniqueIndexFact(
            name,
            "unique_index",
            tuple(cols),
            f"UNIQUE INDEX {prep.quote(name)} ({', '.join(prep.quote(c) for c in cols)})",
        )
        for name, cols in _mysql_simple_indexes(conn, schema, table, fetch_unique_index_columns_sql())
    ]


_UNIQUE_INDEX_READERS: dict[str, Any] = {
    "mssql": _mssql_unique_indexes,
    "oracle": _oracle_unique_indexes,
    "postgresql": _pg_unique_indexes,
    "mysql": _mysql_unique_indexes,
}


def inbound_foreign_keys(
    conn: Any, schema: str | None, table: str, dialect: str | None = None
) -> list[InboundForeignKeyFact]:
    """FK que referencian la tabla y que ``disable_indexes="all"`` tiene que reactivar o recrear (v3.3.0).

    SQL Server (todas, con su estado), Oracle (las activas) y PostgreSQL (todas, con su DDL); resto ``[]`` (en
    MariaDB/MySQL los índices referenciados no se tocan).
    """
    dialect = dialect or conn.dialect.name
    if dialect == "mssql":
        return [
            InboundForeignKeyFact(str(index), str(s), str(t), str(name), not bool(disabled), not bool(untrusted))
            for index, s, t, name, disabled, untrusted in conn.execute(
                text(_mssql_inbound_fks_sql()), {"tbl": table, "schema": schema}
            )
        ]
    if dialect == "oracle":
        return [
            InboundForeignKeyFact(str(ref), str(owner), str(t), str(name), True, str(validated).upper() == "VALIDATED")
            for ref, owner, t, name, validated in conn.execute(
                text(_oracle_inbound_fks_sql()), {"tbl": table, "owner": schema}
            )
        ]
    if dialect == "postgresql":
        return [
            InboundForeignKeyFact("", str(s), str(t), str(name), True, bool(validated), str(ddl))
            for name, s, t, ddl, validated in conn.execute(
                text(_pg_inbound_fks_sql()), {"tbl": table, "schema": schema}
            )
        ]
    return []


def _mysql_fk_column_lists(conn: Any, params: dict[str, Any], table: str) -> list[list[str]]:
    """Columnas (en minúsculas y en orden) de cada FK de la tabla y de cada FK de otra tabla que la referencia."""
    child: dict[tuple[str, str, str], list[str]] = {}
    parent: dict[tuple[str, str, str], list[tuple[int, str]]] = {}
    for row in conn.execute(text(fetch_table_fk_columns_sql()), params):
        key = (str(row[0]), str(row[1]), str(row[2]))
        if str(row[1]).lower() == table.lower():
            child.setdefault(key, []).append(str(row[3]).lower())
        if str(row[5]).lower() == table.lower():
            parent.setdefault(key, []).append((int(row[8] or row[7] or 0), str(row[6]).lower()))
    return list(child.values()) + [[col for _, col in sorted(cols)] for cols in parent.values()]


def foreign_key_definition(conn: Any, table_ref: str, name: str) -> Any:
    """PostgreSQL: ``(tabla referenciada, [columnas], [columnas referenciadas])`` de una FK, citados; o ``None``.

    Args:
        table_ref: Tabla citada (convertible a ``regclass``).
    """
    return conn.execute(text(fetch_fk_definition_sql()), {"tbl": table_ref, "name": name}).first()


__all__: list[str] = [
    "can_create_temp_tables",
    "can_disable_triggers",
    "clustered_index_count",
    "compatibility_level",
    "foreign_key_definition",
    "identity_generation",
    "InboundForeignKeyFact",
    "inbound_foreign_keys",
    "secondary_nonunique_indexes",
    "serial_sequence",
    "storage_engine",
    "UniqueIndexFact",
    "unique_indexes",
]
