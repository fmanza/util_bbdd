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
