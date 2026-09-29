# Gestión de Conexiones (Asíncrono)

## 1. Descripción General

Permite ejecutar operaciones de base de datos de forma no bloqueante dentro de aplicaciones Python asíncronas (FastAPI, aiohttp, scripts de pipeline concurrente) sin penalizar el rendimiento del proceso principal. Las mismas operaciones que ofrece el gestor síncrono — introspección de esquema, ejecución de queries, inventario de almacenamiento — están disponibles con `async/await` y un pool de conexiones gestionado automáticamente.

Es el punto de entrada recomendado para servicios web de alta concurrencia y pipelines que procesan múltiples bases de datos en paralelo.

**Precondiciones:**

- Python 3.10+ con soporte `asyncio`
- Driver async instalado para el motor objetivo (`asyncpg` para PostgreSQL, `aiomysql` para MariaDB y MySQL, etc.)
- Parámetros de conexión válidos incluyendo `database`
- Tipo de motor declarado: MariaDB, MySQL, PostgreSQL, Oracle, SQL Server, SQLite, Snowflake o Redshift
- El gestor no conecta en el constructor: es obligatorio inicializarlo explícitamente o usar el context manager async antes de cualquier operación

## 2. Reglas de Negocio

| Regla | Descripción | Impacto si se viola |
|---|---|---|
| Inicialización obligatoria | El constructor no conecta; toda operación sin inicialización activa una inicialización perezosa automática | Sin inicialización explícita, la primera operación puede fallar con error de conexión sin contexto claro |
| Pool con fallback | Si el motor no soporta pool async, cae silenciosamente a conexión directa | El comportamiento es correcto pero sin pool la concurrencia no se beneficia del pool |
| Caché de metadatos por sesión | Los metadatos de esquema se cachean en memoria desde la primera consulta | Cambios de esquema durante la sesión no se reflejan hasta reiniciar el gestor |
| Cierre explícito recomendado | Usar cierre explícito o context manager async garantiza liberación de recursos del pool | Sin cierre, el pool puede quedarse abierto hasta que el recolector de basura lo recoja |
| Parámetro `database` obligatorio | Debe estar presente en los parámetros de conexión para todos los motores | Error de validación en construcción si falta |

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
        App->>Mgr: await obtener_tablas() / await ejecutar_query()
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

**Motor sin pool async:** El gestor detecta que el motor no soporta pool async y cae automáticamente a conexión directa, sin error para el llamador.

**Límites y exclusiones:**

- No apto para código síncrono: todos sus métodos son corrutinas (`await` obligatorio)
- No realiza operaciones bulk (INSERT/UPDATE/DELETE masivo desde DataFrame): usar el módulo de operaciones bulk con el engine de SQLAlchemy
- No genera documentación ni informes
- No compara esquemas
- HSQLDB (motor in-memory): el gestor lo detecta y usa estrategia síncrona de forma transparente

## 4. Glosario y Términos

| Término | Definición |
|---|---|
| Corrutina | Función Python definida con `async def` que puede suspenderse y reanudarse, permitiendo concurrencia no bloqueante |
| Pool async | Conjunto de conexiones asíncronas mantenidas abiertas y reutilizadas entre operaciones concurrentes |
| Inicialización perezosa | Conexión que se establece en la primera operación real, no en el momento de crear el objeto |
