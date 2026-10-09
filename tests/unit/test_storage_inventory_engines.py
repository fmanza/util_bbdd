"""Inventario de almacenamiento por motor (tabla declarativa de ``storage/engines.py``; A-01, B-01)."""

from __future__ import annotations

import logging

from typing import Any, cast

from util_bbdd._core.exceptions import DatabaseException
from util_bbdd.doc.infrastructure.storage.runtime import StorageInventoryRuntime


def _runtime(db_type: str, manager: object, print_config: dict[str, Any] | None = None) -> StorageInventoryRuntime:
    return StorageInventoryRuntime(
        db_manager=cast(Any, manager),
        logger=logging.getLogger(__name__),
        db_type=db_type,
        database="demo",
        print_config=print_config or {},
    )


def test_sqlserver_uses_its_queries_without_the_generic_notice(caplog: Any) -> None:
    class _Manager:
        conn_params: dict[str, Any] = {}

        def get_storage_rows(self, query_name: str, **_: Any) -> list[tuple[Any, ...]]:
            return [("demo", "demo_data", "ROWS", "C:/data/demo.mdf", 8.0, -1, 0, "64 MB")]

    with caplog.at_level(logging.WARNING):
        report = _runtime("sqlserver", _Manager()).get_storage_inventory_report()

    assert [s["query"] for s in report["sections"]] == ["ficheros_fisicos", "temp_tablespaces"]
    assert not caplog.records  # B-01: sin aviso de inventario genérico
    first = report["sections"][0]
    assert first["status"] == "ok"
    assert first["headers"][:4] == ["Database", "Nombre logico", "Tipo de fichero", "Archivo fisico"]
    assert first["rows"][0][4] == "8,00"  # Tamaño (MB) con coma decimal
    assert first["numeric_columns"] == [4, 5]


class _OracleManager:
    """``user_tablespaces`` → (USERS, TEMP); las consultas por tablespace devuelven filas (y fallan en ``BAD``)."""

    def __init__(self, conn_tablespace: str = "") -> None:
        self.conn_params: dict[str, Any] = {"tablespace": conn_tablespace} if conn_tablespace else {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_storage_rows(self, query_name: str, **params: Any) -> list[tuple[Any, ...]]:
        self.calls.append((query_name, params))
        if query_name == "user_tablespaces":
            return [("USERS", "TEMP")]
        if params.get("tablespace") == "BAD":
            raise DatabaseException("ORA-00942")
        tablespace = params["tablespace"]
        return [(tablespace, f"/u01/{tablespace.lower()}.dbf", 100.5, "AVAILABLE", "DATA", "YES", 2048)]


def test_oracle_queries_each_tablespace_and_joins_the_rows() -> None:
    manager = _OracleManager(conn_tablespace="APP")

    report = _runtime("oracle", manager).get_storage_inventory_report()

    files, temp = report["sections"]
    assert report["tablespace"] == "APP"
    assert files["status"] == "ok"
    assert files["message"] == "OK (2 tablespace(s) consultado(s))"
    assert [row[0] for row in files["rows"]] == ["APP", "USERS"]
    assert files["rows"][0][2] == "100,50"
    assert [row[0] for row in temp["rows"]] == ["TEMP"]


def test_oracle_reports_partial_errors_and_missing_tablespaces() -> None:
    report = _runtime("oracle", _OracleManager(conn_tablespace="BAD")).get_storage_inventory_report()
    files = report["sections"][0]
    assert files["status"] == "ok"
    assert "Con incidencias parciales: BAD: ORA-00942" in files["message"]

    class _NoTablespaces:
        conn_params: dict[str, Any] = {}

        def get_storage_rows(self, query_name: str, **_: Any) -> list[Any]:
            raise DatabaseException("sin permiso")

    sections = _runtime("oracle", _NoTablespaces()).get_storage_inventory_report()["sections"]
    assert [s["status"] for s in sections] == ["missing_params", "missing_params"]
