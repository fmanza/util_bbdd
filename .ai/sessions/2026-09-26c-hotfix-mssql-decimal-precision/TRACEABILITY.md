# TRACEABILITY

## Session metadata
- id: 2026-09-26c-hotfix-mssql-decimal-precision
- fecha: 2026-09-26
- rama: develop (base `bba6ed1`)
- skill: hotfix (PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION)
- origen: PD-10 (MEDIA), detectado en `2026-09-26-hotfix-dump-fidelity`; roadmap `2026-09-25b-performance-audit-dump-delta`, paso 0.10

## Prompt issued
```
/hotfix PD-10: en SQL Server con pyodbc y fast_executemany, un Decimal con 38 dígitos significativos se redondea al
escribir (27 dígitos llegan exactos). Afecta a dump y a BulkCrud directo. Supuesto: enviar Decimal como str o fijar
setinputsizes. Criterios: DECIMAL(38,10) con 38 dígitos exacto en dump y BulkCrud; escritura sin empeorar > 5 %.
```

## RCA
- El supuesto de partida era incompleto. SQLAlchemy sí trata los `Decimal` (`_MSNumeric_pyodbc`), y `bulk` usa `insert(tabla)`; el redondeo ocurre **dentro de pyodbc**.
- Con `fast_executemany`, pyodbc convierte cada `Decimal` al `NUMERIC` del parámetro **con el contexto `decimal` del hilo**, de 28 dígitos por defecto. Pista: el valor redondeado (`…678.9012345678` → `…679`) tiene exactamente 28 dígitos significativos.
- Verificado con pyodbc 5.3.0 directo contra SQL Server 2022:
  - sin `fast_executemany` → exacto;
  - con `fast_executemany` y `prec=28` → redondeo, o error 8023 si el redondeo desborda (`-9999…9,9999999999`);
  - con `prec=38` o `50` → exacto.
- **Descartado**: enviar el `Decimal` como `str`. Con `fast_executemany` pyodbc dimensiona el búfer por el parámetro descrito y falla (`String data, right truncation`). `setinputsizes` exigiría reconstruir el orden de parámetros de cada sentencia.
- **Efecto en `bulk`** (antes del arreglo): INSERT con claves DECIMAL de 38 dígitos → error 8023; UPDATE y DELETE por esas claves no encontraban la fila; `dump` → valor redondeado sin aviso.

## FIX (mínimo)
- `bulk/_execution/batch.py`: `_driver_decimal_context(engine)` (nuevo) devuelve `decimal.localcontext` con `prec = max(actual, 38)` si el engine es SQL Server con `dialect.fast_executemany`, y `nullcontext` en otro caso. Envuelve la llamada a la estrategia en `BatchStatementExecutor._execute_on_connection` (INSERT y UPDATE) y en `DeleteBatchExecutor` (DELETE).
- Se mira `engine.dialect.fast_executemany` al ejecutar, no el parámetro `enable_fast_executemany` de la instancia: el flag es de todo el engine (`_register_fast_executemany`) y puede venir de otra instancia o de `create_engine(..., fast_executemany=True)`.
- `localcontext` es por hilo: vale para `ParallelBulkLoader`. Solo afecta al código que corre dentro de la llamada al driver.
- `CHANGELOG.md`: entrada *Fixed*; se retira la «limitación conocida» que dejó la entrada de PD-05.

## Validación
- **Tests** (`tests/unit/bulk/test_mssql_decimal_context.py`, nuevo, 6): precisión dentro del contexto por dialecto y flag (mssql+fast → 38; mssql sin fast, PostgreSQL, Oracle → sin cambio); se respeta una precisión mayor del usuario; se restaura al salir; el ejecutor llama a la estrategia con precisión 38 en cada lote.
- **Calidad**: `ruff format` + `ruff check` limpios; `mypy src` limpio; `pytest tests/unit`: **4528 passed**.
- **SQL Server real** (pyodbc + ODBC Driver 18):

| Prueba | Sin el arreglo | Con el arreglo |
|---|---|---|
| Round-trip de `dump` (`zz_pd05`, DECIMAL(38,10) de 38 dígitos) | `…679.0000000000` | **exacto** |
| `BulkCrud` INSERT con claves DECIMAL(38,10) de 38 dígitos | error 8023 | **OK** |
| `BulkCrud` UPDATE / DELETE por esa clave | no encuentra la fila | **OK** |
| `BulkCrud` INSERT con `Decimal` de escalas distintas (12.5, 1E-10, 7) | exacto | exacto |

- **Rendimiento** (A/B intercalado, `large`, `ab_antes/`, `ab_despues/`): `write` 53,2 · 54,5 s → 52,6 · 57,5 s (media +2 %, dentro del ruido; una repetición «después» es más rápida que las dos «antes»). Criterio ≤ 5 % cumplido.

## AUDIT_CODE
- **Otros motores / SQL Server sin `fast_executemany`**: `nullcontext`, sin cambio.
- **Contexto del usuario**: se copia el contexto actual (redondeo, trampas) y solo se sube la precisión; si ya es mayor de 38, no se toca. Se restaura al salir aunque la llamada falle (`with`).
- **Hilos**: `decimal.localcontext` es local al hilo; los hilos de `ParallelBulkLoader` suben su propio contexto.
- **Alcance**: solo la llamada al driver (lote a lote). La normalización y el resto de `bulk` siguen con el contexto del usuario.
- **Hallazgo previsto y descartado**: en la investigación se sospechó que mezclar escalas de `Decimal` en un lote fallaba con `fast_executemany` (error 8023 con pyodbc directo). Con `BulkCrud` funciona también sin el arreglo; el error venía del valor de 38 dígitos al desbordar con 28. No hay hallazgo aparte.
- **Compatibilidad**: sin cambios de API.

## VERSION
- Commit: `fix(bulk): no redondear DECIMAL de más de 28 dígitos en SQL Server con fast_executemany (PD-10)`
- Changelog: *Fixed* (y retirada de la limitación de PD-05).
- Rollback: `git revert <commit>`.

## Directrices para Futuras IAs
- **[bulk/mssql]**: pyodbc con `fast_executemany` usa el contexto `decimal` del hilo al convertir `Decimal`. Cualquier nueva ruta de escritura a SQL Server debe pasar por `_driver_decimal_context`.
- **[bulk/mssql]**: no envíes `Decimal` como `str` con `fast_executemany`: el búfer se dimensiona por el parámetro descrito (`right truncation`).
- **[investigación]**: al probar pyodbc directo, un error puede venir de un valor de otra fila del lote; aísla fila a fila antes de concluir.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- PD-09 (MySQL/MariaDB: el listener `checkin` tapa el error original), PD-06 (SQLite con rangos), PD-07 (origen SQLite).
