# TRACEABILITY

## Session metadata
- id: 2026-09-22-audit-completo-remediacion
- fecha: 2026-09-22
- rama: develop
- skill: audit_code → tech_debt
- fase: AUDIT_CODE (12 franjas) + PLAN + AUDIT_PLAN

## Prompt issued
1. "AUDIT_CODE — De todo el proyecto — Separa la auditoría por módulos y por capas."
2. "Aplicar un PLAN y AUDIT_PLAN de la auditoria, pregunta lo que necesites."

## Context supplied
- `.github/SHARED_INSTRUCTIONS.md`, `CLAUDE.md`, `docs/architecture.md`,
  `scripts/gen_arquitectura_capas.py` (tabla `LAYER`/`LEVEL`)
- `.ai/sessions/INDEX.md` (histórico completo, usado para detectar que `MIG-02` ya fue una
  decisión previa deliberada — no un bug nuevo)
- 335 archivos de `src/util_bbdd/` (los 17 paquetes de primer nivel), leídos íntegramente por
  12 agentes de auditoría en paralelo

## AI output summary
- Se lanzaron 12 agentes de auditoría en paralelo, uno por franja de capa/módulo (Foundation;
  Servicios base; connection; metadata núcleo; metadata mariadb+mysql+oracle; metadata
  postgresql+redshift+snowflake; metadata sqlite+sqlserver; managers+analysis+dump;
  bulk+comparar; migrate núcleo; migrate _compat+transformadores; doc).
- Cada agente devolvió veredicto propio: **RECHAZADO** en `metadata/mariadb+mysql+oracle` y en
  `doc`; **APROBADO CON CONDICIONES** en las otras 10 franjas.
- Se consolidó un AUDIT_CODE único organizado por Nivel (1 Foundation, 2 Servicios,
  3 Especialización) y módulo, con veredicto global **RECHAZADO**.
- Se preguntó al usuario (AskUserQuestion) alcance, estructura y tratamiento de
  redshift/snowflake para la fase de remediación.
- Se verificó contra `git log`/`.ai/sessions/INDEX.md` que el hallazgo de `emitters/mariadb.py`
  (AUTO_INCREMENT→INT(11) fijo) corresponde a una decisión deliberada del commit `a950d18`
  (sesión `2026-05-22h-hotfix-mariadb-autoincrement`), no a un bug nuevo — documentado en
  `00_CONTEXT_SNAPSHOT.md` para que la fase IMPLEMENT no la revierta a ciegas.
- Se generó `01_PLAN_remediacion.md`: backlog de 10 ítems P0, 15 ítems P1, 27 ítems P2 y una
  lista consolidada de tests P3, con AUDIT_PLAN de riesgos funcionales/técnicos/seguridad,
  dependencias de orden obligatorio y 5 decisiones abiertas.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| AUDIT_CODE consolidado (12 franjas) | entregado en el chat de la sesión (no persistido como archivo aparte) | emitido |
| REQUEST | `.ai/sessions/2026-09-22-audit-completo-remediacion/00_REQUEST.md` | emitido |
| CONTEXT_SNAPSHOT | `.ai/sessions/2026-09-22-audit-completo-remediacion/00_CONTEXT_SNAPSHOT.md` | emitido |
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-09-22-audit-completo-remediacion/01_PLAN_remediacion.md` | emitido |
| IMPLEMENT — 9 ítems P0 | ver tabla de commits abajo | **completado** |
| IMPLEMENT — P1/P2 restantes del backlog | — | pendiente (sesión futura) |

### Commits de la fase IMPLEMENT (2026-09-22, todos en `develop`)

| Commit | Ítem | Resumen |
|---|---|---|
| `0597751` | DOC-01 | Autoescape Jinja2 activado en plantillas `*.html.j2` (XSS) |
| `b595f5b` | MEO-02 | `schema`/`table` bindeados como parámetros en helpers SQL de MariaDB (SQLi) |
| `843ca58` | SVC-02 | Allowlist de identificadores en `tabla`/`rutina`/`tipo_rutina`/`tablespace` (SQLi) |
| `ab92fcc` | SVC-01 | Password redactada en el log del connection string sync |
| `c1451eb` | CNX-01 | `user`/`password`/`database` URL-encoded en conninfo del pool PostgreSQL |
| `3a0f962` | CNX-02 | Valores escapados en el DSN ODBC de SQL Server (sync + async) |
| `0dabae6` | CMP-01 | Aviso de overflow TINYINT en `NUMBER(1-2,0)` Oracle→SQL Server |
| `cd874d8` | DOC-02 | El ZIP de documentación ya no se incluye a sí mismo |
| `c373e29` | MDC-05+MEO-01+MSS-01+MEO-03 | Conformidad de adaptadores con `SourceAdapter`/`RoutineAdapter` (Oracle async, SQL Server rutinas, MariaDB schema) |

Cada commit incluye su propio test de regresión. Suite completa verde tras cada commit
(3697→3742 tests según se añadían); `ruff check`/`ruff format --check`/`mypy src
tests/unit/test_protocol_conformance.py` limpios en el estado final.

## Directrices para Futuras IAs
- **[migrate]**: `emitters/mariadb.py:211-213` fuerza `INT(11)` para todo `AUTO_INCREMENT` por
  decisión deliberada del commit `a950d18`, no por descuido. Cualquier cambio a esa regla debe
  revisar los 3 tests de esa sesión (parametrizados ×5 tipos fuente + regresión no-AUTO_INCREMENT),
  no limitarse a revertir la línea.
- **[metadata]**: el patrón "test de paridad que certifica el bug en vez de detectarlo" apareció
  de forma independiente en `test_oracle_adapter_parity.py`, `test_sqlserver_adapter_parity.py` y
  `test_type_map_sqlserver.py`. Al escribir un test de "paridad"/"conformidad" futuro, comparar
  siempre contra el `Protocol` real (`_adapter_protocol.py`), no contra `hasattr(...)` del propio
  método bajo prueba.
- **[metadata]**: `test_protocol_conformance.py` (creado en la sesión
  `2026-09-21-regla6-ciclo-connection-factory`) solo cubre `MetadataCachePort`. Ampliarlo a
  `SourceAdapterSync/Async`/`RoutineAdapterSync/Async` para los 9 motores es la mitigación
  estructural única que habría detectado 3 de los hallazgos más severos de esta auditoría.
- **[proceso]**: la interpolación insegura de identificadores/SQL apareció de forma independiente
  en al menos 6 módulos no relacionados (`query/resolver`, `validators/`, `mariadb/_adapter_helpers`,
  `sqlite/*`, `comparar/reporters/sql_reporter`, `connection/*`). No tratarlo como una serie de
  bugs puntuales cerrados de una vez: falta una política de proyecto ("todo identificador se cita,
  todo valor se bindea") verificable con una regla de lint o un test transversal.
- **[alcance]**: los hallazgos de `metadata/redshift` y `metadata/snowflake` (incluida la
  evidencia de que ninguno de los dos se ha conectado nunca a una BD real) se excluyeron a
  propósito de esta ronda de remediación por decisión del usuario. No asumir que están
  descartados: es una decisión de producto pendiente, no resuelta.

## Veredicto final
Veredicto: **GO** para los 9 ítems P0 (implementados, testeados, commiteados sin incidencias)
Pendientes al cierre:
- Backlog P1 (15 ítems) y P2 (27 ítems) de `01_PLAN_remediacion.md` — quedan para sesión(es) futuras.
- Decisión ya tomada pero **no implementada**: MIG-02 (preservar ancho de tipo en
  `emitters/mariadb.py` para AUTO_INCREMENT) — P1, no estaba en el alcance de "todos los P0 hoy".
- Decisión ya tomada pero **no implementada**: MDC-01 (conectar `MetadataManager`/
  `MetadataFetcher`/`DDLBuilder` a la ruta real) — P1, requiere su propio `/refactor` de mayor
  alcance (corregir antes `builder.py::_quote_identifier` y decidir qué managers lo exponen).
- Decisión sin resolver: alcance de la exclusión redshift/snowflake en documentación pública.
- Esta sesión permanece **IN_PROGRESS**: el AUDIT_CODE y la fase P0 del backlog están cerrados;
  el backlog P1/P2 y las 2 decisiones tomadas-pero-no-implementadas quedan abiertos para
  continuar en una sesión futura referenciando este mismo documento.
