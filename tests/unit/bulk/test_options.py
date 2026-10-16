"""Paquetes de opciones de BulkCrud y ParallelBulkLoader (v3.0.0): validación, inmutabilidad y opciones de los workers."""

from __future__ import annotations

import dataclasses

from pathlib import Path
from typing import Any

import pytest

from sqlalchemy.exc import OperationalError

from util_bbdd.bulk.options import (
    AuditOptions,
    BatchOptions,
    BulkOptions,
    ExecutionOptions,
    ParallelOptions,
    RejectOptions,
    RetryOptions,
)


class TestBatchOptions:
    def test_defaults(self) -> None:
        assert BatchOptions() == BatchOptions(chunk_size=None, commit_every_n_chunks=None, prefetch_blocks=False)

    @pytest.mark.parametrize("value", [0, -1, True, 1.5, "10"])
    def test_invalid_chunk_size(self, value: Any) -> None:
        with pytest.raises(ValueError, match="chunk_size debe ser un entero ≥ 1"):
            BatchOptions(chunk_size=value)

    @pytest.mark.parametrize("value", [0, -3, True, 2.0])
    def test_invalid_commit_every_n_chunks(self, value: Any) -> None:
        with pytest.raises(ValueError, match="commit_every_n_chunks debe ser None o un entero ≥ 1"):
            BatchOptions(commit_every_n_chunks=value)

    def test_is_frozen(self) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            BatchOptions().chunk_size = 3  # type: ignore[misc]


class TestAuditOptions:
    def test_csv_path_str_is_read_as_path(self) -> None:
        assert AuditOptions(csv_path="logs/audit.csv").csv_path == Path("logs/audit.csv")

    def test_invalid_csv_path_names_the_package(self) -> None:
        with pytest.raises(ValueError, match=r"audit\.csv_path debe ser una ruta"):
            AuditOptions(csv_path=3)  # type: ignore[arg-type]

    def test_enabled(self) -> None:
        assert not AuditOptions().enabled
        assert AuditOptions(csv_path="a.csv").enabled
        assert AuditOptions(sink=object()).enabled  # type: ignore[arg-type]

    def test_replace_keeps_the_path(self) -> None:
        audit = AuditOptions(csv_path="a.csv")
        assert dataclasses.replace(audit, strict=True).csv_path == Path("a.csv")


class TestRejectOptions:
    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"on_error": "skip"}, "on_error"),
            ({"on_error": "isolate"}, "rejects_csv_path"),
            ({"csv_path": "r.csv"}, "solo se usan"),
            ({"on_error": "isolate", "csv_path": "r.csv", "max_rejects": -1}, "max_rejects"),
        ],
    )
    def test_invalid_combinations(self, kwargs: dict[str, Any], message: str) -> None:
        with pytest.raises(ValueError, match=message):
            RejectOptions(**kwargs)

    def test_invalid_csv_path_names_the_package(self) -> None:
        with pytest.raises(ValueError, match=r"rejects\.csv_path debe ser una ruta"):
            RejectOptions(on_error="isolate", csv_path=1)  # type: ignore[arg-type]

    def test_isolate(self) -> None:
        rejects = RejectOptions(on_error="isolate", csv_path="r.csv", max_rejects=0)
        assert (rejects.csv_path, rejects.max_rejects) == (Path("r.csv"), 0)


class TestRetryOptions:
    def test_backoff_is_normalized_to_floats(self) -> None:
        assert RetryOptions(backoff=(1, 2)).backoff == (1.0, 2.0)

    @pytest.mark.parametrize("value", [-1, True, 1.5])
    def test_invalid_max_retries(self, value: Any) -> None:
        with pytest.raises(ValueError, match="max_retries debe ser un entero ≥ 0"):
            RetryOptions(max_retries=value)

    def test_should_retry_uses_is_retriable_by_default(self) -> None:
        retriable = OperationalError("SELECT 1", {}, Exception("deadlock detected"))
        assert RetryOptions().should_retry(ValueError("datos")) is False
        assert RetryOptions(retry_on=lambda _exc: True).should_retry(ValueError("datos")) is True
        assert isinstance(RetryOptions().should_retry(retriable), bool)


class TestParallelOptions:
    def test_defaults(self) -> None:
        options = ParallelOptions()
        assert (options.mode, options.max_workers, options.min_rows, options.disable_constraints) == (
            "manual",
            4,
            None,
            False,
        )
        assert options.retry == RetryOptions()

    def test_invalid_mode(self) -> None:
        with pytest.raises(ValueError, match="mode debe ser"):
            ParallelOptions(mode="fast")  # type: ignore[arg-type]

    @pytest.mark.parametrize("value", [0, True, 2.5])
    def test_invalid_max_workers(self, value: Any) -> None:
        with pytest.raises(ValueError, match="max_workers debe ser un entero ≥ 1"):
            ParallelOptions(max_workers=value)

    def test_invalid_min_rows(self) -> None:
        with pytest.raises(ValueError, match="min_rows debe ser un entero ≥ 1"):
            ParallelOptions(min_rows=0)


class TestBulkOptions:
    def test_of_fills_the_missing_packages(self) -> None:
        options = BulkOptions.of(batch=BatchOptions(chunk_size=10))
        assert options.batch.chunk_size == 10
        assert (options.audit, options.rejects, options.execution, options.parallel) == (
            AuditOptions(),
            RejectOptions(),
            ExecutionOptions(),
            None,
        )

    def test_for_worker_never_parallelizes_and_takes_the_run_id(self) -> None:
        """T1: el worker de una carga paralela no vuelve a paralelizar ni avisa de la auditoría deshabilitada."""
        options = BulkOptions.of(audit=AuditOptions(csv_path="a.csv"), parallel=ParallelOptions(mode="auto"))
        worker = options.for_worker(run_id="run-1")
        assert worker.parallel is None
        assert (worker.audit.run_id, worker.audit.warn_if_disabled, worker.audit.csv_path) == (
            "run-1",
            False,
            Path("a.csv"),
        )
        assert options.audit.run_id is None  # el original no cambia

    def test_as_kwargs_are_the_constructor_arguments(self) -> None:
        assert set(BulkOptions().as_kwargs()) == {"batch", "audit", "rejects", "execution", "parallel"}
