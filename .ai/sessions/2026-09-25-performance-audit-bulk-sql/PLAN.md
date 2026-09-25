# PLAN — Serialización SQL de bulk (P0 + P1 del roadmap)

<!-- arquetipo: informativo-libre -->

- **Origen**: [`.ai/audit/audit_report_bulk_sql_serialization_20260925.md`](../../audit/audit_report_bulk_sql_serialization_20260925.md),
  [`.ai/audit/optimization_roadmap_bulk_sql_serialization.md`](../../audit/optimization_roadmap_bulk_sql_serialization.md)
- **Flujo de implementación**: `/refactor` (sin cambio funcional: salida byte-idéntica)
- **Baseline (SQLite, 1M filas, `generar_sql=True`)**: INSERT 11,60 s · UPDATE 11,89 s · DELETE 2,16 s
- **Objetivo**: INSERT ≤ 7,5 s en SQLite; render ≤ 5,5 µs/fila en sqlite/oracle/mssql y ≤ 7,5 µs/fila en PG/MySQL

## Fuera de alcance (decidido)

| Elemento | Motivo | Destino |
|---|---|---|
| P-30 (binarios no UTF-8 por plantilla) + C-1 (`0x…` inválido en PG/Oracle/SQLite) | Cambian la salida; C-1 es de corrección, no de rendimiento | `/hotfix` aparte, los dos juntos |
| P-34 (camino SQL sin `dict` por fila) | −8 %, reestructura `restore_binary_values` y `__record_blocks` | Reevaluar tras medir P1 |
| P-35 (plantilla entre bloques) | < 1 % estimado, sin medir | Medir con P0; solo si > 2 % |

## Paso 0 — Benchmark reproducible (P0)

**Fichero nuevo**: `scripts/bench_sqlgen.py` (a partir de `bench_sqlgen.py` de la auditoría).

- Mide por dialecto, sin servidor (`create_engine(url).dialect`), las etapas normalización / render / escritura de
  INSERT, UPDATE y DELETE, con el dataset de `bench_bulk.make_dataframe`.
- Argumentos: `--rows` (100000), `--dialects` (todos), `--chunk-size` (5000), `--repeat` (3, mediana), `--out` (CSV
  opcional).
- Modo `--e2e`: API pública con SQLite en fichero temporal (`bulk_*_from_df(..., generar_sql=True)`).
- Sin tests unitarios propios; se excluye del paquete como el resto de `scripts/`.

Tests de equivalencia: **no hace falta crear golden nuevos**. Ya existen y cubren P1:

- `tests/unit/bulk/test_generate_sql_template.py`: plantilla contra compilación por fila en 8 drivers (INSERT, override
  identity, UPDATE, PK compuesta, DELETE, `None` en WHERE, `%(x)s`, claves distintas, sin compilación por fila).
- `tests/unit/bulk/test_dataframe_to_sql_records.py`: igualdad estricta (valor + tipo) contra
  `normalize_records_for_sql(df.to_dict("records"))` en 24 dtypes.

**Medir baseline con `scripts/bench_sqlgen.py` antes del paso 1** y guardarlo en `baseline/` de esta sesión.

## Paso 1 — P-33: vía rápida de columnas de texto

**Fichero**: `src/util_bbdd/bulk/normalize.py`, `_normalize_column` (rama final, líneas 207-210).

```python
def _normalize_text_column(values: list[Any]) -> list[Any] | None:
    """Vía rápida (P-33): columna solo de ``str`` exacto y nulos. ``None`` si hay otro tipo (camino general)."""
    for value in values:
        if type(value) is not str and value is not None and value is not pd.NA and not (
            type(value) is float and value != value
        ):
            return None
    return [None if (value is None or type(value) is not str) else (value.strip() if value else value) for value in values]
```

- Se aplica solo si `dtype == object` o `isinstance(dtype, pd.StringDtype)` (incluye la `str` de pandas 3); **no** a
  `category` ni a otras extensiones.
- `type(value) is str` exacto: `np.str_` y subclases van al camino general.
- Equivalencia: `normalize_sql_literal(str)` → `strip()` si no vacío; `None`, `pd.NA` y `NaN` → `None`
  (`maybe_box_native` no cambia `str` ni `None`).

**Tests** (`tests/unit/bulk/test_dataframe_to_sql_records.py`), añadir a `DTYPE_MATRIX`:

- `object_str_only`: `[" a ", None, "", "x ", np.nan]` (object con NaN float)
- `object_str_pd_na`: `["a", pd.NA, " b", "", None]`
- `string_pyarrow`: `pd.array([...], dtype="string[pyarrow]")`, con `importorskip("pyarrow")`
- `object_np_str`: `[np.str_(" a "), "b", None]` (debe ir al camino general y seguir igual)
- `object_str_and_int`: `["a", 1, None]` (sale de la vía rápida en el 2.º valor)

## Paso 2 — P-31: render por columnas

**Fichero**: `src/util_bbdd/bulk/_support/sql_helpers.py`.

1. `_LiteralTemplate.__init__`: precalcular
   - `self._fmt`: `"".join(part.replace("%", "%%") + "%s" for part in self._parts) + self._tail.replace("%", "%%")`
   - por hueco (en el orden de `self._order`): tipo de render (`String()` si JSON, el de la columna si no).
2. Nuevo `_LiteralTemplate.render_block(records, per_row) -> list[str]`:
   - `bad = bytearray(n)`; con `exact_keys`, marcar las filas con `record.keys() != self._keys`.
   - Para cada hueco, un bucle local sobre las filas no marcadas:
     - `KeyError` → marcar la fila.
     - `None` → `"NULL"`, o marcar la fila si el hueco está en el WHERE.
     - WHERE: `render(value, slot.type.coerce_compared_value(operators.eq, value))`; VALUES/SET: `render(value, type_)`.
     - `Exception` → marcar la fila.
     - `if undouble and "%%" in s: s = s.replace("%%", "%")`.
   - Ensamblado: `fmt % fila` por fila buena y `per_row(records[i])` por fila marcada, en orden.
3. `_render_lines`: `template.render_block(records, per_row)` si hay plantilla; si no, igual que ahora.
4. Retirar `render()` y `_literal()` si no quedan usos (grep en `src/` y `tests/`); si algún test los usa, mantener
   `render()` delegando en `render_block([record], …)`.

Invariantes que se conservan: mismo orden de líneas; las filas no renderizables usan `per_row` (misma salida o mismo
error); `test_template_path_is_used_without_per_row_compilation` sigue sin compilaciones por fila.

## Paso 3 — P-32: procesador precalculado

**Fichero**: `src/util_bbdd/bulk/_support/sql_helpers.py`, `_LiteralTemplate.__init__` y `render_block`.

- `direct = type(self._compiler).render_literal_value is SQLCompiler.render_literal_value` (import de
  `sqlalchemy.sql.compiler`).
- Si `direct`, para cada hueco de VALUES/SET: `proc = type_.dialect_impl(dialect).literal_processor(dialect)` (API
  pública). Si es `None`, ese hueco usa `render` (hoy daría `CompileError` → fallback; se conserva).
- En `render_block`: `proc(value)` en lugar de `render(value, type_)` cuando haya `proc`. Los huecos del WHERE siguen
  con `coerce_compared_value` + `render`.
- PostgreSQL y MySQL/MariaDB no cambian: su compilador redefine `render_literal_value` (escape de `\`).

**Test nuevo** en `test_generate_sql_template.py`: `test_direct_processor_only_for_base_compiler`. Comprueba que el
atajo se activa en sqlite/mssql/oracle, no en postgresql/mysql/mariadb, y que la salida sigue igual a `_ref_insert`
(ya cubierto por los tests de equivalencia existentes).

## Paso 4 — Validación y cierre

1. `python -m ruff format src tests scripts` · `python -m ruff check src tests scripts` ·
   `python -m mypy src tests/unit/test_protocol_conformance.py` · `python -m pytest`
2. `scripts/bench_sqlgen.py` después de cada paso (1, 2, 3) → `validation/` de esta sesión; tabla antes/después en
   `validation_report_20260925.md`.
3. `--e2e` con 1M filas en SQLite para la métrica final.
4. `CHANGELOG.md` → *Performance*: P-31/P-32/P-33 con cifras medidas. Sin cambios de API pública ni en
   `COMPATIBILITY.md`. Sin cambios de imports entre paquetes: no hay que regenerar el diagrama de capas.
5. `/audit-code` sobre `normalize.py` y `sql_helpers.py`.

## Estimación

| Paso | Esfuerzo |
|---|---|
| 0 — benchmark en el repo + baseline | 1,5 h |
| 1 — P-33 + tests | 1,5 h |
| 2 — P-31 | 3 h |
| 3 — P-32 + test | 1 h |
| 4 — validación, CHANGELOG, audit-code | 1,5 h |
| **Total** | **~8,5 h** |
