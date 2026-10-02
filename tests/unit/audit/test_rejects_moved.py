"""F2 (sesión 2026-10-02c): el CSV de rechazos vive en ``util_bbdd.audit.rejects``; ``bulk`` conserva ``Isolator``."""

from __future__ import annotations

import logging

from pathlib import Path

import pytest

from sqlalchemy.exc import IntegrityError

from util_bbdd.audit import locks, rejects
from util_bbdd.audit.text import AuditText
from util_bbdd.bulk._support import rejects as bulk_rejects


def _error() -> IntegrityError:
    return IntegrityError("INSERT ...", {}, Exception("UNIQUE constraint failed: t.id"))


def test_bulk_re_exporta_el_escritor() -> None:
    assert bulk_rejects.RejectsWriter is rejects.RejectsWriter
    assert bulk_rejects.REJECT_COLUMNS is rejects.REJECT_COLUMNS


def test_comparte_el_lock_con_la_auditoria(tmp_path: Path) -> None:
    writer = rejects.RejectsWriter(tmp_path / "r.csv")
    assert writer._lock is locks.path_lock(tmp_path / "r.csv")


def test_aparta_fichero_ajeno_con_el_logger_de_siempre(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    path = tmp_path / "r.csv"
    path.write_text("a,b,c\n1,2,3\n", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="util_bbdd.bulk._support.rejects"):
        rejects.RejectsWriter(path).write(table="t", operation="INSERT", position=0, error=_error(), values={"id": 1})

    apartados = list(tmp_path.glob("r.invalid-*.csv"))
    assert len(apartados) == 1
    assert apartados[0].read_text(encoding="utf-8") == "a,b,c\n1,2,3\n"
    assert path.read_text(encoding="utf-8").splitlines()[0] == "\t".join(rejects.REJECT_COLUMNS)
    assert any("se ha apartado" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("prefix", AuditText.FORMULA_PREFIXES)
def test_safe_csv_cell_neutraliza_formulas(prefix: str) -> None:
    assert AuditText.safe_csv_cell(f"{prefix}1") == f"'{prefix}1"


def test_safe_csv_cell_deja_el_resto() -> None:
    assert AuditText.safe_csv_cell("tabla") == "tabla"
    assert AuditText.safe_csv_cell("") == ""


def test_error_summary_solo_primera_linea_del_driver() -> None:
    error = IntegrityError("INSERT INTO t VALUES (?)", {"secreto": 1}, Exception("línea 1\nlínea 2"))

    assert AuditText.error_summary(error) == "IntegrityError: línea 1"
    assert AuditText.error_summary(ValueError("")) == "ValueError: "
