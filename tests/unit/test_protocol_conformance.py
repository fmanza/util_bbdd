"""Conformidad estructural de los Protocols consumidores con sus implementaciones reales.

Los paquetes de capas altas no importan los de capas más bajas por su clase concreta (Regla #6): dependen de un
``Protocol`` definido por el consumidor. Este módulo comprueba que la implementación real lo cumple:

- **En ejecución**, ``isinstance`` contra un ``@runtime_checkable`` comprueba que los miembros existen.
- **Con mypy**, las funciones ``_as_*`` comprueban además miembros, tipos, aridad y propiedades. No comparan los
  nombres de los parámetros, por eso los Protocols los declaran posicionales (``/``). mypy solo revisa ``src/`` por
  defecto: para verlo, ``python -m mypy tests/unit/test_protocol_conformance.py``.
"""

from __future__ import annotations

import logging

from util_bbdd.managers._manager_cache_service import CacheService
from util_bbdd.metadata.adapters._adapter_protocol import MetadataCachePort
from util_bbdd.metadata.cache import DatabaseMetadataCache, RelationshipMetadataCache


def _as_metadata_cache_port(service: CacheService) -> MetadataCachePort:
    return service


def test_cache_service_satisfies_metadata_cache_port() -> None:
    db_cache = DatabaseMetadataCache()
    service = CacheService(db_cache, RelationshipMetadataCache(db_cache=db_cache), logging.getLogger(__name__))

    assert isinstance(service, MetadataCachePort)
    assert _as_metadata_cache_port(service) is service
