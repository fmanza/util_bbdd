# S-1 · Procesos en lugar de hilos en `ParallelBulkLoader` — informe

- Pregunta: el INSERT paralelo de PostgreSQL no escala con hilos (S-3: el cliente psycopg 3 está limitado por el GIL).
  ¿Escala con procesos?
- Método: `s1/s1_processes.py`: hilos = `ParallelBulkLoader.load` (API actual, lotes de 20 000); procesos =
  `ProcessPoolExecutor` (`spawn`, Windows) con una función de módulo; cada proceso crea su engine desde la variable de
  entorno heredada (sin pasar la contraseña), genera su partición determinista y la inserta con
  `bulk_insert_from_chunks`. 1M filas; recuentos verificados. Log: `s1/s1.log`.

## Resultados (segundos)

| Motor | Trabajadores | Hilos | Procesos: total | Procesos: solo inserción | Procesos: arranque |
|---|---|---|---|---|---|
| PostgreSQL | 1 | 3,46 | 5,36 | 3,47 | 1,34 |
| PostgreSQL | 2 | 3,27 | 3,78 | 1,82 | 1,37 |
| PostgreSQL | 4 | 3,36 | 3,74 | **1,25** | 1,77 |
| SQL Server | 1 | 14,56 | 16,57 | 14,48 | 1,50 |
| SQL Server | 2 | 7,75 | 9,21 | 7,41 | 1,25 |
| SQL Server | 4 | 5,44 | 5,81 | 3,86 | 1,35 |

(«Arranque» incluye crear el proceso, importar pandas/SQLAlchemy y, en este prototipo, generar el DataFrame de 1M para
cortar su partición; en un uso real cada proceso leería solo su partición del origen.)

## Conclusión
- Confirma S-3: en PostgreSQL la fase de inserción escala con procesos (1,25 s con 4 frente a 3,36 s con 4 hilos: 2,7×);
  con hilos no escala nada. En SQL Server los hilos ya escalan (2,7×) y los procesos añaden poco (1,4× en inserción).
- A 1M filas el arranque de cada proceso (1,3–1,8 s en Windows) se come la ganancia: el total con procesos es igual o
  peor que con hilos. Compensaría en cargas de más de ~5–10M filas por tabla (HIPÓTESIS, extrapolada, sin medir).
- Criterio del PLAN («≥ 2× sobre 4 hilos en PostgreSQL y resolver R-5…R-7»): se cumple en la fase de inserción, no en
  tiempo total a 1M, y R-5 (API de lectores serializables), R-6 (lock de fichero para la auditoría) y R-7 siguen
  pendientes.
- **Decisión: NO_GO por ahora.** Reabrir si aparece un caso real de cargas de ≥ 10M filas por tabla en PostgreSQL:
  medir primero a 10M con lectores que lean solo su partición, y diseñar entonces la API (`reader factory` importable,
  p. ej. `(sql, params)`) y el lock de fichero de `AuditCsvRepository`.
