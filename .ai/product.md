# 📦 Product Context - util_bbdd

## Descripción

**util_bbdd** es una librería Python especializada en operaciones de base de datos para múltiples motores (MariaDB, MySQL, PostgreSQL, Oracle, SQLite, SQL Server, HSQLDB, Redshift, Snowflake). Proporciona abstracción unificada con operaciones CRUD en lote, auditoría automática, gestión de conexiones con pool singleton, y análisis de relaciones.

**Versión:** ver `pyproject.toml` y `.ai/CURRENT_STATE.md` | **Estado:** Estable | **Python:** `requires-python` de `pyproject.toml`

> Las capacidades de este fichero se revisaron por última vez con v0.10.0; las posteriores
> (v0.11.0+) están en `.ai/CURRENT_STATE.md` y `CHANGELOG.md`.

## Motores Soportados

| Motor      | Sync | Async | Driver            |
|------------|------|-------|-------------------|
| MariaDB    | ✅   | ✅    | `mariadb` (sync), `aiomysql` (async) |
| MySQL      | ✅   | ✅    | `pymysql` (sync), `aiomysql` (async) |
| PostgreSQL | ✅   | ✅    | `asyncpg`         |
| Oracle     | ✅   | ✅    | `oracledb`        |
| SQLite     | ✅   | ✅    | `aiosqlite`       |
| SQL Server | ✅   | ✅    | `aioodbc`         |
| HSQLDB     | ✅   | ❌    | Solo sync         |
| Redshift   | ✅   | ❌    | Via PostgreSQL    |
| Snowflake  | ✅   | ❌    | Via SQLAlchemy    |

## Capacidades Principales

- **CRUD en lote**: Insert/Update/Delete masivo desde DataFrames con path optimizados por motor
- **Fast paths INSERT**: `PostgresCopyStrategy` (psycopg3 COPY ~10×), `MySQLMultiRowInsertStrategy` (multi-fila), `InsertStrategyResolver` (selección automática)
- **Carga masiva paralela**: `ParallelBulkLoader` con `RangePartitioner` (PK entera/datetime) y `HashPartitioner` (string/UUID)
- **Auditoría**: CSV de operaciones `bulk` (formato fijo) y eventos opcionales comunes a `bulk`, `dump` y `migrate` (`util_bbdd.audit`, `audit_sink`); thread-safe en modo paralelo
- **Managers**: APIs sync (`SyncDatabaseManager`) y async (`AsyncDatabaseManager`)
- **Metadata**: lectura del catálogo por lotes (`CatalogSource` → `SchemaSnapshot`, ADR-003), DDL e inventario de almacenamiento; único punto con SQL de catálogo
- **Query Registry**: Registro centralizado y versionado de consultas
- **Visualización**: Grafos de relaciones multinivel (graphviz, matplotlib)
- **Documentación de BD**: Generación automática de esquema en HTML, Word y Excel
- **Migración DDL**: `MigrationPlanner` convierte DDL entre 4 motores (12 combinaciones: Oracle/MariaDB/SQL Server/PostgreSQL); tablas, vistas, rutinas (PROCEDURE/FUNCTION/PACKAGE); 25+ tipos mapeados por par de motores
- **Comparación de esquemas**: `SchemaComparator` detecta diferencias entre dos schemas; reporters HTML/Excel/Word/Markdown/SQL; cross-engine case-insensitive
- **Volcado de datos**: `DumpOrchestrator` copia datos entre motores con gestión de constraints, paralelización por niveles FK, `DumpAuditSummary` integrado
- **Sincronización de PK**: `PKSequenceSyncer` ajusta contadores PK post-bulk (PostgreSQL/SQL Server/MariaDB/Oracle ≥12c)
- **Variables MySQL/MariaDB**: `MySQLVariableValidator` + `MySQLOptimalConfig` detectan y recomiendan configuración óptima para bulk
- **Documentación offline**: Plugin MkDocs `documentation_zip` genera ZIP con SHA256; auto-publicación en GitHub Releases

## Migración y compatibilidad

- v0.6.0: breaking change deliberado en grafos y documentación
- v0.8.0: módulos `migrate/` y `dump/` introducidos
- v0.9.0: `ParallelBulkLoader`, `IndexManager`, `commit_every_n_chunks`, paralelización FK-topológica
- v0.10.0: `PostgresCopyStrategy`, `MySQLMultiRowInsertStrategy`, `InsertStrategyResolver`, `MySQLVariableValidator`; `PKSequenceSyncer`; `HashPartitioner`

## Audiencia

- Desarrolladores backend Python con BD complejas
- Equipos que necesitan abstracción multi-motor
- Proyectos con requisitos de auditoría y versionado de schema
- Ingenieros de datos con cargas ETL masivas
