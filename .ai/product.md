# 📦 Product Context - util_bbdd

## Descripción

**util_bbdd** es una librería Python especializada en operaciones de base de datos para múltiples motores (MariaDB, PostgreSQL, Oracle, SQLite, SQL Server, HSQLDB). Proporciona abstracción unificada con operaciones CRUD en lote, auditoría automática, gestión de conexiones con pool singleton, y análisis de relaciones.

**Versión:** 0.6.2 | **Estado:** Estable | **Python:** ≥3.11

## Motores Soportados

| Motor      | Sync | Async | Driver            |
|------------|------|-------|-------------------|
| MariaDB    | ✅   | ✅    | `aiomysql`        |
| PostgreSQL | ✅   | ✅    | `asyncpg`         |
| Oracle     | ✅   | ✅    | `oracledb`        |
| SQLite     | ✅   | ✅    | `aiosqlite`       |
| SQL Server | ✅   | ✅    | `aioodbc`         |
| HSQLDB     | ✅   | ❌    | Solo sync         |

## Capacidades Principales

- **CRUD en lote**: Insert/Update/Delete masivo desde DataFrames
- **Auditoría**: Registro automático en CSV con timestamps y user context
- **Managers**: APIs sync (`SyncDatabaseManager`) y async (`AsyncDatabaseManager`)
- **Metadata**: Caché de esquema, introspection, relaciones
- **Query Registry**: Registro centralizado y versionado de consultas
- **Visualización**: Grafos de relaciones multinivel (graphviz, matplotlib)
- **Documentación**: Generación automática de esquema en HTML, Word y Excel

## Migración y compatibilidad

La librería conserva compatibilidad histórica selectiva en algunos wrappers. v0.6.0 introdujo el breaking change deliberado del contrato de grafos y documentación, v0.6.1 consolidó la semántica visual y v0.6.2 cierra la portabilidad offline con payloads compartidos de leyenda/resumen, SVG inline e iconografía local para HTML exportado.

## Audiencia

- Desarrolladores backend Python con BD complejas
- Equipos que necesitan abstracción multi-motor
- Proyectos con requisitos de auditoría y versionado de schema
