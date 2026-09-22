"""Conformidad estructural de los Protocols consumidores con sus implementaciones reales.

Los paquetes de capas altas no importan los de capas más bajas por su clase concreta (Regla #6): dependen de un
``Protocol`` definido por el consumidor. Este módulo comprueba que la implementación real lo cumple:

- **En ejecución**, ``isinstance`` contra un ``@runtime_checkable`` comprueba que los miembros existen.
- **Con mypy**, las funciones de conversión (``_*_as_*``) comprueban además miembros, tipos, aridad y propiedades. No
  comparan los nombres de los parámetros, por eso los Protocols los declaran posicionales (``/``). ``mypy src`` no
  revisa este fichero: el paso ``mypy`` de CI (``.github/workflows/tests.yml``) lo ejecuta junto a ``src``, y en local
  se lanza con ``python -m mypy src tests/unit/test_protocol_conformance.py``.
"""

from __future__ import annotations

import logging

from util_bbdd.analysis.contracts import RelationshipGraphSource
from util_bbdd.doc.application.ports import DocumentationManagerPort, DocumentationSourcePort
from util_bbdd.doc.infrastructure.adapters.sync_database_manager_adapter import SyncDatabaseManagerAdapter
from util_bbdd.managers import SyncDatabaseManager
from util_bbdd.managers._manager_cache_service import CacheService
from util_bbdd.metadata.adapters._adapter_protocol import MetadataCachePort
from util_bbdd.metadata.cache import DatabaseMetadataCache, RelationshipMetadataCache


def _as_metadata_cache_port(service: CacheService) -> MetadataCachePort:
    return service


# ``analysis`` y ``doc`` reciben el manager real, pero ``doc`` también le pasa a ``analysis`` su adaptador y su puerto:
# los tres deben cumplir el contrato de ``analysis``.
def _manager_as_relationship_source(manager: SyncDatabaseManager) -> RelationshipGraphSource:
    return manager


def _adapter_as_relationship_source(adapter: SyncDatabaseManagerAdapter) -> RelationshipGraphSource:
    return adapter


def _documentation_port_as_relationship_source(port: DocumentationManagerPort) -> RelationshipGraphSource:
    return port


# ``doc`` consume el manager a través de su adaptador, y el adaptador debe cumplir el puerto de orquestación.
def _manager_as_documentation_source(manager: SyncDatabaseManager) -> DocumentationSourcePort:
    return manager


def _adapter_as_documentation_port(adapter: SyncDatabaseManagerAdapter) -> DocumentationManagerPort:
    return adapter


def test_cache_service_satisfies_metadata_cache_port() -> None:
    db_cache = DatabaseMetadataCache()
    service = CacheService(db_cache, RelationshipMetadataCache(db_cache=db_cache), logging.getLogger(__name__))

    assert isinstance(service, MetadataCachePort)
    assert _as_metadata_cache_port(service) is service
