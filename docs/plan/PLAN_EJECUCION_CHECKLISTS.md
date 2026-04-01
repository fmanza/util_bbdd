# Plan de Ejecución: PRs por Fase (Checklist Ejecutable)

**Documento de referencia rápida para ejecutar cada fase de refactorización.**

Cada sección contiene:
- Archivos a crear/modificar
- Tests a crear
- Comando de validación
- Incompatibilidades

---

## PR 0: Preparación (Base de infraestructura)

**Duración estimada:** 2-3 horas
**Dependencias:** Ninguna
**Status:** 🔄 No iniciado

### Archivos a crear

#### 1. `src/util_bbdd/models.py` (nuevo)
```python
"""Modelos de datos unificados para queries y tipos de BD"""
from dataclasses import dataclass, field
from typing import Any

@dataclass
class QueryDefinition:
    """Define una consulta SQL con metadatos"""
    name: str                               # ej. "obtener_tablas"
    db_type: str                            # ej. "mariadb"
    sql_template: str                       # SQL template con {placeholders}
    required_params: list[str]              # [database, tabla]
    optional_params: list[str] = field(default_factory=list)
    docstring: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class DatabaseTypeDefinition:
    """Define capacidades de un motor de BD"""
    name: str                               # ej. "MariaDB"
    db_type: str                            # ej. "mariadb"
    version_range: str                      # ej. "5.5.0+"
    default_port: int
    drivers: list[str]
    supported_features: list[str]
    required_params: list[str]
    optional_params: list[str]
    connection_param_schema: dict[str, Any]

@dataclass
class ResolvedQuery:
    """Resultado de resolver una query con parámetros"""
    query_definition: QueryDefinition
    final_sql: str                          # SQL con params interpolados
    validated: bool                         # True si pasó validación
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
```

#### 2. `src/util_bbdd/database_exceptions.py` (actualizar)
Agregar al final del archivo:
```python
# ✅ QueryError y subclases (nuevas)
class QueryError(DatabaseError):
    """Base para errores de resolución de queries"""
    pass

class QueryNotFoundError(QueryError):
    """Query no existe en registry"""
    pass

class QueryValidationError(QueryError):
    """Validación de parámetros falló"""
    pass

class QueryParameterError(QueryError):
    """Parámetro específico inválido"""
    pass

class QueryTimeoutError(QueryError):
    """Query ejecutó pero excedió timeout"""
    pass

class DatabaseTypeNotSupportedError(DatabaseError):
    """Tipo de BD no soportado"""
    pass

# ✅ Alias deprecated para backward compat
DatabaseQueryError = QueryNotFoundError
```

#### 3. `src/util_bbdd/query_registry.py` (nuevo)
```python
"""Centraliza carga y acceso a definiciones de queries desde sql_queries.json"""
import json
import logging
import re
from pathlib import Path
from typing import Any

from .database_exceptions import QueryNotFoundError
from .models import QueryDefinition

PARAMETER_PATTERN = r"\{(\w+)\}"

class QueryRegistry:
    """Lee sql_queries.json y proporciona QueryDefinition normalizadas"""

    def __init__(self, queries_file: Path | None = None) -> None:
        self.logger = logging.getLogger(__name__)
        default_path = Path(__file__).parent / "data" / "sql_queries.json"
        self.queries_file = queries_file or default_path
        self.queries = self._load_queries()
        self.logger.debug(f"✅ QueryRegistry initialized with {len(self.queries)} db_types")

    def _load_queries(self) -> dict[str, dict[str, str]]:
        """Carga consultas desde JSON"""
        try:
            with open(self.queries_file, encoding="utf-8") as f:
                queries = json.load(f)
            self.logger.debug(f"✅ Loaded queries from {self.queries_file}")
            return queries
        except FileNotFoundError as e:
            self.logger.error(f"❌ Queries file not found: {self.queries_file}")
            raise FileNotFoundError(f"Queries file not found: {self.queries_file}") from e
        except json.JSONDecodeError as e:
            self.logger.error(f"❌ Invalid JSON in queries file: {e}")
            raise ValueError(f"Invalid JSON in queries file: {e}") from e

    def get_query_definition(self, db_type: str, query_name: str) -> QueryDefinition:
        """Obtiene QueryDefinition para un db_type + query_name"""
        db_type = db_type.lower().strip()

        try:
            sql_template = self.queries[db_type][query_name]
        except KeyError as e:
            msg = f"Query '{query_name}' not found for db_type '{db_type}'"
            self.logger.error(f"❌ {msg}")
            raise QueryNotFoundError(msg) from e

        required_params = self._extract_placeholders(sql_template)

        return QueryDefinition(
            name=query_name,
            db_type=db_type,
            sql_template=sql_template,
            required_params=list(required_params),
            metadata={"source": "sql_queries.json"}
        )

    def get_available_queries(self, db_type: str) -> list[str]:
        """Lista nombres de queries disponibles para un db_type"""
        db_type = db_type.lower().strip()
        return list(self.queries.get(db_type, {}).keys())

    def _extract_placeholders(self, sql_template: str) -> set[str]:
        """Extrae nombres de placeholders del template"""
        return set(re.findall(PARAMETER_PATTERN, sql_template))
```

#### 4. `tests/unit/conftest.py` (crear si no existe)
```python
"""Fixtures compartidas para tests unitarios"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock

@pytest.fixture
def temp_queries_file(tmp_path):
    """Crea un archivo temporal de queries para testing"""
    import json
    queries = {
        "mariadb": {
            "obtener_tablas": "SELECT * FROM information_schema.tables WHERE table_schema = '{database}'",
            "columnas_tabla": "SELECT * FROM information_schema.columns WHERE table_schema = '{database}' AND table_name = '{tabla}'"
        },
        "oracle": {
            "obtener_tablas": "SELECT * FROM all_tables WHERE owner = '{esquema}'"
        }
    }
    file_path = tmp_path / "test_queries.json"
    with open(file_path, "w") as f:
        json.dump(queries, f)
    return file_path

@pytest.fixture
def mock_connection():
    """Mock de conexión BD"""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    return conn
```

### Tests a crear

#### `tests/unit/test_query_registry.py` (nuevo)
```python
"""Tests para QueryRegistry (sin dependencias BD)"""
import pytest
from pathlib import Path
from util_bbdd.query_registry import QueryRegistry
from util_bbdd.database_exceptions import QueryNotFoundError

def test_load_queries_success(temp_queries_file):
    """Test carga exitosa de queries"""
    registry = QueryRegistry(temp_queries_file)
    queries = registry.get_available_queries("mariadb")
    assert "obtener_tablas" in queries
    assert "columnas_tabla" in queries

def test_get_query_definition_exists(temp_queries_file):
    """Test obtención de QueryDefinition existente"""
    registry = QueryRegistry(temp_queries_file)
    qdef = registry.get_query_definition("mariadb", "obtener_tablas")
    assert qdef.name == "obtener_tablas"
    assert qdef.db_type == "mariadb"
    assert "database" in qdef.required_params
    assert "{database}" in qdef.sql_template

def test_get_query_definition_not_found(temp_queries_file):
    """Test excepción cuando query no existe"""
    registry = QueryRegistry(temp_queries_file)
    with pytest.raises(QueryNotFoundError) as exc:
        registry.get_query_definition("mariadb", "nonexistent")
    assert "nonexistent" in str(exc.value)
    assert exc.value.__cause__ is not None

def test_db_type_case_insensitive(temp_queries_file):
    """Test que db_type es case-insensitive"""
    registry = QueryRegistry(temp_queries_file)
    qdef1 = registry.get_query_definition("MariaDB", "obtener_tablas")
    qdef2 = registry.get_query_definition("mariadb", "obtener_tablas")
    assert qdef1.sql_template == qdef2.sql_template

def test_extract_placeholders():
    """Test extracción de placeholders"""
    registry = QueryRegistry(temp_queries_file)
    placeholders = registry._extract_placeholders("SELECT * WHERE schema = '{database}' AND table = '{tabla}'")
    assert placeholders == {"database", "tabla"}

def test_get_available_queries_empty(temp_queries_file):
    """Test lista vacía para db_type inexistente"""
    registry = QueryRegistry(temp_queries_file)
    queries = registry.get_available_queries("nonexistent_db")
    assert queries == []
```

### Archivos a actualizar

#### `src/util_bbdd/database_exceptions.py`
✅ Ver sección "Archivos a crear" → punto 2

#### `pyproject.toml`
Sin cambios (pytest ya existe)

### Validación

```bash
# Ejecutar tests PR 0
pytest tests/unit/test_query_registry.py -v

# Verificar estructura de excepciones
pytest tests/unit/ -k "exception" -v

# Coverage
pytest tests/unit/test_query_registry.py --cov=src/util_bbdd.query_registry --cov-report=term-missing

# Esperado: ✅ Todos los tests pasan
# Esperado: 0 llamadas a base de datos
```

### Incompatibilidades introducidas

- `DatabaseQueryError` es ahora alias de `QueryNotFoundError` (backward compat)
- Nuevas excepciones disponibles pero sin breaking changes aún

---

## PR 1: Query Resolver (Resolución + Validación)

**Duración estimada:** 4-5 horas
**Dependencias:** PR 0 completado
**Status:** 🔄 No iniciado

### Archivos a crear

#### 1. `src/util_bbdd/query_resolver.py` (nuevo)
```python
"""Resuelve queries: obtiene SQL + valida parámetros por motor"""
import logging
import time
from typing import Any

from .database_exceptions import (
    QueryNotFoundError,
    QueryValidationError,
    QueryParameterError,
)
from .models import QueryDefinition, ResolvedQuery
from .query_registry import QueryRegistry
from .validators import get_type_validator

class QueryResolver:
    """Resuelve queries con validación avanzada por motor"""

    def __init__(self, registry: QueryRegistry | None = None) -> None:
        self.logger = logging.getLogger(__name__)
        self.registry = registry or QueryRegistry()

    def resolve(
        self,
        query_name: str,
        db_type: str,
        params: dict[str, Any] | None = None
    ) -> ResolvedQuery:
        """Resuelve query: obtiene definición, valida, interpola parámetros"""
        params = params or {}
        start_time = time.time()

        try:
            # Obtener definición
            query_def = self.registry.get_query_definition(db_type, query_name)

            # Validar parámetros
            validator = get_type_validator(db_type)
            is_valid, warnings = validator.validate_parameters(query_def, params)

            if not is_valid:
                msg = f"Validation failed for query '{query_name}' on db_type '{db_type}'"
                self.logger.error(f"❌ {msg}")
                raise QueryValidationError(msg)

            # Interpolar SQL
            final_sql = self._interpolate_sql(query_def.sql_template, params)

            elapsed_ms = (time.time() - start_time) * 1000
            self.logger.debug(
                f"✅ Query resolved: name={query_name}, db_type={db_type}, "
                f"elapsed_ms={elapsed_ms:.2f}, param_count={len(params)}"
            )

            return ResolvedQuery(
                query_definition=query_def,
                final_sql=final_sql,
                validated=True,
                warnings=warnings,
                metadata={"elapsed_ms": elapsed_ms}
            )

        except (QueryNotFoundError, QueryValidationError):
            raise
        except Exception as e:
            self.logger.error(f"❌ Error resolving query '{query_name}': {e}", exc_info=True)
            raise QueryParameterError(f"Failed to resolve query '{query_name}'") from e

    def _interpolate_sql(self, template: str, params: dict[str, Any]) -> str:
        """Interpola parámetros en template SQL"""
        try:
            return template.format(**params)
        except KeyError as e:
            msg = f"Missing required parameter: {e}"
            raise QueryParameterError(msg) from e
```

#### 2. `src/util_bbdd/validators/__init__.py` (nuevo)
```python
"""Validadores de queries por motor de BD"""
from .base_validator import DatabaseTypeValidator
from .mariadb_validator import MariaDBValidator
from .oracle_validator import OracleValidator
from .postgresql_validator import PostgreSQLValidator
from .hsqldb_validator import HSQLDBValidator
from .sqlserver_validator import SQLServerValidator
from .sqlite_validator import SQLiteValidator

_VALIDATORS = {
    "mariadb": MariaDBValidator(),
    "oracle": OracleValidator(),
    "postgresql": PostgreSQLValidator(),
    "hsqldb": HSQLDBValidator(),
    "sqlserver": SQLServerValidator(),
    "sqlite": SQLiteValidator(),
}

def get_type_validator(db_type: str) -> DatabaseTypeValidator:
    """Obtiene validador para db_type"""
    db_type = db_type.lower().strip()
    if db_type not in _VALIDATORS:
        raise ValueError(f"Unsupported db_type: {db_type}")
    return _VALIDATORS[db_type]
```

#### 3. `src/util_bbdd/validators/base_validator.py` (nuevo)
```python
"""Clase base para validadores de BD"""
from abc import ABC, abstractmethod
from typing import Any
from util_bbdd.models import QueryDefinition

class DatabaseTypeValidator(ABC):
    """Base para validadores específicos de motor"""

    @abstractmethod
    def validate_parameters(
        self,
        query_def: QueryDefinition,
        params: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """Valida parámetros para esta query en este motor

        Returns:
            (is_valid, warnings_list)
        """
        pass
```

#### 4-9. Validadores por motor (esqueleto)
```python
# src/util_bbdd/validators/mariadb_validator.py
from .base_validator import DatabaseTypeValidator
from typing import Any
from util_bbdd.models import QueryDefinition

class MariaDBValidator(DatabaseTypeValidator):
    def validate_parameters(
        self,
        query_def: QueryDefinition,
        params: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        warnings = []

        # Verificar parámetros requeridos
        for req_param in query_def.required_params:
            if req_param not in params or params[req_param] is None:
                return False, [f"Missing required parameter: {req_param}"]

        # MariaDB específico: validar charset si está presente
        if "charset" in params and params["charset"] not in ["utf8", "utf8mb4", "latin1"]:
            warnings.append(f"Unusual charset: {params['charset']}")

        return True, warnings
```

**Crear similarmente:** `oracle_validator.py`, `postgresql_validator.py`, `hsqldb_validator.py`, `sqlserver_validator.py`, `sqlite_validator.py`

### Tests a crear

#### `tests/unit/test_query_resolver.py` (nuevo)
```python
"""Tests para QueryResolver"""
import pytest
from util_bbdd.query_resolver import QueryResolver
from util_bbdd.query_registry import QueryRegistry
from util_bbdd.database_exceptions import (
    QueryValidationError,
    QueryParameterError,
)

def test_resolve_with_valid_params(temp_queries_file):
    """Test resolución exitosa con parámetros válidos"""
    registry = QueryRegistry(temp_queries_file)
    resolver = QueryResolver(registry)

    resolved = resolver.resolve(
        "obtener_tablas",
        "mariadb",
        {"database": "test_db"}
    )

    assert resolved.validated
    assert "test_db" in resolved.final_sql
    assert resolved.query_definition.name == "obtener_tablas"

def test_resolve_missing_required_param(temp_queries_file):
    """Test excepción cuando falta parámetro requerido"""
    registry = QueryRegistry(temp_queries_file)
    resolver = QueryResolver(registry)

    with pytest.raises(QueryValidationError) as exc:
        resolver.resolve("obtener_tablas", "mariadb", {})  # Falta "database"

    assert exc.value.__cause__ is not None

def test_resolve_all_placeholder_interpolated(temp_queries_file):
    """Test que todos los placeholders se interpolan"""
    registry = QueryRegistry(temp_queries_file)
    resolver = QueryResolver(registry)

    resolved = resolver.resolve(
        "columnas_tabla",
        "mariadb",
        {"database": "mydb", "tabla": "users"}
    )

    assert "{" not in resolved.final_sql
    assert "mydb" in resolved.final_sql
    assert "users" in resolved.final_sql

def test_resolve_metadata_includes_elapsed_ms(temp_queries_file):
    """Test que metadata incluye elapsed_ms"""
    registry = QueryRegistry(temp_queries_file)
    resolver = QueryResolver(registry)

    resolved = resolver.resolve("obtener_tablas", "mariadb", {"database": "db"})
    assert "elapsed_ms" in resolved.metadata
    assert resolved.metadata["elapsed_ms"] >= 0
```

#### `tests/unit/validators/test_mariadb_validator.py` (nuevo)
```python
"""Tests para MariaDB validator"""
import pytest
from util_bbdd.validators import get_type_validator
from util_bbdd.models import QueryDefinition

def test_mariadb_validator_valid_params():
    """Test validación exitosa"""
    validator = get_type_validator("mariadb")
    qdef = QueryDefinition(
        name="obtener_tablas",
        db_type="mariadb",
        sql_template="...",
        required_params=["database"]
    )

    is_valid, warnings = validator.validate_parameters(qdef, {"database": "mydb"})
    assert is_valid
    assert warnings == []

def test_mariadb_validator_missing_param():
    """Test falla sin parámetro requerido"""
    validator = get_type_validator("mariadb")
    qdef = QueryDefinition(
        name="obtener_tablas",
        db_type="mariadb",
        sql_template="...",
        required_params=["database"]
    )

    is_valid, warnings = validator.validate_parameters(qdef, {})
    assert not is_valid
```

**Crear similarmente:** tests para otros validadores

### Validación

```bash
pytest tests/unit/test_query_resolver.py -v
pytest tests/unit/validators/ -v

# Expectedado: ✅ Todos pasan, 0 BD calls
```

### Incompatibilidades introducidas

- Ninguna aún (nuevos componentes, APIs existentes sin cambios)

---

## PR 2: Sync Query Executor

**Duración estimada:** 4-5 horas
**Dependencias:** PR 0, PR 1 completados
**Status:** 🔄 No iniciado

### Archivos a crear

#### `src/util_bbdd/executors/__init__.py`
```python
"""Executores de queries (sync y async)"""
```

#### `src/util_bbdd/executors/sync_query_executor.py`
```python
"""Ejecutor de queries sync"""
import logging
import time
from typing import Any

from ..database_exceptions import QueryTimeoutError, DatabaseOperationError
from ..query_resolver import QueryResolver
from ..query_registry import QueryRegistry

class SyncQueryExecutor:
    """Ejecuta queries SQL de forma sync"""

    def __init__(
        self,
        connection_provider,
        connection_releaser,
        registry: QueryRegistry | None = None,
        resolver: QueryResolver | None = None
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.connection_provider = connection_provider
        self.connection_releaser = connection_releaser
        self.registry = registry or QueryRegistry()
        self.resolver = resolver or QueryResolver(self.registry)

    def execute_query(
        self,
        query_name: str,
        db_type: str,
        params: dict[str, Any] | None = None,
        fetch_one: bool = False,
        timeout: float | None = None
    ) -> Any:
        """Resuelve y ejecuta una query por nombre"""
        params = params or {}

        try:
            # Resolver query
            resolved = self.resolver.resolve(query_name, db_type, params)

            # Ejecutar
            return self.execute_custom_query(
                resolved.final_sql,
                fetch_one=fetch_one,
                timeout=timeout
            )

        except Exception as e:
            self.logger.error(f"❌ Error executing query '{query_name}': {e}", exc_info=True)
            raise DatabaseOperationError(f"Failed to execute query '{query_name}'") from e

    def execute_custom_query(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        fetch_one: bool = False,
        timeout: float | None = None
    ) -> Any:
        """Ejecuta SQL custom"""
        conn = None
        start_time = time.time()

        try:
            conn = self.connection_provider()

            # Aplicar timeout si se especifica
            if timeout is not None:
                # SQLAlchemy: execution_options(timeout=...)
                pass

            cursor = conn.cursor()
            cursor.execute(sql, params or {})

            result = cursor.fetchone() if fetch_one else cursor.fetchall()

            elapsed_ms = (time.time() - start_time) * 1000
            result_rows = 1 if fetch_one else len(result) if result else 0
            self.logger.debug(f"✅ Query executed: elapsed_ms={elapsed_ms:.2f}, result_rows={result_rows}")

            return result

        except TimeoutError as e:
            raise QueryTimeoutError(f"Query execution exceeded timeout") from e

        finally:
            if conn:
                self.connection_releaser(conn)
```

### Tests a crear

#### `tests/unit/test_sync_executor_contract.py`
```python
"""Tests para SyncQueryExecutor (contrato)"""
import pytest
from unittest.mock import MagicMock, patch
from util_bbdd.executors.sync_query_executor import SyncQueryExecutor
from util_bbdd.query_registry import QueryRegistry
from util_bbdd.database_exceptions import QueryTimeoutError

def test_execute_query_by_name(temp_queries_file):
    """Test ejecución de query por nombre"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [("table1",), ("table2",)]
    mock_conn.cursor.return_value = mock_cursor

    provider = MagicMock(return_value=mock_conn)
    releaser = MagicMock()

    registry = QueryRegistry(temp_queries_file)
    executor = SyncQueryExecutor(provider, releaser, registry)

    result = executor.execute_query("obtener_tablas", "mariadb", {"database": "db"})
    assert result == [("table1",), ("table2",)]

def test_execute_custom_query(temp_queries_file):
    """Test ejecución de SQL custom"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = ("value",)
    mock_conn.cursor.return_value = mock_cursor

    provider = MagicMock(return_value=mock_conn)
    releaser = MagicMock()

    registry = QueryRegistry(temp_queries_file)
    executor = SyncQueryExecutor(provider, releaser, registry)

    result = executor.execute_custom_query("SELECT 1", fetch_one=True)
    assert result == ("value",)

def test_connection_released_on_error(temp_queries_file):
    """Test que conexión se libera aunque haya error"""
    mock_conn = MagicMock()
    mock_conn.cursor.side_effect = RuntimeError("DB error")

    provider = MagicMock(return_value=mock_conn)
    releaser = MagicMock()

    registry = QueryRegistry(temp_queries_file)
    executor = SyncQueryExecutor(provider, releaser, registry)

    with pytest.raises(Exception):
        executor.execute_custom_query("SELECT 1")

    releaser.assert_called_once_with(mock_conn)
```

### Validación

```bash
pytest tests/unit/test_sync_executor_contract.py -v
pytest tests/unit/test_database_manager_backward_compat.py -v

# Esperado: ✅ Todos pasan
```

### Incompatibilidades introducidas

- Ninguna a nivel público (refactor interno)

---

## PR 3: Async Query Executor + Completude AsyncDatabaseManager

**Duración estimada:** 4-5 horas
**Dependencias:** PR 0-2 completados
**Status:** 🔄 No iniciado

### Archivos a crear

#### `src/util_bbdd/executors/async_query_executor.py`
```python
"""Ejecutor de queries async"""
import asyncio
import logging
import time
from typing import Any

from ..database_exceptions import QueryTimeoutError, DatabaseOperationError
from ..query_resolver import QueryResolver
from ..query_registry import QueryRegistry

class AsyncQueryExecutor:
    """Ejecuta queries SQL de forma async"""

    def __init__(
        self,
        connection_provider,
        connection_releaser,
        registry: QueryRegistry | None = None,
        resolver: QueryResolver | None = None
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.connection_provider = connection_provider
        self.connection_releaser = connection_releaser
        self.registry = registry or QueryRegistry()
        self.resolver = resolver or QueryResolver(self.registry)

    async def execute_query(
        self,
        query_name: str,
        db_type: str,
        params: dict[str, Any] | None = None,
        fetch_one: bool = False,
        timeout: float | None = None
    ) -> Any:
        """Resuelve y ejecuta una query por nombre (async)"""
        params = params or {}

        try:
            resolved = self.resolver.resolve(query_name, db_type, params)
            return await self.execute_custom_query(
                resolved.final_sql,
                fetch_one=fetch_one,
                timeout=timeout
            )
        except Exception as e:
            self.logger.error(f"❌ Error executing query '{query_name}': {e}", exc_info=True)
            raise DatabaseOperationError(f"Failed to execute query '{query_name}'") from e

    async def execute_custom_query(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        fetch_one: bool = False,
        timeout: float | None = None
    ) -> Any:
        """Ejecuta SQL custom (async)"""
        conn = None
        start_time = time.time()

        try:
            conn = await self.connection_provider()

            # Función de ejecución
            async def do_execute():
                cursor = await conn.cursor() if hasattr(conn, 'cursor') else conn
                await cursor.execute(sql, params or {})
                return await cursor.fetchone() if fetch_one else await cursor.fetchall()

            # Aplicar timeout si se especifica
            if timeout is not None:
                result = await asyncio.wait_for(do_execute(), timeout=timeout)
            else:
                result = await do_execute()

            elapsed_ms = (time.time() - start_time) * 1000
            self.logger.debug(f"✅ Async query executed: elapsed_ms={elapsed_ms:.2f}")

            return result

        except asyncio.TimeoutError as e:
            raise QueryTimeoutError(f"Async query execution exceeded timeout") from e

        finally:
            if conn:
                await self.connection_releaser(conn)
```

### Tests a crear

#### `tests/unit/test_async_executor_contract.py`
```python
"""Tests para AsyncQueryExecutor"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from util_bbdd.executors.async_query_executor import AsyncQueryExecutor
from util_bbdd.query_registry import QueryRegistry
from util_bbdd.database_exceptions import QueryTimeoutError

@pytest.mark.asyncio
async def test_async_execute_query(temp_queries_file):
    """Test ejecución async de query por nombre"""
    mock_conn = AsyncMock()
    mock_cursor = AsyncMock()
    mock_cursor.fetchall.return_value = [("table1",), ("table2",)]
    mock_conn.cursor.return_value = mock_cursor

    provider = AsyncMock(return_value=mock_conn)
    releaser = AsyncMock()

    registry = QueryRegistry(temp_queries_file)
    executor = AsyncQueryExecutor(provider, releaser, registry)

    result = await executor.execute_query("obtener_tablas", "mariadb", {"database": "db"})
    assert result == [("table1",), ("table2",)]

@pytest.mark.asyncio
async def test_async_timeout(temp_queries_file):
    """Test timeout en async"""
    async def slow_provider():
        await asyncio.sleep(10)
        return AsyncMock()

    provider = slow_provider
    releaser = AsyncMock()

    registry = QueryRegistry(temp_queries_file)
    executor = AsyncQueryExecutor(provider, releaser, registry)

    with pytest.raises(QueryTimeoutError):
        await executor.execute_query(
            "obtener_tablas",
            "mariadb",
            {"database": "db"},
            timeout=0.1
        )
```

#### `tests/unit/test_sync_async_contract.py`
```python
"""Tests para verificar contrato unificado sync/async"""
import pytest

def test_sync_async_same_resolver_output(temp_queries_file):
    """Verificar que sync y async usan el mismo resolver"""
    # Ambos executores usen QueryRegistry y QueryResolver iguales
    # Result final_sql debe ser idéntico
    pass
```

### Validación

```bash
pytest tests/unit/test_async_executor_contract.py -v
pytest tests/unit/test_sync_async_contract.py -v

# Esperado: ✅ Todos pasan (requiere pytest-asyncio)
```

### Incompatibilidades introducidas

- Ninguna a nivel público

---

## PR 4: Validadores avanzados por motor (refinamiento)

**Duración estimada:** 3-4 horas
**Dependencias:** PR 0-3 completados
**Status:** 🔄 No iniciado

### Archivos a actualizar

- `src/util_bbdd/validators/oracle_validator.py` → mapear db_context a esquema
- `src/util_bbdd/validators/postgresql_validator.py` → mapear db_context a database
- `src/util_bbdd/validators/hsqldb_validator.py` → validar nombres de tabla
- Otros validadores → refinar reglas

### Validación

```bash
pytest tests/unit/validators/ -v --cov=src/util_bbdd.validators

# Esperado: ✅ 80%+ coverage
```

---

## PR 5: Refactor SRP de `database_queries.py`

**Duración estimada:** 3-4 horas
**Dependencias:** PR 2-4 completados
**Status:** 🔄 No iniciado

### Cambios principales

- `database_queries.py` → wrapper convenience sobre resolver
- Mantener métodos `get_tables_query()`, `get_columns_query()`, etc.
- Eliminar `validate_query_parameters()`, `analyze_query_parameters()`
- Logueo consistente

### Validación

```bash
pytest tests/unit/test_database_queries_refactored.py -v
pytest tests/unit/test_documentation_contract.py -v

# Esperado: ✅ DatabaseDocumentation no se rompe
```

---

## PR 6: Documentación final (README, CHANGELOG, tests E2E)

**Duración estimada:** 2-3 horas
**Dependencias:** PR 0-5 completados
**Status:** 🔄 No iniciado

### Cambios

- README.md → sección "Breaking Changes" + nuevas APIs
- CHANGELOG.md → entrada v0.2.0 con incompatibilidades
- Tests E2E sin BD reales

### Validación

```bash
pytest tests/integration/test_end_to_end_no_db.py -v

# Verifica README y CHANGELOG
head -30 README.md | grep -i "breaking\|incompatibilidad"
head -30 CHANGELOG.md | grep -i "0.2.0\|breaking"

# Esperado: ✅ Documentación clara
```

---

## Final: Checklist de Salida Completa

```bash
# 1. Tests unitarios
pytest tests/unit/ -q --cov=src/util_bbdd --cov-report=term-missing
# Esperado: 80%+ coverage, 0 fallos

# 2. Tests integración (sin BD reales)
pytest tests/integration/ -q
# Esperado: 0 fallos

# 3. Linting
ruff check src tests
ruff format --check src tests
# Esperado: 0 errores

# 4. Type checking
mypy src
# Esperado: 0 errores

# 5. Docs
grep -i "breaking" README.md
grep -i "v0.2.0" CHANGELOG.md
# Esperado: Secciones presentes y claras

# 6. Backward compat
pytest tests/unit/test_database_manager_backward_compat.py -q
pytest tests/unit/test_documentation_contract.py -q
# Esperado: ✅ Todos pasan

# 7. Finales
pytest -q
# Esperado: ✅ 100% de tests pasan
```

---

**Documento generado:** 6 de marzo de 2026
**Próximo paso:** Ejecutar PR 0
