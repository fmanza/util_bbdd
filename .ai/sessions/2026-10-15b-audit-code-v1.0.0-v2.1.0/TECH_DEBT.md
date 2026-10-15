# TECH_DEBT — inventario tras el audit-code v1.0.0 → HEAD

- Fecha: 2026-10-15 · Rama: `develop` · Base: `0c0e6a65` (v2.1.0 + `[Unreleased]`)
- Supuestos (sin inputs explícitos): módulo = cambios v1.0.0..HEAD; síntomas = `AUDIT_REPORT.md`; scope inicial solo
  análisis, después **IMPLEMENT autorizado** («IMPLEMENT») para la Fase 1; no se rompen contratos públicos.
- Veredicto: **DEUDA_MENOR**

## Bugs fuera de este inventario (van por `/hotfix`)

A-01 (evento `run` `ok` con constraints sin reactivar), A-04 (recomendaciones que fallan), A-02 (asyncpg y literales),
D-01 (CHANGELOG 2.0.0).

## Inventario

| ID | Prioridad | Estado | Deuda | Resultado |
|---|---|---|---|---|
| T-01 | quick_win | Confirmado | Comentarios de justificación perdidos en `21df2668` (`dump/orchestrator.py`) | ✅ Restaurados (solo comentarios) |
| T-02 | quick_win | Confirmado | Hoja «Errores de Reactivación»: orden y anchos (`dump/reporters.py`) | ✅ Al final (antes de «Condiciones del motor»), anchos 30/80, ajuste de texto; 3 tests |
| T-03 | quick_win | Confirmado | Umbrales incoherentes con su texto (`write_timeout`, `cost threshold`) | Pendiente de A-05 |
| T-04 | quick_win | Hipótesis | `reactivation_error = str(exc)` frente a la política «solo el tipo» | Pendiente de A-07 |
| T-05 | quick_win | Confirmado | `batch_window_seconds` sin validar; nombres reservados de Windows | ✅ Validación + 7 casos de test; la parte de Windows era un falso positivo (A-11) |
| T-06 | deuda_estructural | Confirmado | `_check_*` duplicados y MySQL dentro del advisor → Strategy con registro por motor | Pendiente (`/refactor`) |
| T-07 | fase_media | Confirmado | Casting sin validar en PostgreSQL; MySQL corta los dinámicos ante un valor inválido | Pendiente (con T-06) |
| T-08 | fase_media | Confirmado | `except Exception` + DEBUG en el advisor oculta errores de programación | Pendiente (con T-06) |
| T-09 | fase_media | Confirmado | `DumpConfig` con rutas tipadas `StrPath` tras normalizar a `Path` | Pendiente |
| T-10 | fase_media | Confirmado | `db_type` `sqlserver`/`mssql` según el camino; sin `get_engine_readiness` async | Pendiente |
| T-11 | fase_media | Hipótesis | Dos escritores de la hoja de condiciones (audit y doc) | Pendiente |
| T-12 | quick_win | Confirmado | Sin página de API del advisor; enlaces y referencia rotos; guía de prompts en la navegación de usuario | ✅ `docs/api/engine_readiness_advisor.md`, enlaces, nav |
| T-13 | quick_win | Confirmado | `.ai/CURRENT_STATE.md` en v1.1.1 e `INDEX.md` sin 13 sesiones | ✅ Actualizados |

## Orden de las fases restantes

1. `/hotfix`: A-01, A-04, A-02, D-01.
2. Decisiones A-05 y A-07 → T-03, T-04.
3. `fase_media`: T-09, T-10.
4. `deuda_estructural` con PLAN + AUDIT_PLAN propios: T-06 (absorbe T-07 y T-08), después T-11. Validar con SQL Server
   en el banco (hoy bloqueado por el puerto 51433).
