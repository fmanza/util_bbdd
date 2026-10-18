"""Tests de ``util_bbdd._core.timing``: decorador ``medir_tiempo`` y formato de duraciones."""

from __future__ import annotations

import functools
import logging

from collections.abc import AsyncIterator, Callable, Iterator

import pytest

from util_bbdd._core.timing import _format_seconds, medir_tiempo

LOGGER_NAME = __name__  # el decorador registra en el logger del módulo de la función decorada


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "00:00:00.000"),
        (0.0004, "00:00:00.000"),
        (1.5, "00:00:01.500"),
        (59.9996, "00:01:00.000"),  # redondeo antes de repartir: nunca "00:00:60.000"
        (3661, "01:01:01.000"),
        (86_399.9999, "1 día 00:00:00.000"),
        (86_461, "1 día 00:01:01.000"),
        (2 * 86_400 + 3, "2 días 00:00:03.000"),
    ],
)
def test_format_seconds(seconds: float, expected: str) -> None:
    assert _format_seconds(seconds) == expected


def test_returns_result_and_logs_with_function_name(caplog: pytest.LogCaptureFixture) -> None:
    @medir_tiempo()
    def sumar(a: int, b: int = 1) -> int:
        return a + b

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        assert sumar(2, b=3) == 5

    [record] = [r for r in caplog.records if r.name == LOGGER_NAME]
    assert record.levelno == logging.INFO
    assert record.getMessage().startswith("⏱️  Tiempo ejecución de sumar: 00:00:")
    assert "(con error)" not in record.getMessage()


def test_custom_process_name_and_level(caplog: pytest.LogCaptureFixture) -> None:
    @medir_tiempo("carga diaria", level=logging.DEBUG)
    def cargar() -> None:
        return None

    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        cargar()

    [record] = [r for r in caplog.records if r.name == LOGGER_NAME]
    assert record.levelno == logging.DEBUG
    assert "Tiempo ejecución de carga diaria:" in record.getMessage()


def test_exception_propagates_and_is_logged_as_error(caplog: pytest.LogCaptureFixture) -> None:
    @medir_tiempo()
    def fallar() -> None:
        raise ValueError("boom")

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME), pytest.raises(ValueError, match="boom"):
        fallar()

    [record] = [r for r in caplog.records if r.name == LOGGER_NAME]
    assert record.getMessage().endswith("(con error)")


def test_disabled_level_logs_nothing(caplog: pytest.LogCaptureFixture) -> None:
    @medir_tiempo(level=logging.DEBUG)
    def cargar() -> int:
        return 7

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        assert cargar() == 7

    assert not [r for r in caplog.records if r.name == LOGGER_NAME]


def test_preserves_function_metadata() -> None:
    def original(x: int) -> int:
        """Docstring original."""
        return x

    decorated = medir_tiempo()(original)

    assert decorated.__name__ == "original"
    assert decorated.__doc__ == "Docstring original."
    assert decorated.__wrapped__ is original  # type: ignore[attr-defined]


async def _coroutine() -> None:
    return None


def _generator() -> Iterator[int]:
    yield 1


async def _async_generator() -> AsyncIterator[int]:
    yield 1


@pytest.mark.parametrize("function", [_coroutine, _generator, _async_generator])
def test_rejects_functions_that_return_lazy_objects(function: Callable[[], object]) -> None:
    """Llamarlas solo crea la corrutina o el generador: se mediría su creación, no su ejecución."""
    with pytest.raises(TypeError, match=f"no admite funciones async ni generadores .*: {function.__name__}"):
        medir_tiempo()(function)


def test_rejects_partial_of_async_function() -> None:
    async def consulta(limite: int) -> int:
        return limite

    with pytest.raises(TypeError, match=": partial$"):
        medir_tiempo()(functools.partial(consulta, 1))


def test_accepts_callables_without_name(caplog: pytest.LogCaptureFixture) -> None:
    """``functools.partial`` y las instancias con ``__call__`` no tienen ``__name__``."""

    class Contador:
        def __call__(self) -> int:
            return 3

    parse_binary = medir_tiempo()(functools.partial(int, base=2))
    contar = medir_tiempo("contar")(Contador())

    with caplog.at_level(logging.INFO):
        assert parse_binary("11") == 3
        assert contar() == 3

    messages = [r.getMessage() for r in caplog.records]
    assert any("Tiempo ejecución de partial:" in m for m in messages)
    assert any("Tiempo ejecución de contar:" in m for m in messages)


def test_bulk_crud_logs_timing_in_util_bbdd_hierarchy(caplog: pytest.LogCaptureFixture) -> None:
    """Sin el paquete externo ``util``, BulkCrud mide igualmente y lo registra bajo ``util_bbdd``."""
    import pandas as pd

    from sqlalchemy import create_engine, text

    from util_bbdd import BulkCrud

    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, nombre TEXT)"))
        crud = BulkCrud(engine=engine)

        with caplog.at_level(logging.INFO, logger="util_bbdd"):
            crud.bulk_insert_from_df(pd.DataFrame({"id": [1, 2], "nombre": ["a", "b"]}), "t", generar_sql=False)
    finally:
        engine.dispose()

    messages = [r.getMessage() for r in caplog.records if r.name == "util_bbdd.bulk.crud"]
    assert any(m.startswith("⏱️  Tiempo ejecución de bulk_insert_from_df: ") for m in messages)
