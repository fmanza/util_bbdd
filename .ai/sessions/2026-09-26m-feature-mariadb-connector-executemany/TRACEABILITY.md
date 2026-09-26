# TRACEABILITY

## Session metadata
- id: 2026-09-26m-feature-mariadb-connector-executemany
- fecha: 2026-09-26
- rama: develop (base `bfe1127`)
- skill: new-feature (PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION)
- origen: PF-09 (sesión `2026-09-26l-bench-mariadb-connector`); el usuario pidió implementarlo («Hazlo»)

## Prompt issued
```
/new-feature PF-09: en MySQL/MariaDB con MariaDB Connector/Python usar el executemany nativo del driver cuando las
columnas del lote tengan tipo Python uniforme, y la vía multi-fila actual en otro caso. Sin cambios de API; resultado
idéntico; None no rompe la uniformidad; coste despreciable; fallback a multi-fila; verificar fidelidad y medir dump
large; PyMySQL sin cambios; validar UPDATE por staging.
```

## Investigación previa (reglas reales del envío masivo de Connector/Python 1.1.14, MariaDB 11.4)

| Mezcla en una columna | Resultado |
|---|---|
| `Decimal` + `float` | acepta (convierte) |
| `int` + `bool` | acepta |
| `None` delante o detrás | acepta |
| `bytes` + `str` (BLOB) | `ProgrammingError: Invalid parameter type` |
| `int` + `float` | error |
| `datetime` + `date` | error |
| `str` + `int` (VARCHAR) | error |

Los fallos son excepciones, no corrupción silenciosa.

## PLAN / AUDIT_PLAN (veredicto GO)
- `MariaDBConnectorInsertStrategy` (nueva) decide por lote: si cada columna tiene un único tipo exacto sin contar `None` (`_uniform_column_types`), delega en `MySQLDriverExecutemanyStrategy`; si no (o si la sentencia no es un `Insert`), en `MySQLMultiRowInsertStrategy`. Criterio más estricto que el del driver (`Decimal`+`float` y `int`+`bool` van por multi-fila).
- `InsertStrategyResolver`: `mysql`/`mariadb` + `mariadbconnector` → la nueva estrategia; otros drivers (p. ej. `mysqlconnector`, `mysqldb`) siguen en multi-fila; PyMySQL y el override `mysql_strategy` sin cambios.
- Sin cambios de API. Ambas vías insertan los mismos valores sin procesadores de tipo de SQLAlchemy (como ya hacía la vía multi-fila con `text()`).

## IMPLEMENT
- `bulk/_execution/batch.py`: `MariaDBConnectorInsertStrategy`, `_uniform_column_types`, rama en `InsertStrategyResolver` y su docstring.
- `docs/api/bulk-crud.md` y `docs/guides/benchmarks.md`: estrategia por driver.
- `CHANGELOG.md`: *Changed* (rendimiento).

## Validación
- **Tests** (`tests/unit/bulk/test_insert_strategies.py`): el resolvedor lleva `mariadbconnector` a la nueva estrategia y otros drivers a multi-fila (el test anterior `test_mysql_family_routes_to_multirow` fijaba el comportamiento antiguo y se sustituye); tipos uniformes (incluido `None`) → driver; `bytes`+`str`, `int`+`float`, `int`+`bool` → multi-fila; `Update` → multi-fila.
- **Calidad**: `ruff format` + `ruff check` limpios; `mypy src` limpio; `pytest tests/unit`: **4569 passed**.
- **MariaDB real con Connector/Python**:
  - round-trip exacto de PD-05 (BIGINT ±(2^63−1) y 2^53+1 con NULL, DECIMAL(38,10), cadenas con espacios), ahora por la vía del driver;
  - `BulkCrud` INSERT uniforme → vía del driver, datos correctos; INSERT con `bytes`+`str` en un BLOB → también vía del driver, porque `restore_binary_values` (P-21) ya convierte el `str` a `bytes` antes de la estrategia (mismo dato que la vía multi-fila, `b'texto'`);
  - UPDATE por staging (carga la tabla temporal con esta estrategia): correcto con BD por defecto en la URL. Sin BD por defecto y tabla `esquema.tabla` falla con `No database selected` **también con PyMySQL**: fallo previo e independiente, registrado como **PD-12**.
- **A/B intercalado, `dump` `large` con Connector/Python** (`ab_antes/`, `ab_despues/`):

| | Total | `read` | `write` | RSS pico | Verificación |
|---|---|---|---|---|---|
| Sin PF-09 | 75,0 · 85,0 s | 4,0 · 6,2 s | 67,7 · 77,0 s | 192 MB | 2/2 |
| Con PF-09 | **24,5 · 33,6 s** | 4,2 · 10,2 s | **16,9 · 24,5 s** | 158 MB | 2/2 |

  Media 80,0 → 29,1 s (**−64 %**); más rápido que PyMySQL (≈ 38 s).
- **PyMySQL (control)**: sin cambio de código en su ruta (test del resolvedor). La primera medición tras las de Connector/Python salió en 81,5 s y otra en 55,4 s; la siguiente, **38,0 s** (`control_pymysql/`), su valor habitual. Patrón observado varias veces en la sesión: la primera medición de MariaDB/MySQL tras otra carga pesada sale lenta.

## AUDIT_CODE
- **Coste de la comprobación**: un recorrido por columna y lote en Python (conjunto de tipos); no aparece en el tiempo total (la escritura baja de 70 a 17–25 s).
- **Edge cases**: columna toda `None` → uniforme; lote vacío → multi-fila (no hace nada); tipos numpy (`np.int64`) cuentan como tipo distinto de `int` si se mezclan → multi-fila; subclases (`pd.Timestamp` frente a `datetime`) → multi-fila (criterio de tipo exacto).
- **Seguridad**: identificadores con `identifier_preparer`, valores como parámetros `?` (misma SQL que `MySQLDriverExecutemanyStrategy`).
- **Compatibilidad**: sin cambios de API; resultado idéntico al de la vía multi-fila.

## VERSION
- Commit: `feat(bulk): executemany del driver con MariaDB Connector/Python si los tipos del lote son uniformes (PF-09)`
- Rollback: `git revert <commit>`.

## Directrices para Futuras IAs
- **[bulk/mariadb]**: con `mariadbconnector`, el lote va por el `executemany` del driver solo si cada columna tiene un único tipo exacto; no relajes el criterio sin probar con el driver real (sus errores dependen de la combinación de tipos).
- **[bench]**: tras una carga pesada en otro motor o driver, descarta la primera medición de MariaDB/MySQL o repite.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- PD-12: UPDATE por staging en MySQL/MariaDB sin BD por defecto y tabla `esquema.tabla`.
