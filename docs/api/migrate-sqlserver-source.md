# API migrate — SQL Server como fuente

## SQLServerSchemaExtractor

**Módulo**: `util_bbdd.migrate.extractors.sqlserver`

Extrae el esquema SQL Server hacia IR canónico (`CanonicalTable`, `CanonicalView`).

### Constructor

```python
SQLServerSchemaExtractor(manager: Any)
```

| Parámetro | Tipo | Descripción |
|---|---|---|
| `manager` | Any | SyncDatabaseManager compatible. Requiere `execute_custom_many(sql, params) → Rows`. Param style: `%(name)s` (pymssql). |

### Métodos

#### `extract(schema: str) → list[CanonicalTable]`

Extrae todas las tablas `BASE TABLE` del `TABLE_SCHEMA` indicado.

- Detecta IDENTITY mediante `COLUMNPROPERTY(OBJECT_ID(...), col, 'IsIdentity')`.
- Preserva `char_length=-1` para tipos `MAX`.
- `is_external=True` en FKs cuando `REF_SCHEMA != schema`.

#### `extract_views(schema: str) → list[CanonicalView]`

Extrae todas las vistas. `CanonicalView.query` contiene `VIEW_DEFINITION` de
`INFORMATION_SCHEMA.VIEWS`.

---

## Mapas de tipos

### `type_map_sqlserver_to_oracle`

**Módulo**: `util_bbdd.migrate._compat.type_map_sqlserver_to_oracle`

```python
TypeMappingSQLServerToOracle(
    source_base: str,
    oracle_type: str,
    warning_msg: str | None = None,
    proposals: tuple[str, ...] = (),
    requires_ddl_comment: bool = False,
    ddl_comment: str | None = None,
    severity: WarningSeverity = "INFO",
)
```

```python
resolve_sqlserver_type_oracle(sqlserver_type: str) → TypeMappingSQLServerToOracle | None
```

### `type_map_sqlserver_to_mariadb`

**Módulo**: `util_bbdd.migrate._compat.type_map_sqlserver_to_mariadb`

```python
resolve_sqlserver_type_mariadb(sqlserver_type: str) → TypeMappingSQLServerToMariaDB | None
```

### `type_map_sqlserver_to_postgresql`

**Módulo**: `util_bbdd.migrate._compat.type_map_sqlserver_to_postgresql`

```python
resolve_sqlserver_type_postgresql(sqlserver_type: str) → TypeMappingSQLServerToPostgreSQL | None
```

---

## Transformers

### `SQLServerToOracleTransformer`

**Módulo**: `util_bbdd.migrate.transformers.sqlserver_to_oracle`

```python
transformer = SQLServerToOracleTransformer()
tables = transformer.transform(raw_tables)      # list[CanonicalTable]
views  = transformer.transform_views(raw_views) # list[CanonicalView]
```

**Reglas de identificadores**: truncado a 30 chars (Oracle 12.1).

**Reglas especiales**:
- `VARCHAR(MAX)`/`NVARCHAR(MAX)` → `CLOB`
- `VARCHAR(n>4000)` → `CLOB` + warning
- `VARBINARY(n>2000)` → `BLOB` + warning; `VARBINARY(MAX)` → `BLOB`
- `DECIMAL(p,s)` → `NUMBER(p,s)`; default `NUMBER(18,0)` si sin precision
- FK `ON UPDATE CASCADE` → warning (Oracle no soporta ON UPDATE)

### `SQLServerToMariaDBTransformer`

**Módulo**: `util_bbdd.migrate.transformers.sqlserver_to_mariadb`

**Reglas de identificadores**: truncado a 64 chars.

**Reglas especiales**:
- `VARCHAR(MAX)`/`NVARCHAR(MAX)` → `LONGTEXT`
- `VARBINARY(MAX)` → `LONGBLOB`
- `DATETIME2` → `DATETIME(6)` (SS hasta 7 fracciones, MariaDB max 6)
- `DATETIMEOFFSET` → `VARCHAR(35)` + warning

### `SQLServerToPostgreSQLTransformer`

**Módulo**: `util_bbdd.migrate.transformers.sqlserver_to_postgresql`

**Reglas de identificadores**: truncado a 63 chars.

**Reglas especiales**:
- `VARCHAR(MAX)`/`NVARCHAR(MAX)` → `TEXT`
- `BINARY`/`VARBINARY` → `BYTEA` (PostgreSQL no acepta longitud en BYTEA)
- `DATETIME2` → `TIMESTAMP(6)`
- `DATETIMEOFFSET` → `TIMESTAMPTZ`

---

## MigrationPlanner — parámetros para SQL Server source

```python
MigrationPlanner(
    source_engine="sqlserver",          # nuevo valor soportado
    target_engine="oracle",             # o "mariadb" o "postgresql"
    # Sólo aplican según target_engine:
    charset="utf8mb4",                  # target=mariadb
    collation="utf8mb4_unicode_ci",     # target=mariadb
    engine="InnoDB",                    # target=mariadb
    pg_schema="mi_schema",             # target=postgresql (opcional)
    sql_server_collation="...",         # target=sqlserver (no aplica aquí)
)
plan = planner.plan(connection=sqlserver_manager, schema="dbo")
```

El parámetro `schema` en `plan()` corresponde a `TABLE_SCHEMA` en SQL Server
(habitualmente `'dbo'`).

---

## Contratos IR preservados

| Campo IR | Fuente SQL Server |
|---|---|
| `CanonicalColumn.oracle_type` | `DATA_TYPE` de `INFORMATION_SCHEMA.COLUMNS` (nombre histórico) |
| `CanonicalColumn.char_length` | `CHARACTER_MAXIMUM_LENGTH` (-1 para MAX) |
| `CanonicalColumn.precision` | `NUMERIC_PRECISION` |
| `CanonicalColumn.scale` | `NUMERIC_SCALE` |
| `CanonicalColumn.auto_increment` | `COLUMNPROPERTY(..., 'IsIdentity')` |
| `CanonicalFK.is_external` | `REF_SCHEMA != schema` |
| `CanonicalIndex.unique` | `sys.indexes.is_unique` |
