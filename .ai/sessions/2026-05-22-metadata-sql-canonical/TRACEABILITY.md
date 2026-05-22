# TRACEABILITY

## Session metadata
- id: 2026-05-22-metadata-sql-canonical
- fecha: 2026-05-22
- rama: develop
- skill: refactor
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION (× 2 iteraciones)

## Prompt issued

```
Maximizar la reutilización de código, eliminar la duplicación de funcionalidades
y homogeneizar la estructura para facilitar el mantenimiento a largo plazo.
[→ análisis confirmó duplicación entre migrate/sql/ y metadata/]
migrate/sql/*.py actúa como capa de compatibilidad, analizar si es conveniente
eliminarla, la premisa es no tener capas innecesarias.
```

## Context supplied
- `src/util_bbdd/migrate/sql/*.py` — 3 archivos con funciones `fetch_*_sql()` propias
- `src/util_bbdd/migrate/extractors/*.py` — 4 extractores (oracle ya canónico)
- `src/util_bbdd/metadata/*/tables.py` — tablas de metadatos por motor
- Sesión previa: `2026-05-21-migrate-sql-refactor` (creó `migrate/sql/`)
- Historial comprimido (context window) — continuación con summary

## AI output summary

### Iteración 1 — Centralizar SQL en metadata/*/tables.py

**Verificaciones previas (R8, R9):**
- R8: `migrate/sql/__init__.py` sin `__all__` — confirmado.
- R9: Solo extractores importan de `migrate/sql/` — confirmado.

**Hallazgo crítico (AUDIT_PLAN):** La premisa inicial era incorrecta.
- `metadata/mariadb/tables.py` y `metadata/sqlserver/tables.py` NO tenían funciones
  `fetch_*_sql()` de extracción.
- `metadata/postgresql/tables.py` tenía 3 funciones con el mismo nombre que las de
  migrate pero con SQL INCOMPATIBLE (diferente número de columnas y fuentes de datos).
- Oracle era el único con el patrón correcto (referencia canónica).
- Decisión: Opción P-A (aliases `_for_extract_sql`) para las 3 funciones conflictivas
  de PostgreSQL. Usuario aprobó.

**Fase 1 — Añadir SQL a metadata/:**
- `metadata/mariadb/tables.py`: 7 funciones `fetch_*_sql()` añadidas al final.
- `metadata/sqlserver/tables.py`: 7 funciones `fetch_*_sql()` añadidas (con COLUMNPROPERTY
  para IDENTITY + sys.indexes para índices no-PK).
- `metadata/postgresql/tables.py`: 4 funciones sin conflicto + 3 aliases P-A
  (`fetch_tables_for_extract_sql`, `fetch_columns_for_extract_sql`,
  `fetch_indexes_for_extract_sql`) añadidas antes de `build_schema_qualified_table_name`.
- SQL copiado VERBATIM desde migrate/sql/ para preservar compatibilidad con mocks
  de tests basados en pattern-matching.

**Fase 2 — Convertir migrate/sql/*.py en re-exportadores:**
- `migrate/sql/mariadb.py`, `migrate/sql/sqlserver.py`, `migrate/sql/postgresql.py`
  reemplazados por re-exportadores que delegan a `metadata/*/tables.py`.
- Incidente: primera sustitución dejó cuerpos de función huérfanos (el oldString solo
  cubría el docstring + def, no el cuerpo). Corregido con segunda pasada.

**Fase 3 — Redirigir imports en extractores:**
- `migrate/extractors/mariadb.py`: import redirigido a `metadata/mariadb/tables`.
- `migrate/extractors/sqlserver.py`: import redirigido a `metadata/sqlserver/tables`.
- `migrate/extractors/postgresql.py`: import con aliases P-A a `metadata/postgresql/tables`.

**Commit:** `7d58c15` — `refactor(metadata): centralizar SQL de inspeccion en metadata/*/tables.py`
(10 files, +557 / -458 líneas)

### Iteración 2 — Eliminar migrate/sql/ (capa de compatibilidad sin consumidores)

**Análisis post-Fase 3:**
- 0 imports de `migrate.sql.*` en `src/`, `tests/` ni docs.
- `migrate/__init__.py` no expone `sql` subpackage.
- `migrate/sql/__init__.py` tenía docstring desactualizado ("Los extractores importan
  desde aquí" — ya incorrecto).
- Decisión: eliminar directamente, sin período de deprecación (no API pública
  documentada, librería no publicada en PyPI con esta versión).

**Eliminación:** 4 archivos borrados por el usuario/herramienta entre sesiones.

**Actualización CHANGELOG.md:** Entrada `### Changed` corregida — capa de compatibilidad
descrita como eliminada (no mantenida).

**Commit:** `057d639` — `refactor(migrate): eliminar migrate/sql/ (capa de compatibilidad sin consumidores)`
(5 files, +7 / -103 líneas, 4 deletes)

### Validación final

| Check | Resultado |
|---|---|
| `ruff check migrate/ metadata/` | ✅ All checks passed |
| `mypy src/util_bbdd/migrate/` | ✅ No issues (50 archivos) |
| `pytest --tb=short -q` | ✅ 3202 passed, 1 skipped |

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| 7 funciones fetch_*_sql() | `src/util_bbdd/metadata/mariadb/tables.py` | añadido |
| 7 funciones fetch_*_sql() | `src/util_bbdd/metadata/sqlserver/tables.py` | añadido |
| 4 funciones + 3 aliases P-A | `src/util_bbdd/metadata/postgresql/tables.py` | añadido |
| migrate/sql/mariadb.py | eliminado (era re-exportador) | — |
| migrate/sql/sqlserver.py | eliminado (era re-exportador) | — |
| migrate/sql/postgresql.py | eliminado (era re-exportador) | — |
| migrate/sql/__init__.py | eliminado | — |
| Import redirigido | `src/util_bbdd/migrate/extractors/mariadb.py` | modificado |
| Import redirigido | `src/util_bbdd/migrate/extractors/sqlserver.py` | modificado |
| Import con alias P-A | `src/util_bbdd/migrate/extractors/postgresql.py` | modificado |
| CHANGELOG.md | `CHANGELOG.md` | modificado (entrada ### Changed) |

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Ninguno. `metadata/*/tables.py` es el único punto canónico para SQL de introspección.
  3202 tests pasan. ruff + mypy limpios.
- Lección documentada: al sustituir archivos completos con `replace_string_in_file`,
  el `oldString` debe incluir todo el contenido o usar estrategia de reescritura total.
