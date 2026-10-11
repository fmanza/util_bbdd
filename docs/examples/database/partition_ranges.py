# Calcular rangos de partición a partir del MIN/MAX de la PK
from sqlalchemy import text

from util_bbdd.bulk import RangePartitioner


def calculate_ranges(source_engine, table: str, pk_column: str, n_partitions: int) -> list[tuple[int, int]]:
    """Rangos (lo, hi) inclusivos, disjuntos y que cubren [MIN(pk), MAX(pk)]."""
    with source_engine.connect() as conn:
        min_pk, max_pk = conn.execute(text(f"SELECT MIN({pk_column}), MAX({pk_column}) FROM {table}")).one()
    return RangePartitioner.partition_ranges(min_pk, max_pk, n_partitions)
