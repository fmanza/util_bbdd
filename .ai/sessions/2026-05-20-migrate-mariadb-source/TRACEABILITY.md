# TRACEABILITY

## Session metadata
- id: 2026-05-20-migrate-mariadb-source
- fecha: 2026-05-20
- rama: develop
- skill: new_feature
- fase: PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued

```
Queremos ampliar las funcionalidades actuales del módulo migrate,
contemplar la migración de MariaDB hacia Oracle / SQL Server / PostgreSQL.
En la carpeta .ai se encuentra todo el proceso realizado hasta la fecha,
empezando en esta fecha .ai\sessions\2026-05-18-migrate-oracle-mariadb en adelante.
```

Decisiones adicionales (AskUserQuestion):
- Vistas v1: **pass-through** (sin reescritura SQL; warning para revisión manual)
- Identificadores Oracle: **double-quote + uppercase** (`"TABLE_NAME"`)

## Context supplied
- Módulo `migrate/` con soporte completo Oracle → MariaDB / SQL Server / PostgreSQL + vistas
- Sesiones anteriores: 2026-05-18 → 2026-05-20-migrate-views
- Sesión comprimida (context window) — continuación en nueva ventana con summary

## AI output summary

### Nuevos componentes

#### Extractor (`extractors/mariadb.py`)
- `MariaDBSchemaExtractor` — Lee tablas, columnas, PKs, FKs, índices y vistas de
  `INFORMATION_SCHEMA` con param style `%(name)s` (PyMySQL/MariaDB Connector).
- Detecta `AUTO_INCREMENT` en campo `EXTRA`.
- FKs cross-database → `is_external=True` cuando `ref_schema != schema`.
- `oracle_type` reusado como campo "tipo fuente MariaDB" (DATA_TYPE de INFORMATION_SCHEMA).

#### Type maps (`_compat/`)
- `type_map_mariadb_to_oracle.py` — `TypeMappingMariaToOracle` + `MARIADB_TO_ORACLE` +
  `resolve_mariadb_type_oracle()`. Cubre INT→NUMBER(10,0)/NUMBER(19,0), VARCHAR→VARCHAR2,
  TEXT/LONGTEXT→CLOB, BLOB, DATETIME→DATE, TIMESTAMP (WARNING), BOOL→NUMBER(1,0),
  JSON→CLOB (WARNING), ENUM (WARNING+ddl_comment), BIT (WARNING), UUID→CHAR(36),
  GEOMETRY (ERROR).
- `type_map_mariadb_to_sqlserver.py` — `MARIADB_TO_SQLSERVER` + `resolve_mariadb_type_sqlserver()`.
  TINYINT signed/unsigned WARNING, JSON WARNING, TIMESTAMP WARNING, UUID→UNIQUEIDENTIFIER.
- `type_map_mariadb_to_postgresql.py` — `MARIADB_TO_POSTGRESQL` + `resolve_mariadb_type_postgresql()`.
  JSON→JSONB (INFO), ENUM→TEXT (WARNING), BIT(n) nativo, UUID→UUID, TINYINT→SMALLINT.

#### Identifier rules
- `MAX_ORACLE_IDENTIFIER_LENGTH: int = 30` añadido a `_compat/identifier_rules.py`.

#### Transformers
- `MariaDBToOracleTransformer` — id. truncados a 30 chars; VARCHAR>4000→CLOB,
  VARBINARY>2000→BLOB, BIT(1)→NUMBER(1,0), BIT(n)→RAW(ceil(n/8)), DECIMAL/NUMERIC(p,s),
  ENUM→VARCHAR2(255); FK ON UPDATE → WARNING (Oracle no soporta ON UPDATE CASCADE);
  `auto_increment` preservado para SEQUENCE+TRIGGER.
- `MariaDBToSQLServerTransformer` — id. truncados a 128; VARCHAR/NVARCHAR(n),
  CHAR/NCHAR, BINARY/VARBINARY con umbral 8000→MAX; `auto_increment` preservado
  para IDENTITY(1,1).
- `MariaDBToPostgreSQLTransformer` — id. truncados a 63; VARCHAR(n), CHAR(n), BIT(n)
  nativo, NUMERIC(p,s); `auto_increment` preservado para SERIAL/BIGSERIAL/SMALLSERIAL.

#### Emitter Oracle (`emitters/oracle.py`)
- `OracleDDLEmitter` — identificadores `"UPPER_CASE"` (double-quoted).
- `_seq_name` / `_trg_name` — nombres ≤30 chars (26 prefix + sufijo).
- SEQUENCE + TRIGGER por columna `auto_increment` (patrón clásico, compatible Oracle 11g+).
- COMMENT ON TABLE / COMMENT ON COLUMN para comentarios no vacíos.
- ON DELETE: solo CASCADE/SET NULL; ON UPDATE silenciado (ya avisado por transformer).
- Vistas: `CREATE OR REPLACE VIEW "NAME" AS`.
- Orden topológico tablas+vistas reutilizando `_topological_sort` / `_topological_sort_views`
  de `emitters/mariadb.py`.
- `_format_default_oracle()` — NOW()→SYSDATE, CURRENT_TIMESTAMP→SYSDATE,
  CURRENT_DATE→TRUNC(SYSDATE), TRUE→1, FALSE→0.

#### Vistas v1 (pass-through)
Los 3 transformers MariaDB emiten vistas sin reescritura SQL, añadiendo
`MigrationWarning(severity="WARNING")` con aviso de revisión manual para
funciones dialect-específicas de MariaDB (NOW, IFNULL, GROUP_CONCAT, etc.).

#### Planner (`planner.py`)
- `source_engine="mariadb"` soportado junto a `"oracle"`.
- `target_engine="oracle"` soportado junto a los existentes.
- Validación `src == tgt` → `ValueError`.
- `_plan_from_mariadb()` nuevo pipeline: `MariaDBSchemaExtractor` + transformer MariaDB + emitter.

#### Module `__init__.py`
- Exports añadidos: `MariaDBSchemaExtractor`, `MariaDBToOracleTransformer`,
  `OracleDDLEmitter`, `MariaDBToSQLServerTransformer`, `MariaDBToPostgreSQLTransformer`.
- Docstring actualizado con ejemplos de uso para los 3 flujos MariaDB→*.

### Tests

| Fichero | Tests | Cobertura |
|---|---|---|
| `test_type_map_mariadb.py` | 50 | `resolve_mariadb_type_oracle/sqlserver/postgresql`, case-insensitivity, all keys |
| `test_transformer_mariadb_to_oracle.py` | 31 | Tipos, truncación (30), FK ON UPDATE, views pass-through |
| `test_transformer_mariadb_to_sqlserver.py` | 31 | Tipos, truncación (128), FK externas, views pass-through |
| `test_transformer_mariadb_to_postgresql.py` | 33 | Tipos, truncación (63), FK externas, views pass-through |
| `test_emitter_oracle.py` | 32 | CREATE TABLE, SEQUENCE+TRIGGER, COMMENT ON, índices, vistas, topological sort, `_format_default_oracle` |
| **Total** | **177** | |

### AUDIT_CODE
Veredicto: **APROBADO** — 177/177 tests nuevos, 2583/2583 suite completa. ruff limpio, mypy 0 errores.

## Artefactos generados/modificados

| Artefacto | Ruta | Estado |
|---|---|---|
| Identifier rules | `migrate/_compat/identifier_rules.py` | modificado (+MAX_ORACLE_IDENTIFIER_LENGTH) |
| Type map → Oracle | `migrate/_compat/type_map_mariadb_to_oracle.py` | creado |
| Type map → SQL Server | `migrate/_compat/type_map_mariadb_to_sqlserver.py` | creado |
| Type map → PostgreSQL | `migrate/_compat/type_map_mariadb_to_postgresql.py` | creado |
| MariaDB extractor | `migrate/extractors/mariadb.py` | creado |
| Transformer → Oracle | `migrate/transformers/mariadb_to_oracle.py` | creado |
| Transformer → SQL Server | `migrate/transformers/mariadb_to_sqlserver.py` | creado |
| Transformer → PostgreSQL | `migrate/transformers/mariadb_to_postgresql.py` | creado |
| Oracle emitter | `migrate/emitters/oracle.py` | creado |
| Planner | `migrate/planner.py` | modificado (+mariadb source, +oracle target, +same-engine guard) |
| Module __init__ | `migrate/__init__.py` | modificado (+5 exports, docstring actualizado) |
| Tests type maps | `tests/unit/migrate/test_type_map_mariadb.py` | creado |
| Tests transformer Oracle | `tests/unit/migrate/test_transformer_mariadb_to_oracle.py` | creado |
| Tests transformer SQL Server | `tests/unit/migrate/test_transformer_mariadb_to_sqlserver.py` | creado |
| Tests transformer PostgreSQL | `tests/unit/migrate/test_transformer_mariadb_to_postgresql.py` | creado |
| Tests emitter Oracle | `tests/unit/migrate/test_emitter_oracle.py` | creado |
| CHANGELOG | `CHANGELOG.md` | modificado ([Unreleased]: MariaDB→Oracle/SQL Server/PostgreSQL) |

## Métricas

| Métrica | Antes | Después |
|---|---|---|
| Tests migrate | 428 | 605 (+177) |
| Tests totales | 2406 | 2583 (+177) |
| Tests skipped | 1 | 1 |
| ruff | ✅ | ✅ |
| mypy | ✅ | ✅ |

## Veredicto final

Veredicto: **CLOSED**

Pendientes al cierre:
- Ninguno. Funcionalidad completa: extractor + 3 transformers + emitter Oracle + 177 tests.
- Vistas v1 pass-through documentado (no es un bug; reescritura SQL para MariaDB→* queda para v2).
