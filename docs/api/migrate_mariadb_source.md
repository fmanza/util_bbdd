# API — Migración MariaDB como Origen

Orquesta la migración DDL desde MariaDB hacia Oracle, MySQL, SQL Server o PostgreSQL en tres capas desacopladas: extracción vía `INFORMATION_SCHEMA`, transformación al modelo canónico IR y emisión del script DDL.

## 1. Arquitectura y Diseño

```mermaid
flowchart TD
    PL["MigrationPlanner\n(source='mariadb')"]
    EX["MariaDBSchemaExtractor\n(snapshot de metadata/)"]
    TR_OR["MariaDBToOracleTransformer"]
    TR_SS["MariaDBToSQLServerTransformer"]
    TR_PG["MariaDBToPostgreSQLTransformer"]
    EM["Generadores DDL\n(por motor destino)"]
    OUT["MigrationPlan\n.emit_ddl() → .sql\n.execute(target)"]

    PL --> EX
    EX --> TR_OR & TR_SS & TR_PG
    TR_OR & TR_SS & TR_PG --> EM
    EM --> OUT
```

## 2. Modelo de Datos / Contratos

### API pública

| Clase / Función | Firma simplificada | Descripción | Retorna |
|---|---|---|---|
| `MigrationPlanner` | `(source_engine, target_engine, ...)` | Orquestador principal | instancia |
| `MigrationPlanner.plan` | `(connection, schema: str)` | Extrae, transforma y consolida en plan ejecutable | `MigrationPlan` |
| `MigrationPlan.emit_ddl` | `()` | Script DDL completo listo para guardar en `.sql` | `str` |
| `MigrationPlan.execute` | `(target_connection, *, audit_sink=None)` | Ejecuta cada sentencia DDL contra el motor destino; con `audit_sink`, un evento por sentencia ([auditoría](audit.md)) | `None` |
| `MigrationPlan.error_count` | propiedad | Número de warnings con severidad `ERROR` | `int` |
| `format_plan_text` | `(plan: MigrationPlan)` | Reporte de texto plano con avisos | `str` |
| `format_plan_markdown` | `(plan: MigrationPlan)` | Reporte Markdown con tabla de avisos | `str` |

### Contrato de entrada

| Parámetro | Tipo | Descripción | Restricciones |
|---|---|---|---|
| `source_engine` | `str` | Motor origen | `"mariadb"` para este flujo |
| `target_engine` | `str` | Motor destino | `"oracle"`, `"mysql"`, `"sqlserver"` o `"postgresql"` |
| `sql_server_collation` | `str \| None` | COLLATE para SQL Server | Solo si `target_engine="sqlserver"` |
| `pg_schema` | `str \| None` | Schema PostgreSQL | Solo si `target_engine="postgresql"` |
| `connection` | `SyncDatabaseManager` o `MetadataSource` | Manager MariaDB activo | Lee el catálogo con `metadata_source` (snapshot de `metadata/`, una consulta por tipo de objeto; ADR-003) |
| `schema` | `str` | Nombre del schema MariaDB (`TABLE_SCHEMA`) | Sensible a mayúsculas |

### Contrato de salida

- **`MigrationPlan.emit_ddl()`** — `str` con el script DDL completo, ordenado por dependencias FK.
- **`MigrationPlan.warnings`** — `list[MigrationWarning]` con `severity`, `message`, `table`, `column`.

### Errores y casos especiales

| Error | Cuándo ocurre |
|---|---|
| `ValueError` | Motor origen/destino no soportado |
| `MetadataError` | Error al leer el catálogo del origen (envuelve el error del driver) |
| `TypeError` | `connection` no es un manager de `util_bbdd` ni una `MetadataSource` |

## 3. Componentes y Clases

| Clase | Responsabilidad |
|---|---|
| `MigrationPlanner` | Orquestación del flujo completo |
| `MariaDBSchemaExtractor` | Snapshot de `metadata/` → IR con las convenciones de `INFORMATION_SCHEMA` |
| `MariaDBToOracleTransformer` / `MariaDBToSQLServerTransformer` / `MariaDBToPostgreSQLTransformer` | Mapeo de tipos al dialecto destino |

## 4. Dependencias y Requisitos

| Dependencia | Propósito | Requerida | Comportamiento sin ella |
|---|---|---|---|
| `SyncDatabaseManager` con engine MariaDB | Acceso a `INFORMATION_SCHEMA` | Sí | Extracción imposible |
| `mariadb` (MariaDB Connector/Python, extra `util_bbdd[mariadb]`) | Driver del manager sync de MariaDB | Sí | `DriverError` al crear el manager |

## 5. Ejemplos Relacionados

- [Ejemplo: Migración DDL MariaDB → Oracle / SQL Server / PostgreSQL](../examples/migrate_mariadb_source.md) — Script completo de migración con `MigrationPlanner`
