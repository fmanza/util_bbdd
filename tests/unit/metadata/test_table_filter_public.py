"""5.9.0: ``TableFilter`` público en ``util_bbdd.metadata`` (lo comparten doc, migrate y dump)."""

from __future__ import annotations

from typing import Any

import pytest

from util_bbdd.doc.domain import table_filter as doc_table_filter
from util_bbdd.metadata import TableFilter
from util_bbdd.metadata.table_filter import FILTER_KEY

pytestmark = pytest.mark.unit


def test_doc_reexports_the_same_class() -> None:
    assert doc_table_filter.TableFilter is TableFilter
    assert doc_table_filter.FILTER_KEY == FILTER_KEY == "filtro"


def test_from_patterns_accepts_lists_strings_and_generators() -> None:
    f = TableFilter.from_patterns(include=(p for p in [" MVG_* ", "MVG_*", "COB_*"]), exclude="*_BAK")
    assert f == TableFilter(("MVG_*", "COB_*"), ("*_BAK",), True)
    assert f.matches("mvg_pedido")
    assert not f.matches("MVG_PEDIDO_BAK")
    assert not f.matches("AUX_LOG")


@pytest.mark.parametrize("include, exclude", [(None, None), ([], ()), (None, [])])
def test_from_patterns_without_patterns_is_none(include: Any, exclude: Any) -> None:
    assert TableFilter.from_patterns(include, exclude) is None


@pytest.mark.parametrize(
    "include",
    [[""], ["   "], ["x" * 129], ["A\nB"], [1], [f"P{i}" for i in range(101)]],
)
def test_from_patterns_validates_like_from_config(include: Any) -> None:
    with pytest.raises(ValueError, match="incluir"):
        TableFilter.from_patterns(include=include)


def test_from_patterns_equals_from_config() -> None:
    assert TableFilter.from_patterns(["A*"], ["B*"]) == TableFilter.from_config({"incluir": ["A*"], "excluir": ["B*"]})
