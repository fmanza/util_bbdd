"""Helpers para construir conn_params de SyncDatabaseManager por motor."""

import dataclasses

from collections.abc import Callable
from typing import Any

from .config import (
    HSQLDBConnectionConfig,
    MariaDBConnectionConfig,
    MariaDBPoolConfig,
    OracleConnectionConfig,
    OraclePoolConfig,
    PostgreSQLConnectionConfig,
    PostgreSQLPoolConfig,
    SQLiteConnectionConfig,
    SQLitePoolConfig,
    SQLServerConnectionConfig,
    SQLServerPoolConfig,
)


def _default(config_cls: type, name: str) -> Any:
    """Valor por defecto del campo ``name`` de una ``*Config``: los defaults viven solo en las configs."""
    for config_field in dataclasses.fields(config_cls):
        if config_field.name == name and config_field.default is not dataclasses.MISSING:
            return config_field.default
    raise KeyError(f"{config_cls.__name__}.{name} no tiene valor por defecto")


def build_conn_params(db_type: str, **kwargs: Any) -> dict[str, Any]:
    """Construye parámetros de conexión normalizados por tipo de base de datos.

    Args:
        db_type: Tipo de base de datos.
        **kwargs: Parámetros de conexión y opciones específicas del motor.

    Returns:
        Diccionario conn_params listo para SyncDatabaseManager.

    Raises:
        ValueError: Si el tipo de base no es soportado o faltan parámetros requeridos.
    """
    builders: dict[str, Callable[[dict[str, Any], str], dict[str, Any]]] = {
        "mariadb": _build_mariadb_params,
        "mysql": _build_mariadb_params,
        "oracle": _build_oracle_params,
        "postgresql": _build_postgresql_params,
        "hsqldb": _build_hsqldb_params,
        "sqlserver": _build_sqlserver_params,
        "sqlite": _build_sqlite_params,
    }

    normalized_type: str = db_type.strip().lower()
    builder = builders.get(normalized_type)

    if not builder:
        raise ValueError(f"Tipo de base de datos no soportado para build_conn_params: {db_type}")

    return builder(kwargs, normalized_type)


def _validate_required(required: list[str], kwargs: dict[str, Any], db_type: str) -> None:
    """Valida presencia de parámetros requeridos."""
    missing: list[str] = [key for key in required if key not in kwargs or kwargs[key] in (None, "")]
    if missing:
        raise ValueError(f"Faltan parámetros requeridos para {db_type}: {', '.join(missing)}")


def _build_mariadb_params(kwargs: dict[str, Any], db_type: str) -> dict[str, Any]:
    """Construye parámetros para MariaDB y MySQL (mismos requeridos y valores por defecto)."""
    required: list[str] = ["host", "user", "password", "database"]
    _validate_required(required, kwargs, db_type)
    conn_params: dict[str, Any] = {
        "host": kwargs["host"],
        "user": kwargs["user"],
        "password": kwargs["password"],
        "database": kwargs["database"],
        "port": kwargs.get("port", _default(MariaDBConnectionConfig, "port")),
        "pool_size": kwargs.get("pool_size", _default(MariaDBPoolConfig, "pool_size")),
    }

    if "charset" in kwargs:
        conn_params["charset"] = kwargs["charset"]

    return conn_params


def _build_oracle_params(kwargs: dict[str, Any], db_type: str) -> dict[str, Any]:
    """Construye parámetros para Oracle."""
    required: list[str] = ["user", "password"]
    _validate_required(required, kwargs, db_type)

    has_dsn: bool = bool(kwargs.get("dsn"))
    has_service: bool = bool(kwargs.get("service_name"))
    has_sid: bool = bool(kwargs.get("sid"))
    # ``database`` es alias de service_name en OracleConnectionConfig y en las conexiones (makedsn).
    has_database: bool = bool(kwargs.get("database"))

    if not (has_dsn or has_service or has_sid or has_database):
        raise ValueError("Para oracle debe informar 'dsn' o 'service_name' o 'sid' o 'database'")

    conn_params: dict[str, Any] = {
        "user": kwargs["user"],
        "password": kwargs["password"],
        "pool_size": kwargs.get("pool_size", _default(OraclePoolConfig, "pool_size")),
        "max_lifetime": kwargs.get("max_lifetime", _default(OraclePoolConfig, "max_lifetime")),
    }

    if kwargs.get("oracle_client_path"):
        conn_params["oracle_client_path"] = kwargs["oracle_client_path"]

    if has_dsn:
        conn_params["dsn"] = kwargs["dsn"]
    else:
        conn_params["host"] = kwargs.get("host", _default(OracleConnectionConfig, "host"))
        conn_params["port"] = kwargs.get("port", _default(OracleConnectionConfig, "port"))
        if has_service:
            conn_params["service_name"] = kwargs["service_name"]
        if has_sid:
            conn_params["sid"] = kwargs["sid"]
        if has_database:
            conn_params["database"] = kwargs["database"]

    return conn_params


def _build_postgresql_params(kwargs: dict[str, Any], db_type: str) -> dict[str, Any]:
    """Construye parámetros para PostgreSQL."""
    required: list[str] = ["host", "user", "password", "database"]
    _validate_required(required, kwargs, db_type)
    return {
        "host": kwargs["host"],
        "user": kwargs["user"],
        "password": kwargs["password"],
        "database": kwargs["database"],
        "port": kwargs.get("port", _default(PostgreSQLConnectionConfig, "port")),
        "schema": kwargs.get("schema", _default(PostgreSQLConnectionConfig, "schema")),
        "pool_size": kwargs.get("pool_size", _default(PostgreSQLPoolConfig, "pool_size")),
        "pool_timeout": kwargs.get("pool_timeout", _default(PostgreSQLPoolConfig, "pool_timeout")),
    }


def _build_hsqldb_params(kwargs: dict[str, Any], db_type: str) -> dict[str, Any]:
    """Construye parámetros para HSQLDB."""
    required: list[str] = ["user", "jdbc_url", "jdbc_jar"]
    _validate_required(required, kwargs, db_type)
    return {
        "user": kwargs["user"],
        "password": kwargs.get("password", _default(HSQLDBConnectionConfig, "password")),
        "jdbc_url": kwargs["jdbc_url"],
        "jdbc_jar": kwargs["jdbc_jar"],
        "jdbc_driver": kwargs.get("jdbc_driver", _default(HSQLDBConnectionConfig, "jdbc_driver")),
        "schema": kwargs.get("schema", _default(HSQLDBConnectionConfig, "schema")),
    }


def _build_sqlserver_params(kwargs: dict[str, Any], db_type: str) -> dict[str, Any]:
    """Construye parámetros para SQL Server."""
    required: list[str] = ["host", "user", "password", "database"]
    _validate_required(required, kwargs, db_type)
    return {
        "host": kwargs["host"],
        "user": kwargs["user"],
        "password": kwargs["password"],
        "database": kwargs["database"],
        "port": kwargs.get("port", _default(SQLServerConnectionConfig, "port")),
        "schema": kwargs.get("schema", _default(SQLServerConnectionConfig, "schema")),
        "sql_server_driver": kwargs.get("sql_server_driver", _default(SQLServerConnectionConfig, "sql_server_driver")),
        "driver_name": kwargs.get("driver_name", _default(SQLServerConnectionConfig, "driver_name")),
        "pool_size": kwargs.get("pool_size", _default(SQLServerPoolConfig, "pool_size")),
        "max_overflow": kwargs.get("max_overflow", _default(SQLServerPoolConfig, "max_overflow")),
        "pool_timeout": kwargs.get("pool_timeout", _default(SQLServerPoolConfig, "pool_timeout")),
    }


def _build_sqlite_params(kwargs: dict[str, Any], db_type: str) -> dict[str, Any]:
    """Construye parámetros para SQLite."""
    required: list[str] = ["database"]
    _validate_required(required, kwargs, db_type)
    return {
        "database": kwargs["database"],
        "timeout": kwargs.get("timeout", _default(SQLiteConnectionConfig, "timeout")),
        "check_same_thread": kwargs.get("check_same_thread", _default(SQLiteConnectionConfig, "check_same_thread")),
        "isolation_level": kwargs.get("isolation_level", _default(SQLiteConnectionConfig, "isolation_level")),
        "cached_statements": kwargs.get("cached_statements", _default(SQLiteConnectionConfig, "cached_statements")),
        "pool_size": kwargs.get("pool_size", _default(SQLitePoolConfig, "pool_size")),
    }
