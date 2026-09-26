# TRACEABILITY

## Session metadata
- id: 2026-09-26t-version-closure-v0.16.0
- fecha: 2026-09-26
- rama: develop
- skill: version-closure
- origen: el usuario eligió «cerrar versión y hacer push» tras replantear Q9 (Fase 3)

## Prompt issued
```
/version-closure — cerrar la versión con el trabajo de las sesiones 2026-09-25b a 2026-09-26s y push a origin/develop.
```

## Versión
- **v0.16.0** (MINOR): API pública nueva sin cambios incompatibles (`DumpConfig.write_batch_size`; `strip_strings` en `BulkCrud` y `ParallelBulkLoader`), más cambios de comportamiento observables listados en el CHANGELOG («Cambios de comportamiento a revisar al actualizar»).

## Contenido (sesiones `2026-09-25b` a `2026-09-26s`)
- **Banco y auditoría**: `scripts/bench_dump.py` real (incl. `mariadb_connector`); auditoría delta sobre v0.15.0.
- **Fixed (12)**: PD-01 (SQL Server columnas en minúsculas), PD-02 + PD-03 (PK sync con `target_schema`, TRUNCATE en PG), PD-04 (validación real de FK en PG), PD-05 (fidelidad de datos), PD-06 (SQLite sin paralelismo), PD-07 (aviso de origen SQLite), PD-08 (reflexión recursiva por FK), PD-09 (error tapado en MySQL/MariaDB), PD-10 (DECIMAL de 38 dígitos en SQL Server), PD-11 (PK sync con rangos), PD-12 (UPDATE por staging sin BD por defecto).
- **Rendimiento**: Q1 (Oracle `arraysize`), Q2 (cursor de servidor), Q3 (solape lectura/escritura), Q4 (guía de `parallel_pk_ranges`), PF-09 (MariaDB Connector/Python), Q5 (`write_batch_size`), Q6 (guía de `manage_indexes`), 2.3 (aviso LOB), 3.4 (resumen de auditoría incremental). Q9 medido y replanteado.
- **Commits ajenos incluidos en el push**: `518f3e4`, `633b1c2`, `0ea1047` (configuración IA) y `1e46bb4` (docs de reutilización), hechos en paralelo fuera de esta sesión.

## Checklist (`.github/instructions/sync.instructions.md`)
- [x] `ruff check src tests` y `ruff format --check`: limpios.
- [x] `mypy src tests/unit/test_protocol_conformance.py`: sin errores (342 ficheros).
- [x] `pytest`: **5054 passed / 165 skipped** sin URLs de servidor (los mismos 165 saltos que en v0.15.0).
- [x] `pytest tests/integration` con las URLs del banco (`scripts/bench_env.example.sh`, 5 servidores): **303 passed, 0 skipped**.
- [x] `python -m build`: `util_bbdd-0.16.0` (sdist y wheel).
- [x] `pyproject.toml` → `0.16.0`; `requires-python` sin cambios.
- [x] `CHANGELOG.md`: `[Unreleased]` → `[0.16.0] - 2026-09-26` con introducción, cambios de comportamiento y *Fixed*/*Changed*/*Added*; `[Unreleased]` nuevo vacío. No existen `docs/CHANGELOG.md` ni `COMPATIBILITY.md`.
- [x] `mkdocs build --strict`: sin errores (solo el aviso informativo del equipo de Material for MkDocs).

## Resultado medido (volcado de 3,5M filas, contenedores locales)

| Motor | v0.15.0 | v0.16.0 | Memoria pico |
|---|---|---|---|
| PostgreSQL | 19,1 s | ≈ 12,5 s | 417 → ≈ 190 MB |
| MariaDB (Connector/Python) | ≈ 78 s | ≈ 24 s | 192 → 158 MB |
| MariaDB (PyMySQL) | 52,9 s | ≈ 37,5 s | 859 → 162 MB |
| MySQL | 57,0 s | ≈ 38 s | 859 → 162 MB |
| Oracle | 57,6 s | ≈ 32–38 s | 171 MB |
| SQL Server | 65,8 s | ≈ 57–64 s (≈ 34–44 s con `parallel_pk_ranges=4`) | 164 MB |
| SQLite (desde PG) | 21,3 s | ≈ 20 s | 421 → 176 MB |

## Commits
- `693f9c2` `release: v0.16.0 - …` (CHANGELOG y `pyproject.toml`) y tag anotado `v0.16.0` sobre él.
- Commit `docs(ai)` con esta sesión, `CURRENT_STATE`, `INDEX` y `SESSIONS_DIGEST`.

## Rollback
- Antes del push: `git tag -d v0.16.0` y `git revert 693f9c2`.
- Tras el push: borrar el tag remoto (`git push origin :refs/tags/v0.16.0`) si nadie lo ha consumido y `git revert` del release; cada hallazgo tiene su propio commit para revertirlo por separado.

## Pendientes al cierre
- Roadmap Fase 3: Q8 (ruta sin pandas, medir antes), Q9 para SQL Server (consultas propias a `sys.*`), 3.3 (Oracle `APPEND_VALUES`).
- `scripts/bench_bulk.py` crea columnas en MAYÚSCULAS en SQL Server (no detectaría un fallo tipo PD-01).
- La matriz de motores de `CURRENT_STATE.md` es la de `migrate`; conviene separar la de `dump`.
- Contenedores del banco en marcha con los datos `large` en `dump_src`/`dump_dst`.

## Directrices para Futuras IAs
- **[cierre]**: igual que v0.15.0: `release:` solo con CHANGELOG y `pyproject.toml` + tag anotado; después `docs(ai)`; push de `develop` y del tag (no de `main`).

## Veredicto final
Veredicto: CLOSED
