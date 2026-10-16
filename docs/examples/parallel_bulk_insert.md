# Ejemplo: Carga Paralela de Millones de Filas

## 1. Contexto del Ejemplo

Demuestra cómo usar `ParallelBulkLoader` para cargar 100K filas en 4 particiones paralelas desde un CSV, comparando el throughput paralelo vs. secuencial.

Resuelve el cuello de botella de inserción en procesos ETL de alto volumen cuando una sola tabla domina el tiempo de carga. La ganancia depende del motor: ver [benchmarks](../guides/benchmarks.md#carga-paralela-por-particiones).

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

**Pool de conexiones**: el engine destino debe tener capacidad ≥ `ParallelOptions.max_workers`. Para 4 workers:

```python
--8<-- "examples/database/pool_setup.py"
```

**Lectores de partición**: cada reader es un callable que retorna un iterador de DataFrames para su partición:

```python
--8<-- "examples/database/reader_factory.py"
```

**Commit cadence**: comitear cada N lotes acota el undo log y permite reanudar una partición tras un fallo (no acelera la carga; ver [benchmark](benchmark_commit_cadence.md)):

```python
--8<-- "examples/database/commit_cadence.py"
```

**Throughput**: el ejemplo usa SQLite, que admite un solo escritor: la carga paralela no gana (en la revisión de 2026-10-11, este ejemplo tardó 0,53 s en paralelo frente a 0,27 s en secuencial). Lo medido con 4 hilos y 1M filas: SQL Server ≈ 2,7×, MySQL/MariaDB ≈ 1,7×, PostgreSQL con psycopg 3 1,05×, Oracle 1,14× ([benchmarks](../guides/benchmarks.md#carga-paralela-por-particiones)).

**`RangePartitioner` — PK entera, DataFrame en memoria:**

```python
from util_bbdd.bulk import RangePartitioner, ParallelBulkLoader
from util_bbdd.bulk.options import ParallelOptions

# Divide el DataFrame en 4 slices disjuntos ordenados por 'id'
partitions = RangePartitioner.partition_dataframe(df, pk_col="id", n_partitions=4)
readers = [lambda p=part: iter([p]) for part in partitions]
result = ParallelBulkLoader(engine, parallel=ParallelOptions(max_workers=4)).load("orders", readers)
```

**`RangePartitioner` — rangos para lectores SQL (volúmenes >RAM):**

```python
from util_bbdd.bulk.options import ParallelOptions
# Genera rangos (lo, hi) sin materializar el DataFrame completo
ranges = RangePartitioner.partition_ranges(1, 13_000_000, n_partitions=8)
readers = [
    lambda lo=lo, hi=hi: pd.read_sql(
        "SELECT * FROM orders WHERE id BETWEEN :lo AND :hi",
        src_engine, params={"lo": lo, "hi": hi}, chunksize=5000,
    )
    for lo, hi in ranges
]
result = ParallelBulkLoader(dst_engine, parallel=ParallelOptions(max_workers=8)).load("orders", readers)
```

**`HashPartitioner` — PK de tipo UUID o string:**

```python
from util_bbdd.bulk import HashPartitioner
from util_bbdd.bulk.options import ParallelOptions

# Acepta cualquier tipo hashable; distribución estadísticamente uniforme
partitions = HashPartitioner.partition_dataframe(df, pk_col="uuid_col", n_partitions=4)
readers = [lambda p=part: iter([p]) for part in partitions]
result = ParallelBulkLoader(engine, parallel=ParallelOptions(max_workers=4)).load("orders", readers)
```

**Constraints desactivadas durante la carga (cargas >1 M filas):**

```python
from util_bbdd.bulk.options import ParallelOptions
# Cada worker desactiva las constraints en su propia sesión (maintenance_scope) y las restaura al terminar.
# No envolver loader.load() en el maintenance_scope de otra BulkCrud: en MySQL/MariaDB FOREIGN_KEY_CHECKS es
# de sesión y no alcanzaría a las conexiones de los workers.
result = ParallelBulkLoader(engine, parallel=ParallelOptions(max_workers=4, disable_constraints=True)).load("orders", readers)
```

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/parallel_bulk_insert.py

# Ejecución completa (usa SQLite; genera CSV de prueba y mide throughput)
python docs/examples/parallel_bulk_insert.py
```

Resultado esperado (las cifras de tiempo y throughput dependen de la máquina):

```
✅ Carga completada
   Filas cargadas: 100,000
   Throughput: <n> filas/seg
   Tiempo total: <s>s (wall-clock: <s>s)
   ✓ Todas las particiones cargadas exitosamente
```

Ver [API Reference: ParallelBulkLoader](../api/bulk_parallel.md) y [Benchmark: Commit Cadence](benchmark_commit_cadence.md).

## 5. Referencias Relacionadas

- **Documentación funcional**: [Carga Masiva Paralela](../functional/bulk_parallel_loading.md) — reglas de negocio sobre particionado y paralelismo
- **Referencia técnica**: [Carga Masiva Paralela](../api/bulk_parallel.md) — API de `ParallelBulkLoader` y `ParallelLoadResult`
- **Referencia técnica**: [CRUD Masivo (BulkCrud)](../api/bulk_crud.md) — primitiva de inserción usada por cada worker
- **Ejemplos relacionados**: [Benchmark: Commit Cadence](benchmark_commit_cadence.md) — optimización de commits en alto volumen
