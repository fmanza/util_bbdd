"""Fachada de compatibilidad de las operaciones batch internas de ``bulk_crud``.

R10b (refactor de reutilización 2026-09-26): el contenido se dividió en ``_driver_quirks``, ``insert_strategies``,
``staging_update``, ``delete_strategies`` y ``executors``. Este módulo re-exporta todos sus nombres (también los
privados que importan los tests) para no romper imports existentes.
"""

from __future__ import annotations

from ._driver_quirks import (
    _MSSQL_MAX_DECIMAL_PRECISION as _MSSQL_MAX_DECIMAL_PRECISION,
    _MSSQL_MAX_DELETE_PARAMS as _MSSQL_MAX_DELETE_PARAMS,
    _MYSQL_MAX_STATEMENT_PARAMS as _MYSQL_MAX_STATEMENT_PARAMS,
    _begin_if_needed as _begin_if_needed,
    _driver_decimal_context as _driver_decimal_context,
    _PlainDecimal as _PlainDecimal,
    _pymssql_plain_decimals as _pymssql_plain_decimals,
    _register_fast_executemany as _register_fast_executemany,
    _wrap_driver_error as _wrap_driver_error,
)
from .delete_strategies import (
    _DEFAULT_SQL_BASED_DELETE_DIALECTS as _DEFAULT_SQL_BASED_DELETE_DIALECTS,
    _MAX_DELETE_PARAMS as _MAX_DELETE_PARAMS,
    DeleteExecutionStrategyProtocol as DeleteExecutionStrategyProtocol,
    DeleteStrategyResolver as DeleteStrategyResolver,
    GenericDeleteStrategy as GenericDeleteStrategy,
    PostgreSQLAnyDeleteStrategy as PostgreSQLAnyDeleteStrategy,
    SqlBasedDeleteStrategy as SqlBasedDeleteStrategy,
)
from .executors import (
    BatchStatementExecutor as BatchStatementExecutor,
    DeleteBatchExecutor as DeleteBatchExecutor,
    _commit_periodico as _commit_periodico,
    validate_chunk_size as validate_chunk_size,
)
from .insert_strategies import (
    DefaultInsertStrategy as DefaultInsertStrategy,
    InsertExecutionStrategyProtocol as InsertExecutionStrategyProtocol,
    InsertStrategyResolver as InsertStrategyResolver,
    MariaDBConnectorInsertStrategy as MariaDBConnectorInsertStrategy,
    MySQLDriverExecutemanyStrategy as MySQLDriverExecutemanyStrategy,
    MySQLMultiRowInsertStrategy as MySQLMultiRowInsertStrategy,
    PostgresCopyStrategy as PostgresCopyStrategy,
    PostgreSQLExecuteValuesStrategy as PostgreSQLExecuteValuesStrategy,
    _RawInsertStrategy as _RawInsertStrategy,
    _uniform_column_types as _uniform_column_types,
)
from .staging_update import (
    _MYSQL_PRIVILEGE_DENIED_ERRNOS as _MYSQL_PRIVILEGE_DENIED_ERRNOS,
    MySQLStagingUpdateStrategy as MySQLStagingUpdateStrategy,
    _mysql_errno as _mysql_errno,
)

__all__: list[str] = [
    "BatchStatementExecutor",
    "DefaultInsertStrategy",
    "DeleteBatchExecutor",
    "DeleteExecutionStrategyProtocol",
    "DeleteStrategyResolver",
    "GenericDeleteStrategy",
    "InsertExecutionStrategyProtocol",
    "InsertStrategyResolver",
    "MySQLDriverExecutemanyStrategy",
    "MySQLMultiRowInsertStrategy",
    "MySQLStagingUpdateStrategy",
    "PostgresCopyStrategy",
    "PostgreSQLAnyDeleteStrategy",
    "PostgreSQLExecuteValuesStrategy",
    "SqlBasedDeleteStrategy",
    "validate_chunk_size",
]
