"""Tests de regresión para exports del paquete raíz util_bbdd [FND-04].

Antes de este fix, util_bbdd/__init__.py no exportaba ComparerError/DumpError
pese a que sus productores (SchemaComparator, DumpOrchestrator) sí son API
pública — un consumidor no podía hacer `except util_bbdd.DumpError` sin conocer
la ruta interna `util_bbdd.dump.DumpError` (o `util_bbdd._core.exceptions`).
"""

from __future__ import annotations

import util_bbdd


def test_comparer_error_hierarchy_exported() -> None:
    assert util_bbdd.ComparerError is not None
    assert issubclass(util_bbdd.SchemaDiffValidationError, util_bbdd.ComparerError)
    assert issubclass(util_bbdd.MetadataIntrospectionError, util_bbdd.ComparerError)
    assert issubclass(util_bbdd.DiffReportGenerationError, util_bbdd.ComparerError)


def test_dump_error_hierarchy_exported() -> None:
    assert util_bbdd.DumpError is not None
    assert issubclass(util_bbdd.DumpConstraintError, util_bbdd.DumpError)
    assert issubclass(util_bbdd.DumpReportError, util_bbdd.DumpError)


def test_comparer_error_is_database_exception() -> None:
    assert issubclass(util_bbdd.ComparerError, util_bbdd.DatabaseException)


def test_dump_error_is_database_exception() -> None:
    assert issubclass(util_bbdd.DumpError, util_bbdd.DatabaseException)


def test_new_exception_names_present_in_dunder_all() -> None:
    expected = {
        "ComparerError",
        "SchemaDiffValidationError",
        "MetadataIntrospectionError",
        "DiffReportGenerationError",
        "DumpError",
        "DumpConstraintError",
        "DumpReportError",
    }
    assert expected.issubset(set(util_bbdd.__all__))


def test_audit_module_exported() -> None:
    """Sesión 2026-10-02c: los destinos de auditoría se usan desde la raíz (BulkCrud/DumpConfig(audit_sink=...))."""
    from util_bbdd import audit

    for name in ("AuditEvent", "AuditSink", "JsonLinesAuditSink", "MemoryAuditSink", "NullAuditSink"):
        assert getattr(util_bbdd, name) is getattr(audit, name)
        assert name in util_bbdd.__all__
