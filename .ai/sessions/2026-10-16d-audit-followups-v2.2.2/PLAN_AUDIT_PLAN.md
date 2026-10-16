# PLAN + AUDIT_PLAN — pendientes de la auditoría de v2.2.2

- Sesión: `2026-10-16d-audit-followups-v2.2.2` · rama `develop` (base `252fe00f`, tag `v2.2.2`)
- Origen: residuos del `/audit-code` de `.ai/sessions/2026-10-16c-sonarlint-cleanup/` (hipótesis H1, H2; tests
  sugeridos) y los avisos de SonarLint que quedaron fuera (literal `"CURRENT_TIMESTAMP"`, `_rejected_optional_param`
  duplicado).
- Estado: **aprobado** («si»: D1–D6 con las opciones recomendadas) e implementado en v2.2.3.

## PLAN

### A1 — `fix(analysis)`: la precarga de Graphviz puede bloquearse para siempre (confirmado por lectura)

**Evidencia.** `GraphvizRelationshipGraphExt.prefetch` crea un `Future` por grafo
([graphviz_ext.py:794](../../../src/util_bbdd/analysis/graphviz_ext.py#L794)) y reparte los lotes con
`executor.map(self._render_batch, ...)`. `_render_batch` solo captura `OSError` en la fase del lote
([graphviz_ext.py:830](../../../src/util_bbdd/analysis/graphviz_ext.py#L830)); cualquier otra excepción (p. ej.
`UnicodeEncodeError`, que es `ValueError`, al escribir el `.gv` con `dot.encoding`, o el `ImportError` añadido en
v2.2.2 en la línea 813) sale antes de resolver los `Future` de **ese** lote. `prefetch` propaga la excepción, pero los
`Future` pendientes siguen en `self._prefetched`: la siguiente llamada que pida ese grafo ejecuta
`prefetched.result()` sin timeout ([graphviz_ext.py:871](../../../src/util_bbdd/analysis/graphviz_ext.py#L871)) y se
bloquea.

**Cambio.** En `_render_batch`:

1. la fase del lote captura `Exception` (no solo `OSError`) y, como hoy, cae al render grafo a grafo con `dot.pipe`,
   que guarda en cada `Future` el resultado o la excepción exacta de una llamada sin precarga (es el contrato del
   docstring);
2. el `graphviz is None` deja de lanzar: resuelve los `Future` del lote con `ImportError(GRAPHVIZ_MISSING_MSG)` y
   vuelve (Pylance sigue estrechando el tipo);
3. un `try/finally` final garantiza que ningún `Future` del lote queda sin resolver (`set_exception` con el error que
   interrumpió el bucle).

**Tests** (`tests/unit/analysis/`, sin Graphviz real: `dot` simulado como en los tests de precarga existentes):
`Path.write_text` que lanza `ValueError` → `prefetch` termina y la llamada real devuelve el `dot.pipe`; un `dot.pipe`
que lanza → la llamada real recibe esa excepción, sin bloqueo (`future.done()` antes de pedir el resultado).

### A2 — `test(migrate)`: casos de `_strip_pg_cast`

Los casos del fuzz de la sesión anterior (no versionado) como tests en el fichero de tests de `default_normalizer`:
`'x'::character varying(30)`, `'0'::numeric( 10 , 2 )`, `'{}'::text[][]`, `'a'::"MyType"`, `'a::b'` (sin cast: se
queda igual), `'a::b'::text` → `'a::b'`, `('x'::text)::character varying` (cast encadenado), `nextval('s'::regclass)`
(sin cambios) y `'0'::numeric(,)` (decisión de v2.2.2: se quita). Sin cambio de código.

### A3 — `refactor(migrate)`: literal `"CURRENT_TIMESTAMP"` (SonarLint S1192)

- `migrate/_compat/default_normalizer.py`: 5 apariciones (4 conjuntos + el `return` de la forma canónica) →
  constante `_CURRENT_TIMESTAMP`.
- `migrate/emitters/mariadb.py` (líneas 497 y 513, seleccionada en el IDE): `_with_timestamp_precision` y
  `_format_default` → constante del módulo.
- Los demás emitters (`oracle`, `postgresql`, `sqlserver`) tienen una sola aparición: no se tocan.

### A4 — `refactor(connection)`: `_rejected_optional_param` duplicado

Las dos copias ([connection_mariadb.py:95](../../../src/util_bbdd/connection/mariadb/connection_mariadb.py#L95),
[pool_connection_mariadb.py:163](../../../src/util_bbdd/connection/mariadb/pool_connection_mariadb.py#L163)) solo
difieren en el conjunto (`_OPTIONAL_CONN_PARAMS` / `_OPTIONAL_POOL_PARAMS`, hoy ambos `{"init_command"}`). Una sola
función `rejected_optional_param(err, optional)` en `connection_mariadb.py`, que el pool importa (el pool ya importa
de `..params`; `connection_mariadb` no importa el pool: sin ciclo).

### A5 — H2: doble ERROR al fallar una conexión (confirmado, previo a v2.2.2)

`MariaDBConnection.connect` (y las otras 13) registran el fallo y lanzan `ConnectionError`; el manager lo vuelve a
registrar ([_manager_lifecycle_sync.py:129](../../../src/util_bbdd/managers/_manager_lifecycle_sync.py#L129),
[sync_mgr.py:163](../../../src/util_bbdd/managers/sync_mgr.py#L163)). Eran dos líneas ERROR antes de v2.2.2; ahora la
primera lleva traceback. Ver D4.

### A6 — `test(migrate)`: destinos de vistas sincronizados con el planner

`_transpile_view` lanza `KeyError` con un destino sin dialecto de sqlglot; no es alcanzable desde la API porque
`MigrationPlanner` valida `_SUPPORTED_TARGET` ([planner.py:53](../../../src/util_bbdd/migrate/planner.py#L53)) y ese
conjunto coincide hoy con las claves de `SQLGLOT_DIALECT`
([_dialects.py:13](../../../src/util_bbdd/migrate/views/_dialects.py#L13)). Test que fija
`_SUPPORTED_TARGET <= set(SQLGLOT_DIALECT)` (y lo mismo para el origen): si se añade un motor al planner sin dialecto,
falla el test en lugar de un `KeyError` en producción. Sin cambio de código.

### Fuera de alcance

- Comparación antes/después de vistas como test versionado (JSON de referencia): ver D6.
- Otros avisos de SonarLint no pegados todavía.

### Versión

Con A1: `v2.2.3` (PATCH, `fix`). Sin A1: los demás puntos son `refactor`/`test` y pueden esperar a la siguiente
versión.

## AUDIT_PLAN

| Punto | Riesgo funcional | Riesgo técnico | Mitigación / verificación |
|---|---|---|---|
| A1 | Capturar `Exception` en el lote podría ocultar un fallo del lote; no lo oculta: cada grafo se renderiza solo y su `Future` lleva la excepción real de `dot.pipe` | `KeyboardInterrupt`/`SystemExit` no deben convertirse en resultado: el `finally` los propaga tras resolver los `Future` | 2 tests nuevos; tests de precarga existentes; `pytest -k graphviz`; documentación con grafos en el banco (`doc` usa la precarga) |
| A2 | Ninguno (solo tests) | El caso `numeric(,)` fija una decisión de v2.2.2 | — |
| A3 | Ninguno: mismo texto en los mismos sitios | — | Comparación antes/después de `normalize_default` y de los DEFAULT emitidos por MariaDB con los tests de `migrate` |
| A4 | Ninguno: misma regex y mismos conjuntos | Import nuevo `pool → connection_mariadb` dentro del mismo paquete | `pytest -k mariadb`; `gen_arquitectura_capas.py` (mismo paquete: no cambia el diagrama) |
| A5 | Según D4 | Cambiar el nivel en managers afecta a todos los motores | Solo si D4 = (b) |
| A6 | Ninguno | — | — |

**Seguridad:** A1 no cambia qué se escribe en disco (directorio temporal propio) ni los argumentos de `dot`; A5 no
añade datos a los logs (el traceback no incluye variables locales).

**Puerta de cierre:** `ruff check` + `ruff format --check` (`src tests`), `mypy src tests/unit/test_protocol_conformance.py`,
`pytest` sin URLs del banco y con los 6 motores, `zensical build --strict`; `/version-closure` si hay versión.

## Decisiones del usuario

| ID | Pregunta | Opciones | Recomendada |
|---|---|---|---|
| D1 | ¿Corregir A1 (bloqueo de la precarga de Graphviz)? | (a) sí, `v2.2.3`; (b) no | **(a)** |
| D2 | ¿Alcance del resto? | (a) A2 + A3 + A4 + A6; (b) solo tests (A2 + A6); (c) nada más | **(a)** |
| D3 | A3: ¿constante por fichero o compartida? | (a) por fichero; (b) una sola en `_compat/default_normalizer.py` importada por el emitter | **(a)**: es un literal SQL, no lógica compartida |
| D4 | A5 (doble ERROR) | (a) dejarlo; (b) el manager baja su línea a DEBUG cuando la causa es `ConnectionError` | **(a)**: ya existía antes de v2.2.2 y cambiarlo afecta a los 7 motores |
| D5 | ¿Commits, tag y push al terminar? | (a) sí, como en v2.2.2; (b) solo commits locales | **(a)** si D1 = (a) |
| D6 | ¿Versionar la comparación antes/después de vistas como test (JSON de referencia de ~1000 casos)? | (a) no; (b) sí | **(a)**: un JSON grande que cambia con cada mejora de sqlglot; los 2590 tests y los e2e ya cubren la salida |

## Veredicto del AUDIT_PLAN

`GO_CONDICIONAL`: el plan se puede ejecutar tal cual con las opciones recomendadas; A1 es el único cambio de
comportamiento y tiene tests que reproducen el bloqueo antes del arreglo.
