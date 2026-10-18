# TRACEABILITY

## Session metadata
- id: 2026-10-18-timing-decorator
- fecha: 2026-10-18
- rama: develop
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
Se quiere incorparar la función decoradora C:\Desarrollo\python\libs\util\src\util\timing\medir_tiempo.py como parte del
proyecto, actualmente se usa placeholder en algunas partes de la aplicación y queremos dejar deimportar el paquete util.
Queremo analizar el imnpacto dentro del actual desarrollo y ver si se puede mejorar tanto la función como su uso en la
aplicación. PLAN y AUDIT_PLAN

(Después: «IMPLEMENT con las recomendaciones dadas», «AUDIT_CODE», «si» a aplicar B1, B2 y D1 y pasar a VERSION.)

## Context supplied
- `CLAUDE.md` + `.github/SHARED_INSTRUCTIONS.md` (importado)
- `.github/prompts/new_feature.prompt.md` (contrato de fases)
- Origen: `C:\Desarrollo\python\libs\util\src\util\timing\medir_tiempo.py` y `util/conversion/conversor.py` (solo lectura)

## AI output summary
- PLAN/AUDIT_PLAN: único uso de `util` en `src/` = `bulk/crud.py` (try/except con placeholder, 6 métodos públicos de
  `BulkCrud`). `util` era dependencia obligatoria `git+…@develop` (repo privado; bloquea PyPI; 4 workflows con `GH_PAT`).
  Comprobado con `reveal_type`: los 6 métodos decorados eran `Any` para mypy. Bug de redondeo en
  `Conversor.formatear_segundos` (59,9996 s → `00:00:60.000`). `docs/api/bulk_crud.md` afirmaba en falso que sin `util`
  el CSV registraba 0 ms. Veredicto GO_CONDICIONAL; decisiones D1 privado en `_core`, D2 CI en commit aparte, D3
  rechazar `async`.
- IMPLEMENT: `src/util_bbdd/_core/timing.py` (nuevo; `ParamSpec`, logger del módulo decorado, `(con error)`,
  `isEnabledFor`, `TypeError` para `async`, `_format_seconds` redondeando a ms). `crud.py`: fuera el placeholder, 6×
  `@medir_tiempo()`. `pyproject.toml`: fuera `util` y su override; `disallow_any_decorated` en `util_bbdd.bulk.crud`.
  Guarda `test_library_does_not_import_the_external_util_package`. Scripts del banco, docs, CHANGELOG `[Unreleased]`.
  CI: eliminados 6 pasos `Configure git credentials for private deps`; aviso histórico en las 3 guías
  `.github/GITHUB_ACTIONS_*.md`.
- AUDIT_CODE: guarda de mypy verificada con un decorador `-> Any` temporal (6 errores, revertido). Hallazgos: B1
  generadores aceptados (medían su creación), B2 `AttributeError` con `functools.partial`/invocables, D1 engine sin
  `dispose()` en el test. Veredicto APROBADO CON CONDICIONES.
- Correcciones B1/B2/D1 aplicadas con 4 tests más (19 en `test_core_timing.py`).
- Puerta final (sin `util`, simulado con un `util` que lanza `ImportError` en `PYTHONPATH`, y sin URLs del banco):
  `ruff check` OK, `ruff format` sin cambios, `mypy src tests/unit/test_protocol_conformance.py` OK (340 ficheros),
  `pytest` 6266 passed / 542 skipped (`build/logs/timing_decorator_pytest.txt`), `zensical build --strict` sin avisos
  (`build/logs/timing_decorator_docs.txt`).

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Decorador | `src/util_bbdd/_core/timing.py` | completado |
| Uso | `src/util_bbdd/bulk/crud.py` | completado |
| Tests | `tests/unit/test_core_timing.py`, `tests/unit/test_architecture_import_rules.py` | completado |
| Config | `pyproject.toml` | completado |
| CI | `.github/workflows/{tests,docs,docs-release,integration}.yml`, `.github/GITHUB_ACTIONS_*.md` | completado |
| Docs | `docs/installation.md`, `docs/guides/onboarding_dev.md`, `docs/api/bulk_crud.md`, `docs/architecture.md`, `.ai/runtime.md` | completado |
| CHANGELOG | `CHANGELOG.md` `[Unreleased]` (Changed, Removed, Fixed) | completado |

## Directrices para Futuras IAs
- **[timing]**: el punto canónico para medir y registrar la duración de una función es
  `util_bbdd._core.timing.medir_tiempo` (privado, sin compromiso SemVer). No reintroducir `util.timing`: lo vigila
  `test_library_does_not_import_the_external_util_package`.
- **[timing]**: el mensaje sale en el logger del **módulo de la función decorada** (para `BulkCrud`,
  `util_bbdd.bulk.crud`, el mismo que `self.logger`): silenciarlo silencia también los `INFO` de `BulkCrud`.
- **[timing]**: `medir_tiempo` rechaza (`TypeError`) corrutinas, generadores y generadores async, porque llamarlos solo
  crea el objeto. Si hace falta medir algo async, añadir una variante explícita; no quitar el rechazo.
- **[bulk]**: el tiempo del decorador (llamada completa: reflexión, reparto paralelo) y `tiempo_seg` del CSV de
  auditoría (`perf_counter` alrededor de ejecutar o generar SQL en `crud.py`) son medidas distintas e independientes.
- **[tipado]**: un decorador con `-> Any` borra la firma del método para los consumidores (la librería lleva
  `py.typed`). `disallow_any_decorated` está activo solo en `util_bbdd.bulk.crud`; en todo `src` daría 5 falsos
  positivos (`contextmanager`/`lru_cache` con `Any` legítimo).
- **[ci]**: ya no hay dependencias privadas: los workflows no configuran credenciales git. El secreto `GH_PAT` puede
  revocarse.
- **[técnica]**: para probar «sin un paquete instalado» sin tocar el venv, anteponer en `PYTHONPATH` una carpeta con un
  paquete homónimo cuyo `__init__.py` lance `ImportError`.

## Version closure (2026-10-18)
- Commits de la sesión: `0356b780` (fix(bulk)) y `ed53629e` (chore(ci)); sin push.
- `/version-closure` → **3.1.0** (MINOR): `[Unreleased]` pasa a `## [3.1.0] - 2026-10-18` (incluye lo acumulado desde
  3.0.3: D4 de documentación, `/doc-generator`, umbral de `filtrar_multiple`). Campos de versión: `pyproject.toml`,
  `README.md` (cabecera y «Current Version»), `docs/index.md`, `docs/roadmap.md`, pie de figura de
  `docs/architecture.md` (340 ficheros según `scripts/gen_arquitectura_capas.py`, sin cambios en el SVG),
  `.ai/CURRENT_STATE.md` y `.ai/sessions/SESSIONS_DIGEST.md`.
- Las instrucciones de instalación siguen en `@v3.0.3` hasta que exista el tag `v3.1.0` (mismo criterio que R4).

## Veredicto final
Veredicto: CLOSED (AUDIT_CODE: APROBADO CON CONDICIONES → condiciones B1, B2 y D1 resueltas; versión 3.1.0 cerrada)
Pendientes al cierre:
- R5 (`.ai/CURRENT_STATE.md`): push de `develop`, CI en verde sin `GH_PAT`, tag `v3.1.0`, `main`, instalación a
  `@v3.1.0`, revocar el secreto `GH_PAT`.
- Fuera de alcance: `elapsed_ms` con `time.time()` (no monotónico) en `executors/sync_query_executor.py`,
  `executors/async_query_executor.py` y `query/resolver.py`.
