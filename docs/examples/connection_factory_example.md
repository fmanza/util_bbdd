# Ejemplo: Conexiones Nativas con ConnectionFactory

## 1. Contexto del Ejemplo

Los managers (`SyncDatabaseManager`, `AsyncDatabaseManager`) crean sus conexiones a través de `ConnectionFactory`, con
pool. Llamar a la factoría directamente solo tiene sentido cuando se necesita la conexión nativa del driver, sin pool
ni manager: por ejemplo, para una utilidad que abre una conexión, ejecuta una sentencia y la cierra.

El ejemplo abre una conexión síncrona y otra asíncrona a SQLite en memoria y muestra el rechazo de un motor no
soportado.

## 2. Implementación de Referencia

```python
--8<-- "examples/connection_factory_example.py"
```

## 3. Explicación del Código

- **Objeto nativo del driver**: `create_connection` devuelve la conexión del driver (`sqlite3.Connection` en SQLite),
  no un objeto de SQLAlchemy ni de la librería. Su API es la del driver.
- **Async**: `create_async_connection` es una corrutina y devuelve la conexión del driver async (`aiosqlite` en SQLite,
  que se instala con el extra `dev` o aparte).
- **Cierre**: sin pool ni manager, cerrar la conexión es responsabilidad de quien la abre (`try`/`finally`).
- **Motor no soportado**: `"postgres"` no es un `db_type` válido (es `"postgresql"`); se rechaza con
  `InvalidDatabaseType` antes de intentar conectar. La factoría también registra el error en el LOG, por eso aparece
  una línea `❌ Error al crear conexión…` en la salida de error.

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/connection_factory_example.py

# Ejecución (SQLite en memoria; la parte async necesita aiosqlite)
python docs/examples/connection_factory_example.py
```

Resultado esperado (salida estándar):

```text
sync: (1,)
async: (2,)
rechazado: InvalidDatabaseType
```

## 5. Referencias Relacionadas

- **Documentación funcional**: [Conexiones y Pools](../functional/connection_management.md) — validación de
  parámetros, pools y credenciales
- **Referencia técnica**: [Factory de Conexiones](../api/connection_factory.md) — API de `ConnectionFactory` y
  `PoolFactory`
- **Ejemplos relacionados**: [Conectar e Introspeccionar Base de Datos](example_connect_introspect.md) — el uso
  habitual, a través de un manager
