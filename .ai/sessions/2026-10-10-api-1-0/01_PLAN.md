# PLAN + AUDIT_PLAN — API pública 1.0, fase 0.43.0

Fecha: 2026-10-10 · Base: `develop` @ v0.42.1 (`676ee482`) · Origen: `../2026-10-10-plan-pendientes-global/Q6_PLAN_API_1_0.md`
(A1–A6 aceptadas). Solo lectura hasta la aprobación.

## PLAN

### Objetivo

Que `util_bbdd` exponga en la raíz solo los puntos de entrada y sus resultados (13 símbolos) y que los 46 nombres que salen
sigan funcionando durante la serie 0.43–0.x con `DeprecationWarning`, señalando su ruta nueva. Que los dos managers
compartan nombres de ciclo de vida. Sin cambios funcionales: misma clase, mismo objeto, otra ruta.

### Superficie resultante

**Raíz `util_bbdd.__all__` (13)**: `SyncDatabaseManager`, `AsyncDatabaseManager`, `BulkCrud`, `ParallelBulkLoader`,
`DumpOrchestrator`, `DumpConfig`, `DumpResult`, `MigrationPlanner`, `MigrationPlan`, `SchemaComparator`, `SchemaDiff`,
`DatabaseDocumentation`, `DatabaseException`.

**Alias deprecados en la raíz (46)** — todos los destinos ya existen y ya exportan el símbolo (verificado), salvo
`util_bbdd.exceptions`, que es nuevo:

| Ruta nueva | Símbolos |
|---|---|
| `util_bbdd.exceptions` (nuevo) | 31 excepciones: `ConnectionError`, `PoolConnectionError`, `PoolExhaustedError`, `PoolTimeoutError`, `DriverError`, `ValidationError`, `InvalidDatabaseType`, `DatabaseOperationError`, `DatabaseConfigurationError`, `QueryError`, `QueryNotFoundError`, `QueryValidationError`, `QueryParameterError`, `QueryTimeoutError`, `QueryExecutionError`, `ComparerError`, `SchemaDiffValidationError`, `MetadataIntrospectionError`, `DiffReportGenerationError`, `DumpError`, `DumpConstraintError`, `DumpReportError`, `AuditError`, `AuditConfigError`, `AuditFileError`, `AuditDataError`, `AuditExportError`, `AuditValidationError`, `DocumentationError`, `DocumentationConfigError`, `DocumentationRenderError` |
| `util_bbdd.audit` | `AuditEvent`, `AuditSink`, `JsonLinesAuditSink`, `MemoryAuditSink`, `NullAuditSink` |
| `util_bbdd.metadata` | `SyncMetadataProvider`, `AsyncMetadataProvider` (A3) |
| `util_bbdd.connection` | `build_conn_params`, `EngineReadinessAdvisor`, `AdvisoryFinding` |
| `util_bbdd.factory` | `ConnectionFactory`, `PoolFactory` (ver D1) |
| `util_bbdd.async_utils` | `maybe_await` (ver D2) |
| `util_bbdd.dump` | `TableDumpResult` |
| `util_bbdd.migrate` | `MigrationWarning` |

Submódulos públicos estables (documentados como tales en la guía): `exceptions`, `audit`, `metadata`, `connection`,
`factory`, `analysis`, `async_utils`, más los paquetes de cada punto de entrada (`bulk`, `dump`, `migrate`, `comparar`,
`doc`), que ya eran públicos.

**Managers (A4)**:

| Hoy | 0.43.0 |
|---|---|
| `AsyncDatabaseManager.init()` (async) | sin cambios |
| — (sync conecta en `__init__`) | `SyncDatabaseManager.init() -> Self`: idempotente, devuelve `self` (aditivo, sin alias) |
| `AsyncDatabaseManager.release_connection(conn)` | sin cambios (nombre canónico) |
| `SyncDatabaseManager.close_connection(conn=None)` | **`release_connection(conn=None)`** canónico; `close_connection` alias con `DeprecationWarning` |

`release_connection` es el canónico porque es lo que hace (devolver al pool o cerrar la directa), no se confunde con
`close()` y ya es el nombre interno (`SyncConnectionLifecycleManager.release_connection`).

### Rutas afectadas

| Ruta | Cambio |
|---|---|
| `src/util_bbdd/exceptions.py` | **nuevo**: reexporta `_core.exceptions.__all__` (la implementación se queda en `_core`) |
| `src/util_bbdd/__init__.py` | reescrito: 3 imports directos ligeros (managers + `DatabaseException`), 10 perezosos (`_LAZY`), 46 deprecados (`_DEPRECATED`), `__getattr__`, `__dir__`, bloque `TYPE_CHECKING` para los 13 |
| `src/util_bbdd/managers/sync_mgr.py` | `init()`, `release_connection()`, `close_connection()` → alias; el `connection_releaser` interno pasa a `release_connection` |
| `scripts/gen_arquitectura_capas.py` | si el script mide `exceptions.py` como paquete de primer nivel: `LEVEL["exceptions"] = 1` y arista `exceptions → _core` |
| `docs/architecture.md` | pie de figura (versión, fecha, nº de ficheros) |
| `tests/unit/test_top_level_exports.py` | reescrito: fija `__all__` (13), identidad de cada alias con su destino, `DeprecationWarning` por alias (parametrizado, 46), perezosidad (`pandas` no cargado tras `import util_bbdd`, en subproceso) |
| `tests/unit/test_manager_symmetry.py` (nuevo) | `init`/`release_connection` en ambos managers; `close_connection` avisa y delega |
| 30 ficheros de `tests/` | `from util_bbdd import <excepción…>` → `from util_bbdd.exceptions import …` (lista medida en el anexo) |
| `tests/integration/test_mariadb_tls_own_ca.py` | `close_connection` → `release_connection` |
| `docs/` (7 ficheros) + `docs/api/exceptions.md` | imports nuevos; `::: util_bbdd._core.exceptions` → `::: util_bbdd.exceptions` |
| `docs/guides/api_1_0_migration.md` (nuevo) + `mkdocs.yml` | guía de migración 0.42 → 0.43 → 1.0 con la tabla completa |
| `CHANGELOG.md`, `pyproject.toml`, `README.md` | 0.43.0 con sección `Deprecated`; README solo si nombra alguno (medido: 0 imports de símbolos movidos) |

### Componentes implicados

Raíz del paquete, `_core.exceptions` (sin tocar), `managers/sync_mgr.py`, test de exportaciones, docs de API y guías,
script de capas. **No** se tocan `bulk/`, `dump/`, `migrate/`, `comparar/`, `doc/` ni la lógica de los managers.

### Riesgos de regresión

1. Usuarios con `from util_bbdd import X` (X movido): siguen funcionando con aviso. Sin regresión.
2. `from util_bbdd import *`: deja de traer los 46 nombres, **sin aviso** (el `*` solo mira `__all__`). Ruptura
   silenciosa, acotada a quien use `*` (ver D5).
3. `import util_bbdd` deja de cargar pandas/openpyxl/docx/jinja2: código de terceros que dependiera de ese efecto
   lateral (p.ej. `util_bbdd.dump` sin importarlo explícitamente) recibe `AttributeError` en vez de funcionar por
   casualidad — los subpaquetes se cargan en Python al importar el submódulo, no por atributo. Mitigación: `__getattr__`
   también resuelve los nombres de subpaquete públicos (`util_bbdd.dump`, `.bulk`…) vía `import_module` (ver D3).
4. Errores de dependencias opcionales (driver, `docx`…) pasan de aflorar en `import util_bbdd` a aflorar en el primer
   acceso a `util_bbdd.BulkCrud` etc. Es lo deseado; se documenta.

## AUDIT_PLAN

### Riesgos funcionales

| Riesgo | Evidencia | Mitigación |
|---|---|---|
| Alias que no devuelve el mismo objeto (`except util_bbdd.QueryError` dejaría de capturar) | — | Test de identidad `util_bbdd.X is <destino>.X` para los 46 |
| `close_connection` sync con semántica distinta tras el cambio | `sync_mgr.py:275` delega en `session_manager.close_connection` | El alias llama a `release_connection` con el mismo argumento; test con mock del `session_manager` |
| `SyncDatabaseManager.init()` reconecta o duplica pool | sync conecta en `__init__` | `init()` no hace I/O: devuelve `self`; test de identidad y de que no crea pool nuevo |
| Avisos espurios desde la propia librería | `grep` de `from util_bbdd import` en `src/`: 0 en `.py` | Test que importa todos los subpaquetes con `warnings.simplefilter("error", DeprecationWarning)` |
| Docs con imports antiguos | 7 ficheros de `docs/` (anexo) | Se actualizan en el mismo commit; `zensical build --strict` |

### Riesgos técnicos

| Riesgo | Evidencia | Mitigación |
|---|---|---|
| Tiempo de import | Hoy **1,08–1,10 s** en caliente (3,0 s en frío), 80 % en `util_bbdd.comparar` (pandas 255 ms, openpyxl 202 ms, docx 49 ms). Solo bulk/doc perezosos **no** mejora nada: comparar y dump ya cargan pandas | Perezosos los 10 símbolos de `bulk`/`doc`/`dump`/`migrate`/`comparar`; directos solo managers + `DatabaseException`. Sonda medida: **~0,31 s** y sin pandas/jinja2/openpyxl/docx/numpy. Logs `build/logs/api10_importtime_{before,after}_*.txt` |
| Capas | `connection`=4, `factory`=5: reexportar `PoolFactory` desde `connection` sería import hacia arriba | D1: `PoolFactory` sigue en `util_bbdd.factory`. `gen_arquitectura_capas.py` antes (verde, `build/logs/api10_capas_before.txt`) y después |
| Tipado para usuarios | `__getattr__ -> Any` borra el tipo de los 13 perezosos | Bloque `if TYPE_CHECKING:` con los 13; los 46 deprecados quedan `Any` en mypy (aceptable: van a desaparecer) |
| `stacklevel` del aviso | `from m import n` ejecuta `IMPORT_FROM` en C | `stacklevel=2`; el test comprueba que `w.filename` es el del test, no `__init__.py` |
| mkdocstrings sobre reexportaciones (`::: util_bbdd.exceptions`) | griffe resuelve alias de `__all__` | Verificar en `zensical build --strict`; si no renderiza, mantener `::: util_bbdd._core.exceptions` con texto que indique la ruta pública |
| `__module__` de las excepciones sigue siendo `util_bbdd._core.exceptions` (trazas, `repr`) | — | Fuera de alcance: no cambia comportamiento; anotar como pendiente 1.0 |
| `filterwarnings` | `pytest.ini` no convierte avisos en error | No hace falta tocarlo; los tests de alias usan `pytest.warns` |

### Riesgos de seguridad

Ninguno: no cambia SQL, parametrización, credenciales ni manejo de recursos (el alias `close_connection` delega en la
misma ruta de liberación). `import_module` solo recibe rutas de tablas constantes, nunca nombres de usuario.

### Simplificaciones posibles

- Una sola tabla `_DEPRECATED: dict[str, str]` (nombre → módulo) en vez de 46 imports + `__all__` paralelo.
- Reutilizar el patrón de `analysis/__init__.py` (`_SYMBOL_TO_MODULE` + `globals()[name] = value`) para los perezosos;
  los deprecados **no** se cachean en `globals()` para que cada acceso avise.
- Reescribir `test_top_level_exports.py` en vez de añadir otro test de exportaciones.

### Decisiones que necesito confirmar

| # | Decisión | Recomendación |
|---|---|---|
| D1 | `PoolFactory` (y `ConnectionFactory`) en `util_bbdd.factory`, no en `connection` como decía Q6 (capas 4→5) | **Sí**: `factory` pasa a la lista de submódulos estables; `ConnectionFactory` ya está en ambos |
| D2 | `maybe_await` → `util_bbdd.async_utils` (módulo ya existente y sin guion bajo) | **Sí** |
| D3 | Perezosos también dump/migrate/comparar (no solo bulk/doc), y `__getattr__` resuelve los subpaquetes por nombre | **Sí**: es lo único que da la mejora medida (~1,1 s → ~0,3 s) |
| D4 | Otras asimetrías no listadas en A4: `is_db_type_supported`/`validate_db_type_static` solo en sync; `get_query_info`/`get_available_queries` son corrutinas en async y funciones en sync | Añadir los 2 estáticos al async (aditivo, trivial). **No** tocar la asincronía de `get_query_info`/`get_available_queries` (cambiarla rompe y no aporta); queda documentada como diferencia intencional |
| D5 | Regla del prompt de refactor: enfoque solo OO, sin wrappers de función; se acepta la ruptura silenciosa de `from util_bbdd import *` (riesgo 2) y el cambio de `__all__` | **Sí**; se anuncia en `CHANGELOG` (`Changed`) y en la guía |

### Estrategia de tests

- Nuevos: `__all__` exacto (13); parametrizado 46 × (aviso + identidad + ruta del aviso en el mensaje); `dir(util_bbdd)`
  incluye los 13; subproceso: `import util_bbdd` no carga `pandas` y sí carga tras `util_bbdd.BulkCrud`; managers
  simétricos.
- Existentes: 30 ficheros de tests con imports nuevos; deben pasar igual. Ninguno debe emitir los avisos nuevos
  (comprobación: `pytest -W error::DeprecationWarning:util_bbdd` sobre `tests/unit` como paso extra, log en
  `build/logs/`).
- Puerta: ruff, ruff format, mypy (`src tests/unit/test_protocol_conformance.py`), pytest ×2 (sin banco / con
  `scripts/bench_env.example.sh` + `JAVA_HOME`), `python -m build`, `zensical build --strict`,
  `gen_arquitectura_capas.py`.

### Commits previstos (locales)

1. `refactor(api): util_bbdd.exceptions como módulo público de la jerarquía de excepciones`
2. `refactor(api): raíz reducida a 13 puntos de entrada con exportación perezosa y alias deprecados` (incluye tests y docs de imports)
3. `refactor(managers): init y release_connection simétricos; close_connection deprecado`
4. `docs: guía de migración a la API 1.0`
5. `release: v0.43.0 - API pública 1.0 (superficie nueva + alias deprecados)`

### Veredicto

**GO_CONDICIONAL** — condiciones: confirmar D1–D5.

## Anexo: medidas

- `python -X importtime -c "import util_bbdd"` ×3: 3 027 982 µs (frío), 1 103 847 µs, 1 076 393 µs.
- Sonda (paquete vacío + `_core.exceptions` + ambos managers) ×3: 0,322 / 0,301 / 0,316 s; sin pandas.
- Tests que importan desde la raíz símbolos que salen: 30 ficheros (28 `unit`, 2 `integration`), todos excepciones salvo
  `maybe_await`, `build_conn_params`, `ConnectionFactory`.
- Docs: `api/async_utils.md`, `api/audit.md`, `api/index.md`, `examples/async_concurrent_queries.py`,
  `examples/exception_handling.py`, `guides/exceptions.md`, `guides/migration_guide_v0.6.7.md` (histórica: se añade nota,
  no se reescribe).
- `close_connection`/`release_connection` públicos usados en tests: `test_async_database_manager.py`,
  `integration/test_mariadb_tls_own_ca.py`; en `docs/`: 0.
