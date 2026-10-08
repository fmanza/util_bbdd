# TRACEABILITY

## Session metadata
- id: 2026-10-08-drivers-connections-audit-fase1
- fecha: 2026-10-08
- rama: develop
- skill: audit_code + version_closure (más corrección de la skill `drivers-connections-audit`)
- fase: FASE 1 (RECONNAISSANCE) de `drivers-connections-audit` vía `/audit-code` (PLAN + AUDIT_PLAN + AUDIT_CODE + VERSION); corrección de premisas de la skill; VERSION de cierre de sesión

## Prompt issued
```text
/audit-code

Objeto: drivers-connections-audit SKILL de util_bbdd
Fases: FASE 1 (RECONNAISSANCE) — Inventario de drivers, duplicidades, auditoría por motor
Alcance: src/util_bbdd/connection/**, src/util_bbdd/metadata/**, src/util_bbdd/_drivers/**, src/util_bbdd/managers/**
Motores: MariaDB, MySQL, PostgreSQL, Oracle, SQL Server, SQLite, HSQLDB
Aspectos: Seguridad, Rendimiento, Bugs Residuales, Duplicidades, Charset Strategy

Entregar:
1. Tabla resumen de motores (inventario de drivers/configs/metadata)
2. Matriz de duplicidades (% LoC, ubicaciones, prioridad)
3. Hallazgos de auditoría por motor (seguridad, rendimiento, bugs)
4. Matriz de dependencias (bulk, dump, managers vs connection/metadata)
```
Después: «corregir la premisas del skill», «si» (actualizar también AUDIT_REPORT.md y la guía de ejecución) y
«generar versión» (`/version-closure`).

## Context supplied
- `.github/prompts/audit_code.prompt.md`, `.github/agents/code-auditor.agent.md`
- `.github/skills/drivers-connections-audit/SKILL.md` (v1.0.2), `AUDIT_REPORT.md`, `CORRECTIONS_APPLIED.md`
- `.claude/DRIVERS_CONNECTIONS_AUDIT_EXECUTION.md`
- `pyproject.toml`, `src/util_bbdd/data/database_types.json`
- `.github/agents/version-closer.agent.md`, `.github/prompts/version_closure.prompt.md`, `.github/instructions/sync.instructions.md`

## AI output summary
- Lectura de `connection/**` (6.572 LoC), `metadata/**` (5.828), `_drivers/**` (824), `managers/**` (2.834) y, por dependencia, `factory/**` e imports de `bulk/` y `dump/`.
- Verificación empírica: `ConnectionParamsManager.prepare_and_validate` con 8 casos (7 rechazos indebidos), `repr()` de config con contraseña, URLs del factory con `make_url` (redirección de host reproducida), `_sanitize_conn_str` (fuga parcial de contraseña).
- Duplicidad medida con `difflib.SequenceMatcher` (pools 32 % de media; cierre de pools 38–72 %; factories sync/async 43 %).
- pytest del lote FASE 1 de la skill: 265 passed, 5 failed (`build/logs/drivers_audit_fase1_baseline.txt`). Suite completa: 5148 passed, 10 failed, 497 skipped (`build/logs/drivers_audit_fase1_full_suite.txt`).
- Veredicto AUDIT_CODE: **RECHAZADO** con 5 P0 (S1, B1, B2, S4, T1); P1: Q1, Y3, M3/Y2, M1, P1, O1.
- Corrección de la skill: `SKILL.md` 1.0.2 → 1.0.3 (10 premisas refutadas, P-1…P-10); registro en `CORRECTIONS_APPLIED.md`; aviso + anexo de contraste en `AUDIT_REPORT.md`; `.claude/DRIVERS_CONNECTIONS_AUDIT_EXECUTION.md` con resultado de FASE 1, comando `/hotfix` para los P0 y comandos correctos por fase (`/refactor` en FASE 4, `/version-closure` en FASE 6).
- VERSION: sin cambios en `src/` → sin bump; se mantiene v0.35.4. Campos de versión de § 4 sincronizados a 0.35.4 (estaban en 0.35.2/0.35.3 desde la release): `README.md` (cabecera y «Current Version»), `docs/index.md`, `docs/roadmap.md`, pie de figura de `docs/architecture.md` (329 ficheros medidos). `python scripts/gen_arquitectura_capas.py` pasa la verificación y regenera el SVG (etiqueta ×14 → ×15).
- Suite tras el cierre: 5153 passed, 5 failed (solo `test_charset_detection.py`), 497 skipped (`build/logs/drivers_audit_version_closure_suite.txt`). `zensical build --strict`: 3 anclas rotas preexistentes (`build/logs/drivers_audit_version_closure_zensical.txt`).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Informe FASE 1 (AUDIT_CODE) | respuesta en la conversación; resumen en `.claude/DRIVERS_CONNECTIONS_AUDIT_EXECUTION.md` § Resultado de FASE 1 | emitido (RECHAZADO) |
| Skill corregida | `.github/skills/drivers-connections-audit/SKILL.md` (v1.0.3) | modificado |
| Registro de correcciones | `.github/skills/drivers-connections-audit/CORRECTIONS_APPLIED.md` | ampliado |
| Auditoría histórica anotada | `.github/skills/drivers-connections-audit/AUDIT_REPORT.md` | aviso + anexo |
| Guía de ejecución | `.claude/DRIVERS_CONNECTIONS_AUDIT_EXECUTION.md` | modificado |
| Campos de versión | `README.md`, `docs/index.md`, `docs/roadmap.md`, `docs/architecture.md` | sincronizados a 0.35.4 |
| Diagrama de capas | `docs/assets/diagrams/arquitectura-capas.svg` | regenerado por script |
| Logs | `build/logs/drivers_audit_*.txt` | generados |

## Directrices para Futuras IAs
- **[metadata/MySQL]**: MySQL sí tiene catálogo propio: `MySQLCatalog(MariaDBCatalog)` en `src/util_bbdd/metadata/mariadb/catalog.py:476`, registrado como `"mysql"` en `metadata/catalog_registry.py:23`. No buscar `metadata/mysql/`.
- **[conexión/dos caminos]**: hay dos caminos de conexión que aplican configuración distinta: nativo (managers → `ConnectionFactory`/`PoolFactory` → `connection/<motor>/` → `*Config.to_driver_kwargs()`) y SQLAlchemy (`get_sqlalchemy_engine()` → `factory/sqlalchemy_engine_factory.py`, URL a mano sin `connect_args`). Todo cambio de TLS/charset debe verificarse en ambos.
- **[bulk/dump]**: bulk y dump no usan los pools de `connection/`: reciben un `Engine` y dependen de `metadata/` (facts, source, reflection, model); bulk además de `connection/performance_advisor.py`.
- **[validación conn_params]**: la validación está en tres capas que divergen: `connection/builder.py`, `_drivers/validator.py` (lista blanca = `optional` de `data/database_types.json`) y `connection/config.py` (`from_params`). Un parámetro nuevo en una config no se puede usar desde el manager hasta que se añade al JSON. `validators/<motor>_validator.py` valida parámetros de **queries**, no de conexión.
- **[charset MariaDB]**: el ejecutor adaptativo (`metadata/_adaptive_executor.py`) solo se activa en `managers/_catalog_executor.py` (sync) cuando el módulo raíz de la conexión es `mariadb` o `pymysql`; con el `QueuePool` de MySQL la conexión es `_ConnectionFairy` (módulo `sqlalchemy`) y no se activa. Nunca en async ni en `SqlAlchemyCatalogExecutor`.
- **[tests/charset]**: en v0.35.4, `tests/unit/metadata/test_charset_detection.py` tiene 5 fallos porque código y tests divergen (`_determine_state` con servidor latin1 → MIXED; `_inject_convert` sin alias `AS campo`). Decidir cuál manda antes de tocar la detección.
- **[técnica/duplicidad]**: medir duplicidad con `difflib.SequenceMatcher` sobre líneas no vacías en vez de estimar; las estimaciones de la skill (~60 % pools) resultaron ser 32 %.
- **[herramientas/Windows]**: `database_types.json` debe abrirse con `encoding="utf-8"`; con el default cp1252 de Windows lanza `UnicodeDecodeError`.
- **[VERSION]**: `tests/unit/test_docs_version.py` falla si `README.md`, `docs/index.md`, `docs/roadmap.md` o el pie de `docs/architecture.md` no coinciden con `pyproject.toml`; la release v0.35.4 se publicó sin sincronizarlos (corregido en esta sesión).
- **[skills]**: `/audit-code` es de solo lectura; para IMPLEMENT usar `/hotfix`, `/refactor` o `/new-feature`.

## Veredicto final
Veredicto: CLOSED (sesión de auditoría; el veredicto técnico de FASE 1 es RECHAZADO)
Pendientes al cierre:
- `/hotfix` de los P0 de FASE 1: S1 (URLs sin escapar en `factory/`), B1 (lista blanca JSON), B2 (`oracle_thick_mode`), S4 (camino SQLAlchemy sin TLS/charset), T1 (5 tests rojos de `test_charset_detection.py`).
- `zensical build --strict`: 3 anclas rotas a `connection_guide.md#6-parámetros-especiales-de-mariadb-init_command-y-encoding_errors` en `docs/api/connection_factory.md:87`, `docs/guides/mariadb_v0.35.0_charset_handling.md:224` y `docs/guides/troubleshooting.md:81` (preexistentes).
- FASE 2 de la skill tras corregir los P0.
- Commit propuesto, no ejecutado; `.github/skills/` y `.claude/DRIVERS_CONNECTIONS_AUDIT_EXECUTION.md` siguen sin versionar.
