# TRACEABILITY

## Session metadata
- id: 2026-09-25-hotfix-audit-cache-stale
- fecha: 2026-09-25
- rama: develop (base `8e8539f`)
- skill: hotfix
- origen: roadmap `.ai/sessions/2026-09-25-audit-code-audit-manager/` (M-4 → H6)

## Prompt issued
```
Sigue con el roadmap
```

## AI output summary
- **RCA**: `AuditCsvRepository.es_cache_valido()` solo comprobaba el TTL. La caché se invalidaba con las escrituras de la propia instancia (`registrar_operacion`), pero no con las de otras instancias sobre el mismo CSV (una `BulkCrud` por hilo en `ParallelBulkLoader`, o un `AuditManager` de lectura aparte).
- **Fix**:
  - se guarda la firma `(st_mtime_ns, st_size)` del CSV, tomada **antes** de leerlo;
  - `es_cache_valido()` exige además que la firma no haya cambiado (1 `stat`, ~4 µs);
  - si el fichero no existe, la caché no es válida.
- **Tests** (`tests/unit/test_audit_subsystem.py::TestRepositoryCache`, 3 nuevos):
  - escritura de otra instancia (R6) y fichero borrado: en rojo antes, en verde después;
  - reutilización sin cambios, sin `read_csv`: guarda.
- **Validación**:
  - `ruff check` y `ruff format --check` limpios; `mypy` limpio;
  - `tests/unit` 4375 passed;
  - R6: A ve 2 filas tras escribir B.

## AUDIT_CODE
- **Regresiones**: ninguna en API ni formato. Una lectura cacheada añade un `stat`.
- **Edge cases**:
  - Una escritura durante la lectura cambia la firma, y la próxima lectura vuelve a leer (seguro).
  - Una reescritura del fichero con el mismo tamaño y la misma `mtime` no se detecta. Requiere una resolución de `mtime` gruesa (FAT: 2 s); el TTL sigue siendo el tope.

## Rollback
`git revert <commit>`.

## Directrices para Futuras IAs
- **[auditoría / caché]**: la validez de la caché depende del TTL **y** de la firma del fichero. Todo camino que cachee lecturas debe guardar `_cache_firma` tomada antes de leer.
