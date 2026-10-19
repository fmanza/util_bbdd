# AUDIT_CODE

## Bugs potenciales

- Corregido en la propia auditoría: `IndexDdlRunner._find_duplicates` pasaba a `text()` la clave sin escapar los `:`;
  con un índice basado en función con un literal como `' :X'`, el diagnóstico fallaba (se perdían las claves). Ahora
  usa `_escape_colons` (`src/util_bbdd/bulk/_support/secondary_indexes.py`).
- Sin hallazgos abiertos.

## Edge cases revisados

| Caso | Resultado |
|---|---|
| Índice basado en función (columnas ocultas `SYS_NC…$` que cambian al recrear) | La clave del diagnóstico sale de `ALL_IND_EXPRESSIONS` (`key_sql`) |
| `:` en literales del DDL | Escapados en `restore_sql`; el DDL original queda en `recovery_ddl` y en el log |
| Claves todo-NULL | No cuentan como duplicadas (Oracle no las indexa) |
| `GET_DDL` sin privilegios / respuesta no reconocible | `"skipped"` con el motivo y warning; no se ejecuta DDL |
| Duplicados al recrear | `IndexRebuildError` con claves y `recovery_ddl`; el índice queda borrado (documentado) |
| `require_optimization` / `optimization_applied` | No dependen de los índices: un paso `skipped` no los altera |
| Restauración tras error de la carga | `_restore_after_error` usa el mismo `restore()`: también informa `skipped` |

## Performance

- Una llamada a `GET_DDL` por índice único sin constraint, solo en `"all"` y una vez por tabla y operación.
- Sin coste en `"secondary"` ni en los demás motores.

## Seguridad

- El DDL ejecutado lo genera el servidor (`DBMS_METADATA`); no hay entrada del usuario. Los nombres van citados.
- El DDL va al log (nombres de objetos y tablespace; sin datos), como ya hacía PostgreSQL.

## Tipado

- `mypy` sin errores. `IndexActionResult.action` es un `Literal` ampliado (aditivo).

## Deuda técnica

- `fk_orphans.orphan_check_sql` en Oracle usa `FETCH FIRST` (12c+): ver `03_IMPLEMENT.md` § Out-of-scope.
- H1: constraints sobre índices únicos previos (`USING INDEX`).

## Veredicto: APROBADO
