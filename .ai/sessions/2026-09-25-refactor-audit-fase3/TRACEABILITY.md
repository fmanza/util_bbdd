# TRACEABILITY

## Session metadata
- id: 2026-09-25-refactor-audit-fase3
- fecha: 2026-09-25
- rama: develop (base `615ab0b`)
- skill: refactor
- origen: roadmap `.ai/sessions/2026-09-25-audit-code-audit-manager/`, fase 3 (L-1a..d → H5, H7, H8, tipado; L-3 → H14)

## Prompt issued
```
Sigue con el roadmap
```

## AI output summary
- **L-1a (H5)**: el docstring de `AuditManager.registrar_operacion`, `AuditTransaction.obtener_resumen` y `docs/api/bulk-audit.md` aclaran que `total_filas`/`rowcount` son filas enviadas, no afectadas.
- **L-1b (H7)**: el setter `AuditManager.columnas_auditoria` emite `DeprecationWarning` (se retira en la próxima versión menor).
- **L-1c (H8)**: `AuditConfigError(AuditError, ValueError)`; `AuditCsvRepository.validar_ruta` la lanza en lugar de `ValueError`.
- **L-1d**: `AuditTransaction.__exit__` tipado (`type[BaseException] | None`, `BaseException | None`, `TracebackType | None`); la rama usa `exc_type is None` para acotar el tipo.
- **L-3 (H14)**:
  - `.claude/commands/performance-audit-bulk.md`: la tabla de las 10 áreas entera tenía rutas inventadas, no solo la línea 50.
  - `.github/prompts/audit_audit_manager_bulk.prompt.md`: rutas y funciones reales y un mapa verificado del componente.
- **Fuera de alcance**: L-2 (futuro de `AuditTransaction`), una decisión de versión mayor pendiente del mantenedor.

## Validación
- **Tests nuevos** (2, `tests/unit/test_audit_subsystem.py`): el setter avisa; una ruta inaccesible lanza `AuditConfigError` que es `ValueError`.
- **Calidad**:
  - `ruff check` y `ruff format --check` limpios; `mypy` limpio (342 ficheros);
  - `tests/unit` 4377 passed, también con `-W error::DeprecationWarning:util_bbdd` (nada interno usa el setter);
  - `mkdocs build --strict` sin avisos.

## AUDIT_CODE
- **API pública**:
  - Deprecación explícita del setter, justificada porque rompe el CSV.
  - `AuditConfigError` gana una base (`ValueError`): compatible hacia atrás. Un `except ValueError` ahora también la captura; en `bulk/crud.py` no se llega a ese caso (con `audit_csv_path=None`, `registrar_operacion` sale antes).
- **Comportamiento**: sin cambios salvo el aviso de deprecación y la clase de la excepción de `validar_ruta`.

## Rollback
`git revert <commit>`.

## Directrices para Futuras IAs
- **[auditoría / contrato]**: `total_filas` = filas enviadas. No presentarlo como filas afectadas en docs ni informes.
- **[config IA]**: antes de citar un fichero en un prompt o comando, comprobar que existe (`Glob`). Este prompt se generó con rutas inventadas y desvió la primera fase de la auditoría.
