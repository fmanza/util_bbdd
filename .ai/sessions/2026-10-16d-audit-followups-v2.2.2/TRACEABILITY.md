# TRACEABILITY

## Session metadata
- id: 2026-10-16d-audit-followups-v2.2.2
- fecha: 2026-10-16
- rama: develop (base `252fe00f`, tag `v2.2.2`)
- skill: fix + refactor + test, version_closure v2.2.3
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + VERSION

## Prompt issued
«PLAN y AUDIT_PLAN de la auditoria» (residuos del `/audit-code` de v2.2.2, con `"CURRENT_TIMESTAMP"` de
`migrate/emitters/mariadb.py:497` seleccionado en el IDE); después «si» (D1–D6 con las opciones recomendadas).

## Context supplied
- `/audit-code` de `.ai/sessions/2026-10-16c-sonarlint-cleanup/` (hipótesis H1 y H2, tests sugeridos).
- `PLAN_AUDIT_PLAN.md` de esta sesión.

## AI output summary
- PLAN + AUDIT_PLAN: H1 resultó un bug real y previo a v2.2.2 (A1); H2 (doble ERROR) confirmado y dejado (D4).
- **A1** (`fix(analysis)`): 3 tests que reproducen el bloqueo (fallaban antes del arreglo); `_render_batch` con
  `_render_with_dot` (captura `Exception`) y `_fail_pending` (ningún `Future` sin resolver, también sin Graphviz o con
  `BaseException`).
- **A2** (`test(migrate)`): 8 casos de `_strip_pg_cast`. El caso `('x'::text)::character varying` da `'x'::text`
  igual que en v2.2.1 (los paréntesis exteriores se quitan después del bucle de casts): no se incluyó.
- **A3** (`refactor(migrate)`): `_CURRENT_TIMESTAMP` en `default_normalizer.py` (5) y `emitters/mariadb.py` (2).
- **A4** (`refactor(connection)`): `_rejected_optional_param(err, optional)` única en `connection_mariadb.py`.
- **A6** (`test(migrate)`): `_SUPPORTED_SOURCE`/`_SUPPORTED_TARGET` del planner ⊆ `SQLGLOT_DIALECT`.
- `/version-closure` v2.2.3: CHANGELOG, `pyproject.toml`, `README.md` (2), `docs/index.md`, `docs/roadmap.md`, pie de
  `docs/architecture.md`, `CURRENT_STATE`, `SESSIONS_DIGEST`, `INDEX`.

## Tests and evidence
- `build/logs/v2.2.3_gate.txt`: `ruff check` y `ruff format --check` (709 ficheros), `mypy` sin errores (337),
  `pytest` sin URLs del banco **6097 passed, 532 skipped**, `zensical build --strict` sin avisos.
- `build/logs/v2.2.3_bench.txt`: banco con los 6 motores **6621 passed, 8 skipped** (v2.2.2: 6609).
- `scripts/gen_arquitectura_capas.py`: sin cambios de contenido (337 ficheros).
- `tests/unit/test_docs_version.py`: 6 passed con 2.2.3.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-10-16d-audit-followups-v2.2.2/PLAN_AUDIT_PLAN.md` | aprobado |
| Logs | `build/logs/v2.2.3_gate.txt`, `build/logs/v2.2.3_bench.txt` | generados |

## Known limitations
- H2: el fallo de conexión sigue registrándose dos veces (conexión con traceback y manager), como antes de v2.2.2.
- `normalize_default("postgresql", "('x'::text)::character varying")` conserva el cast interior (`'x'::text`), igual
  que en v2.2.1.

## Rollback
- `git revert` de los commits de la sesión y del de release; el tag se retira con `git push origin :v2.2.3`. Riesgo
  bajo: solo A1 cambia comportamiento (la precarga deja de bloquearse).

## Directrices para Futuras IAs
- **[analysis]**: todo `Future` de `GraphvizRelationshipGraphExt._prefetched` debe resolverse en `_render_batch`
  (`_fail_pending`): `_pipe_graph_bytes` llama a `Future.result()` sin timeout.
- **[analysis]**: para probar la precarga sin Graphviz real, `tests/unit/test_graphviz_ext_prefetch.py` tiene
  `_FakeDot`, `_FakeDotProcess` (sustituye a `subprocess.run`) y `_generator()`; comprobar `future.done()` antes de
  pedir el resultado para que un fallo no bloquee el test.
- **[migrate]**: `normalize_default` de PostgreSQL quita los casts finales y después los paréntesis exteriores: un cast
  dentro de paréntesis (`('x'::text)::varchar`) se conserva.
- **[migrate]**: `tests/unit/migrate/test_planner.py::test_every_planner_engine_has_a_sqlglot_dialect_for_views` obliga
  a añadir el dialecto de sqlglot al añadir un motor a `MigrationPlanner`.
- **[connection]**: `_rejected_optional_param(err, optional)` vive en `connection/mariadb/connection_mariadb.py`; el
  pool nativo la importa (sin ciclo: `connection_mariadb` no importa el pool).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Ninguno de la versión (commits, tag `v2.2.3` y push hechos al cerrar).
