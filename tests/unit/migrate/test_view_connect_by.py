"""``CONNECT BY`` de Oracle → CTE recursiva (V4, sesión 2026-09-29c-migrate-views).

El SQL generado para PostgreSQL se ejecuta además en SQLite (admite ``WITH RECURSIVE``, ``||``, ``COALESCE`` y
``CAST(... AS VARCHAR(n))``) para comparar filas: un ``WHERE`` colocado en la CTE en lugar de fuera poda la rama del
jefe inactivo y el test lo detecta.
"""

from __future__ import annotations

import sqlite3

import pytest

sqlglot = pytest.importorskip("sqlglot")

from sqlglot import exp  # noqa: E402

from util_bbdd.migrate.ir.models import CanonicalView  # noqa: E402
from util_bbdd.migrate.views.transpiler import ViewTranspileContext, transpile_view  # noqa: E402

TYPES: dict[str, dict[str, str]] = {
    "ZZV_EMP": {
        "ID": "NUMBER",
        "NOMBRE": "VARCHAR2",
        "CODIGO": "CHAR",
        "JEFE_ID": "NUMBER",
        "ACTIVO": "NUMBER",
        "SALARIO": "NUMBER",
        "ALTA": "DATE",
    },
}
INTEGERS: dict[str, frozenset[str]] = {"ZZV_EMP": frozenset({"ID", "JEFE_ID", "ACTIVO"})}

# 1 Ana (raíz) → 2 Luis (inactivo) → 3 Eva; 1 → 4 Juan; 5 Rosa (raíz, sin hijos)
ROWS = [(1, "Ana", None, 1), (2, "Luis", 1, 0), (3, "Eva", 2, 1), (4, "Juan", 1, 1), (5, "Rosa", None, 1)]


def _ctx(target: str, extra_objects: dict[str, str] | None = None) -> ViewTranspileContext:
    return ViewTranspileContext(
        source_engine="oracle",
        target_engine=target,
        source_schema="BENCH",
        object_names={"zzv_emp": "zzv_emp"} | (extra_objects or {}),
        column_names={c.lower(): c.lower() for c in TYPES["ZZV_EMP"]},
        column_types=TYPES,
        integer_columns=INTEGERS,
    )


def _transpile(sql: str, target: str = "postgresql", **kwargs: dict[str, str]) -> CanonicalView:
    return transpile_view(CanonicalView("zzv_v", "zzv_v", "BENCH", sql, [], "", []), _ctx(target, **kwargs))


def _types(view: CanonicalView) -> list[str]:
    return [w.target_type for w in view.warnings]


def _messages(view: CanonicalView) -> str:
    return " | ".join(w.message for w in view.warnings)


def _run_sqlite(query: str) -> list[tuple[object, ...]]:
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute('CREATE TABLE "zzv_emp" ("id" INT, "nombre" VARCHAR(50), "jefe_id" INT, "activo" INT)')
        conn.executemany('INSERT INTO "zzv_emp" VALUES (?, ?, ?, ?)', ROWS)
        return sorted(conn.execute(query).fetchall())
    finally:
        conn.close()


HIERARCHY = (
    "SELECT e.id, e.nombre, LEVEL AS nivel FROM zzv_emp e WHERE e.activo = 1 "
    "START WITH e.jefe_id IS NULL CONNECT BY PRIOR e.id = e.jefe_id"
)
PATH = (
    "SELECT id, SYS_CONNECT_BY_PATH(nombre, '/') AS ruta, CONNECT_BY_ROOT nombre AS raiz FROM zzv_emp "
    "START WITH jefe_id IS NULL CONNECT BY jefe_id = PRIOR id"
)


class TestHierarchy:
    def test_where_is_applied_after_the_hierarchy(self) -> None:
        view = _transpile(HIERARCHY)
        # Luis (inactivo) no sale, pero su subordinada Eva sí, con nivel 3: como en Oracle.
        assert _run_sqlite(view.query) == [(1, "Ana", 1), (3, "Eva", 3), (4, "Juan", 2), (5, "Rosa", 1)]

    def test_where_is_in_the_outer_query_only(self) -> None:
        tree = sqlglot.parse_one(_transpile(HIERARCHY).query, read="postgres")
        cte = tree.find(exp.CTE)
        assert cte is not None
        cte_filters = [s.args["where"].sql().lower() for s in cte.find_all(exp.Select) if s.args.get("where")]
        assert cte_filters and not any("activo" in f for f in cte_filters)  # solo START WITH en el ancla
        assert "activo" in tree.args["where"].sql().lower()

    def test_path_and_root(self) -> None:
        rows = _run_sqlite(_transpile(PATH).query)
        assert rows == [
            (1, "/Ana", "Ana"),
            (2, "/Ana/Luis", "Ana"),
            (3, "/Ana/Luis/Eva", "Ana"),
            (4, "/Ana/Juan", "Ana"),
            (5, "/Rosa", "Rosa"),
        ]

    def test_path_on_integer_column(self) -> None:
        sql = "SELECT SYS_CONNECT_BY_PATH(id, '-') AS ruta FROM zzv_emp START WITH id = 1 CONNECT BY PRIOR id = jefe_id"
        assert _run_sqlite(_transpile(sql).query) == [("-1",), ("-1-2",), ("-1-2-3",), ("-1-4",)]

    def test_without_start_with_every_row_is_a_root(self) -> None:
        sql = "SELECT id, LEVEL AS nivel FROM zzv_emp CONNECT BY PRIOR id = jefe_id"
        rows = _run_sqlite(_transpile(sql).query)
        # Una fila por nodo y antepasado (camino): 1 + 2 + 3 + 2 + 1, como Oracle sin START WITH.
        assert (3, 1) in rows and (3, 2) in rows and (3, 3) in rows and len(rows) == 9

    @pytest.mark.parametrize(
        ("target", "with_clause", "path_type", "limit"),
        [
            ("postgresql", "WITH RECURSIVE", "VARCHAR(4000)", "no limita"),
            ("sqlserver", "WITH ", "NVARCHAR(4000)", "100 niveles"),
            ("mysql", "WITH RECURSIVE", "CHAR(4000)", "1000 niveles"),
            ("mariadb", "WITH RECURSIVE", "CHAR(4000)", "no limita"),
        ],
    )
    def test_sql_and_warning_per_target(self, target: str, with_clause: str, path_type: str, limit: str) -> None:
        view = _transpile(PATH, target)
        assert view.query.startswith(with_clause)
        assert target != "sqlserver" or "RECURSIVE" not in view.query
        assert f"AS {path_type})" in view.query
        for oracle_only in ("CONNECT BY", "PRIOR", "SYS_CONNECT_BY_PATH", "CONNECT_BY_ROOT"):
            assert oracle_only not in view.query
        assert "VIEW (jerarquía)" in _types(view) and limit in _messages(view)
        assert "VIEW (sin reescribir)" not in _types(view)

    def test_source_schema_is_dropped_and_external_schema_is_kept(self) -> None:
        own = _transpile(HIERARCHY.replace("FROM zzv_emp e", "FROM BENCH.zzv_emp e"))
        assert "BENCH" not in own.query.upper()
        other = _transpile(HIERARCHY.replace("FROM zzv_emp e", "FROM OTRO.zzv_emp e"))
        assert other.query.upper().count("OTRO.") == 2 and "VIEW (referencia externa)" in _types(other)

    def test_cte_name_avoids_plan_objects(self) -> None:
        view = _transpile(HIERARCHY, extra_objects={"connect_by_tree": "connect_by_tree"})
        assert "CONNECT_BY_TREE_2" in view.query.upper()


class TestGenerator:
    @pytest.mark.parametrize("condition", ["LEVEL <= 4", "LEVEL < 5", "4 >= LEVEL", "5 > LEVEL"])
    def test_rows(self, condition: str) -> None:
        view = _transpile(f"SELECT LEVEL AS n FROM dual CONNECT BY {condition}")
        assert _run_sqlite(view.query) == [(1,), (2,), (3,), (4,)]
        assert "VIEW (jerarquía)" not in _types(view)

    @pytest.mark.parametrize(
        ("target", "rows", "rewritten"),
        [("sqlserver", 101, True), ("sqlserver", 102, False), ("mysql", 1001, True), ("mysql", 1002, False)],
    )
    def test_recursion_limit(self, target: str, rows: int, rewritten: bool) -> None:
        sql = f"SELECT LEVEL AS n FROM dual CONNECT BY LEVEL <= {rows}"
        view = _transpile(sql, target)
        assert (view.query != sql) is rewritten
        if not rewritten:
            assert "recursiones" in _messages(view)


class TestNotRewritten:
    @pytest.mark.parametrize(
        ("sql", "reason"),
        [
            ("SELECT id FROM zzv_emp CONNECT BY NOCYCLE PRIOR id = jefe_id", "NOCYCLE"),
            ("SELECT id FROM zzv_emp CONNECT BY PRIOR id = jefe_id ORDER SIBLINGS BY nombre", "ORDER SIBLINGS BY"),
            ("SELECT id FROM zzv_emp CONNECT BY PRIOR id = jefe_id AND LEVEL <= 3", "PRIOR columna = columna"),
            ("SELECT id FROM zzv_emp CONNECT BY PRIOR id + 1 = jefe_id", "PRIOR columna = columna"),
            (
                "SELECT e.id FROM zzv_emp e JOIN zzv_emp j ON j.id = e.jefe_id CONNECT BY PRIOR e.id = e.jefe_id",
                "joins",
            ),
            ("SELECT * FROM (SELECT id FROM zzv_emp CONNECT BY PRIOR id = jefe_id)", "subconsulta"),
            ("SELECT id, CONNECT_BY_ISLEAF AS hoja FROM zzv_emp CONNECT BY PRIOR id = jefe_id", "CONNECT_BY_ISLEAF"),
            ("SELECT id FROM zzv_emp WHERE ROWNUM <= 3 CONNECT BY PRIOR id = jefe_id", "ROWNUM"),
            ("SELECT id, PRIOR nombre AS jefe FROM zzv_emp CONNECT BY PRIOR id = jefe_id", "PRIOR fuera"),
            ("SELECT id FROM zzv_emp START WITH LEVEL = 1 CONNECT BY PRIOR id = jefe_id", "LEVEL en START WITH"),
            ("SELECT SYS_CONNECT_BY_PATH(alta, '/') AS r FROM zzv_emp CONNECT BY PRIOR id = jefe_id", "DATE"),
            ("SELECT SYS_CONNECT_BY_PATH(codigo, '/') AS r FROM zzv_emp CONNECT BY PRIOR id = jefe_id", "CHAR"),
            ("SELECT SYS_CONNECT_BY_PATH(salario, '/') AS r FROM zzv_emp CONNECT BY PRIOR id = jefe_id", "NUMBER"),
            ("SELECT SYS_CONNECT_BY_PATH(nombre, nombre) AS r FROM zzv_emp CONNECT BY PRIOR id = jefe_id", "literal"),
            ("SELECT id FROM otra CONNECT BY PRIOR id = jefe_id", "fuera del plan"),
            ("SELECT LEVEL AS n, dummy FROM dual CONNECT BY LEVEL <= 3", "dual"),
            (
                "WITH x AS (SELECT 1 AS a FROM dual) SELECT id FROM zzv_emp CONNECT BY PRIOR id = jefe_id",
                "WITH propio",
            ),
        ],
    )
    def test_passthrough_with_reason(self, sql: str, reason: str) -> None:
        view = _transpile(sql, "mysql")
        assert view.query == sql
        assert "VIEW (sin reescribir)" in _types(view)
        assert "CONNECT BY (" in _messages(view) and reason in _messages(view)
