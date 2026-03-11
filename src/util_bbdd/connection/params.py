"""Gestión centralizada de validación y saneamiento de conn_params."""

from __future__ import annotations

import logging

from typing import Any

from ..connection.builder import build_conn_params
from ..connection.config import (
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
from ..database_type_validator import DatabaseTypeValidator, get_database_validator


class ConnectionParamsManager:
    """Centraliza validación, construcción y filtrado de `conn_params` por motor."""

    logger: logging.Logger = logging.getLogger(__name__)

    _BUILD_SUPPORTED_TYPES: set[str] = {
        "mariadb",
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
    ) -> dict[str, Any]:
        """Construye y valida los `conn_params` de entrada para un motor."""
        normalized_type: str = db_type.lower().strip()
        input_params: dict[str, Any] = ConnectionParamsManager._normalize_input_aliases(
            normalized_type,
            conn_params,
        )

        if normalized_type in ConnectionParamsManager._BUILD_SUPPORTED_TYPES:
            built_params: dict[str, Any] = build_conn_params(normalized_type, **input_params)
            # Preservar parámetros opcionales válidos aportados por el usuario.
            input_params = {**built_params, **input_params}

        validator: DatabaseTypeValidator = db_validator or get_database_validator()
        validator.validate_connection_params(normalized_type, input_params)
        ConnectionParamsManager.get_connection_config(normalized_type, input_params)
        if normalized_type in {"mariadb", "oracle", "postgresql", "sqlserver", "sqlite"}:
            ConnectionParamsManager.get_pool_config(normalized_type, input_params)
        return input_params

    @staticmethod
    def sanitize_for_connection(
        db_type: str,
        conn_params: dict[str, Any],
        driver: str | None = None,
    ) -> dict[str, Any]:
        """Filtra parámetros aptos para crear conexión raw por motor."""
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
        return sanitized

    @staticmethod
    def sanitize_for_pool(
        db_type: str,
        conn_params: dict[str, Any],
    ) -> dict[str, Any]:
        """Filtra parámetros aptos para inicialización de pool por motor."""
        normalized_type: str = db_type.lower().strip()
        config = ConnectionParamsManager.get_pool_config(normalized_type, conn_params)
        sanitized = config.to_driver_kwargs()
        ConnectionParamsManager._log_ignored(
            db_type=normalized_type,
            original=conn_params,
            sanitized=sanitized,
            context="pool",
        )
        return sanitized

    @staticmethod
    def get_connection_config(
        db_type: str,
        conn_params: dict[str, Any],
        driver: str | None = None,
    ) -> Any:
        normalized_type: str = db_type.lower().strip()
        if normalized_type == "mariadb":
            return MariaDBConnectionConfig.from_params(conn_params)
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
        raise ValueError(f"Tipo de base de datos no soportado para configuración de conexión: {db_type}")

    @staticmethod
    def get_pool_config(
        db_type: str,
        conn_params: dict[str, Any],
    ) -> Any:
        normalized_type: str = db_type.lower().strip()
        if normalized_type == "mariadb":
            return MariaDBPoolConfig.from_params(conn_params)
        if normalized_type == "oracle":
            return OraclePoolConfig.from_params(conn_params)
        if normalized_type == "postgresql":
            return PostgreSQLPoolConfig.from_params(conn_params)
        if normalized_type == "sqlserver":
            return SQLServerPoolConfig.from_params(conn_params)
        if normalized_type == "sqlite":
            return SQLitePoolConfig.from_params(conn_params)
        raise ValueError(f"Tipo de base de datos no soportado para configuración de pool: {db_type}")

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
