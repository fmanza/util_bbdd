# Managers

Los managers son el punto de entrada principal de `util_bbdd`.
Proveen la API de alto nivel para operaciones sobre bases de datos.

Los dos comparten los nombres del ciclo de vida: `init()`, `get_connection()`, `release_connection()` y `close()` (en el
async son corrutinas). `SyncDatabaseManager.close_connection()` se retiró en 1.0.0; ver
[Migración a la API 1.0](../guides/api_1_0_migration.md).

---

## SyncDatabaseManager

Manager sincrónico para operaciones de base de datos. Soporta todos los motores
(MariaDB, MySQL, PostgreSQL, Oracle, SQLite, SQL Server, HSQLDB). Referencia curada: [Manager Síncrono](managers_sync.md).

::: util_bbdd.managers.sync_mgr.SyncDatabaseManager
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"
        - "!^test"

---

## AsyncDatabaseManager

Manager asincrónico compatible con `asyncio`. Soporta PostgreSQL, SQLite, MariaDB, MySQL,
Oracle y SQL Server (HSQLDB no tiene driver async). Referencia curada: [Manager Asíncrono](managers_async.md).

!!! warning "Inicialización requerida"
    Llamar a `await manager.init()` antes de cualquier operación.

::: util_bbdd.managers.async_mgr.AsyncDatabaseManager
    options:
      show_source: false
      heading_level: 3
      members_order: source
      filters:
        - "!^_"
        - "!^test"
