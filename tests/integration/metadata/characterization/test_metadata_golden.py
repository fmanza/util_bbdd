"""Tests de caracterización de la lectura de metadatos por motor (A0, ADR-003).

Congelan, contra servidores reales, lo que hoy devuelven los caminos que la centralización de ``metadata/`` va a
sustituir, para que cada grupo del plan demuestre que no cambia el resultado:

- ``manager``: salida de los ``get_*`` de ``SyncDatabaseManager``: modelos neutros del snapshot desde E2 (D9-2), cuando
  se re-baselineó a propósito (antes, tuplas con forma distinta por motor).
- ``ir``: IR de ``migrate`` (tablas, vistas y routines extraídas): neutro entre motores; debe quedar idéntico.
- ``doc``: texto del HTML de ``DatabaseDocumentation`` (sin etiquetas ni fechas); no en Oracle, cuyo schema de
  pruebas no está aislado.

Ficheros dorados: ``tests/fixtures/metadata_golden/<motor>.json`` y ``<motor>_doc.txt``. Para regenerarlos (solo
cuando un cambio de resultado está justificado y revisado)::

    UTIL_BBDD_UPDATE_GOLDEN=1 python -m pytest tests/integration/metadata/characterization -m integration

Requiere las URLs ``UTIL_BBDD_TEST_<MOTOR>_URL`` del banco (``scripts/bench_env.example.sh``); SQLite no.
"""

from __future__ import annotations

import dataclasses
import html
import json
import os
import re
import tempfile

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from util_bbdd import SyncDatabaseManager

from ._schemas import ORACLE_ADMIN_URL_ENV, PREFIX, GoldenTarget, build, drop, oracle_doc_target, targets

pytestmark = pytest.mark.integration

GOLDEN_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "metadata_golden"
UPDATE = os.environ.get("UTIL_BBDD_UPDATE_GOLDEN") == "1"


def _ours(name: Any) -> bool:
    return str(name).lower().startswith(PREFIX)


def _plain(value: Any) -> Any:
    """Valor serializable y estable (modelos → dicts, tuplas → listas, LOBs/Decimal/fechas → str)."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _call(fn: Callable[[], Any]) -> Any:
    """Resultado o, si falla, el tipo de excepción (caracteriza también los fallos)."""
    try:
        return _plain(fn())
    except Exception as exc:  # noqa: BLE001 - el fallo forma parte del comportamiento caracterizado
        return {"error": type(exc).__name__}


def _manager_snapshot(mgr: SyncDatabaseManager) -> dict[str, Any]:
    tables = sorted(t.name for t in mgr.get_tables() if _ours(t.name))
    views = sorted(v.name for v in mgr.get_views() if _ours(v.name))
    routines = sorted({(r.name, r.routine_type) for r in mgr.get_routines() if _ours(r.name)})
    return {
        "tables": tables,
        "views": views,
        "routines": [list(r) for r in routines],
        "per_table": {
            t: {
                "columns": _call(lambda t=t: mgr.get_columns(t)),
                "indices": _call(lambda t=t: sorted(map(_plain, mgr.get_indices(t)), key=str)),
                "pk": _call(lambda t=t: mgr.get_primary_keys(t)),
                "fk": _call(lambda t=t: sorted(map(_plain, mgr.get_foreign_keys(t)), key=str)),
                "uk": _call(lambda t=t: sorted(map(_plain, mgr.get_unique_constraints(t)), key=str)),
                "ddl": _call(lambda t=t: mgr.get_ddl(t)),
            }
            for t in tables
        },
        "per_view": {v: {"ddl": _call(lambda v=v: mgr.get_view_ddl(v))} for v in views},
        "per_routine": {
            f"{name}:{kind}": {
                "parameters": _call(lambda n=name, k=kind: mgr.get_routine_parameters(n, k)),
                "ddl": _call(lambda n=name, k=kind: mgr.get_routine_ddl(n, k)),
            }
            for name, kind in routines
        },
    }


def _ir_snapshot(engine: str, mgr: SyncDatabaseManager, schema: str) -> dict[str, Any]:
    from util_bbdd.migrate.extractors.mariadb import MariaDBSchemaExtractor
    from util_bbdd.migrate.extractors.mysql import MySQLSchemaExtractor
    from util_bbdd.migrate.extractors.oracle import OracleSchemaExtractor
    from util_bbdd.migrate.extractors.postgresql import PostgreSQLSchemaExtractor
    from util_bbdd.migrate.extractors.sqlserver import SQLServerSchemaExtractor

    cls = {
        "postgresql": PostgreSQLSchemaExtractor,
        "mysql": MySQLSchemaExtractor,
        "mariadb": MariaDBSchemaExtractor,
        "sqlserver": SQLServerSchemaExtractor,
        "oracle": OracleSchemaExtractor,
    }[engine]
    extractor = cls(mgr)
    return {
        kind: _call(
            lambda fn=fn: sorted(
                (dataclasses.asdict(obj) for obj in fn(schema) if _ours(obj.name)), key=lambda d: d["name"]
            )
        )
        for kind, fn in (
            ("tables", extractor.extract),
            ("views", extractor.extract_views),
            ("routines", extractor.extract_routines),
        )
    }


_ORACLE_IDENTITY_SEQ = re.compile(r"ISEQ\$\$_\d+")
_TAG = re.compile(r"<[^>]+>")
_EMBEDDED = re.compile(r"<(style|script)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
_VOLATILE = re.compile(r"\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?|\d{2}/\d{2}/\d{4}( \d{2}:\d{2}(:\d{2})?)?")


def _doc_text(mgr: SyncDatabaseManager, engine: str) -> str:
    from util_bbdd.doc import DatabaseDocumentation

    out = Path(tempfile.mkdtemp(prefix="gold_doc_"))
    DatabaseDocumentation(
        db_manager=mgr,
        directorio_salida=out,
        fichero_salida=Path(f"gold_{engine}"),
        imprimir={
            "tablas": {
                "imprimir_tablas": True,
                "ddl": True,
                "columnas": True,
                "pk": True,
                "fk": True,
                "unicas": True,
                "indices": True,
            },
            "vistas": {"imprimir_vistas": True, "ddl": True, "columnas": True},
            "rutinas": {"imprimir_procedures": True, "imprimir_function": True},
            "grafo": {"enabled": False},
        },  # fmt: skip
        formatos=["html"],
    ).generate()
    pages = sorted(out.rglob("*.html"))
    text = "\n".join(html.unescape(_TAG.sub(" ", _EMBEDDED.sub(" ", p.read_text(encoding="utf-8")))) for p in pages)
    lines = (" ".join(_VOLATILE.sub("<fecha>", line).split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line) + "\n"


@pytest.fixture(params=targets(), ids=lambda t: t.engine)
def target(request: pytest.FixtureRequest) -> Iterator[GoldenTarget]:
    t: GoldenTarget = request.param
    if t.url_env and not os.environ.get(t.url_env):
        pytest.skip(f"{t.url_env} no definida")
    build(t)
    try:
        yield t
    finally:
        drop(t)


def _compare(path: Path, actual: str) -> None:
    if UPDATE or not path.exists():
        if not UPDATE:
            pytest.fail(f"No existe el dorado {path.name}: genéralo con UTIL_BBDD_UPDATE_GOLDEN=1 y revísalo")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(actual, encoding="utf-8")
        return
    expected = path.read_text(encoding="utf-8")
    assert actual == expected, f"{path.name} cambió: revisa el diff y, si es correcto, regenera el dorado"


def test_metadata_matches_golden(target: GoldenTarget) -> None:
    db_type, params = target.manager_args()
    with SyncDatabaseManager(db_type, params, use_pool=False) as mgr:
        snapshot: dict[str, Any] = {"manager": _manager_snapshot(mgr)}
        if target.migrate_source:
            snapshot["ir"] = _ir_snapshot(target.engine, mgr, target.schema)
    serialized = json.dumps(snapshot, ensure_ascii=False, indent=1, sort_keys=True)
    # Oracle: la secuencia de una columna identidad se llama ISEQ$$_<n> con n distinto en cada creación
    serialized = _ORACLE_IDENTITY_SEQ.sub("ISEQ$$_<n>", serialized)
    _compare(GOLDEN_DIR / f"{target.engine}.json", serialized)


def test_doc_matches_golden(target: GoldenTarget) -> None:
    doc_target: GoldenTarget | None = target if target.doc else oracle_doc_target(target)
    if doc_target is None:
        pytest.skip(f"schema de pruebas no aislado y sin {ORACLE_ADMIN_URL_ENV} para crear uno propio")
    if doc_target is not target:
        build(doc_target)
    try:
        db_type, params = doc_target.manager_args()
        with SyncDatabaseManager(db_type, params, use_pool=False) as mgr:
            _compare(GOLDEN_DIR / f"{target.engine}_doc.txt", _doc_text(mgr, target.engine))
    finally:
        if doc_target is not target:
            drop(doc_target)
