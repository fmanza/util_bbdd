# Informe de validación — performance-audit de `bulk/` (2026-10-01h)

Validación de las hipótesis del informe con el banco real, **sin tocar `src/`**: línea base con `scripts/bench_bulk.py` y
prototipos A/B en `bench/` (parches de instancia o SQL propio). Cada medición se verificó con SQL (recuento o suma de la
columna actualizada). Los experimentos se ejecutaron en serie para no competir por CPU.

## Reproducción

```bash
# URLs del banco (ver .ai/runtime.md); SQL Server con mssql+pyodbc + ODBC Driver 18
python scripts/bench_bulk.py --sizes 1000,10000,100000 --repeat 3 --variants baseline --out <sesión>/baseline/small
python scripts/bench_bulk.py --sizes 1000000 --repeat 1 --variants baseline --out <sesión>/baseline/1m
python scripts/bench_bulk.py --sizes 1000000 --chunk-size {1000,20000,50000} --out <sesión>/bench/chunks/c<N>
python <sesión>/bench/proto_bulk_todo.py {prep,share,pipeline,pgupdate,msupdate,oracleupd,msdelete,parallel,cadence,audit}
python <sesión>/bench/proto_oracle_delete.py
python <sesión>/bench/proto_pg_parallel_update.py
```

## Resultados

| Exp. | Hipótesis | Resultado | Mediciones OK | Veredicto |
|---|---|---|---|---|
| Línea base | — | 1M: 18/18; 1K–100K: 54/54 | 72/72 | referencia |
| E1 `share` | La preparación pesa en el INSERT | 9,9 % (MySQL) – 31,2 % (PG) | 6/6 | confirmada |
| E2 `prep` | Columnas→tuplas ahorra CPU | 2,37–2,84 s → 1,39 s por 1M | CPU | **B-03 confirmada** |
| E3 `pipeline` | Prefetch solapa preparación y escritura | INSERT +0–17 %, Oracle −18 % | 24/24 | **B-09: ganancia baja e irregular** |
| E4 `pgupdate` | Staging acelera el UPDATE de PG | 24,9 → 10,6 s (2,35×) | 6/6 | **B-01 confirmada** |
| E4b `msupdate` | Staging acelera el UPDATE de SQL Server | 21,7 → 28,9 s (lote 5000); 21,5 → 22,8 s (50.000) | 6/6 | descartada |
| E4c `oracleupd` | Staging (PTT + MERGE) en Oracle | 15,1 → 20,9 s; el CREATE de la PTT confirma la transacción | 5/5 | descartada |
| E5 `msdelete` | OPENJSON evita la compilación de IN largos | 1M 3,45×; 10K 20×; 1K 8× | 24/24 | **B-02 confirmada** |
| E5b Oracle DELETE | Colección en lugar de executemany | ≤ 8–15 % con ruido | 12/12 | descartada |
| E6 `chunks` | El lote óptimo depende de motor y operación | 20.000 gana en INSERT PG/SQL Server; 50.000 daña DELETE MySQL/MariaDB | 54/54 | **B-04 confirmada** (1 repetición) |
| E7 `parallel` | UPDATE paralelo escala | SQL Server 2,9×, MySQL 2,3×, MariaDB 1,8×, Oracle 1,0×, **PG 0,45×** | 40/40 | **B-05 confirmada** |
| E7b PG | Causa: convoy del GIL | `setswitchinterval` sin efecto; 82 % `ClientRead`; staging ×4 hilos 6,3 s | 3/3 | GIL descartado; límite en el cliente |
| E8a `cadence` | Coste de la cadencia | ±6 % salvo SQLite (+14/+31 %) y MariaDB (+12/+22 %) | 18/18 | **B-12 confirmada** |
| E8b rollback | Coste del rollback de 1M | 0,001 s (PG) – 2,41 s (MariaDB) | 6/6 | B-15 (dato) |
| E8c reanudación | `rows_committed` sirve de checkpoint | 600.000 confirmadas y 1M exactas tras reanudar en 6/6 motores; 0,94–1,07× del tiempo limpio | 6/6 | **B-11 confirmada** |
| E9 `audit` | La auditoría CSV tiene coste | −0,7 % a +2,5 % (ruido) | 24/24 | **B-18: limpio** |
| Mapeo de errores | Reintento por clase incoherente | PyMySQL 1045/1054/1292 → `OperationalError`; Oracle ORA-00060 → `DatabaseError` | — | **B-13 confirmada** |

## Mejoras validadas listas para implementar

| Hallazgo | Antes (1M) | Prototipo (1M) | Factor |
|---|---|---|---|
| B-01 PG UPDATE staging | 24,9 s | 10,6 s | 2,35× |
| B-01 + B-05 PG UPDATE staging con 4 hilos | 24,9 s | 6,3 s | 3,95× |
| B-02 SQL Server DELETE OPENJSON | 8,45 s | 2,45 s | 3,45× |
| B-05 SQL Server UPDATE 4 hilos | 22,7 s | 7,9 s | 2,9× |
| B-05 MySQL UPDATE 4 hilos | 27,7 s | 12,6 s | 2,2× |
| B-11 fallo al 60 % → reanudación | 1,6× (reinicio) | 1,0–1,07× | −33 a −37 % |

## Límites de la validación
- Docker local: latencia de red ~0 y buffer pool caliente (el rollback de MySQL sería más caro bajo presión).
- Oracle 23 Free limitado a 2 hilos de CPU: no sirve para juzgar el paralelismo en Oracle.
- Una repetición en 1M para E3, E6 y E7: diferencias < 10 % se tratan como ruido.
- B-03 medido solo en CPU; la ganancia extremo a extremo es una estimación.
- El deadlock de SQL Server con pyodbc (SQLSTATE 40001) no se reprodujo.
