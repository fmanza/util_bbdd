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


class TestLevelBoundAndLeaf:
    """E3 (0.22.0): ``AND LEVEL <= n`` en la condición y ``CONNECT_BY_ISLEAF``."""

    @pytest.mark.parametrize(
        "condition",
        ["PRIOR id = jefe_id AND LEVEL <= 2", "LEVEL < 3 AND jefe_id = PRIOR id", "2 >= LEVEL AND PRIOR id = jefe_id"],
    )
    def test_level_bound_in_connect_by(self, condition: str) -> None:
        sql = f"SELECT id, LEVEL AS nivel FROM zzv_emp START WITH jefe_id IS NULL CONNECT BY {condition}"
        view = _transpile(sql)
        assert _run_sqlite(view.query) == [(1, 1), (2, 2), (4, 2), (5, 1)]
        assert "VIEW (jerarquía)" in _types(view)

    def test_level_bound_below_two_keeps_only_roots(self) -> None:
        sql = "SELECT id FROM zzv_emp START WITH jefe_id IS NULL CONNECT BY PRIOR id = jefe_id AND LEVEL <= 1"
        assert _run_sqlite(_transpile(sql).query) == [(1,), (5,)]

    def test_is_leaf_ignores_the_where_filter(self) -> None:
        sql = (
            "SELECT e.id, CONNECT_BY_ISLEAF AS hoja FROM zzv_emp e WHERE e.activo = 1 "
            "START WITH e.jefe_id IS NULL CONNECT BY PRIOR e.id = e.jefe_id"
        )
        # Luis (inactivo) no sale; Ana sigue sin ser hoja y Eva sí lo es, como en Oracle.
        assert _run_sqlite(_transpile(sql).query) == [(1, 0), (3, 1), (4, 1), (5, 1)]

    def test_is_leaf_with_level_bound(self) -> None:
        sql = (
            "SELECT id, CONNECT_BY_ISLEAF AS hoja FROM zzv_emp START WITH jefe_id IS NULL "
            "CONNECT BY PRIOR id = jefe_id AND LEVEL <= 2"
        )
        # Luis tiene a Eva debajo, pero en el nivel máximo ya no se expande: es hoja.
        assert _run_sqlite(_transpile(sql).query) == [(1, 0), (2, 1), (4, 1), (5, 1)]

    def test_bare_is_leaf_keeps_its_column_name(self) -> None:
        query = _transpile("SELECT id, CONNECT_BY_ISLEAF FROM zzv_emp CONNECT BY PRIOR id = jefe_id").query
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute('CREATE TABLE "zzv_emp" ("id" INT, "nombre" VARCHAR(50), "jefe_id" INT, "activo" INT)')
            names = [d[0] for d in conn.execute(query).description]
        finally:
            conn.close()
        assert [n.lower() for n in names] == ["id", "connect_by_isleaf"]

    @pytest.mark.parametrize("target", ["postgresql", "sqlserver", "mysql", "mariadb"])
    def test_is_leaf_per_target(self, target: str) -> None:
        view = _transpile("SELECT id, CONNECT_BY_ISLEAF AS hoja FROM zzv_emp CONNECT BY PRIOR id = jefe_id", target)
        assert "CONNECT_BY_ISLEAF" not in view.query.upper() and "EXISTS" in view.query
        assert "VIEW (sin reescribir)" not in _types(view)


class TestSelectStar:
    """H1 (auditoría 0.22.0): ``SELECT *`` / ``alias.*`` se expande con las columnas de la tabla, en su orden.

    Antes, la CTE solo llevaba las columnas nombradas y la vista devolvía ``jefe_id, id, cb_level``.
    """

    COLUMNS = {"ZZV_EMP": {"ID": "NUMBER", "NOMBRE": "VARCHAR2", "JEFE_ID": "NUMBER", "ACTIVO": "NUMBER"}}

    def _run(self, sql: str) -> tuple[list[str], list[tuple[object, ...]]]:
        ctx = ViewTranspileContext(
            source_engine="oracle",
            target_engine="postgresql",
            source_schema="BENCH",
            object_names={"zzv_emp": "zzv_emp"},
            column_names={c.lower(): c.lower() for c in self.COLUMNS["ZZV_EMP"]},
            column_types=self.COLUMNS,
            integer_columns=INTEGERS,
        )
        view = transpile_view(CanonicalView("zzv_v", "zzv_v", "BENCH", sql, [], "", []), ctx)
        assert "VIEW (sin reescribir)" not in _types(view)
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute('CREATE TABLE "zzv_emp" ("id" INT, "nombre" VARCHAR(50), "jefe_id" INT, "activo" INT)')
            conn.executemany('INSERT INTO "zzv_emp" VALUES (?, ?, ?, ?)', ROWS)
            cursor = conn.execute(view.query)
            return [d[0].lower() for d in cursor.description], cursor.fetchall()
        finally:
            conn.close()

    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT * FROM zzv_emp START WITH jefe_id IS NULL CONNECT BY PRIOR id = jefe_id",
            "SELECT e.* FROM zzv_emp e START WITH e.jefe_id IS NULL CONNECT BY PRIOR e.id = e.jefe_id",
        ],
        ids=["star", "alias-star"],
    )
    def test_star_returns_the_table_columns(self, sql: str) -> None:
        names, rows = self._run(sql)
        assert names == ["id", "nombre", "jefe_id", "activo"]
        assert sorted(rows, key=lambda r: r[0]) == sorted(ROWS, key=lambda r: r[0])

    def test_star_with_level(self) -> None:
        names, rows = self._run(
            "SELECT e.*, LEVEL AS nivel FROM zzv_emp e START WITH e.jefe_id IS NULL CONNECT BY PRIOR e.id = e.jefe_id"
        )
        assert names == ["id", "nombre", "jefe_id", "activo", "nivel"]
        assert (3, "Eva", 2, 1, 3) in rows

    def test_star_in_a_row_generator_is_not_rewritten(self) -> None:
        view = _transpile("SELECT * FROM dual CONNECT BY LEVEL <= 3", "mysql")
        assert "VIEW (sin reescribir)" in _types(view) and "DUMMY" in _messages(view)


class TestOrderSiblings:
    """F1 (0.23.0): ``ORDER SIBLINGS BY`` → ``cb_order`` (rango de hermanos por nivel) y ``ORDER BY cb_order``.

    El SQL de PostgreSQL se ejecuta en SQLite **sin ordenar** las filas: el orden es lo que se prueba. Árbol: Ana
    (Luis → Eva, Juan) y Rosa; en profundidad y con los hermanos por nombre: Ana, Juan, Luis, Eva, Rosa.
    """

    BASE = "SELECT nombre, LEVEL AS nivel FROM zzv_emp START WITH jefe_id IS NULL CONNECT BY PRIOR id = jefe_id"

    @staticmethod
    def _ordered(query: str) -> list[tuple[object, ...]]:
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute('CREATE TABLE "zzv_emp" ("id" INT, "nombre" VARCHAR(50), "jefe_id" INT, "activo" INT)')
            conn.executemany('INSERT INTO "zzv_emp" VALUES (?, ?, ?, ?)', ROWS)
            return conn.execute(query).fetchall()
        finally:
            conn.close()

    @pytest.mark.parametrize(
        ("order", "expected"),
        [
            ("nombre", ["Ana", "Juan", "Luis", "Eva", "Rosa"]),
            ("nombre DESC", ["Rosa", "Ana", "Luis", "Eva", "Juan"]),
            ("id DESC", ["Rosa", "Ana", "Juan", "Luis", "Eva"]),
        ],
    )
    def test_depth_first_with_sorted_siblings(self, order: str, expected: list[str]) -> None:
        view = _transpile(f"{self.BASE} ORDER SIBLINGS BY {order}")
        assert [row[0] for row in self._ordered(view.query)] == expected
        assert "SIBLINGS" not in view.query.upper() and "se conserva" in _messages(view)

    def test_where_filters_after_ordering(self) -> None:
        sql = self.BASE.replace("FROM zzv_emp", "FROM zzv_emp WHERE activo = 1") + " ORDER SIBLINGS BY nombre"
        # Luis (inactivo) no sale; su subordinada Eva conserva su sitio, detrás de Juan.
        assert [row[0] for row in self._ordered(_transpile(sql).query)] == ["Ana", "Juan", "Eva", "Rosa"]

    @pytest.mark.parametrize("target", ["mysql", "mariadb"])
    def test_mysql_family_ranks_outside_the_recursion(self, target: str) -> None:
        """MySQL/MariaDB no admiten ventanas en la rama recursiva (3575/4008): la numeración va en una CTE previa."""
        query = _transpile(f"{self.BASE} ORDER SIBLINGS BY nombre", target).query.upper()
        ranked, recursive = query.split("CONNECT_BY_TREE AS (", 1)
        assert "ROW_NUMBER() OVER (PARTITION BY" in ranked
        assert "OVER (PARTITION BY" not in recursive.split(" UNION ALL ", 1)[1]
        # El orden de NULL de Oracle (NULLS LAST en ASC) se hace explícito en MySQL.
        assert "CASE WHEN ZZV_EMP.`NOMBRE` IS NULL THEN 1 ELSE 0 END" in query
        # sqlglot añade también aquí el CASE de NULL; cb_order nunca es NULL, así que no cambia el orden.
        assert query.endswith("ZZV_EMP.CB_ORDER") and " ORDER BY " in query.rsplit("FROM CONNECT_BY_TREE", 1)[1]

    def test_sqlserver_converts_without_order_and_warns(self) -> None:
        view = _transpile(f"{self.BASE} ORDER SIBLINGS BY nombre", "sqlserver")
        assert "ORDER BY" not in view.query.upper() and "CB_ORDER" not in view.query.upper()
        assert "VIEW (sin reescribir)" not in _types(view)
        assert "no admite ORDER BY en una vista" in _messages(view)


class TestNocycle:
    """E3 (0.22.0): ``NOCYCLE`` → array de antepasados en PostgreSQL; en el resto de destinos, sin reescribir.

    Las filas se comparan con Oracle en ``tests/integration/test_migrate_views_e2e.py`` (SQLite no tiene arrays).
    """

    SQL = (
        "SELECT id, LEVEL AS nivel, CONNECT_BY_ISLEAF AS hoja FROM zzv_emp START WITH id = 1 "
        "CONNECT BY NOCYCLE PRIOR id = jefe_id"
    )

    def test_postgresql_stops_at_ancestors(self) -> None:
        view = _transpile(self.SQL)
        query = view.query.upper()
        # C1 (auditoría 0.22.0): claves como TEXT; un ARRAY de VARCHAR(n)/NUMERIC(p,s) rompía la CTE en PostgreSQL.
        assert 'ARRAY[CAST(ZZV_EMP."ID" AS TEXT)] AS CB_KEYS' in query
        assert 'CONNECT_BY_PARENT.CB_KEYS || ARRAY[CAST(ZZV_EMP."ID" AS TEXT)] AS CB_KEYS' in query
        tree = sqlglot.parse_one(view.query, read="postgres")
        recursive = tree.find(exp.CTE).this.expression  # type: ignore[union-attr]
        # C2: COALESCE para que un NULL en la columna de PRIOR no pierda la fila.
        assert (
            'NOT COALESCE(CAST(ZZV_EMP."ID" AS TEXT) = ANY(CONNECT_BY_PARENT.CB_KEYS), FALSE)'
            in recursive.args["where"].sql().upper()
        )
        # ISLEAF no cuenta el hijo que cerraría el ciclo; la consulta exterior no filtra nada.
        assert 'NOT COALESCE(CAST(CB_CHILD."ID" AS TEXT) = ANY(ZZV_EMP.CB_KEYS), FALSE)' in query
        assert tree.args.get("where") is None
        assert "VIEW (jerarquía)" in _types(view) and "NOCYCLE" in _messages(view)
        assert "NOCYCLE" not in query and " CYCLE " not in query

    def test_is_cycle_counts_children_on_the_path(self) -> None:
        """F2 (0.23.0): CONNECT_BY_ISCYCLE = hay un hijo visitable que ya está en el camino (espejo de ISLEAF)."""
        sql = self.SQL.replace("CONNECT_BY_ISLEAF AS hoja", "CONNECT_BY_ISCYCLE AS ciclo") + " AND LEVEL <= 3"
        view = _transpile(sql)
        query = view.query.upper()
        assert "CONNECT_BY_ISCYCLE" not in query and "VIEW (sin reescribir)" not in _types(view)
        assert (
            'CASE WHEN ZZV_EMP.CB_LEVEL < 3 AND EXISTS(SELECT 1 AS "1" FROM "ZZV_EMP" AS CB_CHILD WHERE '
            'CB_CHILD."JEFE_ID" = ZZV_EMP."ID" AND COALESCE(CAST(CB_CHILD."ID" AS TEXT) = ANY(ZZV_EMP.CB_KEYS), FALSE)) '
            "THEN 1 ELSE 0 END AS CICLO"
        ) in query

    def test_where_of_the_view_stays_in_the_outer_query(self) -> None:
        sql = self.SQL.replace("FROM zzv_emp ", "FROM zzv_emp WHERE activo = 1 ")
        where = sqlglot.parse_one(_transpile(sql).query, read="postgres").args["where"].sql().lower()
        assert "activo" in where and "cb_keys" not in where

    @pytest.mark.parametrize(
        ("target", "binary_search", "separator"),
        [
            ("sqlserver", "COLLATE LATIN1_GENERAL_BIN2", "CHAR(31)"),
            ("mysql", "AS BINARY)", "CHAR(31)"),
            ("mariadb", "AS BINARY)", "CHAR(31)"),
        ],
    )
    def test_other_targets_use_a_text_path(self, target: str, binary_search: str, separator: str) -> None:
        """F3 (0.23.0): sin arrays, el camino es texto separado por CHAR(31) y se busca en binario.

        Binario: con la collation por defecto (sin distinguir mayúsculas), 'abc' y 'ABC' serían la misma clave y darían
        un falso ciclo. Las filas se comparan con Oracle en el e2e.
        """
        view = _transpile(self.SQL, target)
        query = view.query.upper()
        assert "VIEW (sin reescribir)" not in _types(view) and "VIEW (jerarquía)" in _types(view)
        assert "NOCYCLE" not in query and "ANY(" not in query and "ARRAY[" not in query
        assert separator in query and binary_search in query
        assert "CHAR(31)" in _messages(view)
        # La búsqueda es COALESCE(posición, 0) > 0: SQL Server no admite COALESCE sobre una condición.
        assert ", 0) > 0" in query


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
            (
                "SELECT id FROM zzv_emp CONNECT BY PRIOR id = jefe_id ORDER SIBLINGS BY UPPER(nombre)",
                "ORDER SIBLINGS BY con algo que no es una columna",
            ),
            (
                "SELECT LEVEL AS n FROM dual CONNECT BY LEVEL <= 3 ORDER SIBLINGS BY n",
                "ORDER SIBLINGS BY en un generador",
            ),
            ("SELECT id FROM zzv_emp CONNECT BY PRIOR id = jefe_id AND activo = 1", "PRIOR columna = columna"),
            ("SELECT id FROM zzv_emp CONNECT BY PRIOR id = jefe_id AND LEVEL <= jefe_id", "PRIOR columna = columna"),
            ("SELECT id FROM zzv_emp CONNECT BY PRIOR id + 1 = jefe_id", "PRIOR columna = columna"),
            (
                "SELECT e.id FROM zzv_emp e JOIN zzv_emp j ON j.id = e.jefe_id CONNECT BY PRIOR e.id = e.jefe_id",
                "joins",
            ),
            ("SELECT * FROM (SELECT id FROM zzv_emp CONNECT BY PRIOR id = jefe_id)", "subconsulta"),
            ("SELECT id, CONNECT_BY_ISCYCLE AS c FROM zzv_emp CONNECT BY PRIOR id = jefe_id", "ISCYCLE sin NOCYCLE"),
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
