"""Equivalencia estricta de ``dataframe_to_sql_records`` con la ruta anterior (P-03 del performance-audit de bulk).

``dataframe_to_sql_records(df)`` debe producir exactamente ``normalize_records_for_sql(df.to_dict(orient="records"))``:
mismas claves en el mismo orden, mismos valores y mismos tipos Python (en Python ``1 == True == 1.0``, así que se
compara también el tipo).
"""

from __future__ import annotations

import datetime
import decimal
import warnings

from typing import Any

import numpy as np
import pandas as pd
import pytest

from util_bbdd.bulk.normalize import dataframe_to_sql_records, normalize_records_for_sql

pytestmark = pytest.mark.unit


def _reference(df: pd.DataFrame) -> list[dict[str, Any]]:
    return normalize_records_for_sql(df.to_dict(orient="records"))


def _strict(value: Any) -> Any:
    """Representación comparable que distingue tipos (y zona horaria en las fechas)."""
    if isinstance(value, datetime.datetime):
        return ("datetime", value.isoformat(), str(value.tzinfo))
    if isinstance(value, np.ndarray):
        return ("ndarray", value.tobytes())
    return (type(value).__name__, value)


def _assert_equivalent(df: pd.DataFrame) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # Timestamp.to_pydatetime avisa al descartar nanosegundos (en ambas rutas)
        expected = _reference(df)
        actual = dataframe_to_sql_records(df)
    assert len(actual) == len(expected)
    for got, want in zip(actual, expected, strict=True):
        assert list(got) == list(want)  # mismas claves y orden
        assert [_strict(v) for v in got.values()] == [_strict(v) for v in want.values()]


DTYPE_MATRIX: dict[str, Any] = {
    "int64": np.array([1, -2, 3, 2**40, 0]),
    "uint64": np.array([0, 1, 2**63, 5, 7], dtype="uint64"),
    "uint8": np.array([0, 1, 2, 255, 7], dtype="uint8"),
    "int8": np.array([-128, 0, 1, 127, 3], dtype="int8"),
    "float64": [1.5, np.nan, -0.0, np.inf, -np.inf],
    "float32": np.array([0.1, np.nan, 2.0, 3.5, -1e30], dtype="float32"),
    "float_all_nan": [np.nan] * 5,
    "bool": [True, False, True, False, True],
    "datetime_ns": pd.to_datetime(
        ["2026-01-01 10:00:00.123456789", None, "2026-01-02 00:00:00", "1970-01-01 00:00:00", "2262-04-11 00:00:00"],
        format="ISO8601",
    ),
    "datetime_s": pd.array(pd.to_datetime(["2026-01-01", None, "2026-01-02", "2026-01-03", "2026-01-04"]))
    .astype("datetime64[s]")
    .to_numpy(),
    "datetime_tz": pd.to_datetime(
        ["2026-03-29 01:30", None, "2026-10-25 02:30", "2026-01-03", "2026-07-01"], format="ISO8601"
    ).tz_localize("Europe/Madrid", ambiguous="NaT", nonexistent="NaT"),
    "datetime_utc": pd.to_datetime(["2026-01-01", None, "2026-01-02", "2026-01-03", "2026-01-04"], utc=True),
    "timedelta": pd.to_timedelta([1, None, 3, 4, 5], unit="s"),
    "Int64": pd.array([1, None, 3, 4, 5], dtype="Int64"),
    "Float64": pd.array([1.5, None, 3.0, 4.0, 5.0], dtype="Float64"),
    "boolean": pd.array([True, None, False, True, False], dtype="boolean"),
    "str": pd.array([" a ", None, "", "x", "ñ"], dtype="str"),
    "string_python": pd.array([" a ", None, "", "x", "ñ"], dtype="string[python]"),
    "string_pyarrow": pd.array([" a ", None, "", "x", "ñ"], dtype="string[pyarrow]"),
    "category": pd.Categorical(["a", None, "b", "a", "c"]),
    # P-33: vía rápida de texto (solo str exacto y nulos) y salidas al camino general.
    "object_str_only": [" a ", None, "", "x ", np.nan],
    "object_str_pd_na": ["a", pd.NA, " b", "", None],
    "object_np_str": [np.str_(" a "), "b", None, "c", ""],
    "object_str_and_int": ["a", 1, None, " b ", ""],
    "object_str_and_nan32": ["a", np.float32("nan"), None, " b ", ""],
    "object_mixed": [" a ", None, {"k": 1}, b"\xff", [1, "x"]],
    "object_numpy_scalars": [
        np.int64(1),
        np.float64(np.nan),
        np.bool_(True),
        np.datetime64("2026-01-01T00:00:00"),
        None,
    ],
    "object_bytes_utf8": [b"q", b"", b"\xc3\xb1", None, bytearray(b"z")],
    "decimal": [decimal.Decimal("1.1"), None, decimal.Decimal("2"), decimal.Decimal("-0.5"), decimal.Decimal("NaN")],
    "object_dates": [
        datetime.date(2026, 1, 1),
        None,
        datetime.datetime(2026, 1, 1, 10),
        pd.Timestamp("2026-02-01"),
        pd.NaT,
    ],
}


@pytest.mark.parametrize("column", sorted(DTYPE_MATRIX))
def test_each_dtype_matches_the_previous_path(column: str) -> None:
    _assert_equivalent(pd.DataFrame({column: DTYPE_MATRIX[column]}))


def test_full_matrix_in_one_frame_matches() -> None:
    _assert_equivalent(pd.DataFrame(DTYPE_MATRIX))


def test_non_string_and_duplicate_column_names_match() -> None:
    df = pd.DataFrame([[1, 2.5, "a", 4]], columns=[1, "1.0", "x", "x"])
    _assert_equivalent(df)


@pytest.mark.parametrize(
    "df",
    [
        pd.DataFrame(),
        pd.DataFrame({"a": pd.Series([], dtype="int64")}),
        pd.DataFrame(index=range(3)),
        pd.DataFrame({"a": [1, 2]}, index=[10, 10]),
    ],
    ids=["vacío", "sin_filas", "sin_columnas", "índice_duplicado"],
)
def test_edge_shapes_match(df: pd.DataFrame) -> None:
    _assert_equivalent(df)


def test_column_slice_of_larger_frame_matches() -> None:
    df = pd.DataFrame(DTYPE_MATRIX).iloc[1:4]
    _assert_equivalent(df[["int64", "float64", "datetime_tz", "str"]])
