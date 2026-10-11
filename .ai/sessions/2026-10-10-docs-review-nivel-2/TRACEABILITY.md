# TRACEABILITY

## Session metadata
- id: 2026-10-10-docs-review-nivel-2
- fecha: 2026-10-10 / 2026-10-11
- rama: develop
- skill: documentation (+ `/hotfix` × 2 y `/version-closure` → v1.1.1)
- fase: PLAN + AUDIT_PLAN + IMPLEMENT (C1, C2 y 4 tandas) + puerta de cierre + VERSION (esta traza; sin release)

## Prompt issued
`.ai/sessions/2026-10-10-plan-pendientes-post-1-0/NEXT_SESSION_PROMPT.md` (sesión de revisión de docs nivel 2, 82
páginas), pegado por el usuario.

## Context supplied
- `.ai/sessions/2026-10-10-plan-pendientes-post-1-0/02_DOC_REVIEW.md`, `03_DOCS_PENDIENTES.txt`
- `.ai/sessions/2026-10-10-api-1-0-final/02_DOC_REVIEW.md`
- `.github/DOCUMENTATION_STANDARD.md`, `.github/instructions/docs.instructions.md`
- `CLAUDE.md` + `.github/SHARED_INSTRUCTIONS.md`; memoria del usuario

## AI output summary
- PLAN + AUDIT_PLAN (`PLAN_AUDIT_PLAN.md`); el usuario aprobó D1–D5 según la recomendación.
- Comprobador reescrito (`tools/doc_check.py`, sigue `--8<--`) con lista de excepciones; `tools/overlap.py`;
  `tools/apply_edits.py` (sustituciones exactas con recuento, conserva el fin de línea).
- C1: `api/managers_sync_technical.md` consolidada en `api/managers_sync.md` (`a26cf3c2`).
- Tanda 1 `docs/api/` (25) `f0f8d81c`; C2 (aprobada por el usuario) `a1ccaf1b`; tanda 2 `docs/functional/` (14)
  `9cf2c2d0`; tanda 3 `docs/examples/` (17, todos ejecutados, SQLite y banco) `12568b5e`; tanda 4a (9 guías de uso)
  `7d4c5c13`; tanda 4b (15) `b78568d2`. Registro detallado en `02_DOC_REVIEW.md`.
- En la tanda 3 apareció un fallo de la librería (WinError 123 con SQLite `:memory:` en `DatabaseDocumentation`): me
  detuve y pregunté; el usuario eligió `/hotfix` aparte → `ae1e8098` (test primero, puerta completa).
- Banco: tablas temporales `docsn2_*` en MariaDB, MySQL, Oracle, PostgreSQL y SQL Server; borradas (0 restos).
- `.ai/CURRENT_STATE.md`: D2 hecho; H2 (hotfix sin publicar) y D3 (hallazgos de código) añadidos.
- Puerta de cierre: ruff, ruff format, mypy (334 ficheros), `python -m build`, pytest sin URLs del banco (5734 passed,
  531 skipped; `build/logs/docsn2_close_pytest_sin_banco.txt`) y con ellas + `JAVA_HOME` jdk-25 (6258 passed, 7 skipped, 1 aviso de jaydebeapi; `docsn2_close_pytest_con_banco.txt`); `zensical build --strict` y comprobador sin hallazgos en las 82 páginas.

- Tras el cierre, decisiones del usuario sobre D3 (2026-10-11): D3.1 excepciones reservadas (retirada en 2.0.0),
  D3.2 hotfix `2e23e8bb` (sesión `2026-10-11-hotfix-doc-render-error`), D3.3 a 1.2.0, D3.4 docstrings (`69445300`).
  Subido el `NEXT_SESSION_PROMPT.md` de `2026-10-10-api-1-0-final` (`82b88fd7`).
- VERSION 1.1.1 (`/version-closure`): `pyproject.toml`, CHANGELOG `[1.1.1] - 2026-10-11`, README, `docs/index.md`,
  `docs/roadmap.md`, pie de `docs/architecture.md`, `CURRENT_STATE.md` y `SESSIONS_DIGEST.md`. Puerta: ruff, format,
  mypy, `zensical build --strict`, `python -m build` (1.1.1), pytest sin banco 5735 passed / 531 skipped
  (`build/logs/v111_pytest_sin_banco.txt`) y con banco 6259 passed / 7 skipped (`v111_pytest_con_banco.txt`).

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| REQUEST | `.ai/sessions/2026-10-10-docs-review-nivel-2/00_REQUEST.md` | emitido |
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-10-10-docs-review-nivel-2/PLAN_AUDIT_PLAN.md` | aprobado |
| Registro de revisión | `.ai/sessions/2026-10-10-docs-review-nivel-2/02_DOC_REVIEW.md` | completado |
| Herramientas | `.ai/sessions/2026-10-10-docs-review-nivel-2/tools/` | completado |
| Docs | 80 páginas corregidas o verificadas + 2 consolidadas (borradas) | completado |
| Hotfix | `src/util_bbdd/doc/infrastructure/runtime/output_runtime.py` (+ test, CHANGELOG) | completado |
| Logs | `build/logs/docsn2_*`, `build/logs/hotfix_docname_*` | completado |

## Directrices para Futuras IAs
- **[docs]**: el comprobador de imports/métodos está en `tools/doc_check.py` de esta sesión (no en `scripts/`); sigue
  las inclusiones `--8<--` de `docs/examples/*.md` y usa `tools/doc_check_allow.txt` para los bloques «antes»
  intencionados (por `path:línea`: hay que actualizarla si se editan esas páginas). Candidato a `scripts/` con test.
- **[docs]**: en estas páginas casi no hay errores de import; los errores están en tablas y prosa. Lo que más falla:
  firmas «simplificadas» con parámetros que no existen, listas de motores sin MySQL, excepciones que el código nunca
  lanza (`PoolExhaustedError`, `DiffReportGenerationError`), cifras sin fuente, instalación con la forma de PyPI y
  descripciones anteriores a ADR-003 (`INFORMATION_SCHEMA`, `COLUMNPROPERTY`, `VIEW_DEFINITION`). Contrastar siempre
  con `inspect.signature`, `grep raise` y una ejecución.
- **[managers]**: una consulta fallida (`execute_*`) llega como `DatabaseOperationError` con el error del driver en
  `__cause__`, no como `QueryError` ni `ConnectionError`. Con pool, un fallo de conexión al crear el manager llega como
  `DatabaseConfigurationError`; `ConnectionError` solo con conexión única.
- **[async]**: `AsyncDatabaseManager` inicializa de forma perezosa (la primera operación llama a `init()`); HSQLDB
  falla con `NotImplementedError` (no hay caída a sync); el pool async de SQLite es una conexión con semáforo.
- **[connection]**: los parámetros de pool válidos por motor son los campos de `*PoolConfig` de
  `connection/config.py`; una clave ajena (p. ej. `max_overflow` en PostgreSQL) da `ValidationError` al construir el
  manager (sync y async).
- **[bulk]**: `ParallelBulkLoader(disable_constraints=True)` es la forma de desactivar constraints en carga paralela;
  envolver `loader.load()` en el `maintenance_scope` de otra `BulkCrud` no afecta a los workers (en MySQL/MariaDB
  `FOREIGN_KEY_CHECKS` es de sesión).
- **[examples]**: los ejemplos con hosts de relleno se ejecutan con copias que sustituyen `conn_params`
  (`run_bench_example.py` del scratchpad de esta sesión es el patrón); los schemas del banco están vacíos: sin tablas
  temporales, un ejemplo de `migrate`/`dump` «funciona» sin probar nada.
- **[tooling]**: en Windows, redirigir la salida de un ejemplo con emojis a fichero falla con `UnicodeEncodeError`
  (cp1252): usar `PYTHONUTF8=1`. `gen_arquitectura_capas.py` deja los SVG/CSS como modificados solo por fin de línea
  (`git diff` vacío; `git checkout --` los restaura).
- **[entorno]**: la instalación editable de este equipo es de v0.29.0 (`importlib.metadata.version`); el código se
  carga de `src/`. Reinstalar con `pip install -e ".[dev,docs]"` antes de verificar versiones.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Publicar v1.1.1: commits locales en `develop` (docs, los hotfix `ae1e8098` y `2e23e8bb`, D3 y la release); push, tag y release requieren autorización.
- D3 (hallazgos de código, en `02_DOC_REVIEW.md` § Fuera de alcance) y A2 (`driver_name` de SQL Server): por decidir.
