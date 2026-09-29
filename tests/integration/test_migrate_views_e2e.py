"""Vistas de ``MigrationPlanner`` con ``view_strategy="transpile"`` entre los 5 motores reales (20 pares).

Para cada par: crea en el origen dos tablas con datos y un corpus de vistas en el dialecto nativo; planifica con
``MigrationPlanner``; ejecuta el DDL del plan (tablas y vistas) en el destino; copia los datos; comprueba que cada
vista se crea y devuelve lo mismo que en el origen. Los datos evitan la cadena vacía y los NULL en concatenaciones:
en Oracle ``''`` es NULL y ``||`` ignora los NULL (el plan lo avisa; no es un fallo de la reescritura).

Se salta si falta alguna URL (``UTIL_BBDD_TEST_{POSTGRESQL,MYSQL,MARIADB,MSSQL,ORACLE}_URL``, ver
``scripts/bench_env.example.sh``) o sqlglot. Crea y borra bases/schemas ``zz_util_bbdd_vw_src``/``zz_util_bbdd_vw_dst``
(MySQL, MariaDB, SQL Server, PostgreSQL) y tablas/vistas ``ZZVW_*`` en el schema del usuario Oracle.
"""

from __future__ import annotations

import datetime as dt
import os

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest

from sqlalchemy import MetaData, Table, create_engine, select, text
from sqlalchemy.engine import URL, Engine, make_url

from util_bbdd import SyncDatabaseManager

pytest.importorskip("sqlglot")

from util_bbdd.migrate import MigrationPlanner  # noqa: E402

ENGINES = ["mysql", "mariadb", "postgresql", "sqlserver", "oracle"]
URL_ENV = {
    "mysql": "UTIL_BBDD_TEST_MYSQL_URL",
    "mariadb": "UTIL_BBDD_TEST_MARIADB_URL",
    "postgresql": "UTIL_BBDD_TEST_POSTGRESQL_URL",
    "sqlserver": "UTIL_BBDD_TEST_MSSQL_URL",
    "oracle": "UTIL_BBDD_TEST_ORACLE_URL",
}
MISSING = [env for env in URL_ENV.values() if not os.environ.get(env)]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(bool(MISSING), reason=f"{', '.join(MISSING)} no definida(s)"),
]

SRC, DST = "zz_util_bbdd_vw_src", "zz_util_bbdd_vw_dst"
C, P, E = "zzvw_clientes", "zzvw_pedidos", "zzvw_empleados"
A = "zzvw_autoinc"  # A2 (hotfix): id autoincremental; sin filas en el origen (IDENTITY de SQL Server no admite ids)
AUTOINC_ID = {
    "mysql": "id INT AUTO_INCREMENT PRIMARY KEY",
    "mariadb": "id INT AUTO_INCREMENT PRIMARY KEY",
    "postgresql": "id SERIAL PRIMARY KEY",
    "sqlserver": "id INT IDENTITY(1,1) PRIMARY KEY",
    "oracle": "id NUMBER(10) PRIMARY KEY",
}
# A4 (hotfix): DEFAULT y comentario con barras invertidas y comilla. MySQL/MariaDB escapan la barra en el literal.
RUTA = "C:\\datos\\x'q"
RUTA_LITERAL = {
    "mysql": "'C:\\\\datos\\\\x''q'",
    "mariadb": "'C:\\\\datos\\\\x''q'",
}

CLIENTES = [
    (1, "Ana", "Madrid", "2024-01-10", "100.50"),
    (2, "Luis", None, "2024-02-20", "0.00"),
    (3, "Eva", "Sevilla", "2023-12-01", "250.00"),
    (4, "Juan", "Madrid", "2024-03-05", "-20.25"),
]
# Jerarquía (V4, CONNECT BY): Luis está inactivo y tiene a Eva debajo. Oracle aplica el WHERE después de recorrer la
# jerarquía, así que Eva sale con nivel 3; un WHERE colocado dentro de la CTE podaría su rama.
EMPLEADOS = [(1, "Ana", None, 1), (2, "Luis", 1, 0), (3, "Eva", 2, 1), (4, "Juan", 1, 1), (5, "Rosa", None, 1)]
PEDIDOS = [
    (1, 1, "2024-01-15", "30.00"),
    (2, 1, "2024-02-01", "45.50"),
    (3, 3, "2024-01-20", "120.00"),
    (4, 4, "2024-03-10", "5.25"),
]


def _per(my: str | None, pg: str | None, ss: str | None, ora: str | None) -> dict[str, str]:
    return {
        k: v for k, v in {"mysql": my, "mariadb": my, "postgresql": pg, "sqlserver": ss, "oracle": ora}.items() if v
    }


# (clave, SQL común | {motor: SQL}); una cabecera "(a, b) AS ..." declara columnas (SQL Server).
CORPUS: list[tuple[str, Any]] = [
    ("inner_join", f"SELECT c.nombre, p.importe FROM {C} c INNER JOIN {P} p ON p.cliente_id = c.id"),
    (
        "nulos",
        _per(
            f"SELECT id, IFNULL(ciudad, 'x') AS ciudad FROM {C}",
            f"SELECT id, COALESCE(ciudad, 'x') AS ciudad FROM {C}",
            f"SELECT id, ISNULL(ciudad, 'x') AS ciudad FROM {C}",
            f"SELECT id, NVL(ciudad, 'x') AS ciudad FROM {C}",
        ),
    ),
    (
        "concatenacion",
        _per(
            f"SELECT id, CONCAT(nombre, ' - ', nombre) AS e FROM {C}",
            f"SELECT id, nombre || ' - ' || nombre AS e FROM {C}",
            f"SELECT id, nombre + ' - ' + nombre AS e FROM {C}",
            f"SELECT id, nombre || ' - ' || nombre AS e FROM {C}",
        ),
    ),
    (
        "sumar_dias",
        _per(
            f"SELECT id, DATE_ADD(alta, INTERVAL 30 DAY) AS vence FROM {C}",
            f"SELECT id, alta + 30 AS vence FROM {C}",
            f"SELECT id, DATEADD(day, 30, alta) AS vence FROM {C}",
            f"SELECT id, alta + 30 AS vence FROM {C}",
        ),
    ),
    (
        "diferencia_dias",
        _per(
            f"SELECT p.id, DATEDIFF(p.fecha, c.alta) AS d FROM {P} p JOIN {C} c ON c.id = p.cliente_id",
            f"SELECT p.id, p.fecha - c.alta AS d FROM {P} p JOIN {C} c ON c.id = p.cliente_id",
            f"SELECT p.id, DATEDIFF(day, c.alta, p.fecha) AS d FROM {P} p JOIN {C} c ON c.id = p.cliente_id",
            f"SELECT p.id, p.fecha - c.alta AS d FROM {P} p JOIN {C} c ON c.id = p.cliente_id",
        ),
    ),
    (
        "cast_texto",
        _per(
            f"SELECT CAST(id AS CHAR(10)) AS t FROM {C}",
            f"SELECT CAST(id AS VARCHAR(10)) AS t FROM {C}",
            f"SELECT CAST(id AS VARCHAR(10)) AS t FROM {C}",
            f"SELECT CAST(id AS VARCHAR2(10)) AS t FROM {C}",
        ),
    ),
    (
        "top_n",
        _per(
            f"SELECT id, importe FROM {P} ORDER BY importe DESC LIMIT 2",
            f"SELECT id, importe FROM {P} ORDER BY importe DESC LIMIT 2",
            f"SELECT TOP 2 id, importe FROM {P} ORDER BY importe DESC",
            f"SELECT * FROM (SELECT id, importe FROM {P} ORDER BY importe DESC) WHERE ROWNUM <= 2",
        ),
    ),
    (
        "cte",
        f"WITH t AS (SELECT cliente_id, SUM(importe) AS total FROM {P} GROUP BY cliente_id) SELECT cliente_id, total FROM t",
    ),
    ("exists", f"SELECT c.id FROM {C} c WHERE EXISTS (SELECT 1 FROM {P} p WHERE p.cliente_id = c.id)"),
    (
        "outer_join_oracle",
        {"oracle": f"SELECT c.nombre, p.id AS pedido FROM {C} c, {P} p WHERE p.cliente_id (+) = c.id"},
    ),
    ("ilike", {"postgresql": f"SELECT id FROM {C} WHERE nombre ILIKE 'a%'"}),
    (
        "agregado_texto",
        _per(
            f"SELECT cliente_id, GROUP_CONCAT(id ORDER BY id SEPARATOR ',') AS ids FROM {P} GROUP BY cliente_id",
            None,
            None,
            f"SELECT cliente_id, LISTAGG(id, ',') WITHIN GROUP (ORDER BY id) AS ids FROM {P} GROUP BY cliente_id",
        ),
    ),
    ("cabecera_columnas", {"sqlserver": f"(codigo, texto) AS SELECT id, nombre FROM {C}"}),
    (
        "jerarquia",
        {
            "oracle": f"SELECT e.id, e.nombre, LEVEL AS nivel FROM {E} e WHERE e.activo = 1 "
            "START WITH e.jefe_id IS NULL CONNECT BY PRIOR e.id = e.jefe_id"
        },
    ),
    (
        "jerarquia_ruta",
        {
            "oracle": f"SELECT id, SYS_CONNECT_BY_PATH(nombre, '/') AS ruta, CONNECT_BY_ROOT nombre AS raiz FROM {E} "
            "START WITH jefe_id IS NULL CONNECT BY jefe_id = PRIOR id"
        },
    ),
    ("generador", {"oracle": "SELECT LEVEL AS n FROM dual CONNECT BY LEVEL <= 5"}),
]


# ─── Conexiones y espacios de nombres ────────────────────────────────────────────


def _base_url(engine_name: str) -> URL:
    return make_url(os.environ[URL_ENV[engine_name]])


def _url(engine_name: str, namespace: str) -> URL:
    url = _base_url(engine_name)
    if engine_name in ("mysql", "mariadb", "sqlserver"):
        return url.set(database=namespace)
    return url


def _engine(engine_name: str, namespace: str | None, *, autocommit: bool = True) -> Engine:
    kwargs: dict[str, Any] = {"isolation_level": "AUTOCOMMIT"} if autocommit else {}
    if engine_name == "postgresql" and namespace:
        kwargs["connect_args"] = {"options": f"-c search_path={namespace}"}
    url = _url(engine_name, namespace) if namespace else _base_url(engine_name)
    if engine_name == "sqlserver" and not namespace:
        url = url.set(database="master")
    return create_engine(url, **kwargs)


def _run(engine_name: str, namespace: str | None, statements: list[str], ignore: bool = False) -> None:
    eng = _engine(engine_name, namespace)
    try:
        with eng.connect() as conn:
            for statement in statements:
                cursor = conn.connection.dbapi_connection.cursor()
                try:
                    cursor.execute(statement)
                except Exception:
                    if not ignore:
                        raise
                finally:
                    cursor.close()
    finally:
        eng.dispose()


def _drop_namespace(engine_name: str, namespace: str) -> None:
    if engine_name in ("mysql", "mariadb"):
        _run(engine_name, None, [f"DROP DATABASE IF EXISTS {namespace}"], ignore=True)
    elif engine_name == "postgresql":
        _run(engine_name, None, [f"DROP SCHEMA IF EXISTS {namespace} CASCADE"], ignore=True)
    elif engine_name == "sqlserver":
        _run(
            engine_name,
            None,
            [
                f"IF DB_ID('{namespace}') IS NOT NULL BEGIN ALTER DATABASE {namespace} SET SINGLE_USER WITH ROLLBACK "
                f"IMMEDIATE; DROP DATABASE {namespace}; END"
            ],
            ignore=True,
        )
    else:
        _run(
            engine_name,
            None,
            [
                "BEGIN FOR v IN (SELECT view_name FROM user_views WHERE view_name LIKE 'ZZVW%') LOOP "
                "EXECUTE IMMEDIATE 'DROP VIEW \"' || v.view_name || '\"'; END LOOP; END;",
                "BEGIN FOR t IN (SELECT table_name FROM user_tables WHERE table_name LIKE 'ZZVW%') LOOP "
                "EXECUTE IMMEDIATE 'DROP TABLE \"' || t.table_name || '\" CASCADE CONSTRAINTS'; END LOOP; END;",
                "BEGIN FOR q IN (SELECT sequence_name FROM user_sequences WHERE sequence_name LIKE 'ZZVW%') LOOP "
                "EXECUTE IMMEDIATE 'DROP SEQUENCE \"' || q.sequence_name || '\"'; END LOOP; END;",
            ],
        )


def _create_namespace(engine_name: str, namespace: str) -> None:
    _drop_namespace(engine_name, namespace)
    if engine_name in ("mysql", "mariadb", "sqlserver"):
        _run(engine_name, None, [f"CREATE DATABASE {namespace}"])
    elif engine_name == "postgresql":
        _run(engine_name, None, [f"CREATE SCHEMA {namespace}"])


def _source_objects(engine_name: str) -> list[str]:
    if engine_name == "oracle":
        i, v, d, n = "NUMBER(10)", "VARCHAR2(50)", "DATE", "NUMBER(10,2)"
    else:
        i, v, d, n = "INT", "VARCHAR(50)", "DATE", "DECIMAL(10,2)"
    date = (lambda x: f"CAST('{x}' AS DATE)") if engine_name == "sqlserver" else (lambda x: f"DATE '{x}'")
    text = lambda x: "NULL" if x is None else f"'{x}'"  # noqa: E731
    statements = [
        f"CREATE TABLE {C} (id {i} PRIMARY KEY, nombre {v} NOT NULL, ciudad {v}, alta {d}, saldo {n})",
        f"CREATE TABLE {P} (id {i} PRIMARY KEY, cliente_id {i}, fecha {d}, importe {n})",
    ]
    statements += [f"INSERT INTO {C} VALUES ({a}, '{b}', {text(c)}, {date(e)}, {f})" for a, b, c, e, f in CLIENTES]
    statements += [f"INSERT INTO {P} VALUES ({a}, {b}, {date(c)}, {e})" for a, b, c, e in PEDIDOS]
    statements.append(f"CREATE TABLE {E} (id {i} PRIMARY KEY, nombre {v} NOT NULL, jefe_id {i}, activo {i})")
    ruta = RUTA_LITERAL.get(engine_name, "'C:\\datos\\x''q'")
    comment = f" COMMENT {ruta}" if engine_name in ("mysql", "mariadb") else ""
    statements.append(
        f"CREATE TABLE {A} ({AUTOINC_ID[engine_name]}, v {i}, ruta {v.replace('50', '80')} DEFAULT {ruta}{comment})"
    )
    if engine_name in ("postgresql", "oracle"):
        statements.append(f"COMMENT ON COLUMN {A}.ruta IS {ruta}")
    if engine_name in ("mysql", "mariadb", "sqlserver"):
        # A3 (hotfix): mismo nombre de índice en dos tablas (válido aquí; en PostgreSQL y Oracle es único por schema).
        statements += [f"CREATE INDEX zzvw_idx ON {E} (activo)", f"CREATE INDEX zzvw_idx ON {A} (v)"]
    statements += [
        f"INSERT INTO {E} VALUES ({emp}, '{name}', {'NULL' if boss is None else boss}, {active})"
        for emp, name, boss, active in EMPLEADOS
    ]
    for key, sql in CORPUS:
        native = sql if isinstance(sql, str) else sql.get(engine_name)
        if native:
            statements.append(
                f"CREATE VIEW zzvw_{key} {native}" if native.startswith("(") else f"CREATE VIEW zzvw_{key} AS {native}"
            )
    return statements


def _manager(engine_name: str, namespace: str = SRC) -> SyncDatabaseManager:
    url = _url(engine_name, namespace)
    params: dict[str, Any] = {"host": url.host, "port": url.port, "user": url.username, "password": url.password}
    if engine_name == "oracle":
        params["service_name"] = url.query.get("service_name")
    else:
        params["database"] = url.database if engine_name != "postgresql" else _base_url(engine_name).database
    return SyncDatabaseManager(engine_name, params, use_pool=False)


def _source_schema(engine_name: str) -> str:
    return {"sqlserver": "dbo", "oracle": str(_base_url("oracle").username).upper()}.get(engine_name, SRC)


# ─── Comparación ─────────────────────────────────────────────────────────────────


def _norm(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return str(Decimal(str(value)).quantize(Decimal("0.01")))
    if isinstance(value, dt.datetime):
        return value.date().isoformat() if value.time() == dt.time(0) else value.isoformat(sep=" ")
    if isinstance(value, dt.date):
        return value.isoformat()
    return str(value).rstrip()


def _rows(engine: Engine, sql: str) -> list[tuple]:
    with engine.connect() as conn:
        rows = conn.exec_driver_sql(sql).fetchall()
    return sorted(
        (tuple(_norm(v) for v in r) for r in rows), key=lambda r: tuple("" if x is None else str(x) for x in r)
    )


QUOTE = {
    "mysql": lambda n: f"`{n}`",
    "mariadb": lambda n: f"`{n}`",
    "postgresql": lambda n: f'"{n}"',
    "sqlserver": lambda n: f"[{n}]",
    "oracle": lambda n: f'"{n.upper()}"',
}


@pytest.fixture
def source_target(request: pytest.FixtureRequest) -> Iterator[tuple[str, str]]:
    source, target = request.param
    _create_namespace(source, SRC)
    _create_namespace(target, DST)
    try:
        _run(source, SRC, _source_objects(source))
        yield source, target
    finally:
        _drop_namespace(source, SRC)
        _drop_namespace(target, DST)


PAIRS = [(s, t) for s in ENGINES for t in ENGINES if s != t]


@pytest.mark.parametrize("source_target", PAIRS, indirect=True, ids=[f"{s}-{t}" for s, t in PAIRS])
def test_views_are_created_and_return_the_same_rows(source_target: tuple[str, str]) -> None:
    source, target = source_target
    manager = _manager(source)
    try:
        plan = MigrationPlanner(
            source_engine=source,
            target_engine=target,
            view_strategy="transpile",
            pg_schema=DST if target == "postgresql" else None,
        ).plan(manager, _source_schema(source))
    finally:
        manager.close()
    # Solo los objetos del test (el schema del usuario Oracle puede tener otros).
    plan.tables = [t for t in plan.tables if t.original_name.lower().startswith("zzvw_")]
    plan.views = [v for v in plan.views if v.original_name.lower().startswith("zzvw_")]
    expected_views = {v.original_name.lower() for v in plan.views}
    assert len(expected_views) == sum(1 for _, sql in CORPUS if isinstance(sql, str) or source in sql)

    if target in ("postgresql", "sqlserver"):
        # validate_views crea tablas y vistas en una transacción que deshace: todo válido y el destino sigue vacío.
        validation_engine = _engine(target, DST, autocommit=False)
        try:
            results = plan.validate_views(validation_engine)
            assert {r.view.lower() for r in results if r.valid and r.method == "transaction"} == {
                v.name.lower() for v in plan.views
            }, [r for r in results if not r.valid]
            with validation_engine.connect() as conn:
                leftovers = conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables WHERE table_name LIKE :prefix"
                        + (f" AND table_schema = '{DST}'" if target == "postgresql" else "")
                    ),
                    {"prefix": "zzvw%"},
                ).fetchall()
            assert not leftovers
        finally:
            validation_engine.dispose()

    # A1 (hotfix): el plan se aplica con su propia API, por una conexión del manager destino.
    target_manager = _manager(target, DST)
    try:
        plan.execute(target_manager)
    finally:
        target_manager.close()

    src_engine, dst_engine = _engine(source, SRC), _engine(target, DST)
    try:
        src_meta, dst_meta = MetaData(), MetaData()
        for table in plan.tables:
            src_name = table.original_name.lower() if source == "oracle" else table.original_name
            dst_name = table.name.lower() if target == "oracle" else table.name
            src_table = Table(src_name, src_meta, autoload_with=src_engine)
            dst_table = Table(dst_name, dst_meta, autoload_with=dst_engine)
            with src_engine.connect() as conn:
                rows = conn.execute(select(src_table)).fetchall()
            columns = [c.name for c in dst_table.columns]
            if not rows:
                continue
            with dst_engine.begin() as conn:
                conn.execute(dst_table.insert(), [dict(zip(columns, row, strict=True)) for row in rows])

        # A2 (hotfix): el id autoincremental migrado se genera en el destino (Oracle: SEQUENCE + TRIGGER válido).
        autoinc = [t for t in plan.tables if t.original_name.lower() == A]
        auto_cols = [c for t in autoinc for c in t.columns if c.auto_increment]
        if auto_cols:
            table_name, value_col = autoinc[0].name, next(c.name for c in autoinc[0].columns if not c.auto_increment)
            with dst_engine.begin() as conn:
                conn.exec_driver_sql(f"INSERT INTO {QUOTE[target](table_name)} ({QUOTE[target](value_col)}) VALUES (7)")
            ruta_col = next(c.name for c in autoinc[0].columns if c.original_name.lower() == "ruta")
            generated = _rows(
                dst_engine,
                f"SELECT {QUOTE[target](auto_cols[0].name)}, {QUOTE[target](ruta_col)} FROM {QUOTE[target](table_name)}",
            )
            assert generated == [("1.00", RUTA)], generated  # A4: el DEFAULT conserva barras y comilla
            # Comentarios: los extractores de SQL Server y PostgreSQL no los leen (limitación documentada, v1).
            if target in ("mysql", "mariadb") and source in ("mysql", "mariadb", "oracle"):
                comment = _rows(
                    dst_engine,
                    "SELECT COLUMN_COMMENT FROM information_schema.COLUMNS "
                    f"WHERE TABLE_SCHEMA = '{DST}' AND TABLE_NAME = '{table_name}' AND COLUMN_NAME = '{ruta_col}'",
                )
                assert comment == [(RUTA,)], comment
        else:
            assert source == "oracle", f"{source}: la columna autoincremental no se detectó"

        differences: dict[str, tuple[list[tuple], list[tuple]]] = {}
        for view in plan.views:
            assert any(w.target_type == "VIEW (reescrita)" for w in view.warnings), f"{view.name} sin reescribir"
            source_rows = _rows(src_engine, f"SELECT * FROM {view.original_name}")
            target_rows = _rows(dst_engine, f"SELECT * FROM {QUOTE[target](view.name)}")
            if source_rows != target_rows:
                differences[view.original_name] = (source_rows, target_rows)
        assert not differences, differences
    finally:
        src_engine.dispose()
        dst_engine.dispose()
