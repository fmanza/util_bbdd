"""
Ejemplo: Carga paralela de 1M de filas desde CSV usando ParallelBulkLoader.
Requisitos: pandas, util_bbdd, sqlalchemy
"""

import time

from pathlib import Path

import pandas as pd

from sqlalchemy import create_engine, text

from util_bbdd.bulk import ParallelBulkLoader

# ============================================================================
# 1. Preparar datos de ejemplo
# ============================================================================

# Generar CSV de 100K filas (reducido para demostración; escala a 1M+)
print("📋 Generando datos de ejemplo...")
data = {
    "id": range(1, 100_001),
    "date": pd.date_range("2024-01-01", periods=100_000, freq="1min").astype(str),
    "amount": (pd.Series(range(1, 100_001)) * 1.5 % 1000).round(2),
    "customer_id": (pd.Series(range(1, 100_001)) % 500) + 1,
}
df_source = pd.DataFrame(data)

# Guardar como CSV temporal
csv_path = Path("sales_data_source.csv")
df_source.to_csv(csv_path, index=False)
print(f"✓ CSV generado: {csv_path} ({len(df_source):,} filas)")

# ============================================================================
# 2. Crear engines
# ============================================================================

print("\n🔌 Inicializando conexiones...")

# Destino con pool ampliado para 4 workers
target_engine = create_engine(
    "sqlite:///target_parallel.db",
    pool_size=4,
    max_overflow=2,
    echo=False,
)

print("✓ Engines creados")

# ============================================================================
# 3. Preparar tabla destino
# ============================================================================

print("\n📊 Preparando tabla destino...")

with target_engine.begin() as conn:
    conn.execute(text("DROP TABLE IF EXISTS sales_data"))
    conn.execute(
        text("""
        CREATE TABLE sales_data (
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            customer_id INTEGER NOT NULL
        )
    """)
    )

print("✓ Tabla creada")

# ============================================================================
# 4. Definir lectores de partición (4 particiones de 25K cada una)
# ============================================================================

print("\n📁 Preparando lectores de partición...")

# Particiones: [1-25K], [25K-50K], [50K-75K], [75K-100K+]
ranges = [
    (1, 25_001),
    (25_001, 50_001),
    (50_001, 75_001),
    (75_001, 100_001),
]


def make_reader(lo: int, hi: int, csv_file: Path):
    """Crea un lector que extrae una partición del CSV."""

    def _reader():
        # Leer todo el CSV (en escenario real sería lectura remota/SQL)
        df = pd.read_csv(csv_file)
        # Filtrar por rango de ID
        df_partition = df[(df["id"] >= lo) & (df["id"] < hi)]

        # Devolver en chunks de 5K
        for i in range(0, len(df_partition), 5_000):
            chunk = df_partition.iloc[i : i + 5_000].reset_index(drop=True)
            if not chunk.empty:
                yield chunk

    return _reader


readers = [make_reader(lo, hi, csv_path) for lo, hi in ranges]
print(f"✓ {len(readers)} lectores de partición creados")

# ============================================================================
# 5. Ejecutar carga paralela
# ============================================================================

print("\n⚡ Iniciando carga paralela...")
print(f"   Particiones: {len(ranges)}")
print("   Tamaño lote: 5,000 filas")
print("   Workers: 4")

start_time = time.time()

loader = ParallelBulkLoader(
    engine=target_engine,
    chunk_size=5_000,
    max_workers=4,
    commit_every_n_chunks=2,  # Commit cada 10K filas
)

result = loader.load(
    tabla_destino="sales_data",
    partition_readers=readers,
    override_identity=False,
)

elapsed = time.time() - start_time

# ============================================================================
# 6. Mostrar resultado
# ============================================================================

print("\n✅ Carga completada")
print(f"   Filas cargadas: {result.total_rows:,}")
print(f"   Throughput: {result.rows_per_second:,.0f} filas/seg")
print(f"   Tiempo total: {result.elapsed_seconds:.2f}s (wall-clock: {elapsed:.2f}s)")

if result.partition_errors:
    print("\n⚠️  Errores por partición:")
    for error in result.partition_errors:
        print(f"   - {error}")
else:
    print("   ✓ Todas las particiones cargadas exitosamente")

# ============================================================================
# 7. Validación post-carga
# ============================================================================

print("\n📊 Validación post-carga...")

with target_engine.connect() as conn:
    total_rows = conn.execute(text("SELECT COUNT(*) FROM sales_data")).scalar()
    avg_amount = conn.execute(text("SELECT AVG(amount) FROM sales_data")).scalar()
    unique_customers = conn.execute(text("SELECT COUNT(DISTINCT customer_id) FROM sales_data")).scalar()

print(f"   Filas totales: {total_rows:,}")
print(f"   Importe promedio: ${avg_amount:.2f}")
print(f"   Clientes únicos: {unique_customers:,}")

# ============================================================================
# 8. Comparar con carga secuencial
# ============================================================================

print("\n⏱️  Benchmark: paralelo vs. secuencial...")

# Vaciar tabla
with target_engine.begin() as conn:
    conn.execute(text("DELETE FROM sales_data"))

# Carga secuencial (referencia)
start_time = time.time()

from util_bbdd.bulk import BulkCrud

bcm = BulkCrud(engine=target_engine, chunk_size=5_000)
bcm.bulk_insert_from_df(df_source, tabla_destino="sales_data", generar_sql=False)

sequential_elapsed = time.time() - start_time

print(f"   Secuencial: {sequential_elapsed:.2f}s → {len(df_source) / sequential_elapsed:,.0f} rows/s")
print(f"   Paralelo:   {elapsed:.2f}s → {result.rows_per_second:,.0f} rows/s")
print(f"   Speedup:    {sequential_elapsed / elapsed:.1f}×")

# ============================================================================
# 9. Limpieza
# ============================================================================

print("\n🧹 Limpieza...")
csv_path.unlink()
target_engine.dispose()

print("✓ Ejemplo completado")
