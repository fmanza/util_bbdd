"""Tests para el Protocol SchemaExtractor (migrate/extractors/base.py)."""

from __future__ import annotations

from typing import Any

from util_bbdd.migrate.extractors.base import SchemaExtractor
from util_bbdd.migrate.extractors.mariadb import MariaDBSchemaExtractor
from util_bbdd.migrate.extractors.oracle import OracleSchemaExtractor
from util_bbdd.migrate.extractors.postgresql import PostgreSQLSchemaExtractor
from util_bbdd.migrate.extractors.sqlserver import SQLServerSchemaExtractor

from ._snapshot_source import FakeSource


class TestSchemaExtractorProtocolConformance:
    """MIG-04 (AUDIT_CODE 2026-09-22): las 4 implementaciones reales exponen
    extract_views y migrate/planner.py lo invoca incondicionalmente, pero el
    Protocol no lo declaraba — una implementación incompleta (sin
    extract_views) pasaba isinstance() igualmente."""

    def test_all_concrete_extractors_satisfy_the_protocol(self) -> None:
        for extractor_cls in (
            OracleSchemaExtractor,
            MariaDBSchemaExtractor,
            PostgreSQLSchemaExtractor,
            SQLServerSchemaExtractor,
        ):
            extractor = extractor_cls(FakeSource("postgresql"))
            assert isinstance(extractor, SchemaExtractor)

    def test_incomplete_implementation_without_extract_views_is_rejected(self) -> None:
        class _IncompleteExtractor:
            def extract(self, schema: str) -> list[Any]:
                return []

            def extract_routines(self, schema: str) -> list[Any]:
                return []

        assert not isinstance(_IncompleteExtractor(), SchemaExtractor)
