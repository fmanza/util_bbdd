# API — Migración SQL Server como Origen

Orquesta la migración DDL desde SQL Server hacia Oracle, MariaDB, MySQL o PostgreSQL en tres capas desacopladas: extracción vía `INFORMATION_SCHEMA` y `sys.*`, transformación al modelo canónico IR y emisión del script DDL.

## 1. Arquitectura y Diseño

```mermaid
flowchart TD
    PL["MigrationPlanner\n(source='sqlserver')"]
    EX["SQLServerSchemaExtractor\n(snapshot de metadata/:\nsys.*)"]
    TR_OR["SQLServerToOracleTransformer"]
    TR_MB["SQLServerToMariaDBTransformer"]
    TR_PG["SQLServerToPostgreSQLTransformer"]
    EM["Generadores DDL\n(por motor destino)"]
    OUT["MigrationPlan\n.emit_ddl() → .sql\n.execute(target)"]

    PL --> EX
    EX --> TR_OR & TR_MB & TR_PG
    TR_OR & TR_MB & TR_PG --> EM
    EM --> OUT
```

## 2. Modelo de Datos / Contratos

### API pública

| Clase / Función | Firma simplificada | Descripción | Retorna |
|---|---|---|---|
| `MigrationPlanner` | `(source_engine, target_engine, ...)` | Orquestador principal | instancia |
| `MigrationPlanner.plan` | `(connection, schema: str, *, table_filter=None)` | Extrae, transforma y consolida en plan ejecutable; con `table_filter` (`TableFilter.from_patterns` de `util_bbdd.metadata`, 5.9.0) solo las tablas y vistas que casan con los patrones | `MigrationPlan` |
| `MigrationPlan.emit_ddl` | `()` | Script DDL completo listo para guardar en `.sql` | `str` |
| `MigrationPlan.execute` | `(target_connection, *, audit_sink=None)` | Ejecuta cada sentencia DDL contra el motor destino; con `audit_sink`, un evento por sentencia ([auditoría](audit.md)) | `None` |
| `MigrationPlan.error_count` | propiedad | Número de warnings con severidad `ERROR` | `int` |
| `format_plan_text` | `(plan: MigrationPlan)` | Reporte de texto plano con avisos | `str` |
| `format_plan_markdown` | `(plan: MigrationPlan)` | Reporte Markdown con tabla de avisos | `str` |

### Contrato de entrada

| Parámetro | Tipo | Descripción | Restricciones |
|---|---|---|---|
| `source_engine` | `str` | Motor origen | `"sqlserver"` para este flujo |
| `target_engine` | `str` | Motor destino | `"oracle"`, `"mariadb"`, `"mysql"` o `"postgresql"` |
| `charset` | `str` | CHARACTER SET MariaDB | Solo si `target_engine="mariadb"` |
| `sql_server_collation` | `str \| None` | COLLATE SQL Server | N/A como origen; aplica solo a destino SQL Server |
| `oracle_identity_mode` | `Literal["sequence_trigger","identity_by_default_on_null"]` | Modo columnas IDENTITY en Oracle destino | Solo si `target_engine="oracle"` |
| `connection` | `SyncDatabaseManager` o `MetadataSource` | Manager SQL Server activo | Lee el catálogo con `metadata_source` (snapshot de `metadata/`, una consulta por tipo de objeto; ADR-003) |
| `schema` | `str` | Nombre del schema (`TABLE_SCHEMA`) | Habitualmente `'dbo'` |
| `table_filter` | `TableFilter \| None` | Tablas y vistas a migrar por patrones *glob* sin distinguir mayúsculas (5.9.0) | Las rutinas no se filtran; si no casa nada, `ValueError`. Una FK hacia una tabla de fuera va como `ALTER TABLE` al final, con el aviso `FK_OUTSIDE_FILTER` |

### Contrato de salida

- **`MigrationPlan.emit_ddl()`** — `str` con el script DDL completo.
- **`MigrationPlan.warnings`** — `list[MigrationWarning]` con severidad `INFO`/`WARNING`/`ERROR`.
- **`MigrationPlan.table_filter`** / **`MigrationPlan.frontier`** (5.9.0) — el filtro aplicado y las tablas de fuera unidas por FK a las del plan (con `TableFilter.frontier`, `True` por defecto); viajan en `to_dict()`/`from_dict()` como claves opcionales (`format_version` no cambia). Las FK hacia tablas de fuera llevan `CanonicalFK.outside_filter=True`. Una vista del plan que lea una tabla de fuera falla en el destino si esa tabla no existe: compruébalo con `validate_views` (modo seco).

### Errores y casos especiales

| Error | Cuándo ocurre |
|---|---|
| `ValueError` | Motor origen/destino no soportado; ninguna tabla ni vista casa con `table_filter` (5.9.0) |
| `MetadataError` | Error al leer el catálogo del origen (envuelve el error del driver) |
| `TypeError` | `connection` no es un manager de `util_bbdd` ni una `MetadataSource` |

La definición de las vistas se lee con `OBJECT_DEFINITION` (`sys.views`), sin el límite de 4000 caracteres de `INFORMATION_SCHEMA.VIEWS.VIEW_DEFINITION`.

## 3. Componentes y Clases

| Clase | Responsabilidad |
|---|---|
| `MigrationPlanner` | Orquestación del flujo completo |
| `SQLServerSchemaExtractor` | Snapshot de `metadata/` (`sys.*`) → IR con las convenciones de `INFORMATION_SCHEMA` |
| `SQLServerToOracleTransformer` / `SQLServerToMariaDBTransformer` / `SQLServerToPostgreSQLTransformer` | Mapeo de tipos al dialecto destino |

## 4. Dependencias y Requisitos

| Dependencia | Propósito | Requerida | Comportamiento sin ella |
|---|---|---|---|
| `SyncDatabaseManager` con engine SQL Server | Acceso a catálogos | Sí | Extracción imposible |
| `pymssql` o `pyodbc` (según `sql_server_driver` del manager; no hay extra, se instalan aparte) | Driver del manager sync de SQL Server | Sí | `DriverError` al crear el manager |

## 5. Ejemplos Relacionados

- [Ejemplo: Migración DDL SQL Server → Oracle / MariaDB / PostgreSQL](../examples/migrate_sqlserver_source.md) — Script completo de migración con `MigrationPlanner`
