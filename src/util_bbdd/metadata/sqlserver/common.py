"""Helpers puros compartidos para metadata SQL Server.

Proporciona mapeos de tipos T-SQL a tipos genéricos, escaping de identificadores,
y funciones de normalización.
"""

from __future__ import annotations


def fetch_compatibility_level_sql() -> str:
    """SQL que devuelve el nivel de compatibilidad de la base de datos actual.

    Lo usa el DELETE masivo de ``bulk`` en SQL Server: ``OPENJSON`` exige nivel ≥ 130 (SQL Server 2016).

    Returns:
        str: SQL con una fila y un entero.
    """
    return "SELECT compatibility_level FROM sys.databases WHERE name = DB_NAME()"
