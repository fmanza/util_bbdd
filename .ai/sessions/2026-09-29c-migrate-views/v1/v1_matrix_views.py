"""V1: matriz de 20 pares con MigrationPlanner (tablas + vistas del plan), datos copiados y resultados comparados.

Reutiliza el corpus y utilidades de v0_spike_views.py. Uso: BENCH_PW=... python v1_matrix_views.py <v0_spike.py> [salida.json]
"""

from __future__ import annotations

import importlib.util
import json
import sys
import traceback

from typing import Any

from sqlalchemy import MetaData, Table, create_engine, select

spec = importlib.util.spec_from_file_location("v0", sys.argv[1])
v0 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v0)

from util_bbdd.migrate import MigrationPlanner  # noqa: E402

# V2: casos adicionales (top-N de Oracle con subconsulta ordenada; cabecera con columnas en SQL Server).
v0.CORPUS += [
    ("e08_top_n_oracle", "especifica",
     {"oracle": f"SELECT * FROM (SELECT id, saldo FROM {v0.C} ORDER BY saldo DESC) WHERE ROWNUM <= 2"}),
    ("e09_cabecera_columnas", "especifica", {"sqlserver": f"(codigo, texto) AS SELECT id, nombre FROM {v0.C}"}),
]

ENGINES = v0.ENGINES
QPW, H = v0.QPW, v0.H
TARGET_URL = {
    "mysql": f"mysql+pymysql://root:{QPW}@{H}:53306/zzv_dst",
    "mariadb": f"mysql+pymysql://root:{QPW}@{H}:53307/zzv_dst",
    "postgresql": f"postgresql+psycopg://bench:{QPW}@{H}:55432/bench",
    "sqlserver": f"mssql+pymssql://sa:{QPW}@{H}:51433/zzv_dst",
    "oracle": f"oracle+oracledb://bench:{QPW}@{H}:51521/?service_name=FREEPDB1",
}
DROP_SS_DST = v0.DROP_SS.replace("zzv", "zzv_dst")


def target_engine(kind: str):
    kwargs: dict[str, Any] = {"isolation_level": "AUTOCOMMIT"}
    if kind == "postgresql":
        kwargs["connect_args"] = {"options": "-c search_path=zzv_dst"}
    return create_engine(TARGET_URL[kind], **kwargs)


def reset_target(kind: str) -> None:
    if kind in ("mysql", "mariadb"):
        v0.execute(kind, ["DROP DATABASE IF EXISTS zzv_dst", "CREATE DATABASE zzv_dst"], admin=True)
    elif kind == "sqlserver":
        v0.execute(kind, [DROP_SS_DST, "CREATE DATABASE zzv_dst"], admin=True)
    elif kind == "postgresql":
        v0.execute(kind, ["DROP SCHEMA IF EXISTS zzv_dst CASCADE", "CREATE SCHEMA zzv_dst"])
    else:
        v0.cleanup_oracle()


def drop_target(kind: str) -> None:
    if kind in ("mysql", "mariadb"):
        v0.execute(kind, ["DROP DATABASE IF EXISTS zzv_dst"], admin=True, ignore=True)
    elif kind == "sqlserver":
        v0.execute(kind, [DROP_SS_DST], admin=True, ignore=True)
    elif kind == "postgresql":
        v0.execute(kind, ["DROP SCHEMA IF EXISTS zzv_dst CASCADE"], ignore=True)
    else:
        v0.cleanup_oracle()


def run_target(kind: str, stmts: list[str]) -> dict[str, str]:
    """Ejecuta sentencia a sentencia; devuelve {primera línea: error} de las que fallan."""
    errors: dict[str, str] = {}
    eng = target_engine(kind)
    try:
        with eng.connect() as conn:
            for stmt in stmts:
                sql = stmt.replace("%", "%%") if kind in ("mysql", "mariadb", "postgresql") else stmt
                try:
                    conn.exec_driver_sql(sql)
                except Exception as err:  # noqa: BLE001
                    errors[stmt] = str(err).splitlines()[0][:200]
    finally:
        eng.dispose()
    return errors


def copy_data(source: str, target: str, table_names: dict[str, str]) -> None:
    """Copia las filas de las tablas base del origen a las tablas migradas (columnas por posición)."""
    src_eng, dst_eng = v0.engine(source), target_engine(target)
    try:
        src_meta, dst_meta = MetaData(), MetaData()
        for src_name, dst_name in table_names.items():
            # SQLAlchemy refleja los nombres de Oracle sin comillas (mayúsculas) en minúsculas.
            src_table = Table(src_name.lower() if source == "oracle" else src_name, src_meta, autoload_with=src_eng)
            dst_table = Table(dst_name.lower() if target == "oracle" else dst_name, dst_meta, autoload_with=dst_eng)
            with src_eng.connect() as conn:
                rows = conn.execute(select(src_table)).fetchall()
            dst_cols = [c.name for c in dst_table.columns]
            with dst_eng.begin() as conn:
                conn.execute(dst_table.insert(), [dict(zip(dst_cols, row, strict=True)) for row in rows])
    finally:
        src_eng.dispose()
        dst_eng.dispose()


def target_rows(kind: str, view_sql_name: str) -> list[tuple]:
    eng = target_engine(kind)
    try:
        with eng.connect() as conn:
            rows = conn.exec_driver_sql(f"SELECT * FROM {view_sql_name}").fetchall()
    finally:
        eng.dispose()
    return sorted((tuple(v0.norm(v) for v in r) for r in rows), key=lambda r: tuple("" if x is None else str(x) for x in r))


QUOTE = {
    "mysql": lambda n: f"`{n}`",
    "mariadb": lambda n: f"`{n}`",
    "postgresql": lambda n: f'"{n}"',
    "sqlserver": lambda n: f"[{n}]",
    "oracle": lambda n: f'"{n.upper()}"',
}
SOURCE_SCHEMA = {"mysql": "zzv", "mariadb": "zzv", "postgresql": "zzv", "sqlserver": "dbo", "oracle": "BENCH"}


def main() -> None:
    out_path = sys.argv[2] if len(sys.argv) > 2 else None
    results: list[dict[str, Any]] = []
    for source in ENGINES:
        v0.setup_namespace(source)
        try:
            created: list[str] = []
            for key, _kind, sql in v0.CORPUS:
                native = sql if isinstance(sql, str) else sql.get(source)
                if native is None:
                    continue
                header = native.startswith("(")  # la cabecera declara columnas: CREATE VIEW v (a, b) AS ...
                v0.execute(source, [f"CREATE VIEW zzv_v_{key} {native}" if header else f"CREATE VIEW zzv_v_{key} AS {native}"])
                created.append(key)
            expected = {key: v0.rows_of(source, f"zzv_v_{key}") for key in created}
            kinds = {key: k for key, k, _ in v0.CORPUS}
            for target in ENGINES:
                if target == source:
                    continue
                reset_target(target)
                try:
                    m = v0.manager(source)
                    try:
                        plan = MigrationPlanner(source_engine=source, target_engine=target).plan(m, SOURCE_SCHEMA[source])
                    finally:
                        m.close()
                    stmts = plan.emit_statements()
                    errors = run_target(target, stmts)
                    table_names = {t.original_name: t.name for t in plan.tables}
                    table_errors = [e for s, e in errors.items() if "CREATE TABLE" in s.upper()]
                    if table_errors:
                        results.append({"source": source, "target": target, "view": "*tablas*", "status": "tablas_falla",
                                        "detail": table_errors[0]})
                        continue
                    copy_data(source, target, table_names)
                    views = {v.original_name.lower(): v for v in plan.views}
                    for key in created:
                        view = views.get(f"zzv_v_{key}")
                        record: dict[str, Any] = {"source": source, "target": target, "view": key, "kind": kinds[key]}
                        if view is None:
                            record["status"] = "no_extraida"
                            results.append(record)
                            continue
                        rewritten = any(w.target_type == "VIEW (reescrita)" for w in view.warnings)
                        record["mode"] = "transpile" if rewritten else "passthrough"
                        record["sql"] = view.query
                        failed = next((e for s, e in errors.items() if view.name.lower() in s.lower() and "VIEW" in s.upper()), None)
                        if failed:
                            record.update(status="crear_falla", detail=failed)
                        else:
                            try:
                                got = target_rows(target, QUOTE[target](view.name))
                                record["status"] = "ok" if got == expected[key] else "resultado_distinto"
                                if got != expected[key]:
                                    record["detail"] = f"origen={expected[key][:3]} destino={got[:3]}"
                            except Exception as err:  # noqa: BLE001
                                record.update(status="select_falla", detail=str(err).splitlines()[0][:200])
                        results.append(record)
                except Exception:  # noqa: BLE001
                    traceback.print_exc()
                finally:
                    drop_target(target)
        finally:
            v0.teardown_namespace(source)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=1)
    summarize(results)


def summarize(results: list[dict[str, Any]]) -> None:
    pairs: dict[tuple[str, str], dict[str, int]] = {}
    for r in results:
        if r.get("kind") != "comun":
            if r.get("status") == "tablas_falla":
                print(f"TABLAS FALLAN {r['source']} → {r['target']}: {r['detail']}")
            continue
        st = pairs.setdefault((r["source"], r["target"]), {"total": 0, "ejecuta": 0, "igual": 0, "pass": 0})
        st["total"] += 1
        st["ejecuta"] += r["status"] in ("ok", "resultado_distinto")
        st["igual"] += r["status"] == "ok"
        st["pass"] += r.get("mode") == "passthrough"
    print(f"{'par':<26}{'se ejecuta':>14}{'mismo resultado':>18}{'sin reescribir':>16}")
    for (s, t), st in sorted(pairs.items()):
        print(f"{s + ' → ' + t:<26}{st['ejecuta']:>6}/{st['total']:<3}{100 * st['ejecuta'] / st['total']:>4.0f}%"
              f"{st['igual']:>9}/{st['total']:<3}{100 * st['igual'] / st['total']:>4.0f}%{st['pass']:>12}")


if __name__ == "__main__":
    main()
