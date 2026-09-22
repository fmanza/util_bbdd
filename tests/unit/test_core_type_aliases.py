"""Tests de contrato para aliases compartidos en _core."""

from __future__ import annotations

from typing import get_args, get_origin

from util_bbdd._core.contracts import ConnectionProviderProtocol, ConnectionReleaserProtocol
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


class TestConnectionProtocolsDistinctFromCallbackAliases:
    """FND-05 (AUDIT_CODE 2026-09-22): _core.types.ConnectionProvider/ConnectionReleaser
    (alias Callable) y _core.contracts.ConnectionProviderProtocol/ConnectionReleaserProtocol
    (Protocol con método nombrado) antes compartían nombre y solo se distinguían por un
    alias de import (`as ...Protocol`) en _core/__init__.py; renombrados en el origen."""

    def test_callback_alias_and_protocol_are_different_objects(self) -> None:
        assert ConnectionProvider is not ConnectionProviderProtocol
        assert ConnectionReleaser is not ConnectionReleaserProtocol

    def test_protocol_requires_named_method_not_bare_callable(self) -> None:
        class BareCallableProvider:
            def __call__(self) -> object:
                return object()

        # Un callable plano NO satisface el Protocol (exige el método get_connection()).
        assert not isinstance(BareCallableProvider(), ConnectionProviderProtocol)

        class MethodProvider:
            def get_connection(self) -> object:
                return object()

        assert isinstance(MethodProvider(), ConnectionProviderProtocol)

    def test_releaser_protocol_requires_close_connection_method(self) -> None:
        class MethodReleaser:
            def close_connection(self, connection: object) -> None:
                pass

        assert isinstance(MethodReleaser(), ConnectionReleaserProtocol)

        class NotAReleaser:
            pass

        assert not isinstance(NotAReleaser(), ConnectionReleaserProtocol)

    def test_core_package_exports_both_without_collision(self) -> None:
        import util_bbdd._core as core

        assert core.ConnectionProvider is ConnectionProvider
        assert core.ConnectionReleaser is ConnectionReleaser
        assert core.ConnectionProviderProtocol is ConnectionProviderProtocol
        assert core.ConnectionReleaserProtocol is ConnectionReleaserProtocol
