"""FK compuestas de Oracle contra un servidor real (hotfix 2026-09-30).

``fetch_fk_constraint_sql`` unía las columnas de la FK con las de la constraint referenciada sin emparejar
posiciones: la FK ``(a, b) → padre(a, b)`` salía como ``(A, A, B, B) → (A, B, A, B)`` en orden no determinista y el
DDL migrado era inválido. Se salta sin ``UTIL_BBDD_TEST_ORACLE_URL``. Crea y borra ``ZZFK_PADRE`` y ``ZZFK_HIJA``.
"""

from __future__ import annotations

import os

from collections.abc import Iterator

import pytest

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from util_bbdd import SyncDatabaseManager
from util_bbdd.migrate.extractors.oracle import OracleSchemaExtractor

URL = os.environ.get("UTIL_BBDD_TEST_ORACLE_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not URL, reason="UTIL_BBDD_TEST_ORACLE_URL no definida"),
]

_DDL = [
    "CREATE TABLE zzfk_padre (a NUMBER(10), b NUMBER(10), c NUMBER(10), CONSTRAINT zzfk_pk PRIMARY KEY (a, b, c))",
    "CREATE TABLE zzfk_hija (id NUMBER(10) PRIMARY KEY, x NUMBER(10), y NUMBER(10), z NUMBER(10), "
    "CONSTRAINT zzfk_fk FOREIGN KEY (z, y, x) REFERENCES zzfk_padre (a, b, c) ON DELETE CASCADE)",
]
_CLEANUP = ["DROP TABLE zzfk_hija", "DROP TABLE zzfk_padre"]


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
def composite_fk() -> Iterator[str]:
    _run(_CLEANUP, ignore_errors=True)
    _run(_DDL, ignore_errors=False)
    try:
        yield str(make_url(URL or "").username).upper()
    finally:
        _run(_CLEANUP, ignore_errors=True)


def test_composite_fk_columns_are_paired_by_position(composite_fk: str) -> None:
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
        tables = {t.name: t for t in OracleSchemaExtractor(manager).extract(composite_fk)}
    finally:
        manager.close()
    [fk] = tables["ZZFK_HIJA"].foreign_keys
    # Orden de la FK (z, y, x) y su pareja en la clave referenciada (a, b, c), una vez cada una
    assert (fk.columns, fk.ref_table, fk.ref_columns) == (["Z", "Y", "X"], "ZZFK_PADRE", ["A", "B", "C"])
    assert fk.on_delete == "CASCADE"
