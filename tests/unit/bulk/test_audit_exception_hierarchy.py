"""La familia ``AuditError`` forma parte de la jerarquía canónica (``_core/exceptions.py``) desde v0.18.0."""

from __future__ import annotations

import pickle

import pytest

import util_bbdd.bulk as bulk_pkg
import util_bbdd.exceptions as public_exceptions

from util_bbdd._core import exceptions as core
from util_bbdd.bulk import audit as bulk_audit
from util_bbdd.bulk._audit import errors as audit_errors

pytestmark = pytest.mark.unit

NAMES = ["AuditError", "AuditConfigError", "AuditFileError", "AuditDataError", "AuditValidationError"]


@pytest.mark.parametrize("name", NAMES)
def test_every_import_path_gives_the_same_class(name: str) -> None:
    cls = getattr(core, name)
    assert getattr(audit_errors, name) is cls
    assert getattr(bulk_audit, name) is cls
    assert getattr(public_exceptions, name) is cls
    if name == "AuditError":
        assert bulk_pkg.AuditError is cls


@pytest.mark.parametrize("name", NAMES)
def test_audit_errors_are_database_exceptions(name: str) -> None:
    exc = getattr(core, name)("mensaje")
    assert isinstance(exc, core.AuditError)
    assert isinstance(exc, core.DatabaseException)
    assert str(exc) == "mensaje"  # sin operation/db_type/details, DatabaseException no añade texto


def test_audit_config_error_is_still_a_value_error() -> None:
    """H8: quien capturaba ValueError al validar la ruta del CSV sigue funcionando."""
    with pytest.raises(ValueError, match="ruta"):
        raise core.AuditConfigError("ruta no válida")


@pytest.mark.parametrize("name", NAMES)
def test_audit_errors_survive_pickle(name: str) -> None:
    """Las excepciones cruzan procesos (p. ej. concurrent.futures con procesos): pickle debe reconstruirlas."""
    exc = getattr(core, name)("mensaje")
    restored = pickle.loads(pickle.dumps(exc))
    assert type(restored) is type(exc)
    assert str(restored) == "mensaje"


def test_database_exception_handler_now_catches_audit_errors() -> None:
    with pytest.raises(core.DatabaseException):
        raise core.AuditValidationError("operación inválida")
