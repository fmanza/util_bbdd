"""V0 (sesión 2026-09-29c-migrate-views): ¿transpila sqlglot las vistas de migrate entre los 5 motores?

Para cada motor origen: crea tablas base + datos idénticos y un corpus de vistas en su dialecto nativo; lee la
definición de cada vista del catálogo con los extractores de util_bbdd (el texto que usaría migrate); la transpila a
los otros 4 motores con la normalización AST prevista para V1 (sin esquema, identificadores sin comillas); la crea en
el destino y compara su resultado con el del origen.

Uso: BENCH_PW=... python v0_spike_views.py [ruta_json_salida]
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import sys
import traceback

from decimal import Decimal
from typing import Any
from urllib.parse import quote_plus

import sqlglot

from sqlalchemy import create_engine
from sqlglot import exp
from sqlglot.errors import ErrorLevel

from util_bbdd import SyncDatabaseManager
from util_bbdd.migrate.extractors.mariadb import MariaDBSchemaExtractor
from util_bbdd.migrate.extractors.oracle import OracleSchemaExtractor
from util_bbdd.migrate.extractors.postgresql import PostgreSQLSchemaExtractor
from util_bbdd.migrate.extractors.sqlserver import SQLServerSchemaExtractor

logging.basicConfig(level=logging.CRITICAL)
PW = os.environ["BENCH_PW"]
QPW = quote_plus(PW)
H = "127.0.0.1"
ENGINES = ["mysql", "mariadb", "postgresql", "sqlserver", "oracle"]
DIALECT = {"mysql": "mysql", "mariadb": "mysql", "postgresql": "postgres", "sqlserver": "tsql", "oracle": "oracle"}

URL = {
    "mysql": f"mysql+pymysql://root:{QPW}@{H}:53306/zzv",
    "mariadb": f"mysql+pymysql://root:{QPW}@{H}:53307/zzv",
    "postgresql": f"postgresql+psycopg://bench:{QPW}@{H}:55432/bench",
    "sqlserver": f"mssql+pymssql://sa:{QPW}@{H}:51433/zzv",
    "oracle": f"oracle+oracledb://bench:{QPW}@{H}:51521/?service_name=FREEPDB1",
}
ADMIN_URL = {
    "mysql": f"mysql+pymysql://root:{QPW}@{H}:53306/",
    "mariadb": f"mysql+pymysql://root:{QPW}@{H}:53307/",
    "sqlserver": f"mssql+pymssql://sa:{QPW}@{H}:51433/master",
}


def engine(kind: str, admin: bool = False):
    url = ADMIN_URL[kind] if admin else URL[kind]
    kwargs: dict[str, Any] = {"isolation_level": "AUTOCOMMIT"}
    if kind == "postgresql" and not admin:
        kwargs["connect_args"] = {"options": "-c search_path=zzv"}
    return create_engine(url, **kwargs)


def execute(kind: str, stmts: list[str], ignore: bool = False, admin: bool = False) -> None:
    eng = engine(kind, admin)
    try:
        with eng.connect() as conn:
            for stmt in stmts:
                # exec_driver_sql pasa el SQL por el formateo de parámetros del driver en PyMySQL y psycopg.
                if kind in ("mysql", "mariadb", "postgresql"):
                    stmt = stmt.replace("%", "%%")
                try:
                    conn.exec_driver_sql(stmt)
                except Exception:
                    if not ignore:
                        raise
    finally:
        eng.dispose()


def fetch(conn: Any, sql: str) -> list[tuple]:
    return [tuple(r) for r in conn.exec_driver_sql(sql).fetchall()]


# ─── Datos base ──────────────────────────────────────────────────────────────────

CLIENTES = [
    (1, "Ana", "Madrid", "2024-01-10", "100.50", 1),
    (2, "Luis", None, "2024-02-20", "0.00", 0),
    (3, "Eva", "Sevilla", "2023-12-01", "250.00", 1),
    (4, "Juan", "Madrid", "2024-03-05", "-20.25", 1),
    (5, "Sara", "", "2024-01-31", "75.00", 0),
]
PEDIDOS = [
    (1, 1, "2024-01-15", "30.00"),
    (2, 1, "2024-02-01", "45.50"),
    (3, 3, "2024-01-20", "120.00"),
    (4, 4, "2024-03-10", "5.25"),
    (5, 3, "2024-02-28", "80.00"),
    (6, 1, "2024-03-01", "12.00"),
]


def base_ddl(kind: str) -> list[str]:
    if kind == "oracle":
        types = ("NUMBER(10)", "VARCHAR2(50)", "DATE", "NUMBER(10,2)", "NUMBER(5)")
    else:
        types = ("INT", "VARCHAR(50)", "DATE", "DECIMAL(10,2)", "SMALLINT")
    i, v, d, n, s = types
    date = (lambda x: f"CAST('{x}' AS DATE)") if kind == "sqlserver" else (lambda x: f"DATE '{x}'")
    lit = lambda x: "NULL" if x is None else f"'{x}'"  # noqa: E731
    stmts = [
        f"CREATE TABLE zzv_clientes (id {i} PRIMARY KEY, nombre {v} NOT NULL, ciudad {v}, alta {d}, saldo {n}, "
        f"activo {s})",
        f"CREATE TABLE zzv_pedidos (id {i} PRIMARY KEY, cliente_id {i}, fecha {d}, importe {n})",
    ]
    stmts += [
        f"INSERT INTO zzv_clientes VALUES ({a}, '{b}', {lit(c)}, {date(e)}, {f}, {g})" for a, b, c, e, f, g in CLIENTES
    ]
    stmts += [f"INSERT INTO zzv_pedidos VALUES ({a}, {b}, {date(c)}, {e})" for a, b, c, e in PEDIDOS]
    return stmts


def setup_namespace(kind: str) -> None:
    if kind in ("mysql", "mariadb"):
        execute(kind, ["DROP DATABASE IF EXISTS zzv", "CREATE DATABASE zzv"], admin=True)
    elif kind == "sqlserver":
        execute(kind, [DROP_SS, "CREATE DATABASE zzv"], admin=True)
    elif kind == "postgresql":
        execute(kind, ["DROP SCHEMA IF EXISTS zzv CASCADE", "CREATE SCHEMA zzv"])
    else:
        cleanup_oracle()
    execute(kind, base_ddl(kind))


DROP_SS = (
    "IF DB_ID('zzv') IS NOT NULL BEGIN ALTER DATABASE zzv SET SINGLE_USER WITH ROLLBACK IMMEDIATE; "
    "DROP DATABASE zzv; END"
)


def cleanup_oracle() -> None:
    execute(
        "oracle",
        [
            "BEGIN FOR v IN (SELECT view_name FROM user_views WHERE view_name LIKE 'ZZV%') LOOP "
            "EXECUTE IMMEDIATE 'DROP VIEW \"' || v.view_name || '\"'; END LOOP; END;",
            "BEGIN FOR t IN (SELECT table_name FROM user_tables WHERE table_name LIKE 'ZZV%') LOOP "
            "EXECUTE IMMEDIATE 'DROP TABLE \"' || t.table_name || '\" CASCADE CONSTRAINTS'; END LOOP; END;",
        ],
    )


def teardown_namespace(kind: str) -> None:
    if kind in ("mysql", "mariadb"):
        execute(kind, ["DROP DATABASE IF EXISTS zzv"], admin=True, ignore=True)
    elif kind == "sqlserver":
        execute(kind, [DROP_SS], admin=True, ignore=True)
    elif kind == "postgresql":
        execute(kind, ["DROP SCHEMA IF EXISTS zzv CASCADE"], ignore=True)
    else:
        cleanup_oracle()


# ─── Corpus ──────────────────────────────────────────────────────────────────────
# (clave, tipo, sql común | {motor: sql}); tipo: "comun" cuenta para el umbral, "especifica" no.

C = "zzv_clientes"
P = "zzv_pedidos"
MY = ("mysql", "mariadb")


def per(mysql: str | None, pg: str | None, ss: str | None, ora: str | None) -> dict[str, str]:
    out = {"postgresql": pg, "sqlserver": ss, "oracle": ora, "mysql": mysql, "mariadb": mysql}
    return {k: v for k, v in out.items() if v is not None}


CORPUS: list[tuple[str, str, Any]] = [
    ("c01_proyeccion", "comun", f"SELECT id, nombre FROM {C}"),
    ("c02_where_and_or", "comun", f"SELECT id, nombre FROM {C} WHERE (saldo > 0 AND activo = 1) OR ciudad = 'Madrid'"),
    ("c03_inner_join", "comun", f"SELECT c.nombre, p.importe FROM {C} c INNER JOIN {P} p ON p.cliente_id = c.id"),
    ("c04_left_join", "comun", f"SELECT c.nombre, p.id AS pedido FROM {C} c LEFT JOIN {P} p ON p.cliente_id = c.id"),
    (
        "c05_group_agregados",
        "comun",
        f"SELECT cliente_id, COUNT(*) AS n, SUM(importe) AS total, AVG(importe) AS media, MIN(fecha) AS primera, "
        f"MAX(fecha) AS ultima FROM {P} GROUP BY cliente_id",
    ),
    ("c06_having", "comun", f"SELECT cliente_id, SUM(importe) AS total FROM {P} GROUP BY cliente_id HAVING SUM(importe) > 50"),
    (
        "c07_case",
        "comun",
        f"SELECT id, CASE WHEN saldo > 100 THEN 'alto' WHEN saldo > 0 THEN 'medio' ELSE 'bajo' END AS nivel FROM {C}",
    ),
    ("c08_coalesce", "comun", f"SELECT id, COALESCE(ciudad, 'desconocida') AS ciudad FROM {C}"),
    (
        "c09_nulos_dialecto",
        "comun",
        per(
            f"SELECT id, IFNULL(ciudad, 'x') AS ciudad FROM {C}",
            f"SELECT id, COALESCE(ciudad, 'x') AS ciudad FROM {C}",
            f"SELECT id, ISNULL(ciudad, 'x') AS ciudad FROM {C}",
            f"SELECT id, NVL(ciudad, 'x') AS ciudad FROM {C}",
        ),
    ),
    (
        "c10_concatenacion",
        "comun",
        per(
            f"SELECT id, CONCAT(nombre, ' - ', ciudad) AS etiqueta FROM {C}",
            f"SELECT id, nombre || ' - ' || ciudad AS etiqueta FROM {C}",
            f"SELECT id, nombre + ' - ' + ciudad AS etiqueta FROM {C}",
            f"SELECT id, nombre || ' - ' || ciudad AS etiqueta FROM {C}",
        ),
    ),
    ("c11_upper_lower_trim", "comun", f"SELECT id, UPPER(nombre) AS u, LOWER(nombre) AS l, TRIM(nombre) AS t FROM {C}"),
    (
        "c12_substring",
        "comun",
        per(
            f"SELECT id, SUBSTRING(nombre, 1, 2) AS ini FROM {C}",
            f"SELECT id, SUBSTRING(nombre FROM 1 FOR 2) AS ini FROM {C}",
            f"SELECT id, SUBSTRING(nombre, 1, 2) AS ini FROM {C}",
            f"SELECT id, SUBSTR(nombre, 1, 2) AS ini FROM {C}",
        ),
    ),
    (
        "c13_longitud",
        "comun",
        per(
            f"SELECT id, CHAR_LENGTH(nombre) AS n FROM {C}",
            f"SELECT id, LENGTH(nombre) AS n FROM {C}",
            f"SELECT id, LEN(nombre) AS n FROM {C}",
            f"SELECT id, LENGTH(nombre) AS n FROM {C}",
        ),
    ),
    (
        "c14_anio",
        "comun",
        per(
            f"SELECT id, YEAR(alta) AS anio FROM {C}",
            f"SELECT id, EXTRACT(YEAR FROM alta) AS anio FROM {C}",
            f"SELECT id, YEAR(alta) AS anio FROM {C}",
            f"SELECT id, EXTRACT(YEAR FROM alta) AS anio FROM {C}",
        ),
    ),
    (
        "c15_sumar_dias",
        "comun",
        per(
            f"SELECT id, DATE_ADD(alta, INTERVAL 30 DAY) AS vence FROM {C}",
            f"SELECT id, alta + 30 AS vence FROM {C}",
            f"SELECT id, DATEADD(day, 30, alta) AS vence FROM {C}",
            f"SELECT id, alta + 30 AS vence FROM {C}",
        ),
    ),
    (
        "c16_diferencia_dias",
        "comun",
        per(
            f"SELECT p.id, DATEDIFF(p.fecha, c.alta) AS dias FROM {P} p JOIN {C} c ON c.id = p.cliente_id",
            f"SELECT p.id, p.fecha - c.alta AS dias FROM {P} p JOIN {C} c ON c.id = p.cliente_id",
            f"SELECT p.id, DATEDIFF(day, c.alta, p.fecha) AS dias FROM {P} p JOIN {C} c ON c.id = p.cliente_id",
            f"SELECT p.id, p.fecha - c.alta AS dias FROM {P} p JOIN {C} c ON c.id = p.cliente_id",
        ),
    ),
    (
        "c17_cast_texto",
        "comun",
        per(
            f"SELECT CAST(id AS CHAR(10)) AS t FROM {C}",
            f"SELECT CAST(id AS VARCHAR(10)) AS t FROM {C}",
            f"SELECT CAST(id AS VARCHAR(10)) AS t FROM {C}",
            f"SELECT CAST(id AS VARCHAR2(10)) AS t FROM {C}",
        ),
    ),
    (
        "c18_aritmetica",
        "comun",
        f"SELECT id, ROUND(saldo * 1.21, 2) AS con_iva, ABS(saldo) AS absoluto, saldo / 4 AS cuarto FROM {C}",
    ),
    ("c19_in_subconsulta", "comun", f"SELECT id, nombre FROM {C} WHERE id IN (SELECT cliente_id FROM {P})"),
    (
        "c20_exists",
        "comun",
        f"SELECT c.id FROM {C} c WHERE EXISTS (SELECT 1 FROM {P} p WHERE p.cliente_id = c.id)",
    ),
    (
        "c21_tabla_derivada",
        "comun",
        f"SELECT t.cliente_id, t.total FROM (SELECT cliente_id, SUM(importe) AS total FROM {P} GROUP BY cliente_id) t "
        "WHERE t.total > 10",
    ),
    (
        "c22_union_all",
        "comun",
        f"SELECT id, nombre FROM {C} WHERE activo = 1 UNION ALL SELECT id, nombre FROM {C} WHERE activo = 0",
    ),
    ("c23_distinct", "comun", f"SELECT DISTINCT ciudad FROM {C}"),
    (
        "c24_cte",
        "comun",
        f"WITH t AS (SELECT cliente_id, SUM(importe) AS total FROM {P} GROUP BY cliente_id) SELECT cliente_id, total FROM t",
    ),
    (
        "c25_ventana",
        "comun",
        f"SELECT id, cliente_id, ROW_NUMBER() OVER (PARTITION BY cliente_id ORDER BY fecha, id) AS rn FROM {P}",
    ),
    (
        "c26_top_n",
        "comun",
        per(
            f"SELECT id, importe FROM {P} ORDER BY importe DESC LIMIT 3",
            f"SELECT id, importe FROM {P} ORDER BY importe DESC LIMIT 3",
            f"SELECT TOP 3 id, importe FROM {P} ORDER BY importe DESC",
            f"SELECT id, importe FROM {P} ORDER BY importe DESC FETCH FIRST 3 ROWS ONLY",
        ),
    ),
    ("c27_like", "comun", f"SELECT id FROM {C} WHERE nombre LIKE 'A%'"),
    ("c28_between", "comun", f"SELECT id FROM {C} WHERE saldo BETWEEN 0 AND 200"),
    ("c29_is_null", "comun", f"SELECT id FROM {C} WHERE ciudad IS NULL"),
    ("c30_select_star", "comun", f"SELECT * FROM {P}"),
    (
        "c31_subconsulta_escalar",
        "comun",
        f"SELECT c.id, (SELECT COUNT(*) FROM {P} p WHERE p.cliente_id = c.id) AS n FROM {C} c",
    ),
    # Específicas de dialecto (no cuentan para el umbral)
    (
        "e01_condicional_dialecto",
        "especifica",
        per(
            f"SELECT id, IF(activo = 1, 'si', 'no') AS a FROM {C}",
            None,
            f"SELECT id, IIF(activo = 1, 'si', 'no') AS a FROM {C}",
            f"SELECT id, DECODE(activo, 1, 'si', 'no') AS a FROM {C}",
        ),
    ),
    ("e02_rownum", "especifica", {"oracle": f"SELECT id FROM {C} WHERE ROWNUM <= 3"}),
    (
        "e03_outer_join_oracle",
        "especifica",
        {"oracle": f"SELECT c.nombre, p.id AS pedido FROM {C} c, {P} p WHERE p.cliente_id (+) = c.id"},
    ),
    ("e04_ilike", "especifica", {"postgresql": f"SELECT id FROM {C} WHERE nombre ILIKE 'a%'"}),
    (
        "e05_agregado_texto",
        "especifica",
        per(
            f"SELECT cliente_id, GROUP_CONCAT(id ORDER BY id SEPARATOR ',') AS ids FROM {P} GROUP BY cliente_id",
            f"SELECT cliente_id, STRING_AGG(CAST(id AS VARCHAR), ',' ORDER BY id) AS ids FROM {P} GROUP BY cliente_id",
            f"SELECT cliente_id, STRING_AGG(CAST(id AS VARCHAR(10)), ',') WITHIN GROUP (ORDER BY id) AS ids FROM {P} "
            "GROUP BY cliente_id",
            f"SELECT cliente_id, LISTAGG(id, ',') WITHIN GROUP (ORDER BY id) AS ids FROM {P} GROUP BY cliente_id",
        ),
    ),
    ("e06_connect_by", "especifica", {"oracle": "SELECT LEVEL AS n FROM DUAL CONNECT BY LEVEL <= 3"}),
    ("e07_cast_pg", "especifica", {"postgresql": f"SELECT id::text AS t FROM {C}"}),
]


# ─── Extracción del catálogo (lo que ve migrate) ─────────────────────────────────


def manager(kind: str) -> SyncDatabaseManager:
    params = {
        "mysql": {"host": H, "port": 53306, "user": "root", "password": PW, "database": "zzv"},
        "mariadb": {"host": H, "port": 53307, "user": "root", "password": PW, "database": "zzv"},
        "postgresql": {"host": H, "port": 55432, "user": "bench", "password": PW, "database": "bench"},
        "sqlserver": {"host": H, "port": 51433, "user": "sa", "password": PW, "database": "zzv"},
        "oracle": {"host": H, "port": 51521, "user": "bench", "password": PW, "service_name": "FREEPDB1"},
    }[kind]
    return SyncDatabaseManager(kind, params, use_pool=(kind == "postgresql"))


def catalog_definitions(kind: str) -> dict[str, str]:
    extractor_cls, schema = {
        "mysql": (MariaDBSchemaExtractor, "zzv"),
        "mariadb": (MariaDBSchemaExtractor, "zzv"),
        "postgresql": (PostgreSQLSchemaExtractor, "zzv"),
        "sqlserver": (SQLServerSchemaExtractor, "dbo"),
        "oracle": (OracleSchemaExtractor, "BENCH"),
    }[kind]
    m = manager(kind)
    try:
        views = extractor_cls(m).extract_views(schema)
    finally:
        m.close()
    return {v.name.lower(): v.query for v in views if v.name.lower().startswith("zzv_v_")}


# ─── Transpilado (normalización AST prevista para V1) ────────────────────────────


def transpile(sql: str, source: str, target: str) -> tuple[str, list[str]]:
    """Devuelve (sql destino, construcciones que sqlglot declara no soportadas)."""
    tree = sqlglot.parse_one(sql.strip().rstrip(";"), read=DIALECT[source])
    for node in tree.find_all(exp.Table, exp.Column):
        node.set("db", None)
        node.set("catalog", None)
    for ident in tree.find_all(exp.Identifier):
        ident.set("quoted", False)
        if target in MY:
            ident.set("this", ident.name.lower())
    unsupported: list[str] = []
    try:
        tree.sql(dialect=DIALECT[target], unsupported_level=ErrorLevel.RAISE)
    except Exception as err:  # noqa: BLE001
        unsupported.append(str(err).splitlines()[0][:140])
    return tree.sql(dialect=DIALECT[target], unsupported_level=ErrorLevel.IGNORE), unsupported


# ─── Comparación de resultados ───────────────────────────────────────────────────


def norm(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, Decimal)):
        return str(Decimal(str(value)).quantize(Decimal("0.01")))
    if isinstance(value, dt.datetime):
        return value.date().isoformat() if value.time() == dt.time(0) else value.isoformat(sep=" ")
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, dt.timedelta):
        return str(Decimal(value.days).quantize(Decimal("0.01")))
    return str(value).rstrip()


def rows_of(kind: str, view: str) -> list[tuple]:
    eng = engine(kind)
    try:
        with eng.connect() as conn:
            rows = fetch(conn, f"SELECT * FROM {view}")
    finally:
        eng.dispose()
    return sorted((tuple(norm(v) for v in r) for r in rows), key=lambda r: tuple("" if x is None else str(x) for x in r))


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else None
    for kind in ENGINES:
        setup_namespace(kind)
    results: list[dict[str, Any]] = []
    try:
        for source in ENGINES:
            created: list[str] = []
            for key, kind_, sql in CORPUS:
                native = sql if isinstance(sql, str) else sql.get(source)
                if native is None:
                    continue
                view = f"zzv_v_{key}"
                try:
                    execute(source, [f"CREATE VIEW {view} AS {native}"])
                    created.append(key)
                except Exception as err:  # noqa: BLE001
                    results.append(
                        {"source": source, "target": None, "view": key, "kind": kind_, "status": "origen_falla",
                         "detail": str(err).splitlines()[0][:200]}
                    )
            definitions = catalog_definitions(source)
            expected = {key: rows_of(source, f"zzv_v_{key}") for key in created}
            for target in ENGINES:
                if target == source:
                    continue
                for key in created:
                    kind_ = next(k for c, k, _ in CORPUS if c == key)
                    definition = definitions.get(f"zzv_v_{key}")
                    record: dict[str, Any] = {"source": source, "target": target, "view": key, "kind": kind_}
                    if not definition:
                        record.update(status="sin_definicion", detail="")
                        results.append(record)
                        continue
                    try:
                        target_sql, unsupported = transpile(definition, source, target)
                    except Exception as err:  # noqa: BLE001
                        record.update(status="parse_falla", detail=str(err).splitlines()[0][:200])
                        results.append(record)
                        continue
                    record["unsupported"] = unsupported
                    record["sql"] = target_sql
                    tview = "zzv_t"
                    try:
                        execute(target, [f"CREATE VIEW {tview} AS {target_sql}"])
                    except Exception as err:  # noqa: BLE001
                        record.update(status="crear_falla", detail=str(err).splitlines()[0][:220])
                        results.append(record)
                        continue
                    try:
                        got = rows_of(target, tview)
                        record["status"] = "ok" if got == expected[key] else "resultado_distinto"
                        if got != expected[key]:
                            record["detail"] = f"origen={expected[key][:3]} destino={got[:3]}"
                    except Exception as err:  # noqa: BLE001
                        record.update(status="select_falla", detail=str(err).splitlines()[0][:220])
                    finally:
                        execute(target, [f"DROP VIEW {tview}"], ignore=True)
                    results.append(record)
            execute(source, [f"DROP VIEW zzv_v_{key}" for key in created], ignore=True)
    except Exception:
        traceback.print_exc()
    finally:
        for kind in ENGINES:
            teardown_namespace(kind)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=1)
    summarize(results)


def summarize(results: list[dict[str, Any]]) -> None:
    pairs: dict[tuple[str, str], dict[str, int]] = {}
    for r in results:
        if r["target"] is None or r["kind"] != "comun":
            continue
        stats = pairs.setdefault((r["source"], r["target"]), {"total": 0, "ejecuta": 0, "igual": 0})
        stats["total"] += 1
        stats["ejecuta"] += r["status"] in ("ok", "resultado_distinto")
        stats["igual"] += r["status"] == "ok"
    print(f"{'par':<26}{'ejecuta':>12}{'mismo resultado':>18}")
    for (s, t), st in sorted(pairs.items()):
        print(f"{s + ' → ' + t:<26}{st['ejecuta']:>5}/{st['total']:<3} {100 * st['ejecuta'] / st['total']:>3.0f}%"
              f"{st['igual']:>9}/{st['total']:<3} {100 * st['igual'] / st['total']:>3.0f}%")
    origin = [r for r in results if r["status"] == "origen_falla"]
    if origin:
        print("\nVistas que no se pudieron crear en el origen:")
        for r in origin:
            print(f"  {r['source']} {r['view']}: {r['detail']}")


if __name__ == "__main__":
    main()
