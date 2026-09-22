"""Tests para las exportaciones públicas de migrate/emitters/__init__.py."""

from __future__ import annotations

from util_bbdd.migrate import emitters


class TestEmittersPackageExports:
    """MIG-05 (AUDIT_CODE 2026-09-22): emitters/__init__.py solo exportaba DDLEmitter
    y MariaDBDDLEmitter; Oracle/PostgreSQL/SQL Server no eran importables desde el
    paquete emitters directamente (sí desde migrate de nivel superior)."""

    def test_all_four_emitters_importable_from_the_subpackage(self) -> None:
        assert emitters.DDLEmitter is not None
        assert emitters.MariaDBDDLEmitter is not None
        assert emitters.OracleDDLEmitter is not None
        assert emitters.PostgreSQLDDLEmitter is not None
        assert emitters.SQLServerDDLEmitter is not None

    def test_all_exports_match_dunder_all(self) -> None:
        expected = {
            "DDLEmitter",
            "MariaDBDDLEmitter",
            "OracleDDLEmitter",
            "PostgreSQLDDLEmitter",
            "SQLServerDDLEmitter",
        }
        assert set(emitters.__all__) == expected
        for name in expected:
            assert hasattr(emitters, name)
