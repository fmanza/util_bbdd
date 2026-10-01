"""S-2: aislamiento de filas erróneas con SAVEPOINT por lote y bisección (prototipo; sin cambios en ``src/``).

Una carga masiva atómica se deshace entera por una sola fila mala. Alternativa: cada lote en un SAVEPOINT; si falla, se
vuelve al SAVEPOINT y se reintenta por mitades (cada una en su SAVEPOINT) hasta aislar las filas que fallan; las buenas
se quedan, las malas se apartan. Todo en una transacción.

Mide, por motor (mismo método de envío en todas las variantes: ``connection.execute(insert(t), registros)``, con
``fast_executemany`` en SQL Server como la librería):
- ``limpia``: sin SAVEPOINT (referencia).
- ``limpia_sp``: con SAVEPOINT por lote (coste fijo del mecanismo).
- ``malas_N``: con N filas malas (PK duplicadas de filas ya insertadas) repartidas; filas en BD y rechazos verificados.
- ``fallo_y_recarga`` (estimado): tiempo hasta fallar en la fila mala + rollback + carga limpia completa.

Uso: python s2_isolate.py <motor,...> [filas]
"""

from __future__ import annotations

import json
import sys
import time

from pathlib import Path
from typing import Any

import pandas as pd
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / ".ai/sessions/2026-10-01h-performance-audit-bulk-todo/bench"))

import proto_bulk_todo as p  # noqa: E402

from util_bbdd.bulk import BulkCrud  # noqa: E402
from util_bbdd.bulk.normalize import dataframe_to_sql_records  # noqa: E402

ENGINES = sys.argv[1].split(",")
ROWS = int(sys.argv[2]) if len(sys.argv) > 2 else 1_000_000
BATCH = 5000


def load(conn: Any, table: sa.Table, records: list[dict[str, Any]], *, savepoints: bool, rejects: list[int], base: int = 0) -> None:
    """Inserta ``records``; con ``savepoints`` aísla por bisección las filas que fallan (índices en ``rejects``)."""
    if not savepoints:
        conn.execute(sa.insert(table), records)
        return
    sp = conn.begin_nested()
    try:
        conn.execute(sa.insert(table), records)
        sp.commit()
    except sa.exc.DBAPIError:
        sp.rollback()
        if len(records) == 1:
            rejects.append(base)
            return
        half = len(records) // 2
        load(conn, table, records[:half], savepoints=True, rejects=rejects, base=base)
        load(conn, table, records[half:], savepoints=True, rejects=rejects, base=base + half)


def run_variant(engine: sa.Engine, df: pd.DataFrame, bad_positions: list[int], *, savepoints: bool) -> dict[str, Any]:
    table = p.fresh(engine)
    data = df.copy()
    id_col = p.bb.physical_column("id", engine.dialect.name)
    for pos in bad_positions:  # PK duplicada de la fila 0 (ya insertada en el primer lote)
        data.loc[pos, id_col] = data.loc[0, id_col]
    rejects: list[int] = []
    t0 = time.perf_counter()
    failed_at: float | None = None
    try:
        with engine.begin() as conn:
            for start in range(0, len(data), BATCH):
                records = dataframe_to_sql_records(data.iloc[start : start + BATCH])
                try:
                    load(conn, table, records, savepoints=savepoints, rejects=rejects, base=start)
                except sa.exc.DBAPIError:
                    failed_at = time.perf_counter() - t0
                    raise
    except sa.exc.DBAPIError:
        pass
    elapsed = time.perf_counter() - t0
    rows = p.count(engine, table)
    return {"seconds": round(elapsed, 3), "rows": rows, "rejects": len(rejects),
            "rejects_ok": sorted(rejects) == sorted(bad_positions) if savepoints else None,
            "failed_at": round(failed_at, 3) if failed_at is not None else None}


for key in ENGINES:
    engine = p.engine_for(key)
    BulkCrud(engine, warn_if_audit_disabled=False)  # fast_executemany en SQL Server, como la librería
    df = p.bb.make_dataframe(ROWS, engine.dialect.name)
    out: dict[str, Any] = {"engine": key, "rows": ROWS}
    out["limpia"] = run_variant(engine, df, [], savepoints=False)
    out["limpia_sp"] = run_variant(engine, df, [], savepoints=True)
    for n in (1, 10, 100):
        positions = sorted({round((i + 1) * (ROWS - 1) / (n + 1)) for i in range(n)})
        out[f"malas_{n}"] = run_variant(engine, df, positions, savepoints=True)
    fail = run_variant(engine, df, [ROWS // 2], savepoints=False)  # fallo a mitad, modo actual
    out["fallo_mitad_actual"] = fail
    out["fallo_y_recarga_estimado_s"] = round(fail["seconds"] + out["limpia"]["seconds"], 3)
    print(json.dumps(out, ensure_ascii=False), flush=True)
    p.bb.drop_table(engine, p.bb.build_table(engine.dialect.name))
    engine.dispose()
