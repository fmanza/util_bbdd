# Análisis de Refactorización: Unificación de Consultas, Executors y SRP (Python 3.12+)

## 1. Resumen ejecutivo

**Problema a resolver:**
- La librería `util_bbdd` tiene duplicación de lógica entre `database_manager.py` (sync) y `async_database_manager.py` (async).
- Acceso a consultas SQL disperso sin un mecanismo centralizado de resolución y validación.
- `database_queries.py` mezcla responsabilidades: obtención, validación, información, metadatos y documentación.
- No hay clara separación de concerns entre "obtener consulta", "ejecutar consulta" y "validar consulta".
- Gestión de errores inconsistente (falta `raise ... from err` en algunos casos).

**Resultado esperado después de refactorización:**
- **Query Registry unificado:** un componente único que carga `sql_queries.json` y proporciona `QueryDefinition` normalized.
- **Executors desacoplados:** `QueryResolver`, `SyncQueryExecutor`, `AsyncQueryExecutor`, validadores por motor.
- **SRP en managers:** `DatabaseManager` y `AsyncDatabaseManager` delegan resolución/ejecución a ejecutores.
- **Validación avanzada centralizada:** reglas por motor BD desde `database_types.json`.
- **Tests sin dependencias externas:** contrato sync/async, timeout, errores con `raise ... from err`.
- **Documentación actualizada:** README.md, CHANGELOG.md reflejan breaking changes.
- **No backward compatibility:** se informan explícitamente incompatibilidades.

---

## 2. Estado actual (inspección obligatoria)

### 2.1 Estructura de consultas (`sql_queries.json`)
```
- Organización: {motor_bd: {nombre_query: sql_template}}
- Motores soportados: mariadb, oracle, postgresql, hsqldb, sqlserver, sqlite
- Modalidad de parámetros: {placeholder} dentro de strings SQL
- Ejemplo: "obtener_tablas": "SELECT ... WHERE table_schema = '{database}' ..."
- Total de queries por motor: ~18-20 queries frecuentes
```

**Características:**
- Centralizado en `src/util_bbdd/data/sql_queries.json`
- Patrón de parámetros: `{nombre_placeholder}` (regex: `\{(\w+)\}`)
- Consistencia: no hay validación de que placeholders requeridos se proporcionen

### 2.2 Información de tipos de BD (`database_types.json`)
```
- Estructura: {database_types: {motor: {name, description, version_range, drivers, supported_features, connection_params, driver_info}}}
- Información clave:
  - Puertos por defecto (MariaDB: 3306, Oracle: 1521, PostgreSQL: 5432, etc.)
  - Parámetros requeridos y opcionales (host, user, password, database)
  - Características soportadas (transacciones, triggers, procedimientos, etc.)
  - Reglas de validación implícitas (ej. Oracle != MariaDB en contexto/esquema)
```

**Consumo actual:**
- `DatabaseTypeValidator` lo carga y valida tipos de BD.
- Métodos útiles: `validate_db_type()`, `get_db_type_info()`, `get_db_type_examples()`
- **NO se usa explícitamente para validación de placeholders/particularidades de motors**

### 2.3 `DatabaseManager` (sync)
```python
# Inicialización:
__init__(db_type, conn_params, queries_file=None, use_pool=True)
  - Instancia DatabaseQueries para acceso a queries
  - Crea DatabaseQueryExecutor stateless con connection provider/releaser
  - Soporta pooling opcional

# Métodos de acceso de datos:
execute_custom_query(sql, params, fetch_one, timeout)
  - Ejecuta SQL directo usando query_executor
get_tables(), get_views(), get_routines()
  - Usan DatabaseQueries para obtener la SQL y luego ejecutan
get_columns(), get_indices(), get_primary_keys(), etc.
  - Igual patrón

# Gestión de conexiones:
__enter__/__exit__ (context manager)
disconnect()
```

**Problemas identificados:**
- `DatabaseQueryExecutor` es tightly coupled con la instancia de conexión.
- Duplicación de lógica de resolución de queries entre sync y async.
- No hay validación explícita de parámetros antes de ejecutar.

### 2.4 `AsyncDatabaseManager` (async)
```python
# Inicialización:
__init__(db_type, conn_params, use_pool=True, connection_factory=None, pool_factory=None)
  - Integración con factories async
ainit() -> AsyncDatabaseManager
  - Lazy initialization (patrón)

# Métodos:
async get_connection(), async release_connection()
async execute_custom_query(sql, params, fetch_one)
  - Similar a sync pero async

# Diferencias clave con sync:
- No instancia DatabaseQueries directamente (ausente)
- AsyncDatabaseQueryExecutor no tiene acceso a queries
- NO hay get_tables(), get_views(), etc. (funcionalidad faltante)
- Pool factory no siempre implementado (fallback a conexión directa)
```

**Problemas identificados:**
- **Funcionalmente incompleto:** AsyncDatabaseManager no expone `get_tables()`, `get_views()`, etc.
- No usa `DatabaseQueries` centralizado.
- Divergencia clara con versión sync.

### 2.5 `DatabaseQueries` (unificado, pero sin SRP)
```python
# Responsabilidades actuales (VIOLACIÓN DE SRP):
1. Carga de queries desde JSON (_load_queries)
2. Obtención básica (get_query)
3. Conveniencia (get_tables_query, get_columns_query, etc.)
4. Información (get_available_query_names, get_all_queries)
5. Validación (validate_query_parameters, analyze_query_parameters)
6. Metadatos (get_db_type_info, get_config_examples vía db_validator)
7. Documentación (consumido por DatabaseDocumentation)

# Métodos principales:
get_query(query_name, **kwargs) -> str
get_tables_query(database) -> str
get_columns_query(database, table) -> str
get_routines_query(database) -> str
get_storage_inventory_queries(database, tablespace) -> dict[str, str]
[Y más...]

# Metodología de placeholders:
- Usa .format(**kwargs) para reemplazos
- No realiza validación previa (puede fallar en runtime)
```

**Problemas identificados:**
- Mezcla **5 responsabilidades distintas** (SRP violation).
- Manejo de errores inconsistente (algunas excepciones no usan `raise ... from err`).
- No diferencia entre "obtener" y "resolver" (resolver debería incluir validación).
- `database_types.json` no se consulta para validaciones avanzadas por motor.

### 2.6 `DatabaseDocumentation` (docs)
```python
# Entrada principal:
__init__(db_manager, directorio_salida, fichero_salida, imprimir, formatos, headers_file)

# Asunciones:
- db_manager debe ser DatabaseManager (sync)
- Llama a db_manager.get_tables(), get_views(), get_routines(), etc.
- Genera documentos Word, Excel, HTML

# Consumo de APIs:
db_manager.get_tables() -> list
db_manager.get_views() -> list
db_manager.get_routines() -> list
```

**Implicaciones para refactorización:**
- NO debe romperse `get_tables()`, `get_views()`, `get_routines()` en `DatabaseManager`.
- Si se centraliza en executores, asegurar que `DatabaseManager` siga exponiendo estas APIs.

### 2.7 Excepciones actuales
```python
# En database_exceptions.py:
DatabaseError (base)
  ├── DatabaseConnectionError
  ├── DatabasePoolError
  │   ├── DatabasePoolExhaustedError
  │   └── DatabasePoolTimeoutError
  ├── DatabaseDriverError
  ├── DatabaseValidationError
  ├── DatabaseOperationError
  └── DatabaseConfigurationError

# En database_queries.py:
DatabaseQueryError (Exception)  # NO hereda de DatabaseError ❌
```

**Problemas identificados:**
- `DatabaseQueryError` no hereda de `DatabaseError` (inconsistencia).
- Falta `QueryNotFoundError`, `QueryValidationError`, `DatabaseTypeError`, `TimeoutError`.
- No hay logging consistente con formato `raise ... from err`.

---

## 3. Decisiones de diseño (ADR-style)

### ADR-1: Query Registry unificado
**Decisión:** Crear `QueryRegistry` que centralice carga y normalización de `sql_queries.json`.

**Justificación:**
- Actualmente `DatabaseQueries` lo hace, pero mezcla responsabilidades.
- Registry será consumido por `QueryResolver` (validación) y ejecutores.
- Permite versioning futuro de estructuras de queries.

**Implementación:**
```python
class QueryRegistry:
    """Lee sql_queries.json y proporciona QueryDefinition por db_type + query_name."""
    def __init__(self, queries_file: Path | None = None)
    def get_query_definition(self, db_type: str, query_name: str) -> QueryDefinition
    def get_available_queries(self, db_type: str) -> list[str]
```

### ADR-2: Modelo de QueryDefinition
**Decisión:** Definir `QueryDefinition` como dataclass normalizando metadatos.

**Estructura:**
```python
@dataclass
class QueryDefinition:
    name: str                          # ej. "obtener_tablas"
    db_type: str                       # ej. "mariadb"
    sql_template: str                  # template SQL con {placeholders}
    required_params: list[str]         # params obligatorios extraídos
    optional_params: list[str] = field(default_factory=list)
    docstring: str = ""               # descripción
    metadata: dict[str, Any] = field(default_factory=dict)  # data_type, input_format, etc.
```

### ADR-3: Ejecutores desacoplados (SRP)
**Decisión:** Crear tres ejecutores con responsabilidades claras.

**Componentes:**
```python
class QueryResolver:
    """Obtiene QueryDefinition, valida placeholders/params, retorna SQL final."""
    def resolve(self, query_name: str, db_type: str, params: dict) -> ResolvedQuery

class SyncQueryExecutor:
    """Ejecuta SQL sync en conexión del pool/directa."""
    async execute(self, sql: str, params: dict, fetch_one: bool, timeout: float | None) -> Any

class AsyncQueryExecutor:
    """Ejecuta SQL async en conexión del pool/directa."""
    async execute(self, sql: str, params: dict, fetch_one: bool, timeout: float | None) -> Any
```

**Justificación:**
- Clara separación: resolver ≠ ejecutar.
- Permite testing de lógica de resolución sin BD.
- Sync y Async reutilizan registry + resolver.

### ADR-4: Validación avanzada por motor
**Decisión:** Crear validadores por `db_type` que consulten `database_types.json`.

**Estrategia:**
```python
class DatabaseTypeValidator:
    """Válida particularidades de motor desde database_types.json."""
    def validate_placeholder_format(self, db_type: str, placeholders: set[str]) -> bool
    def validate_supported_feature(self, db_type: str, feature: str) -> bool
    def get_placeholder_style(self, db_type: str) -> str  # ej. "%" para PostgreSQL parameterized

class MotorValidators:
    """Registry de validadores por motor."""
    mariadb = MariaDBValidator()
    oracle = OracleValidator()
    # ...
```

**Justificación:**
- Reutilizable para outras áreas de validación.
- Base para reglas futuras complejas.
- Aprovechar `database_types.json` como fuente única de verdad.

### ADR-5: Jerarquía de excepciones unificada
**Decisión:** Expandir `database_exceptions.py` y integrar `DatabaseQueryError`.

```python
class DatabaseError(Exception):
    """Base"""

class QueryError(DatabaseError):
    """Errores en resolución/información de queries"""
    class QueryNotFoundError(QueryError)
    class QueryValidationError(QueryError)
    class QueryParameterError(QueryError)

class DataTypeError(DatabaseError):
    """Errores en validación/información de tipos de BD"""
    class DatabaseTypeNotSupportedError(DataTypeError)

# Mantener compatibilidad:
DatabaseQueryError = QueryNotFoundError  # Alias deprecated
```

### ADR-6: Logging consistente
**Decisión:** Usar `logging.getLogger(__name__)` con formato estructurado + `raise ... from err`.

**Estándares:**
```python
# Cada módulo:
logger = logging.getLogger(__name__)

# En capturas:
try:
    ...
except SomeError as e:
    logger.error(f"Error resolviendo query '{name}': {e}", exc_info=True)
    raise QueryValidationError(f"Falló validación de '{name}'") from e

# Info útil en logs:
# - query_name, db_type, elapsed_ms, param_count, result_rows
```

### ADR-7: Timeouts
**Decisión:** Implementar timeout en layer de ejecutor (no en driver).

**Modalidad:**
```python
# Sync: usar timeout mecánismo del driver (ej. SQLAlchemy execution_options)
# Async: usar asyncio.wait_for wrapping la ejecución
# Tests: mock asyncio.sleep o driver delay, verificar timeout exception

# Exception custom:
class QueryTimeoutError(QueryError):
    pass
```

### ADR-8: API pública unificada
**Decisión:** Managers (DatabaseManager, AsyncDatabaseManager) exponen fachada consistente.

**Contrato:**
```python
# Sync:
dm = DatabaseManager(db_type, conn_params)
dm.get_tables(database) -> list
dm.get_columns(database, table) -> list
dm.execute_query(query_name, **params) -> Any  # Nuevo: por nombre de query

# Async (nuevo):
adm = AsyncDatabaseManager(db_type, conn_params)
await adm.get_tables(database) -> list
await adm.execute_query(query_name, **params) -> Any
```

**Ventaja:** Mismo contrato, swap sync ↔ async.

---

## 4. Modelo unificado de consultas y metadata

### QueryDefinition (normalización)

```json
{
  "mariadb": {
    "obtener_tablas": {
      "sql_template": "SELECT table_name, table_comment, ... FROM information_schema.tables WHERE table_schema = '{database}' ...",
      "required_params": ["database"],
      "optional_params": [],
      "metadata": {
        "category": "introspection",
        "result_type": "table_list",
        "supported_motors": ["mariadb"],
        "charset_awareness": true
      }
    }
  }
}
```

**Mapeo actual → nuevo:**
| Fuente | Destino | Tipo |
|--------|---------|------|
| `sql_queries.json` clave + valor | `QueryDefinition.name`, `sql_template` | 1:1 |
| Regex `\{(\w+)\}` de template | `required_params` (análisis) | Automático |
| `database_types.json[motor]` | `DatabaseTypeDefinition` en memoria | 1:1 |

### DatabaseTypeDefinition

```python
@dataclass
class DatabaseTypeDefinition:
    name: str                              # ej. "MariaDB"
    db_type: str                           # ej. "mariadb" (key)
    version_range: str                     # ej. "5.5.0+"
    default_port: int
    drivers: list[str]                     # ej. ["mariadb", "mysql"]
    supported_features: list[str]          # ej. ["Transacciones ACID", ...]
    required_params: list[str]             # ej. ["host", "user", "password", "database"]
    optional_params: list[str]             # ej. ["port", "charset", ...]
    connection_param_schema: dict[str, Any]  # Detalle de cada parámetro
```

### QueryInfo

No es clase separada; es el resultado de `QueryResolver.resolve()`:

```python
@dataclass
class ResolvedQuery:
    query_definition: QueryDefinition
    final_sql: str                         # SQL con params interpolados
    validated: bool                        # True si pasó validación
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
```

---

## 5. Validación avanzada por motor

### Por motor: decisiones y reglas

#### **MariaDB**
- Placeholders: `{nombre}` (custom, no native)
- Validación simple: verificar parámetros en template
- Particularidades: charset/collation awareness
- Métodos especiales: `get_storage_inventory_queries()` requiere `database`
- → Mantener como está, solo centralizar

#### **Oracle**
- Placeholders: `{nombre}` (custom, no native)
- Particularidades: distingue `esquema` vs `owner`
- Métodos especiales: requiere `tablespace` para inventario físico, no `database`
- Validación: parámetro `esquema` casi siempre requerido
- → **Separar contexto: Oracle → esquema, MariaDB → database**

#### **PostgreSQL**
- Placeholders: `{nombre}` (custom)
- Particularidades: `table_schema` = `database` en terminology de PG
- Métodos especiales: requiere `tablespace` para inventario físico
- Validación: parámetro `database` (en realidad schema)
- → **Normalizar nombre de parámetro a db_context que auto-mapee a "database" o "esquema"**

#### **HSQLDB**
- Placeholders: `{nombre}` (custom)
- Validación: tabla solo puede tener letras, números, guiones y guiones bajos
- Métodos especiales: NO expone inventario de ficheros físicos
- → **Validador específico para nombres de tabla**

#### **SQL Server**
- Placeholders: `{nombre}` (custom)
- Particularidades: esquema = `dbo` por defecto o custom
- Métodos especiales: inventario físico sin parámetros opcionales
- → Similar a Oracle + parámetro default

#### **SQLite**
- Placeholders: `{nombre}` (custom)
- Conexión directa a fichero, no host/port
- Métodos especiales: inventario físico accesible sin parámetros adicionales
- → Caso especial, simplificar

### Validadores a implementar

```python
class MariaDBQueryValidator(DatabaseTypeValidator):
    def validate_parameters(self, query_def: QueryDefinition, params: dict) -> tuple[bool, list[str]]:
        """Valida params para MariaDB; retorna (is_valid, warnings)"""
        # Revisar que {database} es required en "obtener_tablas", etc.
        # Revisar format previo

class OracleQueryValidator(DatabaseTypeValidator):
    def validate_parameters(self, query_def: QueryDefinition, params: dict) -> tuple[bool, list[str]]:
        # Revisar que {esquema} está presente si requerido
        # Convertir db_context → esquema internamente

# ... y así para PostgreSQL, HSQLDB, SQL Server, SQLite
```

---

## 6. Plan "PR por fase" (checklist exacto por archivo)

### PR 0: Preparación (base de infraestructura)

**Objetivo:** Establecer excepciones, modelos y base de tests sin cambios a APIs.

**Cambios por archivo:**
- [ ] `src/util_bbdd/database_exceptions.py`
  - Expandir jerarquía: `QueryError`, `QueryNotFoundError`, `QueryValidationError`, `QueryParameterError`, `DatabaseTypeNotSupportedError`
  - Mantener backward compat con alias deprecated para `DatabaseQueryError`
  - Agregar `QueryTimeoutError`

- [ ] `src/util_bbdd/models.py` (nuevo)
  - `QueryDefinition` dataclass
  - `DatabaseTypeDefinition` dataclass
  - `ResolvedQuery` dataclass

- [ ] `src/util_bbdd/query_registry.py` (nuevo)
  - `QueryRegistry` clase
  - Método `_load_queries()` (refactor desde DatabaseQueries)
  - Método `get_query_definition(db_type, query_name) -> QueryDefinition`
  - Método `get_available_queries(db_type) -> list[str]`
  - Logueo consistente con `raise ... from err`

- [ ] `src/util_bbdd/validators/database_type_validator.py` (refactor)
  - Cambiar imports a excepciones nuevas
  - Preservar API existente

- [ ] `tests/unit/test_query_registry.py` (nuevo)
  - Test carga de queries desde JSON
  - Test `get_query_definition()` existe y tiene estructura correcta
  - Test `get_available_queries()` retorna lista no vacía
  - Test excepción cuando query no existe (QueryNotFoundError)

- [ ] `tests/unit/helpers/mocks.py` (nuevo)
  - Mock de `QueryRegistry` para tests
  - Factory de `QueryDefinition` fake

- [ ] `pyproject.toml`
  - Sin cambios (pytest ya existe)

**Tests a agregar/modificar:**
- `tests/unit/test_query_registry.py` (cero dependencias BD)
- `tests/conftest.py` actualizar fixtures

**Criterios de aceptación:**
```bash
pytest tests/unit/test_query_registry.py -q
# Debe pasar sin errores, 0 BD calls
pytest tests/unit/test_database_exceptions.py -q
# Verifica jerarquía de excepciones
```

**Incompatibilidades introducidas:**
- `DatabaseQueryError` → deprecated (usar `QueryNotFoundError`)
- Cambian atributos de excepciones: `message` ahora required

---

### PR 1: Query Resolver (resolución y validación unificadas)

**Objetivo:** Crear `QueryResolver` que centralice resolución de queries con validación avanzada por motor.

**Cambios por archivo:**
- [ ] `src/util_bbdd/query_resolver.py` (nuevo)
  - `QueryResolver` clase
  - Método `resolve(query_name: str, db_type: str, params: dict) -> ResolvedQuery`
  - Método `_extract_placeholders(sql_template: str) -> set[str]`
  - Método `_validate_params(query_def, params) -> tuple[bool, list[str]]`
  - Logueo con "elapsed_ms", "param_count", "validated" en nivel DEBUG
  - `raise ... from err` en excepciones

- [ ] `src/util_bbdd/validators/__init__.py` (nuevo)
  - Estrategia pattern: `get_type_validator(db_type) -> DatabaseTypeValidator`

- [ ] `src/util_bbdd/validators/mariadb_validator.py` (nuevo)
- [ ] `src/util_bbdd/validators/oracle_validator.py` (nuevo)
- [ ] `src/util_bbdd/validators/postgresql_validator.py` (nuevo)
- [ ] `src/util_bbdd/validators/hsqldb_validator.py` (nuevo)
- [ ] `src/util_bbdd/validators/sqlserver_validator.py` (nuevo)
- [ ] `src/util_bbdd/validators/sqlite_validator.py` (nuevo)
  - Cada uno implementa `validate_parameters(query_def, params) -> tuple[bool, list[str]]`
  - Reglas específicas del motor (ej. HSQLDB: validar nombre tabla)

- [ ] `tests/unit/test_query_resolver.py` (nuevo)
  - Test resolve con params válidos
  - Test QueryValidationError cuando falta parámetro requerido
  - Test QueryParameterError para parámetros inválidos (ej. HSQLDB tabla)
  - Test resolved.final_sql tiene {placeholders} reemplazados
  - Tests por motor (6 motores × 3 scenarios = ~18 tests)
  - Sin BD reales, usar QueryRegistry mock

- [ ] `tests/unit/validators/test_mariadb_validator.py` (nuevo)
- [ ] `tests/unit/validators/test_oracle_validator.py` (nuevo)
- [ ] ... (similarmente para otros motores)

**Criterios de aceptación:**
```bash
pytest tests/unit/test_query_resolver.py -q
# Pasa sin excepciones, 0 BD calls
pytest tests/unit/validators/ -q
# Validadores funcionan correctamente por motor
```

**Incompatibilidades introducidas:**
- Ninguna aún (PR 1 solo agrega, no cambia APIs existentes)

---

### PR 2: Sync Query Executor

**Objetivo:** Refactor de `DatabaseQueryExecutor` en `database_manager.py` para usar `QueryResolver`.

**Cambios por archivo:**
- [ ] `src/util_bbdd/executors/__init__.py` (nuevo)

- [ ] `src/util_bbdd/executors/sync_query_executor.py` (nuevo)
  - `SyncQueryExecutor` clase
  - Depende de `QueryResolver`, `DatabaseTypeValidator`
  - Método `execute_query(query_name: str, db_type: str, params: dict, fetch_one: bool, timeout: float | None) -> Any`
  - Método `execute_custom_query(sql: str, params: dict, fetch_one: bool, timeout: float | None) -> Any`
  - Manejo de timeout via SQLAlchemy `execution_options` o similar
  - Logueo con "elapsed_ms", "result_rows"
  - `raise ... from err` para excepciones capturadas

- [ ] `src/util_bbdd/database_manager.py` (refactor)
  - **NO cambiar signature de `__init__`** (backward compat)
  - Instanciar `QueryRegistry`, `QueryResolver`, `SyncQueryExecutor` internamente
  - Métodos existentes (`get_tables()`, `execute_custom_query()`, etc.) siguen siendo públicos
  - Internamente, delegar a `SyncQueryExecutor.execute_query()`
  - Logueo consistente con `raise ... from err`

- [ ] `tests/unit/test_sync_executor_contract.py` (nuevo)
  - Test contrato: mismos resultados para mismas entradas (sync)
  - Test execute_query por cada query name (ej. "obtener_tablas")
  - Test execute_custom_query con SQL directo
  - Test timeout (mock driver con delay)
  - Test QueryNotFoundError si query name invalida
  - Test QueryValidationError si falta param requerido
  - Sin BD reales, usar mocks de conexión

- [ ] `tests/unit/test_database_manager_backward_compat.py` (nuevo)
  - Verifica que `get_tables()`, `get_views()`, etc. siguen existiendo
  - Verifica que firmas no cambian
  - Verifica que retornan mismo tipo de datos

**Criterios de aceptación:**
```bash
pytest tests/unit/test_sync_executor_contract.py -q
# Pasa sin errores, 0 BD calls
pytest tests/unit/test_database_manager_backward_compat.py -q
# Backward compat OK
# Verifica logging: grep PR-2 en logs de tests
```

**Incompatibilidades introducidas:**
- Ninguna a nivel público (refactor interno)

---

### PR 3: Async Query Executor + AsyncDatabaseManager completude

**Objetivo:** Implementar `AsyncQueryExecutor` y completar `AsyncDatabaseManager` con APIs de introspection.

**Cambios por archivo:**
- [ ] `src/util_bbdd/executors/async_query_executor.py` (nuevo)
  - `AsyncQueryExecutor` clase (similar a SyncQueryExecutor pero async)
  - Método `async execute_query(query_name: str, db_type: str, params: dict, fetch_one: bool, timeout: float | None) -> Any`
  - Timeout via `asyncio.wait_for()`
  - Logueo + `raise ... from err`

- [ ] `src/util_bbdd/async_database_manager.py` (refactor)
  - Instanciar `AsyncQueryExecutor`
  - **Agregar métodos faltantes:**
    - `async get_tables(database) -> list`
    - `async get_views(database) -> list`
    - `async get_columns(database, table) -> list`
    - `async get_routines(database) -> list`
    - ... (todos los métodos que tiene sync)
  - Método `async execute_query(query_name: str, **params) -> Any` (nuevo, por nombre)
  - Mantener `execute_custom_query()` existente
  - **NO cambiar `__init__` signature** (backward compat)

- [ ] `tests/unit/test_async_executor_contract.py` (nuevo)
  - Test contrato: mismos resultados para mismas entradas (async = sync para mismos params)
  - Test métodos faltantes: `get_tables()`, `get_views()`, etc.
  - Test timeout (mock asyncio.sleep con delay)
  - Test QueryNotFoundError, QueryValidationError
  - Sin BD reales, mocks

- [ ] `tests/unit/test_sync_async_contract.py` (nuevo)
  - **Contrato unificado:** dado query_name, db_type, params → sync y async retornan equivalente
  - Usa fixtures compartidas de query definitions + mocks
  - 6 motores × 5 queries = ~30 scenarios

**Criterios de aceptación:**
```bash
pytest tests/unit/test_async_executor_contract.py -q
# Pasa sin errores, 0 BD calls
pytest tests/unit/test_sync_async_contract.py -q
# Contrato unificado verificado
```

**Incompatibilidades introducidas:**
- Ninguna a nivel público (nuevos métodos se agregan, no reemplazan)

---

### PR 4: Validación avanzada por motor (DB-agnostic refinement)

**Objetivo:** Afinar validadores de motor con reglas particulares desde `database_types.json`.

**Cambios por archivo:**
- [ ] `src/util_bbdd/data/database_types.json` (review, posible expansion)
  - Verficar que metadata necesaria para validadores esté presente
  - Agregar campos si es necesario: `placeholder_style`, `context_param_name` (database vs esquema)
  - Ejemplo:
    ```json
    "mariadb": {
      "placeholder_style": "{name}",
      "context_param_name": "database",
      ...
    }
    ```

- [ ] `src/util_bbdd/validators/*.py` (actualizar todos)
  - Consultar `database_types.json` para placeholder_style, context_param_name, etc.
  - Implementar reglas específicas:
    - **MariaDB**: validar charset_awareness (opcional)
    - **Oracle**: mapear `db_context` → `esquema`; validar tablespace si inventario físico
    - **PostgreSQL**: mapear `db_context` → `database`; validar usuario/rol
    - **HSQLDB**: validar formato de nombre tabla (alfanumérico + guiones/guiones bajos)
    - **SQL Server**: mapear context a `dbo` o custom schema
    - **SQLite**: validar fichero path accesible (no BD real, pero lógica de validación)

- [ ] `tests/unit/validators/*.py` (expand)
  - Tests por motor con particularidades
  - ej. Oracle: verificar que mapeo db_context → esquema funciona
  - ej. HSQLDB: verificar que tabla con caracteres inválidos falla

**Criterios de aceptación:**
```bash
pytest tests/unit/validators/ -q
# Todos pasan
grep -r "database_types.json" src/util_bbdd/validators/
# All validators consultan database_types.json
```

**Incompatibilidades introducidas:**
- Si se cambian campos de `database_types.json`, documentar en CHANGELOG

---

### PR 5: Refactor SRP de `database_queries.py`

**Objetivo:** Decomponer `DatabaseQueries` en módulos con responsabilidad única.

**Cambios por archivo:**
- [ ] `src/util_bbdd/database_queries.py` (refactor)
  - **ELIMINAR:**
    - `_load_queries()` → delegado a `QueryRegistry`
    - `validate_query_parameters()` → delegado a `QueryResolver`
    - `analyze_query_parameters()` → delegado a `QueryResolver`
    - Métodos de información: `get_all_queries()`, `get_available_query_names()`

  - **MANTENER (como convenience layer):**
    - `get_query()` → wrapper sobre `QueryResolver`
    - Métodos de conveniencia: `get_tables_query()`, `get_columns_query()`, etc.
    - `get_storage_inventory_queries()` (especial por motor)

  - **NUEVA RESPONSABILIDAD:**
    - `DatabaseQueries` = Convenience API (fachada sobre resolver)
    - Logging simplificado (resolver maneja detalles)

- [ ] `src/util_bbdd/query_convenience.py` (nuevo, opcional)
  - Si `database_queries.py` queda muy pequeño, combinar con otro módulo
  - O mantener como "convenience layer"

- [ ] `tests/unit/test_database_queries_refactored.py` (nuevo)
  - Verifica que métodos de conveniencia siguen funcionando
  - Test backward compat: `get_query()`, `get_tables_query()`, etc.
  - Verifica que delegan correctamente a resolver

- [ ] `src/util_bbdd/doc/database_documentation.py` (verify, posible update)
  - Review consumo de APIs de `DatabaseManager`
  - Si `database_queries.py` cambió, ajustar imports si es necesario
  - Tests deben verificar que NO se rompe

**Criterios de aceptación:**
```bash
pytest tests/unit/test_database_queries_refactored.py -q
# Pasa sin errores
pytest tests/unit/test_documentation_contract.py -q
# documentación no se rompió
```

**Incompatibilidades introducidas:**
- `analyze_query_parameters()` si se eliminan de `DatabaseQueries` (ver si consumers externos lo usan)
- Revisar imports públicos en `__init__.py`

---

### PR 6: Documentación actualizada (README, CHANGELOG, tests de contrato de docs)

**Objetivo:** Actualizar documentación externa y establecer tests para no romper contrato público.

**Cambios por archivo:**
- [ ] `README.md` (actualizar)
  - Sección "Cambios principales en esta versión"
  - Nueva API: `execute_query(query_name, **params)` en ambos managers
  - Nuevas excepciones: `QueryNotFoundError`, `QueryValidationError`, ...
  - Deprecaciones: `DatabaseQueryError` → `QueryNotFoundError`
  - Ejemplos de uso (sync y async)
  - Tabla de incompatibilidades

- [ ] `CHANGELOG.md` (agregar entrada para esta versión)
  - Breaking changes
  - Nuevas features
  - Bugfixes
  - Deprecaciones

- [ ] `docs/migracion_async_sqlalchemy_engine_factory.md` (review)
  - Verificar que no está desactualizado
  - Ajustar si es necesario

- [ ] `tests/unit/test_documentation_contract.py` (nuevo)
  - Verifica que `DatabaseManager` expone `get_tables()`, `get_views()`, etc.
  - Verifica que `AsyncDatabaseManager` también expone lo mismo
  - Verifica tipos de retorno
  - Verifica que `DatabaseDocumentation` puede instanciarse con refactored managers

- [ ] `tests/integration/test_end_to_end_no_db.py` (nuevo, mock-based)
  - E2E sin BD real
  - Flujo: `DatabaseManager → QueryRegistry → QueryResolver → SyncQueryExecutor → результат`
  - Flujo async equivalente
  - Verifica logging, timeouts, errores

**Criterios de aceptación:**
```bash
pytest tests/unit/test_documentation_contract.py -q
pytest tests/integration/test_end_to_end_no_db.py -q
# README y CHANGELOG tienen estructura clara
head -50 README.md | grep -i "breaking\|incompatibilidad"
head -50 CHANGELOG.md | grep -i "v0.2.0\|breaking"
```

**Incompatibilidades introducidas:**
- Lista en CHANGELOG + README

---

## 7. Tests requeridos (contrato, timeout, errores)

### Contrato sync vs async

```python
# Mismo nombre, params → mismo SQL final y metadata
# Ejemplo:
params = {"database": "my_db"}
sync_result = sync_resolver.resolve("obtener_tablas", "mariadb", params)
async_result = async_resolver.resolve("obtener_tablas", "mariadb", params)
assert sync_result.final_sql == async_result.final_sql
```

### Timeout

```python
# Sync: mock driver con delay, verifica QueryTimeoutError
def test_sync_timeout_expires():
    with patch('sqlalchemy.execute', side_effect=lambda: time.sleep(5)):
        executor = SyncQueryExecutor(...)
        with pytest.raises(QueryTimeoutError):
            executor.execute_query("obtener_tablas", "mariadb", {"database": "db"}, timeout=1.0)

# Async: mock asyncio.sleep, verifica timeout
async def test_async_timeout_expires():
    async def slow():
        await asyncio.sleep(5)
    with patch('async_executor.execute_core', side_effect=slow):
        executor = AsyncQueryExecutor(...)
        with pytest.raises(QueryTimeoutError):
            await executor.execute_query(..., timeout=1.0)
```

### Errores con `raise ... from err`

```python
def test_query_not_found_has_cause():
    resolver = QueryResolver(registry_mock)
    with pytest.raises(QueryNotFoundError) as exc_info:
        resolver.resolve("nonexistent", "mariadb", {})
    assert exc_info.value.__cause__ is not None

def test_validation_error_has_cause():
    resolver = QueryResolver(registry_mock, validator_mock)
    with pytest.raises(QueryValidationError) as exc_info:
        resolver.resolve("obtener_tablas", "mariadb", {})  # Missing "database"
    assert exc_info.value.__cause__ is not None
```

### Estructura de test suite

```
tests/
  unit/
    test_query_registry.py
    test_query_resolver.py
    test_sync_executor_contract.py
    test_async_executor_contract.py
    test_sync_async_contract.py
    test_database_manager_backward_compat.py
    test_database_queries_refactored.py
    test_documentation_contract.py
    validators/
      test_mariadb_validator.py
      test_oracle_validator.py
      test_postgresql_validator.py
      test_hsqldb_validator.py
      test_sqlserver_validator.py
      test_sqlite_validator.py
    helpers/
      mocks.py
  integration/
    test_end_to_end_no_db.py
```

**Total tests esperados:** ~150-200 tests (sin dependencias BD reales)

---

## 8. Consistencia de excepciones y logging (normas)

### Jerarquía de excepciones (final)

| Excepción | Cuándo se levanta | Capa responsable | `raise ... from err` |
|-----------|-------------------|------------------|---------------------|
| `QueryNotFoundError` | query_name no existe en registry | QueryRegistry / Resolver | Si de KeyError |
| `QueryValidationError` | Params no cumplen validación | QueryResolver / Validator | Sí |
| `QueryParameterError` | Parámetro inválido (ej. tabla HSQLDB) | DatabaseTypeValidator | Sí |
| `DatabaseTypeNotSupportedError` | db_type no reconocido | QueryResolver / Validator | Sí |
| `QueryTimeoutError` | Timeout en ejecución | SyncQueryExecutor / AsyncQueryExecutor | Sí (de TimeoutError subyacente) |
| `DatabaseConnectionError` | Fallo de conexión | DatabaseManager / AsyncDatabaseManager | Mantener |
| `DatabasePoolError` | Pool agotado/timeout | Mantener | Mantener |
| `DatabaseOperationError` | Operación fallida (ej. SQL syntax) | Executor | Sí |

### Logging estándar

```python
import logging

logger = logging.getLogger(__name__)

# En QueryRegistry:
logger.debug(f"Loading query registry from {path}")
logger.debug(f"Loaded {len(queries)} queries for db_type={db_type}")

# En QueryResolver:
logger.debug(f"Resolving query {query_name} for db_type={db_type} with params={list(params.keys())}")
logger.debug(f"Query resolved in {elapsed_ms}ms, validated={validated}")

# En Executor:
logger.debug(f"Executing query {query_name}, db_type={db_type}, elapsed={elapsed_ms}ms, rows={result_rows}")

# En error:
logger.error(f"Failed to resolve query {query_name}: {e}", exc_info=True)
raise QueryNotFoundError(f"Query '{query_name}' not found for {db_type}") from e
```

### Convención de mensajes

- Claro y conciso
- Incluir `query_name`, `db_type`, `elapsed_ms` donde sea relevante
- No usar print(), siempre logging
- Nivel DEBUG para info rutinaria, ERROR para excepciones

---

## 9. Incompatibilidades (sin backward compat)

### Imports/paths que se eliminan o cambian

| Antes | Después | Acción |
|-------|---------|--------|
| `from database_queries import DatabaseQueryError` | `from database_exceptions import QueryNotFoundError` | Deprecated (alias) |
| (No existe) | `from query_registry import QueryRegistry` | Nuevo |
| (No existe) | `from query_resolver import QueryResolver` | Nuevo |
| (No existe) | `from executors.sync_query_executor import SyncQueryExecutor` | Nuevo |
| (No existe) | `from executors.async_query_executor import AsyncQueryExecutor` | Nuevo |

### Firmas de métodos cambiadas

| Clase | Método | Antes | Después | Incompatibilidad |
|-------|--------|-------|---------|------------------|
| `DatabaseQueries` | `validate_query_parameters()` | Público | Delegado a Resolver | ⚠️ Si consumidor llama directamente |
| `DatabaseQueries` | `analyze_query_parameters()` | Público | Eliminado | ⚠️ Si consumidor lo usa |
| `DatabaseManager` | new | N/A | `execute_query(query_name, **params)` | ✓ Backward compat (método nuevo) |
| `AsyncDatabaseManager` | new | N/A | `get_tables()`, `get_views()`, `execute_query()` | ✓ Nuevos métodos |

### Cambios en nombres de excepciones

| Antigua | Nueva | Acción |
|---------|-------|--------|
| `DatabaseQueryError` | `QueryNotFoundError` | Deprecar: alias en database_exceptions.py |

### Cambios en estructura esperada de JSON

- `sql_queries.json`: Sin cambios de estructura
- `database_types.json`: Posible adición de campos (`placeholder_style`, `context_param_name`), no eliminación

---

## 10. Checklist final de salida

**Validación:**
- [ ] `pytest -q` pasa sin error (todos los tests unitarios, 0 BD reales)
- [ ] `pytest --cov=src/util_bbdd --cov-report=term-missing -q` cobertura mínima 80%
- [ ] Sin warnings en mypy: `mypy src/util_bbdd --strict`
- [ ] Sin errores en ruff: `ruff check src/util_bbdd`
- [ ] Código formateado: `black src/util_bbdd`

**Arquitectura:**
- [ ] Sync y async usan el mismo `QueryRegistry` y `QueryResolver` (DRY)
- [ ] Validación avanzada centralizada en validators por motor
- [ ] `DatabaseDocumentation` sigue funcionando con `DatabaseManager` refactorizado
- [ ] Todos los logs usan `raise ... from err` en excepciones capturadas

**Documentación:**
- [ ] README.md actualizado con nuevas APIs y breaking changes
- [ ] CHANGELOG.md reflejado con incompatibilidades claras
- [ ] Docstrings en todas las clases y métodos públicos
- [ ] Adición de ejemplos de uso en README (sync y async)

**Pruebas:**
- [ ] Contrato sync/async: misma entrada → outputs equivalentes
- [ ] Timeout: test sync y async con mock delay
- [ ] Errores: `raise ... from err` verificado en todos los casos
- [ ] Sin BD reales por defecto (0 dependencias externas en tests)

**Tests de incompatibilidad:**
- [ ] `test_database_manager_backward_compat.py` pasa
- [ ] `test_async_database_manager_completeness.py` pasa
- [ ] `test_documentation_contract.py` pasa

---

## Apéndice: Notas de implementación

### Orden recomendado de ejecución de PRs
1. PR 0 (preparación)
2. PR 1 (Query Resolver)
3. PR 2 (Sync Executor)
4. PR 3 (Async Executor)
5. PR 4 (Validadores por motor)
6. PR 5 (Refactor database_queries.py)
7. PR 6 (Docs)

### Paralelización posible
- PR 1 y PR 2 pueden iniciarse después de PR 0
- PR 3 depende de PR 2 (mismo framework)
- PR 4 es independiente después de PR 1
- PR 5 depende de PR 2 y 3 (refactor debe usar nuevas APIs)
- PR 6 depende de PR 5 (última, documentación final)

### Comunicación durante implementación
- Cada PR debe tener test suite verde antes de merge
- Documentar any decisiones inesperadas en PR description
- Verificar backward compat en cada PR (especialmente PR 2 y 3)

---

**Documento generado:** 6 de marzo de 2026
**Versión objetivo:** 0.2.0 (sin backward compatibility)
**Python mínimo:** 3.12 (alineado con `pyproject.toml` y la política actual del proyecto)
