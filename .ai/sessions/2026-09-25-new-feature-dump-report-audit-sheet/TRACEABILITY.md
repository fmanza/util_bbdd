# TRACEABILITY

## Session metadata
- id: 2026-09-25-new-feature-dump-report-audit-sheet
- fecha: 2026-09-25
- rama: develop (base `161aae2`)
- skill: new-feature (PLAN + AUDIT_PLAN aprobados; IMPLEMENT + AUDIT_CODE + VERSION)
- origen: fuera del alcance de `2026-09-25-new-feature-dump-audit-counters`: el Excel de `dump` no mostraba el resumen de auditoría

## Prompt issued
```
El informe Excel de dump sigue sin mostrar el resumen de auditoría; quedaba fuera del alcance. Hazlo. PLAN y AUDIT_PLAN
Adelante
```

## Decisiones (AUDIT_PLAN, opciones recomendadas aprobadas con "Adelante")
- **1a**: sin `audit_summary`, no se crea la hoja (como «Índices»).
- **2a**: se neutralizan las fórmulas en **todo el libro**. Cubre la hoja nueva y un hallazgo previo: nombres del catálogo y mensajes de error que empiecen por `=` se guardaban como fórmula.
- **3a**: el helper `_desactivar_formulas` se copia en `dump/reporters.py`, citando H12, para no importar código privado de `bulk`.

## AI output summary
- `dump/orchestrator.py`: `audit_summary` se calcula **antes** del Excel (Fase 5b), se pasa a `generate()` y se reutiliza en `DumpResult`. El CSV se lee una sola vez.
- `dump/reporters.py`:
  - `generate(..., audit_summary=None)`;
  - hoja nueva «Auditoría Bulk», siempre la última: métrica/valor más una nota. Resaltado en rojo para `audit_failures` y `audit_uncommitted_records` > 0, en naranja para `unaudited_committed_rows` > 0, y en amarillo para las filas del CSV ≠ filas del volcado;
  - `_desactivar_formulas(wb)` antes de guardar;
  - docstring del módulo actualizado (ya no son "tres hojas").
- Docs: `docs/api/dump-reporter.md` (diagrama, parámetro, hoja 5, fórmulas), `docs/guides/dump_guide.md`, `docs/examples/dump_data_export.md`. `CHANGELOG.md`: *Added* (hoja) y *Fixed* (fórmulas). Además se quitaron líneas en blanco entre entradas de *Added* que habían dejado las sesiones de hoy.

## Validación
- **Tests**:
  - `test_reporters.py` +7: valores y posición final, sin hoja con `None`, orden tras «Índices», resaltado de incidencias, resaltado de discrepancia, `tabla_mas_activa` con `=HYPERLINK` guardada como texto, sin fórmulas en ninguna hoja.
  - `test_orchestrator.py`: `generate` recibe el mismo objeto que `DumpResult.audit_summary`.
  - `test_parallel_loader_audit.py` +2 E2E: el `.xlsx` real lleva la hoja con 3 filas; sin auditoría no hay hoja.
- **Mutaciones**: 10, todas muertas. La del orden de las hojas sobrevivía hasta añadir `test_sheet_goes_after_the_indexes_sheet`.
- **Calidad**:
  - `ruff check` y `ruff format --check` limpios;
  - `mypy src tests/unit/test_protocol_conformance.py` limpio;
  - `pytest tests/unit`: **4417 passed**;
  - `mkdocs build --strict`: exit 0.

## AUDIT_CODE
- **Compatibilidad**: `generate()` gana un keyword con valor por defecto al final. Las hojas existentes mantienen su posición, porque la nueva va al final.
- **Momento del cálculo**: las cargas y sus sesiones de auditoría ya han terminado antes de la Fase 5b, y la sincronización de PK no audita. El resumen es el mismo que antes, solo que calculado antes.
- **Seguridad**: se cierra la inyección de fórmulas en el Excel de `dump` (hallazgo previo, en *Fixed*).
- **Fuera del alcance**: `pk_sync_results` sigue sin aparecer en el Excel.

## Rollback
`git revert <commit>`.

## Directrices para Futuras IAs
- **[dump / informe]**: toda hoja nueva del Excel va **al final**, para no mover las existentes. `_desactivar_formulas(wb)` debe seguir justo antes de `wb.save()`.
- **[dump / informe]**: el resumen de auditoría se calcula una sola vez en `run()`, antes del Excel. No volver a llamar a `_summarize_audit` al construir `DumpResult`.

## Veredicto final
CLOSED
