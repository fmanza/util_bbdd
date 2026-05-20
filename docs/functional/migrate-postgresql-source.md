# Migración PostgreSQL → Oracle / MariaDB / SQL Server

## Descripción funcional

El módulo `migrate` soporta migración DDL **desde PostgreSQL** como motor origen hacia
tres motores destino: Oracle, MariaDB y SQL Server. El flujo de trabajo es idéntico al
de Oracle, MariaDB y SQL Server como fuentes: extraer metadatos → transformar tipos → emitir DDL.

## Precondiciones

- Conexión activa al esquema PostgreSQL origen (manager compatible con `execute_custom_many`).
- Driver Python compatible: **psycopg2** o **psycopg3** (param style `%(name)s`).
- El parámetro `schema` corresponde a `TABLE_SCHEMA` en PostgreSQL (habitualmente `'public'`).
- La conexión debe apuntar a la base de datos correcta.

## Flujo principal

```
PostgreSQL Schema
        │
        ▼
PostgreSQLSchemaExtractor
  ├── INFORMATION_SCHEMA.TABLES
  ├── INFORMATION_SCHEMA.COLUMNS (auto_increment via nextval())
  ├── INFORMATION_SCHEMA.KEY_COLUMN_USAGE (PK/FK)
  ├── pg_catalog.pg_index + generate_subscripts (índices)
  └── INFORMATION_SCHEMA.VIEWS
        │
        ▼
PostgreSQLTo{Oracle|MariaDB|SQLServer}Transformer
  ├── Mapeo de tipos (type_map_postgresql_to_*)
  ├── Resolución dinámica (CHARACTER VARYING, NUMERIC, BIT)
  ├── char_length=None → sin límite (CLOB/LONGTEXT/NVARCHAR(MAX))
  └── Truncación de identificadores + warnings
        │
        ▼
{Oracle|MariaDB|SQLServer}DDLEmitter
        │
        ▼
MigrationPlan.emit_ddl() → script .sql
```

## Reglas de negocio

### Detección de auto_increment (SERIAL)

Las columnas `SERIAL`, `BIGSERIAL` y `SMALLSERIAL` de PostgreSQL se definen en `INFORMATION_SCHEMA` como
tipos `integer`/`bigint`/`smallint` con `COLUMN_DEFAULT = nextval('tablename_colname_seq'::regclass)`.
El extractor detecta este patrón y activa `auto_increment=True`.

Los emitters destino generan:
- **Oracle**: `SEQUENCE` + `BEFORE INSERT TRIGGER`
- **MariaDB**: `AUTO_INCREMENT`
- **SQL Server**: `IDENTITY(1,1)`

### CHARACTER VARYING sin límite

`character varying` sin longitud explícita devuelve `CHARACTER_MAXIMUM_LENGTH = NULL` en `INFORMATION_SCHEMA`.
A diferencia de SQL Server (donde `-1` indica `MAX`), en PostgreSQL `NULL` indica "sin límite".

Mapeo de `CHARACTER VARYING` con `char_length=None`:

| Destino | Tipo generado |
|---|---|
| Oracle | `CLOB` |
| MariaDB | `LONGTEXT` |
| SQL Server | `NVARCHAR(MAX)` |

### Tipos multi-palabra

PostgreSQL usa tipos multi-palabra en `INFORMATION_SCHEMA.COLUMNS.DATA_TYPE`:

| PostgreSQL DATA_TYPE | Normalizado (uppercase) | Ejemplo destino Oracle |
|---|---|---|
| `character varying` | `CHARACTER VARYING` | `VARCHAR2(n)` |
| `timestamp without time zone` | `TIMESTAMP WITHOUT TIME ZONE` | `TIMESTAMP` |
| `timestamp with time zone` | `TIMESTAMP WITH TIME ZONE` | `TIMESTAMP WITH TIME ZONE` |
| `time without time zone` | `TIME WITHOUT TIME ZONE` | `VARCHAR2(15)` |
| `bit varying` | `BIT VARYING` | `VARCHAR2(n)` |

### Índices no-PK

`INFORMATION_SCHEMA` no expone índices en PostgreSQL. Se usa `pg_catalog.pg_index` con
`generate_subscripts(ix.indkey, 1)` para garantizar el orden correcto de columnas
en índices compuestos (compatible con PostgreSQL 8.4+).

### Vistas (v1 pass-through)

Las vistas se emiten **sin reescritura** del SQL fuente. Se añade un `MigrationWarning` de
severidad `WARNING` indicando que las funciones PostgreSQL-específicas
(`NOW()`, `CURRENT_TIMESTAMP`, `COALESCE`, `EXTRACT`, `GENERATE_SERIES`, etc.) requieren
revisión manual antes de ejecutar en el motor destino.

### FKs externas

Si una FK referencia una tabla en un schema distinto al migrado, se marca `is_external=True`
y se emite como `ALTER TABLE` al final del script, con un `WARNING` para verificación manual.

## Limitaciones v1

| Limitación | Descripción |
|---|---|
| Vistas sin reescritura | Las funciones PostgreSQL-específicas no se traducen automáticamente |
| Comentarios de columna | `pg_description` omitido en v1 |
| Tipos espaciales | `POINT`, `POLYGON`, etc. se mapean a VARCHAR/CLOB/LONGTEXT con severidad `ERROR` |
| `TSVECTOR`/`TSQUERY` | Se mapean a CLOB/LONGTEXT/NVARCHAR(MAX) con severidad `ERROR` |
| `ARRAY` | Se mapea a CLOB/LONGTEXT/NVARCHAR(MAX) con severidad `ERROR` |
| `USER-DEFINED` (enums) | Se mapea a CLOB/LONGTEXT/NVARCHAR(MAX) con severidad `ERROR` |
| Param style asyncpg | asyncpg usa `$1, $2, ...`; requiere wrapper de manager |

## Uso

```python
from util_bbdd.migrate import MigrationPlanner

# PostgreSQL → Oracle
planner = MigrationPlanner(
    source_engine="postgresql",
    target_engine="oracle",
)
plan = planner.plan(connection=pg_manager, schema="public")
ddl = plan.emit_ddl()
print(ddl)

# PostgreSQL → MariaDB
planner = MigrationPlanner(
    source_engine="postgresql",
    target_engine="mariadb",
    charset="utf8mb4",
    collation="utf8mb4_unicode_ci",
)
plan = planner.plan(connection=pg_manager, schema="public")
ddl = plan.emit_ddl()

# PostgreSQL → SQL Server
planner = MigrationPlanner(
    source_engine="postgresql",
    target_engine="sqlserver",
    sql_server_collation="SQL_Latin1_General_CP1_CI_AS",  # opcional
)
plan = planner.plan(connection=pg_manager, schema="public")
ddl = plan.emit_ddl()
```

## Warnings frecuentes

| Tipo origen | Decisión | Severidad |
|---|---|---|
| `BOOLEAN` | → `NUMBER(1,0)` en Oracle | WARNING |
| `TIMESTAMP WITH TIME ZONE` | → `DATETIME(6)` en MariaDB (TZ perdida) | WARNING |
| `JSON`/`JSONB` | → `CLOB`/`LONGTEXT`/`NVARCHAR(MAX)` | WARNING |
| `CHARACTER VARYING(n>4000)` | → `CLOB` en Oracle | WARNING |
| `INTERVAL` | → `VARCHAR(30)` en MariaDB/SQL Server | WARNING |
| `INET`/`CIDR` | → `VARCHAR2(45)` / `VARCHAR(45)` | WARNING |
| `TSVECTOR`/`TSQUERY` | → CLOB equivalente | ERROR |
| `ARRAY` | → CLOB equivalente | ERROR |
| Vistas | SQL sin reescritura | WARNING |
