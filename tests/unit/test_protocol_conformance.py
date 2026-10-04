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

from pathlib import Path
from unittest.mock import MagicMock

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
from util_bbdd.managers._manager_cache_service import CacheService
from util_bbdd.metadata.adapters._adapter_protocol import (
    EngineMetadataAdapterAsync,
    EngineMetadataAdapterSync,
    MetadataCachePort,
    RoutineAdapterAsync,
    RoutineAdapterSync,
    SourceAdapterAsync,
    SourceAdapterSync,
)
from util_bbdd.metadata.cache import DatabaseMetadataCache
from util_bbdd.metadata.mariadb import MariaDBAsyncAdapter, MariaDBSyncAdapter
from util_bbdd.metadata.mysql import MysqlAsyncAdapter, MysqlSyncAdapter
from util_bbdd.metadata.oracle import OracleAsyncAdapter, OracleSyncAdapter
from util_bbdd.metadata.postgresql import PostgreSQLAsyncAdapter, PostgreSQLSyncAdapter
from util_bbdd.metadata.sqlite import SqliteAsyncAdapter, SqliteSyncAdapter
from util_bbdd.metadata.sqlserver import SqlServerAsyncAdapter, SqlServerSyncAdapter


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


def _adapter_as_documentation_port(adapter: SyncDatabaseManagerAdapter) -> DocumentationBackendPort:
    return adapter


def test_cache_service_satisfies_metadata_cache_port() -> None:
    db_cache = DatabaseMetadataCache()
    service = CacheService(db_cache, logging.getLogger(__name__))

    assert isinstance(service, MetadataCachePort)
    assert _as_metadata_cache_port(service) is service


# ---------------------------------------------------------------------------------------------------------------
# MDC-05 (AUDIT_CODE 2026-09-22): SourceAdapterSync/Async y RoutineAdapterSync/Async no tenían ninguna cobertura
# de conformidad, ni en tiempo de ejecución ni con mypy. Esto permitió que 3 adaptadores divergieran del Protocol
# sin que ningún test lo detectara (OracleAsyncAdapter con métodos fetch_*_sync dentro de la clase async — MEO-01;
# SqlServerSyncAdapter.fetch_routine_parameters_sync con firma (object_id) en vez de (schema, routine, routine_type)
# — MSS-01; MariaDBSync/AsyncAdapter sin parámetro schema — MEO-03). Todos los motores salvo MariaDB implementan
# SourceAdapter: MariaDB lo perdió en E2 de ADR-003 (sus fetch_* leían los get_* del manager, que ahora devuelven
# modelos tipados del snapshot; nadie los consumía).
#
# RoutineAdapter completo (Fase 3/4 de la remediación, 2026-09-22): mariadb y oracle lo tenían desde el
# AUDIT_CODE original; postgresql (MPG-01) y sqlserver (MSS-02) expusieron fetch_routine_definition_*
# reutilizando helpers ya existentes sin caller; mysql (MDC-03) requirió implementar
# fetch_routine_definition_* desde cero (SHOW CREATE PROCEDURE/FUNCTION, no existía ningún mecanismo) y
# ampliar fetch_routine_parameters_sync/async con el parámetro routine_type que exige el Protocol (antes
# solo aceptaba schema/routine_name — mismo patrón de firma reducida que MEO-03 detectó en mariadb).
# ---------------------------------------------------------------------------------------------------------------


def _mariadb_sync_as_routine(adapter: MariaDBSyncAdapter) -> RoutineAdapterSync:
    return adapter


def _mariadb_async_as_routine(adapter: MariaDBAsyncAdapter) -> RoutineAdapterAsync:
    return adapter


# Lecturas especializadas que los managers delegan en el adapter del registro (``_get_metadata_adapter``).
def _mariadb_sync_as_engine_metadata(adapter: MariaDBSyncAdapter) -> EngineMetadataAdapterSync:
    return adapter


def _mariadb_async_as_engine_metadata(adapter: MariaDBAsyncAdapter) -> EngineMetadataAdapterAsync:
    return adapter


def _mysql_sync_as_engine_metadata(adapter: MysqlSyncAdapter) -> EngineMetadataAdapterSync:
    return adapter


def _mysql_async_as_engine_metadata(adapter: MysqlAsyncAdapter) -> EngineMetadataAdapterAsync:
    return adapter


def _mysql_sync_as_source(adapter: MysqlSyncAdapter) -> SourceAdapterSync:
    return adapter


def _mysql_async_as_source(adapter: MysqlAsyncAdapter) -> SourceAdapterAsync:
    return adapter


def _mysql_sync_as_routine(adapter: MysqlSyncAdapter) -> RoutineAdapterSync:
    return adapter


def _mysql_async_as_routine(adapter: MysqlAsyncAdapter) -> RoutineAdapterAsync:
    return adapter


def _oracle_sync_as_source(adapter: OracleSyncAdapter) -> SourceAdapterSync:
    return adapter


def _oracle_async_as_source(adapter: OracleAsyncAdapter) -> SourceAdapterAsync:
    return adapter


def _oracle_sync_as_routine(adapter: OracleSyncAdapter) -> RoutineAdapterSync:
    return adapter


def _oracle_async_as_routine(adapter: OracleAsyncAdapter) -> RoutineAdapterAsync:
    return adapter


def _postgresql_sync_as_source(adapter: PostgreSQLSyncAdapter) -> SourceAdapterSync:
    return adapter


def _postgresql_async_as_source(adapter: PostgreSQLAsyncAdapter) -> SourceAdapterAsync:
    return adapter


def _postgresql_sync_as_routine(adapter: PostgreSQLSyncAdapter) -> RoutineAdapterSync:
    return adapter


def _postgresql_async_as_routine(adapter: PostgreSQLAsyncAdapter) -> RoutineAdapterAsync:
    return adapter


def _sqlite_sync_as_source(adapter: SqliteSyncAdapter) -> SourceAdapterSync:
    return adapter


def _sqlite_async_as_source(adapter: SqliteAsyncAdapter) -> SourceAdapterAsync:
    return adapter


def _sqlserver_sync_as_source(adapter: SqlServerSyncAdapter) -> SourceAdapterSync:
    return adapter


def _sqlserver_async_as_source(adapter: SqlServerAsyncAdapter) -> SourceAdapterAsync:
    return adapter


def _sqlserver_sync_as_routine(adapter: SqlServerSyncAdapter) -> RoutineAdapterSync:
    return adapter


def _sqlserver_async_as_routine(adapter: SqlServerAsyncAdapter) -> RoutineAdapterAsync:
    return adapter


_SYNC_SOURCE_ADAPTERS: tuple[type, ...] = (
    MysqlSyncAdapter,
    OracleSyncAdapter,
    PostgreSQLSyncAdapter,
    SqliteSyncAdapter,
    SqlServerSyncAdapter,
)

_ASYNC_SOURCE_ADAPTERS: tuple[type, ...] = (
    MysqlAsyncAdapter,
    OracleAsyncAdapter,
    PostgreSQLAsyncAdapter,
    SqliteAsyncAdapter,
    SqlServerAsyncAdapter,
)

# SQLite queda fuera: sin concepto de rutina almacenada. Ver nota arriba para el resto.
_SYNC_ROUTINE_ADAPTERS: tuple[type, ...] = (
    MariaDBSyncAdapter,
    MysqlSyncAdapter,
    OracleSyncAdapter,
    PostgreSQLSyncAdapter,
    SqlServerSyncAdapter,
)
_ASYNC_ROUTINE_ADAPTERS: tuple[type, ...] = (
    MariaDBAsyncAdapter,
    MysqlAsyncAdapter,
    OracleAsyncAdapter,
    PostgreSQLAsyncAdapter,
    SqlServerAsyncAdapter,
)


@pytest.mark.parametrize("adapter_cls", _SYNC_SOURCE_ADAPTERS, ids=lambda c: c.__name__)
def test_sync_adapter_satisfies_source_adapter_sync(adapter_cls: type) -> None:
    adapter = adapter_cls(MagicMock())
    assert isinstance(adapter, SourceAdapterSync)


@pytest.mark.parametrize("adapter_cls", _ASYNC_SOURCE_ADAPTERS, ids=lambda c: c.__name__)
def test_async_adapter_satisfies_source_adapter_async(adapter_cls: type) -> None:
    adapter = adapter_cls(MagicMock())
    assert isinstance(adapter, SourceAdapterAsync)


@pytest.mark.parametrize("adapter_cls", _SYNC_ROUTINE_ADAPTERS, ids=lambda c: c.__name__)
def test_sync_adapter_satisfies_routine_adapter_sync(adapter_cls: type) -> None:
    adapter = adapter_cls(MagicMock())
    assert isinstance(adapter, RoutineAdapterSync)


@pytest.mark.parametrize("adapter_cls", _ASYNC_ROUTINE_ADAPTERS, ids=lambda c: c.__name__)
def test_async_adapter_satisfies_routine_adapter_async(adapter_cls: type) -> None:
    adapter = adapter_cls(MagicMock())
    assert isinstance(adapter, RoutineAdapterAsync)


_SYNC_ENGINE_METADATA_ADAPTERS: tuple[type, ...] = (MariaDBSyncAdapter, MysqlSyncAdapter)
_ASYNC_ENGINE_METADATA_ADAPTERS: tuple[type, ...] = (MariaDBAsyncAdapter, MysqlAsyncAdapter)


@pytest.mark.parametrize("adapter_cls", _SYNC_ENGINE_METADATA_ADAPTERS, ids=lambda c: c.__name__)
def test_sync_adapter_satisfies_engine_metadata_adapter_sync(adapter_cls: type) -> None:
    adapter = adapter_cls(MagicMock())
    assert isinstance(adapter, EngineMetadataAdapterSync)


@pytest.mark.parametrize("adapter_cls", _ASYNC_ENGINE_METADATA_ADAPTERS, ids=lambda c: c.__name__)
def test_async_adapter_satisfies_engine_metadata_adapter_async(adapter_cls: type) -> None:
    adapter = adapter_cls(MagicMock())
    assert isinstance(adapter, EngineMetadataAdapterAsync)


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
