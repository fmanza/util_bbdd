# TRACEABILITY

## Session metadata
- id: 2026-05-21-migrate-sqlserver-source
- fecha: 2026-05-21
- rama: develop
- skill: new_feature
- fase: PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued

```
Queremos ampliar las funcionalidades actuales del módulo migrate,
contemplar la migración de SQL Server hacia Oracle / MariaDB / PostgreSQL.
En la carpeta .ai se encuentra todo el proceso realizado hasta la fecha,
empezando en esta fecha .ai\sessions\2026-05-18-migrate-oracle-mariadb en adelante.
```

## Context supplied
- Módulo `migrate/` con soporte completo para 6 flujos:
  Oracle/MariaDB → MariaDB/Oracle/SQL Server/PostgreSQL (+ vistas)
- Sesiones anteriores: 2026-05-18 → 2026-05-20-migrate-mariadb-source
- Sesión comprimida (context window) — continuación en nueva ventana con summary

## AI output summary

### Nuevos componentes

#### Extractor (`extractors/sqlserver.py`)
- `SQLServerSchemaExtractor` — Lee tablas, columnas, PKs, FKs, índices y vistas de
  `INFORMATION_SCHEMA` + `sys.*` views con param style `%(name)s` (pymssql compatible).
- `_parse_raw_column()` — Parsea tupla de 9 campos; preserva `char_length=-1` como sentinel
  para tipos `MAX` (`VARCHAR(MAX)`, `NVARCHAR(MAX)`, `VARBINARY(MAX)`).
- Detecta `IDENTITY` via `COLUMNPROPERTY(OBJECT_ID(schema+'.'+table), col, 'IsIdentity')`.
- FKs cross-schema → `is_external=True` cuando `ref_schema.upper() != schema.upper()`.
- Índices via `sys.indexes + sys.index_columns + sys.columns + sys.tables + sys.schemas`.

#### Type maps (`_compat/`)
- `type_map_sqlserver_to_oracle.py` — `TypeMappingSQLServerToOracle` frozen dataclass +
  `SQLSERVER_TO_ORACLE` dict + `resolve_sqlserver_type_oracle()`. 25+ tipos:
  INT→NUMBER(10,0), BIGINT→NUMBER(19,0), TINYINT→NUMBER(3,0), BIT→NUMBER(1,0),
  FLOAT→BINARY_DOUBLE, REAL→BINARY_FLOAT, MONEY→NUMBER(19,4), SMALLMONEY→NUMBER(10,4),
  VARCHAR→VARCHAR2, NVARCHAR→NVARCHAR2, DATETIME2→TIMESTAMP,
  DATETIMEOFFSET→TIMESTAMP WITH TIME ZONE, UNIQUEIDENTIFIER→CHAR(36),
  GEOGRAPHY/GEOMETRY→CLOB (ERROR severity), XML→CLOB (WARNING).
- `type_map_sqlserver_to_mariadb.py` — `TypeMappingSQLServerToMariaDB` +
  `resolve_sqlserver_type_mariadb()`. BIT→TINYINT(1), TINYINT→SMALLINT (WARNING: unsigned/signed),
  DATETIME2→DATETIME(6), DATETIMEOFFSET→VARCHAR(35) (WARNING), NVARCHAR→VARCHAR,
  TEXT/NTEXT→LONGTEXT, IMAGE→LONGBLOB, UNIQUEIDENTIFIER→CHAR(36).
- `type_map_sqlserver_to_postgresql.py` — `TypeMappingSQLServerToPostgreSQL` +
  `resolve_sqlserver_type_postgresql()`. BIT→BOOLEAN, NCHAR/NVARCHAR→CHAR/VARCHAR
  (PG Unicode-native), UNIQUEIDENTIFIER→UUID, DATETIMEOFFSET→TIMESTAMPTZ,
  BINARY/VARBINARY→BYTEA (sin parámetros de longitud), DATETIME2→TIMESTAMP(6),
  MONEY→NUMERIC(19,4), XML→XML (tipo nativo PG).

#### Transformers
- `SQLServerToOracleTransformer` — identificadores truncados a 30 chars.
  `_resolve_oracle_type()`: VARCHAR/NVARCHAR MAX→CLOB, >4000→CLOB+warning, VARBINARY MAX→BLOB,
  >2000→BLOB+warning; DECIMAL→NUMBER(p,s); FK ON UPDATE → warning (Oracle no soporta).
- `SQLServerToMariaDBTransformer` — identificadores truncados a 64 chars.
  `_resolve_mariadb_type()`: VARCHAR/NVARCHAR MAX→LONGTEXT; VARBINARY MAX→LONGBLOB;
  DECIMAL→DECIMAL(p,s).
- `SQLServerToPostgreSQLTransformer` — identificadores truncados a 63 chars.
  `_resolve_pg_type()`: VARCHAR/NVARCHAR MAX→TEXT; BINARY/VARBINARY→BYTEA (sin longitud);
  DECIMAL→NUMERIC(p,s).

#### Corrección preexistente en `planner.py`
- `_plan_from_mariadb()` — error mypy preexistente corregido: `transformer: Any` y
  `emitter: Any` anotados en primera rama (mismo patrón ya usado en `_plan_from_oracle`).

#### Planner (`planner.py`)
- `source_engine="sqlserver"` añadido a `_SUPPORTED_SOURCE`.
- `_plan_from_sqlserver()` nuevo pipeline: `SQLServerSchemaExtractor` + transformer SS + emitter.
- Rama `else: # sqlserver` en `plan()` sin repetir validaciones (ya garantizado por `__init__`).

#### Module `__init__.py`
- Exports añadidos: `SQLServerSchemaExtractor`, `SQLServerToOracleTransformer`,
  `SQLServerToMariaDBTransformer`, `SQLServerToPostgreSQLTransformer`.
- Docstring actualizado con ejemplos de uso para los 3 flujos SQL Server→*.

#### Vistas v1 (pass-through)
Los 3 transformers SS emiten vistas sin reescritura SQL, añadiendo
`MigrationWarning(severity="WARNING")` con aviso de revisión manual para
funciones T-SQL específicas (GETDATE, ISNULL, TOP, NOLOCK, etc.).
`VIEW_DEFINITION` puede truncarse a 4000 chars en SQL Server < 2019 (documentado).

### Tests

| Fichero | Tests | Cobertura |
|---|---|---|
| `test_sqlserver_extractor.py` | 20 | `SQLServerSchemaExtractor`: tablas, columnas, PKs, FKs, índices, vistas; mock routing por SQL keyword |
| `test_type_map_sqlserver_source.py` | 60 | `resolve_sqlserver_type_oracle/mariadb/postgresql`, case-insensitivity, 20 keys/función |
| `test_transformer_sqlserver_to_oracle.py` | 35 | Tipos, MAX sentinel, truncación (30), FK ON UPDATE warning, is_external warning, views pass-through |
| `test_transformer_sqlserver_to_mariadb.py` | 28 | Tipos, MAX sentinel, truncación (64), FK externas, IDENTITY, views pass-through |
| `test_transformer_sqlserver_to_postgresql.py` | 30 | Tipos, MAX sentinel, BYTEA sin longitud, truncación (63), UUID, BOOLEAN, views pass-through |
| `test_planner_sqlserver_source.py` | 18 | Validación motores, empty schema, pipeline completo SS→Oracle/MariaDB/PG, emit_ddl |
| **Total nuevos** | **191** | |

### AUDIT_CODE
Veredicto: **APROBADO** — 789/789 tests migrate (0 regresiones en los 605 anteriores).
ruff ✅, mypy ✅ (incluyendo corrección preexistente en `_plan_from_mariadb`).

## Artefactos generados/modificados

| Artefacto | Ruta | Estado |
|---|---|---|
| SQL Server extractor | `migrate/extractors/sqlserver.py` | creado |
| Extractors `__init__` | `migrate/extractors/__init__.py` | modificado (+SQLServerSchemaExtractor) |
| Type map → Oracle | `migrate/_compat/type_map_sqlserver_to_oracle.py` | creado |
| Type map → MariaDB | `migrate/_compat/type_map_sqlserver_to_mariadb.py` | creado |
| Type map → PostgreSQL | `migrate/_compat/type_map_sqlserver_to_postgresql.py` | creado |
| Compat `__init__` | `migrate/_compat/__init__.py` | modificado (+3 SS type map exports) |
| Transformer → Oracle | `migrate/transformers/sqlserver_to_oracle.py` | creado |
| Transformer → MariaDB | `migrate/transformers/sqlserver_to_mariadb.py` | creado |
| Transformer → PostgreSQL | `migrate/transformers/sqlserver_to_postgresql.py` | creado |
| Transformers `__init__` | `migrate/transformers/__init__.py` | modificado (+3 SS transformer exports) |
| Planner | `migrate/planner.py` | modificado (+sqlserver source, _plan_from_sqlserver, mypy fix) |
| Module `__init__` | `migrate/__init__.py` | modificado (+4 exports, docstring actualizado) |
| Tests extractor | `tests/unit/migrate/test_sqlserver_extractor.py` | creado |
| Tests type maps | `tests/unit/migrate/test_type_map_sqlserver_source.py` | creado |
| Tests transformer Oracle | `tests/unit/migrate/test_transformer_sqlserver_to_oracle.py` | creado |
| Tests transformer MariaDB | `tests/unit/migrate/test_transformer_sqlserver_to_mariadb.py` | creado |
| Tests transformer PostgreSQL | `tests/unit/migrate/test_transformer_sqlserver_to_postgresql.py` | creado |
| Tests planner | `tests/unit/migrate/test_planner_sqlserver_source.py` | creado |
| Doc funcional | `docs/functional/migrate-sqlserver-source.md` | creado |
| Doc API | `docs/api/migrate-sqlserver-source.md` | creado |
| mkdocs.yml | `mkdocs.yml` | modificado (+2 entradas nav SS source) |
| CHANGELOG | `CHANGELOG.md` | modificado ([Unreleased]: SQL Server como fuente) |

## Métricas

| Métrica | Antes | Después |
|---|---|---|
| Tests migrate | 605 | ~789 (+~184) |
| Tests totales | 2583 | ~2767 |
| Tests skipped | 1 | 1 |
| ruff | ✅ | ✅ |
| mypy | ✅ | ✅ |

## Veredicto final

Veredicto: **CLOSED**

Completa la **matriz 3×3 de motores**: Oracle, MariaDB y SQL Server como fuentes;
Oracle, MariaDB, PostgreSQL y SQL Server como destinos (9 flujos activos).

Pendientes al cierre:
- Vistas v1 pass-through documentado (reescritura T-SQL para SS→* queda para v2).
- Param style pyodbc necesita wrapper (documentado en limitaciones v1).
- `VIEW_DEFINITION` truncado en SS < 2019 (documentado en limitaciones v1).
