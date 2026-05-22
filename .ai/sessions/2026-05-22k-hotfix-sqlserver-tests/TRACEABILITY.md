# TRACEABILITY

## Session metadata
- id: 2026-05-22k-hotfix-sqlserver-tests
- fecha: 2026-05-22
- rama: develop
- skill: hotfix
- fase: RCA + FIX + AUDIT_CODE

## Prompt issued
> "@Workflow Director, sigue sin aparecer el código PROCEDURE/FUNCTION para revisión manual"
> (seguimiento de la sesión j — reportado tras el fix de reporters)

## Context supplied
- Sesión `2026-05-22j-migrate-reporters-routines` — fix de reporters (sesión padre)
- Sesión `2026-05-22g-hotfix-sqlserver-routines` — hotfix que refactorizó el extractor SQL Server
- `tests/unit/migrate/test_routines_sqlserver_extractor.py` — 4 tests FALLANDO
- `src/util_bbdd/migrate/extractors/sqlserver.py` — implementación actual del extractor
- `src/util_bbdd/metadata/sqlserver/_adapter_helpers.py` — `build_sqlserver_routines_query()` / `build_sqlserver_routine_body_query()`
- `tests/unit/migrate/test_reporters.py` — 22 tests reporter (estado correcto)

## AI output summary
1. **RCA**: Diagnóstico exhaustivo de todo el pipeline migrate (extractors → transformers → emitters → reporters).
   - Reporters: CORRECTOS (fix sesión j confirmado).
   - Transformer `_transform_routine()`: CORRECTO — deepcopy preserva body, añade WARNING a todas las rutinas.
   - Emitters (MariaDB, PostgreSQL, SQLServer, Oracle): CORRECTOS.
   - Extractor Oracle/MariaDB/PostgreSQL: CORRECTOS.
   - **Extractor SQL Server**: Implementación CORRECTA. **Tests ROTOS** — parche paths obsoletos desde hotfix g.

2. **Root cause identificado**:
   - `test_routines_sqlserver_extractor.py` usaba `patch("...fetch_routines_sync")` y
     `patch("...fetch_routine_body_sync")` — funciones removidas en hotfix `2026-05-22g`.
   - Además importaba `SqlServerRoutineDetail` que el extractor ya no usa.
   - El extractor actual usa `self._query()` → `manager.execute_custom_many()` con raw tuples.

3. **Fix aplicado**: Reescritura completa de `test_routines_sqlserver_extractor.py`:
   - Eliminados: `patch()`, `SqlServerRoutineDetail`, paths de función obsoletos.
   - Nuevo helper `_extractor(routine_rows, body_rows_per_routine)` — mockea `manager.execute_custom_many.side_effect`.
   - Row format routines: `(name, type_str, object_id, params_count)` — 4 columnas.
   - Row format body: `((definition,),)` — 1 columna `sys.sql_modules.definition`.
   - Patrón alineado con `test_routines_mariadb_extractor.py` y `test_routines_oracle_extractor.py`.

4. **Validación**:
   - `test_routines_sqlserver_extractor.py`: 4/4 PASAN ✅
   - Suite completa migrate `tests/unit/migrate/`: 1289/1289 PASAN ✅
   - `ruff check`: Sin errores ✅
   - `mypy src`: Sin errores ✅

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Test reescrito | `tests/unit/migrate/test_routines_sqlserver_extractor.py` | Modificado |

## Contratos verificados

- **OCP**: Extractor SQL Server tests aislados — no rompen tests de otros extractores.
- **SRP**: Tests del extractor SQL Server cubren solo `extract_routines()`, no lógica de emitters.

## Nota sobre el diagnóstico de usuario

La investigación no encontró ningún bug en el pipeline de código (extractors, transformers, emitters,
reporters). Los posibles motivos de "sigue sin aparecer" en uso real son:

1. **Permisos de BD insuficientes**: `ROUTINE_DEFINITION` en MariaDB/PostgreSQL puede ser NULL sin
   privilegio `SELECT` sobre `information_schema.ROUTINES`. En SQL Server, `sys.sql_modules.definition`
   puede ser NULL si el objeto está cifrado (`WITH ENCRYPTION`). En Oracle, `ALL_SOURCE` puede no
   devolver filas si el usuario no tiene `SELECT ANY DICTIONARY` o permisos explícitos.

2. **Oracle PACKAGE members** (comportamiento CORRECTO por diseño): Los miembros de PACKAGE tienen
   `body=""` e `is_package_member=True` — el reporter muestra "[PACKAGE MEMBER] migración manual
   requerida" sin código. Esto es intencional (v1): el PACKAGE BODY como unidad no tiene equivalente
   en otros motores.

3. **Objetos cifrados en SQL Server** (`WITH ENCRYPTION`): `sys.sql_modules.definition` devuelve NULL,
   body="", y el extractor emite un WARNING "no disponible". El reporter muestra "[CÓDIGO NO
   DISPONIBLE]".

## Directrices para futuras IAs

- [hotfix/sqlserver-extractor-tests] Tests del extractor SQL Server deben mockear
  `manager.execute_custom_many.side_effect` con raw tuples — NUNCA parchear funciones
  de módulo como `fetch_routines_sync` (no existen desde hotfix 2026-05-22g).
- [migrate/routines-pipeline] El pipeline extractor→transformer→emitter→reporter está correctamente
  implementado. Si el usuario reporta código vacío en producción, el diagnóstico correcto es
  verificar permisos de BD, no el código de la librería.
- [oracle-packages] La decisión de `body=""` para PACKAGE members es intencional. Si en el futuro
  se decide extraer el PACKAGE BODY fuente completo para información, modificar
  `src/util_bbdd/migrate/extractors/oracle.py` → añadir rama para `raw_type == "PACKAGE BODY"` que
  llame `_fetch_routine_body(schema, name, "PACKAGE BODY")`.
