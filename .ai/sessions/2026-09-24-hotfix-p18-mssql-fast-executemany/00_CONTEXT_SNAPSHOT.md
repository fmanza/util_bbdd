# CONTEXT SNAPSHOT

## Contexto del repositorio revisado
- `.ai/sessions/2026-09-23-performance-audit-bulk/02_BASELINE_MOTORES_REALES.md` (evidencia de P-01 y P-18)
- `src/util_bbdd/bulk/_execution/batch.py` (`_register_fast_executemany`, `_fast_executemany_listener`), `src/util_bbdd/bulk/crud.py`
- SQLAlchemy 2.0.50: `connectors/pyodbc.py:190-216` (`do_set_input_sizes`), `dialects/mssql/pyodbc.py:336-357, 656-678, 735-738`, `sql/crud.py:1659-1673`

## Estado actual observado
- Árbol limpio tras los commits `290c483` y `e22e3bb`.
- Contenedores del banco (`util_bbdd_bench_*`) en marcha; ODBC Driver 18 instalado en el host.
- Ningún test unitario cubría fast_executemany.

## Estado Git relevante
- Rama activa: develop
- Cambios locales pre-existentes: ninguno
- Último tag / versión publicada: v0.10.0 (release 0.11.0 en `CHANGELOG.md`)

## Clasificación metodológica
- Tipo principal: hotfix
- Estado real de alcance: acotado (1 función + docstring)
- Consecuencia: se procede.

## Gate G0 · Context Ready
Veredicto: GO
