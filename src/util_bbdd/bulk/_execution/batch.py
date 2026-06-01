"""Ejecutores OO para operaciones batch internas de bulk_crud."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Any, Protocol

import pandas as pd

from sqlalchemy import Delete, Engine, Table, and_, bindparam, delete, event, text

# ---------------------------------------------------------------------------
# FA — fast_executemany para SQL Server / pyodbc
# ---------------------------------------------------------------------------

_DEFAULT_SQL_BASED_DELETE_DIALECTS: frozenset[str] = frozenset({"mysql", "mariadb", "mssql", "hsqldb"})


def _fast_executemany_listener(
    conn: Any,
    cursor: Any,
    statement: Any,
    params: Any,
    context: Any,
    executemany: bool,
) -> None:
    if executemany and hasattr(cursor, "fast_executemany"):
        cursor.fast_executemany = True


def _register_fast_executemany(engine: Engine) -> None:
    """Registra el listener fast_executemany en el engine si aún no está registrado.

    Omite el registro si ``engine`` no es un Engine SQLAlchemy real (p.ej. MagicMock
    en tests) o si el listener ya está presente. Delega la deduplicación a
    ``event.contains``, evitando el riesgo de falso-positivo con ``id()`` cuando un
    engine destruido y otro nuevo comparten la misma dirección de memoria.
    """
    if not isinstance(engine, Engine):
        return
    if not event.contains(engine, "before_cursor_execute", _fast_executemany_listener):
        event.listen(engine, "before_cursor_execute", _fast_executemany_listener)


# ---------------------------------------------------------------------------
# FB — Estrategias INSERT (execute_values para PostgreSQL/psycopg2)
# ---------------------------------------------------------------------------


class InsertExecutionStrategyProtocol(Protocol):
    """Contrato para ejecutar INSERT de un batch."""

    def execute(
        self,
        *,
        connection: Any,
        stmt: Any,
        records: Sequence[Mapping[str, Any]],
    ) -> None:
        """Ejecuta inserción de un batch."""


class DefaultInsertStrategy:
    """INSERT por defecto: SQLAlchemy executemany (todos los motores)."""

    def execute(
        self,
        *,
        connection: Any,
        stmt: Any,
        records: Sequence[Mapping[str, Any]],
    ) -> None:
        connection.execute(stmt, list(records))


class PostgreSQLExecuteValuesStrategy:
    """INSERT para PostgreSQL/psycopg2 vía execute_values.

    Genera un único ``INSERT INTO t (...) VALUES (%s,...), (%s,...), ...`` por
    batch en lugar de N sentencias individuales: 1 round-trip por chunk en vez
    de N, con ganancia típica de 3–5× respecto a executemany.

    Solo aplica al driver legacy ``psycopg2``. Para ``psycopg`` (psycopg3, el
    driver por defecto de la librería) se usa :class:`PostgresCopyStrategy`.

    Fallback a :class:`DefaultInsertStrategy` cuando:
    - ``stmt`` es un ``TextClause`` (ruta ``override_identity``).
    - psycopg2 no está disponible en el entorno.
    """

    def execute(
        self,
        *,
        connection: Any,
        stmt: Any,
        records: Sequence[Mapping[str, Any]],
    ) -> None:
        if not records:
            return
        if not hasattr(stmt, "table"):
            # TextClause (OVERRIDING SYSTEM VALUE) u otro stmt sin .table → fallback
            connection.execute(stmt, list(records))
            return
        try:
            from psycopg2.extras import execute_values as _pg_execute_values  # type: ignore[import-untyped]
        except ImportError:
            connection.execute(stmt, list(records))
            return

        table = stmt.table
        cols: list[str] = list(records[0].keys())
        preparer = connection.dialect.identifier_preparer
        quoted_table: str = preparer.format_table(table)
        quoted_cols: str = ", ".join(preparer.quote(c) for c in cols)
        sql: str = f"INSERT INTO {quoted_table} ({quoted_cols}) VALUES %s"
        data: list[tuple[Any, ...]] = [tuple(r[c] for c in cols) for r in records]
        with connection.connection.cursor() as raw_cursor:
            _pg_execute_values(raw_cursor, sql, data, page_size=len(data))


class PostgresCopyStrategy:
    """INSERT para PostgreSQL/psycopg3 vía ``COPY ... FROM STDIN`` (``cursor.copy()``).

    Es la vía nativa más rápida de PostgreSQL: ``COPY`` salta el parseo SQL por
    fila y transmite los datos por STDIN (sin staging a disco), con ganancias de
    1 orden de magnitud sobre ``executemany`` en cargas de gran volumen.

    psycopg3 adapta automáticamente cada valor Python (``int``, ``float``, ``str``,
    ``datetime``, ``bytes``, ``None`` → NULL, JSON como texto) al formato COPY, por
    lo que se reutilizan los registros ya normalizados por ``normalize_records_for_sql``.

    Fallback a ejecución estándar (``connection.execute``) cuando ``stmt`` es un
    ``TextClause`` (ruta ``override_identity`` / ``OVERRIDING SYSTEM VALUE``), que
    no es expresable con COPY.
    """

    def execute(
        self,
        *,
        connection: Any,
        stmt: Any,
        records: Sequence[Mapping[str, Any]],
    ) -> None:
        if not records:
            return
        if not hasattr(stmt, "table"):
            # TextClause (OVERRIDING SYSTEM VALUE) u otro stmt sin .table → fallback
            connection.execute(stmt, list(records))
            return

        table = stmt.table
        cols: list[str] = list(records[0].keys())
        preparer = connection.dialect.identifier_preparer
        quoted_table: str = preparer.format_table(table)
        quoted_cols: str = ", ".join(preparer.quote(c) for c in cols)
        sql: str = f"COPY {quoted_table} ({quoted_cols}) FROM STDIN"
        raw_cursor = connection.connection.cursor()
        try:
            with raw_cursor.copy(sql) as copy:
                for record in records:
                    copy.write_row([record[c] for c in cols])
        finally:
            raw_cursor.close()


class MySQLMultiRowInsertStrategy:
    """INSERT para MySQL/MariaDB vía sentencia multi-fila (``INSERT ... VALUES (...),(...)``).

    Construye una única sentencia parametrizada con varias filas por round-trip en
    lugar de N inserts individuales, evitando el coste de parseo por fila. Es la vía
    portable y segura (parametrizada, sin ficheros) frente a ``LOAD DATA INFILE``,
    que exige ``local_infile`` (riesgo de lectura de ficheros) y staging a disco.

    Las filas se sub-lotean en grupos de ``max_rows_per_statement`` para acotar el
    tamaño del paquete (``max_allowed_packet``): una sentencia demasiado grande con
    columnas TEXT/BLOB puede provocar ``Lost connection to server (2013)``.

    **Optimización**: Cachea templates SQL por número de filas para evitar reconstrucción
    en sub-lotes del mismo tamaño (típicamente todos excepto el último).

    Fallback a ejecución estándar cuando ``stmt`` no expone ``.table`` (``TextClause``).
    """

    def __init__(self, *, max_rows_per_statement: int = 1000) -> None:
        if max_rows_per_statement < 1:
            raise ValueError(f"max_rows_per_statement debe ser ≥ 1, recibido: {max_rows_per_statement}")
        self._max_rows: int = max_rows_per_statement
        # Caché: (num_rows, cols_tuple) → (template_sql_string, placeholder_pattern)
        self._sql_template_cache: dict[tuple[int, tuple[str, ...]], tuple[str, str]] = {}

    def _build_sql_template(
        self,
        num_rows: int,
        cols: list[str],
        quoted_table: str,
        quoted_cols: str,
    ) -> str:
        """Construye template SQL para N filas, reutilizando caché si existe.

        Args:
            num_rows: Número de filas en el sub-lote.
            cols: Lista de nombres de columnas (sin comillas).
            quoted_table: Nombre de tabla con comillas.
            quoted_cols: Nombres de columnas con comillas, separados por `,`.

        Returns:
            SQL template como string (p.ej., "INSERT INTO t (a, b) VALUES (:p0_0, :p0_1), (:p1_0, :p1_1)")
        """
        cols_tuple: tuple[str, ...] = tuple(cols)
        cache_key: tuple[int, tuple[str, ...]] = (num_rows, cols_tuple)

        if cache_key in self._sql_template_cache:
            cached_sql, _pattern = self._sql_template_cache[cache_key]
            return cached_sql

        # Construir template: VALUES (:p0_0, :p0_1, ...), (:p1_0, :p1_1, ...), ...
        value_clauses: list[str] = []
        for row_index in range(num_rows):
            tokens: list[str] = []
            for col_index in range(len(cols)):
                bind_name: str = f"p{row_index}_{col_index}"
                tokens.append(f":{bind_name}")
            value_clauses.append(f"({', '.join(tokens)})")

        template_sql: str = f"INSERT INTO {quoted_table} ({quoted_cols}) VALUES {', '.join(value_clauses)}"
        # Guardar en caché
        self._sql_template_cache[cache_key] = (template_sql, "")
        return template_sql

    def execute(
        self,
        *,
        connection: Any,
        stmt: Any,
        records: Sequence[Mapping[str, Any]],
    ) -> None:
        if not records:
            return
        if not hasattr(stmt, "table"):
            connection.execute(stmt, list(records))
            return

        table = stmt.table
        cols: list[str] = list(records[0].keys())
        preparer = connection.dialect.identifier_preparer
        quoted_table: str = preparer.format_table(table)
        quoted_cols: str = ", ".join(preparer.quote(c) for c in cols)

        for start in range(0, len(records), self._max_rows):
            sub_batch: Sequence[Mapping[str, Any]] = records[start : start + self._max_rows]
            num_rows: int = len(sub_batch)

            # Obtener template (del caché si existe)
            template_sql: str = self._build_sql_template(num_rows, cols, quoted_table, quoted_cols)

            # Rellenar parámetros
            params: dict[str, Any] = {}
            for row_index, record in enumerate(sub_batch):
                for col_index, col in enumerate(cols):
                    bind_name: str = f"p{row_index}_{col_index}"
                    params[bind_name] = record[col]

            connection.execute(text(template_sql), params)


class InsertStrategyResolver:
    """Resuelve la estrategia INSERT óptima según dialecto y driver.

    Mapa de resolución:

    - ``postgresql`` + ``psycopg2`` → :class:`PostgreSQLExecuteValuesStrategy`.
    - ``postgresql`` + ``psycopg`` (psycopg3, driver por defecto) → :class:`PostgresCopyStrategy`.
    - ``mysql`` / ``mariadb`` → :class:`MySQLMultiRowInsertStrategy`.
    - resto (Oracle, SQL Server, SQLite, HSQLDB) → :class:`DefaultInsertStrategy`
      (``executemany``; en SQL Server acelerado por ``fast_executemany``).
    """

    def __init__(
        self,
        *,
        pg_copy_strategy: InsertExecutionStrategyProtocol | None = None,
        pg_execute_values_strategy: InsertExecutionStrategyProtocol | None = None,
        mysql_strategy: InsertExecutionStrategyProtocol | None = None,
        default_strategy: InsertExecutionStrategyProtocol | None = None,
    ) -> None:
        self._pg_copy_strategy: InsertExecutionStrategyProtocol = pg_copy_strategy or PostgresCopyStrategy()
        self._pg_execute_values_strategy: InsertExecutionStrategyProtocol = (
            pg_execute_values_strategy or PostgreSQLExecuteValuesStrategy()
        )
        self._mysql_strategy: InsertExecutionStrategyProtocol = mysql_strategy or MySQLMultiRowInsertStrategy()
        self._default_strategy: InsertExecutionStrategyProtocol = default_strategy or DefaultInsertStrategy()

    def resolve(self, dialect_name: str, drivername: str) -> InsertExecutionStrategyProtocol:
        """Devuelve la estrategia adecuada para el dialecto y driver indicados."""
        if dialect_name == "postgresql":
            # "psycopg2" contiene "psycopg": comprobar el legacy primero.
            if "psycopg2" in drivername:
                return self._pg_execute_values_strategy
            if "psycopg" in drivername:
                return self._pg_copy_strategy
        if dialect_name in ("mysql", "mariadb"):
            return self._mysql_strategy
        return self._default_strategy


# ---------------------------------------------------------------------------
# DELETE strategies (sin cambios)
# ---------------------------------------------------------------------------


class DeleteExecutionStrategyProtocol(Protocol):
    """Contrato para ejecutar DELETE de un batch."""

    def execute(
        self,
        *,
        connection: Any,
        table: Table,
        batch_df: pd.DataFrame,
        pk_cols: Sequence[str],
    ) -> None:
        """Ejecuta borrado de un batch."""


class SqlBasedDeleteStrategy:
    """Estrategia de DELETE SQL parametrizado para motores soportados."""

    def execute(
        self,
        *,
        connection: Any,
        table: Table,
        batch_df: pd.DataFrame,
        pk_cols: Sequence[str],
    ) -> None:
        values: list[tuple[Any, ...]] = [tuple(r) for r in batch_df[pk_cols].itertuples(index=False, name=None)]
        if not values:
            return

        preparer = connection.dialect.identifier_preparer
        quoted_table: str = preparer.format_table(table)
        quoted_pk_cols: list[str] = [preparer.quote(column) for column in pk_cols]

        params: dict[str, Any] = {}
        if len(pk_cols) == 1:
            pk_col: str = quoted_pk_cols[0]
            placeholders: list[str] = []
            for row_index, row_values in enumerate(values):
                bind_name: str = f"pk_{row_index}_0"
                placeholders.append(f":{bind_name}")
                params[bind_name] = row_values[0]
            sql = f"DELETE FROM {quoted_table} WHERE {pk_col} IN ({', '.join(placeholders)})"
        else:
            row_placeholders: list[str] = []
            for row_index, row_values in enumerate(values):
                bind_tokens: list[str] = []
                for column_index, raw_value in enumerate(row_values):
                    bind_name = f"pk_{row_index}_{column_index}"
                    bind_tokens.append(f":{bind_name}")
                    params[bind_name] = raw_value
                row_placeholders.append(f"({', '.join(bind_tokens)})")

            pk_tuple_sql: str = ", ".join(quoted_pk_cols)
            sql = f"DELETE FROM {quoted_table} WHERE ({pk_tuple_sql}) IN ({', '.join(row_placeholders)})"

        connection.execute(text(sql), params)


class GenericDeleteStrategy:
    """Estrategia de DELETE genérico con SQLAlchemy Core."""

    def execute(
        self,
        *,
        connection: Any,
        table: Table,
        batch_df: pd.DataFrame,
        pk_cols: Sequence[str],
    ) -> None:
        stmt: Delete = delete(table).where(and_(*(table.c[column] == bindparam(column) for column in pk_cols)))
        records = batch_df.to_dict(orient="records")
        connection.execute(stmt, records)


class DeleteStrategyResolver:
    """Resuelve estrategia DELETE según dialecto."""

    def __init__(
        self,
        *,
        sql_based_dialects: frozenset[str] | None = None,
        sql_based_strategy: DeleteExecutionStrategyProtocol | None = None,
        generic_strategy: DeleteExecutionStrategyProtocol | None = None,
    ) -> None:
        self._sql_based_dialects: frozenset[str] = sql_based_dialects or _DEFAULT_SQL_BASED_DELETE_DIALECTS
        self._sql_based_strategy: DeleteExecutionStrategyProtocol = sql_based_strategy or SqlBasedDeleteStrategy()
        self._generic_strategy: DeleteExecutionStrategyProtocol = generic_strategy or GenericDeleteStrategy()

    def resolve(self, dialect_name: str) -> DeleteExecutionStrategyProtocol:
        """Devuelve la estrategia adecuada para el dialecto indicado."""
        if dialect_name in self._sql_based_dialects:
            return self._sql_based_strategy
        return self._generic_strategy


# ---------------------------------------------------------------------------
# BatchStatementExecutor — INSERT con estrategia por motor
# ---------------------------------------------------------------------------


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
    ) -> None:
        self._engine: Engine = engine
        self._chunk_size: int = chunk_size
        self._active_connection: Any | None = None
        self._commit_every_n_chunks: int | None = commit_every_n_chunks
        self._chunks_since_commit: int = 0
        drivername: str = str(engine.url.drivername).lower()
        self._insert_strategy: InsertExecutionStrategyProtocol = (insert_resolver or InsertStrategyResolver()).resolve(
            engine.dialect.name, drivername
        )
        if enable_fast_executemany and engine.dialect.name == "mssql" and "pyodbc" in drivername:
            _register_fast_executemany(engine)

    def execute(self, *, records: Sequence[Mapping[str, Any]], stmt: Any) -> None:
        """Ejecuta un statement SQLAlchemy por batches.

        Si ``_active_connection`` está activo (inyectado via ``BulkCrud.bulk_session()``),
        reutiliza esa conexión en lugar de abrir una nueva transacción por lote.

        Cuando ``commit_every_n_chunks`` está configurado y no hay conexión activa,
        usa ``engine.connect()`` (commit-as-you-go) en lugar de ``engine.begin()``
        para poder commitear lotes intermedios, y hace un commit final del resto.
        """
        if self._active_connection is not None:
            self._execute_on_connection(self._active_connection, records, stmt)
        elif self._commit_every_n_chunks is not None:
            self._chunks_since_commit = 0
            with self._engine.connect() as connection:
                self._execute_on_connection(connection, records, stmt)
                connection.commit()
                self._chunks_since_commit = 0
        else:
            with self._engine.begin() as connection:
                self._execute_on_connection(connection, records, stmt)

    def _execute_on_connection(self, connection: Any, records: Sequence[Mapping[str, Any]], stmt: Any) -> None:
        """Ejecuta los batches sobre una conexión ya abierta.

        Si ``commit_every_n_chunks`` está activo, commitea sobre ``connection``
        (que debe estar en modo commit-as-you-go) cada N lotes. El commit del
        resto (tail) es responsabilidad del llamador (``execute`` / ``bulk_session``).
        """
        for start in range(0, len(records), self._chunk_size):
            self._insert_strategy.execute(
                connection=connection,
                stmt=stmt,
                records=records[start : start + self._chunk_size],
            )
            if self._commit_every_n_chunks is not None:
                self._chunks_since_commit += 1
                if self._chunks_since_commit >= self._commit_every_n_chunks:
                    connection.commit()
                    self._chunks_since_commit = 0


# ---------------------------------------------------------------------------
# DeleteBatchExecutor (sin cambios)
# ---------------------------------------------------------------------------


class DeleteBatchExecutor:
    """Template Method para ejecutar DELETE por lotes."""

    def __init__(
        self,
        *,
        engine: Engine,
        chunk_size: int,
        resolver: DeleteStrategyResolver | None = None,
    ) -> None:
        self._engine: Engine = engine
        self._chunk_size: int = chunk_size
        self._resolver: DeleteStrategyResolver = resolver or DeleteStrategyResolver()

    def execute(self, *, table: Table, df: pd.DataFrame, pk_cols: Sequence[str]) -> None:
        """Ejecuta DELETE por lotes usando la estrategia resuelta por dialecto."""
        strategy: DeleteExecutionStrategyProtocol = self._resolver.resolve(self._engine.dialect.name)
        with self._engine.begin() as connection:
            for batch_df in self._iter_batches(df=df, pk_cols=pk_cols):
                self._execute_batch(
                    strategy=strategy, connection=connection, table=table, batch_df=batch_df, pk_cols=pk_cols
                )

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
        strategy.execute(connection=connection, table=table, batch_df=batch_df, pk_cols=pk_cols)


__all__: list[str] = [
    "BatchStatementExecutor",
    "DefaultInsertStrategy",
    "DeleteBatchExecutor",
    "DeleteExecutionStrategyProtocol",
    "DeleteStrategyResolver",
    "GenericDeleteStrategy",
    "InsertExecutionStrategyProtocol",
    "InsertStrategyResolver",
    "MySQLMultiRowInsertStrategy",
    "PostgresCopyStrategy",
    "PostgreSQLExecuteValuesStrategy",
    "SqlBasedDeleteStrategy",
]
