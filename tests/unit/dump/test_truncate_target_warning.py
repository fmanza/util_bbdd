"""U-V7 (G30 de util_bbdd_web): ``FutureWarning`` si ``DumpConfig`` se construye sin ``truncate_target`` explícito."""

from __future__ import annotations

import dataclasses
import warnings

import pytest

from sqlalchemy import create_engine

from util_bbdd.dump import DumpConfig

pytestmark = pytest.mark.unit

ENGINE = create_engine("sqlite://")


def test_default_warns_and_keeps_true() -> None:
    with pytest.warns(FutureWarning, match="5.0.0") as caught:
        config = DumpConfig(ENGINE, ENGINE)

    assert config.truncate_target is True
    assert caught[0].filename == __file__  # apunta a quien construye el DumpConfig


@pytest.mark.parametrize("value", [True, False])
def test_explicit_value_does_not_warn(value: bool) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        config = DumpConfig(ENGINE, ENGINE, truncate_target=value)

    assert config.truncate_target is value


def test_default_reads_as_true_everywhere() -> None:
    (field,) = [f for f in dataclasses.fields(DumpConfig) if f.name == "truncate_target"]
    assert bool(field.default) and repr(field.default) == "True"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        implicit = DumpConfig(ENGINE, ENGINE)
    assert implicit == DumpConfig(ENGINE, ENGINE, truncate_target=True)
    assert "truncate_target=True" in repr(implicit)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        copy = dataclasses.replace(implicit, chunk_size=10)  # ya es un valor concreto: no repite el aviso
    assert copy.truncate_target is True


def test_manage_indexes_all_accepts_the_implicit_default() -> None:
    with pytest.warns(FutureWarning):
        config = DumpConfig(ENGINE, ENGINE, manage_indexes="all")
    assert config.truncate_target is True
