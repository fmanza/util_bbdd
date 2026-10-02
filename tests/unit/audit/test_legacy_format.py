"""El formato de los CSV de auditoría y de rechazos queda congelado (regla 4 del prompt ``audit_module``).

Los ficheros de ``tests/fixtures/audit/`` se generaron con el código de v0.28.0, antes de mover la auditoría a
``util_bbdd.audit``. Estos tests escriben lo mismo por la API de siempre y comparan byte a byte: cualquier cambio de
columnas, orden, separador, fin de línea, formato de fecha, coma decimal o ``Sí``/``No`` los rompe.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from util_bbdd.bulk._audit.record import AuditRecord
from util_bbdd.bulk._support.rejects import RejectsWriter
from util_bbdd.bulk.audit import AuditManager

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "audit"

RECORDS = [
    AuditRecord("clientes", "postgresql", "INSERT", 1000, 0.42, False, datetime(2026, 10, 2, 9, 30, 1, 999999)),
    AuditRecord("pedidos_línea", "oracle", "UPDATE", 0, 0.0, False, datetime(2026, 10, 2, 9, 30, 2)),
    AuditRecord("=HYPERLINK(x)", "sqlite", "DELETE", 7, 12.3456, True, datetime(2026, 10, 2, 23, 59, 59)),
]


def test_csv_de_auditoria_identico_a_v0_28_0(tmp_path: Path) -> None:
    path = tmp_path / "auditoria.csv"
    manager = AuditManager(path, cache_enabled=False)
    manager._registrar_lote(RECORDS[:2])
    manager._registrar_lote(RECORDS[2:])

    assert path.read_bytes() == (FIXTURES / "legacy_audit_v0_28_0.csv").read_bytes()


def test_csv_de_rechazos_identico_a_v0_28_0(tmp_path: Path) -> None:
    path = tmp_path / "rechazos.csv"
    writer = RejectsWriter(path)
    error = IntegrityError("INSERT ...", {}, Exception("UNIQUE constraint failed: t.id\nsegunda línea"))
    writer.write(table="t", operation="INSERT", position=3, error=error, values={"id": 1, "txt": "=1+1", "n": None})
    writer.write(table="+tabla", operation="UPDATE", position=0, error=error, values={"id": 2}, partition=1)

    # La columna timestamp es la hora de escritura: se sustituye por "TS", como en el fichero de referencia.
    lines = path.read_bytes().split(b"\r\n")
    normalized = b"\r\n".join([lines[0]] + [b"TS" + line[line.index(b"\t") :] if line else line for line in lines[1:]])

    assert normalized == (FIXTURES / "legacy_rejects_v0_28_0.csv").read_bytes()


def test_lectura_del_csv_de_referencia() -> None:
    frame = AuditManager(FIXTURES / "legacy_audit_v0_28_0.csv", cache_enabled=False).leer_auditoria()

    assert list(frame.columns) == ["timestamp", "tabla", "motor", "operacion", "total_filas", "tiempo_seg", "sql"]
    assert frame["tiempo_seg"].tolist() == [0.42, 0.0, 12.346]
    assert frame["sql"].tolist() == ["No", "No", "Sí"]
