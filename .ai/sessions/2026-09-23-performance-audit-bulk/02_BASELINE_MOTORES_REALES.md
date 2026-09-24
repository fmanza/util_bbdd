# Línea base con motores reales (Fase 0)

- Fecha: 2026-09-24 · Herramienta: `scripts/bench_bulk.py` (sesión `2026-09-24-bulk-bench-harness`)
- Entorno: Windows 11, Python 3.14.2, pandas 3.0.3, SQLAlchemy 2.0.50; servidores en Docker local (`docker-compose.bench.yml`), `chunk_size=5000`
- Motores: SQLite 3.50.4 · PostgreSQL 17.11 (psycopg 3) · MySQL 8.4.11 (PyMySQL) · MariaDB 11.4.13 (PyMySQL) · SQL Server 2022 16.0.4295 con **pymssql 2.3.13** y con **pyodbc 5.3.0 + ODBC Driver 18** · Oracle 23 Free (oracledb thin)
- Tamaños: 1K/10K/100K con 3 repeticiones (mediana); 1M con 1 repetición
- Resultado de verificación:
  - 6 motores (SQL Server con pymssql): 240/240 mediciones con verificación SQL correcta (96 combinaciones motor × operación × tamaño × variante), 0 errores.
  - SQL Server con pyodbc: 33 mediciones correctas, 17 errores esperados y reproducibles: UPDATE `baseline` por P-18; DELETE ≥ 10K por P-05.
- Datos completos:
  - `baseline/summary_{small,1m}.md`, `baseline/results_{small,1m}.csv`, `baseline/environment_{small,1m}.json`
  - SQL Server con pyodbc: `baseline/*_mssql_pyodbc_{small,1m}.*`

**Límite**: servidores en Docker en la misma máquina, con latencia de red casi nula. Contra un servidor remoto, las operaciones con una ida y vuelta por fila (UPDATE en MySQL/MariaDB/SQL Server con pymssql) serán proporcionalmente mucho más lentas.

## Tiempos a 1M filas (segundos)

| Motor | INSERT | UPDATE | DELETE |
|---|---|---|---|
| SQLite | 13,7 | 17,0 | 2,8 |
| PostgreSQL | 20,1 | 40,5 | 28,2 |
| Oracle | 24,5 | 28,3 | 23,4 |
| MySQL | 50,8 (26,7 con P-02) | **378,5** | 15,7 |
| MariaDB | 50,2 (24,5 con P-02) | **339,0** | 15,0 |
| SQL Server (pymssql) | **376,4** | **556,1** | 45,6 |
| SQL Server (pyodbc) `baseline` | **245,5** | **falla (P-18)** | no medido¹ |
| SQL Server (pyodbc) con P-01 | 20,4 | 29,8 | **falla (P-05)** |

¹ El ciclo se corta al fallar el UPDATE; el DELETE falla igualmente por P-05 en la variante P-01.

## Filas por segundo a 100K (mediana de 3)

| Motor | INSERT | UPDATE | DELETE |
|---|---|---|---|
| SQLite | 70.151 | 54.145 | 257.732 |
| PostgreSQL | 47.849 | 23.696 | 35.351 |
| Oracle | 40.284 | 36.283 | 45.255 |
| MySQL | 17.410 → 32.192 (P-02) | 2.627 | 61.406 |
| MariaDB | 19.813 → 38.156 (P-02) | 2.930 | 67.083 |
| SQL Server (pymssql) | 2.702 | 1.728 | 21.250 |
| SQL Server (pyodbc) | 3.841 → **45.842 (P-01)** | falla (P-18) → **33.459 (P-01)** | falla (P-05) a partir de 10K |

## Estado de los hallazgos tras la medición

| ID | Antes | Ahora | Evidencia |
|---|---|---|---|
| P-01 | ALTA · confirmada en código | **CONFIRMADA — CRÍTICA** | INSERT con `create_engine(fast_executemany=True)`: 11,55× (1K), 11,83× (10K), 11,93× (100K), **12,06× (1M: 245,5 s → 20,4 s)**. Además corrige P-18: el UPDATE pasa de fallar a 33.500 filas/s. |
| P-02 | CRÍTICA · hipótesis contra servidor | **CONFIRMADA** | INSERT con executemany del driver: MySQL 1,85× (100K) y 1,90× (1M); MariaDB 1,93× (100K) y 2,05× (1M). A 1K es ruido (0,67×–1,18×). UPDATE y DELETE sin cambios (esperado: la variante solo afecta al INSERT). |
| P-04 | ALTA · hipótesis | **CONFIRMADA** | UPDATE a ~2.600–2.950 filas/s en MySQL/MariaDB y 1.800 en SQL Server con pymssql, frente a 35.000 en Oracle, 24.700 en PostgreSQL y 33.500 en SQL Server con pyodbc + P-01. 1M filas: 339–556 s frente a 28–41 s. |
| P-05 | CRÍTICA · confirmada en código | **CONFIRMADA (ambas partes)** | Sintaxis de PK compuesta: falla con pymssql y con pyodbc. Límite de parámetros: con pyodbc el DELETE de ≥ 10K filas falla con `07002 COUNT field incorrect or syntax error` (lotes de 5000 parámetros); con pymssql no aplica (sustitución en cliente). Tests `xfail(strict=True)` con los dos drivers. |
| P-03 | ALTA | Coherente | SQLite 1M INSERT 13,7 s (13,3 s en la medición del 23-09): la preparación en Python sigue siendo el suelo del resto de motores. |

## Hallazgos nuevos

### P-18: `bulk_update_from_df` falla en SQL Server + pyodbc con columnas DATETIME
**Severidad**: CRÍTICA (fallo funcional con la configuración por defecto)
**Área**: 8 (específico de motor)
**Archivo/Función**: `_execution/batch.py:19-42` (`_fast_executemany_listener`, `_register_fast_executemany`), activado por defecto desde `BulkCrud(enable_fast_executemany=True)`
**Descripción**: con `mssql+pyodbc` y ODBC Driver 18, todo `bulk_update_from_df` sobre una tabla con una columna `DATETIME` falla con `HY104 Invalid precision value (0) (SQLBindParameter)`. El listener activa `cursor.fast_executemany` a espaldas de SQLAlchemy, así que el dialecto no ajusta los tipos de los parámetros (`setinputsizes`) y pyodbc enlaza el `datetime` con precisión 0. El INSERT no falla porque, por P-01, nunca llega a usar fast_executemany.
**Evidencia** (bisección de columnas, 20 filas, tabla con PK + columnas indicadas):

| Columnas además de la PK | Listener (por defecto) | `enable_fast_executemany=False` | `create_engine(fast_executemany=True)` |
|---|---|---|---|
| A INT, F FLOAT, S VARCHAR | OK | — | — |
| solo D DATETIME | **FALLA** | — | — |
| A,D / F,D / S,D | **FALLA** | — | — |
| A, F, S, D | **FALLA** | OK | OK |

Los NULL en la primera fila no influyen: con A, F y S el UPDATE funciona con y sin NULL.

- Banco: UPDATE `baseline` falla en 10 de 10 ejecuciones (1K a 1M).
- Test de integración `test_insert_and_update_roundtrip[mssql]`: falla con pyodbc (marcado `xfail(strict=True)`, P-18) y pasa con pymssql.

**Confirmación**: CONFIRMADA.
**Remediación propuesta**: la de P-01. Que `BulkCrud` no dependa del listener y use fast_executemany a través de SQLAlchemy (`create_engine(fast_executemany=True)` o una estrategia con cursor crudo y `setinputsizes`). Ambas medidas funcionan. Mientras tanto, los usuarios pueden:
- crear el engine con `create_engine(..., fast_executemany=True)`, o
- usar `BulkCrud(..., enable_fast_executemany=False)`.

### P-17: SQL Server + pymssql inserta a ~2.700 filas/s
**Severidad**: ALTA (CRÍTICA para cargas de 1M: 376 s)
**Área**: 8 (específico de motor)
**Archivo/Función**: `_execution/batch.py` `InsertStrategyResolver.resolve` (mssql → `DefaultInsertStrategy`)
**Descripción**: con pymssql, SQLAlchemy aplica insertmanyvalues (sentencias multi-VALUES de ≤ 2099 parámetros, ~233 filas con 9 columnas). cProfile sobre 20K filas: 6,16 s de 6,31 s en `do_execute` (driver + servidor), unos 72 ms por sentencia; SQLAlchemy es despreciable. El `executemany` crudo de pymssql es aún más lento (9,68 s).
**Evidencia**: prueba en el contenedor del banco, tabla temporal de 9 columnas y 20K filas:
- SQLAlchemy (actual): 6,31 s
- `cursor.executemany` de pymssql: 9,68 s
- **`connection.bulk_copy()` de pymssql (BCP/TDS bulk load): 0,94 s (6,7×)**, 20K filas verificadas.
**Confirmación**: CONFIRMADA (medición real).
**Remediación propuesta**: estrategia `MSSQLBulkCopyStrategy` para `mssql+pymssql` cuando `stmt` es `Insert`, con `check_constraints=True` y `fire_triggers=True` para conservar la semántica de un INSERT normal (por defecto BCP no comprueba constraints ni dispara triggers). Hay que verificar:
- atomicidad dentro de `bulk_session` (misma transacción);
- tablas con IDENTITY (`KEEPIDENTITY`);
- tipos (fechas, NULL, Unicode).

Con pyodbc + P-01 el INSERT ya alcanza 49.000 filas/s; para quien pueda elegir driver, pyodbc + ODBC 18 es hoy la mejor vía en SQL Server.

## Prioridad revisada (por impacto medido)

1. **P-01 + P-18**: fast_executemany a través de SQLAlchemy en `mssql+pyodbc`. Corrige un fallo funcional (UPDATE con DATETIME) y acelera el INSERT 12×. Cambio pequeño.
2. **P-05**: hotfix de DELETE en SQL Server (PK compuesta con ambos drivers; límite de parámetros con pyodbc).
3. **P-04**: UPDATE vía tabla temporal en MySQL/MariaDB y SQL Server con pymssql (−300 a −500 s por millón de filas en local).
4. **P-02**: executemany nativo en MySQL/MariaDB (INSERT ~2×, cambio de una línea). Quick win confirmado.
5. **P-17**: `bulk_copy` para SQL Server + pymssql (INSERT 6,7×).
6. **P-03**: normalización por columna (todos los motores; suelo de ~8 s por millón de filas).
