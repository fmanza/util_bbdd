# REQUEST

## Session metadata
- id: 2026-09-24-hotfix-p05-mssql-delete
- fecha: 2026-09-24
- rama: develop
- skill: hotfix
- fase solicitada: RCA → FIX → AUDIT_CODE → VERSION

## Solicitud original saneada
"sí", en respuesta a: "¿Empiezo el `/hotfix` de P-05, el DELETE que falla en SQL Server?"

## Objetivo operativo de esta sesión
- Corregir P-05(a): con pyodbc, `bulk_delete_from_df` falla a partir de ~2100 filas (límite de 2100 parámetros por petición de SQL Server).
- Corregir P-05(b): con PK compuesta, la sintaxis `(a, b) IN ((..), (..))` no existe en SQL Server (falla con cualquier driver).

## Restricciones explícitas
- Hotfix: fix mínimo en la causa raíz, sin refactorizar ni optimizar.
- MySQL, MariaDB y HSQLDB no deben cambiar.

## Resultado esperado
- Fix en `src/util_bbdd/bulk/_execution/batch.py`; test unitario; retirada de los `xfail` de P-05; CHANGELOG y guía.
