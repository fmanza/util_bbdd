# TRACEABILITY

## Session metadata
- id: 2026-05-26-comparar-audit-fix
- fecha: 2026-05-26
- rama: develop
- skill: audit_code → implement
- fase: AUDIT_CODE → IMPLEMENT → VALIDATE

## Prompt issued

```
[AUDIT_CODE sobre src/util_bbdd/comparar/]
IMPLEMENT todos los hallazgos confirmados
```

Seguido de corrección tipo Pylance `reportArgumentType` en `_fk_key`.

## Context supplied
- `src/util_bbdd/comparar/comparator.py`
- `src/util_bbdd/comparar/_routine_fetchers.py`
- `tests/comparar/test_comparator.py`
- `.github/instructions/python.instructions.md`

## AI output summary

### Veredicto auditoría: APROBADO CON CONDICIONES (4 bugs, 1 sec, 1 doc, 2 tech-debt)

| Hallazgo | Severidad | Descripción | Archivo |
|---|---|---|---|
| B1 | Bug | FKs anónimas (`name=None`) silenciadas silenciosamente — droppeadas del dict comprehension | `comparator.py` |
| B2 | Bug | SQL Server: solo `sys.procedures`, omite funciones `FN`/`IF`/`TF` | `_routine_fetchers.py` |
| B3a | Bug | PostgreSQL: `{r["name"]: r for r in routines}` sobreescribía funciones overloaded | `comparator.py` |
| B3b | Bug | PostgreSQL: `::regprocedure` cast fallaba con `ERROR: more than one function named X` | `_routine_fetchers.py` |
| S1 | Seguridad | Password con `@` escapaba la regex `://[^@]+@`, exponiendo credenciales en logs | `comparator.py` |
| E1 | Doc | `include_comments` sin nota de dependencia de `include_tables` | `comparator.py` |
| C1 | Tech-debt | `total_differences` semántica — no implementado (decisión de diseño) | — |
| C2 | Tech-debt | `render_all` partial failure — documentado, no corregido | — |

### Fixes implementados

**B1 — FKs anónimas** (`comparator.py`):
- Nuevo helper `_fk_key(fk: Mapping[str, Any]) -> str`: genera clave sintética
  `__anon__{cols}__{referred_table}__{referred_cols}` cuando `name=None`.
- `_compare_foreign_keys` usa `_fk_key()` en ambos dict comprehensions; ya no filtra con `if fk.get("name")`.

**B2 — SQL Server functions** (`_routine_fetchers.py`):
- Añadida segunda consulta `sys.objects WHERE type IN ('FN','IF','TF')` + `sys.sql_modules`
  dentro del mismo bloque `try/with`; routines tipo `"FUNCTION"` se añaden a la lista.

**B3 — PostgreSQL overloads** (`_routine_fetchers.py`):
- Query principal añade `p.oid` y `pg_catalog.pg_get_function_arguments(p.oid) AS proargs`.
- Two-pass: `name_counts` determina si un nombre es único; `unique_name = f"{name}({args})"`
  solo cuando hay overloads.
- DDL via `SELECT pg_get_functiondef(:oid)` con OID directo (evita cast `::regprocedure`).

**S1 — Credential redaction** (`comparator.py`):
- Primer intento (`URL.set(username=None,password=None)`) fallaba: `str(URL)` retenía username.
- Fix definitivo: `make_url(url_str).render_as_string(hide_password=True)` produce
  `scheme://user:***@host/db`; regex `://[^@]+@` opera sobre `user:***@` (sin password real),
  resultando en `scheme://***@host/db` independientemente del contenido del password original.
- Fallback regex directo si `make_url` lanza excepción.

**E1 — Docstring** (`comparator.py`):
- Añadida nota `**Nota**: Solo efectivo cuando ``include_tables=True``.` al parámetro
  `include_comments` en `compare()`.

**Pylance fix** (`comparator.py`):
- `_fk_key` signature cambiada de `dict[str, Any]` a `Mapping[str, Any]`
  (importado de `collections.abc`), compatible con `ReflectedForeignKeyConstraint` TypedDict SA 2.x.

### Tests actualizados / añadidos (`tests/comparar/test_comparator.py`)

| Test | Acción | Propósito |
|---|---|---|
| `TestGetRoutinesPostgreSQL.test_returns_functions` | Mock actualizado | `oid`, `proargs` añadidos al row mock |
| `TestGetRoutinesPostgreSQL.test_returns_procedures` | Mock actualizado | `oid`, `proargs` añadidos al row mock |
| `TestGetRoutinesMSSQL.test_returns_procedures` | Actualizado | `execute_side_effect` maneja consulta `sys.objects` (retorna vacío) |
| `TestGetRoutinesMSSQL.test_returns_functions` | Nuevo (B2) | `sys.procedures` vacío; `sys.objects` retorna función escalar; `sys.sql_modules` retorna DDL |
| `test_label_hides_credentials_with_encoded_special_chars` | Nuevo (S1/T5) | URL con `p%40ss%21` → ni username ni password en label; `***` presente |
| `test_anonymous_fk_detected` | Nuevo (B1/T1) | FK `name=None` en target → `has_differences=True`, `status="added"` |
| `test_include_comments_requires_include_tables` | Nuevo (E1/T6) | `include_tables=False, include_comments=True` → sin diferencias de comentario |
| `test_anonymous_fk_is_skipped` → `test_anonymous_fk_is_detected` | Renombrado + assertions invertidas | Antes documentaba bug (ignorar anónimas); ahora valida `has_differences=True`, `status="removed"` |

### Resultado final
- `tests/comparar/test_comparator.py`: **140/140 passed** (137 anteriores + 3 nuevos)
- `src/util_bbdd/comparar/comparator.py`: 0 errores Pylance
- Archivos modificados: 3 (`_routine_fetchers.py`, `comparator.py`, `test_comparator.py`)

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| IMPLEMENT B1 | `src/util_bbdd/comparar/comparator.py` | completado |
| IMPLEMENT B2 | `src/util_bbdd/comparar/_routine_fetchers.py` | completado |
| IMPLEMENT B3a+b | `src/util_bbdd/comparar/_routine_fetchers.py` | completado |
| IMPLEMENT S1 | `src/util_bbdd/comparar/comparator.py` | completado |
| IMPLEMENT E1 | `src/util_bbdd/comparar/comparator.py` | completado |
| Tests nuevos T1/T5/T6 | `tests/comparar/test_comparator.py` | completado |
| Pylance fix | `src/util_bbdd/comparar/comparator.py` | completado |

## Directrices para Futuras IAs

- **[comparar/S1]**: `_build_label` usa `make_url(url_str).render_as_string(hide_password=True)` + regex.
  NO usar `URL.set(username=None,password=None)` — `str(URL)` retiene el username igualmente.

- **[comparar/B1]**: FKs anónimas (`name=None`) son válidas en SA 2.x (TypedDict `ReflectedForeignKeyConstraint`).
  El helper `_fk_key()` genera clave sintética; no filtrar por existencia de nombre.

- **[comparar/B3]**: PostgreSQL DDL de rutinas: usar `pg_get_functiondef(:oid)` con OID directo.
  Nunca usar cast `::regprocedure` — falla con overloads (`ERROR: more than one function named X`).

- **[comparar/B2]**: SQL Server: `sys.procedures` solo cubre `P` (stored procedures).
  Para incluir funciones usar `sys.objects WHERE type IN ('P','FN','IF','TF')`.
  (Este mismo fix ya se aplicó en `migrate/` en sesión `2026-05-22m`.)

- **[comparar/typing]**: `get_foreign_keys()` retorna `list[ReflectedForeignKeyConstraint]`.
  Usar `Mapping[str, Any]` (no `dict[str, Any]`) en helpers que aceptan estos objetos.

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- C1: `total_differences` semantics — tech-debt, pospuesto (requiere decisión de diseño)
- C2: `render_all` partial failure — comportamiento documentado, no corregido
