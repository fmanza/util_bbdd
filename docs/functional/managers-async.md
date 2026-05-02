## Objetivo de negocio

Permite ejecutar operaciones de base de datos de forma no bloqueante dentro de aplicaciones Python asíncronas (FastAPI, aiohttp, scripts de pipeline concurrente) sin penalizar el rendimiento del proceso principal. Las mismas operaciones que ofrece el manager síncrono — introspección de esquema, ejecución de queries, inventario de almacenamiento — están disponibles con `async/await` y un pool de conexiones gestionado automáticamente.

Es el punto de entrada recomendado para servicios web de alta concurrencia y pipelines que procesan múltiples bases de datos en paralelo.

## Precondiciones

- Python 3.10+ con soporte `asyncio`
- Driver async instalado para el motor objetivo (`asyncpg` para PostgreSQL, `aiomysql` para MariaDB/MySQL, etc.)
- Parámetros de conexión válidos incluyendo `database`
- Tipo de motor declarado: MariaDB, MySQL, PostgreSQL, Oracle, SQL Server, SQLite, Snowflake o Redshift
- El gestor **no conecta en el constructor**: es obligatorio llamar a `await init()` o usar `async with` antes de cualquier operación

## Flujo principal del usuario

```mermaid
sequenceDiagram
    actor App as Aplicación Async
    participant Mgr as AsyncDatabaseManager
    participant Pool as Pool async
    participant BD as Base de datos

    App->>Mgr: AsyncDatabaseManager(db_type, conn_params)
    Note over Mgr: Constructor solo pre-configura; NO conecta
    App->>Mgr: await init() ó async with
    Mgr->>Pool: Crear pool async (o conexión directa)
    Pool-->>Mgr: Pool listo

    loop Operaciones concurrentes
        App->>Mgr: await get_tables() / await execute_custom_many()
        Mgr->>Pool: Adquirir conexión
        Pool-->>Mgr: Conexión
        Mgr->>BD: Consultar
        BD-->>Mgr: Resultado
        Mgr->>Pool: Liberar conexión
        Mgr-->>App: Resultado (cacheado si es metadato)
    end

    App->>Mgr: await close() ó salida del async with
    Mgr->>Pool: Cerrar pool
```

## Reglas de negocio críticas

| Regla | Descripción | Impacto si se viola |
|---|---|---|
| Inicialización obligatoria | El constructor no conecta; toda operación sin `init()` activa inicialización perezosa automática | Sin `init()` explícito, la primera operación puede fallar con `ConnectionError` sin contexto claro |
| Pool con fallback | Si el motor no soporta pool async, cae silenciosamente a conexión directa | El comportamiento es correcto pero sin pool la concurrencia no se beneficia del pool |
| Caché de metadatos por sesión | Los metadatos de esquema se cachean en memoria desde la primera consulta | Cambios de esquema durante la sesión no se reflejan hasta reiniciar el gestor |
| Cierre explícito recomendado | `await close()` o `async with` garantizan liberación de recursos del pool | Sin cierre, el pool puede quedarse abierto hasta que el GC lo recoja (sin garantía de tiempo) |
| Parámetro `database` obligatorio | Debe estar presente en `conn_params` para todos los motores | `ValidationError` en construcción si falta |

## Límites y exclusiones

- No apto para código síncrono: todos sus métodos son corrutinas (`await` obligatorio)
- No realiza operaciones bulk (INSERT/UPDATE/DELETE masivo desde DataFrame): usar `bulk_crud` con el engine de SQLAlchemy
- No genera documentación ni informes: eso corresponde al módulo de documentación de BD
- No compara esquemas: eso corresponde al módulo de comparación
- HSQLDB (motor in-memory): recibe estrategia de almacenamiento síncrona; el manager lo detecta y lo maneja transparentemente
