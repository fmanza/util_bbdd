"""Tests de contrato para aliases compartidos en _core."""

from __future__ import annotations

from typing import get_args, get_origin

from util_bbdd._core.types import ConnectionProvider, ConnectionReleaser, QueryResult, Row, RowOrNone, Rows


def test_row_aliases_keep_expected_shape() -> None:
    assert get_origin(Row) is tuple
    assert get_origin(Rows) is list
    assert get_args(Rows) == (Row,)
    assert RowOrNone == Row | None
    assert QueryResult == RowOrNone | Rows


def test_connection_callback_aliases_are_callable() -> None:
    def provider() -> object:
        return object()

    typed_provider: ConnectionProvider = provider
    released: list[object] = []

    def releaser(connection: object) -> None:
        released.append(connection)

    connection = typed_provider()
    typed_releaser: ConnectionReleaser = releaser
    typed_releaser(connection)

    assert released == [connection]
