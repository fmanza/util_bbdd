"""Gestión centralizada de validación y saneamiento de conn_params."""

from __future__ import annotations

import dataclasses
import logging

from typing import Any, Literal, cast

from .._core.exceptions import InvalidDatabaseType
from .._drivers import DatabaseTypeValidator, get_database_validator
from ..connection.builder import build_conn_params
from ..connection.config import (
    HSQLDBConnectionConfig,
    MariaDBConnectionConfig,
    MariaDBPoolConfig,
    MySQLConnectionConfig,
    MySQLPoolConfig,
    OracleConnectionConfig,
    OraclePoolConfig,
    PostgreSQLConnectionConfig,
    PostgreSQLPoolConfig,
    SQLiteConnectionConfig,
    SQLitePoolConfig,
    SQLServerConnectionConfig,
    SQLServerPoolConfig,
)

#: Configs de conexión y de pool por motor: fuente única de las claves aceptadas en ``conn_params`` y de sus defaults.
_CONFIG_CLASSES: dict[str, tuple[type, type | None]] = {
    "mariadb": (MariaDBConnectionConfig, MariaDBPoolConfig),
    "mysql": (MySQLConnectionConfig, MySQLPoolConfig),
    "oracle": (OracleConnectionConfig, OraclePoolConfig),
    "postgresql": (PostgreSQLConnectionConfig, PostgreSQLPoolConfig),
    "hsqldb": (HSQLDBConnectionConfig, None),
    "sqlserver": (SQLServerConnectionConfig, SQLServerPoolConfig),
    "sqlite": (SQLiteConnectionConfig, SQLitePoolConfig),
}

#: Clase de un parámetro de conexión (``connection_params.kinds`` de ``database_types.json``; v4.6.0, G12).
ParamKind = Literal["secret", "host", "port", "path", "blocked", "plain"]

#: Claves aceptadas que no son campo de ninguna config: ``close_timeout`` lo usa el manager aunque no haya pool;
#: ``encoding`` (Oracle) se acepta y se ignora (python-oracledb trabaja siempre en UTF-8).
_EXTRA_KEYS: dict[str, frozenset[str]] = {
    "*": frozenset({"close_timeout"}),
    "oracle": frozenset({"encoding"}),
}


class ConnectionParamsManager:
    """Centraliza validación, construcción y filtrado de `conn_params` por motor."""

    logger: logging.Logger = logging.getLogger(__name__)

    @staticmethod
    def allowed_keys(db_type: str) -> frozenset[str]:
        """Claves aceptadas en ``conn_params`` para ``db_type``: campos de su config de conexión y de pool + extras.

        Args:
            db_type: Tipo de motor.

        Raises:
            InvalidDatabaseType: Si el motor no tiene configuración.
        """
        normalized_type: str = db_type.lower().strip()
        if normalized_type not in _CONFIG_CLASSES:
            raise InvalidDatabaseType(
                message=f"Tipo de base de datos no soportado para configuración de conexión: {db_type}",
                db_type=db_type,
            )
        keys: set[str] = set(_EXTRA_KEYS["*"]) | set(_EXTRA_KEYS.get(normalized_type, frozenset()))
        for config_cls in _CONFIG_CLASSES[normalized_type]:
            if config_cls is not None:
                keys.update(f.name for f in dataclasses.fields(config_cls) if f.name != "connection")
        return frozenset(keys)

    @staticmethod
    def param_kinds(db_type: str) -> dict[str, ParamKind]:
        """Clase de cada parámetro de conexión de ``db_type`` (v4.6.0, G12 de util_bbdd_web).

        Sale de ``connection_params.kinds`` de ``database_types.json``, que cubre todos los parámetros declarados
        (los mismos que :meth:`allowed_keys`). Clases (:data:`ParamKind`):

        - ``secret``: credencial (``password``). No debe mostrarse ni guardarse en claro.
        - ``host``: destino de red (``host``; ``dsn`` en Oracle, ``jdbc_url`` en HSQLDB).
        - ``port``: puerto de red.
        - ``path``: ruta del sistema de ficheros (certificados, socket, Instant Client, JAR; ``database`` en SQLite).
        - ``blocked``: ejecuta SQL arbitrario al conectar (``init_command``); una aplicación que deja a sus usuarios
          configurar conexiones no debería aceptarlo.
        - ``plain``: el resto.

        Args:
            db_type: Tipo de motor.

        Raises:
            InvalidDatabaseType: Si el motor no está soportado.

        Example:
            >>> ConnectionParamsManager.param_kinds("postgresql")["password"]
            'secret'
        """
        params = get_database_validator().get_db_type_connection_params(db_type)
        kinds: Any = params.get("kinds", {})
        return {str(name): cast(ParamKind, kind) for name, kind in kinds.items()} if isinstance(kinds, dict) else {}

    @staticmethod
    def param_kind(db_type: str, name: str) -> ParamKind:
        """Clase de un parámetro (:meth:`param_kinds`).

        Raises:
            InvalidDatabaseType: Si el motor no está soportado.
            ValueError: Si ``name`` no es un parámetro de conexión de ``db_type``.
        """
        kinds = ConnectionParamsManager.param_kinds(db_type)
        if name not in kinds:
            raise ValueError(f"'{name}' no es un parámetro de conexión de {db_type}")
        return kinds[name]

    @staticmethod
    def _validate_keys(db_type: str, conn_params: dict[str, Any]) -> None:
        """Rechaza claves que ninguna config del motor admite (mismo mensaje que la lista blanca del JSON)."""
        valid_params: frozenset[str] = ConnectionParamsManager.allowed_keys(db_type)
        extra_params: list[str] = [p for p in conn_params if p not in valid_params]
        if extra_params:
            raise ValueError(
                f"Parámetros no válidos para {db_type}: {', '.join(extra_params)}. "
                f"Parámetros válidos: {', '.join(sorted(valid_params))}"
            )

    _BUILD_SUPPORTED_TYPES: set[str] = {
        "mariadb",
        "mysql",
        "oracle",
        "postgresql",
        "hsqldb",
        "sqlserver",
        "sqlite",
    }

    @staticmethod
    def _normalize_input_aliases(
        db_type: str,
        conn_params: dict[str, Any],
    ) -> dict[str, Any]:
        """Normaliza alias de parámetros de entrada por motor."""
        normalized: dict[str, Any] = dict(conn_params)

        if db_type == "sqlite" and "filepath" in normalized:
            filepath_value: Any = normalized.pop("filepath")
            if filepath_value is not None and str(filepath_value).strip():
                normalized["database"] = str(filepath_value).strip()

        return normalized

    @staticmethod
    def prepare_and_validate(
        db_type: str,
        conn_params: dict[str, Any],
        db_validator: DatabaseTypeValidator | None = None,
        *,
        inject_defaults: bool = True,
    ) -> dict[str, Any]:
        """Construye y valida los `conn_params` de entrada para un motor.

        Args:
            db_type: Motor.
            conn_params: Parámetros de entrada (se admiten alias, p. ej. ``filepath`` en SQLite).
            db_validator: Validador de tipos de BD (por defecto, el singleton).
            inject_defaults: Si es ``True`` (manager sync), el resultado incluye los defaults de ``build_conn_params``.
                El manager async usa ``False``: valida igual, pero sus ``conn_params`` no reciben defaults pensados
                para el camino sync (p. ej. ``sql_server_driver="pymssql"``); las configs los aplican al conectar.

        Raises:
            ValueError: Si faltan requeridos, hay claves no admitidas o valores inválidos.
            InvalidDatabaseType: Si el motor no está soportado.
        """
        normalized_type: str = db_type.lower().strip()
        input_params: dict[str, Any] = ConnectionParamsManager._normalize_input_aliases(
            normalized_type,
            conn_params,
        )

        if normalized_type in ConnectionParamsManager._BUILD_SUPPORTED_TYPES:
            built_params: dict[str, Any] = build_conn_params(normalized_type, **input_params)
            if inject_defaults:
                # Preservar parámetros opcionales válidos aportados por el usuario.
                input_params = {**built_params, **input_params}

        validator: DatabaseTypeValidator = db_validator or get_database_validator()
        validator.validate_db_type(normalized_type)
        ConnectionParamsManager._validate_keys(normalized_type, input_params)
        ConnectionParamsManager.get_connection_config(normalized_type, input_params)
        if normalized_type in {"mariadb", "mysql", "oracle", "postgresql", "sqlserver", "sqlite"}:
            ConnectionParamsManager.get_pool_config(normalized_type, input_params)
        return input_params

    @staticmethod
    def sanitize_for_connection(
        db_type: str,
        conn_params: dict[str, Any],
        driver: str | None = None,
    ) -> dict[str, Any]:
        """Filtra parámetros aptos para crear conexión raw por motor.

        Args:
            db_type: Tipo de motor.
            conn_params: Parámetros del usuario; los que el driver no usa se descartan (con log en DEBUG).
            driver: Driver de SQL Server (``pymssql`` o ``pyodbc``); en el resto de motores no se usa.

        Returns:
            Argumentos para el ``connect`` del driver.

        Raises:
            InvalidDatabaseType: Si ``db_type`` no está soportado.
            ValueError: Si ``conn_params`` no es válido para el motor.
        """
        normalized_type: str = db_type.lower().strip()
        config = ConnectionParamsManager.get_connection_config(normalized_type, conn_params, driver=driver)
        if normalized_type == "sqlserver":
            sanitized = config.to_driver_kwargs(driver=driver)
        else:
            sanitized = config.to_driver_kwargs()

        ConnectionParamsManager._log_ignored(
            db_type=normalized_type,
            original=conn_params,
            sanitized=sanitized,
            context="connection",
        )
        return cast(dict[str, Any], sanitized)

    @staticmethod
    def sanitize_for_pool(
        db_type: str,
        conn_params: dict[str, Any],
    ) -> dict[str, Any]:
        """Filtra parámetros aptos para inicialización de pool por motor.

        Args:
            db_type: Tipo de motor.
            conn_params: Parámetros del usuario; los que el pool no usa se descartan (con log en DEBUG).

        Returns:
            Argumentos para crear el pool del driver.

        Raises:
            InvalidDatabaseType: Si ``db_type`` no tiene configuración de pool.
            ValueError: Si ``conn_params`` no es válido para el motor.
        """
        normalized_type: str = db_type.lower().strip()
        config = ConnectionParamsManager.get_pool_config(normalized_type, conn_params)
        sanitized = config.to_driver_kwargs()
        ConnectionParamsManager._log_ignored(
            db_type=normalized_type,
            original=conn_params,
            sanitized=sanitized,
            context="pool",
        )
        return cast(dict[str, Any], sanitized)

    @staticmethod
    def get_connection_config(
        db_type: str,
        conn_params: dict[str, Any],
        driver: str | None = None,
    ) -> Any:
        """Configuración de conexión tipada de ``db_type`` (``<Motor>ConnectionConfig.from_params``).

        Args:
            db_type: Tipo de motor.
            conn_params: Parámetros de conexión del usuario.
            driver: Driver de SQL Server (``pymssql`` o ``pyodbc``); en el resto de motores no se usa.

        Raises:
            InvalidDatabaseType: Si ``db_type`` no está soportado.
            ValueError: Si ``conn_params`` no es válido para el motor.
        """
        normalized_type: str = db_type.lower().strip()
        if normalized_type == "mariadb":
            return MariaDBConnectionConfig.from_params(conn_params)
        if normalized_type == "mysql":
            return MySQLConnectionConfig.from_params(conn_params)
        if normalized_type == "oracle":
            return OracleConnectionConfig.from_params(conn_params)
        if normalized_type == "postgresql":
            return PostgreSQLConnectionConfig.from_params(conn_params)
        if normalized_type == "hsqldb":
            return HSQLDBConnectionConfig.from_params(conn_params)
        if normalized_type == "sqlserver":
            return SQLServerConnectionConfig.from_params(conn_params, driver=driver)
        if normalized_type == "sqlite":
            return SQLiteConnectionConfig.from_params(conn_params)
        raise InvalidDatabaseType(
            message=f"Tipo de base de datos no soportado para configuración de conexión: {db_type}",
            db_type=db_type,
        )

    @staticmethod
    def get_pool_config(
        db_type: str,
        conn_params: dict[str, Any],
    ) -> Any:
        """Configuración de pool tipada de ``db_type`` (``<Motor>PoolConfig.from_params``).

        Args:
            db_type: Tipo de motor.
            conn_params: Parámetros de conexión y de pool del usuario.

        Raises:
            InvalidDatabaseType: Si ``db_type`` no tiene configuración de pool.
            ValueError: Si ``conn_params`` no es válido para el motor.
        """
        normalized_type: str = db_type.lower().strip()
        if normalized_type == "mariadb":
            return MariaDBPoolConfig.from_params(conn_params)
        if normalized_type == "mysql":
            return MySQLPoolConfig.from_params(conn_params)
        if normalized_type == "oracle":
            return OraclePoolConfig.from_params(conn_params)
        if normalized_type == "postgresql":
            return PostgreSQLPoolConfig.from_params(conn_params)
        if normalized_type == "sqlserver":
            return SQLServerPoolConfig.from_params(conn_params)
        if normalized_type == "sqlite":
            return SQLitePoolConfig.from_params(conn_params)
        raise InvalidDatabaseType(
            message=f"Tipo de base de datos no soportado para configuración de pool: {db_type}",
            db_type=db_type,
        )

    @staticmethod
    def _log_ignored(
        db_type: str,
        original: dict[str, Any],
        sanitized: dict[str, Any],
        context: str,
    ) -> None:
        ignored_keys: list[str] = [key for key in original.keys() if key not in sanitized]
        if ignored_keys:
            ConnectionParamsManager.logger.debug(
                f"⚠️  Parámetros ignorados para {db_type} ({context}): {sorted(ignored_keys)}"
            )
