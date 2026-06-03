# API — Migración MariaDB como Origen

Orquesta la migración DDL desde MariaDB hacia Oracle, SQL Server o PostgreSQL en tres capas desacopladas: extracción vía `INFORMATION_SCHEMA`, transformación al modelo canónico IR y emisión del script DDL.

## 1. Arquitectura y Diseño

```mermaid
flowchart TD
    PL["MigrationPlanner\n(source='mariadb')"]
    EX["MariaDBSchemaExtractor\n(INFORMATION_SCHEMA)"]
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
| `MigrationPlan.execute` | `(target_connection)` | Ejecuta cada sentencia DDL contra el motor destino | `None` |
| `MigrationPlan.error_count` | propiedad | Número de warnings con severidad `ERROR` | `int` |
| `format_plan_text` | `(plan: MigrationPlan)` | Reporte de texto plano con avisos | `str` |
| `format_plan_markdown` | `(plan: MigrationPlan)` | Reporte Markdown con tabla de avisos | `str` |

### Contrato de entrada

| Parámetro | Tipo | Descripción | Restricciones |
|---|---|---|---|
| `source_engine` | `str` | Motor origen | `"mariadb"` para este flujo |
| `target_engine` | `str` | Motor destino | `"oracle"`, `"sqlserver"` o `"postgresql"` |
| `sql_server_collation` | `str \| None` | COLLATE para SQL Server | Solo si `target_engine="sqlserver"` |
| `pg_schema` | `str \| None` | Schema PostgreSQL | Solo si `target_engine="postgresql"` |
| `connection` | `SyncDatabaseManager` | Manager MariaDB activo | Requiere `execute_custom_many(sql, params)` |
| `schema` | `str` | Nombre del schema MariaDB (`TABLE_SCHEMA`) | Sensible a mayúsculas |

### Contrato de salida

- **`MigrationPlan.emit_ddl()`** — `str` con el script DDL completo, ordenado por dependencias FK.
- **`MigrationPlan.warnings`** — `list[MigrationWarning]` con `severity`, `message`, `table`, `column`.

### Errores y casos especiales

| Error | Cuándo ocurre |
|---|---|
| `ValueError` | Motor origen/destino no soportado |
| `SQLAlchemyError` | Error al consultar `INFORMATION_SCHEMA` |

## 3. Componentes y Clases

| Clase | Responsabilidad |
|---|---|
| `MigrationPlanner` | Orquestación del flujo completo |
| `MariaDBSchemaExtractor` | Extracción desde `INFORMATION_SCHEMA` |
| `MariaDBToOracleTransformer` / `MariaDBToSQLServerTransformer` / `MariaDBToPostgreSQLTransformer` | Mapeo de tipos al dialecto destino |

## 4. Dependencias y Requisitos

| Dependencia | Propósito | Requerida | Comportamiento sin ella |
|---|---|---|---|
| `SyncDatabaseManager` con engine MariaDB | Acceso a `INFORMATION_SCHEMA` | Sí | Extracción imposible |
| `pymysql` u otro driver MariaDB | Conexión nativa | Sí (motor-específico) | `DriverError` al conectar |

## 5. Ejemplos Relacionados

- [Ejemplo: Migración DDL MariaDB → Oracle / SQL Server / PostgreSQL](../examples/migrate-mariadb-source.md) — Script completo de migración con `MigrationPlanner`
