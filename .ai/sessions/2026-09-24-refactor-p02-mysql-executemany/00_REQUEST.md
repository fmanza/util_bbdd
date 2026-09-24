# REQUEST

## Session metadata
- id: 2026-09-24-refactor-p02-mysql-executemany
- fecha: 2026-09-24
- rama: develop
- skill: refactor
- fase solicitada: PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION

## Solicitud original saneada
"si", en respuesta a: "El siguiente paso con más impacto es P-02: un cambio de una línea que hace el INSERT de MySQL y MariaDB unas 2 veces más rápido (medido). ¿Lo hago?"

## Objetivo operativo de esta sesión
- Acelerar el INSERT de MySQL/MariaDB usando el `executemany` del driver (P-02).
- Sin cambios funcionales: mismos valores guardados que la vía multi-fila actual.

## Restricciones explícitas
- `MySQLMultiRowInsertStrategy` sigue disponible vía `insert_resolver`.
- Compatibilidad multi-BBDD; API pública sin cambios.

## Resultado esperado
- Cambio en `src/util_bbdd/bulk/_execution/batch.py` con tests, banco y documentación actualizados.
