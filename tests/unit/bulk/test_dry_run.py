"""U-B3 (G35 de util_bbdd_web): ``dry_run`` explícito y ``FutureWarning`` si no se pasa ni ``generar_sql`` ni ``dry_run``."""

from __future__ import annotations

import warnings

from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest

from sqlalchemy import Engine, create_engine, text

from util_bbdd.bulk import BulkCrud
from util_bbdd.bulk.options import AuditOptions

pytestmark = pytest.mark.unit

METHODS = ["bulk_insert_from_df", "bulk_update_from_df", "bulk_delete_from_df"]


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE items (id INTEGER PRIMARY KEY, v TEXT)"))
        conn.execute(text("INSERT INTO items VALUES (1, 'a'), (2, 'b')"))
    yield engine
    engine.dispose()


@pytest.fixture
def crud(engine: Engine) -> BulkCrud:
    return BulkCrud(engine, audit=AuditOptions(warn_if_disabled=False))


DF = pd.DataFrame({"id": [1, 2, 3], "v": ["x", "y", "z"]})


def _rows(engine: Engine) -> list[tuple[int, str]]:
    with engine.connect() as conn:
        return [(int(r[0]), str(r[1])) for r in conn.execute(text("SELECT id, v FROM items ORDER BY id"))]


@pytest.mark.parametrize("method", METHODS)
def test_no_argument_warns_and_writes_sql(crud: BulkCrud, engine: Engine, tmp_path: Path, method: str) -> None:
    df = DF if method == "bulk_insert_from_df" else DF.iloc[:2]
    with pytest.warns(FutureWarning, match="5.0.0") as caught:
        getattr(crud, method)(df, "items", path_sql=tmp_path)

    assert caught[0].filename == __file__  # apunta a quien llama, no a util_bbdd
    assert method in str(caught[0].message)
    assert _rows(engine) == [(1, "a"), (2, "b")]  # no ejecuta
    assert len(list(tmp_path.glob("*.sql"))) == 1


@pytest.mark.parametrize("method", METHODS)
def test_dry_run_true_writes_sql_without_touching_the_db(
    crud: BulkCrud, engine: Engine, tmp_path: Path, method: str
) -> None:
    df = DF if method == "bulk_insert_from_df" else DF.iloc[:2]
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        getattr(crud, method)(df, "items", path_sql=tmp_path, dry_run=True)

    assert _rows(engine) == [(1, "a"), (2, "b")]
    assert len(list(tmp_path.glob("*.sql"))) == 1
    assert crud.rows_committed == 0


def test_dry_run_false_executes(crud: BulkCrud, engine: Engine) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        crud.bulk_insert_from_df(DF.iloc[2:], "items", dry_run=False)
        crud.bulk_update_from_df(DF.iloc[:1], "items", dry_run=False)
        crud.bulk_delete_from_df(DF.iloc[1:2], "items", dry_run=False)

    assert _rows(engine) == [(1, "x"), (3, "z")]


@pytest.mark.parametrize("value", [True, False])
def test_explicit_generar_sql_does_not_warn(crud: BulkCrud, tmp_path: Path, value: bool) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        crud.bulk_insert_from_df(DF.iloc[2:], "items", value, tmp_path)  # posicional, como hasta ahora
        crud.bulk_delete_from_df(DF.iloc[2:], "items", generar_sql=value, path_sql=tmp_path, dry_run=value)


def test_contradictory_values_raise(crud: BulkCrud, engine: Engine) -> None:
    with pytest.raises(ValueError, match="se contradicen"):
        crud.bulk_insert_from_df(DF, "items", generar_sql=False, dry_run=True)
    assert _rows(engine) == [(1, "a"), (2, "b")]


def test_dry_run_is_keyword_only(crud: BulkCrud) -> None:
    with pytest.raises(TypeError):
        crud.bulk_update_from_df(DF, "items", None, None, True)  # type: ignore[call-arg]
