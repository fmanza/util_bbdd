"""Validador read-only de variables MySQL/MariaDB para optimización de bulk operations.

Proporciona introspección de configuración de servidor sin modificación.
Permite detectar problemas de configuración antes de cargas masivas.
"""

from __future__ import annotations

import logging

from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger: logging.Logger = logging.getLogger(__name__)


class MySQLVariableValidator:
    """Validador de variables MySQL/MariaDB (read-only).

    Lee configuración del servidor para detectar problemas potenciales
    antes de ejecutar operaciones bulk de alto volumen.

    **Permisos requeridos**: INFORMACIÓN_SCHEMA (sin SUPER).
    """

    # Variables críticas para bulk operations
    _CRITICAL_VARIABLES: frozenset[str] = frozenset(
        {
            "max_allowed_packet",
            "innodb_buffer_pool_size",
            "innodb_flush_log_at_trx_commit",
            "innodb_log_file_size",
            "innodb_write_io_threads",
        }
    )

    def __init__(self, connection: Any) -> None:
        """Inicializa validador con conexión SQLAlchemy.

        Args:
            connection: Conexión SQLAlchemy a MySQL/MariaDB.

        Raises:
            ValueError: Si connection es None.
        """
        if connection is None:
            raise ValueError("connection no puede ser None")
        self._connection: Any = connection

    def read_variables(self) -> dict[str, int]:
        """Lee variables críticas del servidor MySQL/MariaDB.

        Ejecuta `SHOW VARIABLES LIKE 'variable_name'` para cada variable crítica.
        Retorna dict vacío si la lectura falla (ej. permisos insuficientes).

        Returns:
            dict con nombre→valor (en bytes). Ej:
            {'max_allowed_packet': 16777216, 'innodb_buffer_pool_size': 134217728}

        Examples:
            >>> validator = MySQLVariableValidator(connection)
            >>> vars = validator.read_variables()
            >>> print(vars['max_allowed_packet'])
            16777216
        """
        result: dict[str, int] = {}

        for var_name in self._CRITICAL_VARIABLES:
            try:
                query: str = f"SHOW VARIABLES LIKE '{var_name}'"
                stmt = text(query)
                rows: list[tuple[str, str]] = self._connection.execute(stmt).fetchall()

                if rows:
                    _name, value_str = rows[0]
                    try:
                        result[var_name] = int(value_str)
                    except (ValueError, TypeError):
                        logger.warning(f"No se pudo parsear variable '{var_name}' como int: {value_str}")
                else:
                    logger.debug(f"Variable '{var_name}' no encontrada en SHOW VARIABLES")

            except SQLAlchemyError as exc:
                logger.warning(f"Error leyendo variable '{var_name}': {exc}")

        return result

    def validate(self, required: dict[str, int]) -> dict[str, bool]:
        """Valida que valores actuales del servidor sean >= a los requeridos.

        Args:
            required: dict con variable_name → valor_mínimo_requerido (en bytes).

        Returns:
            dict con variable_name → bool (True = válido, False = necesita ajuste).

        Examples:
            >>> validator = MySQLVariableValidator(connection)
            >>> required = {'max_allowed_packet': 67108864}  # 64 MB
            >>> result = validator.validate(required)
            >>> print(result)
            {'max_allowed_packet': False}  # actual < requerido
        """
        current: dict[str, int] = self.read_variables()
        result: dict[str, bool] = {}

        for var_name, min_value in required.items():
            current_value: int | None = current.get(var_name)
            if current_value is None:
                result[var_name] = False
                logger.warning(f"Variable '{var_name}' no pudo ser leída; asumiendo inválido")
            else:
                is_valid: bool = current_value >= min_value
                result[var_name] = is_valid
                if not is_valid:
                    logger.warning(
                        f"Variable '{var_name}' por debajo de mínimo requerido: "
                        f"actual={current_value} bytes, requerido={min_value} bytes"
                    )

        return result

    def format_bytes(self, size_bytes: int) -> str:
        """Convierte bytes a formato legible (MB, GB, etc).

        Args:
            size_bytes: Tamaño en bytes.

        Returns:
            String legible. Ej: "64 MB", "1 GB".
        """
        for unit, divisor in [("GB", 1_073_741_824), ("MB", 1_048_576), ("KB", 1024)]:
            if size_bytes >= divisor:
                return f"{size_bytes / divisor:.1f} {unit}"
        return f"{size_bytes} bytes"

    def log_summary(self, required: dict[str, int] | None = None) -> None:
        """Emite log estructurado de variables y recomendaciones.

        Args:
            required: Si se proporciona, valida contra estos valores y emite warnings.

        Examples:
            >>> validator.log_summary({'max_allowed_packet': 67108864})
            # Log: "MySQL variables: max_allowed_packet=16 MB, innodb_buffer_pool_size=128 MB"
            # Log Warning: "max_allowed_packet por debajo de mínimo: actual=16 MB, requerido=64 MB"
        """
        current: dict[str, int] = self.read_variables()

        if not current:
            logger.warning("No se pudieron leer variables MySQL; asumiendo valores por defecto")
            return

        # Log información
        formatted: list[str] = []
        for var_name, value in current.items():
            formatted.append(f"{var_name}={self.format_bytes(value)}")
        logger.info(f"MySQL variables: {', '.join(formatted)}")

        # Validar si se proporciona required
        if required:
            is_valid: dict[str, bool] = self.validate(required)
            if not all(is_valid.values()):
                logger.warning(
                    "Una o más variables MySQL están por debajo de lo recomendado. "
                    "Considera ajustar con SET GLOBAL (requiere privilegio SUPER)."
                )
