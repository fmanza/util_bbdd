# Ejemplo: Benchmark — Impacto de `commit_every_n_chunks`

## 1. Contexto del Ejemplo

Demuestra el impacto de la cadencia de commits en cargas masivas sobre MySQL/MariaDB. Sin commits intermedios, la latencia de inserción crece exponencialmente a partir de 1M de filas por saturación del undo log e InnoDB buffer pool.

Resuelve el problema de degradación de rendimiento en procesos ETL de alto volumen sobre MySQL/MariaDB: sin `commit_every_n_chunks`, una carga de 10M filas puede pasar de los 2 segundos esperados a 60+ segundos.

## 2. Implementación de Referencia

```python
--8<-- "examples/benchmark_commit_cadence.py"
```

## 3. Explicación del Código

**Causa raíz de la degradación**: en MySQL/MariaDB con InnoDB, sin commits intermedios toda la carga corre en una única transacción `BEGIN...COMMIT`. El undo log crece linealmente con el número de filas sin commitear. Cuando el buffer pool (128–256 MB por default) se satura, InnoDB empieza a hacer flush de páginas sucias al disco, incrementando la latencia de cada nueva inserción.

**Solución**: `commit_every_n_chunks=N` emite `COMMIT` cada N lotes, liberando el undo log periódicamente y manteniendo la latencia lineal.

| InnoDB buffer pool | `commit_every_n_chunks` recomendado | Filas/commit aprox. |
|---|---|---|
| 256 MB | 10 | 50K |
| 1 GB | 20 | 100K |
| 4 GB+ | 50 | 250K |

**Advertencia de atomicidad**: con `commit_every_n_chunks` activo, la carga de cada tabla deja de ser atómica. Un fallo a mitad deja committeados los lotes anteriores. Diseñar la carga con idempotencia o rollback manual si se requiere atomicidad.

**Nota**: el script usa SQLite en memoria para portabilidad. En MariaDB real con disco, la degradación SIN cadencia sería 5–10× mayor que con SQLite.

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/benchmark_commit_cadence.py

# Test rápido (100K filas)
python docs/examples/benchmark_commit_cadence.py --size small

# Test completo (1M filas)
python docs/examples/benchmark_commit_cadence.py --size large
```

Resultado esperado con SQLite in-memory (degradación mínima):

```
Test 1: SIN cadencia — 8.45s
Test 2: CON cadencia — 7.92s
Speedup: 1.07×
```

Con MariaDB real y disco, el speedup con cadencia es típicamente 3–8× a partir de 1M filas.

## 5. Referencias Relacionadas

- **Documentación funcional**: [Operaciones Bulk (CRUD)](../functional/bulk-operations.md) — reglas de negocio sobre transaccionalidad y rendimiento
- **Referencia técnica**: [CRUD Masivo (BulkCrud)](../api/bulk-crud.md) — parámetro `commit_every_n_chunks` en el contrato de entrada
- **Ejemplos relacionados**: [Bulk Insert desde CSV](bulk_insert_csv.md) — inserción básica sin optimización de cadencia
