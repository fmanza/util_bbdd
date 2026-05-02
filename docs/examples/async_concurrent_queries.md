# Queries Concurrentes (Async)

Ejemplo que muestra cómo ejecutar múltiples queries en paralelo con `AsyncDatabaseManager` y `asyncio.gather()`.

**Cubre:**

- Configurar `AsyncDatabaseManager` con pool
- Ejecutar queries en paralelo con `asyncio.gather()`
- Recolectar resultados
- Manejar `PoolExhaustedError`

!!! info "Beneficio del paralelismo"
    El ejemplo usa `asyncio.gather()` para lanzar cuatro consultas y recoger sus resultados en una sola espera.
    Ver [Guía de Programación Asíncrona](../ASYNC_GUIDE.md) para más detalles.

---

```python
--8<-- "examples/async_concurrent_queries.py"
```

---

!!! tip "Ver también"
    - [Guía Async](../ASYNC_GUIDE.md) — patrones async/await en profundidad
    - [Excepciones](../EXCEPTIONS.md) — `PoolExhaustedError`, `DatabaseException`
