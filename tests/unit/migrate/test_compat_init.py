"""Tests para las exportaciones públicas de migrate/_compat/__init__.py."""

from __future__ import annotations

from util_bbdd.migrate import _compat


class TestCompatPackageExports:
    """CMP-03 (AUDIT_CODE 2026-09-22): _compat/__init__.py solo reexportaba 7 de los
    12 mapas de tipos (faltaban las 3 direcciones con MariaDB como origen y las 2
    direcciones Oracle→PostgreSQL/SQLServer, ocultas tras nombres de fichero que
    rompían la convención type_map_<origen>_to_<destino>.py)."""

    def test_all_12_resolver_functions_importable_from_the_subpackage(self) -> None:
        resolvers = [
            _compat.resolve_mariadb_type_oracle,
            _compat.resolve_mariadb_type_postgresql,
            _compat.resolve_mariadb_type_sqlserver,
            _compat.resolve_oracle_type,
            _compat.resolve_oracle_type_postgresql,
            _compat.resolve_oracle_type_sqlserver,
            _compat.resolve_postgresql_type_mariadb,
            _compat.resolve_postgresql_type_oracle,
            _compat.resolve_postgresql_type_sqlserver,
            _compat.resolve_sqlserver_type_mariadb,
            _compat.resolve_sqlserver_type_oracle,
            _compat.resolve_sqlserver_type_postgresql,
        ]
        assert all(callable(resolver) for resolver in resolvers)

    def test_all_12_type_mapping_dicts_importable_from_the_subpackage(self) -> None:
        maps = [
            _compat.MARIADB_TO_ORACLE,
            _compat.MARIADB_TO_POSTGRESQL,
            _compat.MARIADB_TO_SQLSERVER,
            _compat.POSTGRESQL_TO_MARIADB,
            _compat.POSTGRESQL_TO_ORACLE,
            _compat.POSTGRESQL_TO_SQLSERVER,
            _compat.SQLSERVER_TO_MARIADB,
            _compat.SQLSERVER_TO_ORACLE,
            _compat.SQLSERVER_TO_POSTGRESQL,
        ]
        assert all(isinstance(type_map, dict) and type_map for type_map in maps)

    def test_identifier_rules_importable_from_the_subpackage(self) -> None:
        assert callable(_compat.check_identifier)
        assert callable(_compat.truncate_identifier)
        assert callable(_compat.find_case_insensitive_collisions)

    def test_all_exports_are_actually_accessible(self) -> None:
        for name in _compat.__all__:
            assert hasattr(_compat, name), f"{name} está en __all__ pero no es accesible"
