# Gestión de Conexiones (Asíncrono)

## 1. Descripción General

Permite ejecutar operaciones de base de datos de forma no bloqueante dentro de aplicaciones Python asíncronas (FastAPI, aiohttp, scripts de pipeline concurrente) sin penalizar el rendimiento del proceso principal. Las mismas operaciones que ofrece el gestor síncrono — introspección de esquema, ejecución de queries, inventario de almacenamiento — están disponibles con `async/await` y un pool de conexiones gestionado automáticamente.

Es el punto de entrada recomendado para servicios web de alta concurrencia y pipelines que procesan múltiples bases de datos en paralelo.

**Precondiciones:**

- Python 3.12+
- Driver async instalado para el motor objetivo (`asyncpg` para PostgreSQL, `aiomysql` para MariaDB y MySQL, `aiosqlite` para SQLite, `aioodbc` para SQL Server, `oracledb` para Oracle)
- Parámetros de conexión obligatorios del motor (los mismos que en el gestor síncrono)
- Tipo de motor declarado: MariaDB, MySQL, PostgreSQL, Oracle, SQL Server o SQLite
- El gestor no conecta en el constructor: conecta en `await init()`, al entrar en `async with` o, si no, en la primera operación

## 2. Reglas de Negocio

| Regla | Descripción | Impacto si se viola |
|---|---|---|
| Inicialización perezosa | El constructor no conecta; si no se llama a `init()`, la primera operación inicializa el gestor | Sin `init()` explícito, un error de conexión aparece en la primera operación en lugar de al arrancar |
| Caché de metadatos por sesión | Los metadatos de esquema se cachean en memoria desde la primera consulta | Cambios de esquema durante la sesión no se reflejan hasta invalidar la caché (`clear_cache()`) |
| Cierre explícito recomendado | Usar cierre explícito o context manager async garantiza liberación de recursos del pool | Sin cierre, el pool puede quedarse abierto hasta que el recolector de basura lo recoja |
| Validación de `conn_params` en el constructor | Desde v0.37.0, igual que el gestor sync: rechaza claves que el motor no admite, exige los parámetros requeridos de cada motor (p. ej. `host`, `user`, `password` y `database` en MariaDB, MySQL, PostgreSQL y SQL Server) y valida los valores (`schema`, `charset`, `sslmode`…) | `ValidationError` al construir el gestor; antes las claves desconocidas se descartaban sin aviso |
| `schema` por defecto | Sin `schema`, PostgreSQL usa `public` (también como `search_path` de la sesión), SQL Server `dbo` y HSQLDB `PUBLIC`, igual que el gestor sync | Antes de v0.37.0 el gestor async leía los metadatos del schema con el nombre de la base de datos |

## 3. Casos de Uso

### Flujo principal

```mermaid
sequenceDiagram
    actor App as Aplicación Async
    participant Mgr as Gestor Async de BD
    participant Pool as Pool Async
    participant BD as Base de datos

    App->>Mgr: Crear gestor (tipo motor, parámetros)
    Note over Mgr: Constructor solo pre-configura; NO conecta
    App->>Mgr: Inicializar (await init() o async with)
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

    App->>Mgr: Cerrar (await close() o salida del async with)
    Mgr->>Pool: Cerrar pool
```

### Flujos alternativos

**Uso como async context manager (recomendado):** Con `async with gestor:` se garantiza la inicialización y el cierre automáticos, incluso si se produce una excepción durante las operaciones.

**Límites y exclusiones:**

- No apto para código síncrono: todos sus métodos son corrutinas (`await` obligatorio)
- No realiza operaciones bulk (INSERT/UPDATE/DELETE masivo desde DataFrame): usar el módulo de operaciones bulk con el engine de SQLAlchemy
- No genera documentación ni informes
- No compara esquemas
- HSQLDB no tiene driver async: `AsyncDatabaseManager("hsqldb", ...)` falla con `NotImplementedError` al inicializarse; usar el gestor síncrono

## 4. Glosario y Términos

| Término | Definición |
|---|---|
| Corrutina | Función Python definida con `async def` que puede suspenderse y reanudarse, permitiendo concurrencia no bloqueante |
| Pool async | Conjunto de conexiones asíncronas mantenidas abiertas y reutilizadas entre operaciones concurrentes |
| Inicialización perezosa | Conexión que se establece en la primera operación real, no en el momento de crear el objeto |
