"""``get_schema_metadata()`` de los managers (driver nativo, sync y async) = ``CatalogSource.from_engine`` (C1, ADR-003).

Los managers ejecutan el SQL de catálogo con su conexión nativa (psycopg/asyncpg, oracledb, pymssql/aioodbc,
mariadb/pymysql/aiomysql, sqlite3/aiosqlite), traduciendo ``:nombre`` al ``paramstyle`` de cada driver; el snapshot
debe coincidir con el leído por SQLAlchemy y con el dorado ``<motor>_snapshot.json``.
"""

from __future__ import annotations

import asyncio
import importlib.util

from collections.abc import Iterator

import pytest

from util_bbdd import AsyncDatabaseManager, SyncDatabaseManager
from util_bbdd.metadata import ALL_KINDS, Kind
from util_bbdd.metadata.source import CatalogSource

from ._schemas import GoldenTarget, build, drop, targets
from .test_metadata_golden import GOLDEN_DIR
from .test_snapshot_golden import _engine, _serialize

pytestmark = pytest.mark.integration

_ASYNC_DRIVER = {
    "postgresql": "asyncpg",
    "mysql": "aiomysql",
    "mariadb": "aiomysql",
    "oracle": "oracledb",
    "sqlserver": "aioodbc",
    "sqlite": "aiosqlite",
}


@pytest.fixture(scope="module", params=targets(), ids=lambda t: t.engine)
def target(request: pytest.FixtureRequest) -> Iterator[GoldenTarget]:
    t: GoldenTarget = request.param
    reason = t.skip_reason()
    if reason:
        pytest.skip(reason)
    build(t)
    try:
        yield t
    finally:
        drop(t)


def _comparable(serialized: str, target: GoldenTarget) -> str:
    """En PostgreSQL ``pg_get_viewdef`` califica o no las tablas según el ``search_path`` de la sesión (el manager lo fija
    al schema; un ``Engine`` sin opciones, no): se comparan sin el prefijo del schema."""
    return serialized.replace(f"{target.schema}.", "") if target.engine == "postgresql" else serialized


def _expected(target: GoldenTarget) -> str:
    engine = _engine(target)
    try:
        return _comparable(_serialize(CatalogSource.from_engine(engine).snapshot(target.schema)), target)
    finally:
        engine.dispose()


def test_sync_manager_matches_sqlalchemy_source_and_golden(target: GoldenTarget) -> None:
    db_type, params = target.manager_args()
    with SyncDatabaseManager(db_type, params, use_pool=False) as mgr:
        snapshot = mgr.get_schema_metadata()  # schema por defecto = contexto de metadatos del manager
        assert snapshot.schema.lower() == ("main" if target.engine == "sqlite" else target.schema.lower())
        serialized = _serialize(snapshot)
        # Segunda lectura desde la caché (el mismo snapshot, sin reconstruir su índice); clear_cache() la invalida
        assert mgr.get_schema_metadata() is snapshot
        mgr.clear_cache()
        assert mgr.get_schema_metadata().data[Kind.TABLES] is not snapshot.data[Kind.TABLES]
    serialized = _comparable(serialized, target)
    assert serialized == _expected(target)
    golden = (GOLDEN_DIR / f"{target.engine}_snapshot.json").read_text(encoding="utf-8")
    assert serialized == _comparable(golden, target)


def test_async_manager_matches_sync(target: GoldenTarget) -> None:
    driver = _ASYNC_DRIVER[target.engine]
    if importlib.util.find_spec(driver) is None:
        pytest.skip(f"driver async {driver} no instalado")
    db_type, params = target.manager_args()

    async def read() -> str:
        manager = AsyncDatabaseManager(db_type, params, use_pool=False)
        try:
            await manager.initialize() if hasattr(manager, "initialize") else None
            return _serialize(await manager.get_schema_metadata(kinds=ALL_KINDS))
        finally:
            await manager.close()

    try:
        serialized = asyncio.run(read())
    except Exception as exc:  # noqa: BLE001 - p. ej. sin driver ODBC para aioodbc
        if "driver" in str(exc).lower() or "odbc" in str(exc).lower():
            pytest.skip(f"conexión async no disponible: {str(exc).splitlines()[0][:120]}")
        raise
    assert _comparable(serialized, target) == _expected(target)
