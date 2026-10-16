# util_bbdd

Librería Python para **operaciones de base de datos** sobre múltiples motores (sync/async): CRUD en lote, migración DDL, comparación de esquemas y documentación automática.

**Version:** 2.2.4 | **Status:** ✅ Production/Stable | **Python:** 3.12+

---

## 1. Identidad y Propósito

`util_bbdd` centraliza las operaciones habituales contra bases de datos relacionales detrás de una API uniforme, de modo que el mismo código sirva para MariaDB, MySQL, Oracle, PostgreSQL, SQLite, SQL Server y HSQLDB (este último solo en modo síncrono). Abstrae la conexión, el pooling y la introspección sobre `sqlalchemy`, y añade operaciones de alto nivel (carga masiva con auditoría, comparación de esquemas, migración DDL y generación de documentación).

Está dirigida a **desarrolladores, ingenieros de datos y DBAs** que necesitan mover datos, comparar entornos o documentar esquemas sin reescribir lógica específica por motor.

## 2. Capacidades Principales

- ✅ **Gestión de conexiones** sync (`SyncDatabaseManager`) y async (`AsyncDatabaseManager`) con pool
- ✅ **CRUD en lote** desde DataFrames (insert/update/delete masivo) con auditoría automática en CSV
- ✅ **Carga masiva paralela** (`ParallelBulkLoader`)
- ✅ **Introspección de metadatos** por lotes (`manager.get_schema_metadata()` → `SchemaSnapshot`, una consulta por tipo de objeto; contratos `SyncMetadataProvider`/`AsyncMetadataProvider`), cacheada en el manager hasta `clear_cache()`
- ✅ **Comparación de esquemas** (`SchemaComparator`, `SchemaDiff`) con reportes HTML/Excel/Word/Markdown/SQL
- ✅ **Migración DDL** entre motores (`MigrationPlanner`, `MigrationPlan`)
- ✅ **Volcado de datos** entre esquemas/motores (`DumpOrchestrator`, `DumpConfig`)
- ✅ **Documentación de BD** generada automáticamente (Word, Excel, HTML/Jinja2)
- ✅ **Análisis de relaciones** — grafos de relaciones entre tablas (Graphviz)

### API pública 1.0

La raíz `util_bbdd` exporta los 13 puntos de entrada y sus resultados (`SyncDatabaseManager`, `AsyncDatabaseManager`,
`BulkCrud`, `ParallelBulkLoader`, `DumpOrchestrator`, `DumpConfig`, `DumpResult`, `MigrationPlanner`, `MigrationPlan`,
`SchemaComparator`, `SchemaDiff`, `DatabaseDocumentation`, `DatabaseException`); el resto vive en submódulos públicos
(`util_bbdd.exceptions`, `.audit`, `.metadata`, `.connection`, `.factory`, `.analysis`, `.async_utils`). Desde 1.0.0
sigue SemVer. Si vienes de 0.x: [Migración a la API 1.0](guides/api_1_0_migration.md).

### Soporte por motor

| Motor      | Conexión Sync | Conexión Async | Pool Async | Driver principal |
|------------|:-------------:|:--------------:|:----------:|------------------|
| PostgreSQL | ✅            | ✅             | ✅         | `psycopg` 3 / `asyncpg` |
| SQLite     | ✅            | ✅             | ✅         | `aiosqlite`      |
| MariaDB    | ✅            | ✅             | ✅         | `mariadb` / `aiomysql` |
| MySQL      | ✅            | ✅             | ✅         | `pymysql` / `aiomysql` |
| Oracle     | ✅            | ✅             | ✅         | `oracledb`       |
| SQL Server | ✅            | ✅             | ✅         | `pyodbc` o `pymssql` / `aioodbc` |
| HSQLDB     | ✅            | ❌             | ❌         | `jaydebeapi`     |

!!! note
    `hsqldb` no dispone de implementación async en `util_bbdd`. Las factorías async lanzan error explícito para ese motor.

## 3. Quick Start

```bash
pip install "util_bbdd @ git+https://github.com/fmanza/util_bbdd.git@v1.1.0"
```

```python
from util_bbdd import SyncDatabaseManager

# SQLite en memoria: no requiere servidor externo
with SyncDatabaseManager(db_type="sqlite", conn_params={"database": ":memory:"}) as manager:
    manager.execute_custom_many("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    tablas = manager.get_tables()
    print("Tablas:", [t.name for t in tablas])
    # → Tablas: ['users']
```

## 4. Mapa de la Documentación

| Sección | Para qué sirve | Enlace |
|---|---|---|
| Instalación | Instalar el paquete, drivers y extras | [Guía de instalación](installation.md) |
| Arquitectura | Visión global del sistema y mapa de módulos | [Arquitectura del Sistema](architecture.md) |
| Documentación Funcional | Qué hace cada capacidad y por qué | [Operaciones Bulk](functional/bulk_operations.md) |
| Referencia Técnica | Cómo está construido (API, contratos) | [Índice de Referencia](api/intro.md) |
| Ejemplos | Patrones de implementación ejecutables | [Conectar e Introspeccionar](examples/example_connect_introspect.md) |
| Guías | Async, drivers, troubleshooting | [Programación Asíncrona](guides/async_guide.md) |

## 5. Compatibilidad y Soporte

La matriz de soporte por motor (sync/async, pool y driver) está en la tabla de la sección 2. Puntos clave:

- **Todos los motores** soportan conexión síncrona vía `SyncDatabaseManager`.
- **Todos excepto HSQLDB** soportan conexión y pool asíncronos vía `AsyncDatabaseManager`.
- Salvo `oracledb`, los **drivers no se incluyen** en la instalación básica: se instalan con el extra del motor o a mano (ver [Instalación](installation.md#3-drivers-por-motor)).

Más detalle:

- [Guía de instalación completa](installation.md)
- [Programación asíncrona](guides/async_guide.md)
- [Comparación de esquemas](guides/comparator.md)
- [Troubleshooting](guides/troubleshooting.md)
- [Referencia de API](api/intro.md)
