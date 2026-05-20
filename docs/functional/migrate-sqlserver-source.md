# Migración SQL Server → Oracle / MariaDB / PostgreSQL

## Descripción funcional

El módulo `migrate` soporta migración DDL **desde SQL Server** como motor origen hacia
tres motores destino: Oracle, MariaDB y PostgreSQL. El flujo de trabajo es idéntico al
de Oracle y MariaDB como fuentes: extraer metadatos → transformar tipos → emitir DDL.

## Precondiciones

- Conexión activa al esquema SQL Server origen (manager compatible con `execute_custom_many`).
- Driver Python compatible: **pymssql** (param style `%(name)s`) o pyodbc con wrapper.
- El parámetro `schema` corresponde a `TABLE_SCHEMA` en SQL Server (habitualmente `'dbo'`).
- La conexión debe apuntar a la base de datos correcta (`USE mydb` o en la cadena de conexión).

## Flujo principal

```
SQL Server Schema
        │
        ▼
SQLServerSchemaExtractor
  ├── INFORMATION_SCHEMA.TABLES
  ├── INFORMATION_SCHEMA.COLUMNS + COLUMNPROPERTY (IDENTITY)
  ├── INFORMATION_SCHEMA.KEY_COLUMN_USAGE (PK/FK)
  ├── sys.indexes / sys.index_columns (índices)
  └── INFORMATION_SCHEMA.VIEWS
        │
        ▼
SQLServerTo{Oracle|MariaDB|PostgreSQL}Transformer
  ├── Mapeo de tipos (25+ tipos SQL Server)
  ├── Truncado de identificadores (30/64/63 chars)
  ├── Detección de MAX (char_length = -1)
  └── Warnings por decisiones no triviales
        │
        ▼
{Oracle|MariaDB|PostgreSQL}DDLEmitter
        │
        ▼
MigrationPlan.emit_ddl() → script .sql
```

## Uso básico

### SQL Server → Oracle

```python
from util_bbdd.migrate import MigrationPlanner

planner = MigrationPlanner(
    source_engine="sqlserver",
    target_engine="oracle",
)
plan = planner.plan(connection=sqlserver_manager, schema="dbo")
ddl = plan.emit_ddl()
print(ddl)
```

### SQL Server → MariaDB

```python
from util_bbdd.migrate import MigrationPlanner

planner = MigrationPlanner(
    source_engine="sqlserver",
    target_engine="mariadb",
    charset="utf8mb4",
    collation="utf8mb4_unicode_ci",
)
plan = planner.plan(connection=sqlserver_manager, schema="dbo")
ddl = plan.emit_ddl()
```

### SQL Server → PostgreSQL

```python
from util_bbdd.migrate import MigrationPlanner

planner = MigrationPlanner(
    source_engine="sqlserver",
    target_engine="postgresql",
    pg_schema="mi_schema",  # opcional: emite SET search_path
)
plan = planner.plan(connection=sqlserver_manager, schema="dbo")
ddl = plan.emit_ddl()
```

## Reglas de mapeo por motor destino

### SQL Server → Oracle

| Tipo SQL Server | Tipo Oracle | Notas |
|---|---|---|
| INT | NUMBER(10,0) | |
| BIGINT | NUMBER(19,0) | |
| SMALLINT | NUMBER(5,0) | |
| TINYINT | NUMBER(3,0) | SS unsigned 0-255; Oracle cubre -999..999 |
| BIT | NUMBER(1,0) | Oracle < 23c sin BOOLEAN nativo |
| DECIMAL(p,s) | NUMBER(p,s) | |
| FLOAT | BINARY_DOUBLE | IEEE 754 double |
| REAL | BINARY_FLOAT | IEEE 754 single |
| MONEY | NUMBER(19,4) | |
| SMALLMONEY | NUMBER(10,4) | |
| VARCHAR(n) | VARCHAR2(n) | n>4000 → CLOB |
| VARCHAR(MAX) | CLOB | char_length=-1 sentinel |
| NVARCHAR(n) | NVARCHAR2(n) | n>4000 → CLOB |
| NVARCHAR(MAX) | CLOB | |
| CHAR(n) | CHAR(n) | |
| NCHAR(n) | NCHAR(n) | |
| TEXT/NTEXT | CLOB | Obsoletos en SS 2005+ |
| DATE | DATE | SS DATE solo fecha; Oracle DATE incluye hora |
| TIME | VARCHAR2(15) | Sin equivalente directo en Oracle |
| DATETIME | DATE | |
| DATETIME2 | TIMESTAMP | |
| SMALLDATETIME | DATE | |
| DATETIMEOFFSET | TIMESTAMP WITH TIME ZONE | Warning TZ |
| BINARY(n) | RAW(n) | |
| VARBINARY(n) | RAW(n) si n≤2000; BLOB si n>2000 | |
| VARBINARY(MAX) | BLOB | |
| IMAGE | BLOB | Obsoleto en SS 2005+ |
| UNIQUEIDENTIFIER | CHAR(36) | Formato 8-4-4-4-12 |
| XML | CLOB | Warning: XMLType disponible en Oracle 12c+ |
| GEOGRAPHY | CLOB | ERROR severity; revisar manualmente |
| GEOMETRY | CLOB | ERROR severity; revisar manualmente |

### SQL Server → MariaDB

| Tipo SQL Server | Tipo MariaDB | Notas |
|---|---|---|
| INT | INT | |
| BIGINT | BIGINT | |
| SMALLINT | SMALLINT | |
| TINYINT | SMALLINT | WARNING: usar TINYINT UNSIGNED si rango exacto |
| BIT | TINYINT(1) | Equivale a BOOL MariaDB |
| DECIMAL(p,s) | DECIMAL(p,s) | |
| FLOAT | DOUBLE | |
| REAL | FLOAT | |
| MONEY | DECIMAL(19,4) | |
| VARCHAR(n) | VARCHAR(n) | |
| VARCHAR(MAX) | LONGTEXT | |
| NVARCHAR(n) | VARCHAR(n) | Usar charset utf8mb4 |
| NVARCHAR(MAX) | LONGTEXT | |
| DATETIME2 | DATETIME(6) | SS hasta 7 fracciones; MariaDB max 6 |
| DATETIMEOFFSET | VARCHAR(35) | WARNING: sin TZ nativo en MariaDB |
| VARBINARY(MAX) | LONGBLOB | |
| UNIQUEIDENTIFIER | CHAR(36) | |

### SQL Server → PostgreSQL

| Tipo SQL Server | Tipo PostgreSQL | Notas |
|---|---|---|
| INT | INTEGER | |
| TINYINT | SMALLINT | |
| BIT | BOOLEAN | |
| FLOAT | DOUBLE PRECISION | |
| MONEY | NUMERIC(19,4) | |
| NVARCHAR(n) | VARCHAR(n) | PG es Unicode-native |
| NVARCHAR(MAX) | TEXT | |
| VARCHAR(MAX) | TEXT | |
| BINARY/VARBINARY | BYTEA | Sin parámetros de longitud |
| DATETIME | TIMESTAMP | |
| DATETIME2 | TIMESTAMP(6) | SS hasta 7 fracciones; PG max 6 |
| DATETIMEOFFSET | TIMESTAMPTZ | Mapeo más directo |
| UNIQUEIDENTIFIER | UUID | Tipo nativo PG |
| XML | XML | Tipo nativo PG |

## Comportamiento especial

### Tipos MAX (char_length = -1)
SQL Server usa `-1` como sentinel en `INFORMATION_SCHEMA.COLUMNS.CHARACTER_MAXIMUM_LENGTH`
para `VARCHAR(MAX)`, `NVARCHAR(MAX)` y `VARBINARY(MAX)`. El extractor preserva este valor
en `CanonicalColumn.char_length`; los transformers lo detectan y emiten el tipo LOB apropiado.

### Columnas IDENTITY
Detectadas mediante `COLUMNPROPERTY(OBJECT_ID(...), col, 'IsIdentity')`. El flag
`auto_increment=True` en el IR activa la generación de SEQUENCE+TRIGGER (Oracle),
AUTO_INCREMENT (MariaDB) o SERIAL/BIGSERIAL (PostgreSQL).

### Vistas (v1 pass-through)
Las vistas se extraen con su `VIEW_DEFINITION` de `INFORMATION_SCHEMA.VIEWS` y se emiten
sin reescritura del SQL. Cada vista recibe un `MigrationWarning` indicando que las funciones
T-SQL (`GETDATE`, `ISNULL`, `TOP`, `NOLOCK`, etc.) requieren revisión manual.

> **Nota**: `VIEW_DEFINITION` en SQL Server puede truncarse a 4000 caracteres para vistas
> con definiciones muy largas en versiones < SQL Server 2019.

## Warnings y severidades

| Severidad | Ejemplos |
|---|---|
| ERROR | GEOGRAPHY, GEOMETRY (requieren revisión manual para conversión espacial) |
| WARNING | TINYINT (rango), DATETIMEOFFSET→MariaDB, TEXT/NTEXT obsoletos, VIEW pass-through |
| INFO | BIT, TINYINT→SMALLINT (PG), FLOAT, REAL, MONEY, DATETIME2 truncación |

## Limitaciones v1

- Param style `%(name)s` (pymssql). Para pyodbc se necesita un manager wrapper que
  adapte `%(name)s` → `?`.
- Vistas: pass-through sin reescritura de funciones T-SQL específicas.
- Sin soporte de: columnas computadas, UDTs (User-Defined Types), tipos alias, tablas
  temporales, tablas con particionado.
- `VIEW_DEFINITION` puede truncarse en SQL Server < 2019.
