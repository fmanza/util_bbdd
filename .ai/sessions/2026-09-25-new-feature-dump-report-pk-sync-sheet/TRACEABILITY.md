# TRACEABILITY

## Session metadata
- id: 2026-09-25-new-feature-dump-report-pk-sync-sheet
- fecha: 2026-09-25
- rama: develop (base `0cd5d82`)
- skill: new-feature (IMPLEMENT + AUDIT_CODE + VERSION; mismo patrón que `2026-09-25-new-feature-dump-report-audit-sheet`)
- origen: fuera del alcance de la sesión anterior: `pk_sync_results` no aparecía en el Excel de `dump`

## Prompt issued
```
Hazlo
```

## AI output summary
- `dump/reporters.py`:
  - `generate(..., pk_sync_results=None)`;
  - hoja nueva «Secuencias PK», siempre la última (detrás de «Índices» y «Auditoría Bulk»). Columnas: Tabla, Columna PK, Dialect, MAX(PK) (`—` si es `None`), Estado coloreado y Mensaje. Con una lista vacía muestra un mensaje, como «Índices»;
  - colores nuevos en `_STATUS_BG`: `synced` y `no_rows` en verde. `skipped`, `unsupported` y `error` ya existían;
  - docstring del módulo actualizado.
- `dump/orchestrator.py`: pasa `pk_sync_results` a `generate()`. La Fase 5a ya se ejecutaba antes del informe, así que no cambia el orden.
- Docs: `docs/api/dump-reporter.md` (diagrama, parámetro, hoja 6, orden de las opcionales), `docs/guides/dump_guide.md`, `docs/examples/dump_data_export.md`. `CHANGELOG.md` (*Added*); se corrige también la entrada de «Auditoría Bulk», que decía "la última del Excel".

## Validación
- **Tests**:
  - `test_reporters.py` +5: filas con sus valores, colores por estado, sin hoja con `None`, mensaje con la lista vacía, orden `Índices → Auditoría Bulk → Secuencias PK`.
  - `test_orchestrator.py`: `generate` recibe el mismo objeto que `DumpResult.pk_sync_results`.
  - `test_parallel_loader_audit.py` +1 E2E: el `.xlsx` real lleva la hoja. En SQLite `_sync_pk_sequences` devuelve `None`, así que se sustituye por un resultado fijo.
- **Mutaciones**: 7, todas muertas.
- **Calidad**:
  - `ruff check` y `ruff format --check` limpios;
  - `mypy src tests/unit/test_protocol_conformance.py` limpio;
  - `pytest tests/unit`: **4423 passed**;
  - `mkdocs build --strict`: exit 0.

## AUDIT_CODE
- **Compatibilidad**: keyword nuevo con valor por defecto al final de `generate()`. La hoja va al final, así que las demás no cambian de posición.
- **Seguridad**: los textos (nombre de tabla y columna, mensaje de error) pasan por `_desactivar_formulas`, que recorre todo el libro.
- **Observado, fuera del alcance**: en SQLite, `run()` registra un WARNING porque SQLite no admite `TRUNCATE TABLE` (limpieza del destino). Es previo a esta sesión.

## Rollback
`git revert <commit>`.

## Directrices para Futuras IAs
- **[dump / informe]**: el orden de las hojas opcionales es fijo: Índices → Auditoría Bulk → Secuencias PK. Toda hoja nueva va detrás de todas y necesita un test que fije el orden; sin él, la mutación que reordena sobrevive.

## Veredicto final
CLOSED
