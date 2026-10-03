# CONTEXT SNAPSHOT

## Contexto del repositorio revisado
- `.github/prompts/metadata_centralization_audit_and_refactor.prompt.md` (contrato de salida)
- `.github/instructions/architecture.instructions.md` § «Reglas de acceso a metadatos» (Reglas #1–#6)
- `.github/agents/plan-architect.agent.md`, `.github/agents/performance-auditor.agent.md`
- `.ai/architecture.md`, `.ai/runtime.md`, `.ai/CURRENT_STATE.md`
- `scripts/gen_arquitectura_capas.py` (`LAYER`), `docker-compose.bench.yml`, `scripts/bench_env.example.sh`
- Código: `metadata/` completo, `managers/` (sync/async, estrategias de fetch, contexto, caché), `query/` (registry,
  resolver), `validators/base_validator.py`, `data/sql_queries.json`, consumidores en `bulk/`, `comparar/`, `dump/`,
  `migrate/`, `doc/`, `analysis/`, `connection/`
- Fuentes externas (consultadas 2026-10-03): ver `02_BASELINE_RENDIMIENTO.md` § Fuentes

## Estado actual observado
- Versión `0.30.0` (`pyproject.toml`); HEAD `c1e5c1f`. El prompt se redactó sobre v0.29.0: entre medias se cerró la
  auditoría de `comparar` (v0.30.0), que movió a `metadata/` el SQL de routines de `comparar/_routine_fetchers.py` y
  añadió consultas por schema para SQL Server. El §2 del prompt queda parcialmente desfasado (ver `01_INVENTARIO.md` §0).
- Tests, lint y mypy: no ejecutados en esta sesión (solo lectura de `src/`); la sesión no cambia código.
- Banco: 5 contenedores `util_bbdd_bench_*` en marcha (PostgreSQL 17, MySQL 8.4, MariaDB 11.4, SQL Server 2022,
  Oracle 23 Free). Se crean schemas propios `zz_md_*` / `zz_util_bbdd_md_*` / usuarios `ZZ_MD_*` para el baseline.

## Estado Git relevante
- Rama activa: `develop`
- Cambios locales pre-existentes: ninguno ajeno al inicio de la sesión (solo `.ai/sessions/2026-10-03-metadata-centralization/`, nuevo)
- Último tag / versión publicada: `v0.30.0` (`8e70dc2`)

## Clasificación metodológica
- Tipo principal: refactor transversal + performance (prompt `metadata_centralization_audit_and_refactor`)
- Estado real de alcance: amplio pero acotable por grupos (A–H del prompt)
- Consecuencia: PLAN + AUDIT_PLAN en esta sesión; IMPLEMENT por grupos tras aprobación explícita

## Gate G0 · Context Ready
Veredicto: GO
Condiciones pendientes (si aplica):
- Ninguna para PLAN; IMPLEMENT queda bloqueado hasta aprobación del AUDIT_PLAN.
