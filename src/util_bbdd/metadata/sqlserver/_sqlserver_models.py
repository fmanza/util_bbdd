"""Modelos de datos internos para SQL Server.

Dataclasses para representar resultados de queries en SQL Server.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SqlServerRoutineDetail:
    """Representa un procedimiento almacenado o función en SQL Server.

    Atributos:
        routine_name: Nombre del procedimiento/función
        routine_type: Tipo ('PROCEDURE' o 'FUNCTION')
        object_id: ID único del objeto en SQL Server
        parameters_count: Cantidad de parámetros (excluyendo return value)
    """

    routine_name: str
    routine_type: str
    object_id: int
    parameters_count: int


@dataclass(frozen=True)
class SqlServerParameterDetail:
    """Representa un parámetro de procedimiento/función en SQL Server.

    Atributos:
        param_name: Nombre del parámetro
        object_id: ID del procedimiento/función propietario
        parameter_id: ID del parámetro (>0 para parámetros, 0 para return value)
        data_type: Nombre del tipo de dato
        is_output: True si es parámetro OUTPUT
        precision: Precisión para tipos numéricos
        scale: Escala para tipos numéricos
    """

    param_name: str
    object_id: int
    parameter_id: int
    data_type: str
    is_output: bool
    precision: int | None
    scale: int | None
