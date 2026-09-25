# Resultados: `bench_loader_audit.py` (2026-09-25)

Entorno: Windows 11 Pro 10.0.26200, 32 CPU lógicas, Python 3.14.2, SQLAlchemy 2.0.50, pandas 3.0.3, NTFS local.
SQLite en fichero (WAL, `synchronous=NORMAL`), 4 particiones y 4 workers, `chunk_size=5000` en el loader. Mediana de 3.

- **en escritura CSV**: suma, sobre los 4 hilos, del tiempo dentro de `AuditCsvRepository.escribir_registros` (lock incluido).
  SQLite serializa a los escritores, así que la suma se acerca al impacto en tiempo real. En motores servidor, con
  inserciones realmente paralelas, es una cota superior.
- **en register_operation**: suma sobre los hilos. Con `commit*` incluye escrituras anidadas, así que no se suma a la anterior.

| filas | chunk lector | modo | sin audit (s) | con audit (s) | Δ E2E % | en escritura CSV (ms) | aperturas CSV | filas CSV | en register_operation (ms) | máx. `_pending` | % en escritura CSV |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 100.000 | 5000 | atómico | 0,362 | 0,374 | +3,5 (ruido) | 4,18 | 4 | 20 | 0,24 | 5 | 1,12 |
| 100.000 | 500 | atómico | 0,572 | 0,562 | −1,7 (ruido) | 2,49 | 4 | 200 | 1,11 | 50 | 0,44 |
| 1.000.000 | 5000 | atómico | 3,437 | 3,396 | −1,2 (ruido) | 2,81 | 4 | 200 | 1,79 | 50 | **0,08** |
| 1.000.000 | 500 | atómico | 4,475 | 4,495 | +0,4 (ruido) | 9,67 | 4 | 2000 | 11,20 | 500 | **0,22** |
| 1.000.000 | 500 | mantenimiento (`disable_constraints`) | 4,783 | 4,769 | −0,3 (ruido) | 7,38 | 4 | 2000 | 11,30 | 500 | **0,15** |
| 1.000.000 | 500 | `commit_every_n_chunks=10` | 4,573 | 4,625 | +1,1 | 100,5 | 400 | 2000 | 48,9 | 9 | **2,2** |
| 1.000.000 | 500 | `commit_every_n_chunks=2` (ejecución 1) | 4,688 | 5,120 | +9,2 | 476,8 | 2000 | 2000 | 199,6 | 1 | **9,3** |
| 1.000.000 | 500 | `commit_every_n_chunks=2` (ejecución 2) | 4,636 | 5,018 | +8,2 | 416,0 | 2000 | 2000 | 191,5 | 1 | **8,3** |

Memoria de `_pending`: **~192 B por `AuditRecord`** (tracemalloc, 100.000 registros, incluido el hueco en la lista).
`sys.getsizeof` da una cota superior de 352 B.
