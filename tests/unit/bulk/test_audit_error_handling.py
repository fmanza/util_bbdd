"""Tests de regresión para el manejo de AuditError/OSError en __run_bulk_pipeline [BLK-01].

Antes de este fix, un fallo del subsistema de auditoría (`AuditError`, que hereda de
`Exception`, no de `SQLAlchemyError`/`ValueError`) tras un `execute()` ya comprometido
no era capturado por ningún `except` de `__run_bulk_pipeline`. Dentro de
`bulk_session(atomic=True)`, al compartir una única transacción entre chunks, esto
provoca el rollback de operaciones previas ya ejecutadas en la misma sesión.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from sqlalchemy import Engine, create_engine, text

from util_bbdd.bulk._audit.errors import AuditError
from util_bbdd.bulk.crud import BulkCrud


def _make_sqlite_engine() -> Engine:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
    return engine


def _count_rows(engine: Engine) -> int:
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM items")).scalar_one()


class TestAuditErrorPropagatesAndIsLogged:
    def test_audit_error_is_caught_logged_and_reraised(self, caplog: pytest.LogCaptureFixture) -> None:
        engine = _make_sqlite_engine()
        crud = BulkCrud(engine)
        crud.audit_manager.registrar_operacion = MagicMock(side_effect=AuditError("boom auditoria"))

        df = pd.DataFrame({"id": [1], "name": ["a"]})

        with caplog.at_level("ERROR"):
            with pytest.raises(AuditError, match="boom auditoria"):
                crud.bulk_insert_from_df(df, "items", generar_sql=False)

        assert any("auditoría" in record.message.lower() for record in caplog.records)

    def test_os_error_from_audit_is_caught_logged_and_reraised(self, caplog: pytest.LogCaptureFixture) -> None:
        engine = _make_sqlite_engine()
        crud = BulkCrud(engine)
        crud.audit_manager.registrar_operacion = MagicMock(side_effect=OSError("disk full"))

        df = pd.DataFrame({"id": [1], "name": ["a"]})

        with caplog.at_level("ERROR"):
            with pytest.raises(OSError, match="disk full"):
                crud.bulk_insert_from_df(df, "items", generar_sql=False)

        assert any("auditoría" in record.message.lower() for record in caplog.records)


class TestAuditErrorInAtomicBulkSessionRollsBackPreviousChunks:
    """Documenta el riesgo residual anotado en el docstring de bulk_session(): un fallo
    de auditoría a mitad de una sesión atómica deshace TODOS los chunks de la sesión,
    no solo el que falló."""

    def test_audit_failure_on_second_chunk_rolls_back_first_chunk_too(self) -> None:
        engine = _make_sqlite_engine()
        crud = BulkCrud(engine)

        original_registrar = crud.audit_manager.registrar_operacion
        call_count = {"n": 0}

        def _flaky_registrar(*args: object, **kwargs: object) -> None:
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise AuditError("boom en el segundo chunk")
            original_registrar(*args, **kwargs)

        crud.audit_manager.registrar_operacion = _flaky_registrar

        with pytest.raises(AuditError):
            with crud.bulk_session(atomic=True):
                crud.bulk_insert_from_df(pd.DataFrame({"id": [1], "name": ["a"]}), "items", generar_sql=False)
                crud.bulk_insert_from_df(pd.DataFrame({"id": [2], "name": ["b"]}), "items", generar_sql=False)

        # La sesión completa (ambos chunks) se deshace, aunque el primero se auditó bien.
        assert _count_rows(engine) == 0
