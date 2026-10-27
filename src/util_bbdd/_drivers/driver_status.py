"""Qué drivers de un motor están instalados (v4.6.0, G10 de util_bbdd_web)."""

from __future__ import annotations

import importlib.util

from dataclasses import dataclass

from .validator import get_db_type_info


@dataclass(frozen=True, slots=True)
class DriverStatus:
    """Driver declarado para un motor en ``database_types.json`` y si su módulo está instalado.

    Attributes:
        name: Nombre del módulo del driver (``"oracledb"``, ``"pyodbc"``…), el de la lista ``drivers`` del motor.
        installed: ``True`` si el módulo se encuentra en el entorno (``importlib.util.find_spec``, sin importarlo).
    """

    name: str
    installed: bool


def _installed(module: str) -> bool:
    """``True`` si ``module`` se puede importar; no lo importa (un driver con extensiones nativas no se carga)."""
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def get_driver_status(db_type: str) -> tuple[DriverStatus, ...]:
    """Estado de instalación de cada driver de ``db_type``, en el orden de ``database_types.json``.

    No comprueba requisitos del sistema (Instant Client, ODBC, FreeTDS, Java): solo que el paquete de Python esté.

    Args:
        db_type: Tipo de motor de la librería (``"postgresql"``, ``"sqlserver"``…).

    Raises:
        InvalidDatabaseType: Si ``db_type`` no es un motor soportado.

    Example:
        >>> get_driver_status("sqlite")
        (DriverStatus(name='sqlite3', installed=True),)
    """
    drivers = get_db_type_info(db_type).get("drivers", [])
    return tuple(DriverStatus(name=str(name), installed=_installed(str(name))) for name in drivers)


__all__: list[str] = ["DriverStatus", "get_driver_status"]
