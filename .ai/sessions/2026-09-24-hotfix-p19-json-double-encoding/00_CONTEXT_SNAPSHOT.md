# CONTEXT SNAPSHOT

## Contexto del repositorio revisado
- `.ai/sessions/2026-09-23-performance-audit-bulk/02_BASELINE_MOTORES_REALES.md` (P-19)
- `src/util_bbdd/bulk/crud.py` (`__prepare_insert_operation`, `__resolve_stream_insert`, `__prepare_update_operation`)
- `src/util_bbdd/bulk/normalize.py` (`normalize_sql_literal`: dict/list → `json.dumps`)
- `src/util_bbdd/bulk/_support/sql_helpers.py`

## Estado actual observado
- Árbol limpio tras `9bc03de` (refactor P-02) y `a649f50`.
- Contenedores del banco en marcha (PostgreSQL 17, MySQL 8.4, MariaDB 11.4, SQL Server 2022, Oracle 23).

## Estado Git relevante
- Rama activa: develop
- Cambios locales pre-existentes: ninguno
- Último tag / versión publicada: v0.10.0 (release 0.11.0 en `CHANGELOG.md`)

## Clasificación metodológica
- Tipo principal: hotfix
- Estado real de alcance: acotado (enlace de parámetros de columnas JSON)
- Consecuencia: se procede.

## Gate G0 · Context Ready
Veredicto: GO
