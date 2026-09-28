# Ejemplo: Queries Concurrentes con AsyncDatabaseManager

## 1. Contexto del Ejemplo

Ejecuta múltiples queries en paralelo usando `AsyncDatabaseManager` y `asyncio.gather()`, reduciendo el tiempo total de espera cuando las consultas son independientes entre sí.

Resuelve el caso habitual en servicios web de alta concurrencia: necesito consultar datos de cuatro tablas distintas y no tiene sentido esperarlas secuencialmente cuando pueden lanzarse a la vez.

## 2. Implementación de Referencia

```python
--8<-- "examples/async_concurrent_queries.py"
```

## 3. Explicación del Código

Aspectos críticos del patrón:

- **`asyncio.gather()`**: lanza todas las corrutinas simultáneamente. El tiempo total es el máximo de las duraciones individuales, no la suma.
- **Pool async**: `AsyncDatabaseManager` mantiene un pool de conexiones async; cada corrutina de `gather()` obtiene su propia conexión del pool sin bloquear a las demás.
- **`PoolExhaustedError`**: si hay más corrutinas concurrentes que conexiones en el pool, se lanza este error. Dimensionar el pool según la concurrencia esperada.
- **Inicialización lazy**: el manager no conecta en el constructor; es obligatorio `await init()` o usar `async with` antes de cualquier operación.

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/async_concurrent_queries.py

# Ejecución (requiere BD con driver async instalado)
python docs/examples/async_concurrent_queries.py
```

Ver [Guía de Programación Asíncrona](../guides/async_guide.md) para más patrones async/await.

## 5. Referencias Relacionadas

- **Documentación funcional**: [Gestión de Conexiones (Async)](../functional/managers_async.md) — objetivo de negocio del manager asíncrono
- **Referencia técnica**: [Manager Asíncrono](../api/managers_async.md) — contratos y patrones de inicialización
- **Ejemplos relacionados**: [Conectar e Introspeccionar Base de Datos](example_connect_introspect.md) — versión síncrona equivalente
