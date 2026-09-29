"""V4: SQL generado por oracle_connect_by para el corpus de jerarquías en cada destino (sin servidores)."""

from util_bbdd.migrate.ir.models import CanonicalView
from util_bbdd.migrate.views.transpiler import ViewTranspileContext, transpile_view

QUERIES = {
    "jerarquia": "SELECT e.id, e.nombre, LEVEL AS nivel FROM zzvw_empleados e WHERE e.activo = 1 "
    "START WITH e.jefe_id IS NULL CONNECT BY PRIOR e.id = e.jefe_id",
    "ruta": "SELECT id, SYS_CONNECT_BY_PATH(nombre, '/') AS ruta, CONNECT_BY_ROOT nombre AS raiz FROM zzvw_empleados "
    "START WITH jefe_id IS NULL CONNECT BY jefe_id = PRIOR id ORDER BY ruta",
    "gen": "SELECT LEVEL AS n FROM dual CONNECT BY LEVEL <= 5",
    "nocycle": "SELECT id FROM zzvw_empleados CONNECT BY NOCYCLE PRIOR id = jefe_id",
    "gen200": "SELECT LEVEL AS n FROM dual CONNECT BY LEVEL <= 200",
}
TYPES = {"ZZVW_EMPLEADOS": {"ID": "NUMBER", "NOMBRE": "VARCHAR2", "JEFE_ID": "NUMBER", "ACTIVO": "NUMBER"}}
INTS = {"ZZVW_EMPLEADOS": frozenset({"ID", "JEFE_ID", "ACTIVO"})}
NAMES = {"id": "id", "nombre": "nombre", "jefe_id": "jefe_id", "activo": "activo"}

for target in ("postgresql", "sqlserver", "mysql"):
    ctx = ViewTranspileContext(
        "oracle",
        target,
        "BENCH",
        object_names={"zzvw_empleados": "zzvw_empleados"},
        column_names=NAMES,
        column_types=TYPES,
        integer_columns=INTS,
    )
    for key, query in QUERIES.items():
        view = transpile_view(CanonicalView(name=key, original_name=key, schema="BENCH", query=query, columns=[], comment="", warnings=[]), ctx)
        shown = view.query if view.query != query else "(sin reescribir)"
        notes = [f"{w.target_type}: {w.message[:100]}" for w in view.warnings if "semántica" not in w.target_type]
        print(f"[{target}/{key}] {shown}\n    {notes}")
