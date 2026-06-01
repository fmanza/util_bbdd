"""Unit tests for bulk/normalize.py."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from sqlalchemy import Boolean, DateTime, Float, Integer, LargeBinary, String, Text

from util_bbdd.bulk.normalize import (
    _decode_bytes_to_string,
    iter_normalize_records,
    normalize_records_for_sql,
    normalize_sql_literal,
    pandas_dtype_to_sqlalchemy,
)

# ---------------------------------------------------------------------------
# normalize_sql_literal
# ---------------------------------------------------------------------------


class TestNormalizeSqlLiteralNulls:
    def test_none_returns_none(self) -> None:
        assert normalize_sql_literal(None) is None

    def test_pd_na_returns_none(self) -> None:
        assert normalize_sql_literal(pd.NA) is None

    def test_np_nan_returns_none(self) -> None:
        assert normalize_sql_literal(np.nan) is None

    def test_pd_nat_returns_none(self) -> None:
        assert normalize_sql_literal(pd.NaT) is None


class TestNormalizeSqlLiteralNumpy:
    def test_np_int64_returns_int(self) -> None:
        result = normalize_sql_literal(np.int64(42))
        assert result == 42
        assert isinstance(result, int)

    def test_np_int32_returns_int(self) -> None:
        assert normalize_sql_literal(np.int32(-7)) == -7

    def test_np_float64_returns_float(self) -> None:
        result = normalize_sql_literal(np.float64(3.14))
        assert isinstance(result, float)
        assert abs(result - 3.14) < 1e-10

    def test_np_bool_true_returns_bool(self) -> None:
        result = normalize_sql_literal(np.bool_(True))
        assert result is True
        assert isinstance(result, bool)

    def test_np_bool_false_returns_bool(self) -> None:
        result = normalize_sql_literal(np.bool_(False))
        assert result is False


class TestNormalizeSqlLiteralPandas:
    def test_timestamp_returns_datetime(self) -> None:
        ts = pd.Timestamp("2026-01-15 10:30:00")
        result = normalize_sql_literal(ts)
        assert isinstance(result, datetime)
        assert result.year == 2026 and result.month == 1 and result.day == 15

    def test_timedelta_returns_pytimedelta(self) -> None:
        td = pd.Timedelta("1 days 02:03:04")
        result = normalize_sql_literal(td)
        assert isinstance(result, timedelta)

    def test_categorical_non_null_returns_str(self) -> None:
        cat = pd.Categorical(["a"])[0]
        assert normalize_sql_literal(cat) == "a"


class TestNormalizeSqlLiteralCollections:
    def test_dict_returns_json_string(self) -> None:
        result = normalize_sql_literal({"key": "value", "num": 1})
        assert isinstance(result, str)
        assert '"key"' in result
        assert '"value"' in result

    def test_list_returns_json_string(self) -> None:
        result = normalize_sql_literal([1, 2, 3])
        assert result == "[1, 2, 3]"

    def test_ndarray_returns_bytes(self) -> None:
        arr = np.array([1, 2, 3], dtype=np.int32)
        result = normalize_sql_literal(arr)
        assert isinstance(result, bytes)


class TestNormalizeSqlLiteralStrings:
    def test_plain_string_stripped(self) -> None:
        assert normalize_sql_literal("  hello  ") == "hello"

    def test_empty_string_returned_as_is(self) -> None:
        assert normalize_sql_literal("") == ""

    def test_bytes_utf8_decoded_to_string(self) -> None:
        result = normalize_sql_literal(b"hola")
        assert result == "hola"

    def test_bytes_non_utf8_returned_as_bytes(self) -> None:
        result = normalize_sql_literal(b"\xff\xfe")
        assert isinstance(result, bytes)

    def test_bytearray_utf8_decoded(self) -> None:
        result = normalize_sql_literal(bytearray(b"test"))
        assert result == "test"

    def test_native_int_passthrough(self) -> None:
        assert normalize_sql_literal(99) == 99

    def test_native_float_passthrough(self) -> None:
        result = normalize_sql_literal(1.5)
        assert isinstance(result, float)
        assert abs(result - 1.5) < 1e-10

    def test_native_bool_passthrough(self) -> None:
        assert normalize_sql_literal(True) is True


# ---------------------------------------------------------------------------
# _decode_bytes_to_string
# ---------------------------------------------------------------------------


class TestDecodeBytes:
    def test_bytes_utf8_decoded(self) -> None:
        assert _decode_bytes_to_string(b"hello") == "hello"

    def test_bytearray_utf8_decoded(self) -> None:
        assert _decode_bytes_to_string(bytearray(b"world")) == "world"

    def test_memoryview_utf8_decoded(self) -> None:
        assert _decode_bytes_to_string(memoryview(b"mem")) == "mem"

    def test_non_utf8_returns_bytes(self) -> None:
        result = _decode_bytes_to_string(b"\xff\xfe")
        assert isinstance(result, bytes)

    def test_non_utf8_bytearray_returns_bytes(self) -> None:
        result = _decode_bytes_to_string(bytearray(b"\xff\xfe"))
        assert isinstance(result, bytes)


# ---------------------------------------------------------------------------
# normalize_records_for_sql / iter_normalize_records
# ---------------------------------------------------------------------------


class TestNormalizeRecords:
    def test_basic_records_normalized(self) -> None:
        records = [{"id": np.int64(1), "name": "Alice"}]
        result = normalize_records_for_sql(records)
        assert result == [{"id": 1, "name": "Alice"}]

    def test_keys_converted_to_str(self) -> None:
        records = [{1: "one", 2: "two"}]
        result = normalize_records_for_sql(records)
        assert "1" in result[0]
        assert "2" in result[0]

    def test_nan_becomes_none(self) -> None:
        records = [{"val": np.nan}]
        result = normalize_records_for_sql(records)
        assert result[0]["val"] is None

    def test_empty_list_returns_empty(self) -> None:
        assert normalize_records_for_sql([]) == []

    def test_iter_returns_iterator(self) -> None:
        records = [{"x": 1}]
        iterator = iter_normalize_records(records)
        assert list(iterator) == [{"x": 1}]

    def test_multiple_records_all_normalized(self) -> None:
        records = [
            {"a": np.int64(10), "b": pd.Timestamp("2026-01-01")},
            {"a": np.int64(20), "b": pd.NaT},
        ]
        result = normalize_records_for_sql(records)
        assert isinstance(result[0]["a"], int)
        assert isinstance(result[0]["b"], datetime)
        assert result[1]["b"] is None


# ---------------------------------------------------------------------------
# pandas_dtype_to_sqlalchemy
# ---------------------------------------------------------------------------


class TestPandasDtypeToSqlalchemy:
    def test_integer_series(self) -> None:
        s = pd.Series([1, 2, 3])
        assert pandas_dtype_to_sqlalchemy(s) is Integer

    def test_float_series(self) -> None:
        s = pd.Series([1.0, 2.5])
        assert pandas_dtype_to_sqlalchemy(s) is Float

    def test_bool_series(self) -> None:
        s = pd.Series([True, False])
        assert pandas_dtype_to_sqlalchemy(s) is Boolean

    def test_datetime_series(self) -> None:
        s = pd.Series(pd.to_datetime(["2026-01-01"]))
        assert pandas_dtype_to_sqlalchemy(s) is DateTime

    def test_string_series_returns_string_type(self) -> None:
        s = pd.Series(["hello", "world"])
        result = pandas_dtype_to_sqlalchemy(s)
        assert isinstance(result, String)

    def test_long_string_series_returns_text(self) -> None:
        long_str = "x" * 5000
        s = pd.Series([long_str])
        result = pandas_dtype_to_sqlalchemy(s)
        assert result is Text

    def test_bytes_series_returns_large_binary(self) -> None:
        s = pd.Series([b"\xaa\xbb", b"\xcc\xdd"])
        result = pandas_dtype_to_sqlalchemy(s)
        assert result is LargeBinary

    def test_dict_object_series_returns_json(self) -> None:
        from sqlalchemy import JSON

        s = pd.Series([{"key": "val"}])
        result = pandas_dtype_to_sqlalchemy(s)
        assert result is JSON

    def test_all_null_object_series_returns_string(self) -> None:
        s = pd.Series([None, None], dtype=object)
        result = pandas_dtype_to_sqlalchemy(s)
        assert isinstance(result, String)

    def test_timedelta_series_returns_string(self) -> None:
        s = pd.Series(pd.to_timedelta(["1 days"]))
        result = pandas_dtype_to_sqlalchemy(s)
        assert isinstance(result, String)
