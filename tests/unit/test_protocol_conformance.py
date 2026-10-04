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

from pathlib import Path

import pytest

from util_bbdd.analysis.contracts import RelationshipGraphSource
from util_bbdd.audit import AuditEventSource, AuditSink, JsonLinesAuditSink, MemoryAuditSink, NullAuditSink
from util_bbdd.doc.application.ports import (
    DocumentationBackendPort,
    DocumentationManagerPort,
    DocumentationSourcePort,
)
from util_bbdd.doc.infrastructure.adapters.sync_database_manager_adapter import SyncDatabaseManagerAdapter
from util_bbdd.managers import SyncDatabaseManager


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


def _adapter_as_documentation_port(adapter: SyncDatabaseManagerAdapter) -> DocumentationBackendPort:
    return adapter


# ---------------------------------------------------------------------------------------------------------------
# util_bbdd.audit (sesión 2026-10-02c): destinos de eventos. El contrato de comportamiento (atomicidad, hilos, close)
# está en tests/unit/audit/test_sinks_contract.py; aquí, la conformidad de firmas con mypy y en ejecución.
# ---------------------------------------------------------------------------------------------------------------


def _null_as_audit_sink(sink: NullAuditSink) -> AuditSink:
    return sink


def _memory_as_audit_sink(sink: MemoryAuditSink) -> AuditSink:
    return sink


def _memory_as_audit_event_source(sink: MemoryAuditSink) -> AuditEventSource:
    return sink


def _jsonl_as_audit_sink(sink: JsonLinesAuditSink) -> AuditSink:
    return sink


@pytest.mark.parametrize("sink_cls", (NullAuditSink, MemoryAuditSink), ids=lambda c: c.__name__)
def test_audit_sinks_satisfy_audit_sink(sink_cls: type) -> None:
    assert isinstance(sink_cls(), AuditSink)


def test_jsonl_audit_sink_satisfies_audit_sink(tmp_path: Path) -> None:
    assert isinstance(JsonLinesAuditSink(tmp_path / "a.jsonl"), AuditSink)


def test_memory_audit_sink_satisfies_audit_event_source() -> None:
    assert isinstance(MemoryAuditSink(), AuditEventSource)
