"""Rutas ``str`` en los parámetros de ruta de ``bulk`` (v1.1.0).

Hasta v1.0.0 la firma decía ``Path`` y un ``str`` fallaba: ``audit_csv_path`` con ``AuditConfigError: 'str' object has
no attribute 'parent'`` (``BulkCrud``, ``ParallelBulkLoader``) y ``path_sql`` con ``ValueError`` explícito.
"""

from __future__ import annotations

import csv

from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

from sqlalchemy import Engine, create_engine, text

from util_bbdd.bulk import BulkCrud, ParallelBulkLoader
from util_bbdd.bulk.audit import AuditConfigError, AuditManager
from util_bbdd.bulk.options import AuditOptions, BatchOptions, ParallelOptions, RejectOptions

pytestmark = pytest.mark.unit


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    eng = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    with eng.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE items (id INTEGER PRIMARY KEY, v TEXT NOT NULL)")
    yield eng
    eng.dispose()


def _frame(ids: list[int]) -> pd.DataFrame:
    return pd.DataFrame({"id": ids, "v": [f"v{i}" for i in ids]})


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=_delimiter(path)))


def _delimiter(path: Path) -> str:
    header = path.read_text(encoding="utf-8").splitlines()[0]
    return "\t" if "\t" in header else (";" if ";" in header else ",")


class TestBulkCrud:
    def test_audit_csv_path_str_writes_the_audit(self, engine: Engine, tmp_path: Path) -> None:
        audit = tmp_path / "sub" / "audit.csv"

        crud = BulkCrud(engine, audit=AuditOptions(csv_path=str(audit)))
        crud.bulk_insert_from_df(_frame([1, 2]), "items", generar_sql=False)

        assert crud.audit_manager.audit_csv_path == audit
        assert isinstance(crud.audit_manager.audit_csv_path, Path)
        assert len(_rows(audit)) == 1

    def test_relative_str_is_relative_to_the_working_directory(
        self, engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        BulkCrud(engine, audit=AuditOptions(csv_path="rel/audit.csv")).bulk_insert_from_df(
            _frame([1]), "items", generar_sql=False
        )

        assert (tmp_path / "rel" / "audit.csv").is_file()

    def test_rejects_csv_path_str(self, engine: Engine, tmp_path: Path) -> None:
        rejects = tmp_path / "rejects.csv"
        crud = BulkCrud(engine, rejects=RejectOptions(on_error="isolate", csv_path=str(rejects)))

        crud.bulk_insert_from_df(_frame([1, 1]), "items", generar_sql=False)

        assert crud.rows_rejected == 1
        assert rejects.is_file()

    @pytest.mark.parametrize("operation", ["insert", "update", "delete"])
    def test_path_sql_str_writes_the_sql_file(self, engine: Engine, tmp_path: Path, operation: str) -> None:
        folder = tmp_path / "sql"
        method = getattr(BulkCrud(engine), f"bulk_{operation}_from_df")

        method(_frame([1]), "items", generar_sql=True, path_sql=str(folder))

        assert [p.suffix for p in folder.iterdir()] == [".sql"]

    @pytest.mark.parametrize("parameter", ["audit", "rejects"])
    def test_other_types_raise_value_error(self, engine: Engine, parameter: str) -> None:
        with pytest.raises(ValueError, match=rf"{parameter}\.csv_path debe ser una ruta"):
            if parameter == "audit":
                BulkCrud(engine, audit=AuditOptions(csv_path=123))  # type: ignore[arg-type]
            else:
                BulkCrud(engine, rejects=RejectOptions(on_error="isolate", csv_path=123))  # type: ignore[arg-type]


class TestParallelBulkLoader:
    def test_audit_and_rejects_str(self, engine: Engine, tmp_path: Path) -> None:
        audit, rejects = tmp_path / "audit.csv", tmp_path / "rejects.csv"
        loader = ParallelBulkLoader(
            engine,
            batch=BatchOptions(chunk_size=10),
            audit=AuditOptions(csv_path=str(audit)),
            rejects=RejectOptions(on_error="isolate", csv_path=str(rejects)),
            parallel=ParallelOptions(max_workers=1),
        )

        result = loader.load("items", [lambda: iter([_frame([1, 2])]), lambda: iter([_frame([2, 3])])])

        assert result.partition_errors == []
        assert audit.is_file()
        assert rejects.is_file()
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM items")).scalar_one() == 3

    def test_invalid_audit_path_type_fails_before_loading(self, engine: Engine) -> None:
        with pytest.raises(ValueError, match=r"audit\.csv_path debe ser una ruta"):
            ParallelBulkLoader(engine, audit=AuditOptions(csv_path=123))  # type: ignore[arg-type]


class TestAuditManager:
    def test_constructor_and_setter_accept_str(self, tmp_path: Path) -> None:
        manager = AuditManager(str(tmp_path / "a.csv"))
        assert manager.audit_csv_path == tmp_path / "a.csv"

        manager.audit_csv_path = str(tmp_path / "b.csv")  # type: ignore[assignment]
        assert manager.audit_csv_path == tmp_path / "b.csv"

        manager.audit_csv_path = None
        assert manager.audit_csv_path is None

    def test_invalid_type_is_audit_config_error(self) -> None:
        with pytest.raises(AuditConfigError, match="audit_csv_path debe ser una ruta"):
            AuditManager(123)  # type: ignore[arg-type]

        manager = AuditManager(None, warn_if_disabled=False)
        with pytest.raises(AuditConfigError):
            manager.audit_csv_path = 123  # type: ignore[assignment]
