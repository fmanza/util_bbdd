# S-3 · `ClientRead` en el UPDATE paralelo de PostgreSQL — informe

- Pregunta: con 4 hilos y UPDATE fila a fila (sin `TEMP`) el tiempo empeoraba (25,7 → 56,8 s/1M) y el servidor pasaba el
  82 % en `ClientRead`. ¿Dónde espera el cliente?
- Método (D-1): `s3/s3_clientread.py`, muestreo de pilas de los hilos con `sys._current_frames()` cada 5 ms; mismo
  muestreador con 1 y 4 hilos; `BulkCrud(update_via_staging=False)`. Logs: `s3/s3.log`, `s3/s3_wait_c.log`,
  `s3/s3_contrast.log`.

## Resultados

400K filas, psycopg 3 (`postgresql+psycopg`, Windows):

| Hilos | Tiempo | `wait_select` | `_communicate_gen` (pipeline) | SQLAlchemy/pandas |
|---|---|---|---|---|
| 1 | 10,44 s | 65,8 % | 24,3 % | ~9 % |
| 4 | 22,42 s | 51,6 % | 43,6 % (+ `_fetch_gen` 3,5 %) | < 1 % |

- Con `PSYCOPG_WAIT_FUNC=wait_c` (psycopg evita `wait_c` en Windows por su issue #645): 9,93 s / 21,27 s — **no cambia**.
- Contraste, 100K filas, 1 → 4 hilos:

| Driver | 1 hilo | 4 hilos | Escala |
|---|---|---|---|
| psycopg 3 (pipeline) | 2,66 s | 5,60 s | 0,48× |
| psycopg2 (sin pipeline) | 50,28 s | 13,87 s | 3,6× |
| PyMySQL (UPDATE fila a fila) | 51,63 s | 14,18 s | 3,6× |

## Conclusión
- **Causa (CONFIRMADA a nivel de componente)**: el modo pipeline de psycopg 3 (`executemany`) no escala con hilos: con 1
  hilo es 19× más rápido que psycopg2, pero con 4 hilos cada conexión se frena y el total empeora. No es el transporte ni
  Docker (psycopg2 y PyMySQL escalan 3,6× por la misma red), ni la función de espera de Windows (`wait_c` igual).
- **Mecanismo exacto (HIPÓTESIS)**: contención del GIL en el bucle de E/S no bloqueante del pipeline (cada mensaje exige
  recuperar el GIL; con 4 hilos ocupados en ese bucle el relevo domina). `setswitchinterval` no influye (E7b), coherente
  con relevos al liberar el GIL en cada espera más que con expulsiones por tiempo.
- **Para `bulk`**: la mitigación actual es la correcta (UPDATE por tabla temporal; un solo hilo sin `TEMP`); no hay
  cambio en `src/`.
- **Para S-1**: el cliente de PostgreSQL está limitado por el GIL, que es lo que los procesos evitarían → el spike de S-1
  está justificado (D-3).
