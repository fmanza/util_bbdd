# TRACEABILITY

## Session metadata
- id: 2026-05-20-migrate-oracle-sqlserver
- fecha: 2026-05-20
- rama: develop
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
/new-feature

Objetivo: Ampliar el módulo migrate/ para soportar migración DDL Oracle → SQL Server

Alcance:
  - src/util_bbdd/migrate/_compat/type_map_sqlserver.py (nuevo)
  - src/util_bbdd/migrate/_compat/identifier_rules.py (añadir MAX_SQLSERVER_IDENTIFIER_LENGTH + check_identifier paramétrico)
  - src/util_bbdd/migrate/transformers/oracle_to_sqlserver.py (nuevo)
  - src/util_bbdd/migrate/emitters/sqlserver.py (nuevo)
  - src/util_bbdd/migrate/planner.py (ampliar: sqlserver en _SUPPORTED_TARGET, parámetro sql_server_collation)
  - src/util_bbdd/migrate/__init__.py (ampliar exports)
  - src/util_bbdd/migrate/reporters/markdown.py (corregir "Tipo MariaDB" → "Tipo destino" genérico)
  - tests/unit/migrate/test_type_map_sqlserver.py (nuevo)
  - tests/unit/migrate/test_transformer_sqlserver.py (nuevo)
  - tests/unit/migrate/test_emitter_sqlserver.py (nuevo)
```

## Context supplied
- `src/util_bbdd/migrate/` — módulo Oracle→MariaDB implementado en sesiones previas (100 tests)
- Sesiones: 2026-05-18, 2026-05-19, 2026-05-19b/c/d/e/f/g
- Arquitectura base: extractor/transformer/emitter con IR canónico

## AI output summary

### Fase new_feature — IMPLEMENT (10 ficheros)

#### Level 1 — Tipos e identificadores
1. Modificado `_compat/identifier_rules.py`:
   - Añadido `MAX_SQLSERVER_IDENTIFIER_LENGTH: int = 128`
   - `truncate_identifier(name, max_length=64)` — parámetro `max_length` con default backward compat
   - `check_identifier(name, max_length=64)` — ídem; mensaje genérico `"límite de {max_length}"`
2. Creado `_compat/type_map_sqlserver.py`:
   - `TypeMappingSQLServer` dataclass (nuevo; campo `sqlserver_type` vs `mariadb_type` de MariaDB)
   - `ORACLE_TO_SQLSERVER` dict: 30+ entradas
   - `resolve_oracle_type_sqlserver()` — lookup case-insensitive
   - `resolve_number_type_sqlserver()` — misma lógica que MariaDB pero retorna tipos SS (NUMERIC, FLOAT)

#### Level 2 — Transformer
3. Creado `transformers/oracle_to_sqlserver.py`:
   - `OracleToSQLServerTransformer` — misma estructura que `OracleToMariaDBTransformer`
   - Usa `check_identifier(name, MAX_SQLSERVER_IDENTIFIER_LENGTH=128)` — identificadores SQL Server max 128
   - `_handle_pk_identity()` — PK única entera → `auto_increment=True` (IDENTITY semantics)
   - `_handle_sequence_columns()` — NEXTVAL → IDENTITY(1,1)
   - `_build_target_type()`: NVARCHAR(MAX) si VARCHAR2 > 4000; DATETIME2(7) default sin scale; TIMESTAMP cap a 7
   - FK externas → warning "ALTER TABLE al final"
   - Tipo desconocido → NVARCHAR(MAX) (vs TEXT en MariaDB)

#### Level 3 — Emitter + Planner + Exports + Reporter
4. Creado `emitters/sqlserver.py`:
   - `SQLServerDDLEmitter(collation=None)`
   - `[bracket]` escaping (vs backtick MariaDB)
   - `IDENTITY(1,1)` (vs AUTO_INCREMENT)
   - `NULL` explícito para columnas nullable
   - Sin `ENGINE=` ni `DEFAULT CHARSET=`; sin `COLLATE` a nivel tabla
   - `collation` a nivel columna solo para tipos string (NVARCHAR, VARCHAR, NCHAR, CHAR, NTEXT, TEXT)
   - Comentario columna Oracle → trailing `-- comment` inline; ddl_comment → también trailing
   - Comentario tabla → `-- COMMENT: text` antes del CREATE TABLE
   - Defaults Oracle → SQL Server: SYSDATE→GETDATE(), SYS_GUID()→NEWID(), USER→SYSTEM_USER, etc.
   - FK externas → ALTER TABLE al final con prefijo `-- FK externa:`
   - Importa `_topological_sort` de `emitters.mariadb` (misma lógica Kahn, sin duplicar)
5. Modificado `planner.py`:
   - `_SUPPORTED_TARGET`: `{"mariadb", "sqlserver"}`
   - Nuevo parámetro `sql_server_collation: str | None = None`
   - `charset/collation` no validados para target=sqlserver (sin ValueError)
   - `_SS_FALLBACK_REMAP`: `"DOUBLE"→"FLOAT"` para SQL Server
   - Branch `if mariadb / else sqlserver` en `plan()`
6. Modificado `__init__.py`: exports `OracleToSQLServerTransformer`, `SQLServerDDLEmitter`
7. Modificado `reporters/markdown.py`:
   - `_tables_section(tables, target_engine)` — parámetro adicional
   - `_table_block(table, target_engine)` — header dinámico: `"Tipo {target_engine}"` vs hardcoded "Tipo MariaDB"

#### Tests (113 nuevos)
8. Creado `tests/unit/migrate/test_type_map_sqlserver.py` — 32 tests
9. Creado `tests/unit/migrate/test_transformer_sqlserver.py` — 47 tests
10. Creado `tests/unit/migrate/test_emitter_sqlserver.py` — 34 tests
11. Modificado `tests/unit/migrate/test_planner.py` — 8 tests nuevos (clase `TestMigrationPlannerSQLServer`)

### Fase audit_code
Veredicto: **APROBADO**
- Sin bugs potenciales activos
- Edge cases cubiertos: NVARCHAR(MAX) para VARCHAR2 > 4000, DATETIME2(7) default, NUMBER PK sin precisión → INT IDENTITY
- ruff: 0 errores (2 fixable auto-corregidos por ruff --fix)
- mypy: 0 errores (23 source files)

## Artefactos generados/modificados

| Artefacto | Ruta | Estado |
|---|---|---|
| Identifier rules | `_compat/identifier_rules.py` | modificado (+SQL Server max 128 + `max_length` param) |
| Type map SQL Server | `_compat/type_map_sqlserver.py` | creado |
| Transformer SQL Server | `transformers/oracle_to_sqlserver.py` | creado |
| Emitter SQL Server | `emitters/sqlserver.py` | creado |
| Planner | `planner.py` | modificado (sqlserver target, sql_server_collation) |
| Module init | `__init__.py` | modificado |
| Markdown reporter | `reporters/markdown.py` | modificado (header dinámico) |
| Tests type map SS | `tests/unit/migrate/test_type_map_sqlserver.py` | creado |
| Tests transformer SS | `tests/unit/migrate/test_transformer_sqlserver.py` | creado |
| Tests emitter SS | `tests/unit/migrate/test_emitter_sqlserver.py` | creado |
| Tests planner | `tests/unit/migrate/test_planner.py` | modificado |

## Métricas

| Métrica | Antes | Después |
|---|---|---|
| Tests migrate | 100 | 213 (+113) |
| Tests totales | ~2078 | 2191 + 1 skipped |
| ruff | ✅ | ✅ |
| mypy | ✅ | ✅ |

## Commit message sugerido
```
feat(migrate): Oracle → SQL Server migration pipeline

Adds OracleToSQLServerTransformer, SQLServerDDLEmitter and TypeMappingSQLServer
with 30+ type mappings, IDENTITY(1,1), optional column-level COLLATE,
and FK circular/external handling. MigrationPlanner now supports
target_engine="sqlserver" with sql_server_collation param.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre: Ninguno. Implementación completa, 213 tests migrate verdes, 2191 totales, ruff+mypy limpios. Backward compat con Oracle→MariaDB 100% preservada.
