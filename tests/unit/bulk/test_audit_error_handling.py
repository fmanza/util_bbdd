"""Política ante un fallo al escribir la auditoría (M-2, audit-code de AuditManager 2026-09-25).

- ``audit_strict=False`` (por defecto): la operación ya está en la BD; se registra un ERROR con los registros perdidos,
  se cuentan en ``BulkCrud.audit_failures`` y no se lanza nada. Antes se relanzaba y el llamador, al reintentar,
  duplicaba filas o chocaba con la PK.
- ``audit_strict=True``: se mantiene el comportamiento anterior [BLK-01]: el error se propaga y, dentro de una
  ``bulk_session`` atómica, deshace la sesión entera.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from sqlalchemy import Engine, create_engine, text

from util_bbdd.bulk._audit.errors import AuditError
from util_bbdd.bulk.crud import BulkCrud
from util_bbdd.bulk.options import AuditOptions


def _make_sqlite_engine() -> Engine:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
    return engine


def _count_rows(engine: Engine) -> int:
    with engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM items")).scalar_one()


class TestStrictAuditErrorPropagatesAndIsLogged:
    def test_audit_error_is_caught_logged_and_reraised(self, caplog: pytest.LogCaptureFixture) -> None:
        engine = _make_sqlite_engine()
        crud = BulkCrud(engine, audit=AuditOptions(strict=True))
        crud.audit_manager.registrar_operacion = MagicMock(side_effect=AuditError("boom auditoria"))

        df = pd.DataFrame({"id": [1], "name": ["a"]})

        with caplog.at_level("ERROR"):
            with pytest.raises(AuditError, match="boom auditoria"):
                crud.bulk_insert_from_df(df, "items", generar_sql=False)

        assert any("auditoría" in record.message.lower() for record in caplog.records)

    def test_os_error_from_audit_is_caught_logged_and_reraised(self, caplog: pytest.LogCaptureFixture) -> None:
        engine = _make_sqlite_engine()
        crud = BulkCrud(engine, audit=AuditOptions(strict=True))
        crud.audit_manager.registrar_operacion = MagicMock(side_effect=OSError("disk full"))

        df = pd.DataFrame({"id": [1], "name": ["a"]})

        with caplog.at_level("ERROR"):
            with pytest.raises(OSError, match="disk full"):
                crud.bulk_insert_from_df(df, "items", generar_sql=False)

        assert any("auditoría" in record.message.lower() for record in caplog.records)


class TestStrictAuditErrorInAtomicBulkSessionRollsBackTheSession:
    """Con ``audit_strict=True`` la auditoría de la sesión se escribe antes del commit: si falla, nada se confirma."""

    def test_audit_failure_rolls_back_every_operation_of_the_session(self, tmp_path: Path) -> None:
        engine = _make_sqlite_engine()
        crud = BulkCrud(engine, audit=AuditOptions(csv_path=tmp_path / "audit.csv", strict=True))
        crud.audit_manager._registrar_lote = MagicMock(side_effect=AuditError("boom al volcar la sesión"))  # type: ignore[method-assign]

        with pytest.raises(AuditError):
            with crud.bulk_session(atomic=True):
                crud.bulk_insert_from_df(pd.DataFrame({"id": [1], "name": ["a"]}), "items", generar_sql=False)
                crud.bulk_insert_from_df(pd.DataFrame({"id": [2], "name": ["b"]}), "items", generar_sql=False)

        assert _count_rows(engine) == 0
        assert crud.audit_failures == 0


class TestFailOpenByDefault:
    def test_audit_failure_outside_session_does_not_fail_the_committed_operation(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        engine = _make_sqlite_engine()
        crud = BulkCrud(engine)
        crud.audit_manager.registrar_operacion = MagicMock(side_effect=OSError("CSV bloqueado"))

        with caplog.at_level("ERROR"):
            crud.bulk_insert_from_df(pd.DataFrame({"id": [1, 2], "name": ["a", "b"]}), "items", generar_sql=False)

        assert _count_rows(engine) == 2
        assert crud.audit_failures == 1
        errors = [r.getMessage() for r in caplog.records if r.levelname == "ERROR"]
        assert len(errors) == 1
        assert "CSV bloqueado" in errors[0]
        assert "INSERT items filas=2" in errors[0]

    def test_audit_failure_inside_session_keeps_the_session_committed(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        engine = _make_sqlite_engine()
        crud = BulkCrud(engine, audit=AuditOptions(csv_path=tmp_path / "audit.csv"))
        crud.audit_manager._registrar_lote = MagicMock(side_effect=PermissionError("CSV abierto en Excel"))  # type: ignore[method-assign]

        with caplog.at_level("ERROR"):
            with crud.bulk_session(atomic=True):
                crud.bulk_insert_from_df(pd.DataFrame({"id": [1], "name": ["a"]}), "items", generar_sql=False)
                crud.bulk_insert_from_df(pd.DataFrame({"id": [2], "name": ["b"]}), "items", generar_sql=False)

        assert _count_rows(engine) == 2
        assert crud.audit_failures == 2
        assert any("Registros perdidos (2)" in r.getMessage() for r in caplog.records if r.levelname == "ERROR")

    def test_real_unwritable_csv_does_not_raise(self, tmp_path: Path) -> None:
        engine = _make_sqlite_engine()
        audit_path = tmp_path / "audit.csv"
        crud = BulkCrud(engine, audit=AuditOptions(csv_path=audit_path))
        audit_path.mkdir()  # el destino deja de poder abrirse como fichero

        crud.bulk_insert_from_df(pd.DataFrame({"id": [1], "name": ["a"]}), "items", generar_sql=False)

        assert _count_rows(engine) == 1
        assert crud.audit_failures == 1
