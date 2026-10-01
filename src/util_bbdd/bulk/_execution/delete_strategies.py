"""Estrategias DELETE por motor y su resolución (``DeleteStrategyResolver``).

Separado de ``batch`` (R10b del refactor de reutilización 2026-09-26) sin cambios de comportamiento.
"""

from __future__ import annotations

import decimal
import json
import logging
import operator
import threading
import uuid
import weakref

from collections.abc import Sequence
from typing import Any, ClassVar, Protocol

import pandas as pd

from sqlalchemy import (
    Delete,
    Engine,
    Table,
    and_,
    any_,
    bindparam,
    delete,
    text,
)
from sqlalchemy.dialects.mssql import TINYINT
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.types import (
    NCHAR,
    NVARCHAR,
    BigInteger,
    Float,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Unicode,
    Uuid,
)

from ...metadata.sqlserver.common import fetch_compatibility_level_sql
from ._driver_quirks import _MSSQL_MAX_DELETE_PARAMS, _MYSQL_MAX_STATEMENT_PARAMS

_log = logging.getLogger(__name__)

_DEFAULT_SQL_BASED_DELETE_DIALECTS: frozenset[str] = frozenset({"mysql", "mariadb", "mssql", "hsqldb"})


# Filas máximas por sentencia ``DELETE ... IN (...)`` en MySQL/MariaDB, sea cual sea el lote (B-04, performance-audit de
# bulk 2026-10-01): con lotes de 50 000 el DELETE de 1M filas tardaba +65 % (MySQL) y +42 % (MariaDB) que con 5000.
_MYSQL_MAX_DELETE_ROWS: int = 5000

# Parámetros máximos por sentencia ``DELETE ... IN (...)`` por dialecto; sin entrada, una sentencia por lote.
_MAX_DELETE_PARAMS: dict[str, int] = {
    "mssql": _MSSQL_MAX_DELETE_PARAMS,
    "mysql": _MYSQL_MAX_STATEMENT_PARAMS,
    "mariadb": _MYSQL_MAX_STATEMENT_PARAMS,
}


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
    en sentencias de ``65535 // columnas de la PK`` filas y, como mucho, 5000 (B-04: listas ``IN`` más largas son más
    lentas). El resto de dialectos usa una sentencia por lote.
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
        if dialect_name in ("mysql", "mariadb"):
            rows_per_statement = min(rows_per_statement, _MYSQL_MAX_DELETE_ROWS)
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


# Nivel de compatibilidad mínimo de SQL Server para OPENJSON (SQL Server 2016).
_MSSQL_OPENJSON_MIN_COMPATIBILITY: int = 130


class MSSQLOpenJsonDeleteStrategy:
    """DELETE para SQL Server con la PK del lote en **un** parámetro JSON (B-02, performance-audit de bulk 2026-10-01).

    - PK simple: ``DELETE FROM t WHERE pk IN (SELECT CAST([value] AS tipo) FROM OPENJSON(:pk_json))``.
    - PK compuesta: ``DELETE t FROM t AS t JOIN OPENJSON(:pk_json) WITH (a tipo '$[0]', b tipo '$[1]') AS k ON …``
      (antes, un ``DELETE`` por fila con executemany).

    Con ``IN`` de hasta 2000 marcadores (:class:`SqlBasedDeleteStrategy`) SQL Server compila un plan por forma de
    sentencia, y esa compilación dominaba en lotes pequeños. Medido con PK simple (mediana de 3, SQL Server 2022, pyodbc):
    1K filas 0,156 → 0,019 s, 10K 0,816 → 0,040 s, 1M 8,45 → 2,45 s.

    Usa la estrategia anterior (``fallback``) si algún valor del lote no cabe exactamente en el tipo de su columna
    (:func:`_fits`: cadenas más largas, no ASCII en ``VARCHAR``, decimales que se redondearían, enteros fuera de rango, tipos
    Python distintos, fechas, binarios, ``float``…) o si la base de datos tiene nivel de compatibilidad < 130. El
    nivel se lee una vez por engine. El ``CAST``/``WITH`` usa el tipo de cada columna (sin su ``COLLATE``, que no es válido
    ahí): la comparación se hace sobre el tipo de la PK, sin conversión implícita de la columna, que impediría usar el
    índice, y con la intercalación de la columna.
    """

    _compatibility: ClassVar[weakref.WeakKeyDictionary[Engine, bool]] = weakref.WeakKeyDictionary()
    _compatibility_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, fallback: DeleteExecutionStrategyProtocol | None = None) -> None:
        self._fallback: DeleteExecutionStrategyProtocol = fallback or SqlBasedDeleteStrategy()

    def execute(
        self,
        *,
        connection: Any,
        table: Table,
        batch_df: pd.DataFrame,
        pk_cols: Sequence[str],
    ) -> None:
        payload: str | None = _openjson_payload(
            [batch_df[column].tolist() for column in pk_cols], [table.c[column].type for column in pk_cols]
        )
        if payload is None or not self._openjson_available(connection):
            self._fallback.execute(connection=connection, table=table, batch_df=batch_df, pk_cols=pk_cols)
            return
        dialect = connection.dialect
        preparer = dialect.identifier_preparer
        columns = [table.c[column] for column in pk_cols]
        if len(columns) == 1:
            sql: str = (
                f"DELETE FROM {preparer.format_table(table)} WHERE {preparer.quote(columns[0].name)} IN "
                f"(SELECT CAST([value] AS {_sql_type(columns[0], dialect)}) FROM OPENJSON(:pk_json))"
            )
        else:
            quoted = [preparer.quote(column.name) for column in columns]
            with_clause = ", ".join(
                f"{q} {_sql_type(column, dialect)} '$[{i}]'"
                for i, (q, column) in enumerate(zip(quoted, columns, strict=True))
            )
            condition = " AND ".join(f"_bulk_del_t.{q} = _bulk_del_k.{q}" for q in quoted)
            sql = (
                f"DELETE _bulk_del_t FROM {preparer.format_table(table)} AS _bulk_del_t "
                f"JOIN OPENJSON(:pk_json) WITH ({with_clause}) AS _bulk_del_k ON {condition}"
            )
        connection.execute(text(sql), {"pk_json": payload})

    @classmethod
    def _openjson_available(cls, connection: Any) -> bool:
        """``True`` si la base de datos admite OPENJSON (nivel ≥ 130). Se consulta una vez por engine."""
        engine: Any = getattr(connection, "engine", None)
        cacheable: bool = isinstance(engine, Engine)
        if cacheable:
            with cls._compatibility_lock:
                known: bool | None = cls._compatibility.get(engine)
            if known is not None:
                return known
        try:
            level: Any = connection.execute(text(fetch_compatibility_level_sql())).scalar()
            available: bool = isinstance(level, int) and level >= _MSSQL_OPENJSON_MIN_COMPATIBILITY
        except Exception as exc:  # sin permiso sobre sys.databases, conexión simulada…: se usa la vía anterior
            _log.debug("DELETE SQL Server: no se pudo leer el nivel de compatibilidad (%s); se usa IN (...)", exc)
            return False
        if not available:
            _log.info("DELETE SQL Server: nivel de compatibilidad %s < 130, sin OPENJSON; se usa IN (...)", level)
        if cacheable:
            with cls._compatibility_lock:
                cls._compatibility[engine] = available
        return available


def _sql_type(column: Any, dialect: Any) -> str:
    """Tipo de ``column`` para ``CAST``/``WITH`` de OPENJSON, sin ``COLLATE`` (no es válido ahí)."""
    column_type: Any = column.type
    if getattr(column_type, "collation", None):
        # El tipo reflejado de una columna de texto lleva su COLLATE. Sin él, la comparación usa la intercalación de la
        # columna (precedencia implícita frente a la coercible del CAST).
        column_type = column_type.copy()
        column_type.collation = None
    return str(column_type.compile(dialect=dialect))


# Rango de los tipos enteros de SQL Server (CAST fuera de rango da error 22003; IN no borraba nada).
_INT_RANGES: tuple[tuple[type, int, int], ...] = (
    (TINYINT, 0, 255),
    (SmallInteger, -(2**15), 2**15 - 1),
    (BigInteger, -(2**63), 2**63 - 1),
    (Integer, -(2**31), 2**31 - 1),  # el último: TINYINT, SMALLINT y BIGINT son subclases de Integer
)


def _fits(value: Any, column_type: Any) -> bool:
    """``True`` si ``value`` cabe **exactamente** en ``column_type`` (A1, audit-code 2026-10-01).

    OPENJSON convierte cada clave al tipo de la columna (``CAST``/``WITH``) y SQL Server trunca las cadenas, redondea los
    decimales y sustituye por *best fit* los caracteres que el code page de un ``VARCHAR`` no tiene, sin error: con una
    clave que no cabía se borraban otras filas (``'abcdeXYZ'`` en ``VARCHAR(5)`` borraba ``'abcde'``). Las claves que no
    cumplen esto van por ``IN``, que compara el valor tal cual.
    """
    kind = type(value)
    if kind is str and isinstance(column_type, String):
        length: int | None = column_type.length
        if isinstance(column_type, (Unicode, NVARCHAR, NCHAR)):
            return length is None or len(value.encode("utf-16-le")) // 2 <= length
        return value.isascii() and (length is None or len(value) <= length)
    if kind is int and isinstance(column_type, Integer):
        for int_type, low, high in _INT_RANGES:
            if isinstance(column_type, int_type):
                return bool(low <= value <= high)
        return False
    if kind in (int, decimal.Decimal) and isinstance(column_type, Numeric) and not isinstance(column_type, Float):
        precision, scale = column_type.precision, column_type.scale
        if precision is None or scale is None:
            return False
        number = decimal.Decimal(value)
        if not number.is_finite():
            return False
        with decimal.localcontext(prec=200):  # DECIMAL(38, s) no cabe en los 28 dígitos del contexto por defecto
            exact: bool = number.quantize(decimal.Decimal(1).scaleb(-scale)) == number
            return exact and abs(number) < decimal.Decimal(10) ** (precision - scale)
    return kind is uuid.UUID and isinstance(column_type, Uuid)


_NONE_TYPE: type = type(None)
_EXPONENT = operator.attrgetter("exponent")


def _column_fits(values: list[Any], column_type: Any) -> bool:
    """``True`` si todos los valores no nulos de ``values`` caben en ``column_type``: lo mismo que ``all(_fits(v))``.

    P-1 (sesión 2026-10-01l): ``_fits`` valor a valor costaba 0,40 s por millón de claves enteras y 2,06 s con PK
    ``DECIMAL``. En una columna de PK los valores son casi siempre de un solo tipo, y entonces se decide con operaciones
    agregadas (``min``/``max``, ``max(map(len))``…). Con tipos mezclados, o con decimales con más decimales que la escala
    (``1.100`` en escala 2, que caben), se usa ``_fits`` en esos valores. La equivalencia con ``_fits`` está cubierta por
    ``tests/unit/bulk/test_openjson_column_fits.py``.
    """
    kinds: set[type] = set(map(type, values))
    present: list[Any] = values
    if _NONE_TYPE in kinds:
        kinds.discard(_NONE_TYPE)
        present = [value for value in values if value is not None]
    if not present:
        return True
    if len(kinds) != 1:
        return all(_fits(value, column_type) for value in present)
    kind = kinds.pop()
    if kind is str and isinstance(column_type, String):
        length: int | None = column_type.length
        if isinstance(column_type, (Unicode, NVARCHAR, NCHAR)):
            if length is None:
                return True
            if all(map(str.isascii, present)):
                return max(map(len, present)) <= length
            return max(len(value.encode("utf-16-le")) // 2 for value in present) <= length
        return all(map(str.isascii, present)) and (length is None or max(map(len, present)) <= length)
    if kind is int and isinstance(column_type, Integer):
        for int_type, low, high in _INT_RANGES:
            if isinstance(column_type, int_type):
                return bool(low <= min(present) and max(present) <= high)
        return False
    if kind in (int, decimal.Decimal) and isinstance(column_type, Numeric) and not isinstance(column_type, Float):
        precision, scale = column_type.precision, column_type.scale
        if precision is None or scale is None:
            return False
        if kind is int:
            return bool(max(map(abs, present)) < 10 ** (precision - scale))
        if not all(map(decimal.Decimal.is_finite, present)):
            return False
        # Comparaciones exactas (sin el redondeo de contexto de abs() ni de **): copy_abs y potencia entera de 10.
        if max(map(decimal.Decimal.copy_abs, present)) >= decimal.Decimal(10 ** (precision - scale)):
            return False
        # Más decimales que la escala: puede caber (1.100 en escala 2) o no (1.105): comprobación exacta solo en esos.
        if min(map(_EXPONENT, map(decimal.Decimal.as_tuple, present))) >= -scale:  # finitos: exponente entero
            return True
        return all(
            _fits(value, column_type)
            for value in present
            if isinstance(exponent := value.as_tuple().exponent, int) and exponent < -scale
        )
    return kind is uuid.UUID and isinstance(column_type, Uuid)


def _to_json(values: list[Any]) -> list[Any]:
    """Valores ya validados en su forma JSON: ``Decimal`` como texto (sin pasar por ``float``) y ``UUID`` como texto."""
    if any(type(value) in (decimal.Decimal, uuid.UUID) for value in values):
        return [
            format(value, "f") if type(value) is decimal.Decimal else str(value) if type(value) is uuid.UUID else value
            for value in values
        ]
    return values


def _openjson_payload(columns: list[list[Any]], column_types: Sequence[Any]) -> str | None:
    """JSON del lote: array de valores (PK simple) o de arrays por fila (compuesta); ``None`` si algún valor no cabe."""
    converted: list[list[Any]] = []
    for values, column_type in zip(columns, column_types, strict=True):
        if not _column_fits(values, column_type):
            return None  # fuera del dominio de la PK, bool, float, fechas, bytes, NaN, tipos numpy…
        converted.append(_to_json(values))
    items: list[Any] = converted[0] if len(converted) == 1 else [list(row) for row in zip(*converted, strict=True)]
    return json.dumps(items, ensure_ascii=False)


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
        # B-02: SQL Server con OPENJSON salvo que se haya pasado una estrategia propia para los dialectos SQL.
        self._mssql_strategy: DeleteExecutionStrategyProtocol = (
            self._sql_based_strategy if sql_based_strategy is not None else MSSQLOpenJsonDeleteStrategy()
        )

    def resolve(self, dialect_name: str) -> DeleteExecutionStrategyProtocol:
        """Devuelve la estrategia adecuada para el dialecto indicado."""
        if dialect_name == "mssql" and dialect_name in self._sql_based_dialects:
            return self._mssql_strategy
        if dialect_name in self._sql_based_dialects:
            return self._sql_based_strategy
        if dialect_name == "postgresql":
            return self._postgresql_strategy
        return self._generic_strategy


__all__: list[str] = [
    "DeleteExecutionStrategyProtocol",
    "DeleteStrategyResolver",
    "GenericDeleteStrategy",
    "MSSQLOpenJsonDeleteStrategy",
    "PostgreSQLAnyDeleteStrategy",
    "SqlBasedDeleteStrategy",
]
