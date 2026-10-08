# util_bbdd

Librería Python especializada en **operaciones de base de datos** para MariaDB, MySQL, Oracle, PostgreSQL, SQLite y SQL Server (sync y async), y HSQLDB (sync).

**Version:** 0.35.5 | **Status:** ✅ Estable | **Python:** 3.12+

---

## 🚀 Features principales

| Feature | Sync | Async | Soporta |
|---------|------|-------|---------|
| **CRUD en lote** | ✅ | ✅ | Insert/Update/Delete masivo desde CSV/DataFrame |
| **Async/Await** | ✅ | ✅ | PostgreSQL, SQLite, MariaDB, MySQL, Oracle, SQL Server |
| **Gestión de Pool** | ✅ | ✅ | Connection pooling + singleton + tuning |
| **Análisis de Schema** | ✅ | ✅ | Comparación de tablas, vistas, rutinas, índices |
| **Documentación BD** | ✅ | — | HTML + Word + Excel generado automáticamente |
| **Auditoría** | ✅ | ✅ | Logging de cambios con timestamps en CSV |
| **Performance Monitoring** | ✅ | ✅ | Timing automático en bulk CRUD, métricas en CSV audit |
| **Validación SQL** | ✅ | ✅ | Typechecking por dialecto de BD |
| **Validación MySQL** | ✅ | ✅ | Auto-lectura de variables críticas (max_allowed_packet, innodb_buffer_pool_size) + recomendaciones |
| **Grafos** | ✅ | ✅ | Generar relaciones (Mermaid + GraphViz) |
| **Migración DDL** | ✅ | — | Entre Oracle, MariaDB, SQL Server y PostgreSQL (12 combinaciones): tipos, FKs, secuencias, charset |
| **Volcado de Datos** | ✅ | — | Copia datos entre esquemas/motores, orden topológico FK, gestión de constraints, informe Excel |

---

## 🏗️ Workflow típico

```
┌─────────────────────────────────────────────────────────────┐
│                 Tu Aplicación Python                         │
└──────────────┬──────────────────────────────────────────────┘
               │
        ┌──────▼─────────┐
        │ SyncDatabase   │  Operaciones bloqueantes
        │  Manager       │  (scripts, cron jobs)
        └──────┬─────────┘
               │
        ┌──────▼──────────────┐
        │ AsyncDatabase      │  Operaciones no-bloqueantes
        │  Manager           │  (APIs, web servers, batch)
        └──────┬──────────────┘
               │
    ┌──────────▼──────────────┐
    │  Connection Pool        │
    │  (Singleton, tuned)     │
    └──────────┬──────────────┘
               │
    ┌──────────▼──────────────────────────────┐
    │        Base de Datos                     │
    │  PostgreSQL | MariaDB | Oracle | SQLite │
    │  SQL Server | HSQLDB (sync solo)         │
    └────────────────────────────────────────┘
```

**Flujo de decisión:**
- ¿Script/cron/offline? → Use `SyncDatabaseManager`
- ¿API/web/async? → Use `AsyncDatabaseManager`
- ¿Insertar 100k filas? → Use `BulkCrud.bulk_insert_from_df()` (CSV leído con `pandas.read_csv`)
- ¿Comparar 2 schemas? → Use `SchemaComparator`
- ¿Documentar BD? → Use `DatabaseDocumentation`
- ¿Migrar DDL entre motores (Oracle/MariaDB/SQL Server/PostgreSQL)? → Use `MigrationPlanner`
- ¿Volcar datos entre schemas/motores? → Use `DumpOrchestrator`

---

## Documentar una base de datos

`DatabaseDocumentation` genera documentación HTML, Word o Excel desde un `SyncDatabaseManager` síncrono. El constructor prepara la configuración y carga metadatos iniciales; la escritura de ficheros ocurre al llamar explícitamente a `generate()`.

```python
from pathlib import Path

from util_bbdd.doc import DatabaseDocumentation
from util_bbdd.managers import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="sqlite",
    conn_params={"database": "demo_documentation.db"},
    use_pool=False,
)

documentation = DatabaseDocumentation(
    db_manager=manager,
    directorio_salida=Path("generated_docs"),
    fichero_salida=Path("demo-sqlite"),
    imprimir={
        "tablas": {"imprimir_tablas": True, "ddl": True, "columnas": True},
        "vistas": {"imprimir_vistas": True, "ddl": True},
        "rutinas": {"imprimir_procedures": False, "imprimir_function": False},
    },
    formatos=["html"],
)
documentation.generate()
manager.close()
```

Formatos válidos: `word`, `excel`, `html`. Para un ejemplo completo y verificable con SQLite, consulta `docs/examples/database_documentation_generation.md`.

---

## Migrar DDL entre motores

`MigrationPlanner` genera el script SQL DDL de un schema completo adaptado al motor destino.
Soporta 4 motores origen × 3 motores destino (12 combinaciones: Oracle, MariaDB, SQL Server, PostgreSQL).

```python
from util_bbdd import MigrationPlanner

planner = MigrationPlanner(
    source_engine="oracle",   # "oracle" | "mariadb" | "sqlserver" | "postgresql"
    target_engine="mariadb",  # cualquier motor distinto al origen
    charset="utf8mb4",
    collation="utf8mb4_uca1400_ai_ci",  # por defecto; requiere MariaDB >= 10.10
)
plan = planner.plan(connection=oracle_manager, schema="VENTAS")

# Guardar script SQL
with open(plan.suggested_filename(), "w", encoding="utf-8") as f:
    f.write(plan.emit_ddl())

# Ver avisos de conversión
print(f"Errores: {plan.error_count}  Warnings: {plan.warning_count}")
```

**Columnas AUTO_INCREMENT hacia Oracle** (`oracle_identity_mode`):

| Modo | Comportamiento | Requiere |
|---|---|---|
| `"sequence_trigger"` (por defecto) | `CREATE SEQUENCE` + `CREATE OR REPLACE TRIGGER` | Oracle 11g+ |
| `"identity_by_default_on_null"` | `GENERATED BY DEFAULT ON NULL AS IDENTITY` inline | Oracle 12c+ |

```python
planner = MigrationPlanner(
    source_engine="mariadb",
    target_engine="oracle",
    oracle_identity_mode="identity_by_default_on_null",  # Oracle 12c+
)
```

El módulo también migra stored procedures y funciones (pass-through v1): el body se emite
verbatim con cabecera identificativa y aviso de revisión manual.

Consulta `docs/examples/migrate_mariadb_source.md` o `docs/examples/migrate_oracle_mariadb.md`
para ejemplos completos por motor.

---

## ⚡ Quick Start (5 minutos)

### Instalación

```bash
pip install util_bbdd

# Con soporte de documentación (Word/Excel/HTML)
pip install util_bbdd[doc]

# Con conversión SVG→PNG en memoria para Word (opcional, requiere Cairo)
# Permite reutilizar diagramas SVG generados para HTML al generar Word,
# evitando una segunda llamada a Graphviz por tabla.
pip install util_bbdd[doc-svg]

# Ambos extras a la vez
pip install util_bbdd[doc,doc-svg]
```

### PostgreSQL — Sync (más simple)

```python
from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="postgresql",
    conn_params={
        "host": "localhost", "port": 5432,
        "user": "postgres", "password": "secret",
        "database": "mydb"
    }
)

# Obtener tablas
tables = manager.get_tables()
print(f"Tablas: {len(tables)}")

# Obtener columnas
columns = manager.get_columns("users")
print(f"Columnas: {[(c.name, c.data_type) for c in columns]}")

# Ejecutar query
users = manager.execute_custom_many("SELECT * FROM users LIMIT 5")
print(f"Usuarios: {users}")

manager.close()
```

### PostgreSQL — Async (recomendado para APIs)

```python
import asyncio
from util_bbdd import AsyncDatabaseManager

async def main():
    manager = AsyncDatabaseManager(
        db_type="postgresql",
        conn_params={
            "host": "localhost", "port": 5432,
            "user": "postgres", "password": "secret",
            "database": "mydb",
            "pool_size": 10
        }
    )

    await manager.init()

    # Múltiples queries en paralelo
    tables, views, routines = await asyncio.gather(
        manager.get_tables(),
        manager.get_views(),
        manager.get_routines(),
    )

    print(f"Tablas: {len(tables)}, Vistas: {len(views)}")
    await manager.close()

asyncio.run(main())
```

### Volcado de Datos entre Motores

`DumpOrchestrator` copia datos de un esquema origen a otro destino (igual o distinto motor), detecta el orden topológico de carga por claves foráneas, gestiona constraints y genera un informe Excel de auditoría.

```python
from pathlib import Path
from sqlalchemy import create_engine
from util_bbdd.dump import DumpConfig, DumpOrchestrator

config = DumpConfig(
    source_engine=create_engine("postgresql+psycopg2://user:pw@src/db"),
    target_engine=create_engine("mssql+pymssql://user:pw@dst/db"),
    source_schema="public",
    target_schema="dbo",
    chunk_size=10_000,
    output_dir=Path("reports"),
    truncate_target=True,
)
result = DumpOrchestrator(config).run()
print(f"Informe: {result.report}")
print(f"Tablas cargadas: {sum(1 for t in result.table_results if t.status == 'success')}")
```

Para un ejemplo completo con troubleshooting e interpretación del informe Excel, consulta `docs/examples/dump_data_export.md`.

---

### SQLite — Más rápido para testing

```python
from util_bbdd import SyncDatabaseManager

# En memoria, no requiere BD externa
manager = SyncDatabaseManager(
    db_type="sqlite",
    conn_params={"database": ":memory:"}
)

manager.execute_custom_many(
    "CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)"
)

print("✅ BD de prueba lista")
manager.close()
```

---

## 📚 Documentación

| Tema | Descripción | Link |
|------|-----------|------|
| **Guías** | Programación async, drivers, troubleshooting | [Docs](docs/) |
| **API Reference** | Clases, métodos, tipos | [API](docs/api/intro.md) |
| **Ejemplos** | Casos de uso, snippets de código | [Examples](docs/examples/) |
| **Migration** | Actualizar de v0.6.6 → v0.6.7 | [Migration](docs/guides/migration_guide_v0.6.7.md) |
| **Benchmarks** | Performance, tuning, optimización | [Benchmarks](docs/guides/benchmarks.md) |

---

## 🔗 Soporte Async por Motor

| Motor      | Conexión | Pool | Driver | Performance |
|------------|----------|------|--------|-------------|
| PostgreSQL | ✅ | ✅ | `asyncpg` | ⭐⭐⭐ (Fastest) |
| SQLite     | ✅ | ✅ | `aiosqlite` | ⭐⭐ |
| MariaDB    | ✅ | ✅ | `aiomysql` | ⭐⭐ |
| MySQL      | ✅ | ✅ | `aiomysql` | ⭐⭐ |
| Oracle     | ✅ | ✅ | `oracledb` | ⭐⭐ |
| SQL Server | ✅ | ✅ | `aioodbc` | ⭐ |
| HSQLDB     | ❌ | ❌ | N/A | Sync only |

Recomendación: **PostgreSQL + asyncpg** para máxima performance.

---

## 💡 Copilot Workflow (Desarrollo)

El repositorio usa **Copilot Chat** + **Claude Code** para cambios estructurados:

```
Tu Tarea
  │
  ├─→ Workflow Director (clasificar)
  │     ├─→ New Feature? → Plan Architect
  │     ├─→ Bug? → Hotfix Responder
  │     └─→ Refactor? → Feature Implementer
  │
  └─→ Code Auditor (validar)
        └─→ Version Closer (mergear)
```

[Ver agentes disponibles](.github/AGENTS.md)

---

## 📊 Performance Tips

**Insertar 100k filas:**
```python
# ✅ Rápido: ~1 segundo
manager.bulk_insert_from_csv("users.csv", batch_size=10000)

# ❌ Lento: ~60 segundos
for row in rows:
    manager.execute_custom_many(
        "INSERT INTO users (id, name, email) VALUES (?, ?, ?)",
        params=(row["id"], row["name"], row["email"]),
    )
```

**Pool tuning:**
```python
# ✅ API con 100 usuarios concurrentes
manager = AsyncDatabaseManager(
    db_type="postgresql",
    conn_params={
        "host": "localhost",
        "user": "postgres",
        "password": "secret",
        "database": "mydb",
        "pool_size": 20,        # = 2x CPU cores
        "max_overflow": 10,
    },
)
```

**Metadatos por lotes:**
```python
# ✅ Una consulta por tipo de objeto para todo el schema, cacheada hasta clear_cache()
snapshot = manager.get_schema_metadata()
```

[Benchmarks completos →](docs/guides/benchmarks.md)

---

## Flujo de trabajo con Copilot

El repositorio define una capa combinada de instrucciones, prompts y agentes para trabajar con cambios funcionales, hotfixes, auditorías y cierres.

- Las reglas comunes a todas las plataformas IA están en [.github/SHARED_INSTRUCTIONS.md](.github/SHARED_INSTRUCTIONS.md); cada plataforma añade su especialización ([CLAUDE.md](CLAUDE.md), [.github/copilot-instructions.md](.github/copilot-instructions.md), [GEMINI.md](GEMINI.md), [AGENTS.md](AGENTS.md), [.cursorrules](.cursorrules)).
- Los agentes, prompts y slash commands disponibles están en [.github/AGENTS.md](.github/AGENTS.md).

Cadena recomendada para tareas complejas:

```text
Workflow Director -> Plan Architect -> Feature Implementer o Hotfix Responder -> Code Auditor -> Version Closer
```

Mapa rápido:

| Necesidad | Prompt habitual | Agente recomendado |
|---|---|---|
| Nueva funcionalidad | `new_feature` | `Plan Architect` y luego `Feature Implementer` |
| Hotfix acotado | `hotfix` | `Hotfix Responder` |
| Refactor sin cambio funcional | `refactor` | `Plan Architect` y luego `Feature Implementer` |
| Auditoría técnica | `audit_code` | `Code Auditor` |
| Revisión de seguridad | `security_review` | `Security Reviewer` |
| Cierre de versión o sesión | `version_closure` | `Version Closer` |

## Soporte Async por Motor

| Motor      | Conexión Async | Pool Async | Driver principal |
|------------|----------------|------------|------------------|
| PostgreSQL | ✅             | ✅         | `asyncpg`        |
| SQLite     | ✅             | ✅         | `aiosqlite`      |
| MariaDB    | ✅             | ✅         | `aiomysql`       |
| MySQL      | ✅             | ✅         | `aiomysql`       |
| Oracle     | ✅             | ✅         | `oracledb`       |
| SQL Server | ✅             | ✅         | `aioodbc`        |
| HSQLDB     | ❌             | ❌         | N/A              |

Nota: `hsqldb` no dispone de implementación async en `util_bbdd`. Las factorías async lanzan error explícito para ese motor.

manager.close()
```

### MariaDB / MySQL

```python
from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="mariadb",  # o "mysql"
    conn_params={
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "secret",
        "database": "mydb"
    }
)

tables = manager.get_tables()
print("Tablas:", [table[0] for table in tables])

manager.close()
```

### Oracle

```python
from util_bbdd import SyncDatabaseManager

manager = SyncDatabaseManager(
    db_type="oracle",
    conn_params={
        "host": "localhost",
        "port": 1521,
        "user": "admin",
        "password": "secret",
        "sid": "ORCL"  # o "service_name": "xepdb1"
    }
)

tables = manager.get_tables()
print("Tablas:", [table[0] for table in tables])

manager.close()
```

#### 📌 Ver más

- [Guía de instalación completa](docs/installation.md)
- [Guía de excepciones](docs/guides/exceptions.md)
- [SchemaComparator — Comparación de esquemas](docs/guides/comparator.md)

---

## Arquitectura v0.10.0 — Estructura de 3 Niveles (Estable)

Util_bbdd usa una **arquitectura jerárquica de 3 niveles** para máxima modularidad, extensibilidad y separación de responsabilidades:

### Level 1: Abstracciones Internas (Foundation Layer)

Define tipos, excepciones y contratos. **Regla:** No importar desde Level 2 ni 3.

```
_core/               # Tipos y contratos fundamentales
  ├── types.py       # Type aliases (RowOrNone, Rows, etc.)
  ├── exceptions.py  # Jerarquía unificada de excepciones (DatabaseException raíz)
  ├── contracts.py   # Protocols/interfaces (ConnectionProvider, etc.)
  └── constants.py   # Enums compartidos

_drivers/            # Gestión de drivers (no desde Level 2+)
  ├── validator.py   # DatabaseTypeValidator: valida motores desde database_types.json
  ├── driver_validator.py # DriverValidator: detecta disponibilidad de drivers Python
  └── _config_loader.py # Carga y tipado del JSON de configuración

core/
  └── capabilities.py # Motor capabilities (async support, features)
```

**Beneficio:** Punto único de verdad para excepciones y contratos; facilita evolución sin quebrantar interfaces.

### Level 2: Capas de Acceso (Services Layer)

Operaciones core reutilizables entre managers. **Regla:** Importa solo de capas inferiores (Level 1 y capas previas de Level 2); nunca de Level 3.

```
connection/          # Conexiones y configuración por motor
  ├── factory.py     # Creación de conexiones (sync/async)
  ├── builder.py     # build_conn_params() por motor
  ├── protocols.py   # ConnectionPoolProtocol
  ├── close.py       # Cierre de conexiones y cleanup
  ├── params.py      # Normalización de parámetros
  ├── config.py      # Configuración de conexión
  └── {hsqldb,mariadb,oracle,postgresql,sqlite,sqlserver}/ # Adaptadores y pools por motor

executors/           # Ejecución de queries (paquete de nivel superior)
  ├── base.py        # QueryExecutorBase (abstract)
  ├── sync_query_executor.py
  └── async_query_executor.py

query/               # Registry y resolución de queries
  ├── registry.py    # QueryRegistry: carga y acceso a definiciones JSON
  ├── resolver.py    # QueryResolver: resuelve placeholders en queries
  └── queries.py     # DatabaseQueries: wrapper de conveniencia

metadata/            # Lectura del catálogo (ADR-003): único punto de SQL de introspección
  ├── source.py      # CatalogSource: una consulta por tipo de objeto → SchemaSnapshot
  ├── model.py       # SchemaSnapshot y modelos neutros (TableMeta, ColumnMeta, ForeignKeyMeta…)
  ├── snapshot_cache.py  # Caché LRU de snapshots por schema
  ├── catalog_registry.py  # CatalogDialect por motor
  ├── reflection.py  # Tipos y objetos de SQLAlchemy por lotes (comparar, dump, bulk)
  ├── facts.py       # Consultas puntuales (secuencias, identidad, permisos…)
  ├── ddl.py         # DDL de tablas, vistas y routines
  ├── storage.py     # Inventario de almacenamiento
  ├── contracts.py   # Protocols (MetadataSource, CatalogDialect, Sync/AsyncMetadataProvider)
  └── {hsqldb,mariadb,oracle,postgresql,sqlite,sqlserver}/ # catalog.py (CatalogDialect) y SQL puntual por motor

results/             # Normalización de resultados
  ├── types.py       # RowOrNone, Rows, tipos de resultado
  └── normalizer.py  # ResultNormalizer

factory/             # SQLAlchemy engines
  ├── pool_factory.py
  ├── sqlalchemy_engine_factory.py
  └── async_sqlalchemy_engine_factory.py

validators/          # Validadores de parámetros por motor
  ├── base_validator.py # DatabaseTypeValidator (ABC) + get_type_validator()
  └── {mariadb,oracle,postgresql,hsqldb,sqlserver,sqlite}_validator.py
```

**Beneficio:** Módulos de responsabilidad única, acotados y fáciles de testear en aislamiento.

### Level 3: Especialización (Domain Logic Layer)

Funcionalidad de dominio construida sobre Level 2. **Regla:** Puede importar de Level 1, Level 2 y capas inferiores de Level 3; nunca al revés.

```
managers/            # APIs públicas de alto nivel
  ├── sync_mgr.py    # SyncDatabaseManager: interfaz principal sync
  └── async_mgr.py   # AsyncDatabaseManager: interfaz principal async

bulk/                # Operaciones masivas
  ├── crud.py        # Bulk INSERT/UPDATE/DELETE desde DataFrames
  ├── audit.py       # AuditManager para tracking de cambios
  ├── normalize.py   # Normalización de registros para SQL
  └── _execution/, _audit/, _support/ # Estrategias INSERT por motor, auditoría y utilidades internas

analysis/            # Análisis de relaciones multinivel
  ├── base.py        # GraphDocument, niveles, traversal, dirección, tipología visual
  ├── graphviz_ext.py # Graphviz multinivel con columnas, cardinalidad, leyenda
  └── matplotlib_graph.py # Matplotlib alineado al modelo multinivel

comparar/            # Comparación de esquemas (NEW in v0.6.7)
  ├── comparator.py  # SchemaComparator.compare(source, target) → SchemaDiff
  ├── contracts.py   # Tipos y contratos de comparación
  ├── models.py      # SchemaDiff (frozen dataclasses), resultados tipados
  └── reporters/     # Reporters Excel/HTML/Markdown/SQL/Word del diff

doc/                 # Documentación de BD (arquitectura hexagonal)
  ├── database_documentation.py # Punto de entrada del generador
  ├── application/   # Casos de uso y puertos (documentation_orchestrator, ports)
  ├── domain/        # Modelos y servicios de dominio
  ├── infrastructure/ # Renderers (html/excel/word), storage por motor, runtime, adapters
  └── templates/     # Plantillas Jinja2 modulares (layouts, macros, pages)

[Otros: módulos raíz; async_utils.py y models.py cuentan como Level 1 (no importan nada de la librería)]
├── async_utils.py   # Helpers (maybe_await, etc.)
├── models.py        # Modelos de dominio compartidos
└── data/            # Data fixtures para tests
```

**Beneficio:** Dominio enfocado, sin acoplamiento a infraestructura; fácil agregar nuevos formatos/motores sin editar Level 2.

### Regla de Imports (Flujo Prohibido ↔ Permitido)

```
✅ PERMITIDO (solo hacia capas de número menor)
   Level 1 imports ← capas inferiores de Level 1 (p. ej. _drivers → _core)
   Level 2 imports ← Level 1 y capas inferiores de Level 2 (p. ej. factory → connection)
   Level 3 imports ← Level 1, Level 2 y capas inferiores de Level 3 (p. ej. dump → bulk)

❌ PROHIBIDO
   Importar de una capa superior o de la misma capa, aunque no cierre un ciclo
   Level 2 imports from Level 3; Level 1 imports from Level 2 o 3
   Ciclos entre paquetes (los imports perezosos cuentan)
```

Lo comprueba `tests/unit/test_architecture_import_rules.py`.

### Compatibilidad Viva (v0.10.0)

La ruta recomendada para código nuevo usa **imports canónicos** desde la raíz del paquete. Rutas legacy se mantienen solo como transición.

| Componente | Import Canónico (Recomendado) | Ruta Legacy (Deprecated) |
|---|---|---|
| Manager sync | `from util_bbdd import SyncDatabaseManager` | `from util_bbdd.database_manager import DatabaseManager` |
| Manager async | `from util_bbdd import AsyncDatabaseManager` | `from util_bbdd.async_database_manager import AsyncDatabaseManager` |
| Bulk operations | `from util_bbdd.bulk import bulk_crud, AuditManager` | `from util_bbdd.bulk_crud import bulk_crud, AuditManager` |
| Analysis graphs | `from util_bbdd.analysis import GraphvizRelationshipGraphExt` | `from util_bbdd.grafos import GraphvizRelationshipGraphExt` |
| Comparator | `from util_bbdd import SchemaComparator, SchemaDiff` | N/A (nuevo en v0.6.7) |
| Driver validator | `from util_bbdd._drivers.validator import DatabaseTypeValidator` | `from util_bbdd.database_type_validator import DatabaseTypeValidator` |

**Notas de compatibilidad activa:**

- El código nuevo debe preferir la superficie canónica expuesta desde `util_bbdd`, `util_bbdd.managers`, `util_bbdd.bulk` y `util_bbdd.analysis`.
- Las rutas legacy se mantienen para no romper integraciones existentes, pero ya no son la referencia principal en ejemplos ni en migraciones.
- `get_storage_inventory()` usa el contrato actual por capacidades: `primary`, `temp_tablespaces` y `sqlite_file_summary` cuando aplica.
- La guía de detalle para migrar imports y contratos está en [docs/guides/migration_guide.md](docs/guides/migration_guide.md).

## ✨ Novedades v0.10.0 (Estable Vigente)

### Vías rápidas de INSERT por motor (bulk)
- `InsertStrategyResolver` elige automáticamente la vía nativa más rápida por motor (default `insert_resolver=None`)
- **PostgreSQL**: `COPY ... FROM STDIN` vía psycopg3 (streaming por STDIN, sin staging a disco)
- **MySQL/MariaDB**: `INSERT ... VALUES (...),(...)` multi-fila, sub-loteado por `max_rows_per_statement` (default 1000)
- Oracle, SQL Server, SQLite y HSQLDB siguen con `executemany` (SQL Server acelerado por `fast_executemany`)
- Output idéntico; cambia solo el mecanismo de ejecución (degradación automática a `executemany` cuando aplica)

### Volcado con resolución única por tabla (dump)
- `DumpOrchestrator` reutiliza la resolución de columnas y estrategia de identidad **una sola vez** por tabla
- El renombrado de columnas se aplica de forma perezosa por chunk, manteniendo el streaming

> Detalle completo en [CHANGELOG.md](CHANGELOG.md) y en la tabla "Estrategias INSERT por motor" de [docs/api/bulk_crud.md](docs/api/bulk_crud.md).

---

## 📚 Resumen de Evolución (v0.6.0 → v0.32.1)

### v0.6.2 - Cierre Documental Offline
- Relaciones de n niveles mediante `max_depth`; dirección `incoming`, `outgoing` o `both`
- Cardinalidad en Graphviz; HTML multinivel con pestañas; SVG inline con zoom/paneo

### v0.6.3 - Agentes de Copilot & Flujo Prompt
- Capa de agentes y flujo prompt-agente documentado
- Instrucciones especializadas por archivo (`.instructions.md`)
- Mapeo Copilot Chat ↔ Claude Code

### v0.6.4 → v0.6.6 - Consolidación & API Pública
- Capa de managers estabilizada (`SyncDatabaseManager`, `AsyncDatabaseManager`)
- Testeo multinivel; arquitectura 3 niveles como standard

### v0.6.7 - Comparador de Esquemas
- `SchemaComparator` integrado: difr entre esquemas source/target
- Imports canónicos desde `util_bbdd`, instrucciones especializadas por módulo

### v0.7.0 - Monitorización de Rendimiento
- Medición automática en bulk CRUD (`tiempo_seg` en auditoría)

### v0.8.0 - Tipos Avanzados (Oracle, SQL Server, etc.)
- Introspección completa de tipos en los 8 motores
- Soporte OBJECT types, hierarchical, etc.

### v0.9.0 - Optimizaciones de Rendimiento (Dump)
- Cadencia de commit configurable
- Paralelización por tablas y rangos de PK
- Todas las optimizaciones opt-in (desactivadas por defecto)

### v0.10.0 - Vías Rápidas de INSERT
- PostgreSQL `COPY ... FROM STDIN` automático (streaming sin staging a disco)
- MySQL/MariaDB multi-fila sub-loteada por motor
- Degradación automática a `executemany` cuando no aplica

### v0.11.0 → v0.27.0 - Consolidación & Auditoría Centralizada
- Refactoring de managers y conexiones por motor
- Módulo de auditoría centralizado (`audit/`)
- Optimizaciones de metadata y cache

### v0.28.0 → v0.29.0 - Soporte Mejorado de Motores
- Driver validation y diagnostics mejorados
- Soporte PostgreSQL driver alternativo, MySQL async improvements
- Manejo robusto de timezones y charset

### v0.30.0 - Metadata Refactor & Rendimiento
- Búfer de metadatos optimizado, cache LRU mejorado
- Conversión de tipos avanzada (Oracle LOB duck-typing robusto)

### v0.31.0 → v0.31.2 - Oracle 11g Preliminary Support
- Detección de versión Oracle (11g vs 12c+)
- Captura silenciosa de ORA-00942 en queries identidad (11g pre-fix)

### v0.32.0 - Soporte Completo Oracle 11g (Lazy Version Resolution)
- **Resolución perezosa de versión Oracle**: primera consulta detecta versión y carga `Oracle11Catalog` (11g) u `OracleCatalog` (12c+)
- **Thick Mode seguro**: inicialización thread-safe en `connection/oracle/_thick_mode.py`; async lanza guard error
- **21 nuevas pruebas de integración** para Oracle 11g/12c+
- [docs/adr/ADR-004](docs/adr/ADR-004-lazy-oracle-version-resolution.md) — decisión arquitectónica

### v0.32.1 - Hotfix P2: MariaDB Unicode Decode & Deuda Técnica
- **MariaDB charset fix**: fuerza `utf8mb4` en `MariaDBConnectionConfig` (resuelve `UnicodeDecodeError` en documentación)
- **Deuda técnica (5 items)**: exception chain inspection centralizado, retry logic configurable, rollback logging, driver paramstyle extensible, Oracle LOB robust detection
- **Convención de salida**: test results ahora en `build/logs/` (no en raíz)
- **100% backward compatible**: sin cambios en API pública

---

### Tipología Visual de Tablas (v0.6.2+, vigente)

La clasificación visual de tablas en diagramas NO sustituye el modelo de datos real, sino que ofrece ayuda visual heurística:

- `entity`: tabla de negocio general (color azul pastel)
- `association`: tabla puente detectada por múltiples FKs (color verde pastel)
- `hierarchy`: tabla autorreferencial con relación padre-hijo (color naranja pastel)

Si un esquema contiene tablas híbridas o patrones muy específicos por motor, la tipología debe interpretarse como ayuda visual y no como clasificación canónica.

### Configuración recomendada del bloque grafo

```toml
[imprimir_config.imprimir.grafo]
enabled = true
show_columns = true
max_depth = 3
direction = "both"
images_paginated = true
max_subnodes = 10

[imprimir_config.imprimir.grafo.summary]
enabled = true

[imprimir_config.imprimir.grafo.columns]
mode = "relations"
max_items = 8
show_data_types = false

[imprimir_config.imprimir.grafo.cardinality]
style = "end_markers"
show_constraint_name = false
```

`show_columns` sigue siendo el interruptor global para el detalle tabular del grafo:

- `true`: se muestran columnas segun `grafo.columns.mode`
- `false`: los nodos se renderizan sin columnas aunque el bloque `grafo.columns` exista

### Ejemplo completo de imprimir_config

Existía un ejemplo completo y autocomentado en `docs/examples/imprimir_config_full_example.toml`, retirado
de `docs/` junto con la documentación histórica (commit `be8232e`). Se recupera con:

```bash
git show be8232e^:docs/examples/imprimir_config_full_example.toml
```

Ese fichero documenta todas las secciones soportadas hoy por `imprimir`:

- tablas
- vistas
- rutinas
- almacenamiento
- columnas_charset
- info_database
- grafo
- opciones generales de Word y HTML

### Ejemplo de uso de diagramas multinivel

```python
from util_bbdd.analysis import GraphvizRelationshipGraphExt

graph = GraphvizRelationshipGraphExt(
  db_manager=dm,
  max_depth=3,
  direction="both",
  column_mode="relations",
  max_columns=8,
  show_data_types=False,
)

graph.generate_graphviz_graph_paginated_ext(
  table_name="users",
  output_dir="./graphs",
  format="svg",
  max_subnodes=10,
)
```

---

## Instalación

Requiere **Python 3.12 o superior**.

### Desde PyPI (futuro)
```bash
pip install util_bbdd
```

### Desde fuente (desarrollo)
```bash
git clone https://github.com/fmanza/util_bbdd.git
cd util_bbdd
py -m venv venv
# Windows: si PowerShell bloquea el script (política "Restricted" por defecto), ejecuta antes:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1  # Windows
pip install -e ".[dev]"
```

## Uso Rápido

### Inserción masiva desde DataFrame

```python
from util_bbdd.bulk import bulk_crud
import pandas as pd
from sqlalchemy import create_engine

# Crear engine
engine = create_engine("mysql+pymysql://user:password@localhost/database")

# Crear DataFrame con datos
df = pd.DataFrame({
    'id': [1, 2, 3],
    'name': ['Alice', 'Bob', 'Charlie'],
    'email': ['alice@ex.com', 'bob@ex.com', 'charlie@ex.com']
})

# Inicializar CRUD con auditoría
crud = bulk_crud_audit(
    engine=engine,
    table_name='users',
    audit_csv_path='audit.csv'
)

# Insertar en lote
crud.bulk_insert_from_df(df)
print("✅ Inserción completada")

# Ver auditoría
df_audit = pd.read_csv('audit.csv')
print(df_audit)
```

### Pool de Conexiones

```python
from util_bbdd.connection import PoolFactory

# Crear pool singleton
pool = PoolFactory.create(
    database_type='mysql',
    host='localhost',
    user='root',
    password='secret',
    database='mydb'
)

engine = pool.get_engine()
print(f"✅ Conexión establecida: {pool}")
```

## API Unificada: SyncDatabaseManager (v0.2.0+)

### Uso Síncrono

```python
from util_bbdd import SyncDatabaseManager

# Inicializar gestor de BD
dm = SyncDatabaseManager(
    db_type='mariadb',
    conn_params={
        'host': 'localhost',
        'user': 'root',
        'password': 'secret',
        'database': 'mydb'
    }
)

# Introspection: Listar tablas
tables = dm.get_tables()
print(f"📊 Tablas: {tables}")

# Introspection: Columnas de tabla
columns = dm.get_columns('users')
print(f"📋 Columnas: {columns}")

# Ejecutar query registrada en tu fichero de consultas (SyncDatabaseManager(..., queries_file=Path("consultas.json")))
result = dm.execute_query_many('clientes_activos', pais='ES')
first_row = dm.execute_query_one('total_pedidos')
print(f"🔍 Resultado: {result} | Primera fila: {first_row}")

# Ejecutar SQL custom (many / one)
result = dm.execute_custom_many('SELECT * FROM users LIMIT 10')
ping = dm.execute_custom_one('SELECT 1')
print(f"✅ Consulta ejecutada: {len(result)} filas")

# Cierra conexión
dm.close()
```

### Uso Asíncrono (v0.2.0+)

```python
import asyncio
from util_bbdd.managers import AsyncDatabaseManager

async def main():
    # Inicializar gestor async
    adm = AsyncDatabaseManager(
        db_type='postgresql',
        conn_params={
            'host': 'localhost',
            'user': 'postgres',
            'password': 'secret',
            'database': 'mydb'
        }
    )

    # Inicialización lazy
    await adm.init()

    # Misma API que sync, pero con await
    tables = await adm.get_tables()
    print(f"📊 Tablas: {tables}")

    columns = await adm.get_columns('users')
    print(f"📋 Columnas: {columns}")

    # Ejecutar query registrada en tu fichero de consultas (many / one)
    result = await adm.execute_query_many('clientes_activos', pais='ES')
    first_row = await adm.execute_query_one('total_pedidos')
    print(f"🔍 Resultado: {result} | Primera fila: {first_row}")

    await adm.close()

# Ejecutar
asyncio.run(main())
```

### Excepciones Unificadas (v0.2.0+)

| Excepción | Cuándo | Uso |
|-----------|--------|-----|
| `QueryNotFoundError` | Query no existe | `.handle_missing_query()` |
| `QueryValidationError` | Parámetros inválidos | `.validate_params()` |
| `QueryParameterError` | Parámetro específico inválido | `.check_param()` |
| `QueryTimeoutError` | Timeout en ejecución | `.retry_with_timeout()` |
| `DatabaseConnectionError` | Fallo de conexión | `.reconnect()` |
| `DatabasePoolError` | Pool exhausto/timeout | `.wait_for_pool()` |
| `DatabaseOperationError` | Error en operación SQL | `.handle_sql_error()` |

**Migración desde v0.1.x:**
```python
# v0.1.x (deprecated)
try:
    query = dq.get_query('nonexistent')
except KeyError:
    print("Query not found")

# v0.2.0+ (nuevo)
from util_bbdd.database_exceptions import QueryNotFoundError

try:
    query = dq.get_query('nonexistent')
except QueryNotFoundError as e:
    print(f"Query not found: {e}")
```

### Motores Soportados

| Motor      | Sync | Async | Validadores Avanzados | Versión +0.2 |
|------------|------|-------|----------------------|-------------|
| MariaDB    | ✅   | ✅    | ✅ Charset, Database | ✅         |
| Oracle     | ✅   | ✅    | ✅ Schema (max 30ch) | ✅         |
| PostgreSQL | ✅   | ✅    | ✅ Schema, Database  | ✅         |
| HSQLDB     | ✅   | ❌    | ✅ Table Names       | ✅         |
| SQL Server | ✅   | ✅    | ✅ Schema, Database  | ✅         |
| SQLite     | ✅   | ✅    | ✅ Minimal Params    | ✅         |

## Changes in v0.2.0

### ⚠️ Breaking Changes
- `DatabaseQueryError` alias removed
- `DatabaseQueries._load_queries()` → Now internal (delegated to QueryRegistry)
- Exception hierarchy unified under `DatabaseError` base class
- Public execution API now split and strict:
  - Removed: `execute_query(..., fetch_one=...)`
  - Removed: `execute_custom_query(..., fetch_one=...)`
  - Use: `execute_query_many/execute_query_one`
  - Use: `execute_custom_many/execute_custom_one`

### ✅ New Features
- `SyncDatabaseManager.execute_query_many(query_name, **params)` - Execute by query name (many)
- `SyncDatabaseManager.execute_query_one(query_name, **params)` - Execute by query name (one)
- `AsyncDatabaseManager` - Full parity with sync version
  - `get_tables()`, `get_views()`, `get_columns()`, `get_routines()`
  - `execute_query_many() / execute_query_one()` support
- `get_storage_inventory()` usa claves explícitas por capacidad:
  - `primary`
  - `temp_tablespaces` cuando aplica
  - `sqlite_file_summary` en SQLite
- HTML `Ver todo` incorpora exportación filtrada:
  - `CSV` / `TSV` en UTF-8
  - `XLSX` real
  - `PDF` vía impresión
- Advanced validators per database motor
- Query Registry + Resolver architecture
- Improved error messages with `raise ... from err` pattern
- Comprehensive logging at DEBUG level

---

## 🆕 What's New in v0.5.0

> **Nota histórica.** Esta sección documenta el estado en **v0.5.0** y se conserva como registro.
> Para la estructura vigente consulta [Arquitectura v0.10.0](#arquitectura-v0100--estructura-de-3-niveles-estable).
> Algunas cifras de líneas y rutas internas han evolucionado desde entonces.

**Major Refactoring:** Arquitectura 3-level jerárquica + consolidación de módulos

### ✅ What Changed (Internal)
- ✅ **Reorganización arquitectónica** (Level 1, 2, 3)
- ✅ **3 nuevos módulos especializados**: `bulk/`, `analysis/`, `managers/`
- ✅ **~8,500 líneas** refactorizadas y consolidadas
- ✅ Compatibilidad mantenida en wrappers legacy seleccionados

### 🆕 New Modules (v0.5.0+)

#### `managers/` - Consolidated DB Managers
- `managers.sync_mgr.SyncDatabaseManager`
- `managers.async_mgr.AsyncDatabaseManager`
- **Same API as before**, better code organization

```python
# v0.6.0+ (recommended)
from util_bbdd.managers import SyncDatabaseManager
# Or even simpler:
from util_bbdd import SyncDatabaseManager
```

#### `bulk/` - Bulk Operations Module
- `bulk/crud.py` - Bulk insert/update/delete from DataFrames
- `bulk/audit.py` - Audit trail with transactions
- `bulk/normalize.py` - SQL normalization utilities

```python
# ruta canónica actual
from util_bbdd.bulk import bulk_crud, AuditManager

# ruta canónica ampliada
from util_bbdd.bulk import bulk_crud, AuditManager, normalize_records_for_sql
```

#### `analysis/` - Relationship Graph Analysis
- `analysis/base.py` - Base classes for graph analysis
- `analysis/graphviz_ext.py` - Extended Graphviz with columns/types
- `analysis/matplotlib_graph.py` - Matplotlib/NetworkX visualization

```python
# ruta canónica estable
from util_bbdd.analysis import GraphvizRelationshipGraphExt

# ruta canónica ampliada
from util_bbdd.analysis import (
    DatabaseRelationshipGraphBase,
    GraphvizRelationshipGraphExt,
    MatplotlibRelationshipGraph
)
```

### 📚 Imports canónicos y compatibilidad legacy

| Componente | Import canónico | Ruta legacy aún soportada |
|-----------|-----------------|---------------------------|
| SyncDatabaseManager | `from util_bbdd import SyncDatabaseManager` | `from util_bbdd.database_manager import DatabaseManager` |
| AsyncDatabaseManager | `from util_bbdd import AsyncDatabaseManager` | `from util_bbdd.async_database_manager import AsyncDatabaseManager` |
| Bulk Operations | `from util_bbdd.bulk import bulk_crud, AuditManager` | `from util_bbdd.bulk_crud import bulk_crud, AuditManager` |
| Analysis Graphs | `from util_bbdd.analysis import GraphvizRelationshipGraphExt` | `from util_bbdd.grafos import GraphvizRelationshipGraphExt` |

**Nota:** para código nuevo, usa siempre la superficie canónica. Las rutas legacy quedan solo como compatibilidad transitoria.

Para el núcleo de grafos de relaciones en v0.6.0:
- usa `util_bbdd.analysis.base` como ubicación canónica
- `util_bbdd.bulk.base` fue eliminado y ya no está disponible

### 📖 Documentation (v0.6.0+)

- [**migration_guide.md**](docs/guides/migration_guide.md) - Guía viva de migración y compatibilidad para la superficie pública actual
- [**legacy_versions.md**](docs/legacy_versions.md) - Versiones históricas
- La guía de migración de v0.6.0, la bitácora de refactorización y el refactor de Jinja2 de v0.5.6 se retiraron de
  `docs/` (commit `be8232e`); siguen en el historial de git.

### 🧪 Testing
- Usa las tareas del workspace para validar el estado real actual: `test`, `lint`, `type-check` y `build`.
- `v0.6.0` introduce breaking changes en grafos/documentación y en paths internos retirados; la compatibilidad legacy documentada en `v0.6.3` no revierte esos cambios funcionales.
- La cobertura histórica sigue centrada en paths críticos; toma `pytest` y `htmlcov/` como fuente de verdad del estado vigente.

### 🔄 Deprecation Policy
- v0.5.0: Legacy paths (`bulk_crud/`, `grafos/`) work but discouraged for new code
- v0.6.0: `util_bbdd.bulk.base` eliminado; migra a `util_bbdd.analysis.base`
- v1.0.0: New paths only

---

## Changes in v0.2.0

(See above for v0.5.0 changes)

## Tests

```bash
# Ejecutar tests
pytest tests/ -v --cov=src/util_bbdd

# Con HTML report
pytest tests/ --cov=src/util_bbdd --cov-report=html
# Abrira: htmlcov/index.html
```

## Dependencias

| Paquete     | Uso                           | Versión   |
|-------------|-------------------------------|-----------|
| SQLAlchemy  | ORM y construcción SQL        | >=2.0     |
| pandas      | DataFrames para CRUD          | >=2.3     |
| oracledb    | Driver Oracle                 | >=3.4     |
| openpyxl    | Exportación Excel (auditoría) | >=3.1     |
| python-docx | Generación de Word (docs BD)  | >=1.2     |

## Versionado

Usamos [Semantic Versioning](https://semver.org/):
- `0.x.y` (alpha/beta): APIs experimentales, cambios frecuentes
- `1.0.0` (stable): API estable, cambios siguiendo SemVer

**Current Version: v0.35.5** (hotfix de seguridad: credenciales escapadas en las URLs de Engine; el Engine aplica TLS y charset de `conn_params`; `oracle_thick_mode` y `close_timeout` aceptados)

Roadmap resumido (ver [ROADMAP completo](docs/roadmap.md) y
[CHANGELOG](CHANGELOG.md) para el detalle):
- `v0.1.0 – v0.4.0` ✅: CRUD base + auditoría, documentación de BD, PostgreSQL, primera estable
- `v0.5.0` ✅: Refactorización arquitectónica (jerarquía de 3 niveles)
- `v0.6.x` ✅: Grafos multinivel, HTML tabulado, comparador de esquemas, agentes Copilot
- `v0.7.0` ✅: Timing automático de operaciones en bulk CRUD; retirada de scripts legacy
- `v0.8.0` ✅: Cobertura completa del sistema de tipos (8 motores); hotfix de finalización del pool
- `v0.9.0` ✅: Palancas de rendimiento opt-in en dump (commit cadence, índices, paralelización)
- `v0.10.0` ✅: Vías rápidas de INSERT por motor (PostgreSQL COPY, MySQL multi-fila)
- `v0.11.0 – v0.19.0` ✅ (vigente): auditoría y rendimiento de bulk y dump contra motores reales, verificador de
  condiciones del motor e informes robustos (detalle en el [CHANGELOG](CHANGELOG.md))
- `v1.0.0` (futuro): API estable, cobertura 85%+

## Licencia

MIT - Ver [LICENSE](LICENSE)

## Contribuciones

1. Fork el repo
2. Crea rama: `git checkout -b feat/nueva-funcionalidad`
3. Commit: `git commit -am 'Agregada nueva funcionalidad'`
4. Push: `git push origin feat/nueva-funcionalidad`
5. Pull Request

## Soporte

- 📧 Email: developer@example.com
- 🐛 Issues: https://github.com/fmanza/util_bbdd/issues
- 📚 Docs: https://github.com/fmanza/util_bbdd/tree/main/docs
