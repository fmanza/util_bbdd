# PLAN + AUDIT_PLAN — pendientes tras v1.0.0

Fecha: 2026-10-10 · Base: `develop` @ `158903b6` (v1.0.0) · Solo lectura (sondas en directorios temporales y logs en
`build/logs/postv1_*`).

## 0. Fuentes revisadas

`.ai/CURRENT_STATE.md`, `docs/roadmap.md`, `2026-10-10-api-1-0-final/` (`TRACEABILITY.md`, `02_DOC_REVIEW.md`),
`2026-10-10-plan-pendientes-global/` (`PLAN_AUDIT_PLAN.md`, `Q6_PLAN_API_1_0.md`), `src/util_bbdd/bulk/`, `audit/`,
`dump/`, tests citados, `.github/workflows/`, `mkdocs.yml`, refs de `origin` (`git ls-remote`).

## 1. Inventario verificado

| ID | Pendiente | Estado verificado hoy (evidencia) | Severidad |
|---|---|---|---|
| **P1** | Release en `main` | **Confirmado.** `main` = `origin/main` = `3c94ca4a` (v0.42.1); `develop` = `origin/develop` = `158903b6`; `git merge-base --is-ancestor main develop` → sí; 10 commits. Tags `v0.43.0`, `v0.44.0` y `v1.0.0` ya en origin. `origin/HEAD` → `main`: la portada del repositorio en GitHub muestra el README de 0.42.1 (instalación desde PyPI, que no existe) | Media (lo que ve quien llega al repo está desfasado) |
| **P2** | A5: SRP de `BulkCrud` por dentro | **Premisa desfasada en parte.** `bulk/crud.py` tiene hoy **1943** líneas y 63 métodos (no 1750/62). La auditoría **ya** está fuera: `BulkPersistenceManager` (`_support/persistence.py`) y `AuditManager`; las 5 propiedades `audit_*` son delegaciones de una línea. Los rechazos también: `RejectsWriter`/`Isolator` (`_support/rejects.py`, 315 líneas). Lo que queda dentro de la clase con responsabilidad propia: **mantenimiento de tabla** (`maintenance_scope` + 7 privados de constraints/índices/huérfanos de FK de PG/Oracle, líneas 1492–1866, **~375 líneas**); **orquestación del aislamiento** (`rejects_scope`, `__isolating`, `__batch_errors`, `__rejected_so_far`, `_RejectsScope`, `_IsolatedOperation`, ~130 líneas); generación de SQL a fichero (`__generar_sql_*`, `__guardar_fichero_sql`, ~45 líneas). Acoplamiento de tests a privados: 11 ficheros usan `_BulkCrud__*`, pero solo 4 nombres (`__ejecutar_batch_stmt`, `__prepare_insert_operation`, `__validar_y_generar_path_sql`, `__actualizar_df`), ninguno de mantenimiento ni de aislamiento. `maintenance_scope` lo usan `ParallelBulkLoader` y `tests/unit/bulk/test_maintenance_scope.py` (API pública) | Baja (deuda de diseño, sin fallo) |
| **P3** | Rutas `str` en parámetros `Path` | **Confirmado y más amplio** (`build/logs/postv1_probe_paths.txt`): `BulkCrud(audit_csv_path="audit.csv")` y `ParallelBulkLoader(audit_csv_path=…)` → `AuditConfigError: 'str' object has no attribute 'parent'` (`audit/legacy_csv.py:113`); `DumpConfig(bulk_audit_path="b.csv")` → `AttributeError … 'is_file'` en `audit/files.py:66` **antes** de tocar el destino; **`DumpConfig(output_dir="out")` carga los datos y después falla con `TypeError` en `dump/reporters.py:205`, sin `DumpResult` ni `DumpReportError`** (el destino queda con las filas y quien llama no recibe el resultado); `bulk_*(path_sql="x.sql")` → `ValueError` explícito «debe ser una instancia de Path». `rejects_csv_path` con `str` funciona por casualidad (en `BulkCrud` y `DumpConfig`). Todas las firmas dicen `Path` | Media (`output_dir`: volcado hecho y resultado perdido); baja el resto (fallan al construir o antes de cargar) |
| **P4a** | `ResourceWarning: unclosed database` con `--cov` | **Confirmado; la fuga es de los tests.** Sin `--cov`, 0 avisos en el mismo subconjunto; con `--cov`, 28 (subconjunto) y **340** en la suite completa (5678 passed, 523 skipped; `build/logs/postv1_fullcov_tracemalloc.txt`, agrupado en `postv1_resourcewarnings_by_origin.txt`). `tracemalloc` sitúa 320 aperturas en **40 ficheros de test** (los que más: `test_maintenance_scope.py` 59, `test_on_error_isolate.py` 41, `test_parallel_loader_audit.py` 18, `test_comparator.py` 14, `test_streaming_and_resume.py` 14, `test_parallel_loader_isolate.py` 12); las 20 restantes no tienen marco de test porque se abren en hilos de `ParallelBulkLoader`. Son Engines SQLite creados en los tests y nunca liberados (p. ej. `test_parallel_loader_isolate.py:36` `_engine()`, `test_comparator.py:370–484` `create_engine("sqlite:///:memory:")`). Los marcos de la librería (`metadata/reflection.py:655`, `migrate/views/validation.py:62`, `connection/performance_advisor.py:182`, `bulk/_execution/executors.py:196`) usan `with engine.connect()` o cierran en `finally`: la conexión vuelve al pool **del Engine del test**, que nadie hace `dispose()`. Los avisos se ven en `test_performance_advisor_once.py:94` porque ahí hay un `gc.collect()` | Baja (ruido; puede ocultar una fuga real futura) |
| **P4b** | `SADeprecationWarning` por `strategy="mock"` | **Confirmado**: `tests/_core/test_batching.py:56, 65, 74`; 3 avisos | Baja |
| **P5** | Docs no revisadas página a página | **Confirmado.** 112 `.md` en `docs/` (sin `v0.8.0/` ni `adr/`); la sesión de 1.0 leyó 7 enteras. Barrido rápido hoy: `docs/guides/comparator.md:9` aún dice `pip install util_bbdd` (escapó a la revisión de 1.0); `pip install util_bbdd[analysis]` (forma PyPI) en `functional/graph_analysis.md:16, 63` y `examples/graph_generation.md:10`; `constraints_*.md` y `performance_audit_*.md` están en la raíz de `docs/` (la convención pone las guías en `docs/guides/`) y `constraints_audit_index.md` lleva «Versión 1.0.0 · 2026-09-26», que es la de los prompts, no la de la librería. Tamaño del bloque pedido: rendimiento 3 páginas (1287 líneas), constraints 3 (920), `migrate_*` 12 (1034) | Media (docs que inducen a instalar o usar mal) |
| **P6** | `CURRENT_STATE.md` «Próximos pasos» | **Confirmado**: solo ítems numerados `0…000000000` (históricos) y tachados. Además, la cabecera y la fila `v1.0.0` dicen «sin push ni tag», ya falso (tag y `develop` en origin) | Baja |
| **P7** | Externos | No verificables aquí (sin `gh`). Indicio: en origin no existe `refs/pull/18/merge` (GitHub lo retira al cerrar una PR), igual que en la #19 fusionada → la #18 probablemente ya está cerrada. Borrador del issue ORA-03106 presente (`2026-10-01y-ora03106-repro/ISSUE_DRAFT.md`). `docs-release.yml` se dispara con `push` de tags `v*`; `integration.yml` es nocturno + manual | — (usuario) |
| **N1** | `doc_agents.yml` heredado | **Nuevo.** `.github/workflows/doc_agents.yml:9, 79` usa por defecto `src/util_bbdd/timelog/time_utils.py`, que no existe en este repo (de otro proyecto) | Baja |
| **N2** | Ramas de dependabot | **Nuevo.** 8 ramas `origin/dependabot/*` del 2026-03-31 al 2026-06-23 (checkout 7, codecov 7, create-pull-request 8, build, coverage, jaraco-context, requests, ruff 0.15.8); estado de sus PR no verificable aquí | Baja (usuario) |
| **O1** | Observación, sin acción | `bulk_insert_from_df/update/delete(…, generar_sql=True)` por defecto: sin `path_sql` falla con `ValueError`. Es API pública 1.0; cambiar el default sería MAJOR. Solo se anota para 2.0 | — |

Aparcados sin reabrir: S-1 y las dos limitaciones de driver (ADR-005).

## 2. Decisiones para el usuario

| # | Tema | Opciones | Recomendación |
|---|---|---|---|
| D1 | P1: `main` | (a) fast-forward `main` → `158903b6` y push de `main` ahora, antes de seguir; (b) al cerrar 1.1.0 | **(a)**: v1.0.0 ya está publicada con tag; la rama por defecto de GitHub enseña 0.42.1 y su instalación por PyPI. No hay tag nuevo que crear |
| D2 | P2: alcance de A5 | (a) **re-alcance**: sacar el mantenimiento de tabla a `_support/maintenance.py` (clase propia) y la orquestación del aislamiento a `_support/rejects.py`; la auditoría no se toca (ya está fuera); (b) A5 literal (auditoría y rechazos): casi hecho, ganancia ~130 líneas; (c) aparcar A5 | **(a)**: es donde está el tamaño (~500 de 1943 líneas) y no hay tests atados a esos privados |
| D3 | P3: rutas `str` | (a) `/new-feature` 1.1.0: aceptar `str \| os.PathLike[str]` en **todos** los parámetros de ruta de los puntos de entrada públicos de `bulk` y `dump` (`audit_csv_path`, `rejects_csv_path`, `path_sql`, `output_dir`, `bulk_audit_path`), normalizando con `Path(...)` en la entrada; (b) solo `audit_csv_path`; (c) `/hotfix` 1.0.1 limitado a `output_dir` (el único que pierde el resultado tras cargar) + (a) en 1.1.0; (d) nada | **(a)**: es aditivo (MINOR), un solo patrón y cubre `output_dir`. Si quieres publicar el arreglo de `output_dir` sin esperar al resto, (c) |
| D4 | P5: alcance de docs | (a) nivel 1 ahora: las 18 páginas pedidas (rendimiento, constraints, `migrate_*` funcional y API) + las coincidencias del barrido; nivel 2 (resto, ~85 páginas) en otra sesión; (b) las ~105 ahora | **(a)** |
| D5 | P5: ubicación de `constraints_*`/`performance_audit_*` | (a) moverlas a `docs/guides/` (convención) con sus enlaces y `nav`; (b) dejarlas | **(a)**, en el mismo bloque de docs; `zensical build --strict` detecta enlaces rotos |
| D6 | Versionado | (a) una sola **1.1.0** con B2–B5 (los tests y el refactor no exigen versión propia); (b) 1.0.1 (B2+B4) y 1.1.0 (B3+B5) | **(a)** |

## 3. PLAN por bloques

| # | Bloque | Contenido | Flujo | Versión | Commit |
|---|---|---|---|---|---|
| B0 | Estado y CI | `CURRENT_STATE.md`: cabecera y fila `v1.0.0` (tag y push hechos), «Próximos pasos» rehecho con P1–P7/N1–N2 y su estado; `doc_agents.yml` con un módulo por defecto real (`src/util_bbdd/bulk/crud.py`) | `docs` + `chore(ci)` | — | 2 commits |
| B1 | Release `main` (D1) | `git checkout main && git merge --ff-only develop`, `git push origin main`; comprobar `git rev-parse main origin/main` | `chore` (sin commit) | v1.0.0 | — · **requiere autorización** |
| B2 | Tests (P4) | `engine.dispose()` en los 40 ficheros de `postv1_resourcewarnings_by_origin.txt`: preferible una fixture común `sqlite_engine` (en `tests/conftest.py` o `tests/unit/bulk/conftest.py`) con `yield` + `dispose()` y los helpers `_engine()` convertidos a fixtures, en vez de 40 `try…finally`; `create_mock_engine` en `test_batching.py`. Criterio: `pytest --cov` con 0 `ResourceWarning` y 0 `SADeprecationWarning` | `test` | — | 1–2 |
| B3 | Rutas `str` (D3) | Normalizar en la entrada: `BulkCrud.__init__` (`audit_csv_path`, `rejects_csv_path`), `bulk_*(path_sql)` (relajar la comprobación de `persistence.resolve_sql_output_path`), `ParallelBulkLoader.__init__`, `DumpConfig.__post_init__` (`output_dir`, `bulk_audit_path`, `rejects_csv_path`), `AuditManager`/`legacy_csv` como red de seguridad. Firmas a `str \| os.PathLike[str]` (o un alias `StrPath`). Tests: una prueba por parámetro con `str`, y `dump` con `output_dir=str` que devuelve `DumpResult` con informe. Docstrings y `docs/api/bulk_crud.md`, `dump.md` | `/new-feature` | 1.1.0 | `feat(bulk,dump)` |
| B4 | A5 (D2) | `/refactor` sin cambios funcionales: (1) `TableMaintenance` en `bulk/_support/maintenance.py` con `scope()` y los 7 privados; `BulkCrud.maintenance_scope` delega con la misma firma, docstring y `MaintenanceScopeResult`; (2) aislamiento: `rejects_scope`/`__isolating` delegan en un objeto de `_support/rejects.py` que posee `_RejectsScope`, `_rows_rejected` e `_isolator`. Antes: tests de caracterización de `maintenance_scope` por motor si faltan (SQLite unitario; PG/MySQL/MariaDB/SQL Server/Oracle en integración, ya en `tests/integration/test_bulk_engines.py`). Diagrama de capas sin cambios (todo dentro de `bulk`) | `/refactor` | 1.1.0 | `refactor(bulk)` × 2 |
| B5 | Docs nivel 1 (D4, D5) | Método de `02_DOC_REVIEW.md` (imports + métodos automáticos, lectura completa, ejecución de ejemplos tocados) sobre: `performance_audit_guide.md`, `performance_audit_constraints_guide.md`, `guides/benchmarks.md`, `constraints_*.md` (3), `functional/migrate_*.md` (6), `api/migrate_*.md` (6); más `guides/comparator.md:9`, `functional/graph_analysis.md`, `examples/graph_generation.md` (instalación desde git). Movimiento a `docs/guides/` si D5-(a). Registro en `02_DOC_REVIEW.md` de esta sesión | `docs` | 1.1.0 | 1–2 |
| B6 | Externos | PR #18 (confirmar cerrada), issue ORA-03106, `docs-release.yml` de v0.43.0/v0.44.0/v1.0.0, `integration.yml`, PR de dependabot (N2) | usuario | — | — |
| B7 | VERSION 1.1.0 | Puerta completa ×2 (sin/con banco), CHANGELOG `[1.1.0]` (`Added`: rutas `str`; `Fixed`: `output_dir` en `dump`; `Changed`: interno), `pyproject.toml`, README, `docs/index.md`, `docs/roadmap.md`, pie de `docs/architecture.md` (`test_docs_version`), `CURRENT_STATE`, `SESSIONS_DIGEST`. Tag, push y FF de `main`: **requieren autorización** | `/version-closure` | 1.1.0 | `release: v1.1.0 - …` |

Orden: B0 → B1 (si D1-a) → B2 → B3 → B4 → B5 → B7. B2 antes de B3/B4 para que la suite de referencia no tenga ruido
de avisos; B3 antes de B4 porque toca `BulkCrud.__init__` y es lo que ve el usuario; B4 se hace sobre una base
estable y con la suite en verde.

## 4. AUDIT_PLAN

### Riesgos funcionales

| Bloque | Riesgo | Mitigación |
|---|---|---|
| B1 | FF de `main` con algo no deseado | Solo `--ff-only` (falla si no es FF); `git log main..develop` revisado antes (10 commits, todos de 0.43.0–1.0.0) |
| B1 | `docs.yml`/`docs-zip-release.yml` se disparan con `push` a `main` | Esperado: publica la documentación de 1.0.0; el usuario lo comprueba en Actions |
| B3 | Normalizar con `Path()` cambia el tipo del atributo expuesto (p. ej. `DumpConfig.output_dir` pasa a ser siempre `Path`) | Es lo que la firma ya promete; test que fija `isinstance(cfg.output_dir, Path)` |
| B3 | `DumpConfig` es `dataclass`: normalizar en `__post_init__` muta el campo | Ya valida ahí (`validate_isolation`) y no es `frozen` (`dump/_models.py:58`): asignación directa |
| B3 | `path_sql` hoy rechaza `str` a propósito | Relajar a `str \| PathLike` no rompe a nadie (antes era error); test de `str` y de tipo inválido (`int`) que sigue dando `ValueError` |
| B4 | El refactor cambia el orden de restauración de constraints/índices o el manejo de errores de `maintenance_scope` (Oracle confirma con DDL; PG hace orphan-check) | Mover sin reescribir; `tests/integration/test_bulk_engines.py` y `test_maintenance_scope.py` en los 5 motores antes y después; diff revisado por bloques |
| B4 | `ParallelBulkLoader` usa `maintenance_scope` | La firma y el `MaintenanceScopeResult` no cambian; `test_parallel_loader*.py` en la puerta |
| B4 | Name-mangling: mover privados `__x` a otra clase cambia su nombre interno | Ningún test usa los privados que se mueven (verificado: solo 4 nombres, ninguno de mantenimiento/aislamiento); `grep _BulkCrud__` tras mover |
| B5 | Mover páginas rompe enlaces internos o externos | `grep` de cada nombre en `docs/`, README, `mkdocs.yml`, `.github/`; `zensical build --strict`; nota en CHANGELOG |
| B5 | Corregir docs con APIs inventadas | Regla del proyecto: verificar contra el código; marcar «pendiente de verificación» lo no comprobable |

### Riesgos técnicos

- **Puerta doble** en B2–B5 y B7: sin URL del banco (lo que ve el CI) y con banco + `JAVA_HOME`; la memoria del proyecto
  registra 12 fallos ocultos por el banco en v0.42.1.
- **B2**: la cifra de ~340 depende de cuándo recolecta el GC; el criterio es «0 con `--cov`», no una cuenta concreta.
  Si un aviso remanente viene de la librería (Engine creado por ella y no liberado), se separa a un `fix` con su test.
- **Barras invertidas**: editar con Write/Edit, nada de `sed` global en `src`/`tests` (memoria del proyecto).
- **Trabajo en paralelo del usuario**: añadir solo rutas propias; `NEXT_SESSION_PROMPT.md` sin seguimiento no se toca.
- **mypy estricto**: `str | os.PathLike[str]` en firmas públicas; comprobar `tests/unit/test_protocol_conformance.py`.

### Riesgos de seguridad

- B3: aceptar `str` no amplía la superficie (ya se aceptaba `Path` arbitrario). No se resuelven ni expanden `~` ni
  variables; misma ruta que el usuario pasa.
- B1/B7: ninguna acción remota sin autorización explícita.

### Verificación

| Bloque | Evidencia |
|---|---|
| B0 | Diff de `CURRENT_STATE.md`; `doc_agents.yml` con ruta existente (`test -f`) |
| B1 | `git rev-parse main origin/main` = `158903b6` |
| B2 | `pytest --cov` completo con 0 `ResourceWarning`/`SADeprecationWarning` (`build/logs/`) |
| B3 | La sonda `postv1_probe_paths.txt` re-ejecutada: todo `OK`; tests nuevos en rojo antes, verde después |
| B4 | Suite unitaria + `tests/integration` (5 motores + HSQLDB) idénticas antes/después; `crud.py` ~1450 líneas |
| B5 | Comprobadores de imports/métodos sin hallazgos en las páginas revisadas; `zensical build --strict` |
| B7 | Puerta completa ×2, `python -m build` → `util_bbdd-1.1.0` |

### Veredicto AUDIT_PLAN

**GO_CONDICIONAL**: B0 y B2 pueden empezar sin decisiones; B1 necesita D1 y autorización; B3 necesita D3; B4 necesita
D2; B5 necesita D4–D5; B7, D6 y autorización para tag/push.
