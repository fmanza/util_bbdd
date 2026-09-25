# TRACEABILITY

## Session metadata
- id: 2026-09-26f-hotfix-dump-sqlite-source
- fecha: 2026-09-26
- rama: develop (base `509afd2`)
- skill: hotfix (PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION)
- origen: PD-07 (BAJA) de `2026-09-25-performance-audit-dump`; roadmap `2026-09-25b-performance-audit-dump-delta`, paso 0.9

## Prompt issued
```
/hotfix PD-07: SQLite solo está soportado como destino de dump, pero DumpOrchestrator acepta un origen SQLite: las
columnas TIMESTAMP llegan como texto y el destino SQLite las rechaza. Supuesto: rechazar o avisar (a verificar: los tests
E2E SQLite → SQLite existentes). Criterios: error claro o aviso; test.
```

## RCA
- **La premisa del hallazgo no se sostiene**: «SQLite solo como destino» sale de la matriz de motores de `.ai/CURRENT_STATE.md`, que es la de `migrate` (DDL), no la de `dump`. En ella MySQL tampoco figura como fuente, y `dump` funciona con origen MySQL (banco diario). Ningún documento de `dump` restringe SQLite como origen.
- **Comportamiento medido hoy** (tras PD-05, que lee con `dtype=object`):
  - SQLite → SQLite con TIMESTAMP/DATE: la tabla termina en `error` con `SQLite DateTime type only accepts Python datetime and date objects as input`.
  - SQLite → PostgreSQL con las mismas columnas: `success`, fechas y decimales correctos (el servidor convierte el texto).
  - SQLite → SQLite con INTEGER/TEXT (tests E2E existentes): funciona.
- **Causa**: SQLite no tiene tipos de columna; el driver devuelve las fechas como `str` y los DECIMAL como `float`. Un destino servidor convierte el texto; el tipo `DateTime` de SQLAlchemy en un destino SQLite rechaza texto; los DECIMAL pueden perder precisión en cualquier destino.

## FIX (mínimo)
- **Descartado rechazar un origen SQLite**: rompería usos que funcionan (SQLite → servidor, tests E2E).
- `dump/orchestrator.py`: `_warn_sqlite_source(source, target)` (nuevo), llamado desde `__init__`. Con origen SQLite registra un WARNING con la limitación, más concreto si el destino también es SQLite («las tablas con columnas de fecha fallarán»).
- `docs/api/dump.md` («Errores y casos especiales»): filas para origen SQLite y para destino SQLite con paralelismo (PD-06). HTML comprobado: la tabla tiene sus 4 filas.
- `CHANGELOG.md` (`[Unreleased]` → *Fixed*).

## Validación
- **Tests** (`TestSqliteSourceWarning`, 4): mensaje según origen/destino (SQLite→SQLite, SQLite→PostgreSQL, sin aviso para PostgreSQL→SQLite) y el constructor real con engines SQLite lo emite.
- **Calidad**: `ruff format` + `ruff check` limpios; `mypy` limpio; `pytest tests/unit`: **4536 passed**; `mkdocs build --strict` sin errores.

## AUDIT_CODE
- **Sin cambio de comportamiento**: solo un WARNING en el constructor; ninguna carga cambia.
- **Otros orígenes**: sin aviso (test).
- **Pendiente, fuera del alcance**: hacer que SQLite → SQLite funcione con fechas (convertir texto a `datetime` según el tipo del destino) sería una funcionalidad nueva (`/new-feature`), no un hotfix. También podría corregirse la matriz de `CURRENT_STATE` para distinguir `migrate` de `dump`.

## VERSION
- Commit: `fix(dump): avisar de las limitaciones de un origen SQLite (PD-07)`
- Changelog: una entrada en `[Unreleased]` → *Fixed*.
- Rollback: `git revert <commit>`.

## Directrices para Futuras IAs
- **[dump]**: la matriz «Motores soportados» de `.ai/CURRENT_STATE.md` es la de `migrate`; no la uses para decidir qué orígenes admite `dump`.
- **[dump/sqlite]**: con origen SQLite, fechas → `str` y DECIMAL → `float` (SQLite no tiene tipos). No asumas `datetime`/`Decimal` desde ese origen.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Ninguno de la Fase 0 del roadmap. Siguiente: Fase 1 (quick wins de rendimiento Q1–Q4).
