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
class IndexActionResult:
    """Resultado de gestionar (deshabilitar/reconstruir) un índice individual en el destino.

    Lo devuelven ``dump.IndexManager`` (``DumpResult.index_results``), :meth:`BulkCrud.maintenance_scope`
    (``MaintenanceScopeResult.index_results``) y ``ParallelBulkLoader.load`` (``ParallelLoadResult.index_results``).
    Desde 3.2.0 vive en ``bulk``; ``util_bbdd.dump.IndexActionResult`` es la misma clase.

    Attributes:
        table_name: Tabla a la que pertenece el índice (``"*"`` para resultados globales).
        index_name: Nombre del índice (``"*"``: toda la tabla, p. ej. ``DISABLE KEYS`` de MyISAM/Aria).
        dialect: Dialecto del motor destino.
        action: Resultado de la operación:

            - ``"rebuilt"`` — índice deshabilitado/unusable y reconstruido (mssql/oracle; MyISAM/Aria ``ENABLE KEYS``).
            - ``"recreated"`` — índice eliminado y recreado desde su DDL (postgresql; mariadb/mysql InnoDB).
            - ``"failed"`` — fallo al reconstruir/recrear; ver ``error_msg``.
            - ``"unsupported"`` — motor no soportado (hasta 3.1.x, mariadb/mysql InnoDB en ``dump``).
            - ``"skipped"`` — no se desactivó y se mantuvo durante la carga (desde 4.0.0: índice único de Oracle sin
              constraint cuyo DDL no se pudo obtener; el motivo, en ``error_msg``).
        error_msg: Detalle del error cuando ``action="failed"``, ``"unsupported"`` o ``"skipped"``.
    """

    table_name: str
    index_name: str
    dialect: str
    action: Literal["rebuilt", "recreated", "failed", "unsupported", "skipped"]
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

        with bulk.maintenance_scope("orders", disable_indexes=True) as ms:
            bulk.bulk_insert_from_df(df, "orders")
        for r in ms.constraint_results:
            print(r.constraint_name, r.status)
        for r in ms.index_results:
            print(r.index_name, r.action)

    ``index_results`` (desde 3.2.0): un :class:`IndexActionResult` por índice desactivado con ``disable_indexes``,
    disponible tras salir del bloque sin error.
    """

    optimization_applied: bool = False
    constraint_results: list[MaintenanceScopeConstraintResult] = field(default_factory=list)
    index_results: list[IndexActionResult] = field(default_factory=list)


__all__: list[str] = ["IndexActionResult", "MaintenanceScopeConstraintResult", "MaintenanceScopeResult", "PKSyncResult"]
