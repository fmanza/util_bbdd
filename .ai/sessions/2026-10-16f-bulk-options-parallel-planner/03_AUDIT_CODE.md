# AUDIT_CODE — Paquetes de opciones y planificador de paralelismo (v3.0.0)

Alcance: diff de `src/` (18 ficheros, +743/−453), tests nuevos y migrados, documentación. Revisión manual del diff
completo y de los caminos nuevos (fachada paralela, `_plan` del loader, `"auto"` de `dump`).

## Bugs potenciales y casos límite (corregidos en esta fase)

| # | Ubicación | Hallazgo | Corrección | Test |
|---|---|---|---|---|
| A1 | `bulk/crud.py:866` | Dentro de `rejects_scope()` (sin `bulk_session`) la fachada paralelizaba: las particiones no continuaban la secuencia (`row_offset`) ni el presupuesto `max_rejects` del ámbito | En serie dentro de un ámbito (`RejectsCoordinator.scope_active`, nuevo en `_support/rejects.py`) | `test_inside_rejects_scope_stays_serial` |
| A2 | `bulk/crud.py:908` | UPDATE/DELETE por rangos cortan por posición: con PK repetidas en el DataFrame, la misma clave podía quedar en dos particiones (dos hilos sobre la misma fila: espera de lock o deadlock) | Rangos solo si la columna no tiene repetidos (`is_unique`); si no, hash (las claves iguales van juntas) | `test_update_with_repeated_keys_partitions_by_hash` |
| A3 | `dump/orchestrator.py:865` | Con `parallel_pk_ranges="auto"` y un destino que no gana en ningún volumen (MySQL, MariaDB, PostgreSQL, Oracle, sin medición), cada tabla con PK entera hacía un `SELECT MIN/MAX` en el origen para acabar cargándose entera | `_auto_range_ceiling` devuelve 1 si la regla del destino no paraleliza, con un único INFO por volcado (además baja la complejidad cognitiva de `_resolve_range_count`, Sonar S3776) | `test_targets_without_gain_skip_the_ranges_once` |
| A4 | `bulk/_execution/parallel_loader.py:512` | Con `mode="off"` el loader avisaba de un recorte («1 hilos en lugar de N») | Sin aviso con `"off"` (un hilo es lo pedido) | `test_loader_with_mode_off_is_serial_without_logging` |
| A5 | `docs/api/bulk_crud.md` | No se documentaba que, en paralelo, `fila` del CSV de rechazos es la posición en la partición y `max_rejects` es por partición | Documentado, con el criterio rangos/hash | — |

## Edge cases revisados sin cambios

- DataFrame vacío con `parallel`: va a la vía en serie, que da su error habitual (sin cambio de contrato).
- `generar_sql=True` (el valor por defecto de los `*_from_df`): siempre en serie; el usuario debe pasar `generar_sql=False`.
- `ParallelOptions(max_workers=1)` en `BulkCrud`: plan de 1 hilo → serie atómica.
- Recursión worker → paralelo: imposible (`for_worker` quita `parallel`; test `test_workers_get_the_packages_and_never_parallelize`).
- `insert_resolver` compartido entre hilos: las estrategias incluidas no guardan estado por ejecución (T4); documentado.
- `DumpConfig.parallel_pk_ranges` como `bool` o cadena distinta de `"auto"`: `ValueError` al construir.

## Performance

- La fachada paralela particiona con vistas (`iloc`) en INSERT; `RangePartitioner` ordena (copia) en UPDATE/DELETE, como
  hasta ahora en el uso documentado; `is_unique` es O(n) con hash, despreciable frente a la carga.
- Validación en el banco (5 motores): `"auto"` gana 1,55×–2,82× donde paraleliza; ver `02_IMPLEMENT.md`.

## Seguridad

- Sin cambios en el SQL generado ni en la parametrización; `dump` sigue citando identificadores en `MIN/MAX`.
- Rutas de CSV validadas igual que antes (`OptionalPathField`, ahora con etiqueta de paquete); directorio de auditoría
  comprobado en el constructor del loader antes de lanzar hilos (PL-4).
- `retry_on`, `insert_resolver` y `sink` siguen siendo callables/objetos del usuario: mismo nivel de confianza.
- Concurrencia acotada siempre por `pool_capacity` (sin agotamiento del pool).

## Tipado

- `mypy src tests/unit/test_protocol_conformance.py`: limpio (339 ficheros). Los paquetes con ruta no usan `slots`
  (`OptionalPathField` guarda en `__dict__`), igual que `DumpConfig`.

## Deuda técnica (no bloqueante)

| # | Ubicación | Deuda | Motivo para dejarla |
|---|---|---|---|
| D1 | `bulk/crud.py:840` + `parallel_loader.py:524` | El UPDATE paralelo de PostgreSQL desde `BulkCrud` consulta el privilegio `TEMP` dos veces (una conexión más por llamada) | Coste de milisegundos; evitarlo exige pasar el hecho al loader por una vía privada |
| D2 | `parallel_loader.py:422` | Sin auditoría, cada carga paralela de la fachada registra un INFO «Auditoría deshabilitada» además del WARNING único de la instancia | Nivel INFO; se mantiene el contrato M-4 del loader |
| D3 | `bulk/crud.py:965` | Las filas de una carga paralela no suman a `rows_committed` | Decisión: `rows_committed` es la cadencia de la instancia; las filas están en `last_parallel_result` (documentado) |
| D4 | `dump/orchestrator.py:753` | La cota de filas de `"auto"` es `MAX − MIN + 1`: una PK con huecos sobrestima el volumen (solo afecta a SQL Server ≥ 3,5M) | Evita un `COUNT(*)`; documentado |
| D5 | `parallel_planner.py` (reglas de Oracle) | Mediciones de Oracle 23 Free inestables entre tandas | En serie por criterio; memoria `reference-oracle-free-bench-unstable` |

## Validación tras las correcciones

| Comando | Resultado | Log |
|---|---|---|
| `pytest` (shell sin URLs del banco) | 6203 passed, 532 skipped | `build/logs/v3_pytest_audit.txt` |
| `pytest tests/integration` (banco, 6 motores, `JAVA_HOME=jdk-25`) | 589 passed, 7 skipped | `build/logs/v3_integration_audit.txt` |
| `ruff check`, `ruff format --check`, `mypy` | limpios | — |
| `zensical build --strict` | sin avisos | `build/logs/v3_docs_build.txt` |

## Veredicto: `GO`

Sin hallazgos bloqueantes abiertos. Siguiente fase: VERSION (3.0.0).
