# TRACEABILITY

## Session metadata
- id: 2026-06-01b-dump-skip-schema-comparison
- fecha: 2026-06-01
- rama: develop
- skill: new_feature (perf)
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued

```
Cuando se hace inserciones solo con el módulo src\util_bbdd\dump los tiempos de inserción
son mucho más cortos que cuando se usan atraves de src\util_bbdd\comparar.
Revisar, se necesita que los tiempos sean muy pequeños, buscar optimizaciones.
```

Decisiones del usuario (AskUserQuestion): **Enfoque = eliminar la comparación del dump**;
**Alcance = implementar y verificar**.

## Context supplied
- `src/util_bbdd/dump/orchestrator.py`, `src/util_bbdd/comparar/comparator.py`
- `src/util_bbdd/bulk/crud.py`, `src/util_bbdd/bulk/_execution/batch.py`
- `src/util_bbdd/dump/_models.py`, `src/util_bbdd/dump/reporters.py`, `src/util_bbdd/dump/__init__.py`
- `.ai/sessions/2026-05-31-perf-bulk-dump/` y `2026-05-31-dump-performance/` (optimizaciones previas)
- `tests/unit/dump/test_orchestrator.py`, `tests/unit/dump/test_reporters.py`
- Suite verde previa (subconjunto dump+comparar: 375 passed)

## Análisis de cuello de botella

El hot-path de inserción ya estaba optimizado (sesiones 2026-05-31). El sobrecoste de ir
"a través de comparar" estaba en la **FASE 1** de `DumpOrchestrator.run()`:

```python
diff = SchemaComparator().compare(self._src_insp, self._dst_insp, ..., include_routines=False)
```

- Se ejecutaba **siempre, antes del primer INSERT**, con índices + FKs de destino + comentarios + vistas.
- El propio docstring de `compare()` estima **~500 queries de introspección para 100 tablas**.
- En BD remotas (Oracle/SQL Server/PostgreSQL) son cientos de round-trips secuenciales fijos:
  domina el tiempo total cuando hay muchas tablas y pocas filas por tabla.
- **El `diff` resultante se consumía en un único punto**: `DumpReporter._sheet_missing_columns`,
  que solo extrae las columnas con `attribute=="existence"` y `source_value=="exists"` (presentes en
  origen, ausentes en destino).
- Esa información **ya se calcula durante la carga**: `DumpOrchestrator._common_columns` devuelve
  `skipped` (columnas de origen ausentes en destino) → `TableDumpResult.skipped_columns`.

Conclusión: la comparación de esquemas completa es overhead casi puro para el volcado de datos;
toda la introspección de índices/FKs-destino/comentarios/vistas ni siquiera aparece en el informe.

## AI output summary

### PLAN + AUDIT_PLAN
- Verificado que `diff` solo se referencia en `run()` (creación) y en la llamada al reporter.
- Verificada la equivalencia `skipped_columns` ↔ existence-diffs (`source_value=="exists"`) para
  tablas presentes en ambos esquemas; las tablas solo-origen son `missing_target` con `skipped=[]`
  (equivalente a `td.status != "added"` que el reporter ya filtraba).
- Confirmado que la columna 3 del informe («Valor/Tipo en Origen») mostraba la cadena fija `"exists"`,
  reproducible sin el `diff`.

### IMPLEMENT

#### `src/util_bbdd/dump/orchestrator.py`
- Eliminada la FASE 1 (`SchemaComparator().compare(...)`) y el import `from util_bbdd.comparar import ...`.
- Llamada al reporter sin `diff=diff`.
- Docstring del módulo actualizado (6→5 fases) + nota de rendimiento; fases renumeradas
  (1: análisis, 2: deshabilitar, 3: limpieza, 4: carga, 5a: PK sync, 5b: informe).

#### `src/util_bbdd/dump/reporters.py`
- `generate()` elimina el parámetro `diff: SchemaDiff`; eliminado el import de `SchemaDiff`.
- `_sheet_missing_columns(wb, table_results)` construye las filas desde
  `table_results[*].skipped_columns` en lugar de `diff.table_diffs`. Salida idéntica.

#### Tests
- `tests/unit/dump/test_orchestrator.py`: retirados 13 `@patch(".../SchemaComparator")` y sus
  `mock_comparator`/`mock_cmp` (decorador siempre superior, parámetro siempre último → reemplazo dirigido).
- `tests/unit/dump/test_reporters.py`: eliminados helper `_make_diff` e imports de `comparar`;
  `TestMissingColumnsSheet` reescrito para alimentarse de `skipped_columns`.

### Tests añadidos (2 nuevos)

| Test | Fichero | Qué verifica |
|---|---|---|
| `test_orchestrator_module_does_not_reference_schema_comparator` | `test_orchestrator.py` | `orchestrator` no expone `SchemaComparator`/`SchemaDiff` (regresión perf) |
| `test_report_built_from_skipped_columns_without_diff` | `test_orchestrator.py` | `generate()` se llama sin `diff`; la columna omitida llega vía `skipped_columns` |

### AUDIT_CODE / verificación
- `ruff format` (3 ficheros reformateados) + `ruff check src tests` → **All checks passed**.
- `mypy` sobre `orchestrator.py` y `reporters.py` → **sin errores propios**.
- `pytest` completo → **3601 passed, 1 skipped**.

### DOCS
- `docs/functional/dump-data-export.md`: «Fase 1 — Inspección» → «Introspección» (sin `SchemaDiff`); nodo Mermaid.
- `docs/api/dump.md`: firma de `DumpReporter.generate()` sin `diff`; nota hoja desde `skipped_columns`; «Ver también» depurado.
- `CHANGELOG.md`: entrada en `[Unreleased] · Performance` con el BREAKING CHANGE de `generate()`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| DumpOrchestrator | `src/util_bbdd/dump/orchestrator.py` | modificado |
| DumpReporter | `src/util_bbdd/dump/reporters.py` | modificado |
| Tests orchestrator | `tests/unit/dump/test_orchestrator.py` | modificado (+2 tests, clase `TestSchemaComparisonRemoved`) |
| Tests reporters | `tests/unit/dump/test_reporters.py` | modificado (`TestMissingColumnsSheet` reescrito) |
| Doc funcional dump | `docs/functional/dump-data-export.md` | modificado |
| Doc API dump | `docs/api/dump.md` | modificado |
| Changelog | `CHANGELOG.md` | modificado |

## Métricas

| Métrica | Antes | Después |
|---|---|---|
| pytest | verde (3604 en sesión previa) | ✅ 3601 passed, 1 skipped |
| ruff | ✅ | ✅ |
| mypy (archivos de la sesión) | ✅ | ✅ |
| Round-trips de introspección previos al INSERT | ~10·N (N tablas) + vistas | 0 (solo introspección de carga) |

## Directrices para Futuras IAs

- **[dump/orchestrator]**: El volcado **no** debe ejecutar `SchemaComparator`. Reintroducirlo
  devuelve la cascada N+1 de introspección (índices, FKs de destino, comentarios, vistas) previa
  al primer INSERT. El test `test_orchestrator_module_does_not_reference_schema_comparator` lo protege.
- **[dump/reporters]**: La hoja «Columnas Inexistentes» se deriva de `TableDumpResult.skipped_columns`
  (calculado en `DumpOrchestrator._common_columns`), no de un `SchemaDiff`. `DumpReporter.generate()`
  ya **no** acepta `diff` (BREAKING para llamadas directas a `DumpReporter`).
- **[equivalencia skipped_columns]**: `skipped_columns` ≡ existence-diffs `source_value=="exists"` para
  tablas presentes en ambos esquemas. Las tablas solo-origen llegan como `missing_target` con
  `skipped_columns=[]`, por lo que no generan filas (equivale al antiguo filtro `td.status != "added"`).
- **[deuda preexistente — fuera de alcance]**: `bulk/_support/pk_sync.py:275,351` arrastran 2 errores
  `mypy [arg-type]` (`status: str` vs `Literal[...]`) ajenos a esta sesión; visibles al correr
  `mypy src`. No corregidos aquí para no mezclar dominios.
- **[perf dump]**: Tras esta sesión, el coste de un volcado se acerca al de una inserción directa con
  `bulk`; las optimizaciones pendientes anotadas siguen siendo `COPY FROM STDIN` (PostgreSQL) y
  `executemany` multi-row MariaDB (ver sesión `2026-05-31-perf-bulk-dump`).

## Veredicto final
Veredicto: GO
Pendientes al cierre:
- Commit en `develop` (mensaje preparado; pendiente de ejecución por el usuario).
- Opcional: corregir los 2 errores mypy preexistentes en `bulk/_support/pk_sync.py` en un cambio aparte.
