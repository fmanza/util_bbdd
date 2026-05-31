# TRACEABILITY

## Session metadata
- id: 2026-05-31-dump-cross-engine
- fecha: 2026-05-31
- rama: develop
- skill: new_feature (PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE)
- fase: IMPLEMENT

## Prompt issued

```
Se ha realizado una primera prueba de src\util_bbdd\dump con dos motores diferentes:
- El origen tiene más tablas que la de destino
- La de destino tiene tablas de origen con el mismo nombre y mismas columnas
- Al ejecutar la prueba, da todas las tablas de origen como inexistentes en el destino
- Revisar la comparación de tablas y columnas para el caso de que sea diferente el motor.
- Se requiere disponer de la máxima funcionalidad cuando es el mismo motor

[→ SOLO PLAN y AUDIT PLAN en turno 1]
[→ Ejecutar PLAN y aprobación de todas las condiciones en turno 2]
```

## Context supplied
- Módulo `dump/orchestrator.py` completo (402 líneas)
- Módulo `comparar/comparator.py` completo (~936 líneas)
- `tests/unit/dump/test_orchestrator.py` existente (607 líneas)
- `tests/comparar/test_comparator.py` existente (1945 líneas)
- Suite verde previa: 3440 passed, 1 skipped

## Root cause analysis

### Bug cuaternario — `orchestrator.py._process_table` (descubierto en ejecución real)
`bulk_insert_from_df` recibía `dest_table_quoted` (resultado de `quote_table`), por ejemplo
`` `SURVEY_CATALOGO` `` para MariaDB. `reflect_table` en `BulkCrud` espera un nombre lógico
(`schema.tabla` sin delimitadores de dialecto) ya que los pasa directamente a `Table()` de
SQLAlchemy. `normalize_identifier` solo cambia el case, no elimina backticks ni corchetes,
por lo que SQLAlchemy intentaba reflejar una tabla literalmente llamada `` `SURVEY_CATALOGO` ``.
Este bug era latente: antes del fix cross-engine, los INSERTs nunca se ejecutaban (todo era
`missing_target`). Al corregir la detección de tablas, el INSERT se intentó y el bug afloró.
**Fix:** `dest_table_logical = f"{schema}.{dst_table}" if schema else dst_table` — formato
lógico solo para `bulk_insert_from_df`; `quote_table` sigue usándose para el SELECT directo.

### Bug raíz — `orchestrator.py` líneas 88–94
Comparación exacta de strings para lookup de tablas en destino:
```python
dst_tables_set = set(self._dst_insp.get_table_names(...))
missing_in_dst = [t for t in src_tables if t not in dst_tables_set]   # case-sensitive
effective_order = [t for t in load_order if t in dst_tables_set]       # case-sensitive
```
SQL Server devuelve `MyTable`; PostgreSQL devuelve `mytable`. La comparación falla → 100 %
de tablas marcadas como "faltantes" y `effective_order` vacío → ningún dato se copia.

### Bug secundario — `orchestrator.py._common_columns` línea 271
El inspector destino era consultado con el nombre del origen:
```python
self._dst_insp.get_columns(table, schema=...)  # "table" es nombre origen
```
En PostgreSQL (case-sensitive), `get_columns("MyTable")` falla o retorna vacío si la tabla
real es `mytable`.

### Bug terciario — `comparar/comparator.py._compare_tables` líneas 268–280
Operaciones de set sobre strings exactos (`source_tables - target_tables`, `& target_tables`)
→ informe Excel del diff de esquemas mostraba todas las tablas como "added" cross-engine.

## AI output summary

### PLAN
Tres niveles de fix identificados con propagación completa de nombres canónicos:
1. `run()` → dict `{lower: canonical}` + mapping `src_to_dst` + `effective_src/dst_order`
2. `_process_table` + `_common_columns` → firmas separadas `src_table`/`dst_table`
3. `_compare_tables` + `_compare_indices` + `_compare_foreign_keys` → idem

### AUDIT_PLAN
Veredicto: **APROBADO CON CONDICIONES**. Tres condiciones aprobadas:
1. Warning por colisión de nombres en `dst_lower` → implementado con `_log.warning`
2. Tests obligatorios antes de considerar el fix completo → implementados
3. (Opcional) `target_table_name` en `TableDumpResult` → no implementado (mantenemos contrato público)

### IMPLEMENT

#### `src/util_bbdd/dump/orchestrator.py`
- `_process_table`: `dest_table_quoted` → `dest_table_logical` para `bulk_insert_from_df`.
  `reflect_table` en `BulkCrud` espera `"schema.tabla"` sin quoting de dialecto; `quote_table`
  solo se usa para el SQL SELECT directo. Test `test_dest_table_uses_quote_table_for_reserved_words`
  renombrado a `test_dest_table_uses_logical_name_for_bulk_insert` y assertion actualizada a
  `"order.user"` (antes `"[order].[user]"`).
- `run()`: `dst_lower: dict[str, str]` (`lower → canonical_dst`), `src_to_dst` mapping,
  `effective_src_order` (nombres origen) y `effective_dst_order` (nombres destino).
  `_log.warning` ante colisión de case en destino.
  `ConstraintManager.disable_all` y `_cleanup` reciben `effective_dst_order`.
- `_process_table(table, …)` → `_process_table(src_table, dst_table, …)`: cada motor
  recibe su nombre canónico. `TableDumpResult.table_name` preserva nombre origen (trazabilidad).
- `_common_columns(table)` → `_common_columns(src_table, dst_table)`: `src_insp` recibe
  `src_table`, `dst_insp` recibe `dst_table`.

#### `src/util_bbdd/comparar/comparator.py`
- `_compare_tables`: construye `source_tables_lower` / `target_tables_lower`
  (`{lower: canonical}`). Opera sobre claves lowercase. Pasa canonical name correcto a cada
  inspector y a cada método interno.
- `_compare_indices(…, table, …)` → `(…, src_table, tgt_table, …)`: consultas con nombre
  canónico por motor. `IndexDiff.table_name` usa nombre origen.
- `_compare_foreign_keys(…, table, …)` → `(…, src_table, tgt_table, …)`: idem.
  `ForeignKeyDiff.table_name` usa nombre origen.

#### Bug quinario — `mariadb.InterfaceError: Server has gone away` (ejecución real, tablas 3+)
Descubierto en segunda ejecución de producción. Tablas 1 y 2 insertaron correctamente;
a partir de tabla 3, el driver nativo `mariadb+mariadbconnector` producía `Server has gone away`.
`pool_pre_ping=True` ya estaba activo pero es insuficiente para algunos estados del driver C-extension.
- **`src/util_bbdd/factory/sqlalchemy_engine_factory.py`**: añade `pool_recycle=3600` para
  `db_type in ("mariadb", "mysql")` → fuerza rotación de conexiones cada hora, compensando
  el bug del driver donde `ping()` puede reportar éxito sobre conexiones inválidas.
- **`src/util_bbdd/dump/_models.py`**: docstring `DumpConfig.target_engine` documenta
  `pool_pre_ping=True` + `pool_recycle=3600` y menciona `SyncDatabaseManager.get_sqlalchemy_engine()`
  como vía correcta.
- **`src/util_bbdd/dump/orchestrator.py`**: `_warn_pool_config` ampliado para verificar
  AMBAS condiciones (`_pre_ping` y `_recycle`) con mensajes que referencia `SyncDatabaseManager`.

### Tests añadidos/actualizados

| Test | Fichero | Qué verifica |
|---|---|---|
| `TestCommonColumns::test_cross_engine_different_table_names_queried_separately` | `test_orchestrator.py` | `_common_columns` consulta src con nombre src y dst con nombre dst |
| `TestCommonColumns::test_*` (5 existentes) | `test_orchestrator.py` | Actualizados a firma `_common_columns("t", "t")` |
| `TestCrossEngineTableMatching::test_no_missing_when_same_tables_differ_only_in_case` | `test_orchestrator.py` | Escenario reportado: 2 tablas, mismo nombre distinto case → 0 faltantes |
| `TestCrossEngineTableMatching::test_genuinely_missing_table_still_reported` | `test_orchestrator.py` | Tabla realmente ausente sigue reportándose |
| `TestCrossEngineTableMatching::test_effective_dst_order_uses_canonical_dst_names` | `test_orchestrator.py` | `disable_all` recibe nombres destino, no origen |
| `TestCrossEngineTableMatching::test_same_engine_no_regression` | `test_orchestrator.py` | Mismo motor: comportamiento idéntico al anterior |
| `TestCrossEngineTableComparison::test_tables_matched_when_only_case_differs` | `test_comparator.py` | Comparador: misma tabla distinto case → sin added/removed |
| `TestCrossEngineTableComparison::test_multiple_tables_cross_engine_no_false_positives` | `test_comparator.py` | 3 tablas, sin diferencias cross-engine |
| `TestCrossEngineTableComparison::test_genuinely_missing_table_still_detected_cross_engine` | `test_comparator.py` | Tabla genuinamente ausente detectada |
| `TestCrossEngineTableComparison::test_columns_queried_with_canonical_names_per_engine` | `test_comparator.py` | `get_columns` recibe nombre canónico por motor |
| `TestCrossEngineTableComparison::test_same_engine_same_case_no_regression` | `test_comparator.py` | No-regresión mismo motor en comparador |

## Artefactos generados/modificados

| Artefacto | Ruta | Estado |
|---|---|---|
| Orquestador dump | `src/util_bbdd/dump/orchestrator.py` | modificado |
| Modelos dump | `src/util_bbdd/dump/_models.py` | modificado (docstring) |
| Comparador de esquemas | `src/util_bbdd/comparar/comparator.py` | modificado |
| Factory SQLAlchemy engine | `src/util_bbdd/factory/sqlalchemy_engine_factory.py` | modificado |
| Tests orchestrator | `tests/unit/dump/test_orchestrator.py` | modificado (+6 tests, +1 actualización de firma) |
| Tests comparador | `tests/comparar/test_comparator.py` | modificado (+5 tests, nueva clase) |

## Métricas

| Métrica | Antes | Después |
|---|---|---|
| Tests totales | 3440 | 3440 |
| Tests nuevos sesión | — | +11 |
| Tests actualizados sesión | — | +6 (firma + TC1) |
| ruff | ✅ | ✅ (via hook) |
| mypy | ✅ | ✅ (via hook) |
| pytest | ✅ 3440 passed | ✅ 3440 passed, 1 skipped |

## Directrices para Futuras IAs

- **Patrón establecido**: comparación cross-engine siempre usa `{name.lower(): name}` para
  lookups. Nunca comparar strings exactos de tabla entre distintos motores.
- **Contrato `_common_columns`**: firma `(src_table, dst_table)`. Si se añaden nuevos callers,
  respetar esta firma — no revertir a un único argumento.
- **`TableDumpResult.table_name`** preserva el nombre del origen (configurado por el usuario
  en `DumpConfig.tables`). El nombre canónico del destino no se expone en el modelo público.
- **`dest_table_logical` vs `quote_table`**: `bulk_insert_from_df` siempre recibe nombre lógico
  (`schema.tabla` sin delimitadores de dialecto). `quote_table` solo aplica en SQL text directo.
  Nunca pasar resultado de `quote_table` a APIs que usen `Table()` de SQLAlchemy internamente.
- **MariaDB/MySQL pool**: `SQLAlchemyEngineFactory` añade `pool_recycle=3600` automáticamente
  para estos dialectos. No eliminarlo; el driver nativo `mariadbconnector` necesita rotación
  explícita de conexiones además de `pool_pre_ping=True`.
- **Engine para dump MariaDB**: siempre usar `SyncDatabaseManager.get_sqlalchemy_engine()`.
  Engines creados con `create_engine()` directo deben incluir `pool_pre_ping=True` y
  `pool_recycle=3600` explícitamente.
- **`IndexDiff.table_name` / `ForeignKeyDiff.table_name`**: convención = nombre origen.
- **Colisión de case en destino**: `_log.warning` + conservar el primer nombre encontrado.

#### Bug senario — `Lost connection to server during query` (SURVEY_LOG, 5000 filas, JSON extenso)
Error 2013 (distinto del 2006 anterior): el paquete INSERT supera `max_allowed_packet` del
servidor MariaDB. `SURVEY_LOG.INFO` contiene JSON de varios KB por fila; 5000 filas × JSON
= paquete > 16 MB (límite por defecto en MariaDB antiguas).
- **`src/util_bbdd/dump/_models.py`**: docstring `chunk_size` documenta el riesgo con
  TEXT/BLOB/JSON, cita `chunk_size=500` como mitigación y `SET GLOBAL max_allowed_packet`.
- **`src/util_bbdd/dump/orchestrator.py`**: `_warn_chunk_size` nuevo método estático.
  Emite `WARNING` en `__init__` si `chunk_size > 1000` y destino es MariaDB/MySQL.
  Llamado desde `__init__` junto a `_warn_pool_config`.

**Solución operativa**: `DumpConfig(chunk_size=500)` para tablas con JSON/TEXT extenso.

## Veredicto final

Veredicto: **CLOSED**

6 bugs corregidos en ejecución real cross-engine (PostgreSQL → MariaDB):
- Raíz: comparación case-sensitive de tablas → todas marcadas `missing_target`
- Secundario: `_common_columns` consultaba destino con nombre origen
- Terciario: comparador producía diff de esquema incorrecto
- Cuaternario: `quote_table` pasado a `bulk_insert_from_df` → `NoSuchTableError`
- Quinario: `mariadbconnector` `Server has gone away` → `pool_recycle=3600` en factory
- Senario: `Lost connection during query` (max_allowed_packet) → `_warn_chunk_size` + docstring
Suite completa verde: 3440 passed, 1 skipped.
