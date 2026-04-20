# Queries Concurrentes (Async)

Ejemplo que muestra cómo ejecutar múltiples queries en paralelo con `AsyncDatabaseManager` y `asyncio.gather()`.

**Cubre:**

- Configurar `AsyncDatabaseManager` con pool
- Ejecutar queries en paralelo con `asyncio.gather()`
- Recolectar resultados
- Manejar `PoolExhaustedError`

!!! info "Beneficio del paralelismo"
    4 queries ejecutadas en paralelo (~100ms) vs. secuencial (~400ms).
    Ver [Guía de Programación Asíncrona](../ASYNC_GUIDE.md) para más detalles.

---

```python
--8<-- "examples/async_concurrent_queries.py"
```

---

!!! tip "Ver también"
    - [Guía Async](../ASYNC_GUIDE.md) — patrones async/await en profundidad
    - [Excepciones](../EXCEPTIONS.md) — `PoolExhaustedError`, `DatabaseException`
