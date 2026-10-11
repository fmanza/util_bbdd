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
- **Pool async**: en PostgreSQL, MariaDB, MySQL, Oracle y SQL Server cada corrutina de `gather()` toma su propia conexión del pool (`pool_size` en `conn_params`). En SQLite el pool async es una sola conexión: las consultas se serializan y `gather()` no reduce el tiempo, como muestra la medición del ejemplo.
- **Pool agotado**: con más corrutinas que conexiones, las sobrantes esperan a que se libere una (en PostgreSQL, hasta `pool_timeout`, 30 s por defecto). No se lanza ningún error por el mero hecho de esperar; dimensionar el pool según la concurrencia esperada.
- **Inicialización**: el manager no conecta en el constructor. Conecta en `await init()`, al entrar en `async with` o, si no, en la primera operación; llamar a `init()` al arrancar hace que un error de conexión aparezca ahí.

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/async_concurrent_queries.py

# Ejecución (usa SQLite con aiosqlite; no requiere servidor externo)
python docs/examples/async_concurrent_queries.py
```

Ver [Guía de Programación Asíncrona](../guides/async_guide.md) para más patrones async/await.

## 5. Referencias Relacionadas

- **Documentación funcional**: [Gestión de Conexiones (Async)](../functional/managers_async.md) — objetivo de negocio del manager asíncrono
- **Referencia técnica**: [Manager Asíncrono](../api/managers_async.md) — contratos y patrones de inicialización
- **Ejemplos relacionados**: [Conectar e Introspeccionar Base de Datos](example_connect_introspect.md) — versión síncrona equivalente
