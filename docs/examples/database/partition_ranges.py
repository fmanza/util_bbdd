# Calcular rangos automáticamente
def calculate_ranges(source_engine, pk_column: str, n_partitions: int):
    """Calcular rangos de particiones basado en rango de PK."""
    with source_engine.connect() as conn:
        min_pk = conn.execute(text(f"SELECT MIN({pk_column}) FROM table")).scalar()
        max_pk = conn.execute(text(f"SELECT MAX({pk_column}) FROM table")).scalar()

    step = (max_pk - min_pk) // n_partitions
    return [(min_pk + i * step, min_pk + (i + 1) * step) for i in range(n_partitions)]
