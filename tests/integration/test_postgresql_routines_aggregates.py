"""``metadata.postgresql.routines.fetch_routines_sql`` con agregados en el schema (hotfix 2026-10-02).

``pg_get_functiondef`` falla con los agregados ("... is an aggregate function"); llamado sobre todas las filas de
``pg_proc``, un solo agregado hacía fallar la consulta entera (sin routines en los adaptadores de metadatos ni en
``migrate``). Necesita ``UTIL_BBDD_TEST_POSTGRESQL_URL``; crea y borra un schema propio.
"""

from __future__ import annotations

import os
import uuid

import pytest

from sqlalchemy import create_engine, text

from util_bbdd.metadata.postgresql.routines import fetch_routines_sql

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("UTIL_BBDD_TEST_POSTGRESQL_URL"), reason="UTIL_BBDD_TEST_POSTGRESQL_URL no definida"
    ),
]


def test_schema_with_aggregate_lists_every_routine() -> None:
    engine = create_engine(os.environ["UTIL_BBDD_TEST_POSTGRESQL_URL"])
    schema = f"zz_hf_agg_{uuid.uuid4().hex[:6]}"
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
        conn.execute(text(f"CREATE AGGREGATE {schema}.a_sum(int) (SFUNC = int4pl, STYPE = int)"))
        conn.execute(text(f"CREATE FUNCTION {schema}.b_func() RETURNS int LANGUAGE sql AS 'select 1'"))
        conn.execute(text(f"CREATE PROCEDURE {schema}.c_proc() LANGUAGE sql AS 'select 1'"))
    try:
        with engine.connect() as conn:
            rows = conn.exec_driver_sql(fetch_routines_sql(schema), {"schema": schema}).all()

        # (routine_name, routine_type, definición presente, is_aggregate)
        assert [(r[0], r[1], bool(r[3]), r[5]) for r in rows] == [
            ("a_sum", "AGGREGATE", False, 1),  # sigue en el listado, sin DDL
            ("b_func", "FUNCTION", True, 0),
            ("c_proc", "PROCEDURE", True, 0),
        ]
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        engine.dispose()
