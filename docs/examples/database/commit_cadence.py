# Configuración de commit cadence
from util_bbdd.bulk import ParallelBulkLoader

loader = ParallelBulkLoader(
    engine=target_engine,
    chunk_size=5_000,
    max_workers=4,
    commit_every_n_chunks=2,  # commit cada 10K filas (2 × 5K)
)
