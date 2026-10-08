---
name: "drivers-connections-audit"
description: "Audita la arquitectura de conexiones, metadata y wiring multimotor de util_bbdd con foco en duplicidades, charset, riesgos por motor y decisiones de refactor trazables."
type: "multi-phase-audit"
audience: "senior-engineer, library-architect, devops"
scope: "workspace"
applies_to: "src/util_bbdd/connection/**,src/util_bbdd/_drivers/**,src/util_bbdd/metadata/**,src/util_bbdd/managers/**"
requires_context: ".github/SHARED_INSTRUCTIONS.md, pyproject.toml"
tags: ["drivers", "connections", "architecture", "database-engines", "refactor", "charsets", "api-breaking"]
version: "1.0.3"
created: "2026-10-08"
updated: "2026-10-08"
status: "FASE 1 ejecutada (/audit-code, veredicto RECHAZADO); premisas corregidas contra el código real (v0.35.4)"
---

# Drivers & Connections Architecture Audit — util_bbdd

**Objetivo**: Auditoría integral de la arquitectura de conexiones a motores de BD (MariaDB, MySQL, PostgreSQL, Oracle, SQL Server, SQLite, HSQLDB). Identifica deuda técnica, duplicidades, vulnerabilidades de seguridad, problemas de rendimiento, y propone refactorización con trazabilidad por motor y fase.

**Scope**: Módulos core de conexión, drivers, metadata y managers. Se pueden romper cambios de API pública.

**Entrega**: Informe AUDIT → PLAN por motor → Propuestas de organización → Resoluciones específicas (charset genérico, etc.).

---

## FASE 1: RECONNAISSANCE (Lectura)

### 1.1 Inventario de Drivers y Motores

**Actividades**:

- Listar todos los motores soportados: claves de `database_types` en `src/util_bbdd/data/database_types.json`
  (leer con `encoding="utf-8"`; en Windows el default cp1252 falla)
- Para cada motor, inventariar:
  - Clases de configuración en `connection/config.py` (`<Motor>ConnectionConfig` y `<Motor>PoolConfig`)
  - Clases de conexión: `connection_<motor>.py`, `async_connection_<motor>.py`, `pool_connection_<motor>.py`,
    `async_pool_connection_<motor>.py` (HSQLDB solo tiene `connection_hsqldb.py`)
  - Parámetros de conexión específicos (charset, encoding, TLS, etc.)
  - Drivers PyPI: `pyproject.toml` solo declara extras para `mariadb` y `mysql`; `oracledb` es dependencia base; el
    resto (psycopg, psycopg_pool, asyncpg, pymssql, pyodbc, aioodbc, jaydebeapi) no tiene extra
  - Catálogo en `metadata/<motor>/catalog.py`, registrado en `metadata/catalog_registry.py` (`_BUILTIN`)
  - **No** usar `validators/<motor>_validator.py` como validadores de conexión: validan parámetros de queries
    (`QueryRegistry`). La validación de `conn_params` está en `connection/builder.py`,
    `_drivers/validator.py` (+ `database_types.json`) y `*Config.from_params`

**Entrega**: Tabla resumen (CSV o tabla Markdown). Estado verificado en FASE 1 (v0.35.4):

```markdown
| Motor      | Sync | Async | Pool sync | Pool async | Catálogo (metadata/) | Driver real (sync / async) | Extra pyproject | Special Params |
|---|---|---|---|---|---|---|---|---|
| **MariaDB** | mariadb | aiomysql | mariadb.ConnectionPool | aiomysql | mariadb/ (catalog, _show_create, common, tables) + adaptativo (solo sync) | mariadb / aiomysql | [mariadb] | charset, encoding_errors, init_command |
| **MySQL**   | pymysql | aiomysql | QueuePool SQLAlchemy | hereda AsyncMariaDBPool | `MySQLCatalog(MariaDBCatalog)` en mariadb/catalog.py (MySQL 8.0.16+) | pymysql / aiomysql | [mysql] | ssl_ca/cert/key/verify_* |
| PostgreSQL | psycopg (v3) | asyncpg | psycopg_pool | asyncpg | postgresql/ (catalog, tables) | psycopg3 / asyncpg (el JSON dice psycopg2: desfase) | — | sslmode, schema→search_path, options |
| Oracle     | oracledb (thin) | connect_async | create_pool | create_pool_async | oracle/ (catalog, indexes, tables) | oracledb | dependencia base | dsn/service_name/sid, oracle_client_path, oracle_thick_mode |
| SQL Server | pymssql (def.) / pyodbc | aioodbc | pool propio (Queue + lock) | aioodbc | sqlserver/ (catalog, common, constraints, indexes, tables) | pymssql / pyodbc / aioodbc | — | encryption, trust_cert, driver_name |
| SQLite     | sqlite3 | aiosqlite | conexión única | aiosqlite | sqlite/catalog.py | stdlib / aiosqlite | — (aiosqlite en dev) | — |
| HSQLDB     | jaydebeapi | — | — | — | hsqldb/catalog.py | jaydebeapi | — | jdbc_url, jdbc_jar, connection_properties |
```

### 1.2 Análisis de Duplicidades y Patrones Comunes

**Actividades**:

- Comparar estructuras de clase `<Motor>ConnectionConfig`:
  - Parámetros comunes (host, port, user, password, database)
  - Parámetros opcionales (timeout, poolsize, ssl, charset, encoding)
  - Métodos duplicados: `from_params()`, `to_driver_kwargs()` (las configs son `@dataclass(frozen=True)`; no hay
    `__post_init__`)
  - Validaciones repetidas

- Comparar protocolos de conexión:
  - `connection/<motor>/connection_*.py` vs `connection/<motor>/async_connection_*.py`
  - Pools: `pool_connection_*.py` existe en **6** motores (HSQLDB no tiene pool); cada uno envuelve un pool nativo
    distinto, así que la duplicidad real está en `close()` / `__del__` / `close_connection`, no en el pool entero
  - **AUDITORÍA INDEPENDIENTE**: MariaDB vs MySQL (drivers, comportamiento, capacidades distintas)

- Introspección de catálogos (metadata):
  - **Los 7 motores tienen dialecto de catálogo** registrado en `metadata/catalog_registry.py`. MySQL usa
    `MySQLCatalog(MariaDBCatalog)` en `metadata/mariadb/catalog.py` (comparte SQL con MariaDB y sobrescribe
    `CHECKS`, `INDEXES` y el parseo de defaults/checks). No existe ningún "GAP MySQL"
  - Métodos de SQL query comunes vs. específicos por motor
  - Tablas auxiliares: `tables.py`, `indexes.py`, `constraints.py` (varían por motor)
  - **Charset detection** (`_charset_detection.py` + `_adaptive_executor.py`): se activa en
    `managers/_catalog_executor.py` solo para conexiones cuyo módulo raíz es `mariadb` o `pymysql`, solo en sync
  - Medir cuánto SQL de catálogo duplica `metadata/reflection.py` (prefetch MSSQL/MySQL) frente a
    `metadata/<motor>/`

- Validación de parámetros de conexión (no de queries):
  - Tres capas: `connection/builder.py` (`_validate_required`), `_drivers/validator.py`
    (`validate_connection_params` contra la lista blanca de `database_types.json`) y `*Config.from_params`
  - Comprobar que las tres aceptan el mismo conjunto de claves
  - `validators/<motor>_validator.py` queda fuera: valida parámetros de queries, no de conexión

**Entrega**: Matriz de duplicidades **medida** (p. ej. `difflib.SequenceMatcher` por líneas no vacías), no
estimada. Resultado de FASE 1 (v0.35.4):

```markdown
| Aspecto | Ubicaciones | LoC | Similitud medida | Prioridad |
|---|---|---|---|---|
| Validación conn_params en 3 capas divergentes | builder.py, _drivers/validator.py + JSON, *Config.from_params | ~1.100 | — (rechaza params válidos) | ALTA |
| URL/engine sync vs async (+ `_sanitize_conn_str` copiado) | factory/sqlalchemy_engine_factory.py, factory/async_sqlalchemy_engine_factory.py | 291 / 348 | 43 % | ALTA |
| Defaults (puertos, pool_size, timeouts) | JSON, builder.py, config.py | — | — | MEDIA |
| DSN Oracle | 12 `makedsn` en 4 ficheros + 2 URLs | ~80 | casi idéntico | MEDIA |
| Mapeo kwargs aiomysql | 3 funciones con listas distintas | ~70 | — | MEDIA |
| `_translate_sql` vs `_paramstyle.to_driver` | metadata/_charset_detection.py | ~30 | — | MEDIA |
| Cierre de pools (`close` / `__del__` / `close_connection`) | 6 × pool_connection_*.py | 229 / 49 / 89 | 38 % / 72 % / 53 % | MEDIA |
| Pools sync completos | 6 × pool_connection_*.py | 1.059 | 32 % (máx. 44 %) | BAJA |
| Conexiones sync / async | 7 + 6 ficheros | 468 / 360 | 32 % / 33 % | BAJA |
| `fetch_all` sync vs async | managers/_catalog_executor.py | 38 / 47 | 56 % | BAJA |
| `_variables.py` por motor | 5 ficheros | 789 | 18 % | — (no es duplicidad) |
```

### 1.3 Auditoría por Motor: Seguridad, Rendimiento, Bugs

**Actividades** (para cada motor):

#### **Seguridad**:
- ¿Se validan/sanitizan todos los parámetros de conexión?
- ¿Se manejan secretos (passwords) de forma segura? (no logs, no repr, no stack traces)
- ¿Se usan conexiones TLS/SSL por defecto o configurables?
- ¿Hay inyección de SQL posible en builders?
- ¿Se escapan identificadores (schema, table, column) en queries dinámicas?
- **MariaDB específico**: ¿Se valida el charset antes de usarlo? (Exploit: `charset=../../../etc/passwd`)

#### **Rendimiento**:
- ¿Pool sizing es configurable y sensible por defecto?
- ¿Hay caching de metadata (introspección)?
- ¿Se reutilizan conexiones en loops masivos (bulk)?
- ¿Hay roundtrips innecesarios a BD? (queries de validación)
- **MariaDB específico**: ¿Charset detection (adaptive executor) añade latencia? ¿Es lazy?

#### **Bugs Residuales** (basado en memoria del repo):

##### **MariaDB (Auditoría Independiente)**
- [RESUELTO H-32] UnicodeDecodeError en lectura de catálogo por charset mismatch
- [RESUELTO H-39] TypeError `charset` no soportado en `mariadb.ConnectionPool()`
- Solución actual: charset UTF-8 forzado + fallback adaptativo
- Charset detection adaptive (v0.33.0+): ¿funciona correctamente? ¿hay regresiones?
- **Preguntas**:
  - ¿Se aplica charset strategy solo a MariaDB o debería ser genérico?
  - ¿El módulo `metadata/mariadb/catalog.py` tiene dependencias en charset detection?
  - ¿Necesita MariaDB 10.x vs 11.x handling diferenciado?

##### **MySQL (Auditoría Independiente)**
- Introspección: SQL directo sobre `information_schema` con `MySQLCatalog(MariaDBCatalog)`
  (`metadata/mariadb/catalog.py`), registrado como `"mysql"` en `catalog_registry.py`. Requiere MySQL 8.0.16+
  (`CHECK_CONSTRAINTS`): MySQL 5.7 está sin soporte declarado en `Kind.CHECKS`
- ¿Hereda problemas de charset de MariaDB o tiene comportamiento diferente?
  - PyMySQL vs aiomysql: ¿manejan charset igual? (`charset` es `None` por defecto: depende del default del driver)
  - El ejecutor adaptativo solo se activa si la conexión es de `pymysql` **sin pool**: con pool la conexión llega
    envuelta por SQLAlchemy (`_ConnectionFairy`) y `_resolve_executor` no la desenvuelve
- MySQL 5.7 (EOL) vs 8.0 vs 8.4: ¿soporte diferenciado?
- **Preguntas**:
  - ¿Debe el ejecutor adaptativo aplicarse igual con y sin pool?
  - ¿Se declara MySQL 5.7 sin soporte o se añade una variante de `CHECKS`?

##### **PostgreSQL** (Auditoría Estándar)
- ¿Encoding correctamente negociado en conexión?
- ¿Charset detection es necesario o PostgreSQL lo maneja internamente?

##### **Oracle** (Auditoría Estándar)
- ¿Maneja NLS_LANG y character sets del lado cliente?
- ¿Hay timeout issues en conexión larga?

##### **SQL Server** (Auditoría Estándar)
- ¿Maneja COLLATE y NVARCHAR correctamente?
- ¿pyodbc connection string soporta UTF-8 settings?

#### **Gaps Conocidos**:
- HSQLDB: conexión sync (JDBC vía jaydebeapi), sin async y sin pool — ¿Intención o deuda técnica?
- SQLite: ¿Debería tener pool en-memory para tests?
- Oracle: ¿Soporta fallback a wallet/TNS como MySQL fallback?

#### **Dos caminos de conexión (auditar ambos)**:
- **Nativo** (managers): `ConnectionFactory` / `PoolFactory` → `connection/<motor>/` → `*Config.to_driver_kwargs()`
- **SQLAlchemy** (`get_sqlalchemy_engine()`, usado por bulk, dump y comparar): `factory/sqlalchemy_engine_factory.py`
  y `factory/async_sqlalchemy_engine_factory.py`, que construyen la URL a mano y no pasan `connect_args`
- Para cada parámetro de seguridad o charset (TLS, `charset`, `init_command`, `sslmode`, `encryption`), comprobar
  que se aplica en **los dos** caminos. `factory/` queda fuera de `applies_to`, pero debe leerse

### 1.4 Verificación: MySQL Introspection Strategy (resuelta en FASE 1)

**Contexto**: la premisa original ("MySQL no tiene catálogo propio") era falsa. MySQL usa SQL directo con
`MySQLCatalog(MariaDBCatalog)`; el reflection genérico de SQLAlchemy (`metadata/reflection.py`) solo se usa en
`reflect_table` / prefetch. Los comandos siguientes sirven como verificación de regresión, no como bloqueador:

```bash
# 1. Baseline real del repo: consumidores metadata MySQL
pytest tests/unit/test_mysql_metadata_consumers.py -q

# 2. Registro y wiring del motor MySQL
pytest tests/unit/test_mysql_engine_registration.py -q

# 3. Contrastar metadata específica de MariaDB vs reflexión genérica
git diff --no-index -- src/util_bbdd/metadata/mariadb/catalog.py src/util_bbdd/metadata/reflection.py

# 4. Contrato de catálogos por reflexión (base compartida)
pytest tests/unit/metadata/test_reflection_catalog.py -q

# 5. Driver connection de MySQL y paridad de wiring
pytest tests/unit/connection/mysql/test_mysql_driver_connection.py -q
```

**Decisión (cerrada)**: se mantiene `MySQLCatalog` como subclase de `MariaDBCatalog`. Mover a
`metadata/mysql/catalog.py` sería solo una reorganización de ficheros; no aporta funcionalidad y no bloquea FASE 2.

### 1.5 MariaDB Version Matrix (C7 RESOLVED)

**Antes de FASE 2, validar**: ¿Qué versiones de MariaDB soportamos y cómo varían?

| Versión | Support Status | info_schema Changes | Charset Issues (H-32/H-39) | Strategy | Test Coverage | Notes |
|---|---|---|---|---|---|---|
| 10.3 (EOL 2023) | ❌ Drop | — | — | — | — | No longer supported |
| 10.4 (EOL 2024-09) | ⚠️ LTS (short window) | Minor | H-32 detected, H-39 fixed in v0.35.2 | DETECT | pytest + mariadb driver | Last 10.x LTS |
| 10.5 (EOL 2025) | ✅ LTS | Minor | H-32/H-39 behavior baseline | DETECT | pytest + mariadb driver | Stable baseline |
| 10.6 (EOL 2026) | ✅ LTS | Minor | Inherited fixes | DETECT | pytest + mariadb driver | Current stable |
| 11.0 (Current) | ✅ GA | ❓ Investigar | ❓ H-32/H-39 still valid? | DETECT (TBD) | pytest + mariadb driver | Pre-FASE-1 test: charset_detect.py |
| 11.1+ (Future) | ✅ Future | ❓ TBD | ❓ TBD | TBD | TBD (add to tox matrix) | Follow upstream |

**Pre-FASE-2 Investigation**:
```bash
# Catálogo base de MariaDB
pytest tests/unit/metadata/test_mariadb_catalog.py -q

# Cobertura específica de SHOW CREATE / DDL de MariaDB
pytest tests/unit/metadata/test_mariadb_show_create.py -q

# Wiring del driver MariaDB
pytest tests/unit/connection/mariadb/test_mariadb_driver_connection.py -q

# Validación complementaria E2E si hay entorno de integración disponible
pytest tests/integration/test_mariadb_engine_e2e.py -q
```

### 1.6 Problem Statement: Charset Genérico (MariaDB → All Engines)

**Context**:
- MariaDB ha requerido decisiones defensivas: charset UTF-8 por defecto, adaptive detection, fallback
- Problema: `information_schema` devuelve caracteres que no coinciden con la negociación client/connection/database
- Soluciones parciales existentes:
  1. Forzar UTF-8 por defecto (H-32)
  2. Detección adaptativa de estado (`CharsetStateDetector`, v0.33.0+)
  3. Fallback de reintentos en managers

**Hallazgos de FASE 1 que acotan la pregunta**:
- La estrategia actual solo cubre: sync + conexión nativa + driver `mariadb`, o `pymysql` sin pool. No cubre async
  (`AsyncManagerCatalogExecutor`), ni el camino SQLAlchemy (`SqlAlchemyCatalogExecutor`, bulk/dump), ni MySQL con pool
- PostgreSQL, Oracle thin, SQLite y SQL Server (pyodbc) negocian UTF-8 por sí mismos: no hay evidencia de que
  necesiten una estrategia equivalente
- v0.35.4 tiene 5 tests rojos en `tests/unit/metadata/test_charset_detection.py` (código y tests divergen en
  `_determine_state` y `_inject_convert`): resolver antes de diseñar nada encima

**Pregunta de diseño**:
- ¿Es este problema EXCLUSIVO de MariaDB o afecta a MySQL y otros? (FASE 1: MariaDB/MySQL; el resto, sin evidencia)
- ¿Cuál es la solución correcta?
  - **Defensiva**: Forzar UTF-8 en TODAS las conexiones (actual, pragmática)
  - **Programática**: Parámetro de configuración `charset_strategy` con opciones: `auto`, `utf8mb4`, `native`, `detect`
  - **Híbrida**: Auto-detectar en conexión, registrar en diagnostics, permitir override
- ¿Quién debe decidir el charset? ¿App o servidor?

**Investigación requerida**:
```python
# Para cada motor, testar:
for engine in [MariaDB, MySQL, PostgreSQL, Oracle, SQLServer, SQLite]:
    # 1. ¿Qué charset negocia por defecto?
    conn = engine.connect()  # Sin especificar charset
    metadata = conn.get_information_schema()
    actual_charset = metadata.get('character_set_client', 'UNKNOWN')

    # 2. ¿Qué pasa si hay mismatch?
    conn2 = engine.connect(charset='utf8')  # Diferente del servidor
    metadata2 = conn2.get_information_schema()  # ¿Error o fallback?

    # 3. ¿Qué hay en columns CHARACTER_SET_NAME?
    columns_charset = query("SELECT CHARACTER_SET_NAME FROM information_schema.COLUMNS ...")
    # ¿Coincide con connection charset? ¿Coincide con database charset?
```

### 1.7 Managers / Bulk / Dump Integration Audit (C2 RESOLVED)

**Contexto**: el scope incluye `managers/`, `bulk/` y `dump/`, pero su integración no estaba auditada. Estos módulos dependen de `connection/` y `metadata/`, así que cambios en las capas inferiores pueden romper el ciclo de vida de conexión, el CRUD masivo o el volcado.

**Auditoría requerida**:

- [x] **Bulk**: `src/util_bbdd/bulk/` — no usa el pool de `connection/`: recibe un `Engine` de SQLAlchemy.
  Depende de `metadata` (facts, source, reflection, catalog_registry, model) y de
  `connection/performance_advisor.py` (que carga `<motor>/_variables.py` al usarse). Sin estrategia de charset
- [x] **Dump**: `src/util_bbdd/dump/` — recibe `Engine`; depende de `metadata` (facts, model, source, reflection).
  Sin estrategia de charset
- [x] **Managers**: `src/util_bbdd/managers/` — usa todas las clases por motor vía `ConnectionFactory` /
  `PoolFactory`, `connection` (params, close, protocols), `factory/` y `metadata` (source, catalog_registry, model,
  `_adaptive_executor`, `_paramstyle`, snapshot_cache, ddl, storage). Caché de metadatos en `SnapshotCache`
  (`metadata/snapshot_cache.py`), usada por `CatalogSource`

Nota: `metadata/_charset/` **no existe**; es la propuesta de FASE 2. El código actual está en
`metadata/_charset_detection.py` y `metadata/_adaptive_executor.py`.

**Entrega**: Matriz de dependencias (verificada en FASE 1):

```markdown
| Módulo | connection/<motor> | connection común | factory/ | metadata/ | Charset-aware | Refactor Impact |
|---|---|---|---|---|---|---|
| bulk | no (recibe Engine) | performance_advisor → <motor>/_variables | no | facts, source, reflection, catalog_registry, model | no | MEDIA: contratos de metadata |
| dump | no (recibe Engine) | no | no | facts, model, source, reflection | no | MEDIA: contratos de metadata |
| managers | sí (todos, vía factories) | params, close, protocols | pool_factory + engine factories | source, catalog_registry, model, _adaptive_executor, _paramstyle, … | parcial (sync; mariadb o pymysql sin pool) | ALTA |
```

---

## FASE 2: PLANNING (Auditoría Propuesta)

### 2.1 Propuestas de Organización (Refactorización Arquitectónica)

**Objetivo**: Agrupar módulos por responsabilidad, eliminar duplicidades, mejorar mantenibilidad.

#### **Opción A: Por Capas Transversales (Recomendada)**

```
src/util_bbdd/
├── connection/
│   ├── _base/                    # [NUEVO] Base clases abstractas
│   │   ├── config.py             # Config abstracta + genérica
│   │   ├── protocols.py          # Protocolos (mantener)
│   │   └── builders.py           # Builders genéricos
│   │
│   ├── _pool/                    # [NUEVO] Pool genérico (rompe duplicidad)
│   │   ├── base_pool.py          # PoolConnection genérica
│   │   └── factory.py            # Pool factory
│   │
│   ├── <motor>/
│   │   ├── config.py             # <Motor>ConnectionConfig + <Motor>PoolConfig
│   │   ├── connection.py         # Sync
│   │   ├── async_connection.py   # Async
│   │   └── pool.py               # Pool (thin wrapper sobre _pool/base_pool.py)
│   │
│   ├── factory.py                # ConnectionFactory (mantener, adaptado)
│   └── __init__.py
│
├── metadata/
│   ├── _base/                    # [NUEVO] Catalog executor genérico
│   │   ├── executor.py           # CatalogExecutor abstracto
│   │   └── models.py             # CatalogResult, ColumnMeta, TableMeta
│   │
│   ├── _charset/                 # [NUEVO] Charset handling genérico
│   │   ├── detection.py          # CharsetStateDetector (v0.33.0+, generalizado)
│   │   ├── strategy.py           # CharsetStrategy (enum: auto, utf8mb4, native, detect)
│   │   ├── validator.py          # Validate charset values
│   │   └── handlers.py           # Remediation handlers
│   │
│   ├── <motor>/
│   │   ├── catalog.py            # <Motor>CatalogExecutor : CatalogExecutor
│   │   └── dialects.py           # Motor-specific SQL dialects
│   │
│   ├── __init__.py
│   └── source.py (mantener)
│
└── validators/
    ├── base.py                   # [NUEVO] Validator abstrato
    └── <motor>/
        └── validator.py          # <Motor>-specific rules
```

**Beneficios**:
- ✅ Base classes centralizadas → code reuse, menos duplicación
- ✅ Pool genérico → consolida `close()` / `__del__` / `close_connection` (~370 LoC, 38-72 % de similitud medida);
  el resto de cada pool envuelve un pool nativo distinto (similitud media 32 %), así que el ahorro realista es menor
  que el estimado inicialmente (~500 LoC)
- ⚠️ Charset strategy genérico → FASE 1 solo encontró evidencia del problema en MariaDB/MySQL; antes de
  generalizar, cerrar los huecos reales (async, camino SQLAlchemy, MySQL con pool)
- ✅ Estructura clara: abstracciones, luego especializaciones

**Migraciones**:
1. Crear `_base/` y `_pool/` con interfaces genéricas
2. Mover código común (from_params, to_driver_kwargs, pool boilerplate)
3. Reescribir <motor>/ para heredar de bases
4. Crear `_charset/` con estrategia configurable
5. Tests de integración por motor: verify each motor still works

**Estimación de Esfuerzo (C6 RESOLVED)**:

| Opción | Esfuerzo (h) | API Break | Regresión Risk | Test Effort (h) | Rollback Strategy | Recomendación |
|---|---|---|---|---|---|---|
| **A: Layered** | 35-45 | Sí (Level 2: imports change) | MEDIO (6-8 motores) | 15-20 | Revert commits + shims | ✅ **Recomendada** si timeline lo permite |
| **B: Monolítico** | 15-20 | No (Level 0: backward compat) | BAJO (1-2 engines) | 8-10 | Simple revert | ✅ **Si conservador**: menos riesgo, adopción gradual |
| **C: Plugin** | 20-30 | No (Level 0) | ALTO (MCP complexity) | 12-15 | Revert + config reset | ❌ **No ahora**: overkill actual, complejidad innecesaria |

#### **Opción B: Monolítico Mejorado (Menos Disruptivo)**

Mantener estructura actual, pero:
- Extraer base classes a `connection/_common.py`
- Crear `metadata/_charset_detection.py` centralizado (ya existe, mejorar)
- Consolidar validadores en `_drivers/validator.py` (eliminar duplicados)

**Beneficios**: Menos cambios de API, adopción gradual
**Drawbacks**: Menos limpio, no escala bien

#### **Opción C: Plugin Architecture (Experimental)**

Cada motor registra su driver en una tabla central:
```python
DRIVERS = {
    "mariadb": DriverProfile(
        config_class=MariaDBConnectionConfig,
        connection_class=MariaDBConnection,
        async_class=AsyncMariaDBConnection,
        pool_class=MariaDBPool,
        charset_strategy="auto",
    ),
    ...
}
```

**Beneficios**: Máxima extensibilidad
**Drawbacks**: Overkill actual, complejidad MCP

---

### 2.2 Resolución: Charset Strategy Genérico

**Contexto**: MariaDB tiene histórico de problemas de charset (H-32, H-39). Pregunta es si estos son:
- Específicos de MariaDB (defecto del driver/servidor)
- Heredables a MySQL (drivers PyMySQL/aiomysql vs mariadb)
- Genéricos a todos los engines (problema universal)

**Propuesta de contrato** (aplicable a todos motores, con defaults diferenciados):

```python
# src/util_bbdd/metadata/_charset/strategy.py

from enum import Enum

class CharsetStrategy(Enum):
    """Estrategia de negociación de charset en conexión."""

    DETECT = "detect"      # Auto-detectar estado + fallback a UTF8MB4 (stable, v0.33.0+)
    UTF8MB4 = "utf8mb4"    # Forzar UTF-8 (seguro, pragmático, recomendado)
    NATIVE = "native"      # Usar del servidor (riesgoso, requiere validación)
    CUSTOM = "custom"      # Parámetro explícito en conexión

# En src/util_bbdd/connection/config.py:

class ConnectionConfig:
    """Base para todas las configs de motor."""

    charset_strategy: CharsetStrategy  # Diferente por motor
    charset_custom: str | None = None  # Si strategy == CUSTOM

    def resolve_charset(self, server_info: dict) -> str:
        """
        Resuelve el charset a usar según strategy.

        CharsetStrategy.DETECT fallback chain (stable, v0.33.0+):
          1. Query server CHARSET state (information_schema.SESSION_VARIABLES)
          2. Validate: client_charset == connection_charset == database_charset
          3. If mismatch → Log warning → Fallback to UTF8MB4 → Reconnect
          4. Return final charset (never None, always fallback to UTF8MB4)

        CharsetStrategy.UTF8MB4:
          - Always returns "utf8mb4" (safest default)

        CharsetStrategy.NATIVE:
          - Returns server charset from server_info, fallback to "utf8mb4" if missing

        CharsetStrategy.CUSTOM:
          - Returns user-provided charset or fallback to "utf8mb4"
        """
        match self.charset_strategy:
            case CharsetStrategy.UTF8MB4:
                return "utf8mb4"  # Safe default
            case CharsetStrategy.NATIVE:
                return server_info.get("charset", "utf8mb4")  # Fallback if missing
            case CharsetStrategy.DETECT:
                return self._detect_and_remediate(server_info)  # Fallback to UTF8MB4 if detection fails
            case CharsetStrategy.CUSTOM:
                return self.charset_custom or "utf8mb4"
```

**Decisión por motor (POR AUDITAR INDEPENDIENTEMENTE)**:

| Motor | Default Strategy | Rationale | Verificación Requerida |
|---|---|---|---|
| **MariaDB** | `DETECT` | Problemas históricos (H-32, H-39), adaptive detection existente (v0.33.0+), stable | ✓ Funciona en producción, fallback OK (validar en FASE 1 test suite) |
| **MySQL** | ⚠️ **UTF8MB4** (propuesto) | Comparte catálogo con MariaDB (`MySQLCatalog`); hoy el adaptativo solo actúa sin pool | Verificar: ¿H-32/H-39 aplican con pymysql? ¿default de charset de aiomysql? |
| PostgreSQL | `UTF8MB4` | PostgreSQL maneja bien UTF-8 internamente | Validar: ¿charset negotiation funciona? |
| Oracle | `NATIVE` | NLS_LANG es responsabilidad del DBA | Validar: DBA pre-configura charset |
| SQL Server | `UTF8MB4` | Moderno, SQL Server 2019+ soporta UTF-8 bien | Validar: pyodbc connection string UTF-8 config |
| SQLite | `UTF8MB4` | SQLite nativo UTF-8 desde v3.8.0 | No-op (SQLite siempre UTF-8) |
| HSQLDB | `NATIVE` | Es JDBC, usa charset del JVM | DBA configura JVM charset |

**⚠️ INVESTIGACIÓN CRÍTICA**:

**Para MariaDB**: ¿El DETECT actual (v0.33.0+) es confiable? En v0.35.4 **no**: 5 tests rojos.
```bash
# Detección y ejecutor adaptativo (5 fallos en v0.35.4: resolver primero)
pytest tests/unit/metadata/test_charset_detection.py -q
pytest tests/unit/metadata/test_mariadb_catalog.py -q
pytest tests/unit/connection/mariadb/test_mariadb_driver_connection.py -q
```

**Para MySQL**: ¿Cuál es la estrategia correcta?
```bash
pytest tests/unit/connection/mysql/test_mysql_driver_connection.py -q
pytest tests/unit/test_mysql_metadata_consumers.py -q
pytest tests/unit/test_mysql_engine_registration.py -q
# Pendiente de crear: test que verifique el ejecutor adaptativo con una conexión pymysql del QueuePool
```

Los ficheros `tests/connection/test_mariadb.py`, `tests/connection/test_mysql.py`,
`tests/metadata/test_mariadb_catalog_charset.py` y `tests/metadata/test_mysql_catalog.py` citados en versiones
anteriores de esta skill **no existen**.

---

### 2.3 Plan de Ejecución por Fases

#### **FASE 2A: Auditoría Profunda (Code Review) — 4-6h**

Por cada motor:
1. Listar todos los archivos relevantes
2. Analizar seguridad (inputs, secrets, SQL injection, SSL/TLS)
3. Identificar bugs con stack trace en tests
4. Medir % de duplicación (diff tools)
5. Proponer refactorización específica

**Entrega**: `audit_phase_2a.md` con hallazgos priorizados (C5 RESOLVED)

**Template de audit_phase_2a.md**:

```markdown
# FASE 2A: Auditoría Profunda — Hallazgos Priorizados

## Resumen Ejecutivo
- P0 (bloquean FASE 4): 5 — S1, B1, B2, S4, T1 (verificados en FASE 1)
- P1: Q1, Y3, M3/Y2, M1, P1, O1
- P2: resto

## P0 CRÍTICOS (Bloquean FASE 4) — resultado de FASE 1

### S1: Credenciales sin escapar en URLs de engine
- **Ubicación**: factory/sqlalchemy_engine_factory.py:180,254,285,336,338; factory/async_sqlalchemy_engine_factory.py:214,304,344,395
- **Impacto**: contraseña `a@evil.example:3306/x?` → host `evil.example` (reproducido con `make_url`)

### B1: Lista blanca de database_types.json rechaza parámetros válidos
- **Ubicación**: _drivers/validator.py (`validate_connection_params`), connection/builder.py:74
- **Impacto**: `oracle_thick_mode`, `close_timeout`, `pool_name`, `options`, `target_session_attrs` → ValidationError;
  docs/guides/drivers.md documenta `oracle_thick_mode=True`

### B2: Oracle thick mode no llega a la conexión directa
- **Ubicación**: connection/config.py (`OracleConnectionConfig.to_driver_kwargs`), connection/oracle/pool_connection_oracle.py:110

### S4: El camino SQLAlchemy ignora TLS y charset
- **Ubicación**: factory/sqlalchemy_engine_factory.py (`create_engine` sin `connect_args`)

### T1: v0.35.4 publicada con 10 tests rojos
- **Ubicación**: tests/unit/metadata/test_charset_detection.py (5), tests/unit/test_docs_version.py (5)

## P1 MAYORES (Impactan Arquitectura)

### H.P1.1: Cierre de pools duplicado
- **Ubicación**: 6 × pool_connection_<motor>.py (HSQLDB no tiene pool)
- **Código**: close/__del__/close_connection ≈ 370 LoC, similitud 38-72 % (medida); pools completos 32 %
- **Refactor**: FASE 4.2

### H.P1.2: Coste de la detección de charset
- **Ubicación**: src/util_bbdd/metadata/_charset_detection.py, managers/_catalog_executor.py:242
- **Problema**: `diagnose()` = 8 roundtrips en la primera consulta de cada executor y otra vez tras cada SystemError
- **Refactor**: FASE 4.1 → una sola consulta de variables, sin re-detección en reintentos

...etc

## Por Motor: Hallazgos Específicos

### MariaDB (Auditoría Independiente)
- **Seguridad**: ⚠️ `charset` sin lista blanca; `init_command` acepta SQL arbitrario desde conn_params; `charset` e
  `init_command` independientes (charset=latin1 mantiene SET NAMES utf8mb4)
- **Rendimiento**: 8 roundtrips de diagnóstico; `init_command` manual en cada checkout del pool
- **Bugs**: tests de `test_charset_detection.py` en rojo; adaptativo ausente en async; `encoding_errors="replace"`
  corrompe datos sin aviso

### MySQL (Auditoría Independiente)
- **Introspection**: SQL directo con `MySQLCatalog(MariaDBCatalog)` (8.0.16+)
- **Charset**: adaptativo solo sin pool (Y2)
- **Drivers**: aiomysql descarta `ssl_*` → async sin TLS aunque se configure (Y3)

...etc (PostgreSQL, Oracle, SQL Server, SQLite, HSQLDB: ver informe de FASE 1)

## Recomendaciones FASE 2B (Diseño)

1. Escolher Opción A (Layered 35-45h) o B (Monolítico 15-20h) basado en timeline
2. Crear task list per sub-fase 4.1-4.4 con asignaciones
3. Define test strategy per motor (what regresses?)
```

**Mapping**: cada hallazgo P0 → FASE 3 (validación) → sub-fase de FASE 4 que lo corrige (S1/S4 → nueva sub-fase
de factories; B1 → 4.4; B2 → 4.2; T1 → antes de cualquier sub-fase)

#### **FASE 2B: Diseño Detallado — 2-3h**

1. Elegir Opción A (recomendada) o Opción B/C basado en contexto
2. Especificar contrato de interfaces (abstract base classes)
3. Mappear migraciones: old path → new path
4. Diseñar tests de integración para cada motor
5. Plan de breaking changes y deprecations

**Entrega**: `design_phase_2b.md` + ADR si cambios sustanciales

#### **FASE 2C: Risk Assessment — 1-2h**

1. ¿Qué puede romperse?
2. ¿Qué drivers externos dependen de esto?
3. ¿Necesita deprecation phase o direct migration?
4. Rollback strategy

**Entrega**: `risk_assessment_phase_2c.md`

---

## FASE 3: AUDIT_PLAN (Validación de Plan)

### 3.1 Checklist de Validación

- [ ] ¿Se revisó cada motor con profundidad mínima?
- [ ] ¿Se identificaron TODOS los archivos implicados?
- [ ] ¿Se cuantificó la duplicación (% LoC)?
- [ ] ¿Se definió claramente el charset strategy?
- [ ] ¿Se propuso organización sin contradicciones?
- [ ] ¿Se documentaron riesgos y mitigaciones?
- [ ] ¿Se tiene rollback plan?

### 3.2 Preguntas de Clarificación (si aplica)

Si no hay respuesta a alguna, escalera a usuario:

1. ¿Es aceptable romper API pública de `connection/<motor>/` o debe mantenerse compatible?

2. **MariaDB-específico**: ¿El charset strategy DETECT actual (v0.33.0+) es suficientemente estable para producción, o se prefiere UTF8MB4 forzado?

3. **MySQL-específico (AUDITORÍA INDEPENDIENTE)**:
   - ¿MySQL hereda problemas de charset (H-32, H-39) de MariaDB?
   - ¿El ejecutor adaptativo debe aplicarse también con pool (hoy solo sin pool)?
   - ¿Se declara MySQL 5.7 fuera de soporte (no tiene `CHECK_CONSTRAINTS`)?
   - ¿Cuál es el default charset strategy para MySQL: UTF8MB4, DETECT, o NATIVE?

4. ¿Debe aplicarse charset strategy genérica a TODOS los motores o solo a mariadb/mysql?

5. ¿Quién decide el charset: la librería (defaults inteligentes) o el usuario final (override explícito)?

6. ¿Se requiere bumpear versión mayor (0.36.0) o puede ser 0.35.5?

7. ¿Es HSQLDB critical? ¿Puede quedar sin async/pool indefinidamente?

---

## FASE 4: IMPLEMENT (Refactorización y Resoluciones)

Dependiendo del scope, puede ejecutarse en sub-fases por motor o por aspecto:

### 4.1 Sub-fase: Charset Strategy Genérico (todos motores)

**Entrega**:
- `src/util_bbdd/metadata/_charset/strategy.py` (nuevo)
- `src/util_bbdd/metadata/_charset/detection.py` (refactor desde existing)
- `src/util_bbdd/metadata/_charset/validator.py` (nuevo)
- Actualizar `connection/config.py` para todos los <Motor>ConnectionConfig
- Tests de integration: charset_strategy = DETECT | UTF8MB4 | NATIVE | CUSTOM

**Validación**: pytest mariadb, mysql, postgresql, oracle, sqlserver, sqlite

### 4.2 Sub-fase: Base Classes y Pool Genérico (Opción A)

**Entrega**:
- `src/util_bbdd/connection/_base/config.py`
- `src/util_bbdd/connection/_base/protocols.py` (refactor from existing)
- `src/util_bbdd/connection/_pool/base_pool.py`
- Refactor: `connection/<motor>/pool.py` → thin wrappers
- Refactor: `connection/config.py` consolidation

**Validación**: pytest connection.* (all engines), check no API break

### 4.3 Sub-fase: Metadata Executor Genérico

**Entrega**:
- `src/util_bbdd/metadata/_base/executor.py` (abstract)
- Refactor: `metadata/<motor>/catalog.py` → inherit from base
- Consolidate charset detection + adaptive remediation

**Validación**: pytest metadata.* (test per engine)

### 4.4 Sub-fase: Validadores Consolidados

**Entrega**:
- Consolidate `_drivers/validator.py` + `validators/<motor>_validator.py`
- Centralizar reglas en tabla

**Validación**: pytest validators.*

---

## FASE 5: AUDIT_CODE (Verificación de Implementación)

### 5.1 Code Review Checklist

- [ ] ¿Todas las clases base son abstractas con `@abstractmethod`?
- [ ] ¿Cada motor hereda correctamente?
- [ ] ¿No hay regresión: se ejecutan TODOS los tests previos?
- [ ] ¿Charset strategy funciona para cada motor?
- [ ] ¿Async y pool funcionan en paralelo?
- [ ] ¿Documentación actualizada (docstrings, ADRs)?
- [ ] ¿Coverage no bajó?

### 5.2 Per-Motor Smoke Tests

```bash
# Smoke tests reales del árbol actual
pytest tests/unit/connection/mariadb/test_mariadb_driver_connection.py -q
pytest tests/unit/connection/mysql/test_mysql_driver_connection.py -q
pytest tests/unit/test_async_postgresql.py -q
pytest tests/unit/test_async_oracle.py -q
pytest tests/unit/test_async_sqlserver.py -q
pytest tests/unit/test_async_sqlite.py -q

# Metadata y catálogos por motor
pytest tests/unit/metadata/test_mariadb_catalog.py -q
pytest tests/unit/metadata/test_postgresql_catalog.py -q
pytest tests/unit/metadata/test_oracle_catalog.py -q
pytest tests/unit/metadata/test_sqlserver_catalog.py -q
pytest tests/unit/metadata/test_sqlite_catalog.py -q
pytest tests/unit/metadata/test_hsqldb_catalog.py -q
pytest tests/unit/metadata/test_reflection_catalog.py -q
```

### 5.3 Integration Tests

```bash
# Bulk operations across all engines
pytest tests/unit/bulk -q

# Documentation generation (triggers metadata heavily)
pytest tests/unit/test_database_documentation.py -q
```

---

## FASE 6: VERSION (Cierre y Trazabilidad)

> **Las plantillas de esta fase son ilustrativas.** Las cifras que contienen ("~500 LoC", "60 % pool
> duplication", charset para "all engines") proceden de la estimación inicial y FASE 1 no las confirmó (similitud
> medida de pools: 32 %; problema de charset solo evidenciado en MariaDB/MySQL). Rellenar CHANGELOG, ADR y commits
> con las cifras medidas tras IMPLEMENT.

### 6.1 Changelog Entry

```markdown
## [0.36.0] - 2026-10-XX

### Changed
- **BREAKING**: Refactored connection architecture (Opción A):
  - `connection/_base/` (new) centralizes common patterns
  - `connection/_pool/base_pool.py` (new) eliminates ~500 LoC duplication
  - All motors now inherit from `ConnectionConfig` and `BasePoolConnection`
  - Migration guide: [ADR-XXX](docs/adr/adr-xxx-connection-refactor.md)

### Added
- **Charset Strategy** (all engines):
  - New `metadata/_charset/strategy.py` with `CharsetStrategy` enum
  - Configurable per-connection: `DETECT`, `UTF8MB4` (default), `NATIVE`, `CUSTOM`
  - Replaces ad-hoc fixes (H-32, H-39) with unified approach
  - MariaDB: Charset detection + adaptive fallback now available to all engines

### Fixed
- MariaDB H-32 / H-39: UnicodeDecodeError and charset pool errors fully resolved via unified strategy
- Validators consolidated: eliminated duplication between `_drivers/` and `validators/`
```

### 6.2 ADR (Architecture Decision Record)

```markdown
# ADR-XXX: Connection Architecture Refactor & Unified Charset Strategy

**Status**: Accepted (v0.36.0)

**Context**:
- 7 database engines, repetitive boilerplate (pool, config, async)
- MariaDB charset issues (H-32, H-39) required ad-hoc defensive code
- Problem is systemic, not MariaDB-specific

**Decision**:
1. Refactor connection layer: abstract base classes eliminate 60% pool duplication
2. Introduce CharsetStrategy enum: DETECT, UTF8MB4, NATIVE, CUSTOM (config-driven)
3. Move charset detection out of MariaDB specifics → `metadata/_charset/` (reusable)

**Consequences**:
- ✅ ~500 LoC removed (pool boilerplate)
- ✅ Charset negotiation unified and testable
- ⚠️  API break: `connection/<motor>/` classes now inherit from `_base/`, may affect imports
- ⚠️  Deprecation: old import paths (`from connection.mariadb import MariaDBConnection`) still work 1 release, then removed

**Migrations**:
- Old: `from util_bbdd.connection.mariadb import MariaDBConnection`
- New: `from util_bbdd.connection import MariaDB; conn = MariaDB(...)`
- Or: `from util_bbdd.connection.mariadb import MariaDBConnection` (backward compat layer)

**Testing**:
- Per-motor integration tests pass (mariadb, mysql, postgresql, oracle, sqlserver, sqlite)
- Charset strategy tests cover: DETECT with fallback, UTF8MB4 forced, NATIVE, CUSTOM
- Async + pool + sync all functional
```

### 6.3 Trazabilidad de Cambios

**Commit pattern**:
```
refactor(connection): extract base classes and pool generics

- Create connection/_base/{config,protocols}.py
- Create connection/_pool/base_pool.py
- Migrate pool_connection_*.py to inherit from base_pool.PoolConnection
- Reduce ~500 LoC duplication across 7 engines
- Fully backward compatible via import shims in connection/__init__.py

Related: H-32, H-39 (charset fixes now subsumed into unified strategy)
Tests: connection/*, metadata/test_charset_strategy.py
```

```
feat(metadata): unified charset strategy for all database engines

- Add metadata/_charset/{strategy,detection,validator}.py
- CharsetStrategy enum: DETECT, UTF8MB4, NATIVE, CUSTOM
- Each engine has default strategy (MariaDB=DETECT, others=UTF8MB4)
- Replaces MariaDB-specific hardcoded fixes with configurable approach
- Users can override: ConnectionConfig(charset_strategy=CharsetStrategy.NATIVE)

Related: H-32, H-39
Tests: metadata/test_charset_strategy.py
```

### 6.4 Observabilidad y Diagnostics

**Nuevo**: Logging y diagnostics para charset resolution

```python
# Cuando se resuelve charset, loguear:
logger.debug(f"Charset strategy {self.charset_strategy} → resolved to {charset_final}")
logger.debug(f"Server charset info: {server_info}")
# Si hay fallback:
logger.warning(f"Charset mismatch detected: {actual} vs {expected}, applying fallback strategy")
```

---

## APÉNDICE: Template de Ejecución

### Invocación para Copilot Chat o Claude Code

```markdown
Usa drivers-connections-audit SKILL.

Objetivo: Auditoría completa de arquitectura de conexiones.
Alcance: src/util_bbdd/connection/**, metadata/**, _drivers/**, managers/**
Fases: RECONNAISSANCE → PLANNING → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION

Motores: MariaDB, MySQL, PostgreSQL, Oracle, SQL Server, SQLite, HSQLDB
Aspectos: Seguridad, Rendimiento, Bugs, Duplicidades, Charset (genérico)
Propuestas: Organización (Opción A / B / C), Charset Strategy, Break Changes

Entregar:
1. audit_phase_2a.md (hallazgos por motor + priorización)
2. design_phase_2b.md (refactorización detallada)
3. risk_assessment_phase_2c.md (mitigaciones)
4. ADR-XXX.md (decisión arquitectónica)

API break aceptada. Versión target: 0.36.0
```

### Invocación por Motor (si se prefiere granular)

```markdown
Audita drivers-connections-audit SKILL para MariaDB únicamente.

Fases: RECONNAISSANCE (1h) → PLANNING (30m) → AUDIT_PLAN (15m)
Entregar: hallazgos de seguridad, rendimiento, bugs, charset strategy aplicable
```

---

## Referencias

- **Existing charset work**: `src/util_bbdd/metadata/_charset_detection.py`, `_adaptive_executor.py`
- **Hotfixes history**: Memoria repo `mariadb_*.md` (H-32, H-39, H-41, etc.)
- **Architecture docs**: `.github/SHARED_INSTRUCTIONS.md`, `docs/architecture.md`
- **Connection config**: `src/util_bbdd/connection/config.py` (7 engine configs)
- **Metadata**: `src/util_bbdd/metadata/source.py`, per-motor `catalog.py`

---

*Skill version: 1.0.3 | Last updated: 2026-10-08 | Premisas corregidas tras FASE 1 | Approved for breaking changes*
