# PLAN — pendientes de `bulk` tras v0.25.1

- Base: `develop` = `origin/develop` (`e2ce535`, v0.25.1 publicada).
- Alcance: **P-1** (coste del filtro de OPENJSON del hotfix A1) y **Fase 3** del roadmap de
  `2026-10-01h-performance-audit-bulk-todo` (investigaciones S-1…S-4). Este documento no implementa nada.
- Regla: una sesión y un commit por punto; P-1 con `/refactor` (`perf:`), cada investigación con su informe y su
  decisión **antes** de tocar `src/`.

## Orden propuesto

| # | Punto | Tipo | Esfuerzo | Por qué en este orden |
|---|---|---|---|---|
| 1 | P-1 Filtro de OPENJSON por columna | `/refactor` (`perf:`) | bajo | Ganancia medida y acotada; recupera lo que costó el hotfix |
| 2 | S-4 Prefetch de bloques (repetición) | medición | muy bajo | Solo repetir E3 con `--repeat 3` |
| 3 | S-3 Causa del `ClientRead` en el UPDATE paralelo de PG | diagnóstico | bajo | Sin cambio de código; orienta S-1 |
| 4 | S-2 Aislamiento de filas erróneas | spike + diseño | medio | Mayor valor funcional; API nueva opt-in |
| 5 | S-1 Procesos en lugar de hilos | spike + diseño | alto | Exige API nueva y resolver la auditoría entre procesos |

---

## P-1 · Filtro de OPENJSON por columna (`/refactor`, `perf(bulk):`)

**Problema**: el hotfix A1 (`6075e75`) valida cada clave con `_fits` y `_json_value` en Python
(`bulk/_execution/delete_strategies.py`). Coste medido por millón de claves (CPU, sin BD):

| PK | Hoy (por valor) | Prototipo por columna |
|---|---|---|
| `INT` | 0,40 s | 0,04 s |
| `VARCHAR(10)` | 0,31 s | por medir |
| `NUMERIC(12,2)` | **2,06 s** | por medir |

Con PK entera, el DELETE de 1M en SQL Server pasó de 2,20 a 2,47 s; con PK `DECIMAL` el coste sería mucho mayor.

**Cambio**: `_column_fits(values, column_type) -> bool` decide por columna con operaciones agregadas, sin cambiar la
semántica de `_fits`:
- enteros: tipos exactos con `set(map(type, values))` y `min`/`max` frente al rango del tipo;
- texto: `max(map(len, ...))` (UTF-16 en `NVARCHAR`) y `all(map(str.isascii, ...))` en `VARCHAR`;
- `Decimal`: `as_tuple().exponent` y `adjusted()` en lugar de `quantize` con contexto local; solo los valores con
  exponente más negativo que la escala (ceros a la derecha, p. ej. `1.100`) pasan por la comprobación exacta actual;
- `UUID`, `None`: como hoy.

`_json_value` se reduce a la conversión (`Decimal` → texto, `UUID` → texto).

**Tests**:
- Equivalencia de decisión: `_column_fits(values, t) == all(_fits(v, t) for v in values)` en conjuntos aleatorios por
  tipo y casos límite (rangos exactos de cada entero, longitud exacta, `1.100`, `NaN`, `bool`, `None`, mezcla de tipos,
  caracteres fuera del BMP).
- Se conservan los 27 tests de dominio y los 6 de integración del hotfix (deben seguir pasando sin cambios).

**Aceptación**: CPU del filtro ≤ 0,10 s/1M para `INT`/`VARCHAR` y ≤ 0,40 s/1M para `NUMERIC`; DELETE 1M en SQL Server
con PK entera ≤ 2,25 s (`scripts/bench_bulk.py --engines mssql --ops insert,delete --repeat 3`).

---

## S-4 · Prefetch de bloques (repetición de E3)

- **Pregunta**: ¿la ganancia de preparar el bloque N+1 mientras se escribe el N (+17 % SQL Server, +9 % MySQL, −18 %
  Oracle, una medición) es estable?
- **Método**: `bench/proto_bulk_todo.py pipeline` con 3 repeticiones, solo SQL Server, MySQL y MariaDB, 1M filas.
- **Decisión**: si la mejora es ≥ 10 % con rangos disjuntos en algún motor, opción `prefetch_blocks` opt-in para ese
  motor (`/new-feature`); si no, se cierra como descartada.

## S-3 · Causa del `ClientRead` en el UPDATE paralelo de PostgreSQL

- **Pregunta**: con 4 hilos y UPDATE fila a fila (sin `TEMP`), el servidor pasa el 82 % esperando al cliente y el tiempo
  empeora (25,7 → 56,8 s). No es el convoy del GIL (`setswitchinterval` sin efecto). ¿Dónde espera el cliente?
- **Método**: muestreo de pilas de los 4 hilos con `sys._current_frames()` cada 10 ms durante el UPDATE (biblioteca
  estándar; `py-spy` no está instalado) y recuento por función; comparar 1 hilo frente a 4.
- **Decisión**: documentar la causa; si es corregible en `bulk` (p. ej. pipeline de psycopg y lotes), proponer el
  cambio; si no, se queda la mitigación actual (1 hilo sin `TEMP`).

## S-2 · Aislamiento de filas erróneas (opt-in)

- **Pregunta**: ¿cuánto cuesta no perder una carga entera por unas pocas filas malas?
- **Diseño a validar**: `BulkCrud(..., on_error="isolate", rejects_csv_path=...)`: si falla un lote, se repite dentro de
  un SAVEPOINT por bisección hasta aislar las filas que fallan; las buenas se aplican y las malas se escriben en el CSV
  de rechazos con su posición y el error. Oracle: `executemany(..., batcherrors=True)` como vía nativa.
- **Método**: prototipo fuera de `src/`; 1M filas con 1, 10 y 100 filas malas, 6 motores; medir el tiempo frente a la
  carga limpia y frente a «fallo + corregir + recargar».
- **Decisión**: implementar si el coste con 10 filas malas es ≤ 1,2× la carga limpia.

## S-1 · Procesos en lugar de hilos en `ParallelBulkLoader`

- **Pregunta**: el INSERT paralelo de PostgreSQL apenas escala con hilos (4,3 → 3,7 s con 2 hilos y nada más) porque el
  cliente está limitado por la CPU de Python. ¿Escala con procesos?
- **Método**: prototipo con `ProcessPoolExecutor`, un engine por proceso y lectores serializables; 1M filas, 1/2/4
  procesos, PostgreSQL y SQL Server.
- **Decisión**: implementar solo si 4 procesos dan ≥ 2× sobre 4 hilos en PostgreSQL **y** se resuelven los bloqueos del
  AUDIT_PLAN (lectores serializables, auditoría entre procesos, credenciales).

## Entregables
- P-1: commit `perf(bulk)` con tests y medición antes/después.
- S-1…S-4: un informe por investigación en esta carpeta (`S-n_<tema>.md`) con datos, decisión y, si procede, el PLAN de
  implementación.
