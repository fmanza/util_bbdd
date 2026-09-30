"""A3 (hotfix 2026-09-29): nombres de índice únicos por schema con destino PostgreSQL y Oracle.

MySQL/MariaDB/SQL Server admiten el mismo nombre de índice en tablas distintas (MySQL llama a ``KEY (cliente_id)``
``cliente_id``); en PostgreSQL y Oracle el segundo ``CREATE INDEX`` fallaba («relation already exists», ORA-00955).
"""

from __future__ import annotations

import re

from util_bbdd.migrate.emitters.mariadb import MariaDBDDLEmitter
from util_bbdd.migrate.emitters.oracle import OracleDDLEmitter
from util_bbdd.migrate.emitters.postgresql import PostgreSQLDDLEmitter
from util_bbdd.migrate.ir.models import CanonicalColumn, CanonicalIndex, CanonicalTable, CanonicalView


def _table(name: str, *indexes: str, pk: bool = True) -> CanonicalTable:
    columns = [
        CanonicalColumn(
            name=col,
            original_name=col,
            source_type="INT",
            target_type="INTEGER",
            nullable=True,
            default=None,
            comment="",
            ordinal=n,
        )
        for n, col in enumerate(["id", "cliente_id"], start=1)
    ]
    return CanonicalTable(
        name=name,
        original_name=name,
        schema="s",
        columns=columns,
        primary_key=["id"] if pk else [],
        indexes=[CanonicalIndex(name=i, original_name=i, columns=["cliente_id"], unique=False) for i in indexes],
        foreign_keys=[],
        comment="",
        warnings=[],
    )


def _index_names(statements: list[str]) -> list[str]:
    return [m.group(1) for s in statements if (m := re.match(r'CREATE (?:UNIQUE )?INDEX "([^"]+)"', s))]


class TestPostgreSQL:
    def test_second_duplicate_is_renamed_with_table_prefix_and_warning(self) -> None:
        pedidos, facturas = _table("pedidos", "cliente_id"), _table("facturas", "cliente_id")
        names = _index_names(PostgreSQLDDLEmitter().emit_statements([pedidos, facturas]))
        assert sorted(names) == ["cliente_id", "facturas_cliente_id"] or sorted(names) == [
            "cliente_id",
            "pedidos_cliente_id",
        ]
        renamed = [w for t in (pedidos, facturas) for w in t.warnings if w.category == "INDEX"]
        assert len(renamed) == 1 and "único en el schema" in renamed[0].message

    def test_emitting_twice_gives_same_names_and_one_warning(self) -> None:
        tables = [_table("pedidos", "cliente_id"), _table("facturas", "cliente_id")]
        emitter = PostgreSQLDDLEmitter()
        assert _index_names(emitter.emit_statements(tables)) == _index_names(emitter.emit_statements(tables))
        assert sum(len(t.warnings) for t in tables) == 1

    def test_index_named_like_a_table_or_view_is_renamed(self) -> None:
        tables = [_table("pedidos", "facturas"), _table("facturas")]
        views = [CanonicalView("v_idx", "v_idx", "s", "SELECT 1", [], "", [])]
        tables[1].indexes = [CanonicalIndex("v_idx", "v_idx", ["cliente_id"], False)]
        names = _index_names(PostgreSQLDDLEmitter().emit_statements(tables, views))
        assert "facturas" not in names and "v_idx" not in names

    def test_renamed_index_respects_identifier_limit(self) -> None:
        long_table = "t" * 60
        names = _index_names(PostgreSQLDDLEmitter().emit_statements([_table("a", "idx"), _table(long_table, "idx")]))
        assert all(len(n) <= 63 for n in names) and len(set(names)) == 2


class TestOracle:
    def test_names_are_compared_case_insensitively(self) -> None:
        names = _index_names(OracleDDLEmitter().emit_statements([_table("pedidos", "idx"), _table("facturas", "IDX")]))
        assert len({n.upper() for n in names}) == 2

    def test_index_named_like_a_primary_key_is_renamed(self) -> None:
        names = _index_names(OracleDDLEmitter().emit_statements([_table("pedidos"), _table("facturas", "PK_PEDIDOS")]))
        assert "PK_PEDIDOS" not in names

    def test_renamed_index_respects_30_chars(self) -> None:
        tables = [_table("a", "idx_cliente"), _table("tabla_con_nombre_largo_xx", "idx_cliente")]
        names = _index_names(OracleDDLEmitter().emit_statements(tables))
        assert all(len(n) <= 30 for n in names) and len(set(names)) == 2


def test_mariadb_keeps_duplicate_names_per_table() -> None:
    statements = MariaDBDDLEmitter(charset="utf8mb4", collation="utf8mb4_bin").emit_statements(
        [_table("pedidos", "cliente_id"), _table("facturas", "cliente_id")]
    )
    assert sum("`cliente_id` ON" in s or "INDEX `cliente_id`" in s for s in statements) == 2
