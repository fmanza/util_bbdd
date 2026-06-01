"""Configuraciones recomendadas de MySQL/MariaDB para bulk operations.

Proporciona perfiles predefinidos según workload y tamaño de dataset.
"""

from __future__ import annotations

import logging

from dataclasses import dataclass

logger: logging.Logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MySQLOptimalConfig:
    """Configuración recomendada de MySQL/MariaDB para bulk operations.

    Almacena valores óptimos de:
    - `innodb_buffer_pool_size`: Memoria que InnoDB cachea para tablas/índices
    - `max_allowed_packet`: Tamaño máximo de paquete SQL (SHOW VARIABLES, INSERT multi-fila)

    Valores en bytes. Usar `format_bytes()` para lectura.

    Examples:
        >>> config = MySQLOptimalConfig.dev()
        >>> print(config.innodb_buffer_pool_size)
        268435456  # 256 MB

        >>> config = MySQLOptimalConfig.suggest(num_rows=1_000_000)
        >>> print(config.format_bytes(config.max_allowed_packet))
        "64 MB"
    """

    innodb_buffer_pool_size: int  # bytes
    max_allowed_packet: int  # bytes

    @staticmethod
    def dev() -> MySQLOptimalConfig:
        """Configuración para desarrollo (local, dataset pequeño).

        - Buffer pool: 256 MB (default en MySQL; suficiente para tablas <1GB)
        - max_allowed_packet: 16 MB (default; suficiente para <50K filas por INSERT)
        """
        return MySQLOptimalConfig(
            innodb_buffer_pool_size=256 * 1_048_576,  # 256 MB
            max_allowed_packet=16 * 1_048_576,  # 16 MB
        )

    @staticmethod
    def production() -> MySQLOptimalConfig:
        """Configuración para producción estándar (dataset de cientos de miles).

        - Buffer pool: 1 GB (25–50% de RAM típica; mitiga degradación undo log)
        - max_allowed_packet: 64 MB (permite INSERT multi-fila de ~1000 filas por stmt)
        """
        return MySQLOptimalConfig(
            innodb_buffer_pool_size=1 * 1_073_741_824,  # 1 GB
            max_allowed_packet=64 * 1_048_576,  # 64 MB
        )

    @staticmethod
    def high_volume() -> MySQLOptimalConfig:
        """Configuración para alto volumen (millones de filas, 4+ GB RAM).

        - Buffer pool: 4 GB (50–75% de RAM; máximo retorno en ~256GB de datos)
        - max_allowed_packet: 128 MB (permite INSERT multi-fila de ~5000 filas por stmt)
        """
        return MySQLOptimalConfig(
            innodb_buffer_pool_size=4 * 1_073_741_824,  # 4 GB
            max_allowed_packet=128 * 1_048_576,  # 128 MB
        )

    @staticmethod
    def suggest(num_rows: int, avg_row_bytes: int = 2000) -> MySQLOptimalConfig:
        """Sugiere configuración óptima basada en tamaño de dataset.

        Heurística:
        - num_rows ≤ 100K → dev()
        - 100K < num_rows ≤ 1M → production()
        - num_rows > 1M → high_volume()

        Args:
            num_rows: Cantidad aproximada de filas a insertar.
            avg_row_bytes: Bytes promedio por fila (para cálculos; no afecta resultado final).

        Returns:
            Configuración recomendada.

        Examples:
            >>> config = MySQLOptimalConfig.suggest(50_000)
            >>> # → dev()
            >>> config = MySQLOptimalConfig.suggest(500_000)
            >>> # → production()
        """
        if num_rows <= 100_000:
            return MySQLOptimalConfig.dev()
        elif num_rows <= 1_000_000:
            return MySQLOptimalConfig.production()
        else:
            return MySQLOptimalConfig.high_volume()

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

    def __str__(self) -> str:
        """Representación legible de la configuración."""
        return (
            f"MySQLOptimalConfig(buffer_pool={self.format_bytes(self.innodb_buffer_pool_size)}, "
            f"max_packet={self.format_bytes(self.max_allowed_packet)})"
        )
