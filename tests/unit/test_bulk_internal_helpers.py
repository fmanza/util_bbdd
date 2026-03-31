"""Tests focalizados para los helpers internos de bulk."""

from __future__ import annotations

import re

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, insert

from util_bbdd.bulk._batch_execution import execute_batch_statement
from util_bbdd.bulk._persistence import BulkPersistenceManager
from util_bbdd.bulk._sql_helpers import generate_insert_sql
from util_bbdd.bulk._validation import build_update_plan, resolve_sql_output_path
from util_bbdd.bulk.audit import AuditManager


def test_resolve_sql_output_path_requires_path_instance(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="path_sql es obligatorio"):
        resolve_sql_output_path(None, table_name="users", operation="insert", generate_name=lambda *_: Path("x.sql"))

    with pytest.raises(ValueError, match="instancia de Path"):
        resolve_sql_output_path(
            "invalid",
            table_name="users",
            operation="insert",
            generate_name=lambda *_: Path("x.sql"),
        )

    assert (
        resolve_sql_output_path(
            tmp_path,
            table_name="users",
            operation="insert",
            generate_name=lambda *_: Path("generated.sql"),
        )
        == tmp_path / "generated.sql"
    )


def test_build_update_plan_validates_pk_and_updatable_columns() -> None:
    table = Table(
        "users",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("name", String(50)),
    )

    plan = build_update_plan(table, ["id", "name"], "users")

    assert plan.pk_cols == ["id"]
    assert plan.update_cols == ["name"]
    assert plan.pk_param_map == {"id": "pk_id"}

    with pytest.raises(ValueError, match="claves primarias presentes"):
        build_update_plan(table, ["name"], "users")


def test_execute_batch_statement_splits_payload_by_chunk_size() -> None:
    engine = create_engine("sqlite:///:memory:")
    table = Table(
        "users",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("name", String(50)),
    )
    stmt = insert(table)
    records = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}, {"id": 3, "name": "c"}]

    connection = MagicMock()

    class _BeginContext:
        def __enter__(self):
            return connection

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    engine.begin = MagicMock(return_value=_BeginContext())

    execute_batch_statement(engine=engine, records=records, stmt=stmt, chunk_size=2)

    assert connection.execute.call_count == 2
    first_payload = connection.execute.call_args_list[0].args[1]
    second_payload = connection.execute.call_args_list[1].args[1]
    assert first_payload == records[:2]
    assert second_payload == records[2:]


def test_generate_insert_sql_returns_literal_statements() -> None:
    engine = create_engine("sqlite:///:memory:")
    table = Table(
        "users",
        MetaData(),
        Column("id", Integer, primary_key=True),
        Column("name", String(50)),
    )
    sql_lines = generate_insert_sql(
        insert(table),
        [{"id": 1, "name": "Alice"}],
        engine.dialect,
    )

    assert len(sql_lines) == 1
    assert "INSERT INTO users" in sql_lines[0]
    assert "Alice" in sql_lines[0]


def test_bulk_persistence_manager_builds_sql_path_with_dynamic_name(tmp_path: Path) -> None:
    persistence = BulkPersistenceManager(
        engine_url="sqlite:///mydb.db",
        logger=MagicMock(),
        audit_manager=MagicMock(spec=AuditManager),
        db_info="SQLITE",
    )

    sql_path = persistence.resolve_sql_output_path(tmp_path, "users", "insert")

    assert sql_path.parent == tmp_path
    assert re.fullmatch(r"mydb\.db-users-insert_\d{8}_\d{6}\.sql", sql_path.name)


def test_bulk_persistence_manager_persists_sql_file(tmp_path: Path) -> None:
    logger = MagicMock()
    persistence = BulkPersistenceManager(
        engine_url="sqlite:///mydb.db",
        logger=logger,
        audit_manager=MagicMock(spec=AuditManager),
        db_info="SQLITE",
    )
    sql_file = tmp_path / "bulk" / "users.sql"

    persistence.persist_sql(["SELECT 1;", "SELECT 2;"], sql_file)

    assert sql_file.read_text(encoding="utf-8") == "SELECT 1;\nSELECT 2;"
    logger.info.assert_called_with(f"💾 SQL guardada en: {sql_file}")


def test_bulk_persistence_manager_registers_operations_in_audit() -> None:
    audit_manager = MagicMock(spec=AuditManager)
    persistence = BulkPersistenceManager(
        engine_url="sqlite:///mydb.db",
        logger=MagicMock(),
        audit_manager=audit_manager,
        db_info="SQLITE",
    )

    persistence.register_operation(
        table_name="users",
        operation="INSERT",
        rowcount=3,
        elapsed=1.25,
        generated_sql=True,
    )

    audit_manager.registrar_operacion.assert_called_once_with("users", "SQLITE", "INSERT", 3, 1.25, True)
