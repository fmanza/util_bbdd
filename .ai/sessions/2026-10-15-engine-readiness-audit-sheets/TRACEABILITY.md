# TRACEABILITY

## Session metadata
- id: 2026-10-15-engine-readiness-audit-sheets
- fecha: 2026-10-15
- rama: develop
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
Queremos incluir esta información (EngineReadinessAdvisor) en bulk y dump, como pestaña nueva de los Excel de
auditoría. PLAN y AUDIT-PLAN; después «IMPLEMENTE con tus recomendaciones».

## Context supplied
- `CLAUDE.md` + `.github/SHARED_INSTRUCTIONS.md`, `.github/prompts/new_feature.prompt.md`
- Sesión previa `.ai/sessions/2026-10-15-engine-conditions-doc/` (sección «Condiciones del motor» en doc)
- Decisiones del usuario: dump con origen y destino; pestaña siempre; mostrar la verificación de la carga; lógica
  duplicada con `doc` como deuda

## AI output summary
- PLAN + AUDIT_PLAN: GO_CONDICIONAL (report_once sin regresiones, nunca interrumpir carga/volcado/exportación, `audit`
  sin importar `connection`, arista `dump → connection` dibujada)
- IMPLEMENT: `report_once()` guarda `EngineReadinessReport` por engine; `engine_report()` (espera con `Event`) y
  `describe_engine()`; `report()` devuelve los hallazgos; `audit/readiness.py` (escritor + contrato estructural);
  hoja `Condiciones_motor` en `auditoria.xlsx` (bulk) y «Condiciones del motor» en `dump_report_*.xlsx`
- Diagrama de capas: arista `dump → connection`; la primera ruta tapaba «NIVEL 2 · SERVICIOS» (revisado renderizando
  el SVG a PNG con cairosvg) y se rehízo entrando por el lado derecho de `connection/`
- AUDIT_CODE: nota de la hoja corregida (no siempre es la verificación de la carga) y bucle de espera con plazo en un test
- Puerta: ruff, mypy, pytest 5816 pasan / 531 saltos sin URLs del banco, `gen_arquitectura_capas`, `zensical build
  --strict`; los 15 tests de `report_once()` sin modificar

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| IMPLEMENT | `src/util_bbdd/{connection,audit,bulk,dump}/…`, `scripts/gen_arquitectura_capas.py` | completado |
| Tests | `tests/unit/{connection/test_engine_report,audit/test_readiness_sheet,bulk/test_audit_readiness_sheet,dump/test_dump_readiness_sheet}.py` | completado |
| Docs | `docs/api/dump_reporter.md`, `docs/api/bulk_audit.md`, `docs/examples/dump_data_export.md`, `docs/architecture.md` (+ SVG), `CHANGELOG.md` | completado |
| Logs | `build/logs/readiness_sheets_pytest.txt` | no versionado |

## Directrices para Futuras IAs
- **[connection/advisor]**: `report_once()` guarda el informe por engine (`_reports`, `WeakKeyDictionary`) y señala el fin
  con un `Event` (`_report_done`); `engine_report()` es el punto canónico para leerlo sin reconectar. Los tests de
  `report_once()` parchean `report()` y esperan que se llame con/sin `connection`: no cambiar ese flujo.
- **[audit/capas]**: `audit` (capa 3) no puede importar `connection` (4); las hojas de condiciones usan el contrato
  estructural `ReadinessReportView` de `audit/readiness.py`.
- **[excel]**: `ReadinessSheetWriter` vale para `SafeWorkbook` y para `pd.ExcelWriter(engine="openpyxl").book`; en este
  último hay que neutralizar fórmulas a mano (lo hace el escritor).
- **[diagrama]**: tras tocar `render_svg()` de `gen_arquitectura_capas.py`, renderizar el SVG a PNG
  (`cairosvg.svg2png`) y mirarlo: una flecha que cruza una etiqueta no falla ningún test. El script reescribe también
  CSS y tabla solo con cambios de fin de línea: restaurarlos con `git checkout` si su contenido no cambia.
- **[duplicación]**: la lógica de filas/resumen/avisos existe en `doc/application/use_cases/engine_conditions.py` y en
  `audit/readiness.py`; unificar en un `/refactor` (doc → audit es una arista permitida pero no dibujada).

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Commit (rutas de la sesión) y `/version-closure` (2.2.0)
- `/refactor`: `doc` reutiliza `audit/readiness.py`
- §2b de `.github/prompts/engine_readiness_integration.prompt.md` (sin versionar) no menciona las hojas de bulk/dump
