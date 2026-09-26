"""UPDATE masivo de MySQL/MariaDB por tabla temporal (``update_via_staging``, P-04).

Separado de ``batch`` (R10b del refactor de reutilización 2026-09-26) sin cambios de comportamiento.
"""

from __future__ import annotations

import contextlib
import logging
import uuid

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import (
    Column,
    MetaData,
    Table,
    and_,
    insert,
    text,
    update,
)
from sqlalchemy.exc import DBAPIError

from .._support.sql_helpers import json_passthrough_binds
from .insert_strategies import InsertExecutionStrategyProtocol

# Mismo logger que antes de separar este código de ``batch`` (R10b): los registros no cambian de nombre.
_log = logging.getLogger("util_bbdd.bulk._execution.batch")


# Errores de MySQL/MariaDB por falta de privilegio al crear la tabla temporal del UPDATE por staging:
# 1044 (acceso denegado a la base de datos), 1142 (comando denegado en la tabla), 1227 (privilegio necesario).
_MYSQL_PRIVILEGE_DENIED_ERRNOS: frozenset[int] = frozenset({1044, 1142, 1227})


class MySQLStagingUpdateStrategy:
    """UPDATE masivo para MySQL/MariaDB vía tabla temporal (P-04, performance-audit de bulk).

    Por cada lote: ``CREATE TEMPORARY TABLE`` con la PK y las columnas a actualizar (tipos de la tabla destino),
    carga de las filas con la estrategia de INSERT del motor, un único ``UPDATE destino, tmp SET ... WHERE
    destino.pk = tmp.pk`` y ``DROP TEMPORARY TABLE``. Con ``TEMPORARY`` MySQL no hace commit implícito, así que
    se respetan la transacción de ``bulk_session`` y ``commit_every_n_chunks``. Medido de extremo a extremo
    (``bulk_update_from_df``): ~12,5× más rápido que el executemany fila a fila (1M filas: 29,5 s frente a 376 s en MySQL 8.4; 27,1 s frente a
    331 s en MariaDB 11.4).

    Misma semántica que el UPDATE por executemany: solo actualiza filas existentes, una PK nula no actualiza nada y,
    si una PK se repite en el lote, gana la última aparición. Es la vía por defecto de ``BulkCrud`` en MySQL/MariaDB
    (``update_via_staging=True``).

    Requiere el privilegio ``CREATE TEMPORARY TABLES``. Si el servidor lo deniega al crear la tabla temporal
    (errno 1044/1142/1227), registra un WARNING, marca ``staging_denied`` y ejecuta ``stmt`` (el UPDATE por fila)
    para ese lote y los siguientes. Un fallo de CREATE no aborta la transacción en MySQL/MariaDB, así que se
    mantiene la atomicidad. Cualquier otro error se propaga.
    """

    def __init__(
        self,
        *,
        table: Table,
        pk_cols: Sequence[str],
        update_cols: Sequence[str],
        loader: InsertExecutionStrategyProtocol,
    ) -> None:
        self._table: Table = table
        self._pk_cols: list[str] = list(pk_cols)
        self._update_cols: list[str] = list(update_cols)
        self._loader: InsertExecutionStrategyProtocol = loader
        #: True si el servidor denegó la tabla temporal; a partir de ahí se usa el UPDATE por fila.
        self.staging_denied: bool = False

    def execute(
        self,
        *,
        connection: Any,
        stmt: Any,
        records: Sequence[Mapping[str, Any]],
    ) -> None:
        if not records:
            return
        if self.staging_denied:
            connection.execute(stmt, list(records))
            return
        cols: list[str] = [*self._pk_cols, *self._update_cols]
        # Última aparición por PK, como el executemany secuencial (el dict conserva el orden de primera aparición).
        rows_by_pk: dict[tuple[Any, ...], dict[str, Any]] = {}
        for record in records:
            rows_by_pk[tuple(record[c] for c in self._pk_cols)] = {c: record[c] for c in cols}

        # PD-12 (2026-09-26): en el esquema de la tabla destino. Sin esquema, con una conexión sin base de datos por
        # defecto y la tabla destino como esquema.tabla, CREATE TEMPORARY TABLE fallaba con "No database selected".
        staging = Table(
            f"tmp_bulkupd_{uuid.uuid4().hex[:12]}",
            MetaData(),
            *(Column(c, self._table.c[c].type) for c in cols),
            schema=self._table.schema,
            prefixes=["TEMPORARY"],
        )
        drop_sql = f"DROP TEMPORARY TABLE IF EXISTS {connection.dialect.identifier_preparer.format_table(staging)}"
        try:
            staging.create(connection)
        except DBAPIError as exc:
            if _mysql_errno(exc) not in _MYSQL_PRIVILEGE_DENIED_ERRNOS:
                raise
            self.staging_denied = True
            _log.warning(
                "update_via_staging: el servidor deniega CREATE TEMPORARY TABLES (%s). Se usa el UPDATE fila a fila, "
                "mucho más lento, en '%s'. Concede el privilegio CREATE TEMPORARY TABLES o pasa "
                "BulkCrud(..., update_via_staging=False) para no intentarlo.",
                exc.orig,
                self._table.name,
            )
            connection.execute(stmt, list(records))
            return
        try:
            json_binds = json_passthrough_binds(staging, cols)
            load_stmt = insert(staging).values(json_binds) if json_binds else insert(staging)
            self._loader.execute(connection=connection, stmt=load_stmt, records=list(rows_by_pk.values()))
            connection.execute(
                update(self._table)
                .values({self._table.c[c]: staging.c[c] for c in self._update_cols})
                .where(and_(*(self._table.c[c] == staging.c[c] for c in self._pk_cols)))
            )
        except BaseException:
            # No ocultar el error original si la limpieza también falla.
            with contextlib.suppress(Exception):
                connection.execute(text(drop_sql))
            raise
        connection.execute(text(drop_sql))


def _mysql_errno(exc: DBAPIError) -> int | None:
    """Código de error MySQL/MariaDB de ``exc`` (``orig.errno`` en mariadb; ``orig.args[0]`` en PyMySQL)."""
    orig: Any = exc.orig
    errno = getattr(orig, "errno", None)
    if isinstance(errno, int):
        return errno
    args = getattr(orig, "args", ())
    return args[0] if args and isinstance(args[0], int) else None


__all__: list[str] = ["MySQLStagingUpdateStrategy"]
