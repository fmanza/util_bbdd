# TRACEABILITY

## Session metadata
- id: 2026-09-22-audit-completo-remediacion
- fecha: 2026-09-22
- rama: develop
- skill: audit_code → tech_debt
- fase: AUDIT_CODE (12 franjas) + PLAN + AUDIT_PLAN + IMPLEMENT (P0 + Fase 1 + MIG-02 + MDC-01 +
  Fase 3 del backlog P1/P2; Fase 4 pendiente)

## Prompt issued
1. "AUDIT_CODE — De todo el proyecto — Separa la auditoría por módulos y por capas."
2. "Aplicar un PLAN y AUDIT_PLAN de la auditoria, pregunta lo que necesites."
3. "Remaining backlog (P1/P2, plus two decided-but-not-yet-implemented items — preserving
   AUTO_INCREMENT width in the MariaDB emitter [MIG-02], and connecting the dead
   MetadataManager/DDLBuilder subsystem to production [MDC-01]) is documented in
   `01_PLAN_remediacion.md` for a future session. PLAN y AUDIT_PLAN"
4. "IMPLEMENT y pregunta lo necesario" — 4 preguntas vía `AskUserQuestion` sobre alcance de la
   sesión y las 3 decisiones abiertas de `02_PLAN_p1_p2.md`; respuestas del usuario: (a) alcance
   = Fase 1 + MIG-02 (MDC-01 queda fuera, para su propio `/refactor`); (b) MDC-01 expondría
   `MetadataManager`/`DDLBuilder` vía un método nuevo en `sync_mgr.py`/`async_mgr.py` (decisión
   registrada para cuando se aborde MDC-01, **no implementada** esta sesión); (c) FND-03/FND-04 se
   resuelven conectando `DumpOrchestrator` para que sí lance `DumpError` (decisión registrada,
   **no implementada** esta sesión — FND-03/04 son Fase 4); (d) MIG-01 bloquea `execute()` si
   `error_count > 0` sin flag de override (decisión registrada, **no implementada** esta sesión —
   MIG-01 es Fase 3).
5. "IMPLEMENT: Fase 3 — P1 sueltos, sin dependencias fuertes (10) FND-01, FND-02, MPG-01, MSS-02,
   MGR-01, BLK-01, BLK-02, MIG-01 (gate ya decidido: bloquear sin flag), MIG-03, MDC-02." — los 10
   ítems implementados como ciclos `/hotfix` independientes, un commit por ítem, ver tabla en
   "Fase 3 — IMPLEMENTADA" abajo.

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
- Se generó `02_PLAN_p1_p2.md`: reconciliación del backlog restante (45 ítems) contra el estado
  real tras el IMPLEMENT de los P0, agrupado en 4 fases de ejecución.
- **IMPLEMENT Fase 1 + MIG-02** (4 ítems del backlog P1/P2, ver tabla de commits abajo):
  - Antes de implementar **BLK-03** (escapar `DEFAULT` en `sql_reporter.py`) se verificó con
    SQLite real y con el parser `SHOW CREATE TABLE` del dialecto MySQL de SQLAlchemy que
    `Inspector.get_columns()["default"]` ya devuelve la cláusula `DEFAULT` completa y citada por
    el motor origen — aplicar `_escape_sql_string()` ahí habría corrompido por doble escapado
    cualquier `DEFAULT` string ya correcto. **BLK-03 se descarta como falso positivo, no se
    implementa** (ver "Hallazgos de reconciliación" abajo).
  - **MSS-03, BLK-04, BLK-06** (patrón de interpolación insegura de identificadores) y **MIG-02**
    (preservar ancho de `AUTO_INCREMENT`) implementados con test de regresión cada uno.

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| AUDIT_CODE consolidado (12 franjas) | entregado en el chat de la sesión (no persistido como archivo aparte) | emitido |
| REQUEST | `.ai/sessions/2026-09-22-audit-completo-remediacion/00_REQUEST.md` | emitido |
| CONTEXT_SNAPSHOT | `.ai/sessions/2026-09-22-audit-completo-remediacion/00_CONTEXT_SNAPSHOT.md` | emitido |
| PLAN + AUDIT_PLAN | `.ai/sessions/2026-09-22-audit-completo-remediacion/01_PLAN_remediacion.md` | emitido |
| IMPLEMENT — 9 ítems P0 | ver tabla de commits abajo | **completado** |
| PLAN + AUDIT_PLAN — backlog P1/P2 restante | `.ai/sessions/2026-09-22-audit-completo-remediacion/02_PLAN_p1_p2.md` | emitido |
| IMPLEMENT — Fase 1 + MIG-02 (4 ítems) | ver tabla de commits abajo | **completado** |
| IMPLEMENT — Fase 2 (MDC-01), Fase 3, Fase 4 | — | pendiente (sesión futura) |

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

### Commits de la fase IMPLEMENT — Fase 1 + MIG-02 (2026-09-22, todos en `develop`)

| Commit | Ítem | Resumen |
|---|---|---|
| `0d6c81e` | MSS-03 | Identificadores citados con `quote_sqlite_identifier()` en PRAGMA de sqlite (antes corchetes crudos) |
| `e2813ad` | BLK-04 | `SqlDiffReporter` cita tabla/columna/índice/FK/vista/rutina vía `identifier_preparer` dialect-aware |
| `3986354` | BLK-06 | `_sync_mssql` cita `table_ref` (bracket-quoting) antes de embeberlo en el literal `DBCC CHECKIDENT` |
| `70935d2` | MIG-02 | `AUTO_INCREMENT` preserva la categoría del tipo origen (ya no colapsa BIGINT/SMALLINT a `INT(11)`) |

Cada commit incluye su(s) propio(s) test(s) de regresión. Suite completa verde tras cada commit
(4148→4163 tests); `ruff check`/`ruff format --check`/`mypy src
tests/unit/test_protocol_conformance.py` limpios en el estado final.

### Hallazgos de reconciliación durante IMPLEMENT (no estaban en `01_PLAN_remediacion.md`)

- **BLK-03 es un falso positivo — no implementado.** El hallazgo original asumía que
  `sql_reporter.py` interpolaba valores `DEFAULT` "en bruto" (como los comentarios, que sí
  necesitan `_escape_sql_string`). Verificado con `sqlite3.connect(":memory:")` real y con el
  código fuente del parser `SHOW CREATE TABLE` de `sqlalchemy/dialects/mysql/reflection.py`:
  `Inspector.get_columns()["default"]` devuelve la **cláusula DEFAULT completa ya citada** por el
  motor origen (p.ej. `"'O''Brien'"`, comillas incluidas), no el valor bruto. Aplicar
  `_escape_sql_string()` sobre eso habría duplicado el escapado de cualquier comilla simple ya
  escapada, corrompiendo el DDL generado — el código actual (interpolar `default` tal cual) es
  correcto. Si se reabre este hallazgo en el futuro, releer este párrafo antes de "corregirlo".

## Directrices para Futuras IAs
- **[migrate]**: **RESUELTO en esta sesión (commit `70935d2`, MIG-02)** — `emitters/mariadb.py`
  ya no fuerza `INT(11)` para todo `AUTO_INCREMENT`; `_auto_increment_col_type()` preserva la
  categoría del tipo origen (`TINYINT`/`SMALLINT`/`MEDIUMINT`/`INT`/`BIGINT`) con su display width
  convencional. No reabrir salvo nuevo hallazgo real.
- **[metadata/MDC-01]**: **RESUELTO e IMPLEMENTADO en esta sesión (commits `b701a3d`, `6e5a559`)**
  — `DDLBuilder._quote_identifier`/`DEFAULT` corregidos primero; `SyncDatabaseManager`/
  `AsyncDatabaseManager` exponen `get_metadata_manager()` (construcción diferida, cachea la
  instancia, reutiliza `self` como `metadata_provider` y comparte `db_cache`/
  `relationship_cache`). `MetadataFetcher` resultó ser código muerto dentro de `MetadataManager`
  (nunca invocado) — se eliminó la referencia en vez de implementarlo, ver detalle en "Veredicto
  final" § MDC-01. No reabrir salvo nuevo hallazgo real.
- **[foundation/FND-03-FND-04]**: decisión ya tomada con el usuario (2026-09-22) pero **no
  implementada**: conectar `DumpOrchestrator` para que lance de verdad `DumpError`/
  `DumpConstraintError`/`DumpReportError` en fallos reales (en vez de retirar la jerarquía como
  código muerto). Una vez conectado, exportar toda la jerarquía desde `util_bbdd/__init__.py`
  (FND-04 completo). No implementar FND-03 (retirar) ni FND-04 (exportar) por separado sin este
  contexto — son la misma decisión.
- **[migrate/MIG-01]**: decisión ya tomada con el usuario (2026-09-22) pero **no implementada**:
  `MigrationPlan.execute()` debe bloquear (lanzar excepción) si `self.error_count > 0`, **sin**
  flag de override explícito. No hay callers internos reales que dependan del comportamiento
  permisivo actual (solo un ejemplo en el docstring de `migrate/__init__.py`).
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
Veredicto: **GO** para los 9 ítems P0 (implementados, testeados, commiteados sin incidencias).
Veredicto: **GO** para Fase 1 + MIG-02 del backlog P1/P2 (4 ítems: MSS-03, BLK-04, BLK-06, MIG-02 —
implementados, testeados, commiteados sin incidencias; BLK-03 descartado como falso positivo tras
verificación, ver arriba).
Veredicto: **GO** para MDC-01 (Fase 2 completa, ciclo `/refactor` dedicado — ver detalle abajo).
Veredicto: **GO** para Fase 3 del backlog P1/P2 (10 ítems: FND-01, FND-02, MPG-01, MSS-02, MGR-01,
BLK-01, BLK-02, MIG-01, MIG-03, MDC-02 — implementados, testeados, commiteados sin incidencias; ver
sección "Fase 3 — IMPLEMENTADA" arriba para hallazgos de reconciliación y pendientes de CHANGELOG).

### MDC-01 — IMPLEMENTADO 2026-09-22 (commits `b701a3d`, `6e5a559`)

Ciclo `/refactor` dedicado (PLAN+AUDIT_PLAN+IMPLEMENT+AUDIT_CODE), continuación de esta sesión:

- **Sub-paso 1 (seguridad, commit `b701a3d`)**: `DDLBuilder._quote_identifier` ahora duplica el
  delimitador embebido (backtick/comilla/corchete) en vez de solo envolver el identificador
  — cierra la inyección de identificador. `_build_column_definition` cita y escapa los `DEFAULT`
  string vía `_format_default_value()` (palabras clave/funciones SQL conocidas y numéricos pasan
  sin citar, igual que el patrón ya establecido en `migrate/emitters/mariadb.py::_format_default`,
  replicado localmente para no romper la regla de capas). 22 tests de regresión nuevos
  (`tests/unit/test_metadata_builder.py`), incluidos payloads de inyección explícitos.
- **Hallazgo de reconciliación (no estaba en `01_PLAN_remediacion.md`/`02_PLAN_p1_p2.md`)**:
  `MetadataManager.__init__` construía `self.fetcher = MetadataFetcher(metadata_provider)` pero
  ningún método de `MetadataManager` lo usaba jamás — todas las operaciones ya llamaban
  directamente a `metadata_provider.get_xxx()`. `MetadataFetcher` era código muerto *dentro de*
  `MetadataManager`, no un componente que activar. Confirmado con el usuario vía
  `AskUserQuestion` (2026-09-22): se elimina la línea muerta en vez de "implementar"
  `MetadataFetcher` (que hubiera sido trabajo no consumido por nadie); la clase `MetadataFetcher`
  queda sin tocar y sigue exportada tal cual (sin implementar, comportamiento previo intacto).
  Mismo patrón que el falso positivo BLK-03 de esta sesión: una asunción de plan que la lectura
  del código contradice.
- **Sub-pasos 2-4 (arquitectura, commit `6e5a559`)**: `SyncDatabaseManager.get_metadata_manager()`
  y `AsyncDatabaseManager.get_metadata_manager()` (nuevo, aditivo) construyen de forma diferida un
  `MetadataManager`/`AsyncMetadataManager` (nuevo, espejo async — `SyncDatabaseManager`/
  `AsyncDatabaseManager` ya implementaban íntegramente `SyncMetadataProvider`/
  `AsyncMetadataProvider` contra producción, confirmado con mypy antes de conectar) reutilizando
  `self` como `metadata_provider` y compartiendo `db_cache`/`relationship_cache` con el resto del
  manager (sin duplicar cacheo). 8 tests de integración reales (sqlite3/aiosqlite, no mockeados,
  `tests/unit/test_metadata_manager_production_wiring.py`), incluido un roundtrip: el DDL
  construido por `DDLBuilder` se ejecuta de verdad contra la conexión.
- Suite completa verde tras cada commit (4163→4193 tests); `ruff check`/`ruff format --check`/
  `mypy src tests/unit/test_protocol_conformance.py` limpios; Regla #6
  (`test_architecture_import_rules.py`) verde; diagrama de capas regenerado sin cambios (el borde
  `managers→metadata` ya existía).

### Fase 3 — IMPLEMENTADA 2026-09-22 (10 ítems P1 sueltos, sin dependencias fuertes)

Los 10 ítems de Fase 3 de `02_PLAN_p1_p2.md` implementados como ciclos `/hotfix`
independientes, cada uno con su propio commit (Conventional Commits) y tests de
regresión. Suite completa verde tras cada commit (4193→4252 tests);
`ruff check`/`ruff format --check`/`mypy src tests/unit/test_protocol_conformance.py`
limpios; Regla #6 (`test_architecture_import_rules.py`) verde; diagrama de capas
regenerado sin cambios en cada uno (ningún ítem añadió/movió/eliminó un paquete de
primer nivel ni un import entre paquetes).

| Commit | Ítem | Resumen |
|---|---|---|
| `879aba5` | FND-01 | Docstring de `validate_db_type` corregido (nunca retorna `False`, siempre lanza `InvalidDatabaseType`) |
| `e9e0630` | FND-02 | `DriverValidator.check_driver_availability` unificado a `InvalidDatabaseType` para db_type desconocido (antes `DriverError` genérico) |
| `d8b6dbd` | MPG-01 | `fetch_routine_definition_sync/async` expuesto en adaptadores PostgreSQL (aditivo, reutiliza `process_routine_result()`) |
| `8844f56` | MSS-02 | `fetch_routine_definition_sync/async` expuesto en adaptadores SQL Server (aditivo, reutiliza `fetch_routine_body_sync`) |
| `cdbef6e` | MGR-01 | `close_async_resources` envuelve pool/conexión en try/except por recurso, agregando errores (igual que la versión sync) |
| `b6fa39e` | BLK-01 | `__run_bulk_pipeline` captura también `AuditError`/`OSError`; riesgo residual de rollback documentado en `bulk_session()` |
| `9312d5e` | BLK-02 | Comparación de índices/FKs normalizada a minúsculas (`_case_insensitive_key_map`, mismo patrón que tablas/columnas) — **cambio de salida observable**, pendiente nota en CHANGELOG (ver abajo) |
| `27bf667` | MIG-01 | `MigrationPlan.execute()` bloquea (`ValueError`) si `error_count > 0`, sin flag de override (decisión ya confirmada por el usuario) |
| `53f210f` | MIG-03 | `MigrationWarning` emitido cuando el fallback de `DEFAULT` (valor con forma de función no reconocida) se activa, en los 4 emisores |
| `eaf6098` | MDC-02 | Las 4 cachés de `RelationshipMetadataCache` ahora incluyen `context` (schema) — evita colisión cross-schema entre tablas homónimas |

Hallazgos de reconciliación / decisiones de diseño durante Fase 3 (no estaban en
`01_PLAN_remediacion.md`/`02_PLAN_p1_p2.md`):

- **MIG-03** requirió más que "solo emitir el warning": los emisores descubren el
  fallback de `DEFAULT` en fase de EMISIÓN (`emit_ddl()`/`emit_statements()`), pero
  `MigrationPlan.warnings` se construye en fase de TRANSFORMACIÓN (antes de que el
  emisor se invoque nunca). Sin un paso de resincronización, el warning quedaría
  atrapado en `col.warnings` y nunca llegaría a `plan.warnings`/`plan.error_count`.
  Se añadió `MigrationPlan._sync_warnings_from_tables()`, invocado desde `emit_ddl()`
  y `emit_statements()`, idempotente (no duplica entre llamadas repetidas). Severidad
  del warning deliberadamente `WARNING` (no `ERROR`): `execute()` (MIG-01) comprueba
  `error_count` **antes** de emitir, así que un `ERROR` descubierto solo durante la
  emisión no bloquearía esa primera llamada — se documentó explícitamente en el
  commit para que una futura sesión no lo reabra sin releer este razonamiento.
- **MDC-02** se implementó con `context` **opcional** (`*, context: str = ""`) en vez
  de un parámetro posicional obligatorio, pese a que `RelationshipMetadataCache` es
  API pública exportada desde `util_bbdd.__init__`. Motivo: mantener el fix
  retrocompatible sin requerir confirmación de "cambio de contrato público" (política
  de `02_PLAN_p1_p2.md` — solo MDC-01/MIG-02 tenían decisión ya tomada para romper
  contrato). Todos los callers internos reales (los 4 puntos de uso en
  `analysis/graphviz_ext.py`, el único productor de estas cachés) se actualizaron
  para pasar el contexto real; un caller externo hipotético que no pase `context`
  sigue funcionando igual que antes (namespace único, mismo riesgo de colisión que ya
  tenía). `clear_by_table()` mantiene semántica conservadora por defecto (`context=None`
  invalida en todos los contextos) para no dejar nunca una entrada obsolete al no
  especificarlo.
- **BLK-02** cambia la salida observable de `SchemaComparator.compare()`: pares de
  tablas cuyos índices/FKs solo difieren en el case del nombre ya no se reportan como
  `added+removed`. **Pendiente**: nota en `CHANGELOG.md` — no se añadió en el commit
  de este ítem siguiendo el mismo patrón ya establecido en esta sesión para MIG-02 (P0
  Fase 1, cambio de comportamiento en `AUTO_INCREMENT`), que tampoco recibió entrada
  individual en `CHANGELOG.md`; ambos quedan consolidados para la fase `/version-closure`
  de cierre de esta sesión, que debe repasar `git log` de toda la sesión y no solo el
  `[Unreleased]` actual (que sigue siendo un snapshot de trabajo anterior a esta sesión).

Pendientes al cierre:
- Reconciliación de `01_PLAN_remediacion.md` contra el estado actual: ya implementados MEO-03 (P1)
  y MDC-05 (P2) junto con los P0 en el commit `c373e29`; Fase 1 + MIG-02 de `02_PLAN_p1_p2.md`
  implementados en esta sesión (commits `0d6c81e`…`70935d2`); MDC-01 implementado (commits
  `b701a3d`, `6e5a559`); Fase 3 completa (10 ítems, commits `879aba5`…`eaf6098`, ver tabla arriba).
  Quedan de `02_PLAN_p1_p2.md`: **Fase 4 completa** — FND-03/FND-04 (decisión ya tomada, no
  implementada) + el resto de ítems P2 agrupables por módulo (SVC-03..05, CNX-03..05, MDC-03/04,
  MEO-04..07, MGR-02..04, BLK-04..08 [BLK-04/06 ya implementados en Fase 1], MIG-04..08, CMP-02/03,
  DOC-03).
- Decisión ya tomada pero **no implementada**: FND-03/FND-04 (conectar `DumpOrchestrator` a
  `DumpError` real, luego exportar toda la jerarquía) — Fase 4 de `02_PLAN_p1_p2.md`.
- **CHANGELOG.md pendiente**: MIG-02 (Fase 1, P0) y BLK-02 (Fase 3) cambian comportamiento
  observable y no tienen entrada en `CHANGELOG.md` todavía — consolidar en `/version-closure`.
- Decisión sin resolver: alcance de la exclusión redshift/snowflake en documentación pública.
- Esta sesión permanece **IN_PROGRESS**: AUDIT_CODE, fase P0, Fase 1 + MIG-02, MDC-01 (Fase 2) y
  Fase 3 completa del backlog P1/P2 están cerrados; solo Fase 4 queda abierta para continuar en
  sesión(es) futuras referenciando `01_PLAN_remediacion.md` + `02_PLAN_p1_p2.md` + las decisiones ya
  registradas arriba en "Directrices para Futuras IAs" (para no volver a preguntarlas).
