# CONTEXT SNAPSHOT

## Contexto del repositorio revisado
- `.github/SHARED_INSTRUCTIONS.md` (arquitectura, capas, principios de diseño, convención de commits)
- `CLAUDE.md` (slash commands, flujo PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION)
- `docs/architecture.md` + `scripts/gen_arquitectura_capas.py` (tabla `LAYER`/`LEVEL` canónica de 7 capas)
- `.ai/sessions/INDEX.md` (histórico de sesiones — usado para verificar si algún hallazgo ya
  fue tratado antes; confirmado un caso relevante, ver «Hechos previos» más abajo)
- 335 archivos de `src/util_bbdd/` leídos por 12 agentes de auditoría en paralelo (ver AUDIT_CODE
  consolidado entregado en el chat de esta misma sesión, previo a este snapshot)

## Estado actual observado
- Auditoría de solo lectura completada: 12 franjas, 2 veredictos **RECHAZADO**
  (`metadata/mariadb+mysql+oracle`, `doc`), 9 **APROBADO CON CONDICIONES**, 1 excluida de esta
  ronda (`metadata/postgresql+redshift+snowflake`, solo la parte PostgreSQL queda dentro de alcance).
- Tests/lint/mypy: no re-ejecutados en esta sesión (la auditoría fue de solo lectura sobre el
  árbol tal como quedó en el commit `ee077b8`). Los commits recientes (`ee077b8`, `a4bbcba`,
  `374a2c2`, `7822045`, `2dfd282`) indican que la suite y `mypy` estaban en verde antes de esta
  auditoría. Se recomienda `python -m pytest` + `python -m mypy src tests/unit/test_protocol_conformance.py`
  antes de empezar IMPLEMENT en cualquier fix de este backlog.
- Sin cambios locales pendientes: árbol limpio al iniciar (`git status` limpio en el snapshot de
  gitStatus del sistema).

## Hechos previos relevantes (evitan repetir análisis)
- **[migrate] `emitters/mariadb.py:211-213`**: el forzado de `INT(11)` para toda columna
  `AUTO_INCREMENT` **no es un descuido nuevo**: es una decisión deliberada del commit `a950d18`
  ("fix(migrate): AUTO_INCREMENT columns always emit INT(11) in MariaDB", sesión
  `2026-05-22h-hotfix-mariadb-autoincrement`), con 3 tests dedicados que fijan ese comportamiento
  como esperado (parametrizados ×5 tipos fuente + regresión no-AUTO_INCREMENT). El AUDIT_CODE de
  esta sesión reabre esa decisión porque no contempla el caso `BIGINT`/`SMALLINT` origen, pero
  cualquier fix debe revisar y actualizar esos 3 tests existentes, no limitarse a revertir la línea.
- **[metadata] Patrón repetido de "test de paridad que certifica el bug"**: aparece de forma
  independiente en 3 franjas distintas (`oracle/async_adapter.py` — `test_oracle_adapter_parity.py`;
  `sqlserver` — `test_sqlserver_adapter_parity.py`; `migrate/_compat/type_map_sqlserver.py` —
  `test_type_map_sqlserver.py`). No es un incidente aislado: sugiere que el patrón de test
  "verificar que el método existe" se usó como sustituto de "verificar que cumple el contrato",
  y debería corregirse como práctica, no solo parchear los 3 casos.
- **[metadata] `test_protocol_conformance.py` solo cubre `MetadataCachePort`** (añadido en la
  sesión `2026-09-21-regla6-ciclo-connection-factory`, decisión 3 del plan de capas estrictas).
  Ampliarlo a `SourceAdapterSync/Async` y `RoutineAdapterSync/Async` para los 9 adaptadores de
  motor es la mitigación estructural que habría detectado 3 de los hallazgos más severos de esta
  auditoría (Oracle async, SQL Server sync, MariaDB firma reducida).

## Estado Git relevante
- Rama activa: develop
- Cambios locales pre-existentes: ninguno
- Último commit: `ee077b8` — "docs(ai): actualizar sesión regla6-ciclo-connection-factory (capas estrictas, CI)"

## Clasificación metodológica
- Tipo principal: tech_debt (remediación de auditoría), con varios ítems de severidad
  hotfix (P0-seguridad) dentro del mismo backlog.
- Estado real de alcance: **mezclado por diseño** — el usuario pidió explícitamente un único
  PLAN/AUDIT_PLAN que cubra las 12 franjas, con la condición de que la fase IMPLEMENT posterior
  descomponga cada ítem en un fix independiente y commiteado por separado (no mezclar módulos no
  relacionados en un mismo commit).
- Consecuencia: este documento es el PLAN/AUDIT_PLAN conjunto; cada fila de la tabla de la Fase
  IMPLEMENT (fuera de esta sesión) se tratará como su propio ciclo `/hotfix` o `/refactor` según
  corresponda, referenciando este backlog por id.

## Gate G0 · Context Ready
Veredicto: **GO_CONDICIONAL**
Condiciones pendientes:
- Confirmar antes de IMPLEMENT: `python -m pytest` y `python -m mypy src tests/unit/test_protocol_conformance.py`
  en verde sobre el commit `ee077b8` (línea base), para no confundir regresiones del backlog con
  regresiones preexistentes.
- Ver decisiones abiertas en AUDIT_PLAN (`01_PLAN_remediacion.md`) antes de iniciar cualquier ítem P0.
