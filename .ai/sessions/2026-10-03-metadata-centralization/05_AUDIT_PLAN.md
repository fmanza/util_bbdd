# 05 · AUDIT_PLAN — centralización y rendimiento de metadatos

Sesión `2026-10-03-metadata-centralization` · Plan Architect (+ Performance Auditor para el eje de rendimiento)

Audita `03_DISENO.md` y `04_PLAN.md` contra el código real (`01_INVENTARIO.md`) y las mediciones
(`02_BASELINE_RENDIMIENTO.md`).

---

## Request summary

Centralizar en `metadata/` toda la lectura del diccionario de datos (SQL de catálogo, registry JSON, `Inspector`) y
pasar de lecturas por tabla a lecturas por schema y tipo de objeto, con ruptura de API autorizada.

## Scope in

`metadata/`, `managers/` (lectura de metadatos y cachés), `query/` + `data/sql_queries.json` (consultas de catálogo),
`validators/` (validación de esas consultas), consumidores `doc/`, `analysis/`, `migrate/extractors/`, `comparar/`
(lectura), `dump/` (introspección), `bulk/` (reflexión, `pk_sync`, constraints de Oracle),
`connection/mariadb/update_auto_increment.py`, reglas IA y documentación asociadas.

## Scope out

- `connection/*/_variables.py` y `PRAGMA` de sesión (configuración del servidor/conexión, `EngineReadinessAdvisor`).
- SQL emitido (`comparar/reporters/sql_reporter.py`, `migrate/emitters/`).
- Transformadores y emisores de `migrate`, lógica de carga de `bulk`/`dump`, renderizado de `doc`.
- H-10 y H-17 se corrigen aparte con `/hotfix`; H-14 y H-16 con PRs `perf:` propios (no mezclar flujos).

## Code reality check

| Supuesto del diseño | Verificación | Resultado |
|---|---|---|
| Existen consultas por schema reutilizables para Oracle, PostgreSQL, SQL Server, MariaDB/MySQL | `*_for_schema_sql` en `metadata/{oracle,postgresql,sqlserver,mariadb,mysql}`; `migrate` las usa con 9 consultas para 50 tablas (baseline) | ✅ |
| SQLite y HSQLDB no tienen consultas por schema | `metadata/sqlite` solo `PRAGMA` por tabla; HSQLDB solo JSON | ✅ trabajo nuevo (A5, A6) |
| Los managers usan el JSON para casi todo | `_manager_metadata_runtime.py:195-198` + `GenericMetadataFetchStrategy` | ✅ |
| Los adaptadores M3 no se usan | 0 llamadas en `src/` a `fetch_*_sync`/`_async` | ✅ |
| `metadata/` puede alojar el ejecutor DBAPI | No: `executors/` está en la misma capa 5 → el ejecutor DBAPI se implementa en `managers/` (capa 6) y se inyecta | ⚠️ ajustado en D6 |
| `connection/` no puede leer de `metadata/` | Capa 4 < 5 | ✅ motiva mover `UpdateAutoIncrement` (E1) |
| `doc` depende de la forma por motor de las tuplas | Renderers leen índices posicionales de `get_columns()` etc. (`doc/infrastructure/renderers/*`) | ⚠️ riesgo R1 |
| El patrón por schema es mucho más barato | PostgreSQL: FK por tabla ≈ 95 ms constante vs. 89 ms para 4999 FKs por schema; `manager_scan` 500 tablas 70 s de catálogo | ✅ medido |

## Files likely affected

- Nuevos: `metadata/{contracts,model,snapshot_cache,_paramstyle,registry,source,reflector}.py`,
  `metadata/<motor>/catalog.py` (6), `scripts/bench_metadata.py`, `tests/unit/metadata/*`,
  `tests/integration/metadata/characterization/*`, `tests/unit/test_architecture_metadata_rules.py`.
- Modificados: `managers/{sync_mgr,async_mgr,_metadata_*,_manager_*}.py`, `doc/**` (adaptador y renderers),
  `analysis/base.py`, `analysis/graphviz_ext.py`, `migrate/extractors/*.py`, `migrate/planner.py`,
  `comparar/{comparator,_prefetch,_routine_fetchers}.py`, `comparar/reporters/sql_reporter.py` (lectura),
  `dump/{orchestrator,_constraints,_fk_graph,_indexes}.py`, `bulk/{crud,_support/*,_execution/*}.py`.
- Retirados (E2): `data/sql_queries.json` (consultas de catálogo), `metadata/<motor>/{sync,async}_adapter.py`,
  `metadata/adapters/_adapter_protocol.py`, `metadata/{manager,async_manager,fetcher,cache}.py` si quedan sin uso,
  `metadata/{redshift,snowflake}/` (si D9-1 = a), `connection/mariadb/update_auto_increment.py` (movido).

## Test strategy

Ver `04_PLAN.md` § «Estrategia de pruebas». Puntos de auditoría:

- Los dorados de A0 se generan **antes** de cualquier cambio y con el código de v0.30.0 (y H-10 corregido, para no
  congelar un fallo).
- Los tests de conteo de consultas usan SQLite en memoria (CI sin motores); los dorados por motor son `integration`.
- Paridad sync/async: el mismo test de conteo para `CatalogSource` y su variante async.

## Risks

### Funcionales

| ID | Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|---|
| R1 | `doc` lee tuplas por posición distinta por motor; al pasar a modelos cambian columnas o se pierde información | Alta | Alto | Dorados HTML/Excel por motor (A0); D1 solo se cierra con dorados idénticos o diferencias listadas y aceptadas |
| R2 | Normalización distinta entre JSON, `*_for_schema_sql` e `Inspector` (mayúsculas Oracle, defaults, identity, `NUMBER` sin precisión, vistas sin definición por permisos) | Alta | Medio | Dorados por motor de managers/`migrate`/`comparar`; parseo único por motor |
| R3 | Routines con sobrecarga (PostgreSQL) o cifradas (SQL Server) | Media | Medio | Clave `RoutineKey(name, signature)`; definición `None` con aviso (comportamiento de `comparar` v0.30.0) |
| R4 | Caché obsoleta tras DDL propio (`migrate.execute`, `dump` recreando índices, `bulk.maintenance_scope`) | Media | Alto | `invalidate()` explícito + test que ejecuta DDL y relee |
| R5 | Usuarios externos que llamaban `execute_query_many("obtener_tablas")`, `get_metadata_manager()`, `UpdateAutoIncrement` o pasaban `Inspector` a `compare()` | Media | Medio | Guía de migración en CHANGELOG; cortes de versión (v0.32.0) |

### Técnicos

| ID | Riesgo | Mitigación |
|---|---|---|
| T1 | Traductor `:nombre` → `paramstyle` rompe SQL con `::` (casts PG), `:=` (PL/SQL), literales con `:` | Regex `(?<!:):\w+` ya usada por el executor (`_sql_uses_bind_params`) + tests con esos casos; el SQL de catálogo no lleva PL/SQL |
| T2 | Snapshot de schemas enormes: memoria y latencia de la primera lectura | Medido a 5000 tablas (baseline); `tables=` con umbral; `slots=True`; LRU por schema |
| T3 | `metadata/` ↔ `managers/`: ciclo si el source necesita el manager | El ejecutor DBAPI se inyecta como `CatalogExecutor` (Protocol en `metadata/`, implementación en `managers/`) |
| T4 | Async: `asyncpg`/`aiomysql`/`aiosqlite` tienen paramstyles propios (`$1` en asyncpg) | Traductor por driver async; tests de paridad |
| T5 | Volumen del cambio (≈ 15 k líneas en `metadata/<motor>/`, 40+ ficheros consumidores) | Grupos pequeños, convivencia v0.31–v0.32, trinquete G1 |
| T6 | HSQLDB sin banco | `catalog.py` desde el JSON, marcado pendiente; no bloquea |

### Seguridad

| ID | Riesgo | Mitigación |
|---|---|---|
| S1 | Hoy 95/123 consultas del registry interpolan con `str.format` (mitigado por lista blanca) | El diseño impone bind parameters en todo el SQL de catálogo; identificadores en `SHOW CREATE`/`PRAGMA` citados con los helpers existentes (`quote_mariadb_identifier`) y validados |
| S2 | Privilegios: lecturas por schema pueden necesitar vistas que el usuario no ve (`ALL_*` vs. `DBA_*`, `sys.*` con `VIEW DEFINITION`) | Mismo nivel de privilegio que hoy (`ALL_*`, `sys.*` del propio schema); dorados con el usuario `bench` sin privilegios elevados |
| S3 | Caché con definiciones de routines/vistas en memoria compartida entre hilos | Snapshot inmutable; sin persistencia en disco |

### Rendimiento

| ID | Riesgo | Mitigación |
|---|---|---|
| P1 | Lectura por schema más lenta que por tabla cuando el consumidor solo quiere 1 tabla (`bulk` de una tabla en schema de 5000) | `tables=` (filtro `IN`) por debajo de un umbral medido |
| P2 | Una consulta por schema con `col_description(…::regclass)` por fila (PostgreSQL) cuesta 594 ms con 31 500 columnas | Comentarios como `Kind` aparte y con `LEFT JOIN pg_description` en vez de función por fila (medir en A1) |
| P3 | Paralelizar tipos de objeto agota el pool del consumidor | No se paraleliza en A; solo en F si la medición lo justifica |

## Simplificaciones

- Se borran ≈ 3,4 k líneas inalcanzables (Redshift/Snowflake, si D9-1 = a) y la capa de adaptadores M3.
- Cuatro cachés → una. Tres estilos de parámetros → uno. Cuatro caminos de lectura → dos vistas con criterio único.
- `dump` y `comparar` pierden sus caminos especiales de SQL Server (Q9, `_prefetch.py`) porque el caso general ya es
  por schema.

## Verdict

**GO_CONDICIONAL**

## Conditions or next step

1. **D9-1** (Redshift/Snowflake: retirar o dar de alta) y **D9-2** (forma pública de `get_*`: modelos tipados o tuplas
   con deprecación) decididas por el usuario antes de C1/E2.
2. **H-10** y **H-17** corregidos con `/hotfix`, y las mejoras rápidas **H-16** y **H-14** aplicadas y medidas, antes
   de generar los dorados de A0 (para no congelar fallos ni re-capturar dorados).
3. **A0** (dorados por motor + trinquete G1 + `scripts/bench_metadata.py`) completo antes de cualquier cambio en
   `metadata/` o consumidores.
4. Cada grupo cierra con dorados idénticos (o diferencias listadas y aprobadas) y con su medición antes/después; una
   regresión ≥ 10 % en tiempo o memoria en cualquier flujo bloquea el grupo.
5. IMPLEMENT empieza por **A1** (núcleo + PostgreSQL) en un PR propio; el resto de grupos se aprueban de uno en uno.
