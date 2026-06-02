"""Tests de RangePartitioner y HashPartitioner (particionamiento para carga paralela)."""

from __future__ import annotations

import pandas as pd
import pytest

from util_bbdd.bulk import HashPartitioner, RangePartitioner


class TestPartitionRanges:
    def test_basic_split_three_partitions(self) -> None:
        ranges = RangePartitioner.partition_ranges(1, 10, 3)
        assert ranges == [(1, 4), (5, 8), (9, 10)]

    def test_exact_division(self) -> None:
        ranges = RangePartitioner.partition_ranges(1, 9, 3)
        assert ranges == [(1, 3), (4, 6), (7, 9)]

    def test_single_partition_covers_full_range(self) -> None:
        ranges = RangePartitioner.partition_ranges(5, 100, 1)
        assert ranges == [(5, 100)]

    def test_more_partitions_than_values_caps_to_range(self) -> None:
        ranges = RangePartitioner.partition_ranges(1, 3, 10)
        # step = ceil(3/10) = 1 → 3 rangos de tamaño 1
        assert ranges == [(1, 1), (2, 2), (3, 3)]

    def test_single_value_range(self) -> None:
        ranges = RangePartitioner.partition_ranges(42, 42, 4)
        assert ranges == [(42, 42)]

    def test_ranges_are_contiguous_and_non_overlapping(self) -> None:
        ranges = RangePartitioner.partition_ranges(1, 13_000_000, 8)
        for i in range(len(ranges) - 1):
            assert ranges[i][1] + 1 == ranges[i + 1][0]

    def test_last_range_ends_at_max_val(self) -> None:
        ranges = RangePartitioner.partition_ranges(1, 13_000_000, 8)
        assert ranges[-1][1] == 13_000_000

    def test_first_range_starts_at_min_val(self) -> None:
        ranges = RangePartitioner.partition_ranges(100, 200, 5)
        assert ranges[0][0] == 100

    def test_min_greater_than_max_raises(self) -> None:
        with pytest.raises(ValueError, match="min_val"):
            RangePartitioner.partition_ranges(10, 5, 2)

    def test_n_partitions_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="n_partitions"):
            RangePartitioner.partition_ranges(1, 10, 0)

    def test_n_partitions_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="n_partitions"):
            RangePartitioner.partition_ranges(1, 10, -1)


class TestPartitionDataframe:
    def _make_df(self, n: int) -> pd.DataFrame:
        return pd.DataFrame({"id": range(1, n + 1), "v": [f"x{i}" for i in range(1, n + 1)]})

    def test_basic_split_returns_correct_count(self) -> None:
        df = self._make_df(10)
        parts = RangePartitioner.partition_dataframe(df, "id", 3)
        assert len(parts) == 3

    def test_all_rows_covered_without_duplication(self) -> None:
        df = self._make_df(100)
        parts = RangePartitioner.partition_dataframe(df, "id", 4)
        combined = pd.concat(parts).sort_values("id", ignore_index=True)
        pd.testing.assert_frame_equal(combined, df.sort_values("id", ignore_index=True))

    def test_partitions_are_disjoint(self) -> None:
        df = self._make_df(50)
        parts = RangePartitioner.partition_dataframe(df, "id", 5)
        all_ids = [row for p in parts for row in p["id"].tolist()]
        assert len(all_ids) == len(set(all_ids))

    def test_empty_dataframe_returns_one_empty_partition(self) -> None:
        df = pd.DataFrame({"id": pd.Series([], dtype=int), "v": pd.Series([], dtype=str)})
        parts = RangePartitioner.partition_dataframe(df, "id", 4)
        assert len(parts) == 1
        assert parts[0].empty

    def test_fewer_rows_than_partitions_caps_partitions(self) -> None:
        df = self._make_df(3)
        parts = RangePartitioner.partition_dataframe(df, "id", 10)
        # solo 3 filas → máximo 3 particiones
        assert len(parts) == 3
        assert all(len(p) == 1 for p in parts)

    def test_single_partition_returns_full_sorted_df(self) -> None:
        df = self._make_df(20)
        parts = RangePartitioner.partition_dataframe(df, "id", 1)
        assert len(parts) == 1
        assert len(parts[0]) == 20

    def test_missing_pk_col_raises_value_error(self) -> None:
        df = self._make_df(5)
        with pytest.raises(ValueError, match="'pk_missing'"):
            RangePartitioner.partition_dataframe(df, "pk_missing", 2)

    def test_n_partitions_zero_raises(self) -> None:
        df = self._make_df(5)
        with pytest.raises(ValueError, match="n_partitions"):
            RangePartitioner.partition_dataframe(df, "id", 0)

    def test_string_column_raises_type_error(self) -> None:
        df = pd.DataFrame({"pk": ["a", "b", "c"]})
        with pytest.raises(TypeError, match="enteras o datetime64"):
            RangePartitioner.partition_dataframe(df, "pk", 2)

    def test_float_column_raises_type_error(self) -> None:
        df = pd.DataFrame({"pk": [1.0, 2.0, 3.0]})
        with pytest.raises(TypeError, match="enteras o datetime64"):
            RangePartitioner.partition_dataframe(df, "pk", 2)

    def test_datetime64_column_accepted(self) -> None:
        df = pd.DataFrame({"ts": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])})
        parts = RangePartitioner.partition_dataframe(df, "ts", 2)
        assert len(parts) == 2
        assert sum(len(p) for p in parts) == 3

    def test_unsorted_input_returns_sorted_partitions(self) -> None:
        df = pd.DataFrame({"id": [5, 1, 3, 2, 4]})
        parts = RangePartitioner.partition_dataframe(df, "id", 2)
        first_part_ids = sorted(parts[0]["id"].tolist())
        second_part_ids = sorted(parts[1]["id"].tolist())
        # primer grupo tiene los IDs más bajos
        assert max(first_part_ids) < min(second_part_ids)


class TestHashPartitioner:
    """F-01: HashPartitioner acepta cualquier tipo hashable (str, UUID, int…)."""

    def test_all_rows_covered(self) -> None:
        df = pd.DataFrame({"pk": ["alpha", "beta", "gamma", "delta", "epsilon"]})
        parts = HashPartitioner.partition_dataframe(df, "pk", 3)
        combined = pd.concat(parts)
        assert len(combined) == 5
        assert set(combined["pk"].tolist()) == set(df["pk"].tolist())

    def test_partitions_are_disjoint(self) -> None:
        df = pd.DataFrame({"pk": [f"item_{i}" for i in range(50)]})
        parts = HashPartitioner.partition_dataframe(df, "pk", 4)
        all_vals = [v for p in parts for v in p["pk"].tolist()]
        assert len(all_vals) == len(set(all_vals))

    def test_string_column_accepted(self) -> None:
        df = pd.DataFrame({"pk": ["a", "b", "c", "d"]})
        parts = HashPartitioner.partition_dataframe(df, "pk", 2)
        assert sum(len(p) for p in parts) == 4

    def test_integer_column_accepted(self) -> None:
        df = pd.DataFrame({"pk": list(range(12))})
        parts = HashPartitioner.partition_dataframe(df, "pk", 3)
        assert sum(len(p) for p in parts) == 12

    def test_empty_df_returns_single_empty_partition(self) -> None:
        df = pd.DataFrame({"pk": pd.Series([], dtype=str)})
        parts = HashPartitioner.partition_dataframe(df, "pk", 3)
        assert len(parts) == 1
        assert parts[0].empty

    def test_n_partitions_one_returns_full_df(self) -> None:
        df = pd.DataFrame({"pk": ["x", "y", "z"]})
        parts = HashPartitioner.partition_dataframe(df, "pk", 1)
        assert len(parts) == 1
        assert len(parts[0]) == 3

    def test_n_partitions_zero_raises(self) -> None:
        df = pd.DataFrame({"pk": ["a", "b"]})
        with pytest.raises(ValueError, match="n_partitions"):
            HashPartitioner.partition_dataframe(df, "pk", 0)

    def test_missing_col_raises(self) -> None:
        df = pd.DataFrame({"pk": ["a", "b"]})
        with pytest.raises(ValueError, match="'no_existe'"):
            HashPartitioner.partition_dataframe(df, "no_existe", 2)

    def test_result_has_no_empty_partitions(self) -> None:
        df = pd.DataFrame({"pk": ["only_one_value"] * 10})
        parts = HashPartitioner.partition_dataframe(df, "pk", 4)
        assert all(len(p) > 0 for p in parts)

    def test_total_rows_preserved_with_many_partitions(self) -> None:
        df = pd.DataFrame({"pk": [f"k{i}" for i in range(200)]})
        parts = HashPartitioner.partition_dataframe(df, "pk", 8)
        assert sum(len(p) for p in parts) == 200
