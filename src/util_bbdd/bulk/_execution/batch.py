"""Ejecutores OO para operaciones batch internas de bulk_crud."""

from __future__ import annotations

import contextlib
import decimal
import logging
import operator
import uuid

from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any, Protocol

import pandas as pd

from sqlalchemy import (
    Column,
    Delete,
    Engine,
    Insert,
    MetaData,
    Table,
    and_,
    any_,
    bindparam,
    delete,
    insert,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.exc import DBAPIError, StatementError

from .._support.sql_helpers import json_passthrough_binds

# ---------------------------------------------------------------------------
# FA — fast_executemany para SQL Server / pyodbc
# ---------------------------------------------------------------------------

_log = logging.getLogger(__name__)

# Errores de MySQL/MariaDB por falta de privilegio al crear la tabla temporal del UPDATE por staging:
# 1044 (acceso denegado a la base de datos), 1142 (comando denegado en la tabla), 1227 (privilegio necesario).
_MYSQL_PRIVILEGE_DENIED_ERRNOS: frozenset[int] = frozenset({1044, 1142, 1227})

_DEFAULT_SQL_BASED_DELETE_DIALECTS: frozenset[str] = frozenset({"mysql", "mariadb", "mssql", "hsqldb"})
# SQL Server admite 2100 parámetros por petición (SQLAlchemy usa 2099 en insertmanyvalues); se deja margen.
_MSSQL_MAX_DELETE_PARAMS: int = 2000
# MySQL/MariaDB: máximo de parámetros de una sentencia preparada (P-13; lo aplica el conector ``mariadb``, que prepara
# en el servidor; PyMySQL sustituye en el cliente y no tiene límite, pero trocear no le afecta).
_MYSQL_MAX_STATEMENT_PARAMS: int = 65_535
# Parámetros máximos por sentencia ``DELETE ... IN (...)`` por dialecto; sin entrada, una sentencia por lote.
_MAX_DELETE_PARAMS: dict[str, int] = {
    "mssql": _MSSQL_MAX_DELETE_PARAMS,
    "mysql": _MYSQL_MAX_STATEMENT_PARAMS,
    "mariadb": _MYSQL_MAX_STATEMENT_PARAMS,
}


def validate_chunk_size(chunk_size: Any) -> int:
    """Devuelve ``chunk_size`` como ``int`` si es un entero ≥ 1; si no, ``ValueError``.

    Sin esta validación, un ``chunk_size`` negativo no generaba ningún lote (``range`` vacío): la carga no escribía nada,
    sin error, y la auditoría registraba las filas como procesadas. Con 0, fallaba al ejecutar con
    ``range() arg 3 must not be zero``. Acepta enteros de numpy; rechaza ``bool`` y decimales.
    """
    if isinstance(chunk_size, bool):
        raise ValueError(f"chunk_size debe ser un entero ≥ 1, recibido: {chunk_size!r}")
    try:
        value = operator.index(chunk_size)
    except TypeError:
        raise ValueError(f"chunk_size debe ser un entero ≥ 1, recibido: {chunk_size!r}") from None
    if value < 1:
        raise ValueError(f"chunk_size debe ser un entero ≥ 1, recibido: {chunk_size!r}")
    return value


def _register_fast_executemany(engine: Engine) -> None:
    """Activa fast_executemany en el dialecto mssql+pyodbc igual que ``create_engine(..., fast_executemany=True)``.

    P-18/P-01 (performance-audit de bulk, 2026-09-23): activar ``cursor.fast_executemany`` con un listener, a espaldas
    del dialecto, rompía el UPDATE con columnas DATETIME (``HY104 Invalid precision value``), porque SQLAlchemy solo
    omite ``cursor.setinputsizes()`` en los executemany cuando ``dialect.fast_executemany`` es True. Además, con
    insertmanyvalues activo el INSERT nunca llegaba a ``executemany``. Se fijan los mismos dos atributos que
    ``MSDialect_pyodbc.__init__`` fija con ``fast_executemany=True``; afecta a todo el engine, como el listener.

    Omite engines que no son un Engine SQLAlchemy real (p.ej. MagicMock en tests) y dialectos sin
    ``fast_executemany`` (cualquiera distinto de mssql+pyodbc). Idempotente.
    """
    if not isinstance(engine, Engine):
        return
    dialect: Any = engine.dialect
    if not hasattr(dialect, "fast_executemany"):
        return
    dialect.fast_executemany = True
    dialect.use_insertmanyvalues_wo_returning = False


# ---------------------------------------------------------------------------
# FB — Estrategias INSERT (execute_values para PostgreSQL/psycopg2)
# ---------------------------------------------------------------------------


# Precisión máxima de DECIMAL/NUMERIC en SQL Server.
_MSSQL_MAX_DECIMAL_PRECISION = 38


def _driver_decimal_context(engine: Engine) -> contextlib.AbstractContextManager[Any]:
    """Contexto ``decimal`` para la llamada al driver: en SQL Server con ``fast_executemany``, precisión ≥ 38.

    PD-10 (performance-audit de dump 2026-09-26): con ``fast_executemany`` pyodbc convierte cada ``Decimal`` al
    ``NUMERIC`` del parámetro con el contexto ``decimal`` del hilo, de 28 dígitos por defecto. Un DECIMAL de más de 28
    dígitos significativos se redondeaba sin avisar (o fallaba con el error 8023 si el redondeo desbordaba). Se mira el
    dialecto al ejecutar: ``fast_executemany`` es de todo el engine y puede activarlo otra instancia o el usuario.
    """
    if engine.dialect.name != "mssql" or not getattr(engine.dialect, "fast_executemany", False):
        return contextlib.nullcontext()
    context = decimal.getcontext().copy()
    context.prec = max(context.prec, _MSSQL_MAX_DECIMAL_PRECISION)
    return decimal.localcontext(context)


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


def _begin_if_needed(connection: Any) -> None:
    """Inicia la transacción de SQLAlchemy antes de escribir por el cursor del driver (P-27).

    SQLAlchemy no ve lo que se ejecuta por ``connection.connection.cursor()``: en modo commit-as-you-go
    (``engine.connect()``, usado con ``commit_every_n_chunks``) no habría transacción iniciada, ``commit()`` no haría
    nada y las filas se desharían al devolver la conexión al pool.
    """
    if not connection.in_transaction():
        connection.begin()


def _wrap_driver_error(connection: Any, statement: str, exc: Exception) -> StatementError:
    """Error del driver como ``DBAPIError`` de SQLAlchemy (``IntegrityError``, ``OperationalError``…) (P-28).

    Lo que se ejecuta por el cursor del driver no pasa por SQLAlchemy, que es quien envuelve sus errores; sin esto
    llegarían sin envolver a quien captura ``SQLAlchemyError`` (``ParallelBulkLoader``, ``dump``). Los parámetros no se
    incluyen (pueden ser miles de filas). Si el error es una desconexión, se invalida la conexión como haría SQLAlchemy.
    """
    dialect = connection.dialect
    invalidated: bool = dialect.is_disconnect(exc, connection.connection.dbapi_connection, None)
    if invalidated:
        connection.invalidate(exc)
    return DBAPIError.instance(
        statement, None, exc, dialect.loaded_dbapi.Error, connection_invalidated=invalidated, dialect=dialect
    )


class PostgreSQLExecuteValuesStrategy:
    """INSERT para PostgreSQL/psycopg2 vía execute_values.

    Genera un único ``INSERT INTO t (...) VALUES (%s,...), (%s,...), ...`` por
    batch en lugar de N sentencias individuales: 1 round-trip por chunk en vez
    de N, con ganancia típica de 3–5× respecto a executemany.

    Solo aplica al driver legacy ``psycopg2``. Para ``psycopg`` (psycopg3, el
    driver por defecto de la librería) se usa :class:`PostgresCopyStrategy`.

    Fallback a :class:`DefaultInsertStrategy` cuando:
    - ``stmt`` no es un ``Insert`` (p.ej. ``Update`` en ``bulk_update_from_df``, o
      ``TextClause`` en la ruta ``override_identity``).
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
        if not isinstance(stmt, Insert):
            # Update/Delete/TextClause (OVERRIDING SYSTEM VALUE) u otro stmt que no sea
            # un INSERT real → fallback (p.ej. Update también expone .table).
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
        _begin_if_needed(connection)
        try:
            with connection.connection.cursor() as raw_cursor:
                _pg_execute_values(raw_cursor, sql, data, page_size=len(data))
        except connection.dialect.loaded_dbapi.Error as exc:
            raise _wrap_driver_error(connection, sql, exc) from exc


class PostgresCopyStrategy:
    """INSERT para PostgreSQL/psycopg3 vía ``COPY ... FROM STDIN`` (``cursor.copy()``).

    Es la vía nativa más rápida de PostgreSQL: ``COPY`` salta el parseo SQL por
    fila y transmite los datos por STDIN (sin staging a disco), con ganancias de
    1 orden de magnitud sobre ``executemany`` en cargas de gran volumen.

    psycopg3 adapta automáticamente cada valor Python (``int``, ``float``, ``str``,
    ``datetime``, ``bytes``, ``None`` → NULL, JSON como texto) al formato COPY, por
    lo que se reutilizan los registros ya normalizados por ``normalize_records_for_sql``.

    Fallback a ejecución estándar (``connection.execute``) cuando ``stmt`` no es un
    ``Insert`` (p.ej. ``Update`` en ``bulk_update_from_df``, o ``TextClause`` en la
    ruta ``override_identity`` / ``OVERRIDING SYSTEM VALUE``), que no es expresable
    con COPY.
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
        if not isinstance(stmt, Insert):
            # Update/Delete/TextClause (OVERRIDING SYSTEM VALUE) u otro stmt que no sea
            # un INSERT real → fallback (p.ej. Update también expone .table).
            connection.execute(stmt, list(records))
            return

        table = stmt.table
        cols: list[str] = list(records[0].keys())
        preparer = connection.dialect.identifier_preparer
        quoted_table: str = preparer.format_table(table)
        quoted_cols: str = ", ".join(preparer.quote(c) for c in cols)
        sql: str = f"COPY {quoted_table} ({quoted_cols}) FROM STDIN"
        _begin_if_needed(connection)
        raw_cursor = connection.connection.cursor()
        try:
            with raw_cursor.copy(sql) as copy:
                for record in records:
                    copy.write_row([record[c] for c in cols])
        except connection.dialect.loaded_dbapi.Error as exc:
            raise _wrap_driver_error(connection, sql, exc) from exc
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

    **Optimización**: Cachea templates SQL por (número de filas, tabla, columnas) para evitar
    reconstrucción en sub-lotes del mismo tamaño (típicamente todos excepto el último).

    Fallback a ejecución estándar cuando ``stmt`` no es un ``Insert`` (p.ej. ``Update``
    en ``bulk_update_from_df``, o ``TextClause`` en la ruta ``override_identity``).
    """

    def __init__(self, *, max_rows_per_statement: int = 1000) -> None:
        if max_rows_per_statement < 1:
            raise ValueError(f"max_rows_per_statement debe ser ≥ 1, recibido: {max_rows_per_statement}")
        self._max_rows: int = max_rows_per_statement
        # Caché: (num_rows, quoted_table, cols_tuple) → (template_sql_string, placeholder_pattern). La tabla forma parte
        # de la clave (P-22): sin ella, dos tablas con las mismas columnas compartían plantilla y las filas de la segunda
        # se insertaban en la primera.
        self._sql_template_cache: dict[tuple[int, str, tuple[str, ...]], tuple[str, str]] = {}

    def get_min_max_allowed_packet(self, avg_row_bytes: int = 2000) -> int:
        """Calcula el `max_allowed_packet` mínimo recomendado para esta estrategia.

        Estima el tamaño máximo de una sentencia INSERT multi-fila basado en:
        - Número máximo de filas por statement (max_rows_per_statement)
        - Bytes promedio por fila (datos + overhead SQL parametrizado)
        - Buffer de seguridad (50% extra para overhead de binding)

        Args:
            avg_row_bytes: Estimación de bytes promedio por fila en la sentencia SQL.
                          Default 2000 bytes (típico para columnas normales).

        Returns:
            Tamaño mínimo recomendado en bytes.
            Típicamente 64 MB (67108864) para max_rows_per_statement=1000.

        Examples:
            >>> strategy = MySQLMultiRowInsertStrategy(max_rows_per_statement=1000)
            >>> min_packet = strategy.get_min_max_allowed_packet()
            >>> print(min_packet)
            67108864  # 64 MB
        """
        # Estimación: max_rows × avg_row_bytes × 1.5 (overhead SQL + binding + parsing)
        estimated_size: int = int(self._max_rows * avg_row_bytes * 1.5)

        # Redondear a potencia de 2 más cercana (recomendación práctica)
        # Mínimo 32 MB, máximo 256 MB
        # Usar recomendación de 64 MB como estándar para bulk operations
        if estimated_size <= 16 * 1_048_576:
            return 64 * 1_048_576  # 64 MB (standard para bulk)
        elif estimated_size <= 64 * 1_048_576:
            return 64 * 1_048_576  # 64 MB
        elif estimated_size <= 128 * 1_048_576:
            return 128 * 1_048_576  # 128 MB
        else:
            return 256 * 1_048_576  # 256 MB (máximo seguro)

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
        cache_key: tuple[int, str, tuple[str, ...]] = (num_rows, quoted_table, cols_tuple)

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
        if not isinstance(stmt, Insert):
            # Update/Delete/TextClause u otro stmt que no sea un INSERT real → fallback
            # (p.ej. Update también expone .table, y sus columnas no coinciden con las
            # del registro: incluyen alias de bindparam como "pk_<col>" para el WHERE).
            connection.execute(stmt, list(records))
            return

        table = stmt.table
        cols: list[str] = list(records[0].keys())
        preparer = connection.dialect.identifier_preparer
        quoted_table: str = preparer.format_table(table)
        quoted_cols: str = ", ".join(preparer.quote(c) for c in cols)

        # P-13: con el conector ``mariadb`` la sentencia es preparada y admite como máximo 65.535 parámetros
        # (1000 filas fallaban a partir de 66 columnas).
        rows_per_statement: int = max(1, min(self._max_rows, _MYSQL_MAX_STATEMENT_PARAMS // len(cols)))
        for start in range(0, len(records), rows_per_statement):
            sub_batch: Sequence[Mapping[str, Any]] = records[start : start + rows_per_statement]
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


class MySQLDriverExecutemanyStrategy:
    """INSERT para MySQL/MariaDB con el ``executemany`` nativo de PyMySQL (``exec_driver_sql``).

    PyMySQL reescribe ``executemany`` de un INSERT como sentencias multi-fila en el cliente, troceadas por debajo de
    ``max_allowed_packet``. P-02 (performance-audit de bulk, 2026-09-23): unas 2× más rápido que
    :class:`MySQLMultiRowInsertStrategy` en MySQL 8.4 y MariaDB 11.4, cuyo coste dominante era construir ``text()`` con
    miles de parámetros en Python.

    Solo se resuelve para PyMySQL. El conector ``mariadb`` (``mariadbconnector``) hace un envío masivo que exige el
    mismo tipo Python por columna en todas las filas, y ``normalize_sql_literal`` puede mezclarlos (``bytes`` y
    ``str`` en un BLOB, ``Decimal`` y ``float``): con él se mantiene la vía multi-fila.

    Los valores llegan al driver sin procesadores de tipo de SQLAlchemy, igual que en la vía multi-fila con
    ``text()``. Con ``insert(tabla)`` el tipo ``JSON`` reflejado en MySQL volvería a serializar el texto que ya produce
    ``normalize_sql_literal`` y guardaría ``None`` como el literal JSON ``null``.

    Fallback a ejecución estándar cuando ``stmt`` no es un ``Insert`` (p.ej. ``Update`` en ``bulk_update_from_df``, o
    ``TextClause`` en la ruta ``override_identity``).
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
        if not isinstance(stmt, Insert):
            connection.execute(stmt, list(records))
            return

        cols: list[str] = list(records[0].keys())
        dialect = connection.dialect
        preparer = dialect.identifier_preparer
        quoted_table: str = preparer.format_table(stmt.table)
        quoted_cols: str = ", ".join(preparer.quote(c) for c in cols)
        # Con paramstyle format/pyformat, identifier_preparer ya duplica los '%' de los identificadores.
        placeholder: str = "?" if dialect.paramstyle == "qmark" else "%s"
        sql: str = f"INSERT INTO {quoted_table} ({quoted_cols}) VALUES ({', '.join([placeholder] * len(cols))})"
        connection.exec_driver_sql(sql, [tuple(record[c] for c in cols) for record in records])


class InsertStrategyResolver:
    """Resuelve la estrategia INSERT óptima según dialecto y driver.

    Mapa de resolución:

    - ``postgresql`` + ``psycopg2`` → :class:`PostgreSQLExecuteValuesStrategy`.
    - ``postgresql`` + ``psycopg`` (psycopg3, driver por defecto) → :class:`PostgresCopyStrategy`.
    - ``mysql`` / ``mariadb`` + ``pymysql`` → :class:`MySQLDriverExecutemanyStrategy`.
    - ``mysql`` / ``mariadb`` con otro driver (p.ej. ``mariadbconnector``) → :class:`MySQLMultiRowInsertStrategy`.
    - ``mysql_strategy`` explícito → se usa para mysql/mariadb con cualquier driver.
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
        self._mysql_strategy: InsertExecutionStrategyProtocol | None = mysql_strategy
        self._mysql_pymysql_strategy: InsertExecutionStrategyProtocol = MySQLDriverExecutemanyStrategy()
        self._mysql_multirow_strategy: InsertExecutionStrategyProtocol = MySQLMultiRowInsertStrategy()
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
            if self._mysql_strategy is not None:
                return self._mysql_strategy
            if "pymysql" in drivername:
                return self._mysql_pymysql_strategy
            return self._mysql_multirow_strategy
        return self._default_strategy


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

        staging = Table(
            f"tmp_bulkupd_{uuid.uuid4().hex[:12]}",
            MetaData(),
            *(Column(c, self._table.c[c].type) for c in cols),
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
    """Estrategia de DELETE SQL parametrizado para motores soportados.

    SQL Server (P-05, performance-audit de bulk 2026-09-23): admite como máximo 2100 parámetros por petición y no
    admite constructores de fila en ``IN``. La PK simple se trocea en sentencias de ``_MSSQL_MAX_DELETE_PARAMS``
    parámetros como máximo y la PK compuesta se delega en :class:`GenericDeleteStrategy`
    (``DELETE ... WHERE a = ? AND b = ?`` con executemany).

    MySQL/MariaDB (P-13): el conector ``mariadb`` admite como máximo 65.535 parámetros por sentencia; el lote se trocea
    en sentencias de ``65535 // columnas de la PK`` filas. El resto de dialectos usa una sentencia por lote.
    """

    def execute(
        self,
        *,
        connection: Any,
        table: Table,
        batch_df: pd.DataFrame,
        pk_cols: Sequence[str],
    ) -> None:
        dialect_name: str = connection.dialect.name
        if dialect_name == "mssql" and len(pk_cols) > 1:
            GenericDeleteStrategy().execute(connection=connection, table=table, batch_df=batch_df, pk_cols=pk_cols)
            return
        max_params: int | None = _MAX_DELETE_PARAMS.get(dialect_name)
        if max_params is None:
            self._execute_statement(connection=connection, table=table, batch_df=batch_df, pk_cols=pk_cols)
            return
        rows_per_statement: int = max(1, max_params // len(pk_cols))
        for start in range(0, len(batch_df), rows_per_statement):
            self._execute_statement(
                connection=connection,
                table=table,
                batch_df=batch_df.iloc[start : start + rows_per_statement],
                pk_cols=pk_cols,
            )

    def _execute_statement(
        self,
        *,
        connection: Any,
        table: Table,
        batch_df: pd.DataFrame,
        pk_cols: Sequence[str],
    ) -> None:
        """Ejecuta un único ``DELETE ... WHERE pk IN (...)`` con todas las filas de ``batch_df``."""
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


class PostgreSQLAnyDeleteStrategy:
    """DELETE para PostgreSQL con una sentencia por lote (P-10, performance-audit de bulk 2026-09-23).

    Un parámetro array por columna de la PK, sea cual sea el tamaño del lote:

    - PK simple: ``DELETE FROM t WHERE pk = ANY(:ids)``.
    - PK compuesta: ``DELETE FROM t AS tgt USING unnest(CAST(:k0 AS tipo[]), ...) AS k(a, b) WHERE tgt.a = k.a AND ...``.
      No se usa ``(a, b) IN ((..), ..)``: PostgreSQL lo resuelve mucho peor (100K filas en 35–47 s).

    Antes era un ``executemany`` de una sentencia por fila. 100K filas (mediana de 3, PostgreSQL 17 en local):
    PK simple 2,8 s → 1,0 s con psycopg 3 y 26,8 s → 1,0 s con psycopg2; PK compuesta 2,8 s → 1,2 s y 28,8 s → 1,2 s.
    """

    def execute(
        self,
        *,
        connection: Any,
        table: Table,
        batch_df: pd.DataFrame,
        pk_cols: Sequence[str],
    ) -> None:
        if len(pk_cols) == 1:
            column = table.c[pk_cols[0]]
            stmt: Any = delete(table).where(column == any_(bindparam("pk_ids", type_=ARRAY(column.type))))
            connection.execute(stmt, {"pk_ids": batch_df[pk_cols[0]].tolist()})
            return

        dialect = connection.dialect
        preparer = dialect.identifier_preparer
        quoted: list[str] = [preparer.quote(column) for column in pk_cols]
        arrays: str = ", ".join(
            f"CAST(:pk_{i} AS {table.c[column].type.compile(dialect=dialect)}[])" for i, column in enumerate(pk_cols)
        )
        condition: str = " AND ".join(f"_bulk_del_t.{q} = _bulk_del_k.{q}" for q in quoted)
        sql: str = (
            f"DELETE FROM {preparer.format_table(table)} AS _bulk_del_t "
            f"USING unnest({arrays}) AS _bulk_del_k({', '.join(quoted)}) WHERE {condition}"
        )
        stmt = text(sql).bindparams(
            *(bindparam(f"pk_{i}", type_=ARRAY(table.c[column].type)) for i, column in enumerate(pk_cols))
        )
        connection.execute(stmt, {f"pk_{i}": batch_df[column].tolist() for i, column in enumerate(pk_cols)})


class DeleteStrategyResolver:
    """Resuelve estrategia DELETE según dialecto."""

    def __init__(
        self,
        *,
        sql_based_dialects: frozenset[str] | None = None,
        sql_based_strategy: DeleteExecutionStrategyProtocol | None = None,
        generic_strategy: DeleteExecutionStrategyProtocol | None = None,
        postgresql_strategy: DeleteExecutionStrategyProtocol | None = None,
    ) -> None:
        self._sql_based_dialects: frozenset[str] = sql_based_dialects or _DEFAULT_SQL_BASED_DELETE_DIALECTS
        self._sql_based_strategy: DeleteExecutionStrategyProtocol = sql_based_strategy or SqlBasedDeleteStrategy()
        self._generic_strategy: DeleteExecutionStrategyProtocol = generic_strategy or GenericDeleteStrategy()
        self._postgresql_strategy: DeleteExecutionStrategyProtocol = (
            postgresql_strategy or PostgreSQLAnyDeleteStrategy()
        )

    def resolve(self, dialect_name: str) -> DeleteExecutionStrategyProtocol:
        """Devuelve la estrategia adecuada para el dialecto indicado."""
        if dialect_name in self._sql_based_dialects:
            return self._sql_based_strategy
        if dialect_name == "postgresql":
            return self._postgresql_strategy
        return self._generic_strategy


# ---------------------------------------------------------------------------
# BatchStatementExecutor — INSERT con estrategia por motor
# ---------------------------------------------------------------------------


def _commit_periodico(connection: Any, commit_hook: Callable[[Any], None] | None) -> None:
    """Commit periódico de ``commit_every_n_chunks``.

    Dentro de ``BulkCrud.bulk_session`` pasa por ``commit_hook``, que además vuelca al CSV la auditoría de las
    operaciones que ese commit confirma (M-1, audit-code de AuditManager 2026-09-25).
    """
    if commit_hook is not None:
        commit_hook(connection)
    else:
        connection.commit()


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
        self._chunk_size: int = validate_chunk_size(chunk_size)
        self._active_connection: Any | None = None
        # Gancho de commit que inyecta ``BulkCrud.bulk_session()`` junto con ``_active_connection``.
        self._commit_hook: Callable[[Any], None] | None = None
        self._commit_every_n_chunks: int | None = commit_every_n_chunks
        self._chunks_since_commit: int = 0
        # BLK-08 (AUDIT_CODE 2026-09-22): filas durablemente comprometidas (ya vía
        # commit periódico, ya vía el commit final) frente a las ejecutadas pero
        # aún no commiteadas — permite reportar cuántas filas sobreviven si una
        # carga falla a mitad de sesión con commit_every_n_chunks activo.
        self.rows_committed: int = 0
        self._rows_pending_commit: int = 0
        drivername: str = str(engine.url.drivername).lower()
        self._insert_strategy: InsertExecutionStrategyProtocol = (insert_resolver or InsertStrategyResolver()).resolve(
            engine.dialect.name, drivername
        )
        if enable_fast_executemany and engine.dialect.name == "mssql" and "pyodbc" in drivername:
            _register_fast_executemany(engine)

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
    ) -> None:
        """Ejecuta un statement SQLAlchemy por batches.

        ``strategy`` sustituye a la estrategia INSERT resuelta para este motor (p.ej.
        :class:`MySQLStagingUpdateStrategy` en el UPDATE por staging); ``None`` usa la resuelta.

        Si ``_active_connection`` está activo (inyectado via ``BulkCrud.bulk_session()``),
        reutiliza esa conexión en lugar de abrir una nueva transacción por lote.

        Cuando ``commit_every_n_chunks`` está configurado y no hay conexión activa,
        usa ``engine.connect()`` (commit-as-you-go) en lugar de ``engine.begin()``
        para poder commitear lotes intermedios, y hace un commit final del resto.
        """
        if self._active_connection is not None:
            self._execute_on_connection(self._active_connection, records, stmt, strategy)
        elif self._commit_every_n_chunks is not None:
            self._chunks_since_commit = 0
            with self._engine.connect() as connection:
                self._execute_on_connection(connection, records, stmt, strategy)
                connection.commit()
                self._chunks_since_commit = 0
                self.rows_committed += self._rows_pending_commit
                self._rows_pending_commit = 0
        else:
            with self._engine.begin() as connection:
                self._execute_on_connection(connection, records, stmt, strategy)

    def _execute_on_connection(
        self,
        connection: Any,
        records: Sequence[Mapping[str, Any]],
        stmt: Any,
        strategy: InsertExecutionStrategyProtocol | None = None,
    ) -> None:
        """Ejecuta los batches sobre una conexión ya abierta.

        Si ``commit_every_n_chunks`` está activo, commitea sobre ``connection``
        (que debe estar en modo commit-as-you-go) cada N lotes. El commit del
        resto (tail) es responsabilidad del llamador (``execute`` / ``bulk_session``).
        """
        for start in range(0, len(records), self._chunk_size):
            batch: Sequence[Mapping[str, Any]] = records[start : start + self._chunk_size]
            with _driver_decimal_context(self._engine):
                (strategy or self._insert_strategy).execute(
                    connection=connection,
                    stmt=stmt,
                    records=batch,
                )
            if self._commit_every_n_chunks is not None:
                self._rows_pending_commit += len(batch)
                self._chunks_since_commit += 1
                if self._chunks_since_commit >= self._commit_every_n_chunks:
                    _commit_periodico(connection, self._commit_hook)
                    self._chunks_since_commit = 0
                    self.rows_committed += self._rows_pending_commit
                    self._rows_pending_commit = 0


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
        commit_every_n_chunks: int | None = None,
    ) -> None:
        self._engine: Engine = engine
        self._chunk_size: int = validate_chunk_size(chunk_size)
        self._resolver: DeleteStrategyResolver = resolver or DeleteStrategyResolver()
        # Conexión de ``BulkCrud.bulk_session()`` (P-26): el DELETE participa en la transacción de la sesión.
        self._active_connection: Any | None = None
        self._commit_hook: Callable[[Any], None] | None = None
        self._commit_every_n_chunks: int | None = commit_every_n_chunks

    def execute(self, *, table: Table, df: pd.DataFrame, pk_cols: Sequence[str]) -> None:
        """Ejecuta DELETE por lotes usando la estrategia resuelta por dialecto.

        Dentro de ``BulkCrud.bulk_session()`` usa la conexión de la sesión; fuera, una transacción propia. Con
        ``commit_every_n_chunks`` confirma cada N lotes, como INSERT y UPDATE (auditoría de bulk 2026-09-24,
        hallazgo 7: fuera de la sesión todo el DELETE iba en una sola transacción); si falla, quedan borrados los lotes
        ya confirmados.
        """
        if self._active_connection is not None:
            self._execute_on_connection(self._active_connection, table=table, df=df, pk_cols=pk_cols)
            return
        if self._commit_every_n_chunks is not None:
            with self._engine.connect() as connection:
                self._execute_on_connection(connection, table=table, df=df, pk_cols=pk_cols)
                connection.commit()
            return
        with self._engine.begin() as connection:
            self._execute_on_connection(connection, table=table, df=df, pk_cols=pk_cols)

    def _execute_on_connection(
        self, connection: Any, *, table: Table, df: pd.DataFrame, pk_cols: Sequence[str]
    ) -> None:
        strategy: DeleteExecutionStrategyProtocol = self._resolver.resolve(self._engine.dialect.name)
        batches_since_commit = 0
        for batch_df in self._iter_batches(df=df, pk_cols=pk_cols):
            self._execute_batch(
                strategy=strategy, connection=connection, table=table, batch_df=batch_df, pk_cols=pk_cols
            )
            if self._commit_every_n_chunks is not None:
                batches_since_commit += 1
                if batches_since_commit >= self._commit_every_n_chunks:
                    _commit_periodico(connection, self._commit_hook)
                    batches_since_commit = 0

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


__all__: list[str] = [
    "BatchStatementExecutor",
    "DefaultInsertStrategy",
    "DeleteBatchExecutor",
    "DeleteExecutionStrategyProtocol",
    "DeleteStrategyResolver",
    "GenericDeleteStrategy",
    "InsertExecutionStrategyProtocol",
    "InsertStrategyResolver",
    "MySQLDriverExecutemanyStrategy",
    "MySQLMultiRowInsertStrategy",
    "MySQLStagingUpdateStrategy",
    "PostgresCopyStrategy",
    "PostgreSQLAnyDeleteStrategy",
    "PostgreSQLExecuteValuesStrategy",
    "SqlBasedDeleteStrategy",
    "validate_chunk_size",
]
