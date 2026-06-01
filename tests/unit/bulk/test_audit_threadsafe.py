"""Tests de seguridad ante concurrencia de la escritura de auditoría (bulk.audit)."""

from __future__ import annotations

import threading

from pathlib import Path

from util_bbdd.bulk._audit.repository import _get_file_lock
from util_bbdd.bulk.audit import AuditManager

_HEADER = "timestamp\ttabla\tmotor\toperacion\ttotal_filas\ttiempo_seg\tsql"


class TestFileLockRegistry:
    def test_same_path_returns_same_lock(self, tmp_path: Path) -> None:
        p = tmp_path / "a.csv"
        assert _get_file_lock(p) is _get_file_lock(p)

    def test_equivalent_paths_share_lock(self, tmp_path: Path) -> None:
        p = tmp_path / "a.csv"
        # Ruta con componente redundante "." → resuelve al mismo fichero
        p_alt = tmp_path / "." / "a.csv"
        assert _get_file_lock(p) is _get_file_lock(p_alt)

    def test_different_paths_get_different_locks(self, tmp_path: Path) -> None:
        assert _get_file_lock(tmp_path / "a.csv") is not _get_file_lock(tmp_path / "b.csv")


class TestConcurrentAuditWrites:
    def test_concurrent_writes_single_header_no_interleave(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "audit.csv"
        n_threads, per_thread = 8, 25

        def worker(idx: int) -> None:
            mgr = AuditManager(csv_path)  # instancia propia por hilo (como en el volcado paralelo)
            for j in range(per_thread):
                mgr.registrar_operacion(
                    tabla=f"t{idx}",
                    motor="postgresql",
                    operacion="INSERT",
                    rowcount=j,
                    elapsed=0.001,
                )

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        lines = csv_path.read_text(encoding="utf-8").splitlines()

        # Exactamente una cabecera, en la primera línea
        assert lines[0] == _HEADER
        assert sum(1 for line in lines if line == _HEADER) == 1

        data = lines[1:]
        # Todas las filas escritas, ninguna perdida ni intercalada
        assert len(data) == n_threads * per_thread
        # Cada fila tiene exactamente 7 campos tab-separados (sin líneas partidas)
        assert all(len(line.split("\t")) == 7 for line in data)

    def test_summary_readable_after_concurrent_writes(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "audit.csv"

        def worker(idx: int) -> None:
            mgr = AuditManager(csv_path)
            mgr.registrar_operacion(tabla=f"t{idx}", motor="mssql", operacion="INSERT", rowcount=10, elapsed=0.5)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        df = AuditManager(csv_path, cache_enabled=False).leer_auditoria()
        assert len(df) == 5
        assert int(df["total_filas"].sum()) == 50
