# util_bbdd

Librería Python especializada en **operaciones de base de datos** para MariaDB, Oracle, PostgreSQL, SQLite, SQL Server y HSQLDB (sync).

**Version:** 0.7.0 | **Status:** ✅ Estable | **Python:** 3.12+

---

## Características principales

- ✅ **CRUD en lote** desde DataFrames (insert/update/delete masivo)
- ✅ **Auditoría automática** en CSV con timestamps
- ✅ **Gestión de conexiones** con pool singleton
- ✅ **Gestión async** de conexiones/pools (por motor compatible)
- ✅ **Análisis de relaciones** — Generar grafos de relaciones
- ✅ **Documentación de BD** generada automáticamente
- ✅ **Plantillas HTML Jinja2 modulares** con páginas globales `Ver todo`
- ✅ **Comparación de esquemas** entre dos BDs con reportes HTML/Excel/Word/Markdown/SQL
- ✅ **Validación de tipos** por dialecto SQL
- ✅ **Arquitectura 3-level** jerárquica y modular

---

## Soporte Async por Motor

| Motor      | Conexión Async | Pool Async | Driver principal |
|------------|----------------|------------|------------------|
| PostgreSQL | ✅             | ✅         | `asyncpg`        |
| SQLite     | ✅             | ✅         | `aiosqlite`      |
| MariaDB    | ✅             | ✅         | `aiomysql`       |
| Oracle     | ✅             | ✅         | `oracledb`       |
| SQL Server | ✅             | ✅         | `aioodbc`        |
| HSQLDB     | ❌             | ❌         | N/A              |

!!! note
    `hsqldb` no dispone de implementación async en `util_bbdd`. Las factorías async lanzan error explícito para ese motor.

---

## ⏱️ Performance Monitoring

Operaciones CRUD bulk miden automáticamente su duración usando `util.timing`. Cada operación registra en CSV de auditoría: tabla, motor, total de filas, duración (segundos) y timestamp. Permite analizar tendencias y optimizar batch_size.

---

## ⚡ Quick Start (5 minutos)

### Instalación

```bash
pip install util_bbdd
```

### PostgreSQL — Sync

```python
from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="postgresql",
    conn_params={
        "host": "localhost",
        "port": 5432,
        "user": "postgres",
        "password": "secret",
        "database": "mydb"
    }
)

tables = manager.get_tables()
print("Tablas:", [table[0] for table in tables])

result = manager.execute_custom_many("SELECT * FROM users LIMIT 5")
print("Usuarios:", result)

manager.close()
```

### PostgreSQL — Async

```python
import asyncio
from util_bbdd import AsyncDatabaseManager

async def main():
    manager = AsyncDatabaseManager(
        db_type="postgresql",
        conn_params={
            "host": "localhost",
            "port": 5432,
            "user": "postgres",
            "password": "secret",
            "database": "mydb"
        }
    )
    await manager.init()
    tables = await manager.get_tables()
    print("Tablas:", [table[0] for table in tables])
    await manager.close()

asyncio.run(main())
```

=== "SQLite"

    ```python
    from util_bbdd import SyncDatabaseManager

    manager = SyncDatabaseManager(
        db_type="sqlite",
        conn_params={"database": ":memory:"}
    )
    manager.execute_custom_many("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
    print("Tablas:", manager.get_tables())
    manager.close()
    ```

=== "MariaDB"

    ```python
    from util_bbdd import SyncDatabaseManager

    manager = SyncDatabaseManager(
        db_type="mariadb",
        conn_params={"host": "localhost", "port": 3306, "user": "root",
                     "password": "secret", "database": "mydb"}
    )
    print("Tablas:", [t[0] for t in manager.get_tables()])
    manager.close()
    ```

=== "Oracle"

    ```python
    from util_bbdd import SyncDatabaseManager

    manager = SyncDatabaseManager(
        db_type="oracle",
        conn_params={"host": "localhost", "port": 1521, "user": "admin",
                     "password": "secret", "sid": "ORCL"}
    )
    print("Tablas:", [t[0] for t in manager.get_tables()])
    manager.close()
    ```

### ⏱️ Performance Monitoring

Operaciones CRUD bulk miden automáticamente su duración usando `util.timing`. Cada operación registra en CSV de auditoría: tabla, motor, total de filas, duración (segundos) y timestamp. Permite analizar tendencias y optimizar batch_size.


- [Guía de instalación completa](INSTALLATION.md)
- [Programación asíncrona](ASYNC_GUIDE.md)
- [Comparación de esquemas](COMPARATOR.md)
- [API Reference](api/intro.md)
- [Ejemplos de código](examples/schema_comparison.md)
