# TRACEABILITY

## Session metadata
- id: 2026-05-22l-migrate-routines-package-body
- fecha: 2026-05-22
- rama: develop
- skill: feature / hotfix
- fase: IMPLEMENT → AUDIT_CODE

## Prompt issued
> "@Workflow Director, Replantemos la salida de información de PROCEDURE/FUNCTION, esta debe salir
> siempre para su revisión, informando de donde sale"
> (seguimiento de las sesiones j y k)

## Context supplied
- Sesión `2026-05-22k-hotfix-sqlserver-tests` — contexto de la directriz: "si se decide extraer el
  PACKAGE BODY, añadir rama en oracle.py para `raw_type == 'PACKAGE BODY'` que llame
  `_fetch_routine_body()`".
- `src/util_bbdd/migrate/extractors/oracle.py`
- `src/util_bbdd/migrate/reporters/markdown.py`
- `src/util_bbdd/migrate/reporters/text.py`
- `src/util_bbdd/migrate/ir/models.py` — `CanonicalRoutine`, `MigrationPlan`
- `tests/unit/migrate/test_reporters.py`
- `tests/unit/migrate/test_routines_oracle_extractor.py`

## AI output summary

### Problema raíz
1. **Oracle PACKAGE BODY** — el extractor nunca llamaba a `_fetch_routine_body()` para `raw_type ==
   "PACKAGE BODY"`, dejando siempre `body=""`. La nota de la sesión k lo identificó como punto de
   mejora futuro; se implementa ahora.
2. **Reporters: return temprano** — `_routine_block()` hacía return inmediato al detectar
   `is_package_member=True`, impidiendo la visualización del body aunque este existiera.
3. **Sin información de proveniencia** — los reporters no indicaban de qué motor/schema/tipo provenía
   cada rutina.

### Cambios implementados

**`src/util_bbdd/migrate/extractors/oracle.py`**
- Rama `elif raw_type in ("PACKAGE", "PACKAGE BODY")`:
  - `PACKAGE BODY` → llama `_fetch_routine_body(schema, routine_name, "PACKAGE BODY")` para obtener
    el fuente completo desde `ALL_SOURCE`.
  - `PACKAGE` (spec) → mantiene `body=""` (sin implementación por diseño).

**`src/util_bbdd/migrate/reporters/markdown.py`**
- `format_plan_markdown` → pasa `plan.source_engine` a `_routines_section()`.
- `_routines_section(routines, source_engine: str)` → nuevo parámetro propagado.
- `_routine_block(routine, source_engine: str)`:
  - Determina `src_type`: `"PACKAGE BODY"` si `is_package_member` con body, `"PACKAGE"` si sin body,
    o `routine.routine_type` en caso normal.
  - Añade línea `> **Fuente**: ENGINE · schema · tipo` siempre.
  - Para `is_package_member`: muestra nota de PACKAGE pero **ya no hace return temprano**.
  - Si hay body: muestra bloque ` ```sql `. Si no: `> **Código no disponible**`.

**`src/util_bbdd/migrate/reporters/text.py`**
- Misma estructura: `source_engine` propagado, línea `Fuente: ENGINE · schema · tipo` añadida,
  return temprano eliminado.

**`tests/unit/migrate/test_routines_oracle_extractor.py`**
- Eliminado `test_package_becomes_package_member` + `test_package_body_becomes_package_member`.
- Añadidos:
  - `test_package_body_fetches_and_stores_body` — mock con 2 `side_effect` (routine rows + body rows);
    verifica `body != ""` y `"PKG_UTIL" in r.body`.
  - `test_package_spec_has_no_body` — PACKAGE spec: 1 `side_effect`, verifica `body == ""`.

**`tests/unit/migrate/test_reporters.py`**
- Corregido `test_routine_package_member_shows_package_note` (markdown): usa `body=""` para que la
  aserción `"```sql" not in result` siga siendo válida.
- Añadidos 4 tests nuevos:
  - `test_package_body_member_with_body_shows_code_block` (markdown)
  - `test_routine_shows_source_info_markdown`
  - `test_package_body_member_with_body_shown` (text)
  - `test_routine_shows_source_info_text`

### Validación
- `pytest tests/unit/migrate/`: **1293/1293 PASAN** ✅
- `ruff check`: Sin errores ✅
- `mypy src` (321 archivos): Sin errores ✅

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Extractor Oracle | `src/util_bbdd/migrate/extractors/oracle.py` | Modificado |
| Reporter Markdown | `src/util_bbdd/migrate/reporters/markdown.py` | Modificado |
| Reporter Text | `src/util_bbdd/migrate/reporters/text.py` | Modificado |
| Tests extractor Oracle | `tests/unit/migrate/test_routines_oracle_extractor.py` | Modificado |
| Tests reporters | `tests/unit/migrate/test_reporters.py` | Modificado |

## Contratos verificados

- **SRP**: Cada reporter es responsable solo de su formato de salida; la lógica de `src_type` es
  local a `_routine_block()`.
- **OCP**: El extractor Oracle extiende el comportamiento para PACKAGE BODY sin modificar la lógica
  de PROCEDURE/FUNCTION.
- **Backward compat**: `PACKAGE` spec sigue teniendo `body=""` — comportamiento visible sin cambio.

## Directrices para futuras IAs

- [oracle/package-body] `ALL_SOURCE WHERE type='PACKAGE BODY' AND name=:pkg_name` devuelve el fuente
  completo del package body. `ALL_PROCEDURES` devuelve una sola fila por package (no por miembro).
- [reporters/routines] Los reporters reciben `source_engine` en `_routines_section()` y lo propagan
  a `_routine_block()`. No modificar la firma sin actualizar ambas funciones y sus tests.
- [oracle/package-spec] `raw_type == "PACKAGE"` (interfaz) conserva `body=""` por diseño — el spec
  no contiene implementación. Solo `raw_type == "PACKAGE BODY"` tiene código ejecutable.
- [test-pattern/oracle-extractor] Mock pattern para PACKAGE BODY: `manager.execute_custom_many
  .side_effect = [iter(routine_rows), iter(body_rows)]` — dos llamadas por rutina PACKAGE BODY.
  Para PACKAGE spec: solo `[iter(routine_rows)]` — una llamada.
