# PLAN + AUDIT_PLAN — Deuda menor de la carga paralela (tras v3.0.0)

## Session metadata
- id: 2026-10-16g
- fecha: 2026-10-16
- rama: develop (base `84b3264c`, tag `v3.0.0`)
- skill: tech_debt (`.github/prompts/tech_debt.prompt.md`)
- fase: PLAN + AUDIT_PLAN (sin IMPLEMENT; se espera aprobación)
- origen: deuda D1–D5 de `.ai/sessions/2026-10-16f-bulk-options-parallel-planner/03_AUDIT_CODE.md`

## Supuestos explícitos (inputs del prompt no indicados)
- Módulos objetivo: `src/util_bbdd/bulk/` (fachada paralela, loader) y `src/util_bbdd/dump/orchestrator.py`.
- Scope: PLAN + AUDIT_PLAN ahora; IMPLEMENT solo tras aprobación.
- Compatibilidad: **no** se rompe la API pública (versión PATCH 3.0.1; MINOR 3.1.0 solo si D5 cambia una regla).

---

## PLAN

### Inventario contrastado con el código

| # | Deuda | Evidencia (confirmada) | Impacto real |
|---|---|---|---|
| D1 | Consultas repetidas del privilegio `TEMP` en el UPDATE paralelo de PostgreSQL desde `BulkCrud` | No son 2 sino **N + 2**: `bulk/crud.py:840` (fachada, conexión propia), `bulk/_execution/parallel_loader.py:532` (loader, otra conexión) y `bulk/_execution/staging_update.py:99` (una por worker, dentro de su sesión) | Rendimiento: 2 conexiones y N+2 consultas de catálogo por llamada (milisegundos frente a segundos de carga). Las de los workers son la comprobación autoritativa (la que decide la vía de cada lote) |
| D2 | INFO «Auditoría deshabilitada» en cada carga paralela de la fachada | `parallel_loader.py:422` lo registra si `not audit.enabled`, sin mirar `audit.warn_if_disabled`; la fachada ya avisó con un WARNING al crearse | Ruido en el log (una línea por llamada) |
| D3 | Las filas de una carga paralela no cuentan en `rows_committed` | `bulk/crud.py:965` suma solo auditoría y rechazos | **No es deuda**: `rows_committed` y `last_operation_rows_committed` son posiciones de reanudación de un prefijo (`df.iloc[n:]`); las particiones confirmadas no forman un prefijo. Sumarlas haría reanudar mal. Ya documentado (`last_parallel_result`) |
| D4 | `dump` con `parallel_pk_ranges="auto"` estima las filas con `MAX − MIN + 1` | `dump/orchestrator.py:753`. Pero con `collect_row_counts=True` (default) ya hay un `COUNT(*)` exacto del origen en `orchestrator.py:623`, calculado **antes** de decidir los rangos (`:633`) y sin usar | Decisión: con huecos en la PK se particionan tablas por debajo del umbral medido (solo SQL Server, tablas con rango ≥ 3,5M) |
| D5 | Reglas de Oracle basadas en mediciones inestables | `bulk/_execution/parallel_planner.py` (reglas `oracle`); tandas del 2026-10-16: INSERT 1M en serie 27,3 s y 13,4 s; 200K 1,89× pero 1M 1,33× | Riesgo de decisión subóptima en `"auto"` (en serie cuando quizá gane); las mediciones no son reproducibles: el script vive en el scratchpad de la sesión anterior |

### Propuesta por ítem

| # | Cambio propuesto | Prioridad |
|---|---|---|
| D1 | Quitar las 2 consultas con conexión propia y dejar la de los workers. La fachada pasa el hecho ya comprobado al loader (atributo privado `_temp_tables_allowed` del loader, mismo paquete `bulk`) y el loader lo cachea por instancia, como `BulkCrud`: 1 consulta por instancia de loader y ninguna desde la fachada repetida. Las N de los workers se mantienen (van en su sesión y protegen si el privilegio cambia) | `quick_win` |
| D2 | El loader registra ese INFO solo si `audit.warn_if_disabled`; la fachada le pasa `warn_if_disabled=False` (ya avisó una vez). `dump` ya crea sus loaders sin aviso: verificar que no cambia su salida | `quick_win` |
| D3 | Sin cambio de código: cerrar como decisión de diseño; una línea en `docs/api/bulk_crud.md` explicando **por qué** (prefijo de reanudación) | `quick_win` (solo docs) |
| D4 | Pasar `source_rows` a `_load_in_pk_ranges` (`rows_hint`) y planificar con `min(MAX − MIN + 1, source_rows)` cuando `source_rows ≥ 0`; si no hay recuento (`collect_row_counts=False` o `COUNT` fallido, `-1`), la cota actual. Sin consultas nuevas | `quick_win` |
| D5 | (a) Llevar el benchmark de validación a `scripts/bench_parallel.py` (reproducible, sin contraseñas, opciones `--engines`, `--rows`, `--workers`, `--repeat`); (b) protocolo para Oracle: 1 tanda de calentamiento descartada, ≥ 5 repeticiones **alternando** serie y paralelo (ABAB) para anular la deriva, mediana e IQR, a 200K y 1M; (c) cambiar la regla solo si la mediana da ≥ 1,5× y los rangos intercuartílicos no se solapan en los dos volúmenes; si no, mantener en serie y actualizar `evidence` y `benchmarks.md` | `fase_media` |

### Rutas afectadas

- D1: `bulk/crud.py` (`__load_partitions`), `bulk/_execution/parallel_loader.py` (`_staging_update_available`, `_plan`).
- D2: `bulk/_execution/parallel_loader.py` (`_run`), `bulk/crud.py` (`__load_partitions`).
- D3: `docs/api/bulk_crud.md`.
- D4: `dump/orchestrator.py` (`_process_table_with_columns`, `_load_in_pk_ranges`, `_plan_pk_ranges`), `docs/api/dump.md`, `DumpConfig.parallel_pk_ranges` (docstring).
- D5: `scripts/bench_parallel.py` (nuevo), `docs/guides/benchmarks.md`, `.ai/runtime.md` (si se documenta el script), y si procede `parallel_planner.py` + `docs/api/bulk_parallel.md`.

### Riesgos de regresión

- D1: que el hecho inyectado quede obsoleto entre la comprobación y la carga (milisegundos): los workers siguen comprobando en su sesión, así que el resultado sigue siendo correcto (como mucho, fila a fila en paralelo hasta el primer lote).
- D2: quien dependa de ese INFO en `ParallelBulkLoader` con `AuditOptions(warn_if_disabled=False)` deja de verlo (es lo que pide la opción).
- D4: cambia la decisión de `"auto"` en tablas con huecos (menos particiones). Es el objetivo; con `collect_row_counts=False` no cambia nada.
- D5: ninguno en código salvo que cambie una regla (entonces cambia la decisión de `"auto"` en Oracle).

### Estrategia de pruebas

- D1: test con engine PostgreSQL simulado (patch de `facts.can_create_temp_tables` con contador): una llamada de la fachada paralela ⇒ la fachada consulta 1 vez y el loader 0.
- D2: `caplog` en una carga paralela de la fachada sin auditoría: sin «Auditoría deshabilitada»; con el loader directo y `warn_if_disabled=True`, el INFO sigue.
- D4: `TestLoadInPkRanges` con `rows_hint` < umbral y rango ≥ 3,5M ⇒ tabla entera; con `rows_hint=-1` ⇒ cota del rango (comportamiento actual).
- D5: el script se ejecuta con `--repeat 1 --engines postgresql` como prueba de humo; resultados a `build/logs/`.
- Puerta: `ruff`, `mypy`, `pytest` (también sin URLs del banco), `tests/integration` de `bulk`/`dump`, `zensical build --strict`.

---

## AUDIT_PLAN

### Riesgos funcionales
- D4 es el único cambio de decisión con datos reales; acotado a destino SQL Server (la única regla `source` que paraleliza).
- D3 se cierra sin código: el riesgo de **implementarlo** (sumar filas a `rows_committed`) sería funcional (reanudaciones incorrectas), por eso se descarta.

### Riesgos técnicos
- D1 introduce un acoplamiento privado fachada → loader dentro de `bulk/` (mismo paquete, sin cambiar capas ni API pública). Alternativa descartada: caché por engine a nivel de módulo (estado global mutable, contra `SHARED_INSTRUCTIONS.md` § «OOP y estado», y quedaría obsoleta tras un `GRANT`).
- D4 usa un `COUNT(*)` ya existente: sin coste extra; `source_rows` puede quedar desfasado si el origen cambia durante el volcado (igual que hoy en el informe).
- D5: el banco comparte máquina con otros contenedores (`postgres_db`, `litellm`): ruido posible; el protocolo ABAB lo mitiga, no lo elimina.

### Riesgos de seguridad
- Ninguno nuevo: sin SQL nuevo (D4 reutiliza `COUNT(*)` existente, D1 reutiliza `facts`). El script de D5 lee la contraseña del entorno (`UTIL_BBDD_BENCH_PASSWORD`), nunca la imprime ni la guarda, como `scripts/bench_bulk.py`.

### Dependencias entre ítems
- D1, D2, D3 y D4 son independientes entre sí (pueden ir en un solo commit `refactor`/`fix` o en uno cada uno).
- D5(b)/(c) dependen de D5(a) (script en el repo). Si D5 cambia la regla de Oracle, actualiza también `docs/api/bulk_parallel.md` y `docs/guides/benchmarks.md`.
- D1 y D2 tocan `__load_partitions`: hacerlos en el mismo grupo para no editar dos veces.

### Simplificaciones posibles
- D1: si se prefiere cero acoplamiento, dejar D1 como está (impacto de milisegundos) y cerrarlo como aceptado.
- D5: hacer solo (a) y medir solo 1M (el volumen donde se decidió la regla).

### Versión
- D1 + D2 + D3 + D4: **PATCH 3.0.1** (sin cambio de API; D4 corrige una sobreestimación).
- D5: sin versión si solo cambia evidencia/documentación; **MINOR 3.1.0** si cambia una regla (cambia la decisión de `"auto"`).

### Veredicto del inventario: `DEUDA_MENOR`
### Veredicto del plan: `GO_CONDICIONAL`

Condiciones:
1. Aprobar D3 como «cerrado sin código» (decisión de diseño documentada).
2. Elegir D1: implementar el traspaso privado (recomendado) o aceptar la deuda.
3. Autorizar en D5 la ejecución de benchmarks en el banco (≈ 15–20 min de Oracle con el protocolo ABAB).
