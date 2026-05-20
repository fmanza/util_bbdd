# TRACEABILITY

## Session metadata
- id: 2026-05-21-migrate-postgresql-source
- fecha: 2026-05-21
- rama: develop
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
Queremos ampliar las funcionalidades actuales del módulo migrate, contemplar la
migración de PostgreSQL hacia Oracle / MariaDB / SQL Server.

## Context supplied
- `.ai/sessions/2026-05-21-migrate-sqlserver-source/` — sesión referencia (patrón a seguir)
- `src/util_bbdd/migrate/extractors/sqlserver.py` — plantilla extractor
- `src/util_bbdd/migrate/_compat/type_map_sqlserver_to_oracle.py` — plantilla type map
- `src/util_bbdd/migrate/transformers/sqlserver_to_oracle.py` — plantilla transformer
- `src/util_bbdd/migrate/planner.py` — planner existente con 3 fuentes

## AI output summary
- PLAN: Definido alcance completo (7 nuevos archivos fuente, 6 tests, 2 docs, 6 archivos modificados)
- AUDIT_PLAN: GO — sin riesgos bloqueantes; restricciones específicas PG (multi-word DATA_TYPE, char_length=None, pg_catalog indexes) documentadas
- IMPLEMENT Layer 1: 3 type maps (postgresql_to_oracle, postgresql_to_mariadb, postgresql_to_sqlserver) creados con 25+ tipos cada uno
- IMPLEMENT Layer 2: `PostgreSQLSchemaExtractor` creado; queries INFORMATION_SCHEMA + pg_catalog.pg_index + generate_subscripts; normalización DATA_TYPE→UPPERCASE; auto_increment via nextval(); char_length=None para sin límite
- IMPLEMENT Layer 2: 3 transformers creados (PG→Oracle 30 chars, PG→MariaDB 64 chars, PG→SQL Server 128 chars); resolución dinámica CHARACTER VARYING / NUMERIC / BIT VARYING
- IMPLEMENT Layer 3: `_compat/__init__.py`, `extractors/__init__.py`, `transformers/__init__.py` actualizados con exports PG
- IMPLEMENT Layer 3: `planner.py` → `_SUPPORTED_SOURCE` ampliado + `_plan_from_postgresql()` añadido; `migrate/__init__.py` → 4 exports nuevos + docstring actualizado
- IMPLEMENT Layer 3: 6 ficheros test creados (~205 tests nuevos); docs functional + api creados; mkdocs.yml + CHANGELOG.md actualizados
- AUDIT_CODE: ruff check — 8 errores auto-fix (import order + unused pytest) aplicados; mypy src/util_bbdd/migrate/ — 49 archivos, 0 issues; ruff final → All checks passed
- pytest: 994 passed (789 existentes + 205 nuevos), 0 failed, 0 regressions

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Type map PG→Oracle | `src/util_bbdd/migrate/_compat/type_map_postgresql_to_oracle.py` | completado |
| Type map PG→MariaDB | `src/util_bbdd/migrate/_compat/type_map_postgresql_to_mariadb.py` | completado |
| Type map PG→SQL Server | `src/util_bbdd/migrate/_compat/type_map_postgresql_to_sqlserver.py` | completado |
| Extractor PostgreSQL | `src/util_bbdd/migrate/extractors/postgresql.py` | completado |
| Transformer PG→Oracle | `src/util_bbdd/migrate/transformers/postgresql_to_oracle.py` | completado |
| Transformer PG→MariaDB | `src/util_bbdd/migrate/transformers/postgresql_to_mariadb.py` | completado |
| Transformer PG→SQL Server | `src/util_bbdd/migrate/transformers/postgresql_to_sqlserver.py` | completado |
| Tests extractor | `tests/unit/migrate/test_postgresql_extractor.py` | completado |
| Tests type maps | `tests/unit/migrate/test_type_map_postgresql_source.py` | completado |
| Tests transformer→Oracle | `tests/unit/migrate/test_transformer_postgresql_to_oracle.py` | completado |
| Tests transformer→MariaDB | `tests/unit/migrate/test_transformer_postgresql_to_mariadb.py` | completado |
| Tests transformer→SQL Server | `tests/unit/migrate/test_transformer_postgresql_to_sqlserver.py` | completado |
| Tests planner | `tests/unit/migrate/test_planner_postgresql_source.py` | completado |
| Docs funcional | `docs/functional/migrate-postgresql-source.md` | completado |
| Docs API | `docs/api/migrate-postgresql-source.md` | completado |
| mkdocs.yml | 2 entradas nav añadidas (functional + api) | completado |
| CHANGELOG.md | sección [Unreleased] PostgreSQL source añadida | completado |
| _compat/__init__.py | 9 exports PG añadidos | completado |
| extractors/__init__.py | PostgreSQLSchemaExtractor añadido | completado |
| transformers/__init__.py | 3 transformers PG añadidos | completado |
| planner.py | _SUPPORTED_SOURCE + _plan_from_postgresql() | completado |
| migrate/__init__.py | 4 exports + docstring actualizado | completado |

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Ninguno. ruff clean, mypy 0 issues, 994/994 tests passed.
- Matriz migrate completada: 4×3 (16 flujos: Oracle×3 + MariaDB×3 + SQL Server×3 + PostgreSQL×3 + origen=destino bloqueado).
