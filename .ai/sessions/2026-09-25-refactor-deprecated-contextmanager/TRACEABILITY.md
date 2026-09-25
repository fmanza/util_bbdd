# TRACEABILITY

## Session metadata
- id: 2026-09-25-refactor-deprecated-contextmanager
- fecha: 2026-09-25
- rama: develop
- skill: refactor
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
Se detecta La función "contextmanager" está obsoleta
  Annotating the return type as `-> Iterator[Foo]` with `@contextmanager` is deprecated. Use `-> Generator[Foo]` instead.Pylance, revisa en proyecto partes obsoletas. PLAN y AUDIT_PLAN

(Tras el AUDIT_PLAN: "Adelante con veredicto y tus recomendaciones".)

## Context supplied
- `CLAUDE.md`, `pyproject.toml` (`requires-python >=3.12`, ruff `py312` con `UP`, mypy `3.12`)
- Precedente: `.ai/sessions/2026-06-02-maintenance-scope/TRACEABILITY.md` § "Corrección — Pylance deprecation"
- typeshed de Pylance 2026.4.1 (`dist/typeshed-fallback/stdlib/contextlib.pyi`)

## AI output summary
- Origen del aviso: el typeshed de Pylance tiene overloads `@deprecated` para `contextmanager(-> Iterator)` y
  `asynccontextmanager(-> AsyncIterator)`. El typeshed de mypy 1.19.1 aún no, por eso mypy no lo detectaba.
- Barrido estático: `mypy src --custom-typeshed-dir <typeshed de Pylance> --enable-error-code deprecated` → 4 avisos,
  todos en `src/`. `tests/` y `scripts/`: ninguno de tipo `deprecated`.
- Barrido en ejecución: `pytest tests/unit -W error::DeprecationWarning -W error::FutureWarning
  -W error::PendingDeprecationWarning` → 4377 passed (stdlib, SQLAlchemy, pandas sin avisos).
- Grep de APIs obsoletas conocidas (`utcnow`, `get_event_loop()`, `pkg_resources`, `declarative_base`, `distutils`,
  `asyncio.iscoroutinefunction`, `ast.Str`…) y `ruff --select UP`: sin resultados.
- IMPLEMENT (anotaciones, forma de 3 argumentos como `maintenance_scope`):
  - `bulk/crud.py`: `__blocks_transaction` y `bulk_session` → `Generator[None, None, None]`.
  - `bulk/_execution/parallel_loader.py`: `_hoist_constraints_for_workers` → `Generator[bool, None, None]`; import
    `Iterator` → `Generator` (era su único uso).
  - `executors/async_query_executor.py`: `_timeout_context` → `AsyncGenerator[None, None]`; `ruff format` partió la firma.
  - `docs/api/bulk-crud.md`: tipo de retorno de `bulk_session` en la tabla de API.
- Guardia: `pyproject.toml` `[tool.mypy] enable_error_code = ["deprecated"]` (0 errores hoy).
- AUDIT_CODE: los generadores solo usan `return` sin valor → tercer parámetro `None` correcto; sin Protocols ni tests
  que dependan de la anotación; tipo público de `bulk_session` sin cambios.
- Validación: `ruff format --check` y `ruff check src tests` limpios; `mypy src tests/unit/test_protocol_conformance.py`
  sin errores (con la guardia); mypy con typeshed de Pylance: 0 avisos; `pytest` 4826 passed / 160 skipped; unit con
  `-W error` de deprecaciones 4377 passed.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| IMPLEMENT | `src/util_bbdd/bulk/crud.py`, `src/util_bbdd/bulk/_execution/parallel_loader.py`, `src/util_bbdd/executors/async_query_executor.py` | completado |
| Docs | `docs/api/bulk-crud.md` | completado |
| Config | `pyproject.toml` (`enable_error_code`) | completado |
| CHANGELOG | `[Unreleased]` → *Changed* (2 entradas) | completado |

## Directrices para Futuras IAs
- **[tipado]**: con `@contextmanager` anotar `-> Generator[T, None, None]` y con `@asynccontextmanager`
  `-> AsyncGenerator[T, None]`. Con `target-version = "py312"` ruff no pide la forma corta (UP043 solo aplica a py313+).
- **[tipado]**: mypy con su typeshed propio puede ir por detrás de Pylance. Para ver lo mismo que Pylance:
  `python -m mypy src --custom-typeshed-dir ~/.vscode/extensions/ms-python.vscode-pylance-*/dist/typeshed-fallback
  --enable-error-code deprecated --cache-dir=/dev/null`.
- **[tipado]**: `tests/` no pasa `mypy` completo (errores previos de tipado ajenos a deprecaciones); no usarlo como señal.
- **[entorno]**: existe una caché suelta `src/util_bbdd/bulk/.mypy_cache` (2026-04-18), ignorada por git; se puede borrar.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Ninguno.
