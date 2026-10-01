"""Estrategias INSERT por motor y driver, y su resolución (``InsertStrategyResolver``).

Separado de ``batch`` (R10b del refactor de reutilización 2026-09-26) sin cambios de comportamiento.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, ClassVar, Protocol

from sqlalchemy import (
    Insert,
    text,
)

from .._support.dialect import MYSQL_FAMILY
from .._support.sql_helpers import SqlColumns
from ._driver_quirks import _MYSQL_MAX_STATEMENT_PARAMS, _begin_if_needed, _wrap_driver_error


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


class _RawInsertStrategy:
    """Base de las estrategias INSERT que escriben por el driver o con SQL propio (Template Method).

    ``execute`` resuelve lo común: lote vacío, *fallback* a ``connection.execute(stmt, records)`` cuando ``stmt`` no es
    un ``Insert`` (``Update`` en ``bulk_update_from_df``, cuyos registros llevan además alias ``pk_<col>`` para el WHERE,
    o ``TextClause`` en la ruta ``override_identity``) y las columnas citadas. Cada subclase implementa :meth:`_insert` o,
    si envía tuplas al driver, :meth:`_insert_rows` (y entonces admite bloques por columnas, ``supports_columns``).
    """

    #: ``True`` si la estrategia admite :meth:`execute_columns` (implementa :meth:`_insert_rows`).
    supports_columns: ClassVar[bool] = False

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
        preparer = connection.dialect.identifier_preparer
        self._insert(
            connection=connection,
            stmt=stmt,
            records=records,
            cols=cols,
            quoted_table=preparer.format_table(stmt.table),
            quoted_cols=", ".join(preparer.quote(c) for c in cols),
        )

    def execute_columns(self, *, connection: Any, stmt: Insert, block: SqlColumns) -> None:
        """Inserta un bloque por columnas: las tuplas salen de ``zip(*columnas)``, sin un ``dict`` por fila (B-03)."""
        if not len(block):
            return
        cols: list[str] = list(block.keys())
        columns: list[list[Any]] = [block.column(c) or [] for c in cols]
        preparer = connection.dialect.identifier_preparer
        self._insert_rows(
            connection=connection,
            rows=list(zip(*columns, strict=True)),
            quoted_table=preparer.format_table(stmt.table),
            quoted_cols=", ".join(preparer.quote(c) for c in cols),
        )

    def _insert(
        self,
        *,
        connection: Any,
        stmt: Insert,
        records: Sequence[Mapping[str, Any]],
        cols: list[str],
        quoted_table: str,
        quoted_cols: str,
    ) -> None:
        """Inserta ``records`` (no vacío) en la tabla de ``stmt``. Por defecto, como tuplas con :meth:`_insert_rows`."""
        self._insert_rows(
            connection=connection,
            rows=[tuple(r[c] for c in cols) for r in records],
            quoted_table=quoted_table,
            quoted_cols=quoted_cols,
        )

    def _insert_rows(
        self, *, connection: Any, rows: list[tuple[Any, ...]], quoted_table: str, quoted_cols: str
    ) -> None:
        """Inserta ``rows`` (tuplas en el orden de ``quoted_cols``; no vacío) en ``quoted_table``."""
        raise NotImplementedError


class PostgreSQLExecuteValuesStrategy(_RawInsertStrategy):
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

    supports_columns: ClassVar[bool] = True

    def _insert(
        self,
        *,
        connection: Any,
        stmt: Insert,
        records: Sequence[Mapping[str, Any]],
        cols: list[str],
        quoted_table: str,
        quoted_cols: str,
    ) -> None:
        try:
            import psycopg2.extras  # type: ignore[import-untyped]  # noqa: F401
        except ImportError:
            connection.execute(stmt, list(records))
            return
        super()._insert(
            connection=connection,
            stmt=stmt,
            records=records,
            cols=cols,
            quoted_table=quoted_table,
            quoted_cols=quoted_cols,
        )

    def _insert_rows(
        self, *, connection: Any, rows: list[tuple[Any, ...]], quoted_table: str, quoted_cols: str
    ) -> None:
        from psycopg2.extras import execute_values as _pg_execute_values

        sql: str = f"INSERT INTO {quoted_table} ({quoted_cols}) VALUES %s"
        _begin_if_needed(connection)
        try:
            with connection.connection.cursor() as raw_cursor:
                _pg_execute_values(raw_cursor, sql, rows, page_size=len(rows))
        except connection.dialect.loaded_dbapi.Error as exc:
            raise _wrap_driver_error(connection, sql, exc) from exc


class PostgresCopyStrategy(_RawInsertStrategy):
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

    supports_columns: ClassVar[bool] = True

    def _insert_rows(
        self, *, connection: Any, rows: list[tuple[Any, ...]], quoted_table: str, quoted_cols: str
    ) -> None:
        sql: str = f"COPY {quoted_table} ({quoted_cols}) FROM STDIN"
        _begin_if_needed(connection)
        raw_cursor = connection.connection.cursor()
        try:
            with raw_cursor.copy(sql) as copy:
                for row in rows:
                    copy.write_row(row)
        except connection.dialect.loaded_dbapi.Error as exc:
            raise _wrap_driver_error(connection, sql, exc) from exc
        finally:
            raw_cursor.close()


class MySQLMultiRowInsertStrategy(_RawInsertStrategy):
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

    def _insert(
        self,
        *,
        connection: Any,
        stmt: Insert,
        records: Sequence[Mapping[str, Any]],
        cols: list[str],
        quoted_table: str,
        quoted_cols: str,
    ) -> None:
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


class MySQLDriverExecutemanyStrategy(_RawInsertStrategy):
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

    supports_columns: ClassVar[bool] = True

    def _insert_rows(
        self, *, connection: Any, rows: list[tuple[Any, ...]], quoted_table: str, quoted_cols: str
    ) -> None:
        dialect = connection.dialect
        # Con paramstyle format/pyformat, identifier_preparer ya duplica los '%' de los identificadores.
        placeholder: str = "?" if dialect.paramstyle == "qmark" else "%s"
        sql: str = f"INSERT INTO {quoted_table} ({quoted_cols}) VALUES ({', '.join([placeholder] * len(rows[0]))})"
        connection.exec_driver_sql(sql, rows)


class MariaDBConnectorInsertStrategy:
    """INSERT para MySQL/MariaDB con MariaDB Connector/Python (``mariadbconnector``).

    PF-09 (performance-audit de dump 2026-09-26): con este conector se usaba siempre :class:`MySQLMultiRowInsertStrategy`,
    unas 3,7 veces más lenta que el ``executemany`` del driver (envío masivo; 500K filas: 10,5 s frente a 2,8 s). El envío
    masivo exige un tipo Python compatible por columna en todas las filas: con ``bytes`` y ``str`` en un BLOB, ``int`` y
    ``float``, ``datetime`` y ``date`` o ``str`` e ``int`` falla con ``Invalid parameter type``.

    Por eso decide **por lote**: si cada columna tiene un único tipo exacto (sin contar ``None``), usa el ``executemany``
    del driver (:class:`MySQLDriverExecutemanyStrategy`); si no, la vía multi-fila. El criterio es más estricto que el
    del driver (``Decimal`` y ``float``, o ``int`` y ``bool``, van por la vía multi-fila aunque el driver los aceptase).
    """

    def __init__(self) -> None:
        self._driver_strategy = MySQLDriverExecutemanyStrategy()
        self._multirow_strategy = MySQLMultiRowInsertStrategy()

    def execute(
        self,
        *,
        connection: Any,
        stmt: Any,
        records: Sequence[Mapping[str, Any]],
    ) -> None:
        if records and isinstance(stmt, Insert) and _uniform_column_types(records):
            self._driver_strategy.execute(connection=connection, stmt=stmt, records=records)
        else:
            self._multirow_strategy.execute(connection=connection, stmt=stmt, records=records)


def _uniform_column_types(records: Sequence[Mapping[str, Any]]) -> bool:
    """``True`` si cada columna tiene, sin contar ``None``, un único tipo exacto en todas las filas."""
    none_type: type = type(None)
    for column in records[0]:
        kinds = {type(record[column]) for record in records}
        kinds.discard(none_type)
        if len(kinds) > 1:
            return False
    return True


class InsertStrategyResolver:
    """Resuelve la estrategia INSERT óptima según dialecto y driver.

    Mapa de resolución:

    - ``postgresql`` + ``psycopg2`` → :class:`PostgreSQLExecuteValuesStrategy`.
    - ``postgresql`` + ``psycopg`` (psycopg3, driver por defecto) → :class:`PostgresCopyStrategy`.
    - ``mysql`` / ``mariadb`` + ``pymysql`` → :class:`MySQLDriverExecutemanyStrategy`.
    - ``mysql`` / ``mariadb`` + ``mariadbconnector`` → :class:`MariaDBConnectorInsertStrategy` (``executemany`` del
      driver si los tipos del lote son uniformes; si no, multi-fila).
    - ``mysql`` / ``mariadb`` con otro driver → :class:`MySQLMultiRowInsertStrategy`.
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
        self._mariadb_connector_strategy: InsertExecutionStrategyProtocol = MariaDBConnectorInsertStrategy()
        self._default_strategy: InsertExecutionStrategyProtocol = default_strategy or DefaultInsertStrategy()

    def resolve(self, dialect_name: str, drivername: str) -> InsertExecutionStrategyProtocol:
        """Devuelve la estrategia adecuada para el dialecto y driver indicados."""
        if dialect_name == "postgresql":
            # "psycopg2" contiene "psycopg": comprobar el legacy primero.
            if "psycopg2" in drivername:
                return self._pg_execute_values_strategy
            if "psycopg" in drivername:
                return self._pg_copy_strategy
        if dialect_name in MYSQL_FAMILY:
            if self._mysql_strategy is not None:
                return self._mysql_strategy
            if "pymysql" in drivername:
                return self._mysql_pymysql_strategy
            if "mariadbconnector" in drivername:
                return self._mariadb_connector_strategy
            return self._mysql_multirow_strategy
        return self._default_strategy


__all__: list[str] = [
    "DefaultInsertStrategy",
    "InsertExecutionStrategyProtocol",
    "InsertStrategyResolver",
    "MariaDBConnectorInsertStrategy",
    "MySQLDriverExecutemanyStrategy",
    "MySQLMultiRowInsertStrategy",
    "PostgreSQLExecuteValuesStrategy",
    "PostgresCopyStrategy",
]
