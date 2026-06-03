"""Ejemplo: Volcar datos de PostgreSQL a SQL Server con DumpOrchestrator."""

from pathlib import Path

from sqlalchemy import create_engine

from util_bbdd.dump import DumpConfig, DumpOrchestrator

# 1. Engines (replace with real credentials)
src_engine = create_engine(
    "postgresql+psycopg2://user:password@prod-server:5432/production_db"
)
dst_engine = create_engine(
    "mssql+pymssql://user:password@analytics-server/analytics_db"
)

# 2. Configuración
config = DumpConfig(
    source_engine=src_engine,
    target_engine=dst_engine,
    source_schema="public",
    target_schema="dbo",
    chunk_size=1_000,
    output_dir=Path("reports"),
    truncate_target=True,
)

# 3. Ejecutar volcado
result = DumpOrchestrator(config).run()

# 4. Revisar resultado
print(f"Informe: {result.report}")
print(f"Orden de carga: {result.load_order}")

for tr in result.table_results:
    print(
        f"  [{tr.status.upper():15}] {tr.table_name:30} "
        f"origen={tr.source_rows:>8}  destino={tr.target_rows_after:>8}"
    )
    if tr.error_msg:
        print(f"    ERROR: {tr.error_msg}")
