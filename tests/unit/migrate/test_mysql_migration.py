"""MySQL en ``migrate/``: extractor, emitter, transformers de la familia, collation y planner (sin BD real)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from util_bbdd.migrate import (
    DEFAULT_COLLATION_MYSQL,
    MariaDBDDLEmitter,
    MariaDBFullTypeSchemaExtractor,
    MariaDBToMySQLTransformer,
    MigrationPlanner,
    MySQLDDLEmitter,
    MySQLSchemaExtractor,
    MySQLToMariaDBTransformer,
    OracleDDLEmitter,
    PostgreSQLDDLEmitter,
    SQLServerDDLEmitter,
    validate_mysql_collation,
)
from util_bbdd.migrate.emitters.mysql import strip_int_display_width
from util_bbdd.migrate.extractors.mysql import quote_literal_default
from util_bbdd.migrate.ir.models import CanonicalColumn, CanonicalTable

# (COLUMN_NAME, DATA_TYPE, CHAR_LEN, PRECISION, SCALE, IS_NULLABLE, COLUMN_DEFAULT, EXTRA, COMMENT, ORDINAL, COLUMN_TYPE)
MYSQL_COLUMNS: list[tuple[Any, ...]] = [
    ("id", "int", None, 10, 0, "NO", None, "auto_increment", "", 1, "int unsigned"),
    ("nombre", "varchar", 80, None, None, "NO", "sin nombre", "", "", 2, "varchar(80)"),
    ("codigo", "varchar", 10, None, None, "YES", "5", "", "", 3, "varchar(10)"),
    ("estado", "enum", 1, None, None, "NO", "A", "", "", 4, "enum('A','B')"),
    ("saldo", "decimal", None, 12, 2, "NO", "0.00", "", "", 5, "decimal(12,2)"),
    ("alta", "datetime", None, None, None, "NO", "CURRENT_TIMESTAMP", "DEFAULT_GENERATED", "", 6, "datetime"),
    ("cita", "varchar", 20, None, None, "YES", "it's", "", "", 7, "varchar(20)"),
]


def _manager(columns: list[tuple[Any, ...]] | None = None) -> MagicMock:
    """Manager simulado de la familia MySQL/MariaDB (INFORMATION_SCHEMA)."""
    manager = MagicMock()
    rows_by_marker: dict[str, list[tuple[Any, ...]]] = {
        "TABLE_TYPE = 'BASE TABLE'": [("zz_cliente", "clientes")],
        "COLUMN_TYPE": columns if columns is not None else MYSQL_COLUMNS,
        "CONSTRAINT_NAME = 'PRIMARY'": [("id",)],
    }

    def side_effect(sql: str, params: dict[str, Any]) -> list[tuple[Any, ...]]:
        for marker, rows in rows_by_marker.items():
            if marker in sql:
                return rows
        return []

    manager.execute_custom_many.side_effect = side_effect
    return manager


class TestQuoteLiteralDefault:
    @pytest.mark.parametrize(
        ("default", "data_type", "extra", "expected"),
        [
            ("x", "varchar", "", "'x'"),
            ("5", "varchar", "", "'5'"),
            ("it's", "varchar", "", "'it''s'"),
            ("'ya'", "varchar", "", "'ya'"),
            ("0.00", "decimal", "", "0.00"),
            ("1", "tinyint", "", "1"),
            ("CURRENT_TIMESTAMP", "datetime", "DEFAULT_GENERATED", "CURRENT_TIMESTAMP"),
            ("2020-01-01", "date", "", "'2020-01-01'"),
            (None, "varchar", "", None),
        ],
    )
    def test_quote(self, default: str | None, data_type: str, extra: str, expected: str | None) -> None:
        assert quote_literal_default(default, data_type, extra) == expected


class TestMySQLSchemaExtractor:
    def test_defaults_follow_mariadb_convention_and_data_type_by_default(self) -> None:
        table = MySQLSchemaExtractor(_manager()).extract("db1")[0]
        cols = {c.name: c for c in table.columns}
        assert cols["nombre"].default == "'sin nombre'"
        assert cols["codigo"].default == "'5'"
        assert cols["saldo"].default == "0.00"
        assert cols["alta"].default == "CURRENT_TIMESTAMP"
        assert cols["cita"].default == "'it''s'"
        assert cols["estado"].oracle_type == "ENUM"
        assert cols["id"].auto_increment and cols["id"].is_primary_key
        assert table.comment == "clientes"

    def test_full_column_types(self) -> None:
        cols = {c.name: c for c in MySQLSchemaExtractor(_manager(), full_column_types=True).extract("db1")[0].columns}
        assert cols["estado"].oracle_type == "enum('A','B')"
        assert cols["id"].oracle_type == "int unsigned"

    def test_mariadb_full_type_extractor_keeps_defaults(self) -> None:
        rows = [("nombre", "varchar", 50, None, None, "NO", "'x'", "", "", 1, "varchar(50)")]
        col = MariaDBFullTypeSchemaExtractor(_manager(rows)).extract("db1")[0].columns[0]
        assert col.default == "'x'"
        assert col.oracle_type == "varchar(50)"


class TestMySQLEmitter:
    @pytest.mark.parametrize(
        ("column_type", "expected"),
        [
            ("INT(11)", "INT"),
            ("int(10) unsigned", "int unsigned"),
            ("BIGINT(20)", "BIGINT"),
            ("TINYINT(1)", "TINYINT(1)"),
            ("TINYINT(4)", "TINYINT"),
            ("DECIMAL(10,2)", "DECIMAL(10,2)"),
            ("VARCHAR(40)", "VARCHAR(40)"),
        ],
    )
    def test_strip_int_display_width(self, column_type: str, expected: str) -> None:
        assert strip_int_display_width(column_type) == expected

    def test_emits_without_int_width_and_with_collation(self) -> None:
        table = CanonicalTable(
            name="t",
            original_name="t",
            schema="s",
            columns=[
                CanonicalColumn("id", "id", "INT", "INT", False, None, "", 1, auto_increment=True),
                CanonicalColumn("n", "n", "INT", "INT(11)", True, None, "", 2),
                CanonicalColumn("flag", "flag", "TINYINT", "TINYINT(1)", True, None, "", 3),
            ],
            primary_key=["id"],
            indexes=[],
            foreign_keys=[],
            comment="",
            warnings=[],
        )
        ddl = MySQLDDLEmitter(charset="utf8mb4", collation=DEFAULT_COLLATION_MYSQL).emit([table])
        assert "`id` INT NOT NULL AUTO_INCREMENT" in ddl
        assert "`n` INT" in ddl and "INT(11)" not in ddl
        assert "`flag` TINYINT(1)" in ddl
        assert "COLLATE=utf8mb4_0900_ai_ci" in ddl


class TestFamilyTransformers:
    def _col(self, source_type: str) -> CanonicalTable:
        return CanonicalTable(
            name="t",
            original_name="t",
            schema="s",
            columns=[CanonicalColumn("c", "c", source_type, "", True, None, "", 1)],
            primary_key=[],
            indexes=[],
            foreign_keys=[],
            comment="",
            warnings=[],
        )

    @pytest.mark.parametrize(
        ("source", "target"), [("uuid", "CHAR(36)"), ("inet4", "VARCHAR(15)"), ("INET6", "VARCHAR(39)")]
    )
    def test_mariadb_to_mysql_maps_mariadb_only_types(self, source: str, target: str) -> None:
        col = MariaDBToMySQLTransformer().transform([self._col(source)])[0].columns[0]
        assert col.target_type == target
        assert col.warnings and "MariaDB" in col.warnings[0].message
        assert col.ddl_comment is None

    @pytest.mark.parametrize("source", ["enum('a','b')", "int unsigned", "decimal(10,2)", "json"])
    def test_family_types_pass_through(self, source: str) -> None:
        for transformer in (MariaDBToMySQLTransformer(), MySQLToMariaDBTransformer()):
            col = transformer.transform([self._col(source)])[0].columns[0]
            assert col.target_type == source
            assert col.warnings == []


class TestPlannerWithMySQL:
    def test_default_collation_is_remapped_for_mysql(self) -> None:
        planner = MigrationPlanner(source_engine="oracle", target_engine="mysql")
        assert planner._collation == DEFAULT_COLLATION_MYSQL

    def test_explicit_valid_collation_is_kept(self) -> None:
        planner = MigrationPlanner(source_engine="oracle", target_engine="mysql", collation="utf8mb4_bin")
        assert planner._collation == "utf8mb4_bin"

    def test_mariadb_only_collation_rejected(self) -> None:
        with pytest.raises(ValueError, match="MySQL"):
            validate_mysql_collation("utf8mb4_uca1400_ai_ci")

    def test_mariadb_target_keeps_mariadb_default(self) -> None:
        assert MigrationPlanner(source_engine="mysql", target_engine="mariadb")._collation == "utf8mb4_uca1400_ai_ci"

    @pytest.mark.parametrize(
        ("target", "emitter_cls"),
        [
            ("mariadb", MariaDBDDLEmitter),
            ("oracle", OracleDDLEmitter),
            ("postgresql", PostgreSQLDDLEmitter),
            ("sqlserver", SQLServerDDLEmitter),
        ],
    )
    def test_mysql_source_pipelines(self, target: str, emitter_cls: type) -> None:
        plan = MigrationPlanner(source_engine="mysql", target_engine=target).plan(_manager(), "db1")
        assert type(plan.emitter) is emitter_cls
        assert [t.name.lower() for t in plan.tables] == ["zz_cliente"]
        estado = next(c for c in plan.tables[0].columns if c.name.lower() == "estado")
        # Hacia MariaDB se conserva el tipo completo; hacia el resto, el mapa de tipos de MariaDB.
        assert (estado.target_type == "enum('A','B')") is (target == "mariadb")
        assert plan.emit_ddl()

    def test_mariadb_to_mysql_uses_full_types_and_mysql_emitter(self) -> None:
        plan = MigrationPlanner(source_engine="mariadb", target_engine="mysql").plan(_manager(), "db1")
        assert type(plan.emitter) is MySQLDDLEmitter
        estado = next(c for c in plan.tables[0].columns if c.name == "estado")
        assert estado.target_type == "enum('A','B')"
        assert "COLLATE=utf8mb4_0900_ai_ci" in plan.emit_ddl()

    @pytest.mark.parametrize("source", ["oracle", "sqlserver", "postgresql"])
    def test_other_sources_to_mysql_use_mysql_emitter(self, source: str) -> None:
        planner = MigrationPlanner(source_engine=source, target_engine="mysql")
        plan = planner.plan(MagicMock(execute_custom_many=MagicMock(return_value=[])), "s")
        assert type(plan.emitter) is MySQLDDLEmitter
        assert plan.target_engine == "mysql"

    def test_all_twenty_pairs_are_supported(self) -> None:
        engines = ["oracle", "mariadb", "mysql", "sqlserver", "postgresql"]
        pairs = [(s, t) for s in engines for t in engines if s != t]
        assert len(pairs) == 20
        for source, target in pairs:
            MigrationPlanner(source_engine=source, target_engine=target)
