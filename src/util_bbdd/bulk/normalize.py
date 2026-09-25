"""
Módulo de normalización de datos para operaciones SQL.

Proporciona funciones para convertir tipos de datos de pandas/numpy a tipos
nativos de Python que son compatibles con drivers de bases de datos.

Este módulo maneja:
- Tipos escalares de numpy (np.int64, np.float64, etc.)
- Tipos de pandas (pd.Timestamp, pd.NA, etc.)
- Datos binarios (bytes, bytearray)
- JSON (dict, list)
- Strings (str, unicode, bytes decodificables)
- Valores nulos (None, pd.NA, np.nan, pd.NaT)

Versión: 3.0.0
Fecha: Febrero 2026
"""

import json
import math

from collections.abc import Iterator, Sequence
from typing import Any

import numpy as np
import pandas as pd

from pandas.api.extensions import ExtensionDtype

# La misma conversión que ``DataFrame.to_dict`` aplica a las columnas object y de tipo extensión (Int64, boolean, str,
# category, fechas con zona...). Se usa para que dataframe_to_sql_records sea idéntica a to_dict + normalizar.
from pandas.core.dtypes.cast import maybe_box_native  # type: ignore[attr-defined]  # no está en pandas-stubs
from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, LargeBinary, String, Text


def _detect_type_from_sample(sample: Any) -> Any:
    """Detecta el tipo SQLAlchemy basado en una muestra de dato."""
    if isinstance(sample, (dict, list)):
        return JSON
    if isinstance(sample, (bytes, bytearray)):
        return LargeBinary
    return String(255)


def _get_string_type(series: pd.Series) -> Any:
    """Obtiene el tipo String apropiado según longitud máxima."""
    max_len: int = series.astype(str).str.len().max()
    if pd.isna(max_len):
        return String(255)
    return String(int(max_len) + 1) if max_len < 4000 else Text


def _detect_object_dtype(series: pd.Series) -> Any:
    """Detecta el tipo SQLAlchemy para dtype object."""
    for sample in series:
        try:
            if pd.isna(sample):
                continue
        except (TypeError, ValueError):
            pass
        return _detect_type_from_sample(sample)
    return String(255)


def _detect_binary_or_string_dtype(series: pd.Series) -> Any:
    """Detecta tipo SQLAlchemy para tipos binarios o strings."""
    if len(series) == 0:
        return String(255)
    non_null = series.dropna()
    if non_null.empty:
        return String(255)
    primer = non_null.iloc[0]
    if isinstance(primer, bytes):
        return LargeBinary
    if isinstance(primer, str):
        return _get_string_type(series)
    return String(255)


def _is_bytes_dtype(dtype: Any) -> bool:
    """Compatibilidad: detecta bytes dtype con o sin is_bytes_dtype."""
    is_bytes = getattr(pd.api.types, "is_bytes_dtype", None)
    if callable(is_bytes):
        return bool(is_bytes(dtype))
    return getattr(dtype, "kind", None) in ["S", "V"]


def pandas_dtype_to_sqlalchemy(series: pd.Series) -> Any:
    """
    Convierte un tipo de datos de pandas a un tipo SQLAlchemy.

    Args:
        series: Serie de pandas para mapear su tipo

    Returns:
        Tipo SQLAlchemy correspondiente (Integer, String, JSON, etc.)

    Ejemplos:
        >>> import pandas as pd
        >>> s_int = pd.Series([1, 2, 3])
        >>> pandas_dtype_to_sqlalchemy(s_int)
        <class 'sqlalchemy.sql.sqltypes.Integer'>

        >>> s_str = pd.Series(['a', 'b', 'c'])
        >>> pandas_dtype_to_sqlalchemy(s_str)
        <class 'sqlalchemy.sql.sqltypes.String'>
    """
    dtype = series.dtype

    # Tipos numéricos y booleanos
    if pd.api.types.is_integer_dtype(dtype):
        return Integer
    if pd.api.types.is_float_dtype(dtype):
        return Float
    if pd.api.types.is_bool_dtype(dtype):
        return Boolean
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return DateTime

    if pd.api.types.is_timedelta64_dtype(dtype):
        return String(255)

    # Tipos objeto y string específicos
    if pd.api.types.is_object_dtype(dtype):
        return _detect_object_dtype(series)

    if _is_bytes_dtype(dtype):
        return LargeBinary

    if pd.api.types.is_string_dtype(dtype):
        return _get_string_type(series)

    # Tipos binarios (numpy S/V) y unicode (U) no capturados por las ramas anteriores
    if series.dtype.kind in ["S", "V", "U"]:
        return _detect_binary_or_string_dtype(series)

    return String(255)


def iter_normalize_records(records: Sequence[dict[Any, Any]]) -> Iterator[dict[str, Any]]:
    """
    Procesa una secuencia de registros y los normaliza para SQL, devolviendo un iterador.

    Esta es una versión eficiente en memoria que procesa los registros uno a uno,
    ideal para conjuntos de datos muy grandes.

    Args:
        records: Secuencia de diccionarios con datos a normalizar

    Yields:
        Diccionarios con claves y valores normalizados para SQL

    Ejemplo:
        >>> records = [{'id': 1, 'name': 'Alice'}, {'id': 2, 'name': 'Bob'}]
        >>> list(iter_normalize_records(records))
        [{'id': 1, 'name': 'Alice'}, {'id': 2, 'name': 'Bob'}]
    """
    return ({str(k): normalize_sql_literal(v) for k, v in row.items()} for row in records)


def normalize_records_for_sql(records: Sequence[dict[Any, Any]]) -> list[dict[str, Any]]:
    """
    Normaliza una secuencia de registros para SQL, devolviendo una nueva lista materializada.

    Esta función consume más memoria que `iter_normalize_records` pero es compatible
    con operaciones que requieren una lista completa (ej. acceso por índice, múltiples pasadas).

    Args:
        records: Secuencia de diccionarios con datos a normalizar

    Returns:
        Nueva lista con registros normalizados

    Ejemplo:
        >>> records = [{'id': np.int64(1), 'name': 'Alice'}]
        >>> normalized = normalize_records_for_sql(records)
        >>> normalized[0]['id']
        1
    """
    return list(iter_normalize_records(records))


def dataframe_to_sql_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Registros normalizados para SQL a partir de un DataFrame, preparados por columnas.

    Produce exactamente lo mismo que ``normalize_records_for_sql(df.to_dict(orient="records"))`` (mismas claves, orden,
    valores y tipos Python), pero convierte en bloque las columnas numpy numéricas, booleanas y de fecha en lugar de
    pasar celda a celda por ``normalize_sql_literal``. P-03 (performance-audit de bulk): la preparación celda a celda
    era ~62 % del tiempo de un INSERT de 1M filas en SQLite.

    Args:
        df: DataFrame con las columnas a enviar.

    Returns:
        Lista de diccionarios ``{str(columna): valor}``, uno por fila.
    """
    keys: list[str] = [str(column) for column in df.columns]
    columns: list[list[Any]] = [_normalize_column(df.iloc[:, index]) for index in range(df.shape[1])]
    # Sin columnas, zip() no produce filas: igual que to_dict, que devuelve [] aunque haya filas.
    return [dict(zip(keys, row, strict=True)) for row in zip(*columns, strict=True)]


def _normalize_column(series: pd.Series) -> list[Any]:
    """Valores normalizados de una columna, idénticos a los de ``to_dict`` + ``normalize_sql_literal``."""
    dtype = series.dtype
    if isinstance(dtype, np.dtype) and dtype.kind in "iub":
        # int/uint/bool numpy: to_dict ya da int/bool nativos y normalize_sql_literal los devuelve tal cual.
        return series.to_numpy().tolist()
    if isinstance(dtype, np.dtype) and dtype.kind == "f":
        # float numpy: float nativo; NaN → None (pd.isna en normalize_sql_literal).
        return [None if value != value else value for value in series.to_numpy().tolist()]
    if pd.api.types.is_datetime64_any_dtype(dtype):
        # Fechas (sin y con zona): Timestamp.to_pydatetime(); NaT → None.
        return [None if value is pd.NaT else value for value in series.array.to_pydatetime()]
    if dtype == np.dtype(object) or isinstance(dtype, pd.StringDtype):
        # P-33 (performance-audit de serialización SQL): ``to_numpy(dtype=object)`` da los mismos objetos que
        # ``list(series)`` y es ~12 veces más rápido con la dtype ``str`` respaldada por pyarrow.
        values: list[Any] = list(series.to_numpy(dtype=object))
        text: list[Any] | None = _normalize_text_values(values)
        return text if text is not None else _normalize_values(values, box=True)
    return _normalize_values(list(series), box=isinstance(dtype, ExtensionDtype))


def _normalize_values(values: list[Any], *, box: bool) -> list[Any]:
    """Camino general, celda a celda; ``box`` aplica antes ``maybe_box_native`` (columnas object y de extensión)."""
    if box:
        values = [maybe_box_native(value) for value in values]
    return [normalize_sql_literal(value) for value in values]


def _normalize_text_values(values: list[Any]) -> list[Any] | None:
    """Vía rápida (P-33) para columnas solo de ``str`` y nulos: lo mismo que ``normalize_sql_literal`` celda a celda.

    ``str`` → ``strip()``; ``None``, ``pd.NA`` y ``NaN`` (``float``) → ``None``. Devuelve ``None`` si hay cualquier otro
    valor (incluidas subclases de ``str`` como ``np.str_``) para que la columna siga el camino general.
    """
    for value in values:
        if type(value) is str or value is None or value is pd.NA:
            continue
        if type(value) is not float or not math.isnan(value):
            return None
    return [value.strip() if type(value) is str else None for value in values]


def _decode_bytes_to_string(value: bytes | bytearray | memoryview) -> str | bytes:
    """Intenta decodificar bytes a string UTF-8, retorna bytes si falla."""
    raw: bytes = bytes(value) if not isinstance(value, bytes) else value
    try:
        return raw.decode("utf-8")
    except (UnicodeDecodeError, AttributeError, TypeError):
        return raw


def _convert_numpy_scalar(value: np.generic) -> Any:
    """Convierte tipos escalares de numpy a tipos nativos Python."""
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value.item()


def normalize_sql_literal(value: Any) -> Any:
    """
    Normaliza un valor para su inserción segura en una consulta SQL.

    Convierte tipos de datos de pandas/numpy a tipos nativos de Python
    que son compatibles con los drivers de BBDD (a través de SQLAlchemy).

    Args:
        value: Valor a normalizar de cualquier tipo

    Returns:
        Valor normalizado compatible con SQL

    Maneja:
        - Tipos de Numpy escalares (np.int64, np.float64, np.bool_, etc.)
        - Tipos de Pandas (pd.Timestamp, pd.NA, pd.Categorical)
        - Strings (str, bytes decodificables, Unicode)
        - Binarios (bytes, bytearray, np.ndarray)
        - JSON (dict, list)
        - Nulos (None, pd.NA, np.nan, pd.NaT)

    Ejemplo:
        >>> import numpy as np
        >>> normalize_sql_literal(np.int64(42))
        42

        >>> normalize_sql_literal(pd.Timestamp('2026-02-06'))
        datetime.datetime(2026, 2, 6, 0, 0)

        >>> normalize_sql_literal({'key': 'value'})
        '{"key": "value"}'

        >>> normalize_sql_literal(None)
        None
    """
    # Tipos no escalares: list, dict, array
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, default=str)

    if isinstance(value, np.ndarray):
        return value.tobytes()

    # Strings y bytes (manejo especial)
    if isinstance(value, (bytes, bytearray)):
        return _decode_bytes_to_string(value)

    if isinstance(value, str):
        return value.strip() if value else value

    # Tipos de Pandas
    if isinstance(value, pd.Categorical):
        return str(value) if pd.notna(value) else None

    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()

    if isinstance(value, pd.Timedelta):
        return value.to_pytimedelta()

    # Manejo de nulos
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    # Tipos de Numpy escalares
    if isinstance(value, np.generic):
        return _convert_numpy_scalar(value)

    # Retorna el valor si no necesita conversión
    return value
