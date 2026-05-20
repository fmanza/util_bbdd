# TRACEABILITY

## Session metadata
- id: 2026-05-20-migrate-oracle-postgresql
- fecha: 2026-05-20
- rama: develop
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
/new-feature

Objetivo: Ampliar el módulo migrate/ para soportar migración DDL Oracle → PostgreSQL

Alcance:
  - src/util_bbdd/migrate/_compat/type_map_postgresql.py (nuevo)
  - src/util_bbdd/migrate/_compat/identifier_rules.py (añadir MAX_POSTGRESQL_IDENTIFIER_LENGTH=63)
  - src/util_bbdd/migrate/transformers/oracle_to_postgresql.py (nuevo)
  - src/util_bbdd/migrate/emitters/postgresql.py (nuevo)
  - src/util_bbdd/migrate/planner.py (ampliar: postgresql en _SUPPORTED_TARGET, parámetro pg_schema)
  - src/util_bbdd/migrate/__init__.py (ampliar exports)
  - tests/unit/migrate/test_type_map_postgresql.py (nuevo)
  - tests/unit/migrate/test_transformer_postgresql.py (nuevo)
  - tests/unit/migrate/test_emitter_postgresql.py (nuevo)
```

## Context supplied
- `src/util_bbdd/migrate/` — módulo Oracle→MariaDB + Oracle→SQL Server implementados
- Sesiones previas: 2026-05-18, 2026-05-19, 2026-05-19b/c/d/e/f/g, 2026-05-20-migrate-oracle-sqlserver
- Arquitectura base: extractor/transformer/emitter con IR canónico

## AI output summary

### Fase new_feature — IMPLEMENT (10 ficheros)

#### Level 1 — Constante + Type map
1. Modificado `_compat/identifier_rules.py`:
   - Añadido `MAX_POSTGRESQL_IDENTIFIER_LENGTH: int = 63`
   - Actualizado docstring y `__all__`
2. Creado `_compat/type_map_postgresql.py`:
   - `TypeMappingPostgreSQL` dataclass (frozen+slots, campo `pg_type`)
   - `ORACLE_TO_POSTGRESQL` dict: 30+ entradas
   - `resolve_oracle_type_postgresql()` — lookup case-insensitive
   - `resolve_number_type_postgresql()` — SMALLINT/INTEGER/BIGINT/NUMERIC según precision/scale
   - Diferencias clave vs SQL Server: INTERVAL nativo, VARCHAR (no NVARCHAR), BYTEA, TEXT, TIMESTAMPTZ, DOUBLE PRECISION

#### Level 2 — Transformer
3. Creado `transformers/oracle_to_postgresql.py`:
   - `OracleToPostgreSQLTransformer` — misma estructura que los transformers existentes
   - Usa `check_identifier(name, MAX_POSTGRESQL_IDENTIFIER_LENGTH=63)`
   - `_handle_pk_serial()` — PK única entera → `auto_increment=True` (SERIAL semantics)
   - `_handle_sequence_columns()` — NEXTVAL → SERIAL
   - `_build_target_type()`: VARCHAR(n) para VARCHAR2/NVARCHAR2; TIMESTAMP(n) cap a 6; CHAR(n); NUMERIC(p,s)
   - NUMBER PK sin precisión → INTEGER
   - FK externas → warning "ALTER TABLE al final"
   - Tipo desconocido → TEXT (vs NVARCHAR(MAX) en SQL Server)

#### Level 3 — Emitter + Planner + Exports
4. Creado `emitters/postgresql.py`:
   - `PostgreSQLDDLEmitter(pg_schema=None)`
   - `"double_quotes"` escaping (vs backtick MariaDB / corchetes SQL Server)
   - `SERIAL`/`BIGSERIAL`/`SMALLSERIAL` según tipo base (vs IDENTITY(1,1) SQL Server)
   - SERIAL omite `NOT NULL` y `DEFAULT` implícitos (corrección de invariante PG)
   - `SET search_path = "schema";` al inicio si `pg_schema` no es None
   - Sin `ENGINE=`, `CHARSET=`, ni `COLLATE`
   - Defaults Oracle → PG: SYSDATE→NOW(), SYS_GUID()→gen_random_uuid(), USER→CURRENT_USER
   - FK circulares/externas → ALTER TABLE al final
   - Importa `_topological_sort` de `emitters.mariadb` (reutilización sin duplicar)
5. Modificado `planner.py`:
   - `_SUPPORTED_TARGET`: `{"mariadb", "sqlserver", "postgresql"}`
   - Nuevo parámetro `pg_schema: str | None = None`
   - `_PG_FALLBACK_REMAP`: `"DOUBLE"→"DOUBLE PRECISION"` para PostgreSQL
   - Rama `elif sqlserver / else postgresql` en `plan()`
   - Tipo de unión transformer/emitter ampliado con nuevas clases
6. Modificado `__init__.py`: docstring + exports `OracleToPostgreSQLTransformer`, `PostgreSQLDDLEmitter`

#### Tests (122 nuevos)
7. Creado `tests/unit/migrate/test_type_map_postgresql.py` — 46 tests
8. Creado `tests/unit/migrate/test_transformer_postgresql.py` — 45 tests
9. Creado `tests/unit/migrate/test_emitter_postgresql.py` — 31 tests
10. Modificado `tests/unit/migrate/test_planner.py` — `test_invalid_target_raises` actualizado
    (`"postgresql"` era el valor inválido de prueba; reemplazado por `"db2"`)

### Fase audit_code
Veredicto: **APROBADO**
- Sin bugs potenciales activos
- Edge cases cubiertos: NUMBER PK sin precisión → INTEGER, TIMESTAMP cap 6, SERIAL sin NOT NULL, PK compuesta sin SERIAL, INTERVAL nativo PG
- ruff: 0 errores
- mypy: 0 errores (26 source files en migrate/)

## Artefactos generados/modificados

| Artefacto | Ruta | Estado |
|---|---|---|
| Identifier rules | `_compat/identifier_rules.py` | modificado (+PG max 63) |
| Type map PostgreSQL | `_compat/type_map_postgresql.py` | creado |
| Transformer PostgreSQL | `transformers/oracle_to_postgresql.py` | creado |
| Emitter PostgreSQL | `emitters/postgresql.py` | creado |
| Planner | `planner.py` | modificado (postgresql target, pg_schema) |
| Module init | `__init__.py` | modificado |
| Tests type map PG | `tests/unit/migrate/test_type_map_postgresql.py` | creado |
| Tests transformer PG | `tests/unit/migrate/test_transformer_postgresql.py` | creado |
| Tests emitter PG | `tests/unit/migrate/test_emitter_postgresql.py` | creado |
| Tests planner | `tests/unit/migrate/test_planner.py` | modificado |

## Métricas

| Métrica | Antes | Después |
|---|---|---|
| Tests migrate | 213 | 335 (+122) |
| Tests totales | 2191 | 2313 (+122) |
| ruff | ✅ | ✅ |
| mypy migrate | ✅ | ✅ |

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre: Ninguno. Implementación completa, 335 tests migrate verdes, 2313 totales, ruff+mypy limpios. Backward compat con Oracle→MariaDB y Oracle→SQL Server 100% preservada.
