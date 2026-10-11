# Ejemplo: Conectar e Introspeccionar Base de Datos

## 1. Contexto del Ejemplo

Conecta a una base de datos, lista tablas, obtiene columnas y claves, y ejecuta consultas SQL personalizadas con parámetros. El caso principal usa SQLite en memoria para no requerir servidor externo.

Resuelve el primer paso de cualquier trabajo con `util_bbdd`: verificar conectividad y explorar el esquema de la BD sin modificar datos.

## 2. Implementación de Referencia

```python
--8<-- "examples/example_connect_introspect.py"
```

## 3. Explicación del Código

Aspectos críticos:

- **`db_type`**: debe ser uno de los valores soportados (`mariadb`, `mysql`, `oracle`, `postgresql`, `sqlserver`, `sqlite`, `hsqldb`; sin distinguir mayúsculas). Error común: `"postgre"` o `"postgres"` en lugar de `"postgresql"` (`InvalidDatabaseType`).
- **`execute_custom_many` vs `execute_custom_one`**: el primero retorna `list[tuple]` (siempre, incluso si hay 0 filas), el segundo retorna `tuple | None`.
- **Context manager**: usar `with SyncDatabaseManager(...) as manager:` garantiza que `close()` se llame automáticamente, incluso si se produce una excepción.
- **Parámetros nombrados**: usar siempre `:nombre` en las queries, nunca concatenación de strings. Los parámetros se pasan como `params={"nombre": valor}`.

Para conectar a otros motores, solo cambia `db_type` y `conn_params`:

```python
# PostgreSQL
manager = SyncDatabaseManager(
    db_type="postgresql",
    conn_params={"host": "localhost", "port": 5432, "user": "user", "password": "secret", "database": "mydb"},
)

# MariaDB
manager = SyncDatabaseManager(
    db_type="mariadb",
    conn_params={"host": "localhost", "port": 3306, "user": "root", "password": "secret", "database": "myapp"},
)
```

## 4. Ejecución y Pruebas

```bash
# Validación sintáctica
python -m py_compile docs/examples/example_connect_introspect.py

# Ejecución (usa SQLite en memoria; no requiere servidor externo)
python docs/examples/example_connect_introspect.py
```

Resultado esperado:

```
Tablas: ['usuarios']
  id: INTEGER
  nombre: TEXT
  email: TEXT
Fila: (1, 'Ana', 'ana@example.com')
```

## 5. Referencias Relacionadas

- **Documentación funcional**: [Gestión de Conexiones (Sync)](../functional/managers_sync.md) — objetivo de negocio del manager síncrono
- **Referencia técnica**: [Manager Síncrono](../api/managers_sync.md) — API completa de `SyncDatabaseManager`
- **Ejemplos relacionados**: [Queries Concurrentes (Async)](async_concurrent_queries.md) — versión asíncrona equivalente
