"""Ejecutores por lotes con la cadencia de commit (``BatchStatementExecutor``, ``DeleteBatchExecutor``).

Separado de ``batch`` (R10b del refactor de reutilización 2026-09-26) sin cambios de comportamiento.

Refactor v0.30.1: validate_chunk_size se ha centralizado en _core.validation (ver abajo para re-export).
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

import pandas as pd

from sqlalchemy import (
    Engine,
    Table,
)

from util_bbdd._core.validation import validate_chunk_size

from .._support.rejects import Isolator
from .._support.sql_helpers import SqlColumns
from ._driver_quirks import _driver_decimal_context, _pymssql_plain_decimals, _register_fast_executemany
from .delete_strategies import DeleteExecutionStrategyProtocol, DeleteStrategyResolver
from .insert_strategies import InsertExecutionStrategyProtocol, InsertStrategyResolver
from .session import CommitCadence, SessionScope

# Nota que deja ``_commit_periodico`` cuando falla el COMMIT; ``batch_failure_note`` la reconoce (A4, audit-code 2026-10-01).
_COMMIT_FAILURE_NOTE: str = "bulk: falló el COMMIT periódico de commit_every_n_chunks"


@contextmanager
def batch_failure_note(
    operation: str, table: str, index: int, first_row: int, rows: int, chunk: int | None = None
) -> Generator[None, None, None]:
    """Si el lote falla, añade a la excepción (``add_note``) dónde: operación, tabla, lote y filas de la entrada.

    B-15 (performance-audit de bulk 2026-10-01): el error del driver no decía en qué lote de un millón de filas había
    fallado. Se relanza la misma excepción (mismo tipo y mismo ``str``); la nota sale en el traceback.

    Args:
        operation: ``INSERT``, ``UPDATE`` o ``DELETE``.
        table: Nombre de la tabla destino.
        index: Número de lote (base 0).
        first_row: Posición (base 0) de la primera fila del lote en la entrada (DataFrame o secuencia de chunks).
        rows: Filas del lote.
        chunk: En las vías ``*_from_chunks``, número de chunk de la secuencia (base 0); ``first_row`` es entonces la
            posición en la secuencia entera.
    """
    try:
        yield
    except Exception as exc:
        where: str = f"lote {index}" if chunk is None else f"lote {index} del chunk {chunk}"
        span: str = f"filas {first_row}–{first_row + rows - 1} de la entrada, base 0"
        if _COMMIT_FAILURE_NOTE in getattr(exc, "__notes__", ()):
            # A4: el lote se había ejecutado; lo que falló fue el COMMIT periódico que lo seguía.
            exc.add_note(
                f"bulk {operation} en '{table}': el {where} ({span}) se ejecutó; falló el COMMIT periódico posterior"
            )
        else:
            exc.add_note(f"bulk {operation} en '{table}': falló el {where} ({span})")
        raise


def _commit_periodico(connection: Any, commit_hook: Callable[[Any], None] | None) -> None:
    """Commit periódico de ``commit_every_n_chunks``.

    Dentro de ``BulkCrud.bulk_session`` pasa por ``commit_hook``, que además vuelca al CSV la auditoría de las
    operaciones que ese commit confirma (M-1, audit-code de AuditManager 2026-09-25).
    """
    try:
        if commit_hook is not None:
            commit_hook(connection)
        else:
            connection.commit()
    except Exception as exc:
        exc.add_note(_COMMIT_FAILURE_NOTE)
        raise


class BatchStatementExecutor:
    """Ejecutor OO de statements SQLAlchemy por lotes."""

    def __init__(
        self,
        *,
        engine: Engine,
        chunk_size: int,
        enable_fast_executemany: bool = True,
        insert_resolver: InsertStrategyResolver | None = None,
        commit_every_n_chunks: int | None = None,
        session: SessionScope | None = None,
    ) -> None:
        self._engine: Engine = engine
        self._chunk_size: int = validate_chunk_size(chunk_size)
        #: Conexión y gancho de commit de ``BulkCrud.bulk_session()`` (compartidos con el ``DeleteBatchExecutor``).
        self.session: SessionScope = session or SessionScope()
        # BLK-08 (AUDIT_CODE 2026-09-22): la cadencia distingue las filas durablemente comprometidas (commit periódico
        # o final) de las ejecutadas aún sin commit, para saber cuántas sobreviven si una carga falla a mitad de sesión.
        #: Cadencia de ``commit_every_n_chunks``; el contador de lotes se arrastra entre llamadas dentro de una sesión.
        self.cadence: CommitCadence = CommitCadence(commit_every_n_chunks, ledger=self.session.rows)
        #: ``RejectOptions(on_error="isolate")`` lo fija durante cada operación: cada lote va en un SAVEPOINT (S-2).
        self.isolator: Isolator | None = None
        drivername: str = str(engine.url.drivername).lower()
        self._insert_strategy: InsertExecutionStrategyProtocol = (insert_resolver or InsertStrategyResolver()).resolve(
            engine.dialect.name, drivername
        )
        if enable_fast_executemany and engine.dialect.name == "mssql" and "pyodbc" in drivername:
            _register_fast_executemany(engine)

    @property
    def rows_committed(self) -> int:
        """Filas confirmadas por commits de la cadencia (``commit_every_n_chunks``); 0 sin cadencia (BLK-08)."""
        return self.cadence.rows_committed

    @property
    def insert_strategy(self) -> InsertExecutionStrategyProtocol:
        """Estrategia INSERT resuelta para el motor (la usa también el UPDATE por staging para cargar la temporal)."""
        return self._insert_strategy

    def execute(
        self,
        *,
        records: Sequence[Mapping[str, Any]],
        stmt: Any,
        strategy: InsertExecutionStrategyProtocol | None = None,
        first_row: int = 0,
    ) -> None:
        """Ejecuta un statement SQLAlchemy por batches.

        ``first_row`` es la posición en la entrada de ``records[0]``: la de las filas rechazadas con :attr:`isolator`.

        ``strategy`` sustituye a la estrategia INSERT resuelta para este motor (p.ej.
        :class:`MySQLStagingUpdateStrategy` en el UPDATE por staging); ``None`` usa la resuelta.

        Si ``session`` tiene una conexión (la de ``BulkCrud.bulk_session()``),
        reutiliza esa conexión en lugar de abrir una nueva transacción por lote.

        Cuando ``commit_every_n_chunks`` está configurado y no hay conexión activa,
        usa ``engine.connect()`` (commit-as-you-go) en lugar de ``engine.begin()``
        para poder commitear lotes intermedios, y hace un commit final del resto.
        """
        self._run(lambda connection: self._execute_on_connection(connection, records, stmt, strategy, first_row))

    def execute_columns(self, *, block: SqlColumns, stmt: Any, first_row: int = 0) -> None:
        """Ejecuta un INSERT de un bloque por columnas con la estrategia resuelta, sin un ``dict`` por fila (B-03).

        Solo para estrategias con ``supports_columns`` (COPY de PostgreSQL, ``execute_values``, ``executemany`` de
        PyMySQL), que envían tuplas al driver. El bloque es **un** lote: no se trocea por filas, porque
        ``SqlColumns[a:b]`` construiría un ``dict`` por fila y anularía la mejora. Misma sesión y cadencia que
        :meth:`execute`. Con :attr:`isolator`, si el bloque falla se reenvía como registros para aislar las filas.
        """
        strategy: Any = self._insert_strategy
        if not getattr(strategy, "supports_columns", False):
            raise TypeError(f"{type(strategy).__name__} no admite bloques por columnas")

        def run(connection: Any) -> None:
            if self.isolator is None:
                strategy.execute_columns(connection=connection, stmt=stmt, block=block)
            else:
                self.isolator.run_columns(
                    connection,
                    block,
                    lambda columns: strategy.execute_columns(connection=connection, stmt=stmt, block=columns),
                    lambda records: self._send(connection, records, stmt, strategy),
                    first_row=first_row,
                )
            if self.cadence.on_batch(len(block)):
                _commit_periodico(connection, self.session.commit_hook)
                self.cadence.confirm()

        self._run(run)

    @property
    def supports_columns(self) -> bool:
        """``True`` si la estrategia INSERT resuelta admite :meth:`execute_columns`."""
        return bool(getattr(self._insert_strategy, "supports_columns", False))

    def _run(self, work: Callable[[Any], None]) -> None:
        """Ejecuta ``work(connection)`` en la conexión de la sesión o en una transacción propia (con o sin cadencia)."""
        if self.session.connection is not None:
            work(self.session.connection)
        elif self.cadence.every is not None:
            self.cadence.restart()
            with self._engine.connect() as connection:
                try:
                    work(connection)
                except BaseException:
                    self.cadence.discard_pending()  # lo pendiente se deshace con la conexión
                    raise
                connection.commit()
                self.cadence.confirm()
        else:
            with self._engine.begin() as connection:
                work(connection)

    def _execute_on_connection(
        self,
        connection: Any,
        records: Sequence[Mapping[str, Any]],
        stmt: Any,
        strategy: InsertExecutionStrategyProtocol | None = None,
        first_row: int = 0,
    ) -> None:
        """Ejecuta los batches sobre una conexión ya abierta.

        Si ``commit_every_n_chunks`` está activo, commitea sobre ``connection``
        (que debe estar en modo commit-as-you-go) cada N lotes. El commit del
        resto (tail) es responsabilidad del llamador (``execute`` / ``bulk_session``).
        Con :attr:`isolator`, cada lote va en un SAVEPOINT; el commit periódico queda fuera de él.
        """
        chosen: InsertExecutionStrategyProtocol = strategy or self._insert_strategy
        for start in range(0, len(records), self._chunk_size):
            batch: Sequence[Mapping[str, Any]] = records[start : start + self._chunk_size]
            if self.isolator is None:
                self._send(connection, batch, stmt, chosen)
            else:
                self.isolator.run_records(
                    connection,
                    batch,
                    lambda items: self._send(connection, items, stmt, chosen),
                    first_row=first_row + start,
                )
            if self.cadence.on_batch(len(batch)):
                _commit_periodico(connection, self.session.commit_hook)
                self.cadence.confirm()

    def _send(
        self,
        connection: Any,
        batch: Sequence[Mapping[str, Any]],
        stmt: Any,
        strategy: InsertExecutionStrategyProtocol,
    ) -> None:
        """Envía un lote de registros con ``strategy``."""
        with _driver_decimal_context(self._engine):
            strategy.execute(connection=connection, stmt=stmt, records=_pymssql_plain_decimals(self._engine, batch))


class DeleteBatchExecutor:
    """Template Method para ejecutar DELETE por lotes."""

    def __init__(
        self,
        *,
        engine: Engine,
        chunk_size: int,
        resolver: DeleteStrategyResolver | None = None,
        commit_every_n_chunks: int | None = None,
        session: SessionScope | None = None,
    ) -> None:
        self._engine: Engine = engine
        self._chunk_size: int = validate_chunk_size(chunk_size)
        self._resolver: DeleteStrategyResolver = resolver or DeleteStrategyResolver()
        #: Conexión de ``BulkCrud.bulk_session()`` (P-26): el DELETE participa en la transacción de la sesión.
        self.session: SessionScope = session or SessionScope()
        self._commit_every_n_chunks: int | None = commit_every_n_chunks
        #: Lotes desde el último commit periódico. Se reinicia en cada llamada salvo entre los chunks de un mismo stream
        #: (``bulk_delete_from_chunks``): si no, con chunks de pocos lotes nunca se llegaría al commit periódico.
        self._cadence: CommitCadence = CommitCadence(commit_every_n_chunks, ledger=self.session.rows)
        #: Como en ``BatchStatementExecutor``: cada lote en un SAVEPOINT con ``RejectOptions(on_error="isolate")`` (S-2).
        self.isolator: Isolator | None = None

    def execute(
        self,
        *,
        table: Table,
        df: pd.DataFrame,
        pk_cols: Sequence[str],
        row_offset: int = 0,
        chunk: int | None = None,
        continue_cadence: bool = False,
    ) -> None:
        """Ejecuta DELETE por lotes usando la estrategia resuelta por dialecto.

        Dentro de ``BulkCrud.bulk_session()`` usa la conexión de la sesión; fuera, una transacción propia. Con
        ``commit_every_n_chunks`` confirma cada N lotes, como INSERT y UPDATE (auditoría de bulk 2026-09-24,
        hallazgo 7: fuera de la sesión todo el DELETE iba en una sola transacción); si falla, quedan borrados los lotes
        ya confirmados.
        """
        # Posición en la entrada (nota de error, B-15a) y continuidad de la cadencia entre chunks de un stream (B-08).
        position: dict[str, Any] = {"row_offset": row_offset, "chunk": chunk, "continue_cadence": continue_cadence}
        if self.session.connection is not None:
            self._execute_on_connection(self.session.connection, table=table, df=df, pk_cols=pk_cols, **position)
            return
        if self._commit_every_n_chunks is not None:
            with self._engine.connect() as connection:
                try:
                    self._execute_on_connection(connection, table=table, df=df, pk_cols=pk_cols, **position)
                except BaseException:
                    self.session.rows.discard()  # lo pendiente se deshace con la conexión
                    raise
                connection.commit()
                self.session.rows.confirm()
            return
        with self._engine.begin() as connection:
            self._execute_on_connection(connection, table=table, df=df, pk_cols=pk_cols, **position)

    def _execute_on_connection(
        self,
        connection: Any,
        *,
        table: Table,
        df: pd.DataFrame,
        pk_cols: Sequence[str],
        row_offset: int = 0,
        chunk: int | None = None,
        continue_cadence: bool = False,
    ) -> None:
        strategy: DeleteExecutionStrategyProtocol = self._resolver.resolve(self._engine.dialect.name)
        # El contador de lotes del DELETE empieza en cada llamada (a diferencia del INSERT), salvo entre chunks de un
        # stream. El libro de filas es el de la sesión: sus filas suman a ``rows_committed`` (v0.18.0) y su commit
        # periódico confirma también las filas de INSERT/UPDATE pendientes en la misma transacción (2a).
        cadence = self._cadence
        if not continue_cadence:
            cadence.restart()
        for index, batch_df in enumerate(self._iter_batches(df=df, pk_cols=pk_cols)):
            first_row = row_offset + index * self._chunk_size
            with batch_failure_note("DELETE", table.fullname, index, first_row, len(batch_df), chunk):
                if self.isolator is None:
                    self._execute_batch(
                        strategy=strategy, connection=connection, table=table, batch_df=batch_df, pk_cols=pk_cols
                    )
                else:
                    self.isolator.run_frame(
                        connection,
                        batch_df,
                        lambda frame: self._execute_batch(
                            strategy=strategy, connection=connection, table=table, batch_df=frame, pk_cols=pk_cols
                        ),
                        first_row=first_row,
                    )
            if cadence.on_batch(len(batch_df)):
                _commit_periodico(connection, self.session.commit_hook)
                cadence.confirm()

    def _iter_batches(self, *, df: pd.DataFrame, pk_cols: Sequence[str]) -> Iterator[pd.DataFrame]:
        """Genera batches no vacíos para la ejecución sin materializar la lista completa."""
        pk_list = list(pk_cols)
        for start in range(0, len(df), self._chunk_size):
            batch_df: pd.DataFrame = df[pk_list].iloc[start : start + self._chunk_size]
            if not batch_df.empty:
                yield batch_df

    def _execute_batch(
        self,
        *,
        strategy: DeleteExecutionStrategyProtocol,
        connection: Any,
        table: Table,
        batch_df: pd.DataFrame,
        pk_cols: Sequence[str],
    ) -> None:
        """Hook del template para ejecutar cada batch."""
        with _driver_decimal_context(self._engine):
            strategy.execute(connection=connection, table=table, batch_df=batch_df, pk_cols=pk_cols)


__all__: list[str] = ["BatchStatementExecutor", "DeleteBatchExecutor", "batch_failure_note", "validate_chunk_size"]
