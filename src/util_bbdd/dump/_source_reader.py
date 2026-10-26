"""Lectura del origen del volcado: chunks con ajustes por driver, solape lectura/escritura y reagrupado de lotes.

Separado de ``orchestrator`` (R10a del refactor de reutilización 2026-09-26) sin cambios de comportamiento.
``orchestrator`` re-exporta estos nombres y sus llamadores los usan desde su propio espacio de nombres, así que los
tests que parchean ``util_bbdd.dump.orchestrator._read_chunks`` o ``._prefetch`` siguen interceptándolos.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from datetime import date, datetime, time
from typing import Any

import pandas as pd

from sqlalchemy import event, text
from sqlalchemy.sql import sqltypes

from ..bulk._support.prefetch import PREFETCH_DEPTH, prefetch


def _read_chunks(conn: Any, sql: str, chunk_size: int, params: dict[str, Any] | None = None) -> Iterator[pd.DataFrame]:
    """Lee ``sql`` en DataFrames de hasta ``chunk_size`` filas con ``dtype=object``: cada valor tal como lo da el driver.

    PD-05 (performance-audit de dump 2026-09-25): ``pd.read_sql`` alteraba datos sin avisar. Los enteros de una columna
    con algún NULL pasaban a ``float64`` (BIGINT > 2^53 perdía precisión) y ``coerce_float=True`` (por defecto)
    convertía ``Decimal`` en ``float`` (DECIMAL de más de 15 dígitos). Ninguna opción de ``read_sql`` lo evita del todo:
    ``dtype_backend`` conserva los enteros pero entrega los ``Decimal`` como texto.
    """
    result = _execute_read(conn, sql, chunk_size, params)
    keys = list(result.keys())
    while rows := result.fetchmany(chunk_size):
        yield pd.DataFrame(rows, columns=keys, dtype=object)


# Motores cuyo driver lee con cursor del cliente (todo el resultado en memoria) salvo con ``stream_results``.
_CLIENT_CURSOR_DIALECTS = frozenset({"postgresql", "mysql", "mariadb"})


def _execute_read(conn: Any, sql: str, chunk_size: int, params: dict[str, Any] | None) -> Any:
    """``conn.execute(text(sql))`` con el cursor de lectura ajustado al volcado.

    PostgreSQL, MySQL y MariaDB: cursor de servidor (``stream_results``) con ``max_row_buffer=chunk_size`` (Q2).
    Oracle: ``arraysize = chunk_size`` (Q1, abajo). Resto de motores: sin cambios.

    Q1 (performance-audit de dump 2026-09-25): oracledb lee por defecto 100 filas por ida y vuelta (``arraysize``) y
    SQLAlchemy solo permite cambiarlo en todo el engine. El listener se registra en esta conexión (no en el engine del
    usuario) y solo mientras se crea el cursor; solo sube el valor, nunca baja uno mayor fijado en el engine.
    Medido: 2M filas en 11,7 → 2,5 s.
    """
    if conn.dialect.name in _CLIENT_CURSOR_DIALECTS:
        # Q2 (performance-audit de dump 2026-09-25): psycopg y PyMySQL descargan el resultado entero antes del primer
        # fetchmany (memoria pico proporcional a la tabla mayor). Cursor de servidor solo en esta sentencia.
        stmt = text(sql).execution_options(stream_results=True, max_row_buffer=chunk_size)
        return conn.execute(stmt, params or {})
    if conn.dialect.name != "oracle":
        return conn.execute(text(sql), params or {})

    def _set_arraysize(_conn: Any, cursor: Any, *_args: Any) -> None:
        if cursor.arraysize < chunk_size:
            cursor.arraysize = chunk_size
            if hasattr(cursor, "prefetchrows"):
                cursor.prefetchrows = chunk_size

    event.listen(conn, "before_cursor_execute", _set_arraysize)
    try:
        return conn.execute(text(sql), params or {})
    finally:
        event.remove(conn, "before_cursor_execute", _set_arraysize)


# Motores de origen en los que se solapa la lectura con la escritura (Q3). SQLite no: su conexión no puede usarse desde
# otro hilo (check_same_thread).
_PREFETCH_SOURCE_DIALECTS = frozenset({"postgresql", "mysql", "mariadb", "mssql", "oracle"})


_PREFETCH_DEPTH = PREFETCH_DEPTH


def _prefetch[T](items: Iterator[T], depth: int = _PREFETCH_DEPTH) -> Iterator[T]:
    """Consume ``items`` en un hilo lector con una cola de ``depth`` elementos y los entrega en el mismo orden.

    Q3 (performance-audit de dump 2026-09-25): sin esto, el chunk N+1 no se leía hasta haber escrito el N. La lectura
    (fetch y construcción del DataFrame, en Python) se solapa con la escritura, que espera al servidor sin retener el GIL.
    Implementación en :func:`util_bbdd.bulk._support.prefetch.prefetch` (S-4 de bulk 2026-10-01); aquí el hilo se llama
    ``dump-prefetch``.

    - Una excepción del lector se relanza en quien consume, tras entregar los elementos anteriores.
    - Si quien consume deja de iterar (fallo al escribir), el ``finally`` avisa al lector y **espera a que termine**:
      la conexión de lectura no se cierra mientras el otro hilo la usa.
    """
    return prefetch(items, depth, thread_name="dump-prefetch")


#: Conversión de un valor de texto ISO de SQLite a fecha, fecha y hora u hora (G33, 4.4.0).
type TemporalParser = Callable[[str], date | datetime | time]


def _sqlite_temporal_parsers(
    columns: Iterable[Mapping[str, Any]], target_columns: Iterable[Mapping[str, Any]]
) -> dict[str, TemporalParser]:
    """Columnas ``DATE``/``DATETIME``/``TIMESTAMP``/``TIME`` de una tabla SQLite y su conversión desde texto ISO.

    G33 de util_bbdd_web (4.4.0): SQLite no tiene tipos de columna y el driver entrega estas columnas como texto (la
    lectura usa ``text()``, sin los procesadores de tipo de SQLAlchemy). Un destino servidor convertía el texto, pero
    uno SQLite lo rechazaba (``SQLite Date type only accepts Python date objects``) y la tabla terminaba en ``error``.

    Solo se convierte si la columna del destino (``target_columns``, emparejada sin distinguir mayúsculas) es de fecha
    u hora, y ``TIME`` solo hacia ``TIME``: hacia texto, o hacia el ``DATE`` de Oracle (sin ``TIME``; oracledb rechaza
    ``datetime.time``), el valor sigue llegando como texto, igual que antes.
    """
    targets = {str(c["name"]).lower(): c.get("type") for c in target_columns}
    parsers: dict[str, TemporalParser] = {}
    for column in columns:
        kind, target = column.get("type"), targets.get(str(column["name"]).lower())
        if not isinstance(target, (sqltypes.Date, sqltypes.DateTime, sqltypes.Time)):
            continue
        if isinstance(kind, sqltypes.DateTime):
            parsers[column["name"]] = datetime.fromisoformat
        elif isinstance(kind, sqltypes.Date):
            parsers[column["name"]] = date.fromisoformat
        elif isinstance(kind, sqltypes.Time) and isinstance(target, sqltypes.Time):
            parsers[column["name"]] = time.fromisoformat
    return parsers


def _parse_temporal_text(
    chunks: Iterator[pd.DataFrame], parsers: Mapping[str, TemporalParser]
) -> Iterator[pd.DataFrame]:
    """Convierte el texto ISO de las columnas de ``parsers`` en ``date``/``datetime``/``time`` (G33, 4.4.0).

    Un valor que no es texto o no es ISO se deja como está: el destino lo trata como antes (lo convierte o lo rechaza, y
    ``on_error="isolate"`` puede apartar la fila). La columna sigue siendo ``object`` (``Series.map`` la convertiría en
    ``datetime64`` y llegarían ``Timestamp`` de pandas).
    """
    for chunk in chunks:
        for name, parse in parsers.items():
            if name in chunk.columns:
                chunk[name] = pd.Series(
                    [_parse_iso(value, parse) for value in chunk[name]], index=chunk.index, dtype=object
                )
        yield chunk


def _parse_iso(value: Any, parse: TemporalParser) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return parse(value)
    except ValueError:
        return value


def _rebatch(chunks: Iterator[pd.DataFrame], size: int) -> Iterator[pd.DataFrame]:
    """Agrupa los chunks consecutivos hasta tener al menos ``size`` filas; mismas filas y en el mismo orden (Q5)."""
    pending: list[pd.DataFrame] = []
    rows = 0
    for chunk in chunks:
        pending.append(chunk)
        rows += len(chunk)
        if rows >= size:
            yield pending[0] if len(pending) == 1 else pd.concat(pending, ignore_index=True)
            pending, rows = [], 0
    if pending:
        yield pending[0] if len(pending) == 1 else pd.concat(pending, ignore_index=True)
