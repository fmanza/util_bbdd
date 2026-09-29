"""C1 de V4: texto que guarda Oracle en ALL_VIEWS para las vistas con CONNECT BY del corpus."""

import os

from sqlalchemy import create_engine

VIEWS = {
    "ZZVW_JERARQUIA": "SELECT e.id, e.nombre, LEVEL AS nivel FROM zzvw_empleados e WHERE e.activo = 1 "
    "START WITH e.jefe_id IS NULL CONNECT BY PRIOR e.id = e.jefe_id",
    "ZZVW_JERARQUIA_RUTA": "SELECT id, SYS_CONNECT_BY_PATH(nombre, '/') AS ruta, CONNECT_BY_ROOT nombre AS raiz "
    "FROM zzvw_empleados START WITH jefe_id IS NULL CONNECT BY jefe_id = PRIOR id",
    "ZZVW_GENERADOR": "SELECT LEVEL AS n FROM dual CONNECT BY LEVEL <= 5",
}
engine = create_engine(os.environ["UTIL_BBDD_TEST_ORACLE_URL"], isolation_level="AUTOCOMMIT")
with engine.connect() as conn:
    cur = conn.connection.dbapi_connection.cursor()
    for stmt in ["DROP TABLE zzvw_empleados", *(f"DROP VIEW {v}" for v in VIEWS)]:
        try:
            cur.execute(stmt)
        except Exception:
            pass
    cur.execute("CREATE TABLE zzvw_empleados (id NUMBER(10) PRIMARY KEY, nombre VARCHAR2(50), jefe_id NUMBER(10), activo NUMBER(1))")
    for name, sql in VIEWS.items():
        cur.execute(f"CREATE VIEW {name} AS {sql}")
    cur.execute("SELECT view_name, text FROM user_views WHERE view_name LIKE 'ZZVW%' ORDER BY view_name")
    for name, text in cur.fetchall():
        print(name, "=>", text)
    for stmt in [*(f"DROP VIEW {v}" for v in VIEWS), "DROP TABLE zzvw_empleados"]:
        cur.execute(stmt)
engine.dispose()
