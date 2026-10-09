# TRACEABILITY

## Session metadata
- id: 2026-10-09-drivers-connections-audit-fase6
- fecha: 2026-10-09
- rama: develop (sobre `cd8cd17c`, v0.39.1)
- skill: version_closure
- fase: FASE 6 (VERSION) de `drivers-connections-audit`: cierre de la auditoría, sin cambios en `src/`

## Prompt issued
```text
/version-closure

Objeto: drivers-connections-audit SKILL — FASE 6 VERSION (cierre de la auditoría)
Alcance: versiones v0.35.9..v0.39.1 (FASE 4 + hotfixes) y sesiones .ai/sessions/2026-10-09-*
Entregar: cierre de la skill (estado final en SKILL.md y .claude/DRIVERS_CONNECTIONS_AUDIT_EXECUTION.md), ADR de las decisiones de FASE 3 (validación única desde *Config, política de pool de los Engine, catalog_charset_mode, TLS MariaDB), deuda registrada (F3, F4, F5 de FASE 5; M5; H1; init_command personalizado ignorado en MariaDB async; trust_cert en pymssql) en el roadmap, rollback y Directrices para Futuras IAs
Sin bump de versión salvo que el cierre cambie src/ (no debería)
```
Inputs: cambios = FASE 4 completa + hotfixes; versión = v0.39.1 (sin bump: solo documentación); archivos = ver tabla; sesión = esta carpeta.

## Context supplied
- `.github/agents/version-closer.agent.md`, `.github/prompts/version_closure.prompt.md`, `.github/instructions/sync.instructions.md`
- `.ai/sessions/2026-10-09-*` y `audit_phase_5.md`

## AI output summary
- Desviación consciente del agente Version Closer (que solo edita CHANGELOG, TRACEABILITY y campos de versión): el usuario pidió explícitamente ADR, roadmap y cierre de la skill, así que se editan `docs/adr/`, `docs/roadmap.md`, `mkdocs.yml`, la skill y la guía de ejecución. Sin cambios en `src/` ni `tests/`.
- `docs/adr/ADR-005-conexiones-multimotor.md` (ACEPTADO) y entrada en `mkdocs.yml`.
- `docs/roadmap.md` § «Deuda registrada — conexiones multimotor»: F3, F4, F5, M5, H1, `init_command` en MariaDB async, `trust_cert` en pymssql.
- `SKILL.md` 1.0.4 → 1.0.5 (estado final, cerrada); `CORRECTIONS_APPLIED.md`; `.claude/DRIVERS_CONNECTIONS_AUDIT_EXECUTION.md`.
- `CHANGELOG.md` [0.39.1] § Documentation (añadido tras el tag; solo documentación).
- `zensical build --strict` OK (`build/logs/drivers_audit_fase6_zensical.txt`); tests de documentación OK.

## Resumen de la auditoría

| Fase | Resultado | Versiones |
|---|---|---|
| 1 | RECHAZADO (5 P0) | v0.35.4 |
| fixes FASE 1 | P0, P1, P2 cerrados | v0.35.5–v0.35.8 |
| 2-3 | Opción B acotada; GO_CONDICIONAL; Q2 cambiada por el usuario a `ValidationError` directo | — |
| 4 | B6, B5, B4, B3, hotfix Oracle async, B1, CS, B2 | v0.35.9–v0.39.0 |
| 5 | APROBADO CON CONDICIONES (F1–F5, P3) | — |
| hotfix F1/F2 | | v0.39.1 |
| 6 | ADR-005, deuda en roadmap, skill cerrada | — |

Tests: 5279 (v0.35.8) → 5397 (v0.39.1). `tests/integration`: 552 passed, 10 skipped en todas las versiones.

## Rollback

- Cada bloque es un commit y un tag (`v0.35.9` … `v0.39.1`); revertir un bloque = `git revert <commit>` + nueva versión patch. Sin migraciones de datos ni de esquema en ninguno.
- Bloques con cambio de comportamiento (revertir si un consumidor lo necesita): `5753148e` (v0.36.0, pool de los Engine), `fc74e35a` (v0.37.0, validación async y `search_path`). Revertir v0.37.0 obliga a revertir antes `cd8cd17c` (v0.39.1), que depende de su validación.
- Este cierre (solo documentación) se revierte con `git revert` sin efecto en el código.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| ADR | `docs/adr/ADR-005-conexiones-multimotor.md`, `mkdocs.yml` | creado |
| Deuda | `docs/roadmap.md` | sección nueva |
| Skill | `.github/skills/drivers-connections-audit/SKILL.md` (1.0.5), `CORRECTIONS_APPLIED.md` | cerrada |
| Guía | `.claude/DRIVERS_CONNECTIONS_AUDIT_EXECUTION.md` | estado final |
| CHANGELOG | `CHANGELOG.md` [0.39.1] § Documentation | |

## Directrices para Futuras IAs
- **[conexiones/decisiones]**: las decisiones de diseño de conexiones (validación única, pool de los Engine, `catalog_charset_mode`, TLS MariaDB) están en `docs/adr/ADR-005-conexiones-multimotor.md`; la deuda residual, en `docs/roadmap.md` § «Deuda registrada — conexiones multimotor».
- **[conn_params]**: un parámetro nuevo de conexión = campo en la `*Config` de `connection/config.py` + entrada en `data/database_types.json`; `allowed_keys` y los tests de `test_conn_params_whitelist.py` hacen el resto.
- **[puntos canónicos]**: URL y redacción de Engine → `factory/_url.py`; pool de Engine → `factory/_pool_policy.py`; kwargs de aiomysql → `connection/_aiomysql.py`; cierre de pools sync → `SyncPoolCloseMixin` (`connection/close.py`); DSN Oracle → `connection/oracle/_dsn.py`; TLS MariaDB → `MariaDBConnectionConfig._tls_kwargs`.
- **[método]**: los bloques sin cambio funcional se probaron comparando salidas antes/después con la versión de HEAD cargada en paralelo; los que tocan drivers, contra el banco (5 servidores Docker) antes de cerrar. Las premisas sobre drivers se verificaron siempre contra el driver real (3 resultaron falsas: `encoding_errors`, `create_pool_async`, `ssl_ca` sin verificación).
- **[skills]**: `drivers-connections-audit` está cerrada (1.0.5); si se reutiliza, contrastar antes sus premisas con el código.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Push de `develop` (commits `6dab3e2b` FASE 5, `cd8cd17c` v0.39.1 y el de este cierre) y tag `v0.39.1`.
- Deuda registrada en `docs/roadmap.md` (sin fecha).
- `.ai/CURRENT_STATE.md` y `.ai/sessions/2026-10-08e-fix-drivers-p2b/TRACEABILITY.md` tienen cambios locales ajenos a esta sesión: no se tocaron.
