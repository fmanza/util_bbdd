"""Gestión de índices secundarios del destino durante el volcado de datos.

Deshabilita los índices secundarios **no únicos** del destino antes de la carga masiva y los reconstruye al
finalizar, para acelerar los INSERT en tablas con muchos índices. Desde 3.2.0 es un adaptador de la estrategia común
de ``bulk`` (``bulk/_support/secondary_indexes.py``), la misma que ``BulkCrud.maintenance_scope(disable_indexes=...)``:

  - SQL Server (mssql): ``ALTER INDEX ... DISABLE`` → ``... REBUILD``. Solo índices NONCLUSTERED (deshabilitar el
    clustered dejaría la tabla inaccesible).
  - Oracle: ``ALTER INDEX ... UNUSABLE`` → ``... REBUILD``.
  - PostgreSQL: captura el DDL con ``pg_get_indexdef`` (se loguea antes de borrar), ``DROP INDEX`` y recrea con el DDL
    guardado.
  - MariaDB / MySQL (desde 3.2.0): InnoDB, ``DROP INDEX`` y un ``ALTER TABLE … ADD INDEX …`` por tabla, sin los
    índices que necesita una FK (el DDL se loguea antes); MyISAM/Aria, ``DISABLE KEYS`` → ``ENABLE KEYS``.

Con ``mode="secondary"`` (por defecto) solo se gestionan índices **no únicos**: los que respaldan PK / UNIQUE
constraints o son unique indexes quedan intactos, preservando la integridad durante la carga. Con ``mode="all"``
(3.3.0, ``DumpConfig.manage_indexes="all"``) también los únicos y PK/UNIQUE, con sus FK entrantes; un único que no se
reconstruye queda ``"failed"`` con sus claves duplicadas en ``error_msg``. Cada índice va en su propia transacción: un fallo no detiene
al resto.
"""

from __future__ import annotations

import logging

from typing import ClassVar

from sqlalchemy import Engine

from ..bulk._support.secondary_indexes import (
    SUPPORTED_DIALECTS,
    IndexDdlRunner,
    IndexMode,
    IndexStep,
    SecondaryIndexPlanner,
)
from ._models import IndexActionResult
from ._sql_utils import quote_table


class IndexManager:
    """Gestiona la desactivación/reconstrucción de índices secundarios en el destino.

    Usar como context manager garantiza que ``rebuild_all()`` se llama incluso si la
    carga lanza una excepción. Los resultados quedan en ``index_results`` tras salir
    del bloque ``with``.

    Ejemplo::

        mgr = IndexManager(target_engine, schema="dbo")
        with mgr:
            mgr.disable_all(tables=load_order)
            # ... cargar datos ...
        print(mgr.index_results)

    Permisos requeridos: ``ALTER`` sobre las tablas (mssql/oracle/mariadb/mysql) o propiedad de los
    índices (postgresql ``DROP``/``CREATE INDEX``).
    """

    logger: ClassVar[logging.Logger] = logging.getLogger(__name__)

    def __init__(self, engine: Engine, schema: str | None = None, mode: IndexMode = "secondary") -> None:
        self._engine = engine
        self._schema = schema
        self._dialect = engine.dialect.name
        self._mode: IndexMode = mode
        # Índices desactivados (con su restauración), en orden
        self._disabled: list[IndexStep] = []
        # Resultados accesibles tras __exit__
        self.index_results: list[IndexActionResult] = []

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> IndexManager:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        try:
            self.index_results = self.rebuild_all()
        except Exception:  # noqa: BLE001
            self.logger.exception("Error al reconstruir índices — la excepción original no se enmascara")

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def disable_all(self, tables: list[str]) -> None:
        """Deshabilita los índices secundarios no únicos de las tablas indicadas.

        Args:
            tables: Tablas del destino cuyos índices se deshabilitan.
        """
        if self._dialect not in SUPPORTED_DIALECTS:
            self.logger.warning(
                "Dialect '%s' no soportado para gestión de índices. Se continúa sin tocar índices.", self._dialect
            )
            return
        planner = SecondaryIndexPlanner(self._dialect, self._engine.dialect.identifier_preparer)
        self._disabled = []
        with self._engine.connect() as conn:
            for table in tables:
                steps = planner.plan(
                    conn,
                    table=table,
                    schema=self._schema,
                    quoted_table=quote_table(table, self._schema, self._engine),
                    mode=self._mode,
                )
                self._disabled.extend(self._runner().disable(conn, steps))

    def rebuild_all(self) -> list[IndexActionResult]:
        """Reconstruye todos los índices deshabilitados. Retorna resultado por índice."""
        if not self._disabled:
            return []
        with self._engine.connect() as conn:
            return self._runner().restore(conn, self._disabled)

    def _runner(self) -> IndexDdlRunner:
        return IndexDdlRunner(self._dialect, self.logger, commit=True, savepoint=False)


__all__: list[str] = ["IndexManager"]
