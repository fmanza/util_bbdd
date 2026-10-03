"""UPDATE masivo por tabla temporal (``update_via_staging``): MySQL/MariaDB (P-04) y PostgreSQL (B-01).

Separado de ``batch`` (R10b del refactor de reutilización 2026-09-26). B-01 (performance-audit de bulk 2026-10-01):
PostgreSQL usa la misma estrategia.
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

from ...metadata import facts
from .._support.dialect import MYSQL_FAMILY
from .._support.sql_helpers import json_passthrough_binds
from .insert_strategies import InsertExecutionStrategyProtocol

# Mismo logger que antes de separar este código de ``batch`` (R10b): los registros no cambian de nombre.
_log = logging.getLogger("util_bbdd.bulk._execution.batch")


#: Dialectos con UPDATE por tabla temporal (``BulkCrud(update_via_staging=True)``).
STAGING_UPDATE_DIALECTS: frozenset[str] = MYSQL_FAMILY | {"postgresql"}

# Errores de MySQL/MariaDB por falta de privilegio al crear la tabla temporal del UPDATE por staging:
# 1044 (acceso denegado a la base de datos), 1142 (comando denegado en la tabla), 1227 (privilegio necesario).
_MYSQL_PRIVILEGE_DENIED_ERRNOS: frozenset[int] = frozenset({1044, 1142, 1227})


class StagingUpdateStrategy:
    """UPDATE masivo vía tabla temporal: MySQL/MariaDB (P-04) y PostgreSQL (B-01).

    Por cada lote: tabla temporal con la PK y las columnas a actualizar (tipos de la tabla destino), carga de las filas
    con la estrategia de INSERT del motor, un único ``UPDATE`` con join a la temporal y borrado de la temporal.

    - **MySQL/MariaDB**: ``CREATE TEMPORARY TABLE`` en el esquema de la destino, ``UPDATE destino, tmp SET … WHERE …`` y
      ``DROP TEMPORARY TABLE``. Con ``TEMPORARY`` MySQL no hace commit implícito. Medido (1M filas): 29,5 s frente a
      376 s en MySQL 8.4; 27,1 s frente a 331 s en MariaDB 11.4.
    - **PostgreSQL**: ``CREATE TEMPORARY TABLE tmp AS SELECT pk, cols FROM destino WITH NO DATA`` (copia los tipos
      exactos, también ENUM, dominios y arrays, sin crear tipos), carga por COPY, ``UPDATE destino SET … FROM tmp WHERE
      …`` y ``DROP TABLE``. El DDL es transaccional. Medido (1M filas, PostgreSQL 17): 24,9 s → 10,6 s.

    Se respetan la transacción de ``bulk_session`` y ``commit_every_n_chunks``. Misma semántica que el UPDATE por
    executemany: solo actualiza filas existentes, una PK nula no actualiza nada y, si una PK se repite en el lote, gana la
    última aparición.

    Sin privilegio para crear la temporal (MySQL/MariaDB ``CREATE TEMPORARY TABLES``; PostgreSQL ``TEMP``) registra un
    WARNING, marca ``staging_denied`` y ejecuta ``stmt`` (el UPDATE por fila) para ese lote y los siguientes:

    - MySQL/MariaDB: se detecta por el error al crear (errno 1044/1142/1227); un CREATE fallido no aborta la transacción.
    - PostgreSQL: se comprueba **antes** con ``has_database_privilege(current_database(), 'TEMP')``, porque en PostgreSQL
      un CREATE fallido deja la transacción abortada (``25P02``) y no habría forma de seguir con el UPDATE por fila.

    Cualquier otro error se propaga.
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
        self._temp_privilege_checked: bool = False

    def execute(
        self,
        *,
        connection: Any,
        stmt: Any,
        records: Sequence[Mapping[str, Any]],
    ) -> None:
        if not records:
            return
        postgresql: bool = connection.dialect.name == "postgresql"
        if postgresql and not self._temp_privilege_checked:
            self._temp_privilege_checked = True
            if not facts.can_create_temp_tables(connection):
                self._deny(privilege="TEMP", detail="has_database_privilege(current_database(), 'TEMP') = false")
        if self.staging_denied:
            connection.execute(stmt, list(records))
            return
        cols: list[str] = [*self._pk_cols, *self._update_cols]
        # Última aparición por PK, como el executemany secuencial (el dict conserva el orden de primera aparición).
        rows_by_pk: dict[tuple[Any, ...], dict[str, Any]] = {}
        for record in records:
            rows_by_pk[tuple(record[c] for c in self._pk_cols)] = {c: record[c] for c in cols}

        # PD-12 (2026-09-26): en MySQL, en el esquema de la tabla destino; sin esquema, con una conexión sin base de
        # datos por defecto y la destino como esquema.tabla, CREATE TEMPORARY TABLE fallaba con "No database selected".
        # PostgreSQL no admite esquema en una tabla temporal (va siempre a pg_temp).
        staging = Table(
            f"tmp_bulkupd_{uuid.uuid4().hex[:12]}",
            MetaData(),
            *(Column(c, self._table.c[c].type) for c in cols),
            schema=None if postgresql else self._table.schema,
            prefixes=["TEMPORARY"],
        )
        quoted_staging: str = connection.dialect.identifier_preparer.format_table(staging)
        drop_sql = (
            f"DROP TABLE IF EXISTS {quoted_staging}"
            if postgresql
            else f"DROP TEMPORARY TABLE IF EXISTS {quoted_staging}"
        )
        if not self._create_staging(connection, staging, cols):
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
            # No ocultar el error original si la limpieza también falla (en PostgreSQL la transacción queda abortada y
            # su rollback borra la temporal).
            with contextlib.suppress(Exception):
                connection.execute(text(drop_sql))
            raise
        connection.execute(text(drop_sql))

    def _create_staging(self, connection: Any, staging: Table, cols: Sequence[str]) -> bool:
        """Crea la temporal; ``False`` si MySQL/MariaDB la deniega por privilegio (y entonces queda ``staging_denied``)."""
        preparer = connection.dialect.identifier_preparer
        if connection.dialect.name == "postgresql":
            quoted_cols: str = ", ".join(preparer.quote(c) for c in cols)
            connection.execute(
                text(
                    f"CREATE TEMPORARY TABLE {preparer.format_table(staging)} AS SELECT {quoted_cols} "
                    f"FROM {preparer.format_table(self._table)} WITH NO DATA"
                )
            )
            return True
        try:
            staging.create(connection)
        except DBAPIError as exc:
            if _mysql_errno(exc) not in _MYSQL_PRIVILEGE_DENIED_ERRNOS:
                raise
            self._deny(privilege="CREATE TEMPORARY TABLES", detail=str(exc.orig))
            return False
        return True

    def _deny(self, *, privilege: str, detail: str) -> None:
        """Pasa al UPDATE por fila en este lote y los siguientes, con un WARNING."""
        self.staging_denied = True
        _log.warning(
            "update_via_staging: el servidor deniega %s (%s). Se usa el UPDATE fila a fila, mucho más lento, en '%s'. "
            "Concede el privilegio %s o pasa BulkCrud(..., update_via_staging=False) para no intentarlo.",
            privilege,
            detail,
            self._table.name,
            privilege,
        )


#: Nombre anterior a B-01, cuando la estrategia solo existía para MySQL/MariaDB.
MySQLStagingUpdateStrategy = StagingUpdateStrategy


def _mysql_errno(exc: DBAPIError) -> int | None:
    """Código de error MySQL/MariaDB de ``exc`` (``orig.errno`` en mariadb; ``orig.args[0]`` en PyMySQL)."""
    orig: Any = exc.orig
    errno = getattr(orig, "errno", None)
    if isinstance(errno, int):
        return errno
    args = getattr(orig, "args", ())
    return args[0] if args and isinstance(args[0], int) else None


__all__: list[str] = ["STAGING_UPDATE_DIALECTS", "MySQLStagingUpdateStrategy", "StagingUpdateStrategy"]
