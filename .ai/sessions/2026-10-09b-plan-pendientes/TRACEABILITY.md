# TRACEABILITY

## Session metadata
- id: 2026-10-09b-plan-pendientes
- fecha: 2026-10-09
- rama: develop
- skill: plan (PLAN + AUDIT_PLAN) + P0 (mantenimiento)
- fase: PLAN y AUDIT_PLAN de los pendientes tras `drivers-connections-audit`; ejecución de P0

## Prompt issued
```text
Preparemos un PLAN y AUDIT_PLAN para tratar lo pendiente, pregunta lo que necesites
```
Respuestas del usuario (2 rondas): alcance completo (mantenimiento, deuda pequeña, F3 con CA propia, M5/F5/H1); `init_command` propio en async; WARNING para `trust_cert` con pymssql; conservar `zz_md_*`; recrear MariaDB del banco; F5 con semántica async; HSQLDB en contenedor; M5 en una consulta + falso MIXED. Aprobación del plan y de P0: «si».

## Context supplied
- `.ai/CURRENT_STATE.md`, `docs/roadmap.md` (deuda registrada), banco Docker, ramas y merges de git

## AI output summary
- Verificado: PR #19 (Zenical) fusionada (`c6d765a8`); código de la PR #18 (`9a71e056`) en `main` y `develop` (estado de la PR sin comprobar: no hay `gh`); `cd22520` en `origin/develop`; v0.31.0 con tag; la sección de criterios de aceptación ya no existe en el estándar funcional.
- `PLAN_AUDIT_PLAN.md` (P0–P5, GO_CONDICIONAL), commit `b5299a93`.
- P0: 14 schemas `zz_it_dump_*` borrados del PostgreSQL del banco (patrón validado con regex antes de cada `DROP`); quedan `zz_md_50/500/5000`. `CURRENT_STATE.md` sin pendientes obsoletos (Zenical, PR #18/#19, criterios, `cd22520`, v0.31.0).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-10-09b-plan-pendientes/PLAN_AUDIT_PLAN.md` | emitido |
| P0 | `.ai/CURRENT_STATE.md`; banco PostgreSQL | hecho |

## Directrices para Futuras IAs
- **[banco/schemas]**: los `zz_it_dump_<hex8>` de PostgreSQL los crea `tests/integration/test_dump_engines.py` y los borra en `finally`; si aparecen, son de ejecuciones interrumpidas y se pueden borrar. Los `zz_md_*` (y `zz_util_bbdd_md_*` en MySQL, `ZZ_MD_*` en Oracle) son los datos de `scripts/bench_metadata.py`: no borrarlos sin preguntar.
- **[estado/PRs]**: sin `gh` en el equipo, comprobar si una PR está integrada con `git merge-base --is-ancestor <commit> origin/develop` y `git log --merges --all | grep '#<n>'`.

## Veredicto final
Veredicto: CLOSED (plan completado el 2026-10-09)
Resultado por bloque:
- P0 mantenimiento: hecho (`cd0b3950`).
- P1 → v0.39.2 (`.ai/sessions/2026-10-09c-hotfix-p1-pendientes/`).
- P2 → v0.39.3 (`.ai/sessions/2026-10-09d-charset-diagnosis/`).
- P3 → v0.40.0 con excepción de Oracle acordada (`.ai/sessions/2026-10-09e-engine-url-parity/`).
- P4 → sin cambio de código: F3 cerrado como límite del driver; premisa de rutas absolutas refutada; exención de `localhost` del conector sync comprobada (`.ai/sessions/2026-10-09f-mariadb-tls-own-ca/`).
- P5 → H1 cerrado con HSQLDB en red (`.ai/sessions/2026-10-09g-hsqldb-server/`).
Pendientes: push de `develop` y tag `v0.40.0`; publicar el issue del ORA-03106 (usuario).
