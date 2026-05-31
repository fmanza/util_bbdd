"""Tipos de datos internos del módulo bulk."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class PKSyncResult:
    """Resultado de sincronizar el contador PK de una columna tras carga masiva.

    Attributes:
        table_name: Nombre de la tabla.
        column_name: Nombre de la columna PK sincronizada.
        engine_dialect: Dialecto del motor (``"postgresql"``, ``"mssql"``, etc.).
        max_value: Valor ``MAX(pk)`` leído de la tabla antes del sync;
            ``None`` si la tabla estaba vacía.
        status: Resultado de la operación:

            - ``"synced"`` — contador actualizado correctamente.
            - ``"skipped"`` — columna sin sequence vinculada (PK natural / UUID).
            - ``"no_rows"`` — tabla vacía; contador reiniciado al valor semilla.
            - ``"unsupported"`` — motor o patrón no soportado (Oracle pre-12c).
            - ``"error"`` — fallo durante la sincronización; ver ``error_msg``.
        error_msg: Detalle del error cuando ``status="error"`` o ``"unsupported"``.
    """

    table_name: str
    column_name: str
    engine_dialect: str
    max_value: int | None
    status: Literal["synced", "skipped", "no_rows", "unsupported", "error"]
    error_msg: str = ""


__all__: list[str] = ["PKSyncResult"]
