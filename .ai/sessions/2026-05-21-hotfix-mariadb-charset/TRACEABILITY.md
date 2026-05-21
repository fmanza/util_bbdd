# TRACEABILITY

## Session metadata
- id: 2026-05-21-hotfix-mariadb-charset
- fecha: 2026-05-21
- rama: develop
- skill: hotfix
- fase: RCA × 4 + FIX × 4 + AUDIT_CODE + VERSION

## Prompt issued

```
/hotfix

UnicodeDecodeError: 'utf-8' codec can't decode byte 0xd3 in position 33 [...]
SystemError: <method 'fetchrows' of 'mariadb.cursor' objects> returned a result with an exception set
[...traceback completo de producción reproducido 4 veces con fallo residual tras cada fix]
```

## Context supplied
- Stack trace completo de producción (4 iteraciones)
- `sync_query_executor.py` leído antes de cada iteración
- `test_sync_executor_contract.py` leído antes de cada iteración
- Conocimiento del conector mariadb-connector-python C extension

## AI output summary

**Iteración 1 — `_is_decode_error` no detectaba SystemError sin cadena UnicodeDecodeError**
- RCA: `fetchall()` llama `fetchrows` (C-ext); en Python 3.14, si C-ext tiene excepción activa y
  retorna valor no-NULL, Python eleva `SystemError("returned a result with an exception set")`.
  `_is_decode_error` no reconocía ese patrón de texto → fallback binario nunca se activaba.
- Fix: añadido `"returned a result with an exception set" in message` a `_is_decode_error`.
- Commit: `9f33cd1`

**Iteración 2 — fallback usaba `fetchall()` → mismo bug `fetchrows` en cursor binario**
- RCA: `_retry_fetch_with_binary_cursor` llamaba `cursor.fetchall()` que internamente llama
  `fetchrows` (C-ext) → mismo crash que el original.
- Fix: reemplazado `fetchall()` por bucle `fetchone()` en el cursor de reintento.
- Commit: `54d7321`

**Iteración 3 — `binary=True` cursor no cambia charset; `conn.character_set = "binary"` es no-op**
- RCA: `fetchone()` en cursor binario seguía fallando porque el charset del servidor seguía
  siendo UTF-8. Se intentó `conn.character_set = "binary"` (property setter) pero esta
  propiedad es **client-side only** — no envía `SET NAMES` al servidor.
- Fix: guardar/restaurar `conn.character_set` como referencia. (INSUFICIENTE — ver iteración 4)
- Commit: `f7c21ee`

**Iteración 4 — reemplazar property setter por `SET NAMES 'binary'` vía SQL**
- RCA (definitiva): el traceback completo de producción mostró `UnicodeDecodeError: 'utf-8'`
  en la segunda excepción, probando que el servidor seguía enviando UTF-8. La property setter
  no envía `SET NAMES` al servidor → `character_set_results` permanece UTF-8 → C-ext intenta
  decodificar como UTF-8 → crash.
- Fix: `cursor.execute("SET NAMES 'binary'")` antes del fetch; `cursor.execute("SET NAMES '<saved>'")` 
  al restaurar. El comando SQL cambia `character_set_results` server-side → servidor devuelve
  bytes crudos → C-ext no decodifica → `_decode_binary_value()` maneja los bytes en Python.
- Protocolo de cursores resultante: 4 cursores por operación de reintento:
  1. main (en `_execute_resolved`/`_execute_custom`)
  2. set_names_cursor (SET NAMES 'binary')
  3. binary_cursor (fetch real con fetchone loop)
  4. restore_cursor (SET NAMES '<saved>')
- Tests actualizados: `call_count == 2 → 4`; `assert_called_once() → assert_called()`;
  test `test_execute_custom_mariadb_charset_binary_set_for_fetchone_fallback` reemplazado
  por `test_execute_custom_mariadb_set_names_binary_sent_via_sql` (4 mocks separados).
- Resultado: 18/18 tests verdes.

## Artefactos generados

| Artefacto | Ruta | Estado |
|-----------|------|--------|
| Fix 1 — detect SystemError | `src/util_bbdd/executors/sync_query_executor.py` | commiteado |
| Fix 2 — fetchone loop | `src/util_bbdd/executors/sync_query_executor.py` | commiteado |
| Fix 3 — charset save/restore (property, superado) | `src/util_bbdd/executors/sync_query_executor.py` | commiteado |
| Fix 4 — SET NAMES via SQL | `src/util_bbdd/executors/sync_query_executor.py` | pendiente commit |
| Tests actualizados | `tests/unit/test_sync_executor_contract.py` | pendiente commit |
| Session artifacts | `.ai/sessions/2026-05-21-hotfix-mariadb-charset/` | completados |

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Commit fix 4 + tests
- Push a GitHub (develop)
