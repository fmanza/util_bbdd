# TRACEABILITY

## Session metadata
- id: 2026-09-25-refactor-remove-audit-transaction
- fecha: 2026-09-25
- rama: develop (base `6943fb4`)
- skill: refactor (cambio de API justificado por decisión del usuario)
- origen: roadmap `.ai/sessions/2026-09-25-audit-code-audit-manager/` (L-2 → H11)

## Prompt issued
```
L-2, retirarlo.
```

## AI output summary
- **Retirados**: `AuditTransaction`, `AuditManager.iniciar_transaccion()`, `AuditManager.obtener_historial_transacciones()`, `_historial_transacciones`, y el export en `util_bbdd.bulk` y en `bulk.audit.__all__`.
- **Tests**: se retiran `TestAuditTransaction` (8) y `test_obtener_historial_sin_csv_path_no_lanza`.
- **Docs**: `docs/api/bulk-audit.md` y `docs/functional/bulk-audit.md` reescritas con la API real. Describían métodos inexistentes (`transaction`, `obtener_resumen`, `exportar_excel(ruta)`, `filtrar_por_fecha`), un CSV separado por comas con columna `exito` y reglas de `AuditTransaction` que no se cumplían. Se retira la sección de autodoc de `docs/api/bulk.md`. El prompt de AuditManager queda actualizado.
- **CHANGELOG**: *Removed*, con la alternativa (`bulk_session` + consultas del CSV).

## Validación
- `ruff check` y `ruff format --check` limpios; `mypy` limpio (342 ficheros).
- `tests/unit`: 4368 passed (4377 − 9 retirados).
- `mkdocs build --strict` sin avisos.
- grep en todo el repo (salvo `build/`, `site/`, `.ai/`, `doc_old/`, CHANGELOG): sin referencias.

## AUDIT_CODE
- **Cambio incompatible** para quien importe `AuditTransaction` o llame a los dos métodos: `ImportError` / `AttributeError`. Versión 0.x; anotado en *Removed*.
- Ningún componente interno dependía de ello; la auditoría de `BulkCrud` no cambia.

## Rollback
`git revert <commit>`.

## Directrices para Futuras IAs
- **[auditoría]**: no reintroducir un "historial de transacciones" en memoria. La unidad transaccional es `BulkCrud.bulk_session()` y la traza persistente es el CSV.
