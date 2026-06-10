# Ejemplo: Carga Paralela de Millones de Filas

## 1. Contexto del Ejemplo

Demuestra cómo usar `ParallelBulkLoader` para cargar 100K filas en 4 particiones paralelas desde un CSV, comparando el throughput paralelo vs. secuencial.

Resuelve el cuello de botella de inserción en procesos ETL de alto volumen: un data mart que tarda 30 minutos en recargarse secuencialmente puede reducirse a 8 minutos con paralelismo por particiones de PK.

## 2. Implementación de Referencia

```python
--8<-- "examples/parallel_bulk_insert.py"
```

## 3. Explicación del Código

Aspectos críticos:

**Particiones disjuntas**: las particiones no deben solaparse. El ejemplo usa rangos de PK `(1-25K, 25K-50K, 50K-75K, 75K-100K)`. Los solapamientos provocan `IntegrityError` en destino.

```python
--8<-- "examples/database/partition_ranges.py"
```

**Pool de conexiones**: el engine destino debe tener capacidad ≥ `max_workers`. Para 4 workers:

```python
--8<-- "examples/database/pool_setup.py"
```

**Lectores de partición**: cada reader es un callable que retorna un iterador de DataFrames para su partición:

```python
--8<-- "examples/database/reader_factory.py"
```

**Commit cadence**: para cargas masivas en MySQL/MariaDB, comitear cada N lotes acota el undo log y mantiene la latencia lineal:

```python
--8<-- "examples/database/commit_cadence.py"
```

**Throughput esperado con SQLite** (motor del ejemplo): 1.5× sobre secuencial. Con PostgreSQL/MySQL en producción el speedup típico es 2.5–3.5× con 4 workers.

**`RangePartitioner` — PK entera, DataFrame en memoria:**

```python
from util_bbdd.bulk import RangePartitioner, ParallelBulkLoader

# Divide el DataFrame en 4 slices disjuntos ordenados por 'id'
partitions = RangePartitioner.partition_dataframe(df, pk_col="id", n_partitions=4)
readers = [lambda p=part: iter([p]) for part in partitions]
result = ParallelBulkLoader(engine, max_workers=4).load("orders", readers)
```

**`RangePartitioner` — rangos para lectores SQL (volúmenes >RAM):**

```python
# Genera rangos (lo, hi) sin materializar el DataFrame completo
ranges = RangePartitioner.partition_ranges(1, 13_000_000, n_partitions=8)
readers = [
    lambda lo=lo, hi=hi: pd.read_sql(
        "SELECT * FROM orders WHERE id BETWEEN :lo AND :hi",
        src_engine, params={"lo": lo, "hi": hi}, chunksize=5000,
    )
    for lo, hi in ranges
]
result = ParallelBulkLoader(dst_engine, max_workers=8).load("orders", readers)
```

**`HashPartitioner` — PK de tipo UUID o string:**

```python
from util_bbdd.bulk import HashPartitioner

# Acepta cualquier tipo hashable; distribución estadísticamente uniforme
partitions = HashPartitioner.partition_dataframe(df, pk_col="uuid_col", n_partitions=4)
readers = [lambda p=part: iter([p]) for part in partitions]
result = ParallelBulkLoader(engine, max_workers=4).load("orders", readers)
```

**`maintenance_scope` — deshabilitar FKs e índices para cargas >1 M filas:**

```python
from util_bbdd.bulk import BulkCrud

bulk = BulkCrud(engine)
loader = ParallelBulkLoader(engine, max_workers=4)

with bulk.bulk_session():
    with bulk.maintenance_scope("orders", disable_indexes=True):
        # Las FKs y los índices secundarios están deshabilitados durante la carga
        result = loader.load("orders", readers)
# Al salir del bloque maintenance_scope se restauran automáticamente
```

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/parallel_bulk_insert.py

# Ejecución completa (usa SQLite; genera CSV de prueba y mide throughput)
python docs/examples/parallel_bulk_insert.py
```

Resultado esperado:

```
✅ Filas cargadas: 100,000
⏱️  Throughput: 45,000 filas/seg
⏱️  Tiempo total: 2.22s
✅ Todas las particiones cargadas exitosamente
```

Ver [API Reference: ParallelBulkLoader](../api/bulk-parallel.md) y [Benchmark: Commit Cadence](benchmark_commit_cadence.md).

## 5. Referencias Relacionadas

- **Documentación funcional**: [Carga Masiva Paralela](../functional/bulk-parallel-loading.md) — reglas de negocio sobre particionado y paralelismo
- **Referencia técnica**: [Carga Masiva Paralela](../api/bulk-parallel.md) — API de `ParallelBulkLoader` y `ParallelLoadResult`
- **Referencia técnica**: [CRUD Masivo (BulkCrud)](../api/bulk-crud.md) — primitiva de inserción usada por cada worker
- **Ejemplos relacionados**: [Benchmark: Commit Cadence](benchmark_commit_cadence.md) — optimización de commits en alto volumen
