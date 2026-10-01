# TRACEABILITY

## Session metadata
- id: 2026-10-01j-hotfix-openjson-domain
- fecha: 2026-10-01
- rama: develop (base `722dbd4`, v0.24.0 publicada; B-04 de `2026-10-01i` sin commit en el árbol)
- skill: hotfix
- fase: PLAN → AUDIT_PLAN → IMPLEMENT (RCA + fix) → AUDIT_CODE → VERSION

## Prompt issued
`/hotfix` de A1 y A2 del audit-code `../2026-10-01i-perf-bulk-b04-batch-size/AUDIT_CODE_fases0-2_b04.md` (veredicto
RECHAZADO).

## PLAN
- **Objetivo**: A1 (CRÍTICA, publicado en v0.24.0): el DELETE de SQL Server con OPENJSON borra filas no pedidas cuando la
  clave no cabe en el tipo de la PK. A2 (MEDIA, regresión de B-13): con el conector `mariadb` el lock wait timeout no se
  reintenta.
- **Rutas**: `src/util_bbdd/bulk/_execution/delete_strategies.py` (`MSSQLOpenJsonDeleteStrategy`, `_openjson_payload`),
  `src/util_bbdd/bulk/_support/retry.py` (`_driver_error_is_retriable`).
- **Supuesto**: los tipos reflejados de SQL Server son los de SQLAlchemy 2.0.50 (verificado: `TINYINT` del dialecto,
  `SMALLINT`, `INTEGER`, `BIGINT`, `DECIMAL`/`NUMERIC` con precision/scale, `VARCHAR`/`CHAR` vs `NVARCHAR`/`NCHAR`,
  `UNIQUEIDENTIFIER` ⊂ `Uuid`, `FLOAT` ⊂ `Numeric`).
- **Riesgos**: falsos negativos del filtro (claves válidas que van por `IN`: solo coste) frente a falsos positivos (claves
  que no caben y siguen por OPENJSON: el bug). El filtro es conservador (VARCHAR solo ASCII).

## AUDIT_PLAN
- Funcional: el filtro se evalúa por lote; un lote con una sola clave fuera de dominio va entero por `IN` (correcto).
- Técnico: `Decimal.quantize` lanza con > 28 dígitos en el contexto por defecto → contexto local de 200 dígitos.
- Seguridad: sin cambios (valores siguen como parámetro JSON).
- Simplificación descartada: `CAST` a tipo ancho (`NVARCHAR(MAX)`, `DECIMAL(38,s)`): introduce conversiones implícitas
  en la columna (posible pérdida del index seek) y no resuelve el redondeo con escala > 38.

## IMPLEMENT
- **RCA A1**: `CAST([value] AS <tipo de la PK>)` y `OPENJSON … WITH (<col> <tipo>)` convierten la clave al dominio de la
  columna antes de comparar; SQL Server trunca cadenas, redondea decimales y aplica *best fit* del code page en `VARCHAR`
  sin error, así que la clave convertida puede coincidir con otra fila. La vía `IN` compara el parámetro tal cual.
- **Fix A1**: `_fits(value, column_type)`: `str` solo en columnas de texto y dentro de la longitud (UTF-16 en
  `NVARCHAR/NCHAR`; en `VARCHAR/CHAR` además solo ASCII); `int` solo en enteros (rango de `TINYINT`/`SMALLINT`/`INT`/
  `BIGINT`) o `NUMERIC` (dígitos enteros ≤ precision − scale); `Decimal` solo en `NUMERIC/DECIMAL` sin perder decimales
  ni desbordar; `UUID` solo en `Uuid`; `None` siempre. Si un valor no cabe, el lote va por la estrategia anterior.
  `_openjson_payload(columns, column_types)`.
- **RCA A2**: `_driver_error_is_retriable` decidía por `sqlstate` antes que por `errno`; los errores de `mariadb`
  llevan ambos (1205 → `HY000`, fuera del conjunto de PostgreSQL).
- **Fix A2**: `errno` (entero) primero. psycopg/psycopg2 no tienen `errno` (PostgreSQL no cambia).
- **Tests (test-first: 17 fallaban antes del fix)**: `test_delete_mssql_openjson.py` (+27: 15 fuera de dominio, 11 dentro,
  compuesta; payload con tipos y DECIMAL de 38 dígitos), `test_retry_classification.py` (+5, forma real de `mariadb`),
  integración `test_bulk_audit_20261001.py` (+6: los 4 casos del audit, compuesta y lock wait real con `mariadb`).
  Mutación: con el código de v0.24.0 fallan las 6 de integración.

## AUDIT_CODE
- Regresiones: ninguna en 5875 unit / 455 integración (pyodbc) / 72 con pymssql.
- Edge cases cubiertos: `VARCHAR(MAX)` (sin límite), ceros a la derecha (`1.100` en escala 2), `None`, `bool`
  (rechazado), NaN, `FLOAT` (rechazado), caracteres fuera del BMP en `NVARCHAR`.
- Rendimiento: DELETE 1M en SQL Server 2,20 → 2,47 s (validación en Python por clave); 10K 0,040 → 0,044 s. Sigue 3,4×
  más rápido que `IN` (8,4 s). Sin optimizar (política de hotfix).
- Compatibilidad: sin cambios de API; solo cambia qué lotes van por OPENJSON y qué errores de `mariadb` se reintentan.

## VERSION
- Commit: `hotfix(bulk): DELETE de SQL Server con OPENJSON solo si las claves caben en el tipo de la PK; errno antes que
  sqlstate al reintentar`.
- Changelog: `[Unreleased]` → *Fixed* (dos entradas).
- Rollback: `git revert` del commit (vuelve el bug A1); alternativa sin revert para A1: ninguna en la API (el DELETE de
  SQL Server no tiene interruptor) → no revertir.

## Directrices para Futuras IAs
- **[bulk/delete mssql]**: cualquier `CAST`/`OPENJSON … WITH` al tipo de la columna cambia la semántica de la comparación
  (trunca, redondea, best fit); valida que el valor cabe antes (`_fits`) o compara en el tipo del parámetro.
- **[bulk/retry]**: los errores del conector `mariadb` traen `errno` **y** `sqlstate`; decide por `errno`. Prueba la
  clasificación con errores reales del servidor, no con excepciones simuladas de un solo atributo.
- **[tests]**: para A1 hay que comprobar las filas que **quedan**, no solo que se borran las pedidas: los tests de B-02
  pasaban porque solo miraban lo borrado.

## Veredicto final
Veredicto: CLOSED (fix aplicado y verificado; commit con el cierre de B-04 → v0.25.0)
Pendientes al cierre:
- A3–A5 del audit-code (deuda: guarda de sesión abierta en `*_from_chunks`, nota de commit periódico, `type: ignore`).
