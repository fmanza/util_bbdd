# TRACEABILITY

## Session metadata
- id: 2026-10-02c-audit-module
- fecha: 2026-10-02
- rama: develop
- skill: new_feature (+ `.github/prompts/audit_module.prompt.md`)
- fase: PLAN + AUDIT_PLAN + IMPLEMENT (F0–F5) + AUDIT_CODE + VERSION (propuesta, sin commit)

## Prompt issued
`/new-feature .github\prompts\audit_module.prompt.md`

## Context supplied
- `.github/prompts/audit_module.prompt.md`, `.github/prompts/new_feature.prompt.md`, `.github/agents/plan-architect.agent.md`
- `.ai/audit/audit_module_baseline_inventory.md`
- Código de `bulk/`, `dump/`, `migrate/`, `_core/exceptions.py`, `_core/export_safety.py`; tests con rutas privadas de auditoría
- OpenTelemetry DB semantic conventions; OWASP Logging Cheat Sheet; OWASP CSV Injection

## AI output summary
- Inputs del prompt tomados por defecto y declarados como supuestos (no faltaba ninguno obligatorio).
- Rutas del inventario re-verificadas contra `12d055c`; añadido `INV-X-05` (`_core/export_safety.py`).
- `H-07` verificado y descartado (Excel neutralizado, HTML escapado por `to_html`); riesgo residual en el CSV heredado.
- `H-05` descartado (lock entre procesos: sin multiproceso en `bulk`/`dump`; exigiría código por plataforma o dependencia).
- Detectados 2 destinos de `patch` en `tests/unit/test_audit_subsystem.py` (225, 276) que cambiarían al mover el código.
- PLAN: matriz de 46 `INV-*` (C/Q/A), capa 3, contratos `AuditEvent`/`AuditSink`, fases F0–F5, borrador de ADR-002.
- AUDIT_PLAN: veredicto GO_CONDICIONAL con condiciones C1–C5.
- Sin cambios en `src/` ni `tests/` durante PLAN.
- Usuario: «C3 completo, C4 ok. IMPLEMENT». C1/C2 aplicados como en el PLAN; C5 = F0–F5.
- C4: fixtures CSV de v0.28.0 y microbenchmark generados antes de mover código.
- F0–F5 implementadas con la suite en verde tras cada una (5722 → 5809 passed); integración 5 motores: 408 passed.
- AUDIT_CODE: AC-1 (strict + destino fallido no contaba lo escrito en el CSV) y AC-2 (run_id como estado compartido) corregidos.
- `/audit-code` independiente: APROBADO CON CONDICIONES; hallazgos 1–4 corregidos con tests (5817 passed).
- 3 tests existentes modificados (2 de C2 + firma de `MigrationPlan.execute`); ver `02_IMPLEMENT_AUDIT_CODE_VERSION.md`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| REQUEST | `.ai/sessions/2026-10-02c-audit-module/00_REQUEST.md` | emitido |
| CONTEXT_SNAPSHOT | `.ai/sessions/2026-10-02c-audit-module/00_CONTEXT_SNAPSHOT.md` | emitido |
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-10-02c-audit-module/01_PLAN_AUDIT_PLAN.md` | emitido |
| IMPLEMENT + AUDIT_CODE + VERSION | `.ai/sessions/2026-10-02c-audit-module/02_IMPLEMENT_AUDIT_CODE_VERSION.md` | emitido |
| Paquete | `src/util_bbdd/audit/` | completado |
| Adaptadores | `bulk/_audit/events.py`, `dump/_audit_events.py`, `migrate/_audit_events.py` | completado |
| ADR | `docs/adr/ADR-002-modulo-auditoria.md` | aceptado |
| Docs | `docs/functional/audit.md`, `docs/api/audit.md` | completado |

## Directrices para Futuras IAs
- **[auditoría]**: El punto canónico de neutralización de fórmulas en Excel ya existe: `_core/export_safety.py` (`SafeWorkbook`, `safe_frame`, `neutralize_formulas`); `audit/exporters.py` lo importa directamente (`bulk/_support/excel.py` se eliminó en F1). En CSV la neutralización es otra (apóstrofo delante): `audit/text.py` → `AuditText.safe_csv_cell`.
- **[auditoría]**: El registro de locks por ruta vive en `audit/locks.py` (`path_lock`) y es **único** en el proceso; `bulk._audit.repository._get_file_lock` es el mismo objeto (re-exportado, nunca redefinido; lo fija `tests/unit/audit/test_legacy_csv_moved.py`). Dos registros darían dos locks para el mismo fichero.
- **[auditoría]**: Los tests fijan el logger `util_bbdd.bulk.audit` y el texto «⚠️ Auditoría deshabilitada: audit_csv_path es None» (`tests/unit/test_audit_subsystem.py:413-416`): `AuditManager` debe seguir en `bulk/audit.py`.
- **[auditoría]**: El formato del CSV de auditoría y del de rechazos está congelado: `tests/unit/audit/test_legacy_format.py` los compara byte a byte con `tests/fixtures/audit/*_v0_28_0.csv` (marcados `-text` en `.gitattributes`). Cualquier mejora de formato va a un `AuditSink` nuevo.
- **[auditoría]**: En `bulk`, los eventos de `audit_sink` se emiten en `BulkPersistenceManager._write`/`register_operation`, el mismo punto que el CSV: heredan el diferido de `bulk_session` y `audit_strict`. No emitir eventos `operation` desde otro sitio.
- **[herramientas]**: Fuera de pytest, `import util_bbdd` carga una copia instalada en site-packages; para scripts usar `PYTHONPATH=src`.
- **[herramientas]**: `scripts/gen_arquitectura_capas.py` dibuja la flecha a `audit/` desde `DRAWN` (importadores con destino `audit`): al añadir un consumidor, basta con añadir la arista a `DRAWN`.
- **[arquitectura]**: Un paquete consumido por `bulk`/`migrate` (capa 6) y `dump` (7) debe estar en capa ≤ 5 y no puede importarlos; los tipos de cada módulo se adaptan a eventos en el propio módulo.

## Veredicto final
Veredicto: GO (AUDIT_CODE sin hallazgos abiertos de severidad media o superior)
Pendientes al cierre:
- Commits hechos a petición del usuario: `8467053` (feat(audit), incluye las correcciones del `/audit-code`) y el `docs(ai)` de la sesión. Sin push.
- Opcional: hipótesis 5 del audit-code y tests de `update`/`delete` paralelos con destino.
- `/version-closure` para numerar la versión (sugerencia 0.29.0).
