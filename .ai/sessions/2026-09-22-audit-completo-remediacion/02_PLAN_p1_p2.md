# PLAN + AUDIT_PLAN — Remediación backlog P1/P2 (continuación)

> **Actualización 2026-09-22 (IMPLEMENT parcial)**: Fase 1 completa (MSS-03, BLK-04, BLK-06 —
> BLK-03 descartado como falso positivo, ver `TRACEABILITY.md` § Hallazgos de reconciliación) y
> MIG-02 de Fase 2 implementados y commiteados (`0d6c81e`…`70935d2`). MDC-01 (resto de Fase 2),
> Fase 3 y Fase 4 quedan pendientes. Las 3 decisiones abiertas de la sección "Veredicto" original
> (MDC-01 diseño, FND-03/04, MIG-01 gate) **ya fueron respondidas por el usuario** el 2026-09-22
> — ver el recuadro al inicio de cada fase correspondiente abajo; no volver a preguntarlas, solo
> falta implementarlas.

Estado original (histórico, ver actualización arriba): **plan emitido, IMPLEMENT pendiente**. Continúa la sesión
`2026-09-22-audit-completo-remediacion` tras el cierre de los 9 ítems P0 + el grupo
MDC-05+MEO-01+MSS-01+MEO-03 (ver `TRACEABILITY.md`). Fuente: `01_PLAN_remediacion.md`
(backlog original de las 12 franjas del AUDIT_CODE), reconciliado contra el estado actual del
árbol (`HEAD` = `9a30bf4`). Skill: `tech_debt`. Fase: **PLAN + AUDIT_PLAN únicamente** — no se
implementa nada en esta sesión (petición explícita del usuario).

---

## Reconciliación contra `01_PLAN_remediacion.md`

`01_PLAN_remediacion.md` es un snapshot del commit `ee077b8`; no se ha actualizado con checkmarks
tras el IMPLEMENT de los P0. Antes de planificar el resto hace falta reconciliarlo:

**Ya implementados (no reabrir)**:
- P0 completo (10 ítems): DOC-01, MEO-02, SVC-02, SVC-01, CNX-01, CNX-02, CMP-01, DOC-02, MEO-01, MSS-01.
- P1: **MEO-03** (agrupado en `c373e29` junto con MDC-05/MEO-01/MSS-01).
- P2: **MDC-05** (mismo commit `c373e29`).
- Verificado en esta reconciliación: el sub-hallazgo de CMP-01 sobre `_handle_pk_identity`
  (`oracle_to_sqlserver.py:240-274`) ya queda cubierto — el `ddl_comment`/`MigrationWarning` que
  ahora emite `resolve_number_type_sqlserver()` se adjunta a la columna *antes* de que
  `_handle_pk_identity` la marque como `IDENTITY(1,1)`, así que el aviso de overflow ya llega al
  usuario en ese camino. No requiere fix adicional.

**Referencia obsoleta corregida**: SVC-05 apuntaba a `validators/base_validator.py:11`; tras el
crecimiento del fichero por SVC-02 (+81 líneas) la clase `DatabaseTypeValidator` quedó en la
línea 19. Corregido en la tabla de abajo.

**Contradicción detectada entre FND-03 y FND-04** (no estaba en `01_PLAN`, aparece al verificar
el código antes de planificar el fix): FND-03 afirma que la jerarquía `DumpError`/
`DumpConstraintError`/`DumpReportError` nunca se lanza (código muerto); confirmado por grep — no
hay ni un `raise` de esas clases en todo `src/`, ni en `dump/orchestrator.py`. FND-04 afirma que
`DumpOrchestrator` **sí** es un productor público de `DumpError` y por eso debería exportarse desde
`util_bbdd/__init__.py`. Ambas premisas no pueden ser ciertas a la vez. Verificado también:
`ComparerError` (la otra mitad de FND-04) sí se lanza de verdad vía sus subclases
(`SchemaDiffValidationError`, `MetadataIntrospectionError`, `DiffReportGenerationError`) y ya se
exporta desde `comparar/__init__.py`, solo falta en el `__init__.py` de nivel superior — esa mitad
de FND-04 es válida tal cual. Tratamiento propuesto abajo en la tabla de Fase 3.

**Alcance restante**: 14 ítems P1 (de 15 originales) + 31 ítems P2 (de 32 en la tabla original,
tras excluir MDC-05) = **45 ítems**, más las 2 decisiones de producto ya resueltas pero no
implementadas (MIG-02, MDC-01 — ambas ya cuentan dentro de los 14 P1).

---

## PLAN

**Módulo/paquete objetivo**: transversal — foundation, servicios (query/factory/validators),
connection, metadata (núcleo + mariadb/mysql/oracle/postgresql/sqlite/sqlserver; se excluye
redshift/snowflake, decisión de producto vigente y no revisada en esta sesión), managers/analysis,
bulk/comparar, migrate (núcleo + `_compat` + transformadores), doc. Mismo alcance que
`01_PLAN_remediacion.md`, ahora restringido a P1+P2.

**Deuda conocida**: la descripción completa de cada ítem (archivo, línea, problema, fix propuesto)
ya está en `01_PLAN_remediacion.md`, tablas P1 (líneas 44-61) y P2 (líneas 66-99). Este documento
no la repite; solo referencia el ID y añade lo que cambió en la reconciliación de arriba.

**Scope**: análisis únicamente — PLAN + AUDIT_PLAN. La fase IMPLEMENT queda para sesión(es)
futuras, un ítem o grupo por vez, cada uno con su propio commit (Conventional Commits, sin mezclar
módulos no relacionados — igual que en la tanda P0).

**Política de compatibilidad (supuesto explícito — no bloqueante, con precedente en esta misma
sesión)**: se autorizan cambios de contrato público cuando (a) ya hay una decisión de producto
resuelta que lo exige (MDC-01, MIG-02 — veredicto §5 de `01_PLAN_remediacion.md`), o (b) el cambio
es puramente aditivo — exponer un método que ya faltaba sin tocar los existentes (MPG-01, MSS-02).
Para el resto de ítems P1/P2 se prefiere el fix que **no** cambie una firma pública ya consumida
por callers reales; los que no tienen forma de resolverse sin romper contrato quedan marcados
explícitamente en la tabla de riesgos funcionales para confirmación antes de IMPLEMENT.

**Riesgos de regresión al abordarla**: 45 ítems tocando prácticamente todas las capas. La suite
(3742 tests en el último estado verde) y `mypy src tests/unit/test_protocol_conformance.py` deben
quedar en verde tras **cada** commit, no solo al cierre del lote. Todo cambio dentro de
`metadata/` debe re-verificarse contra `tests/unit/test_architecture_import_rules.py` (Regla #6).
MDC-01 es, con diferencia, el ítem de mayor riesgo de regresión: conecta a producción un subsistema
(`MetadataManager`/`MetadataFetcher`/`DDLBuilder`) que hoy está completamente desconectado y sin
tests de integración reales.

---

## Agrupación propuesta para IMPLEMENT (orden de fases sugerido, no obligatorio salvo donde se
indica dependencia dura)

### Fase 1 — Cierre del patrón de interpolación insegura (seguridad, P1+P2) — ✅ COMPLETADA 2026-09-22
Continúa directamente la recomendación de `TRACEABILITY.md` ("no es un bug puntual sino la
ausencia de una política de proyecto"). Mismo patrón que los P0 de seguridad ya cerrados.

| ID | Prioridad | Resumen | Estado |
|---|---|---|---|
| MSS-03 | P1 | PRAGMA sqlite con `schema`/`table` crudos, sin `quote_sqlite_identifier()` | ✅ `0d6c81e` |
| BLK-03 | P1 | `DEFAULT` sin escapar en `sql_reporter.py` (a diferencia de comentarios) | ❌ **falso positivo, no implementado** — ver `TRACEABILITY.md` |
| BLK-04 | P2 | `sql_reporter.py` no cita identificadores vía `identifier_preparer` | ✅ `e2813ad` |
| BLK-06 | P2 | `_sync_mssql` interpola `table_ref` sin comillas de identificador | ✅ `3986354` |

BLK-03 se investigó antes de implementar (`Inspector.get_columns()["default"]` de SQLAlchemy ya
devuelve la cláusula `DEFAULT` completa y citada por el motor origen, verificado con SQLite real y
con el parser `SHOW CREATE TABLE` de MySQL/MariaDB) y se descartó: aplicar el fix propuesto habría
corrompido por doble escapado cualquier `DEFAULT` string ya correcto. No reabrir sin releer
`TRACEABILITY.md` § Hallazgos de reconciliación primero.

### Fase 2 — Las 2 decisiones de producto ya resueltas (las que el usuario señaló explícitamente)

**MIG-02** (preservar ancho de tipo en `AUTO_INCREMENT`, `emitters/mariadb.py:211-213`) —
✅ **COMPLETADA 2026-09-22, commit `70935d2`**:
- Alcance acotado y sin ambigüedad técnica — la decisión de producto ya estaba tomada.
- Los 2 tests de `a950d18` relevantes (`test_auto_increment_column`,
  `test_auto_increment_always_emits_int11` → renombrado `test_auto_increment_preserves_source_width`,
  ahora parametrizado por tipo esperado en vez de "siempre INT(11)") se actualizaron sin revertir
  su intención original; `test_non_auto_increment_preserves_original_type` quedó sin cambios.

**MDC-01** (conectar `MetadataManager`/`MetadataFetcher`/`DDLBuilder` a producción) —
**decisión de diseño ya tomada (2026-09-22, vía `AskUserQuestion`), IMPLEMENT pendiente**:
- El ítem de mayor esfuerzo del lote completo. Requiere su **propio ciclo `/refactor`** con
  PLAN+AUDIT_PLAN dedicados, no cabe como fila de tabla. Sub-pasos obligatorios en este orden:
  1. Corregir `builder.py::_quote_identifier` (no escapa comillas embebidas — inyección de
     identificador) y `builder.py:107-111` (`DEFAULT` sin comillas para valores string — DDL
     inválido). **Antes** de exponer el subsistema a un caso de uso real (riesgo de seguridad ya
     señalado en `01_PLAN_remediacion.md` AUDIT_PLAN).
  2. **RESUELTO: exponer el subsistema vía un método nuevo en `managers/sync_mgr.py` y su
     equivalente en `async_mgr.py`** (no un manager dedicado, no deprecar). No reabrir esta
     decisión sin justificación nueva.
  3. `MetadataFetcher` lanza `NotImplementedError` incondicional si se instancia — implementar
     (ya no "retirar", dado el punto 2).
  4. Tests de integración reales para la ruta nueva (hoy el subsystem no tiene ninguno end-to-end).
- No implementar en la misma sesión que el resto del lote P1/P2 salvo que el usuario lo priorice
  explícitamente — es un proyecto en sí mismo.

### Fase 3 — P1 restantes sin dependencias fuertes (indepndientes entre sí, `/hotfix` cada uno)

| ID | Resumen |
|---|---|
| FND-01 | Docstring de `validate_db_type` no refleja el comportamiento real |
| FND-02 | Unificar `DriverError`/`InvalidDatabaseType` → `InvalidDatabaseType` (agrupar con CNX-03 de Fase 4, mismo patrón, commits separados por módulo) |
| MPG-01 | Exponer `fetch_routine_definition_sync/async` en PostgreSQL (aditivo) |
| MSS-02 | Exponer `fetch_routine_definition_sync/async` en SQL Server (aditivo) |
| MGR-01 | `close_async_resources` sin try/except por recurso (a diferencia del sync) |
| BLK-01 | Ampliar `except` a `AuditError`/`OSError` en `__run_bulk_pipeline` |
| BLK-02 | Normalizar case en comparación de índices/FKs — **cambio de salida observable**, requiere nota en CHANGELOG (ver riesgos funcionales) |
| MIG-01 | Gate `error_count > 0` antes de `MigrationPlan.execute()` — **RESUELTO (2026-09-22): bloquear sin flag de override**; no hay callers internos reales que dependan del comportamiento permisivo actual (solo un ejemplo en el docstring de `migrate/__init__.py`). IMPLEMENT pendiente. |
| MIG-03 | `MigrationWarning` cuando el fallback de `DEFAULT` se activa |
| MDC-02 | Cachés de `RelationshipMetadataCache` sin contexto de schema (colisión cross-schema) |

### Fase 4 — P2: limpieza estructural y código muerto, bajo riesgo

Agrupables libremente por módulo (cada módulo su commit, no mezclar):

- **Foundation**: FND-03/FND-04 — **RESUELTO (2026-09-22): conectar `DumpOrchestrator` para que
  lance de verdad `DumpError`/`DumpConstraintError`/`DumpReportError` en fallos reales** (en vez de
  retirar la jerarquía como código muerto); una vez conectado, exportar toda la jerarquía desde
  `util_bbdd/__init__.py` (FND-04 completo, incluida la mitad `ComparerError` que ya era válida
  sin esperar esta decisión). IMPLEMENT pendiente — no implementar FND-03 (retirar) por separado,
  queda descartado por esta resolución. FND-05 (unificar `ConnectionProvider`/`ConnectionReleaser`)
  sigue independiente.
- **Servicios**: SVC-03, SVC-04, SVC-05 (colisión de nombre `DatabaseTypeValidator`, ref. corregida
  arriba).
- **Connection**: CNX-03 (mismo patrón que FND-02, ver Fase 3), CNX-04, CNX-05.
- **Metadata núcleo**: MDC-03, MDC-04.
- **Metadata motores**: MEO-04, MEO-05, MEO-06, MEO-07.
- **Managers/analysis**: MGR-02, MGR-04. **MGR-03 depende de que `metadata/cache.py` exponga
  métodos públicos nuevos (`clear_context`/`clear_routine` equivalentes) — dependencia dura ya
  señalada en `01_PLAN_remediacion.md`; planificar justo después de tocar `metadata/cache.py` en
  MDC-02 (Fase 3) para no reabrir el mismo fichero dos veces sin necesidad, aunque son fixes
  lógicamente independientes.**
- **Bulk/comparar**: BLK-05, BLK-07, BLK-08.
- **Migrate**: MIG-04, MIG-05, MIG-06, MIG-07, MIG-08.
- **Migrate `_compat`**: CMP-02, CMP-03.
- **Doc**: DOC-03.

---

## AUDIT_PLAN

### Riesgos funcionales
- **MDC-01** cambia la superficie pública de forma sustancial (expone un subsistema hoy inerte);
  cualquier consumidor que hoy importe `DDLBuilder`/`MetadataFetcher`/`MetadataManager` esperando
  el `NotImplementedError` actual vería un comportamiento distinto. Bajo riesgo real (subsistema
  desconectado, sin consumidores conocidos) pero debe confirmarse antes de IMPLEMENT.
- **MIG-02** ya fue confirmado por el usuario (veredicto §5 de `01_PLAN_remediacion.md`); el riesgo
  residual es solo de regresión en los 3 tests de `a950d18`, no de decisión.
- **BLK-02** (case-insensitive en índices/FKs) cambia la salida de `SchemaComparator.compare()`
  para pares de motores con distinto case-folding — menos falsos positivos, pero observable;
  mencionar en CHANGELOG al implementar.
- **MIG-01** (gate `error_count > 0`) puede bloquear ejecuciones que hoy completan "a medias" sin
  fallar explícitamente — si algún flujo actual depende de ese comportamiento permisivo (aunque sea
  no intencional), el cambio es observable. Confirmar antes de tocar, igual que se hizo con MIG-02.
- **FND-03 vs FND-04** — **RESUELTO (2026-09-22)**: conectar `DumpOrchestrator` para que lance
  `DumpError` de verdad; FND-03 se reduce a limpiar solo `DatabaseType`/`OperationType`/
  `RouterineType` (código muerto no relacionado con `DumpError`), y FND-04 queda íntegro
  (exportar toda la jerarquía, incluida `ComparerError`). IMPLEMENT pendiente.

### Riesgos técnicos
- **MGR-03** depende de que `metadata/cache.py` (capa 5, fuera de `managers/`) exponga métodos
  públicos nuevos antes de tocar `managers/_metadata_cache.py` — dependencia real de secuencia, no
  solo de prioridad (heredada de `01_PLAN_remediacion.md`, sigue vigente).
- **MDC-01** sub-paso 1 (corregir `_quote_identifier`/`DEFAULT`) debe ir **antes** que el sub-paso 2
  (conectar a producción) — si se invierte el orden, el subsistema queda expuesto con una
  vulnerabilidad de inyección de identificador activa en un caso de uso real.
- Todo fix dentro de `metadata/` (capa 5) debe re-verificarse contra
  `tests/unit/test_architecture_import_rules.py` (Regla #6) tras el cambio — guarda estricta ya
  existente en CI, aplica igual que en la tanda P0.
- **FND-02**/**CNX-03** comparten el mismo patrón de fix (unificar a `InvalidDatabaseType`) pero
  viven en módulos distintos (foundation vs connection); implementarlos en paralelo es válido, pero
  cada uno mantiene su propio commit — no mezclar módulos no relacionados aunque el diff sea casi
  idéntico.

### Riesgos de seguridad
- La Fase 1 de este plan (MSS-03, BLK-03, BLK-04, BLK-06) es la continuación directa de la
  recomendación explícita de `TRACEABILITY.md`: el patrón de interpolación insegura de
  identificadores apareció en al menos 6 módulos no relacionados durante el AUDIT_CODE original;
  los P0 cerraron 4 de esos módulos (query/resolver, validators, mariadb helpers, connection
  strings), quedan sqlite (MSS-03) y comparar/sql_reporter+pk_sync (BLK-03/04/06). Tras cerrar
  estos cuatro, **sí se agota** el patrón detectado en esta auditoría — pero se mantiene la
  recomendación de una pasada `/security-review` dedicada aparte, no como sustituto de este cierre.
- **MDC-01** sub-paso 1 (`_quote_identifier`) es en sí mismo un fix de seguridad (inyección de
  identificador) camuflado dentro de un ítem de arquitectura — no debe posponerse ni diluirse
  dentro del esfuerzo de diseño del sub-paso 2.
- Ningún otro ítem P1/P2 restante tiene explotabilidad confirmada (a diferencia de los 6 P0 de
  seguridad, que sí la tenían reproducida contra `data/sql_queries.json` o en vivo).

### Dependencias entre ítems (orden obligatorio, no solo preferido)
1. `metadata/cache.py` expone métodos públicos nuevos (dentro de MDC-02) antes de **MGR-03**.
2. MDC-01 sub-paso 1 (`_quote_identifier`/`DEFAULT`) antes de MDC-01 sub-paso 2 (conectar a
   producción) — antes incluso de sub-paso 3 (decidir `MetadataFetcher`).
3. Resolver la contradicción FND-03/FND-04 antes de implementar cualquiera de los dos.
4. Confirmación de usuario sobre **MIG-01** (gate de `error_count`) antes de tocar
   `MigrationPlan.execute()`, mismo patrón de confirmación que ya se usó para MIG-02.

### Detección de expansión
No se ha añadido ningún ítem nuevo fuera de los ya reportados por `01_PLAN_remediacion.md`. La
única incorporación real de esta fase es la contradicción FND-03/FND-04, detectada al verificar el
código antes de planificar el fix (no es un hallazgo nuevo de auditoría, es una inconsistencia
interna del propio backlog que había que resolver antes de poder planificarlo). Se mantiene la
exclusión de `metadata/redshift`/`metadata/snowflake`.

---

## Veredicto: GO_CONDICIONAL → 3 de 4 condiciones resueltas el 2026-09-22 (ver abajo)

Condiciones originales, actualizadas tras la sesión de IMPLEMENT del 2026-09-22:
1. **Vigente, re-verificar en cada sesión futura**: confirmar `python -m pytest` +
   `python -m mypy src tests/unit/test_protocol_conformance.py` en verde sobre `HEAD` (línea base)
   antes de tocar nada — mismo gate que en la tanda P0. Verde al cierre de esta sesión (4163
   passed, 4 skipped) sobre el commit `70935d2`.
2. **MDC-01 — RESUELTO**: exponer el subsistema vía un método nuevo en `managers/sync_mgr.py` y su
   equivalente en `async_mgr.py`. IMPLEMENT pendiente (Fase 2, su propio `/refactor`).
3. **MIG-01 — RESUELTO**: bloquear `execute()` si `error_count > 0`, sin flag de override. IMPLEMENT
   pendiente (Fase 3).
4. **FND-03/FND-04 — RESUELTO**: conectar `DumpOrchestrator` a `DumpError` real; exportar toda la
   jerarquía después. IMPLEMENT pendiente (Fase 4).
5. Fuera de estas 4 condiciones (ya resueltas, solo falta implementar), las Fases 1 (✅ completada,
   ver arriba), 3 y 4 no tienen bloqueos y pueden iniciarse en cualquier orden dentro de cada fase,
   respetando las dependencias técnicas ya listadas (MDC-02 antes de MGR-03).

Cada ítem se implementa como su propio ciclo (`/hotfix` para P1 acotados, `/refactor` para MDC-01 y
para los P2 que toquen una firma pública), commit propio en Conventional Commits, referenciando su
ID (p. ej. `refactor(migrate): preservar ancho de AUTO_INCREMENT en emitters/mariadb.py [MIG-02]`).
Progreso a registrar en `TRACEABILITY.md` de esta sesión conforme se completa cada uno.
