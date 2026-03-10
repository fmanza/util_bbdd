"""Tests de normalización homogénea de resultados de consulta."""

from __future__ import annotations

from util_bbdd.result_normalizer import ResultNormalizer


class TestResultNormalizer:
    def test_normalize_many_none_returns_empty_list(self) -> None:
        normalizer = ResultNormalizer()
        assert normalizer.normalize_many(None) == []

    def test_normalize_many_tuple_of_rows_returns_list(self) -> None:
        normalizer = ResultNormalizer()
        raw = (("users",), ("orders",))
        assert normalizer.normalize_many(raw) == [("users",), ("orders",)]

    def test_normalize_many_generator_returns_materialized_rows(self) -> None:
        normalizer = ResultNormalizer()
        raw = (item for item in (("a", 1), ("b", 2)))
        assert normalizer.normalize_many(raw) == [("a", 1), ("b", 2)]

    def test_normalize_one_list_row_returns_tuple(self) -> None:
        normalizer = ResultNormalizer()
        assert normalizer.normalize_one(["id", 10]) == ("id", 10)

    def test_normalize_many_flat_list_treated_as_single_row(self) -> None:
        normalizer = ResultNormalizer()
        assert normalizer.normalize_many([1, 2, 3]) == [(1, 2, 3)]

    def test_normalize_one_scalar_wrapped_as_single_column_row(self) -> None:
        normalizer = ResultNormalizer()
        assert normalizer.normalize_one("value") == ("value",)
