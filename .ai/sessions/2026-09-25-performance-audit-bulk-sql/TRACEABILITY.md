# TRACEABILITY

## Session metadata
- id: 2026-09-25-performance-audit-bulk-sql
- fecha: 2026-09-25
- rama: develop
- skill: performance-audit-bulk
- fase: MAP_CURRENT_STATE + MEASURE_OVERHEAD + ANALYZE_CODE + PROPOSE_OPTIMIZATIONS + VALIDATE_MULTI_DIALECT; PLAN + AUDIT_PLAN; /refactor: IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
- `/performance-audit-bulk` — Mejorar los tiempos de serialización de los ficheros SQL. Scope: src/util_bbdd/bulk/ (5 fases).
- "PLAN y AUDIT_PLAN"
- `/refactor con este PLAN . pyarrow ha sido instalado`

## Context supplied
- `CLAUDE.md`, `.claude/commands/performance-audit-bulk.md`
- Respuestas del usuario: 5 dialectos, 1M filas, baseline + validación, salida `.ai/audit/*_bulk_sql_serialization*`

## AI output summary
- Mapeo del camino `generar_sql=True`: `crud.py` → `normalize.dataframe_to_sql_records` → `sql_helpers._LiteralTemplate` → `persistence.persist_sql`.
- Baseline e2e SQLite 1M: INSERT 11,60 s, UPDATE 11,89 s, DELETE 2,16 s. Desglose por etapa en 5 dialectos (100K). cProfile del render.
- Prototipos P-31/P-32 (salida byte-idéntica, −15 a −39 %) y P-33 (−75 % por celda de texto).
- Hallazgo P-30 (binarios no UTF-8, ×12) y C-1 (literal `0x…` inválido en PG/Oracle/SQLite).
- Informes en `.ai/audit/`. PLAN y AUDIT_PLAN (APROBADO CON CONDICIONES) con los supuestos S1–S8 verificados.
- Sin cambios en `src/` ni en `tests/` hasta el `/refactor`.
- `/refactor`, paso 0: `scripts/bench_sqlgen.py`. Baseline con pyarrow (la normalización pasa de 2,8 a 4,1 µs/fila por la dtype `str` en pyarrow): e2e 1M INSERT 12,63 s, UPDATE 12,99 s, DELETE 2,14 s.
- Paso 1 (P-33): `normalize._normalize_column`, que extrae los valores con `to_numpy(dtype=object)` y añade `_normalize_text_values` / `_normalize_values`. Normalización −61 %.
- Paso 2 (P-31): `_LiteralTemplate.render_block` / `_render_column`, que sustituyen a `render` / `_literal`. Un primer intento con `functools.partial(render, type_=…)` solo daba −9 %, por el diccionario de kwargs en cada celda; con la llamada posicional, −21 a −24 %.
- Paso 3 (P-32): `_LiteralTemplate._processor`, con `literal_processor` directo si `render_literal_value` es el de `SQLCompiler`, y el WHERE como procesador (`coerce_compared_value`). Render −39 a −41 % en sqlite/oracle/mssql.
- Tests: 6 dtypes nuevos en `test_dataframe_to_sql_records.py` y 2 tests (16 casos) en `test_generate_sql_template.py`. ruff, mypy y pytest (4896 passed) en verde.
- Equivalencia: SHA-256 de 15 ficheros (5 dialectos × 3 operaciones, 100K) idénticos entre `HEAD` (worktree temporal, ya retirado) y el código nuevo.
- Final e2e 1M SQLite: INSERT 6,09 s (−52 %), UPDATE 6,64 s (−49 %), DELETE 1,89 s (−12 %). CHANGELOG actualizado (*Changed*).

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Informe de auditoría | `.ai/audit/audit_report_bulk_sql_serialization_20260925.md` | emitido |
| Roadmap | `.ai/audit/optimization_roadmap_bulk_sql_serialization.md` | emitido |
| PLAN | `.ai/sessions/2026-09-25-performance-audit-bulk-sql/PLAN.md` | emitido |
| AUDIT_PLAN | `.ai/sessions/2026-09-25-performance-audit-bulk-sql/AUDIT_PLAN.md` | emitido |
| Benchmark | `scripts/bench_sqlgen.py` | nuevo |
| IMPLEMENT | `src/util_bbdd/bulk/normalize.py`, `src/util_bbdd/bulk/_support/sql_helpers.py` | completado |
| Tests | `tests/unit/bulk/test_dataframe_to_sql_records.py`, `tests/unit/bulk/test_generate_sql_template.py` | completado |
| Validación | `validation_report_20260925.md`, `baseline/`, `validation/` | emitido |
| CHANGELOG | `CHANGELOG.md` (*Unreleased → Changed*) | actualizado |

## Directrices para Futuras IAs
- **[bulk/sql_helpers]**: en SQLAlchemy 2.0.50, SQLite, SQL Server y Oracle usan `SQLCompiler.render_literal_value` sin redefinir; PostgreSQL y MySQL/MariaDB lo redefinen (escape de `\`). Cualquier atajo al `literal_processor` debe limitarse a los primeros.
- **[bulk/sql_helpers]**: las filas que caen a `compile_stmt_with_binary_support` formatean **todas** sus columnas con `format_sql_param_value`, no con el dialecto. Sacar una fila del fallback cambia su salida aunque el valor problemático se renderice igual.
- **[bulk/sql_helpers]**: no memoizar literales por igualdad de valor: `Decimal("1.0") == Decimal("1.00")`, `0.0 == -0.0` y los `datetime` con zona iguales se renderizan distinto.
- **[bulk/sql_helpers]**: en el bucle caliente de `_render_column`, no llamar a `render_literal_value` con `partial(..., type_=...)`: el diccionario de kwargs de cada celda se come la mitad de la mejora. Usar llamada posicional.
- **[bulk/normalize]**: con pyarrow instalado, pandas 3 guarda la dtype `str` en pyarrow y `list(series)` cuesta ~0,56 µs/celda; `series.to_numpy(dtype=object)` cuesta ~0,04 µs/celda y da los mismos objetos. Los benchmarks antes/después deben tomarse con el mismo entorno.
- **[bulk/persistence]**: la escritura del `.sql` es ≈ 3 % del tiempo. Pasarla a un hilo o a E/S asíncrona no compensa y rompe la atomicidad `.tmp` → `replace`.

## Veredicto final
Veredicto: GO (AUDIT_PLAN C1–C4 cumplidas; AUDIT_CODE APROBADO)
Pendientes al cierre:
- Commit (no realizado: pendiente de confirmación del usuario).
- `/hotfix` aparte para P-30 + C-1 (binarios no UTF-8: fallback ×12 y literal `0x…` inválido en PG/Oracle/SQLite).
- Opcional: P-34 (−8 %) y P-35 (medir primero).
