# REQUEST

## Session metadata
- id: 2026-09-24-hotfix-p18-mssql-fast-executemany
- fecha: 2026-09-24
- rama: develop
- skill: hotfix
- fase solicitada: RCA → FIX → AUDIT_CODE → VERSION

## Solicitud original saneada
"Hazlo", en respuesta a la propuesta: "commit de esta fase y empezar por P-01 + P-18 con `/hotfix`, porque hoy rompe el UPDATE".

## Objetivo operativo de esta sesión
- Corregir P-18: `bulk_update_from_df` en SQL Server + pyodbc falla con `HY104 Invalid precision value` en tablas con columnas DATETIME.
- Corregir P-01, misma causa raíz: `enable_fast_executemany=True` no acelera el INSERT.
- Test que reproduzca el fallo sin servidor y regresión con servidor real.

## Restricciones explícitas
- Hotfix: fix mínimo, sin refactorizar ni optimizar nada fuera de la causa raíz.
- Mantener `enable_fast_executemany=False` como salida.

## Resultado esperado
- Fix en `src/util_bbdd/bulk/_execution/batch.py`; test unitario; retirada del `xfail` de P-18; CHANGELOG y guía.
