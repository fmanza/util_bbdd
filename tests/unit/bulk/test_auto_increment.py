"""Unit tests para UpdateAutoIncrement (sin servidor MariaDB).

El Engine falso lleva el dialecto MySQL real: el citado de identificadores y el ``SELECT MAX`` compilado se prueban de
verdad. El catálogo (snapshot de ``metadata/``, E1) se sustituye por uno en memoria; contra MariaDB se comprueba aparte.
"""

from __future__ import annotations

import importlib
import logging

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from sqlalchemy.dialects import mysql
from sqlalchemy.exc import OperationalError

from util_bbdd._core.exceptions import DatabaseOperationError, InvalidDatabaseType
from util_bbdd.metadata.model import ColumnMeta, Kind, SchemaSnapshot, TableMeta

module = importlib.import_module("util_bbdd.bulk._support.auto_increment")
UpdateAutoIncrement = module.UpdateAutoIncrement


def _int_id(name: str = "id", *, autoincrement: bool = True) -> dict[str, Any]:
    return {"name": name, "type": "int", "autoincrement": autoincrement}


class _FakeInspector:
    """Catálogo en memoria con la forma del snapshot de ``metadata/`` (tablas + columnas con ``identity``)."""

    def __init__(self, columns_by_table: dict[str, list[dict[str, Any]]]) -> None:
        self._columns_by_table = columns_by_table
        self.schemas_seen: list[str | None] = []

    def __call__(self, engine: Any, connection: Any, schema: str | None) -> SchemaSnapshot:
        self.schemas_seen.append(schema)
        columns = [
            ColumnMeta(
                table,
                c["name"],
                i,
                c["type"],
                c["type"].split("(")[0].split()[0],
                True,
                identity="by default" if c["autoincrement"] else None,
            )  # fmt: skip
            for table, cols in self._columns_by_table.items()
            for i, c in enumerate(cols, 1)
        ]
        tables = tuple(TableMeta(t) for t in self._columns_by_table)
        return SchemaSnapshot("mariadb", schema or "tienda", {Kind.TABLES: tables, Kind.COLUMNS: tuple(columns)})


class _FakeConnection:
    def __init__(self, max_by_table: dict[str, Any], error: Exception | None = None) -> None:
        self._max_by_table = max_by_table
        self._error = error
        self.executed: list[str] = []

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False

    def execute(self, statement: Any) -> SimpleNamespace:
        if self._error is not None:
            raise self._error
        self.executed.append(str(statement.compile(dialect=mysql.dialect())))
        table_name = statement.get_final_froms()[0].name
        return SimpleNamespace(scalar=lambda: self._max_by_table[table_name])


class _FakeEngine:
    def __init__(self, dialect_name: str = "mariadb", connection: _FakeConnection | None = None) -> None:
        self.dialect = mysql.dialect()
        self.dialect.name = dialect_name
        self.url = SimpleNamespace(database="tienda")
        self._connection = connection or _FakeConnection({})
        self.dispose = MagicMock()

    def connect(self) -> _FakeConnection:
        return self._connection


def _generate(
    columns_by_table: dict[str, list[dict[str, Any]]],
    max_by_table: dict[str, Any],
    schema: str | None = None,
) -> tuple[list[str], _FakeConnection, _FakeInspector]:
    connection = _FakeConnection(max_by_table)
    inspector = _FakeInspector(columns_by_table)
    with patch.object(module, "_snapshot", inspector):
        statements = UpdateAutoIncrement(_FakeEngine(connection=connection), schema=schema).salida_sql()
    return statements, connection, inspector


class TestConstruction:
    def test_dict_config_raises_type_error_with_guidance(self) -> None:
        with pytest.raises(TypeError, match="Engine"):
            UpdateAutoIncrement({"database": "tienda"})  # type: ignore[arg-type]

    @pytest.mark.parametrize("dialect_name", ["mysql", "mariadb"])
    def test_supported_dialects_are_accepted(self, dialect_name: str) -> None:
        UpdateAutoIncrement(_FakeEngine(dialect_name))  # no lanza

    @pytest.mark.parametrize("dialect_name", ["sqlite", "postgresql", "oracle"])
    def test_other_dialects_raise_invalid_database_type(self, dialect_name: str) -> None:
        with pytest.raises(InvalidDatabaseType, match=dialect_name):
            UpdateAutoIncrement(_FakeEngine(dialect_name))

    def test_is_exported_from_bulk_and_no_longer_from_connection(self) -> None:
        """E1 (ADR-003): ``util_bbdd.bulk.UpdateAutoIncrement``; ``connection.mariadb`` ya no lo expone."""
        assert importlib.import_module("util_bbdd.bulk").UpdateAutoIncrement is UpdateAutoIncrement
        package = importlib.import_module("util_bbdd.connection.mariadb")
        assert "UpdateAutoIncrement" not in package.__all__
        with pytest.raises(AttributeError):
            package.UpdateAutoIncrement  # noqa: B018


class TestGeneration:
    def test_uses_max_plus_one(self) -> None:
        statements, _, _ = _generate({"orders": [_int_id()]}, {"orders": 41})
        assert statements == ["ALTER TABLE `orders` AUTO_INCREMENT = 42;"]

    def test_empty_table_restarts_at_one(self) -> None:
        statements, _, _ = _generate({"orders": [_int_id()]}, {"orders": None})
        assert statements == ["ALTER TABLE `orders` AUTO_INCREMENT = 1;"]

    @pytest.mark.parametrize("max_value", [0, -1, -5])
    def test_non_positive_max_never_goes_below_one(self, max_value: int) -> None:
        statements, _, _ = _generate({"orders": [_int_id()]}, {"orders": max_value})
        assert statements == ["ALTER TABLE `orders` AUTO_INCREMENT = 1;"]

    def test_supports_unsigned_bigint_beyond_signed_range(self) -> None:
        column = {"name": "id", "type": "bigint unsigned", "autoincrement": True}
        big = 2**63 + 10
        statements, _, _ = _generate({"events": [column]}, {"events": big})
        assert statements == [f"ALTER TABLE `events` AUTO_INCREMENT = {big + 1};"]

    def test_composite_primary_key_uses_only_the_auto_increment_column(self) -> None:
        columns = [_int_id("tenant", autoincrement=False), _int_id("id")]
        statements, connection, _ = _generate({"items": columns}, {"items": 7})
        assert statements == ["ALTER TABLE `items` AUTO_INCREMENT = 8;"]
        assert "max(id)" in connection.executed[0]
        assert "tenant" not in connection.executed[0]

    def test_tables_without_auto_increment_are_skipped(self) -> None:
        statements, connection, _ = _generate({"config": [_int_id(autoincrement=False)]}, {})
        assert statements == []
        assert connection.executed == []

    def test_non_integer_auto_increment_is_skipped_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        column = {"name": "id", "type": "double", "autoincrement": True}
        with caplog.at_level(logging.WARNING, logger=module.__name__):
            statements, connection, _ = _generate({"legacy": [column]}, {})
        assert statements == []
        assert connection.executed == []
        assert "no entero" in caplog.text

    def test_output_is_sorted_by_table_name(self) -> None:
        columns = {"zeta": [_int_id()], "alfa": [_int_id()], "medio": [_int_id()]}
        statements, _, _ = _generate(columns, {"zeta": 1, "alfa": 2, "medio": 3})
        assert [s.split("`")[1] for s in statements] == ["alfa", "medio", "zeta"]

    def test_identifiers_are_always_quoted_and_backticks_are_escaped(self) -> None:
        columns = {"select": [_int_id()], "raro`nombre": [_int_id()]}
        statements, _, _ = _generate(columns, {"select": 1, "raro`nombre": 1})
        assert statements == [
            "ALTER TABLE `raro``nombre` AUTO_INCREMENT = 2;",
            "ALTER TABLE `select` AUTO_INCREMENT = 2;",
        ]

    def test_schema_qualifies_the_statement_and_the_reflection(self) -> None:
        statements, connection, inspector = _generate({"orders": [_int_id()]}, {"orders": 9}, schema="shop")
        assert statements == ["ALTER TABLE `shop`.`orders` AUTO_INCREMENT = 10;"]
        assert inspector.schemas_seen == ["shop"]
        assert "FROM shop.orders" in connection.executed[0]

    def test_only_select_statements_are_executed(self) -> None:
        _, connection, _ = _generate({"orders": [_int_id()], "items": [_int_id()]}, {"orders": 1, "items": 2})
        assert connection.executed
        assert all(sql.lstrip().upper().startswith("SELECT") for sql in connection.executed)


class TestFailureAndLifecycle:
    def test_sqlalchemy_errors_become_database_operation_error(self) -> None:
        original = OperationalError("SELECT max(id)", {}, Exception("servidor caído"))
        connection = _FakeConnection({}, error=original)
        inspector = _FakeInspector({"orders": [_int_id()]})
        with patch.object(module, "_snapshot", inspector):
            with pytest.raises(DatabaseOperationError, match="AUTO_INCREMENT") as excinfo:
                UpdateAutoIncrement(_FakeEngine(connection=connection)).salida_sql()
        assert excinfo.value.__cause__ is original

    def test_failure_does_not_terminate_the_process(self) -> None:
        connection = _FakeConnection({}, error=OperationalError("x", {}, Exception("boom")))
        with patch.object(module, "_snapshot", _FakeInspector({"t": [_int_id()]})):
            try:
                UpdateAutoIncrement(_FakeEngine(connection=connection)).salida_sql()
            except SystemExit:  # pragma: no cover - lo que hacía la versión anterior
                pytest.fail("la utilidad no debe llamar a sys.exit")
            except DatabaseOperationError:
                pass

    def test_engine_is_not_disposed(self) -> None:
        engine = _FakeEngine(connection=_FakeConnection({"orders": 3}))
        with patch.object(module, "_snapshot", _FakeInspector({"orders": [_int_id()]})):
            UpdateAutoIncrement(engine).salida_sql()
        engine.dispose.assert_not_called()
