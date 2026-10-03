"""Integración de la precarga de metadatos de ``SchemaComparator`` (``comparar/_prefetch.py``) contra motores reales.

Paridad: lo precargado (``Inspector.get_multi_*`` y, en SQL Server, las FKs por schema de
``metadata.sqlserver.constraints``) es lo mismo que dan ``get_columns``/``get_pk_constraint``/``get_indexes``/
``get_foreign_keys``/``get_table_comment`` tabla a tabla, y la precarga cubre todas las tablas (ninguna vuelve a la
consulta tabla a tabla). Cada motor con ``UTIL_BBDD_TEST_<MOTOR>_URL``; las tablas se crean en el esquema por defecto
del usuario de pruebas con nombres únicos y se eliminan al terminar.
"""

from __future__ import annotations

import os
import uuid

from typing import Any
from unittest.mock import patch

import pytest

from sqlalchemy import (
    Column,
    Engine,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Inspector,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    event,
    inspect,
)

from util_bbdd.metadata.reflection import prefetch_table_metadata

pytestmark = [pytest.mark.integration, pytest.mark.cross_db]

SERVERS: tuple[str, ...] = ("postgresql", "mysql", "mariadb", "mssql", "oracle")
KINDS = ("columns", "pk", "indexes", "fks", "comments")


def _url_env(key: str) -> str:
    return f"UTIL_BBDD_TEST_{key.upper()}_URL"


def _params() -> list[Any]:
    return [
        pytest.param(
            key,
            id=key,
            marks=pytest.mark.skipif(not os.environ.get(_url_env(key)), reason=f"{_url_env(key)} no definida"),
        )
        for key in SERVERS
    ]


def _tables(prefix: str) -> MetaData:
    md = MetaData()
    Table(
        f"{prefix}_p",
        md,
        Column("id", Integer, primary_key=True, autoincrement=False),
        Column("a", Integer, nullable=False),
        Column("b", String(20), nullable=False, comment="columna b"),
        UniqueConstraint("a", "b", name=f"{prefix}_uq_ab"),
        comment="tabla padre",
    )
    Table(
        f"{prefix}_c",
        md,
        Column("id", Integer, primary_key=True, autoincrement=False),
        Column("p_id", Integer, ForeignKey(f"{prefix}_p.id", name=f"{prefix}_fk_p", ondelete="CASCADE")),
        Column("a", Integer),
        Column("b", String(20)),
        Column("self_id", Integer, ForeignKey(f"{prefix}_c.id", name=f"{prefix}_fk_self")),
        ForeignKeyConstraint(["a", "b"], [f"{prefix}_p.a", f"{prefix}_p.b"], name=f"{prefix}_fk_ab"),
        Index(f"{prefix}_ix_ba", "b", "a"),
    )
    Table(f"{prefix}_e", md, Column("id", Integer, primary_key=True, autoincrement=False))  # sin FKs ni índices
    return md


def _full_column(column: Any) -> dict[str, Any]:
    """Columna reflejada con el tipo como ``repr`` (longitud, precisión, collation…) para compararla entera."""
    return {**column, "type": repr(column["type"])}


def _normalize(kind: str, value: Any) -> Any:
    """Lo que usa el comparador de cada metadato, en un orden estable."""
    if kind == "columns":
        return [(c["name"], str(c["type"]), c.get("nullable"), c.get("default"), c.get("comment")) for c in value]
    if kind == "pk":
        return (value or {}).get("constrained_columns")
    if kind == "indexes":
        return sorted((i["name"], list(i.get("column_names") or []), bool(i.get("unique"))) for i in value)
    if kind == "fks":
        return sorted(
            (
                fk.get("name") or "",
                list(fk["constrained_columns"]),
                fk["referred_table"],
                list(fk["referred_columns"]),
            )
            for fk in value
        )
    return value


@pytest.fixture
def engine_and_tables(request: pytest.FixtureRequest) -> Any:
    key: str = request.param
    engine: Engine = create_engine(os.environ[_url_env(key)])
    prefix = f"zzc{uuid.uuid4().hex[:6]}"
    md = _tables(prefix)
    md.create_all(engine)
    if key == "mssql":
        # Índices con columnas INCLUDE y filtrado: las reglas de MSDialect.get_indexes que hay que reproducir
        with engine.begin() as conn:
            conn.exec_driver_sql(f"CREATE INDEX {prefix}_ix_inc ON {prefix}_c (a) INCLUDE (b, self_id)")
            conn.exec_driver_sql(f"CREATE INDEX {prefix}_ix_filt ON {prefix}_c (p_id) WHERE p_id IS NOT NULL")
            # Tipos variados: las columnas de SQL Server también se precargan por schema (B1) y deben dar los mismos
            # tipos de SQLAlchemy que MSDialect.get_columns tabla a tabla
            conn.exec_driver_sql(
                f"CREATE TABLE {prefix}_t (id INT IDENTITY(10,5) PRIMARY KEY, "
                "n NVARCHAR(30) COLLATE Latin1_General_BIN DEFAULT N'x', d DECIMAL(12,2), f FLOAT, vb VARBINARY(MAX), "
                "v VARCHAR(MAX), dt DATETIME2(3), comp AS (d * 2) PERSISTED, m MONEY, flag BIT, u UNIQUEIDENTIFIER)"
            )
    if key in ("mysql", "mariadb"):
        # H-29: SHOW CREATE TABLE reconstruido desde information_schema; tipos, defaults, collations, columnas
        # generadas, índices de prefijo/DESC/FULLTEXT y reglas de FK deben dar lo mismo que la reflexión tabla a tabla
        stored_not_null = "STORED NOT NULL" if key == "mysql" else "STORED"
        with engine.begin() as conn:
            conn.exec_driver_sql(
                f"CREATE TABLE {prefix}_t (id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, i INT DEFAULT 0, "
                "d DECIMAL(12,2) DEFAULT 1.50, f FLOAT DEFAULT 1.5, b BIT(3) DEFAULT b'101', bo BOOLEAN DEFAULT TRUE, "
                "z INT(5) UNSIGNED ZEROFILL, v1 VARCHAR(30) DEFAULT 'it''s', v2 VARCHAR(30) COLLATE utf8mb4_bin, "
                "v3 VARCHAR(30) CHARACTER SET latin1, v4 VARCHAR(30) CHARACTER SET latin1 COLLATE latin1_bin, "
                "v5 VARCHAR(10) NOT NULL DEFAULT '', tx TEXT, js JSON, e ENUM('a','b''c') DEFAULT 'a', "
                "s SET('x','y') DEFAULT 'x,y', dt DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3), "
                "ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, "
                "tn TIMESTAMP NULL DEFAULT NULL, dd DATE DEFAULT '2020-01-01', u CHAR(36) DEFAULT (uuid()), "
                f"gv INT AS (i * 2) VIRTUAL, gs INT AS (i + 1) {stored_not_null}, "
                "c VARCHAR(5) COMMENT 'com''ent \\\\ x', p_id INT, a INT, "
                f"PRIMARY KEY (id), UNIQUE KEY {prefix}_uk (v5), KEY {prefix}_ix (i DESC, v1(10)), "
                f"FULLTEXT KEY {prefix}_ft (tx), "
                f"CONSTRAINT {prefix}_fk1 FOREIGN KEY (p_id) REFERENCES {prefix}_p (id) "
                "ON DELETE SET NULL ON UPDATE CASCADE, "
                f"CONSTRAINT {prefix}_fk2 FOREIGN KEY (p_id) REFERENCES {prefix}_p (id) ON DELETE RESTRICT, "
                f"CONSTRAINT {prefix}_fk3 FOREIGN KEY (a) REFERENCES {prefix}_p (id) ON DELETE NO ACTION"
                ") ENGINE=InnoDB COMMENT='tabla ''t'''"
            )
    extra = [f"{prefix}_t"] if key in ("mssql", "mysql", "mariadb") else []
    names = [t.name for t in md.sorted_tables] + extra
    try:
        yield key, engine, names
    finally:
        if extra:
            with engine.begin() as conn:
                conn.exec_driver_sql(f"DROP TABLE IF EXISTS {prefix}_t")
        md.drop_all(engine, checkfirst=True)
        engine.dispose()


@pytest.mark.parametrize("engine_and_tables", _params(), indirect=True)
def test_prefetch_matches_per_table_reflection(engine_and_tables: Any) -> None:
    key, engine, created = engine_and_tables
    default_schema = inspect(engine).default_schema_name
    for schema in (None, default_schema):
        insp = inspect(engine)
        names = [t for t in insp.get_table_names(schema=schema) if t in {n.lower() for n in created} | set(created)]
        assert len(names) == len(created), (key, names, created)

        expected = {
            "columns": {t: insp.get_columns(t, schema=schema) for t in names},
            "pk": {t: insp.get_pk_constraint(t, schema=schema) for t in names},
            "indexes": {t: insp.get_indexes(t, schema=schema) for t in names},
            "fks": {t: insp.get_foreign_keys(t, schema=schema) for t in names},
            "comments": {t: insp.get_table_comment(t, schema=schema).get("text") or "" for t in names},
        }

        statements: list[str] = []

        def record(_conn: Any, _cursor: Any, statement: str, *_args: Any, sink: list[str] = statements) -> None:
            sink.append(statement)

        event.listen(engine, "before_cursor_execute", record)
        try:
            meta = prefetch_table_metadata(inspect(engine), schema, names, kinds=KINDS)
        finally:
            event.remove(engine, "before_cursor_execute", record)
        if key in ("mysql", "mariadb"):
            # H-29: todo por lotes (5 consultas por schema), ni un SHOW CREATE TABLE ni la corrección de FKs por tabla
            assert not [s for s in statements if s.upper().startswith("SHOW CREATE")], statements
            assert len(statements) <= 6, statements
        per_table = AssertionError("consulta tabla a tabla: la precarga no cubrió la tabla")
        with (
            patch.object(Inspector, "get_columns", side_effect=per_table),
            patch.object(Inspector, "get_pk_constraint", side_effect=per_table),
            patch.object(Inspector, "get_indexes", side_effect=per_table),
            patch.object(Inspector, "get_foreign_keys", side_effect=per_table),
            patch.object(Inspector, "get_table_comment", side_effect=per_table),
        ):
            for kind in KINDS:
                for table in names:
                    assert _normalize(kind, meta.get(kind, table)) == _normalize(kind, expected[kind][table]), (
                        key,
                        schema,
                        kind,
                        table,
                    )

        if key in ("mssql", "mysql", "mariadb"):
            # PK, índices, FKs, comentarios y columnas salen de consultas por schema: mismo dict que el dialecto tabla a
            # tabla (dialect_options, include_columns, options, referred_schema, computed y tipos incluidos).
            insp = inspect(engine)
            for table in names:
                assert table in meta.prefetched["columns"], table  # precargada, no tabla a tabla
                expected_columns = insp.get_columns(table, schema=schema)
                assert [_full_column(c) for c in meta.get("columns", table)] == [
                    _full_column(c) for c in expected_columns
                ], table
                got_fks = sorted(meta.get("fks", table), key=lambda fk: fk["name"])
                assert got_fks == sorted(expected["fks"][table], key=lambda fk: fk["name"]), table
                assert meta.get("pk", table) == insp.get_pk_constraint(table, schema=schema), table
                assert meta.get("indexes", table) == insp.get_indexes(table, schema=schema), table
                assert meta.prefetched["comments"][table] == expected["comments"][table], table
