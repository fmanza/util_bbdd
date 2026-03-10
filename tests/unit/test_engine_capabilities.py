"""Contrato de capacidades por motor."""

from util_bbdd.core.capabilities import DB_ASYNC_CAPABILITIES, is_async_supported


def test_async_capabilities_include_supported_motors() -> None:
    assert DB_ASYNC_CAPABILITIES["mariadb"] is True
    assert DB_ASYNC_CAPABILITIES["oracle"] is True
    assert DB_ASYNC_CAPABILITIES["postgresql"] is True
    assert DB_ASYNC_CAPABILITIES["sqlserver"] is True
    assert DB_ASYNC_CAPABILITIES["sqlite"] is True


def test_hsqldb_async_is_not_supported() -> None:
    assert DB_ASYNC_CAPABILITIES["hsqldb"] is False
    assert is_async_supported("hsqldb") is False


def test_unknown_engine_returns_none() -> None:
    assert is_async_supported("unknown_db") is None
