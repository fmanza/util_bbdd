"""
Ejemplo: Bulk insert desde CSV con auditoría y lectura del historial de operaciones.
Requisitos: util_bbdd con el extra postgresql (o el driver del motor que uses)
"""

from pathlib import Path

import pandas as pd

from sqlalchemy import text

from util_bbdd import BulkCrud, DatabaseException, SyncDatabaseManager
from util_bbdd.bulk import AuditManager
from util_bbdd.bulk.options import AuditOptions

# Crear datos de ejemplo
df_data = pd.DataFrame(
    {
        "id": range(1, 101),
        "nombre": [f"Usuario{i}" for i in range(1, 101)],
        "email": [f"user{i}@example.com" for i in range(1, 101)],
    }
)

# Guardar CSV temporal
csv_input = Path("usuarios_input.csv")
df_data.to_csv(csv_input, index=False)

# Engine SQLAlchemy del manager (replace with real credentials)
mgr = SyncDatabaseManager(
    db_type="postgresql",
    conn_params={
        "host": "localhost",
        "port": 5432,
        "user": "postgres",
        "password": "secret",
        "database": "test_db",
    },
)
engine = mgr.get_sqlalchemy_engine()

# Tabla destino (BulkCrud no crea tablas)
with engine.begin() as conn:
    conn.execute(
        text("CREATE TABLE IF NOT EXISTS usuarios (id INTEGER PRIMARY KEY, nombre VARCHAR(50), email VARCHAR(100))")
    )
    conn.execute(text("DELETE FROM usuarios"))

# Bulk insert con auditoría: audit_csv_path es la ruta del fichero CSV (el directorio se crea si falta)
audit_csv = Path("audit_bulk") / "auditoria.csv"
bcm = BulkCrud(engine=engine, audit=AuditOptions(csv_path=audit_csv))
try:
    df = pd.read_csv(csv_input)
    bcm.bulk_insert_from_df(df, tabla_destino="usuarios", generar_sql=False)
except DatabaseException as exc:
    print(f"Error de base de datos: {exc}")
    raise

# === ANÁLISIS DE AUDITORÍA ===
print("\n=== Audit Report ===")
audit = AuditManager(audit_csv)
df_audit = audit.leer_auditoria()  # el CSV es tabulado y con coma decimal: leerlo con AuditManager
print(df_audit[["operacion", "tabla", "total_filas", "tiempo_seg", "timestamp"]].tail(1))

stats = audit.obtener_estadisticas()
print(f"\n✓ Operaciones registradas: {stats['total_operaciones']}")
print(f"✓ Filas insertadas (última operación): {int(df_audit['total_filas'].iloc[-1])}")
print(f"✓ Motor: {df_audit['motor'].iloc[-1]}")

# Limpieza
csv_input.unlink()
mgr.close()
