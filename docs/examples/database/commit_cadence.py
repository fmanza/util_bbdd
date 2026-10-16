# Configuración de commit cadence
from util_bbdd.bulk import ParallelBulkLoader
from util_bbdd.bulk.options import BatchOptions, ParallelOptions

loader = ParallelBulkLoader(
    engine=target_engine,
    batch=BatchOptions(chunk_size=5_000, commit_every_n_chunks=2),  # commit cada 10K filas (2 × 5K)
    parallel=ParallelOptions(max_workers=4),
)
