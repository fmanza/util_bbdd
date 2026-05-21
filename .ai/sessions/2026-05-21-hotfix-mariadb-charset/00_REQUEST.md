# REQUEST

## Session metadata
- id: 2026-05-21-hotfix-mariadb-charset
- fecha: 2026-05-21
- rama: develop
- skill: hotfix
- fase solicitada: RCA → FIX × 4 iteraciones → AUDIT_CODE → VERSION

## Solicitud original saneada

Bug: `SyncQueryExecutor.execute_custom_many` falla en MariaDB con Python 3.14 durante
migración de esquemas (`migrate/planner.py` → `extractors/mariadb.py`).

Traceback final reportado (4.ª iteración):
```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xd3 in position 33
→ SystemError: fetchrows returned a result with an exception set  (fetchall)
→ UnicodeDecodeError: 'utf-8' (en handling del anterior)
→ SystemError: fetchone returned a result with an exception set   (fallback)
→ DatabaseOperationError: Error executing custom query
```

## Objetivo operativo de esta sesión
- Identificar la cadena de causas raíz del crash en Python 3.14 + mariadb-connector-python
- Aplicar fix mínimo acotado en `sync_query_executor.py` sin refactorizar
- Garantizar 18 tests contractuales en verde tras cada fix
- Producir artefactos de trazabilidad y mensaje de commit final

## Restricciones explícitas
- Solo fix mínimo: prohibido refactorizar o añadir abstracciones
- No tocar código fuera de `executors/sync_query_executor.py` (+ tests)
- 4 hotfixes iterativos: cada uno corrige el fallo residual del anterior

## Resultado esperado
- `sync_query_executor.py` corregido con `SET NAMES 'binary'` vía SQL antes del fetch
- `test_sync_executor_contract.py` con 18 tests verdes
- Sesión documentada con artefactos de trazabilidad
- Mensaje de commit listo para subir a GitHub
