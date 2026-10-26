"""Las excepciones se presentan con su ruta pública ``util_bbdd.exceptions`` (v0.44.0).

La implementación vive en ``util_bbdd._core.exceptions``, pero trazas, ``repr``, logs y pickle usan la ruta pública.
Los pickles creados con ≤ 0.43 (ruta ``_core``) se siguen cargando.
"""

from __future__ import annotations

import pickle
import subprocess
import sys
import traceback

import pytest

import util_bbdd._core.exceptions as core
import util_bbdd.exceptions as public

pytestmark = pytest.mark.unit

ALL_EXCEPTIONS: list[type[core.DatabaseException]] = sorted(
    (v for v in vars(core).values() if isinstance(v, type) and issubclass(v, core.DatabaseException)),
    key=lambda cls: cls.__name__,
)

# pickle.dumps(QueryError("antiguo"), protocol=4) generado con el código del tag v0.43.0 (git archive): ruta _core.
PICKLE_FROM_0_43 = (
    b"\x80\x04\x95y\x00\x00\x00\x00\x00\x00\x00\x8c\x1autil_bbdd._core.exceptions\x94\x8c\nQueryError\x94\x93\x94"
    b"\x8c\x07antiguo\x94\x85\x94R\x94}\x94(\x8c\x07message\x94h\x03\x8c\toperation\x94\x8c\x07UNKNOWN\x94\x8c\x07"
    b"db_type\x94h\t\x8c\x07details\x94Nub."
)


def test_all_exceptions_are_found() -> None:
    assert (
        len(ALL_EXCEPTIONS) == len(public.__all__) == 43
    )  # MigrationPlanValidationError y MigrationStatementError, v4.3.0


@pytest.mark.parametrize("cls", ALL_EXCEPTIONS, ids=lambda cls: cls.__name__)
def test_exception_reports_public_module(cls: type[core.DatabaseException]) -> None:
    assert cls.__module__ == "util_bbdd.exceptions"
    assert getattr(public, cls.__name__) is cls


@pytest.mark.parametrize("cls", ALL_EXCEPTIONS, ids=lambda cls: cls.__name__)
def test_pickle_round_trip_uses_public_path(cls: type[core.DatabaseException]) -> None:
    exc = cls("mensaje")
    payload = pickle.dumps(exc)
    assert b"util_bbdd.exceptions" in payload
    assert b"_core" not in payload
    restored = pickle.loads(payload)
    assert type(restored) is cls
    assert str(restored) == str(exc)


def test_pickle_round_trip_keeps_context() -> None:
    restored = pickle.loads(pickle.dumps(public.QueryError("x", operation="SELECT", db_type="oracle")))
    assert (restored.operation, restored.db_type) == ("SELECT", "oracle")


def test_pickle_from_0_43_still_loads() -> None:
    restored = pickle.loads(PICKLE_FROM_0_43)
    assert type(restored) is public.QueryError
    assert restored.message == "antiguo"


def test_traceback_shows_public_path() -> None:
    line = traceback.format_exception_only(public.QueryNotFoundError("q"))[0]
    assert line.startswith("util_bbdd.exceptions.QueryNotFoundError: q")


def test_pickle_works_when_only_the_internal_module_is_imported() -> None:
    """Importar ``util_bbdd._core.exceptions`` carga antes el paquete, que carga ``util_bbdd.exceptions``."""
    code = (
        "import pickle\n"
        "from util_bbdd._core.exceptions import QueryError\n"
        "print(type(pickle.loads(pickle.dumps(QueryError('x')))).__module__)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip()
    assert out == "util_bbdd.exceptions"
