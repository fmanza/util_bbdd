# API — Migración PostgreSQL → Oracle / MariaDB / SQL Server

## Extractor

### `PostgreSQLSchemaExtractor`

```python
from util_bbdd.migrate.extractors.postgresql import PostgreSQLSchemaExtractor

extractor = PostgreSQLSchemaExtractor(manager)
tables = extractor.extract(schema="public")        # → list[CanonicalTable]
views  = extractor.extract_views(schema="public")  # → list[CanonicalView]
```

**Parámetros SQL**: estilo `%(name)s` (psycopg2/psycopg3).

**auto_increment**: detectado cuando `COLUMN_DEFAULT` comienza con `nextval(` (SERIAL/BIGSERIAL/SMALLSERIAL).

**char_length**: `None` para tipos sin límite (`text`, `json`, `bytea`, etc.); valor entero para tipos con longitud.

**Índices no-PK**: extraídos via `pg_catalog.pg_index` + `generate_subscripts` (PG 8.4+).

---

## Type Maps

### `resolve_postgresql_type_oracle(pg_type: str) → TypeMappingPostgreSQLToOracle | None`

```python
from util_bbdd.migrate._compat.type_map_postgresql_to_oracle import (
    resolve_postgresql_type_oracle,
    TypeMappingPostgreSQLToOracle,
    POSTGRESQL_TO_ORACLE,
)

mapping = resolve_postgresql_type_oracle("CHARACTER VARYING")
# mapping.oracle_type → "VARCHAR2"
# mapping.warning_msg → None

mapping = resolve_postgresql_type_oracle("BOOLEAN")
# mapping.oracle_type → "NUMBER(1,0)"
# mapping.severity    → "WARNING"
```

### `resolve_postgresql_type_mariadb(pg_type: str) → TypeMappingPostgreSQLToMariaDB | None`

```python
from util_bbdd.migrate._compat.type_map_postgresql_to_mariadb import (
    resolve_postgresql_type_mariadb,
)

mapping = resolve_postgresql_type_mariadb("TIMESTAMP WITHOUT TIME ZONE")
# mapping.mariadb_type → "DATETIME(6)"
```

### `resolve_postgresql_type_sqlserver(pg_type: str) → TypeMappingPostgreSQLToSQLServer | None`

```python
from util_bbdd.migrate._compat.type_map_postgresql_to_sqlserver import (
    resolve_postgresql_type_sqlserver,
)

mapping = resolve_postgresql_type_sqlserver("UUID")
# mapping.ss_type → "UNIQUEIDENTIFIER"
```

**Claves**: el argumento debe ser el `DATA_TYPE` de `INFORMATION_SCHEMA.COLUMNS` en UPPERCASE,
sin parámetros. Los tipos multi-palabra se buscan como clave completa:
`"CHARACTER VARYING"`, `"TIMESTAMP WITH TIME ZONE"`, etc.

---

## Transformers

### `PostgreSQLToOracleTransformer`

```python
from util_bbdd.migrate.transformers.postgresql_to_oracle import PostgreSQLToOracleTransformer

t = PostgreSQLToOracleTransformer()
tables = t.transform(raw_tables)         # list[CanonicalTable] → list[CanonicalTable]
views  = t.transform_views(raw_views)    # list[CanonicalView]  → list[CanonicalView]
```

**Resolución dinámica**:

| Tipo PG | char_length | Resultado Oracle |
|---|---|---|
| `CHARACTER VARYING` | `None` | `CLOB` |
| `CHARACTER VARYING` | `n > 4000` | `CLOB` + WARNING |
| `CHARACTER VARYING` | `n ≤ 4000` | `VARCHAR2(n)` |
| `NUMERIC` | precision/scale | `NUMBER(p,s)` |
| `BIT` | `n` | `CHAR(n)` |
| `BIT VARYING` | `n` | `VARCHAR2(n)` |

**Límite de identificadores**: 30 chars (Oracle 12.1). Identificadores más largos se truncan
con sufijo hash de 4 chars para unicidad.

### `PostgreSQLToMariaDBTransformer`

```python
from util_bbdd.migrate.transformers.postgresql_to_mariadb import PostgreSQLToMariaDBTransformer
```

**Resolución dinámica**:

| Tipo PG | char_length | Resultado MariaDB |
|---|---|---|
| `CHARACTER VARYING` | `None` | `LONGTEXT` |
| `CHARACTER VARYING` | `n` | `VARCHAR(n)` |
| `NUMERIC` | precision/scale | `DECIMAL(p,s)` |
| `BIT` | `n` | `BIT(n)` |
| `BIT VARYING` | `n` | `VARBINARY(ceil(n/8))` |

**Límite de identificadores**: 64 chars.

### `PostgreSQLToSQLServerTransformer`

```python
from util_bbdd.migrate.transformers.postgresql_to_sqlserver import PostgreSQLToSQLServerTransformer
```

**Resolución dinámica**:

| Tipo PG | char_length | Resultado SQL Server |
|---|---|---|
| `CHARACTER VARYING` | `None` | `NVARCHAR(MAX)` |
| `CHARACTER VARYING` | `n > 4000` | `NVARCHAR(MAX)` + WARNING |
| `CHARACTER VARYING` | `n ≤ 4000` | `NVARCHAR(n)` |
| `NUMERIC` | precision/scale | `NUMERIC(p,s)` |
| `BIT VARYING` | `n` | `VARBINARY(ceil(n/8))` |

**Límite de identificadores**: 128 chars.

---

## Planner

```python
from util_bbdd.migrate import MigrationPlanner

planner = MigrationPlanner(
    source_engine="postgresql",   # nuevo en v1.x
    target_engine="oracle",       # "oracle" | "mariadb" | "sqlserver"
    # Parámetros opcionales según target:
    charset="utf8mb4",            # MariaDB
    collation="utf8mb4_unicode_ci",
    sql_server_collation=None,    # SQL Server
)
plan = planner.plan(connection=manager, schema="public")
ddl = plan.emit_ddl()
```

**Motores soportados** (después de esta versión):

| Fuente | Destinos soportados |
|---|---|
| `oracle` | `mariadb`, `sqlserver`, `postgresql` |
| `mariadb` | `oracle`, `sqlserver`, `postgresql` |
| `sqlserver` | `oracle`, `mariadb`, `postgresql` |
| `postgresql` | `oracle`, `mariadb`, `sqlserver` |

**Restricción**: `source_engine ≠ target_engine`.

---

## Tipos disponibles en exports públicos

```python
from util_bbdd.migrate import (
    PostgreSQLSchemaExtractor,
    PostgreSQLToOracleTransformer,
    PostgreSQLToMariaDBTransformer,
    PostgreSQLToSQLServerTransformer,
)
```
