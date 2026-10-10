"""Superficie pública de la raíz ``util_bbdd`` (API 1.0, fase 0.43.0).

Fija los 13 símbolos de ``util_bbdd.__all__``, la carga perezosa de los puntos de entrada pesados y los 46 alias
deprecados que la raíz exportaba hasta 0.42: cada uno avisa con ``DeprecationWarning``, nombra su ruta nueva y devuelve
el mismo objeto que esa ruta (un ``except util_bbdd.QueryError`` sigue capturando lo mismo).
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import warnings

import pytest

import util_bbdd
import util_bbdd._core.exceptions as core_exceptions
import util_bbdd.exceptions as public_exceptions

ROOT_API: list[str] = [
    "SyncDatabaseManager",
    "AsyncDatabaseManager",
    "BulkCrud",
    "ParallelBulkLoader",
    "DumpOrchestrator",
    "DumpConfig",
    "DumpResult",
    "MigrationPlanner",
    "MigrationPlan",
    "SchemaComparator",
    "SchemaDiff",
    "DatabaseDocumentation",
    "DatabaseException",
]

# Los 46 nombres que salen de la raíz en 0.43.0 y el submódulo público que los exporta desde ahora.
DEPRECATED: dict[str, str] = {
    **dict.fromkeys(
        (
            "ConnectionError",
            "PoolConnectionError",
            "PoolExhaustedError",
            "PoolTimeoutError",
            "DriverError",
            "ValidationError",
            "InvalidDatabaseType",
            "DatabaseOperationError",
            "DatabaseConfigurationError",
            "QueryError",
            "QueryNotFoundError",
            "QueryValidationError",
            "QueryParameterError",
            "QueryTimeoutError",
            "QueryExecutionError",
            "ComparerError",
            "SchemaDiffValidationError",
            "MetadataIntrospectionError",
            "DiffReportGenerationError",
            "DumpError",
            "DumpConstraintError",
            "DumpReportError",
            "AuditError",
            "AuditConfigError",
            "AuditFileError",
            "AuditDataError",
            "AuditExportError",
            "AuditValidationError",
            "DocumentationError",
            "DocumentationConfigError",
            "DocumentationRenderError",
        ),
        "exceptions",
    ),
    **dict.fromkeys(("AuditEvent", "AuditSink", "JsonLinesAuditSink", "MemoryAuditSink", "NullAuditSink"), "audit"),
    **dict.fromkeys(("SyncMetadataProvider", "AsyncMetadataProvider"), "metadata"),
    **dict.fromkeys(("build_conn_params", "EngineReadinessAdvisor", "AdvisoryFinding"), "connection"),
    **dict.fromkeys(("ConnectionFactory", "PoolFactory"), "factory"),
    "maybe_await": "async_utils",
    "TableDumpResult": "dump",
    "MigrationWarning": "migrate",
}


def test_root_all_is_the_1_0_surface() -> None:
    assert util_bbdd.__all__ == ROOT_API


def test_deprecated_table_matches_the_package() -> None:
    assert len(DEPRECATED) == 46
    assert util_bbdd._DEPRECATED == DEPRECATED
    assert not set(DEPRECATED) & set(ROOT_API)


@pytest.mark.parametrize("name", ROOT_API)
def test_root_symbols_resolve_without_warning(name: str) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        assert getattr(util_bbdd, name) is not None


@pytest.mark.parametrize(("name", "module"), sorted(DEPRECATED.items()))
def test_deprecated_alias_warns_and_is_the_same_object(name: str, module: str) -> None:
    target = importlib.import_module(f"util_bbdd.{module}")
    with pytest.warns(DeprecationWarning, match=rf"from util_bbdd\.{module} import {name}'") as record:
        value = getattr(util_bbdd, name)
    assert value is getattr(target, name)
    assert name in target.__all__
    # stacklevel=2: el aviso señala al llamante, no a util_bbdd/__init__.py.
    assert record[0].filename == __file__


def test_deprecated_alias_warns_on_from_import() -> None:
    with pytest.warns(DeprecationWarning, match="util_bbdd.QueryError"):
        from util_bbdd import QueryError  # noqa: F401


def test_deprecated_alias_warns_on_every_access() -> None:
    """Los alias no se cachean en el módulo: cada acceso avisa (los perezosos sí se cachean)."""
    for _ in range(2):
        with pytest.warns(DeprecationWarning):
            util_bbdd.QueryError  # noqa: B018
    assert "QueryError" not in vars(util_bbdd)


def test_unknown_attribute_raises_attribute_error() -> None:
    with pytest.raises(AttributeError, match="no_existe"):
        util_bbdd.no_existe  # noqa: B018


def test_dir_lists_the_root_api_but_not_deprecated_aliases() -> None:
    names = dir(util_bbdd)
    assert set(ROOT_API) <= set(names)
    assert not set(DEPRECATED) & set(names)


def test_public_exceptions_module_is_the_full_hierarchy() -> None:
    hierarchy = {
        n
        for n, v in vars(core_exceptions).items()
        if isinstance(v, type) and issubclass(v, core_exceptions.DatabaseException)
    }
    assert set(public_exceptions.__all__) == hierarchy
    for name in public_exceptions.__all__:
        assert getattr(public_exceptions, name) is getattr(core_exceptions, name)
    assert util_bbdd.DatabaseException is public_exceptions.DatabaseException


def test_exception_families_keep_their_bases() -> None:
    exc = public_exceptions
    assert issubclass(exc.SchemaDiffValidationError, exc.ComparerError)
    assert issubclass(exc.DumpConstraintError, exc.DumpError)
    assert issubclass(exc.ComparerError, exc.DatabaseException)
    assert issubclass(exc.DumpError, exc.DatabaseException)


def _run(code: str) -> str:
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip()


def test_import_does_not_load_heavy_dependencies() -> None:
    """``import util_bbdd`` solo carga los managers; pandas y compañía llegan con el primer punto de entrada que los usa."""
    heavy = ("pandas", "openpyxl", "docx", "jinja2", "util_bbdd.bulk", "util_bbdd.comparar", "util_bbdd.dump")
    out = _run(f"import sys, util_bbdd; print([m for m in {heavy!r} if m in sys.modules])")
    assert out == "[]"
    assert _run("import sys, util_bbdd; util_bbdd.BulkCrud; print('pandas' in sys.modules)") == "True"


def test_subpackages_resolve_by_attribute_without_explicit_import() -> None:
    """Hasta 0.42 ``import util_bbdd`` cargaba ``dump``/``bulk``…; ``util_bbdd.dump`` sigue funcionando."""
    out = _run("import util_bbdd; print(util_bbdd.dump.DumpOrchestrator.__name__, util_bbdd.audit.__name__)")
    assert out == "DumpOrchestrator util_bbdd.audit"


def test_library_does_not_use_its_own_deprecated_aliases() -> None:
    """Importar todos los subpaquetes no dispara ningún alias deprecado de la raíz."""
    code = (
        "import warnings; warnings.simplefilter('error', DeprecationWarning)\n"
        "import util_bbdd\n"
        "for m in sorted(util_bbdd._SUBMODULES): getattr(util_bbdd, m)\n"
        "for n in util_bbdd.__all__: getattr(util_bbdd, n)\n"
        "print('ok')"
    )
    assert _run(code) == "ok"
