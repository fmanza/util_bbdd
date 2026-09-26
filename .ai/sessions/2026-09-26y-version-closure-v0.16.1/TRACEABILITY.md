# TRACEABILITY

## Session metadata
- id: 2026-09-26y-version-closure-v0.16.1
- fecha: 2026-09-26
- rama: develop
- skill: version-closure
- origen: el usuario aceptó cerrar v0.16.1 tras resolver los hallazgos del audit-code

## Versión
- **v0.16.1** (PATCH): correcciones sin cambios de API.

## Contenido (sobre v0.16.0)
- `6a6ce66` tests de integración de `dump` contra servidores reales (28) y `bench_bulk` con columnas en minúsculas en SQL Server.
- `c0b54e7` PD-13: DECIMAL exacto con pymssql (notación fija).
- `5284cf5` informe del audit-code de `dump`/`bulk` desde v0.15.0 (APROBADO CON CONDICIONES).
- `4c7f0de` A1–A3: cierre de lectores al fallar la escritura; `strip_strings` con `numpy.str_`.

## Checklist (`.github/instructions/sync.instructions.md`)
- [x] `ruff check` y `ruff format --check`: limpios.
- [x] `mypy src tests/unit/test_protocol_conformance.py`: sin errores.
- [x] `pytest`: **5067 passed / 193 skipped** sin URLs de servidor (165 previos + 28 de integración de `dump`).
- [x] `pytest tests/integration` con las URLs del banco (5 servidores): **331 passed, 0 skipped**.
- [x] `python -m build`: `util_bbdd-0.16.1`.
- [x] `pyproject.toml` → `0.16.1`; `CHANGELOG.md`: `[0.16.1] - 2026-09-26` con introducción, *Fixed* y *Changed*; `[Unreleased]` vacío.
- [x] `mkdocs build --strict`: sin errores.

## Commits y push
- `812a020` `release: v0.16.1 - …` y tag anotado `v0.16.1`; después, este `docs(ai)`.
- Push de `develop` y del tag `v0.16.1` a `origin` (autorizado por el usuario; `main` no se toca). Remoto sin divergencia antes del push (`d510d1b`).

## Rollback
- `git push origin :refs/tags/v0.16.1` si nadie lo ha consumido y `git revert 812a020`; cada arreglo tiene su propio commit.

## Pendientes al cierre
- Roadmap Fase 3: Q8 (medir antes), Q9 para SQL Server, 3.3 (Oracle `APPEND_VALUES`).
- Matriz de motores de `CURRENT_STATE.md`: separar `migrate` y `dump`.
- Contenedores del banco en marcha con los datos `large`.

## Veredicto final
Veredicto: CLOSED
