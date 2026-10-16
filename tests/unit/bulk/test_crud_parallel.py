"""Ruta paralela de ``BulkCrud.bulk_*_from_df`` con ``ParallelOptions`` (v3.0.0).

SQLite admite un solo escritor, así que el planificador lo deja siempre en serie. Para ejercitar la carga con varios
hilos sin un servidor, los tests que lo necesitan quitan SQLite de ``SINGLE_WRITER_DIALECTS``: con una BD en fichero, las
particiones se serializan en el lock de SQLite (``timeout``), pero cada una va en su hilo, su ``BulkCrud`` y su
transacción, que es lo que se comprueba.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from sqlalchemy import Column, Engine, Integer, MetaData, String, Table, create_engine, text

from util_bbdd.bulk import BulkCrud, HashPartitioner, ParallelLoadResult, RangePartitioner
from util_bbdd.bulk._execution import parallel_loader as pl_mod, parallel_planner
from util_bbdd.bulk.options import AuditOptions, ExecutionOptions, ParallelOptions
from util_bbdd.exceptions import ParallelLoadError


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}", connect_args={"timeout": 30})
    metadata = MetaData()
    Table("items", metadata, Column("id", Integer, primary_key=True), Column("v", String(20)))
    Table(
        "pairs",
        metadata,
        Column("a", Integer, primary_key=True),
        Column("b", String(10), primary_key=True),
        Column("v", String(20)),
    )
    metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def several_writers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deja que el planificador use varios hilos con SQLite (ver el docstring del módulo)."""
    monkeypatch.setattr(parallel_planner, "SINGLE_WRITER_DIALECTS", frozenset())


def _items(ids: range | list[int], value: str = "x") -> pd.DataFrame:
    return pd.DataFrame({"id": list(ids), "v": [f"{value}{i}" for i in ids]})


def _rows(engine: Engine, table: str = "items") -> list[tuple[Any, ...]]:
    with engine.connect() as conn:
        return [tuple(row) for row in conn.execute(text(f"SELECT * FROM {table} ORDER BY 1, 2"))]


def _crud(engine: Engine, workers: int = 2, **audit: Any) -> BulkCrud:
    return BulkCrud(
        engine,
        audit=AuditOptions(warn_if_disabled=False, **audit),
        parallel=ParallelOptions(max_workers=workers),
    )


class TestSerialByDefault:
    def test_without_parallel_options_nothing_changes(self, engine: Engine) -> None:
        crud = BulkCrud(engine, audit=AuditOptions(warn_if_disabled=False))
        crud.bulk_insert_from_df(_items(range(1, 6)), "items", generar_sql=False)
        assert len(_rows(engine)) == 5
        assert crud.last_parallel_result is None
        assert crud.parallel_plan("insert", 10**7).reasons == ("sin ParallelOptions: en serie",)

    def test_sqlite_stays_serial(self, engine: Engine) -> None:
        crud = _crud(engine, workers=4)
        crud.bulk_insert_from_df(_items(range(1, 6)), "items", generar_sql=False)
        assert len(_rows(engine)) == 5
        assert crud.last_parallel_result is None
        assert "un solo escritor" in crud.parallel_plan("insert", 5).reasons[0]


@pytest.mark.usefixtures("several_writers")
class TestParallelPath:
    def test_insert_in_partitions(self, engine: Engine) -> None:
        crud = _crud(engine)
        crud.bulk_insert_from_df(_items(range(1, 11)), "items", generar_sql=False)

        result = crud.last_parallel_result
        assert isinstance(result, ParallelLoadResult)
        assert result.total_rows == 10
        assert result.partition_errors == []
        assert result.plan is not None
        assert result.plan.workers == 2
        assert sorted(pr.rows for pr in result.partition_results) == [5, 5]
        assert [row[0] for row in _rows(engine)] == list(range(1, 11))

    def test_update_partitions_by_primary_key(self, engine: Engine) -> None:
        crud = _crud(engine)
        crud.bulk_insert_from_df(_items(range(1, 9)), "items", generar_sql=False)
        crud.bulk_update_from_df(_items(range(1, 9), value="y"), "items", generar_sql=False)

        assert {row[1] for row in _rows(engine)} == {f"y{i}" for i in range(1, 9)}
        assert crud.last_parallel_result is not None
        assert crud.last_parallel_result.total_rows == 8

    def test_delete_with_composite_primary_key_uses_hash(self, engine: Engine) -> None:
        crud = _crud(engine, workers=3)
        pairs = pd.DataFrame({"a": [1, 1, 2, 2, 3, 3], "b": list("xyxyxy"), "v": list("abcdef")})
        crud.bulk_insert_from_df(pairs, "pairs", generar_sql=False)
        crud.bulk_delete_from_df(pairs.iloc[:4][["a", "b"]], "pairs", generar_sql=False)

        assert _rows(engine, "pairs") == [(3, "x", "e"), (3, "y", "f")]

    def test_workers_get_the_packages_and_never_parallelize(self, engine: Engine) -> None:
        """G2 y T1: los workers reciben los paquetes de la instancia (antes se perdían opciones) y sin ``parallel``."""
        execution = ExecutionOptions(update_via_staging=False, strip_strings=False)
        crud = BulkCrud(engine, execution=execution, parallel=ParallelOptions(max_workers=2))
        with patch.object(pl_mod, "BulkCrud", wraps=BulkCrud) as spy:
            crud.bulk_insert_from_df(_items(range(1, 5)), "items", generar_sql=False)

        workers = [call for call in spy.call_args_list if call.kwargs.get("rejects") is not None]
        assert len(workers) == 2
        assert all(call.kwargs["execution"] is execution for call in workers)
        assert all(call.kwargs["parallel"] is None for call in workers)

    def test_failed_partition_raises_and_the_others_stay_committed(self, engine: Engine) -> None:
        crud = _crud(engine)
        crud.bulk_insert_from_df(_items([1]), "items", generar_sql=False)  # en serie: 1 fila
        with pytest.raises(ParallelLoadError) as info:
            crud.bulk_insert_from_df(_items(range(1, 9)), "items", generar_sql=False)  # la partición de 1..4 falla

        result = info.value.result
        assert result is crud.last_parallel_result
        assert len(result.partition_errors) == 1
        assert "quedaron confirmadas" in str(info.value)
        assert [row[0] for row in _rows(engine)] == [1, 5, 6, 7, 8]

    def test_audit_counters_include_the_workers(self, engine: Engine, tmp_path: Path) -> None:
        crud = _crud(engine, csv_path=tmp_path / "audit.csv")
        crud.bulk_insert_from_df(_items(range(1, 11)), "items", generar_sql=False)
        assert crud.audited_rows == 10
        assert crud.audit_failures == 0

    def test_generar_sql_stays_serial(self, engine: Engine, tmp_path: Path) -> None:
        crud = _crud(engine)
        crud.bulk_insert_from_df(_items(range(1, 5)), "items", generar_sql=True, path_sql=tmp_path)
        assert crud.last_parallel_result is None
        assert _rows(engine) == []

    def test_inside_bulk_session_stays_serial(self, engine: Engine) -> None:
        crud = _crud(engine)
        with crud.bulk_session():
            crud.bulk_insert_from_df(_items(range(1, 5)), "items", generar_sql=False)
        assert crud.last_parallel_result is None
        assert len(_rows(engine)) == 4

    def test_inside_rejects_scope_stays_serial(self, engine: Engine) -> None:
        """AUDIT_CODE: las particiones no continuarían la secuencia ni el presupuesto del ámbito."""
        crud = _crud(engine)
        with crud.rejects_scope(row_offset=10):
            crud.bulk_insert_from_df(_items(range(1, 5)), "items", generar_sql=False)
        assert crud.last_parallel_result is None
        assert len(_rows(engine)) == 4

    def test_update_with_repeated_keys_partitions_by_hash(self, engine: Engine) -> None:
        """AUDIT_CODE: los rangos cortan por posición; con claves repetidas, dos hilos tocarían la misma fila."""
        crud = _crud(engine)
        crud.bulk_insert_from_df(_items(range(1, 5)), "items", generar_sql=False)
        repeated = pd.DataFrame({"id": [1, 2, 2, 3, 4, 4], "v": list("abcdef")})
        with (
            patch.object(RangePartitioner, "partition_dataframe", wraps=RangePartitioner.partition_dataframe) as ranges,
            patch.object(HashPartitioner, "partition_dataframe", wraps=HashPartitioner.partition_dataframe) as hashes,
        ):
            crud.bulk_update_from_df(repeated, "items", generar_sql=False)
        ranges.assert_not_called()
        hashes.assert_called_once()
        assert crud.last_parallel_result is not None
        assert crud.last_parallel_result.partition_errors == []

    def test_partition_column_must_be_in_the_dataframe(self, engine: Engine) -> None:
        crud = BulkCrud(engine, parallel=ParallelOptions(max_workers=2, partition_column="nope"))
        with pytest.raises(ValueError, match="partition_column 'nope'"):
            crud.bulk_update_from_df(_items(range(1, 5)), "items", generar_sql=False)


def test_loader_on_sqlite_uses_one_worker_and_warns(engine: Engine, caplog: pytest.LogCaptureFixture) -> None:
    """v3.0.0: con SQLite y varios hilos, el loader daba ``database is locked``; ahora va en serie y avisa."""
    loader = pl_mod.ParallelBulkLoader(engine, parallel=ParallelOptions(max_workers=4))
    with caplog.at_level("WARNING", logger=pl_mod.__name__):
        result = loader.load("items", [lambda i=i: iter([_items([i])]) for i in range(1, 5)])
    assert result.total_rows == 4
    assert result.plan is not None
    assert result.plan.workers == 1
    assert "un solo escritor" in caplog.text


def test_loader_with_mode_off_is_serial_without_logging(engine: Engine, caplog: pytest.LogCaptureFixture) -> None:
    """AUDIT_CODE: con mode="off" un hilo es lo pedido; no se avisa de ningún recorte."""
    loader = pl_mod.ParallelBulkLoader(engine, parallel=ParallelOptions(mode="off"))
    with caplog.at_level("INFO", logger=pl_mod.__name__):
        result = loader.load("items", [lambda i=i: iter([_items([i])]) for i in range(1, 4)])
    assert result.plan is not None
    assert result.plan.workers == 1
    assert "en lugar de" not in caplog.text


class TestParallelFollowups:
    """Deuda D1/D2 tras v3.0.0 (sesión 2026-10-16g)."""

    def test_loader_checks_temp_once_per_instance(self) -> None:
        engine = MagicMock()
        engine.dialect.name = "postgresql"
        engine.pool.size = "x"
        loader = pl_mod.ParallelBulkLoader(engine)
        with patch.object(pl_mod.facts, "can_create_temp_tables", return_value=True) as check:
            assert loader._staging_update_available() is True
            assert loader._staging_update_available() is True
        assert check.call_count == 1

    def test_loader_uses_the_fact_passed_by_the_facade(self) -> None:
        engine = MagicMock()
        engine.dialect.name = "postgresql"
        engine.pool.size = "x"
        loader = pl_mod.ParallelBulkLoader(engine)
        loader._temp_tables_allowed = False
        with patch.object(pl_mod.facts, "can_create_temp_tables") as check:
            assert loader._staging_update_available() is False
        check.assert_not_called()
        engine.connect.assert_not_called()

    @pytest.mark.usefixtures("several_writers")
    def test_facade_hands_its_temp_fact_to_the_loader(self, engine: Engine) -> None:
        crud = _crud(engine)
        crud._temp_tables_allowed = True  # como si parallel_plan lo hubiera comprobado en PostgreSQL
        seen: list[bool | None] = []
        original = pl_mod.ParallelBulkLoader._run

        def spy(self: Any, *args: Any, **kwargs: Any) -> Any:
            seen.append(self._temp_tables_allowed)
            return original(self, *args, **kwargs)

        with patch.object(pl_mod.ParallelBulkLoader, "_run", spy):
            crud.bulk_insert_from_df(_items(range(1, 5)), "items", generar_sql=False)
        assert seen == [True]

    @pytest.mark.usefixtures("several_writers")
    def test_facade_does_not_repeat_the_audit_disabled_info(
        self, engine: Engine, caplog: pytest.LogCaptureFixture
    ) -> None:
        crud = _crud(engine)
        with caplog.at_level("INFO", logger=pl_mod.__name__):
            crud.bulk_insert_from_df(_items(range(1, 5)), "items", generar_sql=False)
        assert crud.last_parallel_result is not None
        assert "Auditoría deshabilitada" not in caplog.text

    def test_loader_alone_still_reports_disabled_audit(self, engine: Engine, caplog: pytest.LogCaptureFixture) -> None:
        loader = pl_mod.ParallelBulkLoader(engine, parallel=ParallelOptions(max_workers=1))
        with caplog.at_level("INFO", logger=pl_mod.__name__):
            loader.load("items", [lambda: iter([_items([1])])])
        assert "Auditoría deshabilitada" in caplog.text
