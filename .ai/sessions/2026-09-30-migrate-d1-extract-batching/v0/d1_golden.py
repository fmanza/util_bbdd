"""D1: IR de referencia de los extractores (antes/después del refactor N+1), por motor, contra el banco.

    python d1_golden.py before   # con los extractores actuales → golden_before.json
    python d1_golden.py after    # tras el refactor → golden_after.json y comparación con before

Schema representativo: PK y FK compuestas (ON DELETE CASCADE), índice único de varias columnas, índice normal de
columnas en otro orden, DEFAULT y NOT NULL, una cadena de FK, vistas y una rutina.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import re
import sys

from pathlib import Path
from typing import Any

from util_bbdd import SyncDatabaseManager
from util_bbdd.migrate.extractors.mariadb import MariaDBSchemaExtractor
from util_bbdd.migrate.extractors.mysql import MariaDBFullTypeSchemaExtractor, MySQLSchemaExtractor
from util_bbdd.migrate.extractors.oracle import OracleSchemaExtractor
from util_bbdd.migrate.extractors.postgresql import PostgreSQLSchemaExtractor
from util_bbdd.migrate.extractors.sqlserver import SQLServerSchemaExtractor

sys.path.insert(0, str(Path(__file__).parent))
import d1_baseline as d1  # noqa: E402

logging.disable(logging.CRITICAL)
ROUTINE = {
    "mysql": "CREATE PROCEDURE {p}proc_a() BEGIN SELECT 1; END",
    "mariadb": "CREATE PROCEDURE {p}proc_a() BEGIN SELECT 1; END",
    "postgresql": "CREATE FUNCTION {p}func_a() RETURNS int LANGUAGE sql AS 'SELECT 1'",
    "sqlserver": "CREATE PROCEDURE {p}proc_a AS SELECT 1",
    "oracle": "CREATE PROCEDURE {p}proc_a AS BEGIN NULL; END;",
}


def _objects(engine: str) -> list[str]:
    i, v = ("NUMBER(10)", "VARCHAR2(50)") if engine == "oracle" else ("INT", "VARCHAR(50)")
    p = "ZZD1_" if engine == "oracle" else ""
    out = [
        f"CREATE TABLE {p}parent (a {i} NOT NULL, b {i} NOT NULL, name {v} DEFAULT 'x' NOT NULL, PRIMARY KEY (a, b))",
        f"CREATE TABLE {p}child (id {i} PRIMARY KEY, a {i}, b {i}, note {v}, "
        f"CONSTRAINT {p}fk_child FOREIGN KEY (a, b) REFERENCES {p}parent (a, b) ON DELETE CASCADE)",
        f"CREATE UNIQUE INDEX {p}ux_child ON {p}child (note, id)",
        f"CREATE INDEX {p}ix_child ON {p}child (b, a)",
        ROUTINE[engine].format(p=p),
    ]
    return out


def _extractors(engine: str, manager: Any) -> dict[str, Any]:
    if engine == "mysql":
        return {"default": MySQLSchemaExtractor(manager), "full": MySQLSchemaExtractor(manager, full_column_types=True)}
    if engine == "mariadb":
        return {"default": MariaDBSchemaExtractor(manager), "full": MariaDBFullTypeSchemaExtractor(manager)}
    cls = {"postgresql": PostgreSQLSchemaExtractor, "sqlserver": SQLServerSchemaExtractor, "oracle": OracleSchemaExtractor}
    return {"default": cls[engine](manager)}


def _snapshot() -> dict[str, Any]:
    d1.N_TABLES, d1.N_VIEWS = 5, 3
    snapshot: dict[str, Any] = {}
    engines = [e for e in os.environ.get("D1_ENGINES", ",".join(d1.ENV)).split(",") if e]
    for engine in engines:
        params, schema = d1._setup(engine)
        base = d1._url(engine, params.get("database") if engine in ("mysql", "mariadb", "sqlserver") else None)
        if engine == "postgresql":
            base = base.set(query={"options": f"-csearch_path={d1.NS}"})
        d1._raw(base, _objects(engine))
        manager = SyncDatabaseManager(engine, params, use_pool=False)
        try:
            for mode, extractor in _extractors(engine, manager).items():
                snapshot[f"{engine}/{mode}"] = {
                    "tables": [dataclasses.asdict(t) for t in extractor.extract(schema)],
                    "views": [dataclasses.asdict(v) for v in extractor.extract_views(schema)],
                    "routines": [dataclasses.asdict(r) for r in extractor.extract_routines(schema)],
                }
                counts = {k: len(val) for k, val in snapshot[f"{engine}/{mode}"].items()}
                print(engine, mode, counts, flush=True)
        finally:
            manager.close()
            d1._teardown(engine)
            if engine == "oracle":
                d1._raw(d1._url(engine), ['DROP PROCEDURE "ZZD1_PROC_A"'])
    return snapshot


def main() -> None:
    phase = sys.argv[1]
    folder = Path(__file__).parent
    snapshot = _snapshot()
    # Oracle da nombres de sistema distintos en cada creación a los índices de PK sin nombre (SYS_Cnnnn)
    text = re.sub(r"SYS_C\d+", "SYS_C#", json.dumps(snapshot, indent=1, ensure_ascii=False, default=str))
    snapshot = json.loads(text)
    (folder / f"golden_{phase}.json").write_text(text, "utf-8")
    if phase == "after":
        before = json.loads((folder / "golden_before.json").read_text("utf-8"))
        after = json.loads(json.dumps(snapshot, ensure_ascii=False, default=str))
        compared = [key for key in before if key in after]
        diffs = [key for key in compared if before[key] != after[key]]
        print(f"comparados: {compared}")
        print("IDÉNTICO" if not diffs else f"DIFERENCIAS: {diffs}")


if __name__ == "__main__":
    main()
