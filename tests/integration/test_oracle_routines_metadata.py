"""Rutinas de Oracle en los adaptadores de metadatos contra un servidor real (hotfix 0.23.1).

``fetch_routines_sql`` devolvía ``(procedure_name, object_type, object_id)``: en ``ALL_PROCEDURES`` el nombre de una
rutina suelta (y el de cada package) está en ``object_name`` y ``procedure_name`` es NULL, así que
``fetch_routines_sync`` las listaba con nombre vacío; además ``decode_oracle_routine_rows`` espera
``(nombre, tipo, owner, object_id)`` y ponía el ``object_id`` como owner. Se salta sin ``UTIL_BBDD_TEST_ORACLE_URL``.
Crea y borra ``ZZRT_PROC``, ``ZZRT_FN``, ``ZZRT_PKG`` y ``ZZRT_T`` (con el disparador ``ZZRT_TRG``).

0.23.2: el listado solo devuelve procedimientos y funciones, como en el resto de motores (``ALL_PROCEDURES`` incluye
también packages, disparadores y tipos).
"""

from __future__ import annotations

import os

from collections.abc import Iterator

import pytest

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from util_bbdd import SyncDatabaseManager
from util_bbdd.metadata.oracle.sync_adapter import OracleSyncAdapter

URL = os.environ.get("UTIL_BBDD_TEST_ORACLE_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not URL, reason="UTIL_BBDD_TEST_ORACLE_URL no definida"),
]

_DDL = [
    "CREATE OR REPLACE PROCEDURE zzrt_proc AS BEGIN NULL; END;",
    "CREATE OR REPLACE FUNCTION zzrt_fn RETURN NUMBER AS BEGIN RETURN 1; END;",
    "CREATE OR REPLACE PACKAGE zzrt_pkg AS PROCEDURE miembro; END zzrt_pkg;",
    # 0.23.2: un disparador también está en ALL_PROCEDURES (object_type TRIGGER) y no es una rutina
    "CREATE TABLE zzrt_t (id NUMBER(10))",
    "CREATE OR REPLACE TRIGGER zzrt_trg BEFORE INSERT ON zzrt_t FOR EACH ROW BEGIN NULL; END;",
]
_CLEANUP = [
    "DROP PROCEDURE zzrt_proc",
    "DROP FUNCTION zzrt_fn",
    "DROP PACKAGE zzrt_pkg",
    "DROP TABLE zzrt_t",  # borra también el disparador
]


def _run(statements: list[str], ignore_errors: bool) -> None:
    engine = create_engine(URL or "", isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            cursor = conn.connection.dbapi_connection.cursor()
            for statement in statements:
                try:
                    cursor.execute(statement)
                except Exception:
                    if not ignore_errors:
                        raise
    finally:
        engine.dispose()


@pytest.fixture
def routines() -> Iterator[str]:
    _run(_CLEANUP, ignore_errors=True)
    _run(_DDL, ignore_errors=False)
    try:
        yield str(make_url(URL or "").username).upper()
    finally:
        _run(_CLEANUP, ignore_errors=True)


def test_routines_are_listed_with_name_and_owner(routines: str) -> None:
    url = make_url(URL or "")
    manager = SyncDatabaseManager(
        "oracle",
        {
            "host": url.host,
            "port": url.port,
            "user": url.username,
            "password": url.password,
            "service_name": url.query.get("service_name"),
        },
        use_pool=False,
    )
    try:
        rows = OracleSyncAdapter(manager).fetch_routines_sync(routines)
    finally:
        manager.close()
    ours = sorted(row for row in rows if str(row[0]).upper().startswith("ZZRT_") or row[0] == "MIEMBRO")
    # Solo procedimientos y funciones (0.23.2), como en el resto de motores: ni el package ni su miembro ni el
    # disparador. Nombre de object_name y owner = el schema, no el object_id (hotfix 0.23.1).
    assert ours == [("ZZRT_FN", "FUNCTION", routines), ("ZZRT_PROC", "PROCEDURE", routines)]
    assert all(row[0] for row in rows), [row for row in rows if not row[0]]
    assert {row[1] for row in rows} <= {"PROCEDURE", "FUNCTION"}, sorted({row[1] for row in rows})
