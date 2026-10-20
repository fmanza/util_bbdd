"""Ejemplo: auditoría común de una carga (BulkCrud) y un volcado (DumpOrchestrator) en un mismo JSON Lines.

Usa dos ficheros SQLite en el directorio actual (origen y destino); no requiere servidor externo. Escribe
``logs/auditoria.jsonl``, el CSV heredado ``logs/auditoria.csv`` y el informe del volcado en ``reports/``.
"""

import json

from collections import Counter
from pathlib import Path

import pandas as pd

from sqlalchemy import create_engine, text

from util_bbdd import BulkCrud, DumpConfig, DumpOrchestrator
from util_bbdd.audit import JsonLinesAuditSink
from util_bbdd.bulk.options import AuditOptions

for name in ("origen.db", "destino.db"):
    Path(name).unlink(missing_ok=True)
jsonl = Path("logs/auditoria.jsonl")
jsonl.unlink(missing_ok=True)

origen = create_engine("sqlite:///origen.db")
destino = create_engine("sqlite:///destino.db")
for engine in (origen, destino):
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE clientes (id INTEGER PRIMARY KEY, nombre VARCHAR(50))"))

sink = JsonLinesAuditSink(jsonl)
try:
    # 1. Carga masiva en el origen: evento en el JSON Lines y fila en el CSV heredado
    df = pd.DataFrame({"id": range(1, 101), "nombre": [f"cliente {i}" for i in range(1, 101)]})
    crud = BulkCrud(origen, audit=AuditOptions(csv_path=Path("logs/auditoria.csv"), sink=sink))
    crud.bulk_insert_from_df(df, "clientes", generar_sql=False)

    # 2. Volcado origen → destino con el mismo destino de eventos
    result = DumpOrchestrator(
        DumpConfig(source_engine=origen, target_engine=destino, output_dir=Path("reports"), audit_sink=sink)
    ).run()
finally:
    sink.close()
    origen.dispose()
    destino.dispose()

# 3. Leer los eventos: los del volcado, también las escrituras que hace con bulk, comparten DumpResult.audit_run_id
events = [json.loads(line) for line in jsonl.read_text(encoding="utf-8").splitlines()]
for e in events:
    run = "volcado" if e["run_id"] == result.audit_run_id else "carga"
    print(f"{run:8} {e['source']:5} {e['kind']:10} {e['operation']:7} {e['target']} filas={e['rows']} {e['status']}")
print("eventos por origen:", dict(sorted(Counter(e["source"] for e in events).items())))
