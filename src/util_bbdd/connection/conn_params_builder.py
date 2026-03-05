"""Helpers para construir conn_params de DatabaseManager por motor."""

from typing import Any, Callable


def build_conn_params(db_type: str, **kwargs: Any) -> dict[str, Any]:
    """Construye parámetros de conexión normalizados por tipo de base de datos.

    Args:
        db_type: Tipo de base de datos.
        **kwargs: Parámetros de conexión y opciones específicas del motor.

    Returns:
        Diccionario conn_params listo para DatabaseManager.

    Raises:
        ValueError: Si el tipo de base no es soportado o faltan parámetros requeridos.
    """
    builders: dict[str, Callable[[dict[str, Any], str], dict[str, Any]]] = {
        "mariadb": _build_mariadb_params,
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
    """Construye parámetros para MariaDB."""
    required: list[str] = ["host", "user", "password", "database"]
    _validate_required(required, kwargs, db_type)
    conn_params: dict[str, Any] = {
        "host": kwargs["host"],
        "user": kwargs["user"],
        "password": kwargs["password"],
        "database": kwargs["database"],
        "port": kwargs.get("port", 3306),
        "pool_size": kwargs.get("pool_size", 5),
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

    if not (has_dsn or has_service or has_sid):
        raise ValueError("Para oracle debe informar 'dsn' o 'service_name' o 'sid'")

    conn_params: dict[str, Any] = {
        "user": kwargs["user"],
        "password": kwargs["password"],
        "pool_size": kwargs.get("pool_size", 5),
        "max_lifetime": kwargs.get("max_lifetime", 3600),
    }

    if kwargs.get("oracle_client_path"):
        conn_params["oracle_client_path"] = kwargs["oracle_client_path"]

    if has_dsn:
        conn_params["dsn"] = kwargs["dsn"]
    else:
        conn_params["host"] = kwargs.get("host", "localhost")
        conn_params["port"] = kwargs.get("port", 1521)
        if has_service:
            conn_params["service_name"] = kwargs["service_name"]
        if has_sid:
            conn_params["sid"] = kwargs["sid"]

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
        "port": kwargs.get("port", 5432),
        "schema": kwargs.get("schema", "public"),
        "pool_size": kwargs.get("pool_size", 5),
        "pool_timeout": kwargs.get("pool_timeout", 30),
    }


def _build_hsqldb_params(kwargs: dict[str, Any], db_type: str) -> dict[str, Any]:
    """Construye parámetros para HSQLDB."""
    required: list[str] = ["user", "jdbc_url", "jdbc_jar"]
    _validate_required(required, kwargs, db_type)
    return {
        "user": kwargs["user"],
        "password": kwargs.get("password", ""),
        "jdbc_url": kwargs["jdbc_url"],
        "jdbc_jar": kwargs["jdbc_jar"],
        "jdbc_driver": kwargs.get("jdbc_driver", "org.hsqldb.jdbcDriver"),
        "schema": kwargs.get("schema", "PUBLIC"),
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
        "port": kwargs.get("port", 1433),
        "schema": kwargs.get("schema", "dbo"),
        "sql_server_driver": kwargs.get("sql_server_driver", "pymssql"),
        "driver_name": kwargs.get("driver_name", "ODBC Driver 17 for SQL Server"),
        "pool_size": kwargs.get("pool_size", 5),
        "max_overflow": kwargs.get("max_overflow", 10),
        "pool_timeout": kwargs.get("pool_timeout", 30),
    }


def _build_sqlite_params(kwargs: dict[str, Any], db_type: str) -> dict[str, Any]:
    """Construye parámetros para SQLite."""
    required: list[str] = ["database"]
    _validate_required(required, kwargs, db_type)
    return {
        "database": kwargs["database"],
        "timeout": kwargs.get("timeout", 5),
        "check_same_thread": kwargs.get("check_same_thread", False),
        "isolation_level": kwargs.get("isolation_level", ""),
        "cached_statements": kwargs.get("cached_statements", 100),
        "pool_size": kwargs.get("pool_size", 1),
    }
