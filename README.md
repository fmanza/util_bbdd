# util_bbdd

Librería Python para **operaciones de base de datos** en MariaDB, MySQL, Oracle, PostgreSQL, SQLite y SQL Server (sync y
async) y HSQLDB (sync): conexiones con pool, carga masiva desde DataFrames, volcado entre motores, migración DDL,
comparación de esquemas y documentación de la base de datos.

**Version:** 2.2.3 | **Status:** ✅ Estable | **Python:** 3.12+

---

## 🚀 Capacidades

| Capacidad | Punto de entrada | Notas |
|---|---|---|
| Conexión y consultas | `SyncDatabaseManager`, `AsyncDatabaseManager` | Pool por defecto; consultas libres o registradas en JSON |
| Metadatos | `manager.get_schema_metadata()` → `SchemaSnapshot` | Una consulta por tipo de objeto y schema, cacheada hasta `clear_cache()` |
| Carga masiva | `BulkCrud`, `ParallelBulkLoader` | INSERT/UPDATE/DELETE desde `pandas.DataFrame`; vía rápida por motor (COPY en PostgreSQL, multi-fila en MySQL/MariaDB) |
| Volcado de datos | `DumpOrchestrator` + `DumpConfig` | Entre schemas o motores, orden por FK, gestión de constraints, informe Excel |
| Migración DDL | `MigrationPlanner` → `MigrationPlan` | Entre Oracle, MariaDB, MySQL, SQL Server y PostgreSQL: tipos, FKs, secuencias, charset |
| Comparación de esquemas | `SchemaComparator` → `SchemaDiff` | Informes HTML, Excel, Word, Markdown y SQL (`util_bbdd.comparar`) |
| Documentación de BD | `DatabaseDocumentation` | HTML, Word y Excel desde el catálogo real |
| Auditoría | `util_bbdd.audit` | CSV de `BulkCrud` y destinos `AuditSink` (JSON Lines, memoria) para bulk, dump y migrate |
| Grafos de relaciones | `util_bbdd.analysis` | Graphviz (extra `analysis`) y Matplotlib (extra `analysis-matplotlib`) |

---

## 📦 Instalación

`util_bbdd` no está publicado en PyPI: se instala desde el repositorio, fijando la versión con su tag.

```bash
pip install "util_bbdd @ git+https://github.com/fmanza/util_bbdd.git@v1.1.0"

# Con los drivers de un motor (extras: postgresql, mariadb, mysql; se combinan con comas)
pip install "util_bbdd[postgresql] @ git+https://github.com/fmanza/util_bbdd.git@v1.1.0"
```

Oracle (`oracledb`), la documentación de BD (`openpyxl`, `python-docx`, `jinja2`) y pandas van en la instalación base.
Extras, drivers por motor y solución de problemas: [docs/installation.md](docs/installation.md).

---

## 🧭 API pública 1.0

La raíz exporta solo los **puntos de entrada y sus resultados**:

```python
from util_bbdd import (
    SyncDatabaseManager, AsyncDatabaseManager,       # conexión y consultas
    BulkCrud, ParallelBulkLoader,                    # carga masiva
    DumpOrchestrator, DumpConfig, DumpResult,        # volcado
    MigrationPlanner, MigrationPlan,                 # migración DDL
    SchemaComparator, SchemaDiff,                    # comparación
    DatabaseDocumentation,                           # documentación
    DatabaseException,                               # error base
)
```

El resto se importa desde su submódulo público:

| Submódulo | Contenido |
|---|---|
| `util_bbdd.exceptions` | Jerarquía completa de excepciones (todas heredan de `DatabaseException`) |
| `util_bbdd.audit` | `AuditEvent`, `AuditSink` y destinos (`JsonLinesAuditSink`, `MemoryAuditSink`, `NullAuditSink`) |
| `util_bbdd.metadata` | `SchemaSnapshot`, `Kind`, contratos `SyncMetadataProvider`/`AsyncMetadataProvider` |
| `util_bbdd.connection` | `build_conn_params`, `ConnectionFactory`, `EngineReadinessAdvisor` |
| `util_bbdd.factory` | `ConnectionFactory`, `PoolFactory` |
| `util_bbdd.async_utils` | `maybe_await` |
| `util_bbdd.analysis` | Grafos de relaciones |
| `util_bbdd.bulk`, `.dump`, `.migrate`, `.comparar`, `.doc` | Tipos auxiliares de cada punto de entrada |

`import util_bbdd` solo carga los managers: los puntos de entrada que usan pandas, openpyxl, python-docx o jinja2 se
cargan la primera vez que se usan. Si vienes de 0.x: [guía de migración a la API 1.0](docs/guides/api_1_0_migration.md).

---

## ⚡ Quick Start

### SQLite (sin servidor)

```python
from util_bbdd import SyncDatabaseManager

with SyncDatabaseManager(db_type="sqlite", conn_params={"database": ":memory:"}) as manager:
    manager.execute_custom_many("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
    print([table.name for table in manager.get_tables()])  # → ['test']
```

### PostgreSQL — sync

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd.exceptions import QueryTimeoutError

manager = SyncDatabaseManager(
    db_type="postgresql",
    conn_params={"host": "localhost", "port": 5432, "user": "postgres", "password": "secret", "database": "mydb"},
)
try:
    tables = manager.get_tables()
    columns = manager.get_columns("users")
    print([(c.name, c.data_type) for c in columns])
    rows = manager.execute_custom_many("SELECT * FROM users LIMIT 5")
except QueryTimeoutError as exc:
    print(f"Consulta demasiado lenta: {exc}")
finally:
    manager.close()
```

### PostgreSQL — async

```python
import asyncio

from util_bbdd import AsyncDatabaseManager


async def main() -> None:
    async with AsyncDatabaseManager(
        db_type="postgresql",
        conn_params={"host": "localhost", "user": "postgres", "password": "secret", "database": "mydb", "pool_size": 10},
    ) as manager:
        tables, views, routines = await asyncio.gather(
            manager.get_tables(), manager.get_views(), manager.get_routines()
        )
        print(f"Tablas: {len(tables)}, vistas: {len(views)}, rutinas: {len(routines)}")


asyncio.run(main())
```

Los dos managers comparten los nombres del ciclo de vida: `init()`, `get_connection()`, `release_connection(conn)` y
`close()` (en el async son corrutinas).

---

## Carga masiva desde un DataFrame

```python
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from util_bbdd import BulkCrud

engine = create_engine("sqlite:///demo_bulk.db")
with engine.begin() as conn:
    conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, email TEXT)"))

df = pd.DataFrame({
    "id": [1, 2, 3],
    "name": ["Alice", "Bob", "Charlie"],
    "email": ["alice@ex.com", "bob@ex.com", "charlie@ex.com"],
})

crud = BulkCrud(engine=engine, audit_csv_path=Path("audit.csv"))
crud.bulk_insert_from_df(df, tabla_destino="users", generar_sql=False)
```

`BulkCrud` también ofrece `bulk_update_from_df`, `bulk_delete_from_df` y las variantes `*_from_chunks` para leer por
lotes. Con un manager, `manager.get_sqlalchemy_engine()` da el Engine. Detalle: [docs/api/bulk_crud.md](docs/api/bulk_crud.md).

---

## Volcado de datos entre motores

`DumpOrchestrator` copia los datos de un schema origen a uno destino (mismo o distinto motor), carga en orden de claves
foráneas, gestiona constraints y genera un informe Excel.

```python
from pathlib import Path

from sqlalchemy import create_engine

from util_bbdd import DumpConfig, DumpOrchestrator

config = DumpConfig(
    source_engine=create_engine("postgresql+psycopg://user:pw@src/db"),
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

Ejemplo completo e interpretación del informe: [docs/examples/dump_data_export.md](docs/examples/dump_data_export.md).

---

## Migrar DDL entre motores

`MigrationPlanner` genera el script DDL de un schema completo adaptado al motor destino.

```python
from util_bbdd import MigrationPlanner

planner = MigrationPlanner(
    source_engine="oracle",   # "oracle" | "mariadb" | "mysql" | "sqlserver" | "postgresql"
    target_engine="mariadb",  # cualquier motor distinto al origen
    charset="utf8mb4",
    collation="utf8mb4_uca1400_ai_ci",  # por defecto; requiere MariaDB >= 10.10
)
plan = planner.plan(connection=oracle_manager, schema="VENTAS")

with open(plan.suggested_filename(), "w", encoding="utf-8") as f:
    f.write(plan.emit_ddl())
print(f"Errores: {plan.error_count}  Warnings: {plan.warning_count}")
```

Columnas autoincrementales hacia Oracle (`oracle_identity_mode`): `"sequence_trigger"` (por defecto, Oracle 11g+) o
`"identity_by_default_on_null"` (Oracle 12c+). Los procedimientos y funciones se emiten tal cual, con aviso de revisión
manual. Ejemplos por motor: [docs/examples/migrate_oracle_mariadb.md](docs/examples/migrate_oracle_mariadb.md) y
[docs/examples/migrate_mariadb_source.md](docs/examples/migrate_mariadb_source.md).

---

## Comparar dos esquemas

```python
from pathlib import Path

from sqlalchemy import inspect

from util_bbdd import SchemaComparator
from util_bbdd.comparar import SchemaDiffReporter

diff = SchemaComparator().compare(
    inspect(origen.get_sqlalchemy_engine()),
    inspect(destino.get_sqlalchemy_engine()),
)
if diff.has_differences:
    SchemaDiffReporter(sql_dialect="postgresql").render_all(diff, output_dir=Path("reportes"), formats=["html", "sql"])
```

Guía: [docs/guides/comparator.md](docs/guides/comparator.md).

---

## Documentar una base de datos

`DatabaseDocumentation` genera documentación HTML, Word o Excel desde un `SyncDatabaseManager`. El constructor solo valida
la configuración; `generate()` lee el catálogo, escribe los ficheros y devuelve un `DocumentationResult`.

```python
from pathlib import Path

from util_bbdd import DatabaseDocumentation, SyncDatabaseManager

manager = SyncDatabaseManager(db_type="sqlite", conn_params={"database": "demo_documentation.db"}, use_pool=False)

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
result = documentation.generate()
print(result.outputs["html"], result.tables)
manager.close()
```

Formatos: `word`, `excel`, `html`. Opciones de `imprimir` (grafos, almacenamiento, charset…):
[docs/api/database_documentation.md](docs/api/database_documentation.md); ejemplo verificable:
[docs/examples/database_documentation_generation.md](docs/examples/database_documentation_generation.md).

---

## 🔗 Soporte por motor

| Motor | Sync | Async | Driver sync | Driver async |
|---|---|---|---|---|
| PostgreSQL | ✅ | ✅ | `psycopg` 3 + `psycopg-pool` | `asyncpg` |
| MariaDB | ✅ | ✅ | `mariadb` (Connector/Python) | `aiomysql` |
| MySQL | ✅ | ✅ | `pymysql` | `aiomysql` |
| Oracle | ✅ | ✅ | `oracledb` | `oracledb` |
| SQL Server | ✅ | ✅ | `pyodbc` / `pymssql` | `aioodbc` |
| SQLite | ✅ | ✅ | `sqlite3` (stdlib) | `aiosqlite` |
| HSQLDB | ✅ | ❌ | `jaydebeapi` (Java) | — |

Parámetros de conexión y pool por motor: [docs/guides/connection_guide.md](docs/guides/connection_guide.md).

---

## 🏗️ Arquitectura

Tres niveles (Foundation → Servicios → Especialización) con imports solo hacia capas inferiores; lo comprueban
`tests/unit/test_architecture_import_rules.py` y `scripts/gen_arquitectura_capas.py`. La lectura del catálogo se
centraliza en `util_bbdd.metadata` (ADR-003). Detalle y diagrama de capas: [docs/architecture.md](docs/architecture.md).

---

## 📚 Documentación

| Tema | Enlace |
|---|---|
| Instalación | [docs/installation.md](docs/installation.md) |
| Referencia de la API | [docs/api/intro.md](docs/api/intro.md) |
| Migración a la API 1.0 | [docs/guides/api_1_0_migration.md](docs/guides/api_1_0_migration.md) |
| Excepciones | [docs/guides/exceptions.md](docs/guides/exceptions.md) |
| Programación async | [docs/guides/async_guide.md](docs/guides/async_guide.md) |
| Rendimiento y benchmarks | [docs/guides/benchmarks.md](docs/guides/benchmarks.md) |
| Solución de problemas | [docs/guides/troubleshooting.md](docs/guides/troubleshooting.md) |
| Ejemplos | [docs/examples/](docs/examples/) |

El sitio se construye con `zensical build` (o `mkdocs build`) a partir de `mkdocs.yml`.

---

## 🛠️ Desarrollo

```bash
git clone https://github.com/fmanza/util_bbdd.git
cd util_bbdd
python -m venv venv
# Windows: .\venv\Scripts\Activate.ps1   |   Linux/Mac: source venv/bin/activate
pip install -e ".[dev,docs]"

python -m ruff check src tests
python -m mypy src tests/unit/test_protocol_conformance.py
python -m pytest
```

Los tests unitarios usan SQLite en memoria; los de integración (`tests/integration/`) necesitan las URL del banco de
pruebas (`scripts/bench_env.example.sh`). Flujo con asistentes de IA (Claude Code, Copilot, Gemini, Codex, Cursor):
[.github/SHARED_INSTRUCTIONS.md](.github/SHARED_INSTRUCTIONS.md) y [.github/AGENTS.md](.github/AGENTS.md).

---

## Versionado

[Semantic Versioning](https://semver.org/): desde 1.0.0, la API pública (la raíz y los submódulos públicos listados
arriba) solo cambia de forma incompatible en una versión MAJOR.

**Current Version: v2.2.3** (la precarga de grafos Graphviz ya no puede bloquearse; pendientes de la auditoría de v2.2.2; API pública estable)

Historial completo: [CHANGELOG.md](CHANGELOG.md) · Hoja de ruta: [docs/roadmap.md](docs/roadmap.md).

## Licencia

MIT — ver [LICENSE](LICENSE).

## Soporte

- 🐛 Issues: https://github.com/fmanza/util_bbdd/issues
- 📚 Documentación: https://fmanza.github.io/util_bbdd/
