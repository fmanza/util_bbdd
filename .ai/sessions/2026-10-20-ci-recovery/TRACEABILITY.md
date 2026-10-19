# TRACEABILITY

## Session metadata
- id: 2026-10-20-ci-recovery
- fecha: 2026-10-19 / 2026-10-20
- rama: develop
- skill: hotfix + tech_debt (CI) + version_closure
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
Tras hacer públicos util_bbdd_web y util_bbdd (las Actions de los repos privados no arrancaban por facturación):
relanzar el CI de util_bbdd, corregir lo que fallase («si»), fijar pandas-stubs, opción A para el CI (entorno de
referencia completo) y `/version-closure` sin inputs (supuestos: v4.0.1, sesión nueva).

## Context supplied
- `gh run view` de los runs fallidos (anotación de facturación; luego log de mypy y de pytest)
- `.github/workflows/tests.yml`, `pyproject.toml`, `.github/instructions/sync.instructions.md`
- `.github/prompts/web_project_bootstrap.prompt.md` (commit `f6e80675`, misma jornada)

## AI output summary
- Diagnóstico: todos los runs desde hacía días fallaban sin arrancar («recent account payments have failed or your
  spending limit…»); con el repo público, el CI mostró un error real de mypy.
- `ae281f7c` hotfix(audit): `operacion_mas_lenta` con `Series.argmax()`; RCA: pandas-stubs 3.0.5.260914 (CI) no
  acepta el `Hashable` de `idxmax()` en `.loc`; el venv tenía 3.0.0. Reproducido subiendo los stubs en el venv; 2 tests.
- `6d3532d7` `pandas-stubs>=3.0.5,<3.1`.
- `3b82291f` `test_docs_build_plugin.py` (`importorskip("mkdocs")`) y `test_dataframe_to_sql_records.py` (caso
  `string[pyarrow]` condicional): rompían la recogida con solo `.[dev]` y pytest abortaba toda la suite.
- Venv limpio `.[dev]`: 75 failed + 20 errors por drivers (pyodbc, mariadb, pymysql, psycopg, graphviz, greenlet…).
  Decisión del usuario: opción A (entorno completo en el CI).
- `6a1895b6` dorado `sqlite_doc.txt` sin la ruta de `tempfile.gettempdir()` (fallaba en Linux): `<sqlite_db>`.
- `5ec6b29d` extras `test-drivers` y `dev-full`; `tests.yml` con Graphviz (apt/choco), `libmariadb-dev`, `unixodbc` y
  `.[dev-full]`; SHARED y `onboarding_dev.md` con el entorno de referencia nuevo.
- Verificación: venv limpio `.[dev-full]` Windows 3.14 y contenedor Linux 3.12 → 6374 passed, 596 skipped; tras el
  push, CI de GitHub en verde en las 6 combinaciones con el mismo recuento, `package`, Docs y Docs ZIP.
- Releases relanzadas: `docs-v4.0.0` (Docs ZIP) y, con el push de tags del usuario, `v3.4.1` y `v4.0.0`.
- VERSION 4.0.1: campos de `sync.instructions.md` § 4, diagrama regenerado (342 ficheros, sin cambios).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Hotfix mypy | `src/util_bbdd/audit/analytics.py`, `tests/unit/test_audit_subsystem.py` | completado |
| Recogida sin extras | `tests/unit/test_docs_build_plugin.py`, `tests/unit/bulk/test_dataframe_to_sql_records.py` | completado |
| Dorado SQLite | `tests/integration/metadata/characterization/test_metadata_golden.py`, `tests/fixtures/metadata_golden/sqlite_doc.txt` | completado |
| CI | `.github/workflows/tests.yml`, `pyproject.toml` (extras) | completado, verde en GitHub |
| Versión | CHANGELOG, `pyproject.toml`, README, `docs/{index,roadmap,architecture}.md`, `.ai/CURRENT_STATE.md`, `SESSIONS_DIGEST.md` | completado |
| Logs | `build/logs/{hotfix_mypy_pandas_stubs,ci_dev_only_venv,ci_full_venv,ci_dev_full_venv,ci_linux_dev_full}.txt` | generado |

## Directrices para Futuras IAs
- **[ci]**: el entorno de referencia es `pip install -e ".[dev-full]"` + Graphviz del sistema (+ `libmariadb-dev` y `unixodbc` en Linux); con solo `.[dev]` fallan ~95 tests por drivers. El venv del usuario lo tiene todo y por eso no lo detecta.
- **[ci]**: valida cambios de dependencias o CI en un venv limpio del scratchpad y en un contenedor `python:3.12-slim` (copiar el repo con `tar` excluyendo `venv/`, `build/`, `site/`, `dist*`, `.git`); ambos dieron exactamente el recuento del CI.
- **[ci]**: hay `gh` autenticado (`"/c/Program Files/GitHub CLI/gh.exe"`, no está en el PATH de Bash): tras cada push del usuario, `gh run list` / `gh run view <id> --log-failed`. Un job que «falla» en 2-3 s con 0 pasos es facturación, no código (`gh run view <id>` muestra la anotación).
- **[ci]**: los repos `util_bbdd` y `util_bbdd_web` son públicos desde 2026-10-20 (Actions gratis); `docs-zip-release.yml` crea o actualiza una release pública en cada push a develop/main que toque `docs/`, `mkdocs.yml` o `pyproject.toml`.
- **[tests]**: pytest aborta toda la ejecución si un módulo falla al importarse: los tests que dependan de extras deben usar `pytest.importorskip(...)` al principio o condicionar el caso (`find_spec`).
- **[tests]**: los dorados no pueden llevar rutas de `tempfile.gettempdir()`; `_doc_text` sustituye la ruta del `.db` de SQLite por `<sqlite_db>`.
- **[tipado]**: `pandas-stubs` tiene tope `<3.1`; al subirlo, `mypy src tests/unit/test_protocol_conformance.py` con la versión nueva antes de cambiar el rango. Con 3.0.5, `.loc[serie.idxmax(), col]` no tipa: usar `serie_col.iloc[serie.argmax()]`.
- **[versión]**: un script que reescriba ficheros con `Path.read_text/write_text` los deja en LF; con `core.autocrlf=true` git solo ve los cambios reales, pero conviene preferir `Edit`.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Tag anotado `v4.0.1`, push de `develop` y del tag, fast-forward de `main` (lo hace el usuario).
- Instrucciones de instalación a `@v4.0.1` cuando exista el tag (hoy `@v4.0.0`, válidas).
- util_bbdd_web sigue con el wheel 4.0.0; actualizarlo a 4.0.1 es opcional (sin cambios de API).
- Windows 3.12 tarda ~9,5 min en el CI frente a 2-4 min del resto (candidato a `/tech-debt`).
