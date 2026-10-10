# Q6 — PLAN + AUDIT_PLAN de la API pública 1.0

Fecha: 2026-10-10 · Base: `develop` @ v0.42.0 · Solo lectura. **Decidido 2026-10-10: A1–A6 aceptadas (§3).** Origen: `2026-10-04-api-single-entry-point-audit`
(Opción A hecha; B y C pendientes). Inventario: `api_inventory.tsv` (en esta carpeta) (cada símbolo de `util_bbdd.__all__`
con el número de ficheros de `docs/`, ejemplos, `tests/` y `src/` que lo nombran).

## 1. Situación medida

| Hecho | Dato |
|---|---|
| Símbolos en `util_bbdd.__all__` | **56** (eran 33 en la auditoría de v0.30) |
| De ellos, excepciones | **35** (62 %) |
| Puntos de entrada en la raíz | `SyncDatabaseManager`, `AsyncDatabaseManager`, `SchemaComparator`, `DumpOrchestrator`, `MigrationPlanner` |
| Puntos de entrada **fuera** de la raíz | `util_bbdd.bulk.BulkCrud`/`ParallelBulkLoader` (14 símbolos en `bulk`), `util_bbdd.doc.DatabaseDocumentation`, `util_bbdd.analysis` (14 símbolos) |
| Símbolos exportados sin documentación en `docs/` | `EngineReadinessAdvisor`, `AdvisoryFinding` (0 ficheros) |
| Contratos `Protocol` en la raíz | `SyncMetadataProvider`, `AsyncMetadataProvider`: 2 ficheros de `docs/`, 0 ejemplos, 1 test; desde ADR-003 la lectura real es `manager.get_schema_metadata()` |
| Piezas de bajo nivel en la raíz | `ConnectionFactory`, `PoolFactory`, `build_conn_params`, `maybe_await` (los managers ya las usan por dentro) |
| `BulkCrud` | 1751 líneas, 62 métodos (22 públicos: insert/update/delete × DataFrame/chunks, rechazos, auditoría, tamaños de lote) |
| `DumpOrchestrator` | 1133 líneas, 41 métodos, 1 público (`run`): la API ya es mínima; el tamaño es interno |
| `SyncDatabaseManager` / `AsyncDatabaseManager` | 30 / 26 métodos públicos; sync y async no son simétricos (`init`, `release_connection` solo en async; `close_connection` solo en sync) |

## 2. Propuesta para 1.0 (a decidir)

**Raíz `util_bbdd`: solo puntos de entrada y sus resultados (~15 símbolos).**

| Grupo | Símbolos |
|---|---|
| Conexión y consultas | `SyncDatabaseManager`, `AsyncDatabaseManager` |
| Carga masiva | `BulkCrud`, `ParallelBulkLoader` (subidos desde `util_bbdd.bulk`) |
| Volcado | `DumpOrchestrator`, `DumpConfig`, `DumpResult` |
| Migración | `MigrationPlanner`, `MigrationPlan` |
| Comparación | `SchemaComparator`, `SchemaDiff` |
| Documentación | `DatabaseDocumentation` (subido desde `util_bbdd.doc`) |
| Error base | `DatabaseException` |

**Submódulos públicos con nombre estable**: `util_bbdd.exceptions` (la jerarquía completa, hoy en `_core.exceptions`),
`util_bbdd.audit`, `util_bbdd.metadata` (`SchemaSnapshot`, `Kind`, los `Protocol` de proveedores), `util_bbdd.connection`
(`ConnectionFactory`, `PoolFactory`, `build_conn_params`, `EngineReadinessAdvisor`), `util_bbdd.analysis`.

**SRP (Opción C de la auditoría)**: `DumpOrchestrator` **no** se parte (su API pública es `run`; partirlo no cambia la
API y el riesgo es alto). `BulkCrud`: separar la auditoría y los rechazos en objetos propios accesibles desde el
resultado de cada operación, manteniendo los 6 métodos `bulk_*` como API; decisión aplazable a después de 1.0 porque no
rompe la API si se hace por dentro.

**Simetría sync/async de los managers**: alinear nombres (`release_connection`/`close_connection`, `init`) antes de 1.0,
porque después sería ruptura.

## 3. Decisiones para el usuario

| # | Decisión | Opciones | Recomendación |
|---|---|---|---|
| A1 | Raíz | (a) ~15 símbolos + submódulos estables; (b) mantener los 56 y documentar | **(a)** |
| A2 | Excepciones | (a) `util_bbdd.exceptions` público y fuera de la raíz salvo `DatabaseException`; (b) dejarlas en la raíz | **(a)**, con alias en la raíz y `DeprecationWarning` durante 0.x |
| A3 | `SyncMetadataProvider`/`AsyncMetadataProvider` | (a) solo en `util_bbdd.metadata`; (b) retirarlos | **(a)** |
| A4 | Simetría de managers | (a) alinear antes de 1.0 con alias deprecados; (b) dejar | **(a)** |
| A5 | `BulkCrud` SRP | (a) después de 1.0, por dentro; (b) antes | **(a)** |
| A6 | Calendario | 0.43.0 con alias y avisos de obsolescencia → 1.0.0 quitándolos | — |

**Decisión del usuario (2026-10-10): se aceptan las recomendaciones A1–A6.** A1 (a), A2 (a) con alias en la raíz y
`DeprecationWarning` durante 0.x, A3 (a), A4 (a), A5 (a) y A6 con el calendario propuesto: 0.43.0 (nueva superficie +
alias deprecados + guía de migración) → 1.0.0 (retirar alias tras al menos una versión con avisos). La implementación
se hace en una sesión propia (`.ai/sessions/<fecha>-api-1-0/`, flujo `/refactor`), que llega solo a 0.43.0.

## 4. AUDIT_PLAN

| Riesgo | Mitigación |
|---|---|
| Ruptura para usuarios de `from util_bbdd import <excepción>` | Alias en la raíz con `DeprecationWarning` (`__getattr__` del módulo) durante toda la serie 0.43–0.x; guía de migración |
| Imports circulares al subir `BulkCrud`/`DatabaseDocumentation` a la raíz (bulk y doc dependen de pandas/jinja2) | Exportación perezosa (`__getattr__`, como `util_bbdd.analysis`); `scripts/gen_arquitectura_capas.py` verifica capas |
| Tiempo de import de `import util_bbdd` | Medir antes/después (`python -X importtime`); exportación perezosa |
| Docs y ejemplos con imports antiguos | `grep` de cada símbolo movido en `docs/`, `README.md`, ejemplos; `zensical build --strict` |
| Tests que importan desde la raíz | Se actualizan en el mismo commit; un test fija `util_bbdd.__all__` |

## 5. Siguiente paso

~~Responder A1–A6.~~ Hecho (2026-10-10, §3). Siguiente: sesión nueva con PLAN → AUDIT_PLAN → IMPLEMENT en dos versiones: **0.43.0** (nueva superficie + alias deprecados + guía) y
**1.0.0** (retirar alias tras al menos una versión con avisos).
