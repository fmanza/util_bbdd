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

        Ejecuta `SHOW VARIABLES WHERE Variable_name = 'variable_name'` (coincidencia exacta) para cada variable crítica.
        Una variable que no existe, que no se puede leer o con una fila o un valor inesperados se omite (WARNING o
        DEBUG); el resto se lee igual. Retorna dict vacío si no se pudo leer ninguna (ej. permisos insuficientes).

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
            # R-1b (2.2.1): coincidencia exacta; con LIKE el ``_`` del nombre es un comodín y rows[0] podía ser otra
            # variable. El nombre es una constante de la clase, no entrada del usuario.
            stmt = text(f"SHOW VARIABLES WHERE Variable_name = '{var_name}'")
            try:
                rows: list[tuple[str, str]] = self._connection.execute(stmt).fetchall()
            except SQLAlchemyError as exc:
                logger.warning(f"Error leyendo variable '{var_name}': {exc}")
                continue
            if not rows:
                logger.debug(f"Variable '{var_name}' no encontrada en SHOW VARIABLES")
                continue
            try:
                _name, value_str = rows[0]
            except (ValueError, TypeError, IndexError):
                # R-1 (2.2.1): una fila con otra forma lanzaba fuera y se perdían todas las variables.
                logger.warning(f"Fila inesperada para la variable '{var_name}' en SHOW VARIABLES; se omite")
                continue
            try:
                result[var_name] = int(value_str)
            except (ValueError, TypeError):
                logger.warning(f"No se pudo parsear variable '{var_name}' como int: {value_str}")

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
