"""
Ejemplo: Bulk insert desde CSV con lectura de auditoría y análisis de timing.
Requisitos: pandas, util_bbdd
"""

from pathlib import Path

import pandas as pd

from util_bbdd.managers import SyncDatabaseManager

# Crear datos de ejemplo
df_data = pd.DataFrame(
    {
        "id": range(1, 101),
        "nombre": [f"Usuario{i}" for i in range(1, 101)],
        "email": [f"user{i}@example.com" for i in range(1, 101)],
    }
)

# Guardar CSV temporal
csv_input = "usuarios_input.csv"
df_data.to_csv(csv_input, index=False)

# Obtener engine SQLAlchemy
mgr = SyncDatabaseManager(
    db_type="postgresql",
    conn_params={"host": "localhost", "port": 5432, "user": "postgres", "password": "secret", "database": "test_db"},
)
engine = mgr.get_sqlalchemy_engine()

# Bulk insert usando BulkCrud
from util_bbdd.bulk import BulkCrud

audit_csv_path = Path("./audit_bulk")
audit_csv_path.mkdir(exist_ok=True)

bcm = BulkCrud(engine=engine, audit_csv_path=audit_csv_path)
df = pd.read_csv(csv_input)
bcm.bulk_insert_from_df(df, tabla_destino="usuarios")

# === ANÁLISIS DE AUDITORÍA CON TIMING ===
print("\n=== Audit Report con Timing ===")

# Leer CSV de auditoría generado
audit_files = list(audit_csv_path.glob("audit_insert_*.csv"))
if audit_files:
    df_audit = pd.read_csv(audit_files[-1])
    print(df_audit[["operacion", "tabla", "total_filas", "tiempo_seg", "timestamp"]])

    # Estadísticas
    print(f"\n✓ Filas insertadas: {df_audit['total_filas'].sum()}")
    print(f"✓ Tiempo total: {df_audit['tiempo_seg'].sum():.3f} segundos")
    print(f"✓ Tiempo promedio por fila: {(df_audit['tiempo_seg'].sum() / df_audit['total_filas'].sum()) * 1000:.2f} ms")
    print(f"✓ Motor: {df_audit['motor'].iloc[0]}")

# Limpieza
Path(csv_input).unlink()
mgr.close()
