"""Tipos de datos internos del módulo bulk."""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class MaintenanceScopeConstraintResult:
    """Resultado de rehabilitar una constraint individual durante :meth:`BulkCrud.maintenance_scope`."""

    constraint_name: str
    status: Literal["enabled", "failed", "unverified"]
    error_msg: str = ""


@dataclass
class MaintenanceScopeResult:
    """Resultado acumulado del context manager :meth:`BulkCrud.maintenance_scope`.

    Se obtiene mediante ``as`` en el bloque ``with``::

        with bulk.maintenance_scope("orders") as ms:
            bulk.bulk_insert_from_df(df, "orders")
        for r in ms.constraint_results:
            print(r.constraint_name, r.status)
    """

    optimization_applied: bool = False
    constraint_results: list[MaintenanceScopeConstraintResult] = field(default_factory=list)


__all__: list[str] = ["MaintenanceScopeConstraintResult", "MaintenanceScopeResult", "PKSyncResult"]
