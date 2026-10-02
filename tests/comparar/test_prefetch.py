"""Precarga de metadatos de ``SchemaComparator`` (``comparar/_prefetch.py``) sin base de datos.

La paridad contra motores reales está en ``tests/integration/test_comparar_prefetch_engines.py``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from util_bbdd.comparar._prefetch import prefetch_table_metadata
from util_bbdd.comparar.comparator import SchemaComparator


class _MultiInspector:
    """Inspector con get_multi_* que devuelven lo indicado y per-table que registran las llamadas."""

    def __init__(self, multi: dict[str, Any], dialect: str = "postgresql") -> None:
        self._multi = multi
        self.dialect = MagicMock()
        self.dialect.name = dialect
        self.per_table: list[tuple[str, str]] = []

    def __getattr__(self, name: str) -> Any:
        if name.startswith("get_multi_"):
            value = self._multi.get(name)
            if value is None:
                raise AttributeError(name)

            def multi(schema: str | None = None, filter_names: list[str] | None = None) -> Any:
                if isinstance(value, Exception):
                    raise value
                return value

            return multi
        if name.startswith("get_"):

            def per_table(table: str, schema: str | None = None) -> Any:
                self.per_table.append((name, table))
                return {"text": "por tabla"} if name == "get_table_comment" else []

            return per_table
        raise AttributeError(name)


class TestTableMetadata:
    def test_prefetched_values_are_indexed_by_table_name(self) -> None:
        insp = _MultiInspector({"get_multi_columns": {("s", "t1"): ["c1"], ("s", "t2"): ["c2"]}})

        meta = prefetch_table_metadata(insp, "s", ["t1", "t2"], kinds=["columns"])  # type: ignore[arg-type]

        assert (meta.get("columns", "t1"), meta.get("columns", "t2")) == (["c1"], ["c2"])
        assert insp.per_table == []

    def test_table_missing_from_result_falls_back_per_table(self) -> None:
        insp = _MultiInspector({"get_multi_indexes": {(None, "t1"): ["ix"]}})

        meta = prefetch_table_metadata(insp, None, ["t1", "t2"], kinds=["indexes"])  # type: ignore[arg-type]

        assert meta.get("indexes", "t2") == []
        assert insp.per_table == [("get_indexes", "t2")]

    @pytest.mark.parametrize("failure", [NotImplementedError(), OperationalError("q", {}, OSError("x"))])
    def test_failing_multi_falls_back_per_table(self, failure: Exception) -> None:
        insp = _MultiInspector({"get_multi_foreign_keys": failure})

        meta = prefetch_table_metadata(insp, None, ["t1"], kinds=["fks"])  # type: ignore[arg-type]

        assert meta.get("fks", "t1") == []
        assert insp.per_table == [("get_foreign_keys", "t1")]

    def test_missing_multi_method_falls_back_per_table(self) -> None:
        insp = _MultiInspector({})

        meta = prefetch_table_metadata(insp, None, ["t1"], kinds=["pk"])  # type: ignore[arg-type]

        meta.get("pk", "t1")
        assert insp.per_table == [("get_pk_constraint", "t1")]

    def test_comments_are_returned_as_text_both_ways(self) -> None:
        insp = _MultiInspector({"get_multi_table_comment": {(None, "t1"): {"text": "hola"}, (None, "t2"): {}}})

        meta = prefetch_table_metadata(insp, None, ["t1", "t2", "t3"], kinds=["comments"])  # type: ignore[arg-type]

        assert [meta.get("comments", t) for t in ("t1", "t2", "t3")] == ["hola", "", "por tabla"]

    def test_non_dict_result_is_ignored(self) -> None:
        insp = _MultiInspector({"get_multi_columns": MagicMock()})

        meta = prefetch_table_metadata(insp, None, ["t1"], kinds=["columns"])  # type: ignore[arg-type]

        meta.get("columns", "t1")
        assert insp.per_table == [("get_columns", "t1")]

    def test_no_tables_issues_no_queries(self) -> None:
        insp = _MultiInspector({"get_multi_columns": RuntimeError("no debería llamarse")})

        meta = prefetch_table_metadata(insp, None, [], kinds=["columns"])  # type: ignore[arg-type]

        assert meta.prefetched == {}


class TestSqlServerForeignKeys:
    @staticmethod
    def _inspector(rows: list[tuple[Any, ...]], default_schema: str = "dbo") -> tuple[MagicMock, MagicMock]:
        engine = MagicMock(spec=Engine)
        conn = MagicMock()
        engine.connect.return_value.__enter__.return_value = conn
        engine.connect.return_value.__exit__.return_value = False
        conn.execute.return_value.all.return_value = rows
        insp = MagicMock()
        insp.dialect.name = "mssql"
        insp.bind = engine
        insp.default_schema_name = default_schema
        insp.get_multi_foreign_keys.side_effect = AssertionError("no debe usarse get_multi_foreign_keys")
        return insp, conn

    def test_composite_fks_are_grouped_with_sqlalchemy_shape(self) -> None:
        insp, conn = self._inspector(
            [
                ("c", "fk_ab", "a", "dbo", "p", "pa", "NO_ACTION", "NO_ACTION"),
                ("c", "fk_ab", "b", "dbo", "p", "pb", "NO_ACTION", "NO_ACTION"),
                ("c", "fk_x", "x", "otro", "q", "id", "SET_NULL", "CASCADE"),
                ("ajena", "fk_z", "z", "dbo", "p", "id", "NO_ACTION", "NO_ACTION"),  # tabla no pedida
            ]
        )

        meta = prefetch_table_metadata(insp, None, ["c", "p"], kinds=["fks"])

        assert meta.get("fks", "c") == [
            {
                "name": "fk_ab",
                "constrained_columns": ["a", "b"],
                "referred_schema": None,  # schema por defecto pedido como None
                "referred_table": "p",
                "referred_columns": ["pa", "pb"],
                "options": {},
            },
            {
                "name": "fk_x",
                "constrained_columns": ["x"],
                "referred_schema": "otro",
                "referred_table": "q",
                "referred_columns": ["id"],
                "options": {"onupdate": "CASCADE", "ondelete": "SET NULL"},
            },
        ]
        assert meta.get("fks", "p") == []  # pedida y sin FKs: lista vacía, no consulta tabla a tabla
        assert conn.execute.call_args.args[1] == {"schema": "dbo"}

    def test_explicit_schema_keeps_referred_schema(self) -> None:
        insp, _ = self._inspector([("c", "fk", "a", "ventas", "p", "id", "NO_ACTION", "NO_ACTION")])

        meta = prefetch_table_metadata(insp, "ventas", ["c"], kinds=["fks"])

        assert meta.get("fks", "c")[0]["referred_schema"] == "ventas"

    def test_multipart_schema_uses_get_multi(self) -> None:
        """'bd.owner' no lo resuelve SCHEMA_ID: la consulta daría cero FKs sin error."""
        insp, conn = self._inspector([])
        insp.get_multi_foreign_keys.side_effect = None
        insp.get_multi_foreign_keys.return_value = {("bd.dbo", "c"): ["fk"]}

        meta = prefetch_table_metadata(insp, "bd.dbo", ["c"], kinds=["fks"])

        assert meta.get("fks", "c") == ["fk"]
        conn.execute.assert_not_called()

    def test_query_failure_uses_get_multi(self) -> None:
        insp, conn = self._inspector([])
        conn.execute.side_effect = OperationalError("q", {}, OSError("x"))
        insp.get_multi_foreign_keys.side_effect = None
        insp.get_multi_foreign_keys.return_value = {(None, "c"): ["fk"]}

        meta = prefetch_table_metadata(insp, None, ["c"], kinds=["fks"])

        assert meta.get("fks", "c") == ["fk"]


class TestSqlServerPkIndexesComments:
    """Formato de MSDialect para PK, índices y comentarios precargados (paridad real en tests/integration)."""

    @staticmethod
    def _inspector(*results: list[tuple[Any, ...]]) -> MagicMock:
        engine = MagicMock(spec=Engine)
        conn = MagicMock()
        engine.connect.return_value.__enter__.return_value = conn
        engine.connect.return_value.__exit__.return_value = False
        conn.execute.return_value.all.side_effect = list(results)
        insp = MagicMock()
        insp.dialect.name = "mssql"
        insp.bind = engine
        insp.default_schema_name = "dbo"
        for method in ("get_multi_pk_constraint", "get_multi_indexes", "get_multi_table_comment"):
            getattr(insp, method).side_effect = AssertionError(f"no debe usarse {method}")
        return insp

    def test_pk_columns_in_key_order_and_default_without_pk(self) -> None:
        insp = self._inspector([("t", "PK_t", "b", 1), ("t", "PK_t", "a", 1)])

        meta = prefetch_table_metadata(insp, None, ["t", "sin_pk"], kinds=["pk"])

        assert meta.get("pk", "t") == {
            "constrained_columns": ["b", "a"],
            "name": "PK_t",
            "dialect_options": {"mssql_clustered": 1},
        }
        assert meta.get("pk", "sin_pk") == {"constrained_columns": [], "name": None}

    def test_indexes_follow_msdialect_rules(self) -> None:
        index_rows = [
            ("t", 2, "ix_inc", False, 2, None),
            ("t", 3, "ix_filt", True, 2, "([a] IS NOT NULL)"),
            ("t", 4, "ccs", False, 5, None),  # columnstore clustered
            ("t", 5, "ncs", False, 6, None),  # columnstore no clustered
        ]
        column_rows = [
            ("t", 2, "a", False),
            ("t", 2, "b", True),  # INCLUDE
            ("t", 3, "a", False),
            ("t", 4, "a", False),
            ("t", 5, "a", False),
            ("t", 5, "b", True),  # columnstore no clustered: las incluidas cuentan como columnas
        ]
        insp = self._inspector(index_rows, column_rows)

        indexes = prefetch_table_metadata(insp, None, ["t", "sin_ix"], kinds=["indexes"]).get("indexes", "t")

        assert [(i["name"], i["unique"], i["column_names"], i["include_columns"]) for i in indexes] == [
            ("ix_inc", False, ["a"], ["b"]),
            ("ix_filt", True, ["a"], []),
            ("ccs", False, [], []),
            ("ncs", False, ["a", "b"], []),
        ]
        options = {i["name"]: i["dialect_options"] for i in indexes}
        assert options["ix_inc"] == {"mssql_clustered": False, "mssql_include": ["b"]}
        assert options["ix_filt"]["mssql_where"] == "([a] IS NOT NULL)"
        assert options["ccs"] == {"mssql_clustered": True, "mssql_columnstore": True, "mssql_include": []}

    def test_comments_as_text_and_empty_without_comment(self) -> None:
        insp = self._inspector([("t", "tabla t"), ("vacia", "")])

        meta = prefetch_table_metadata(insp, None, ["t", "vacia", "sin"], kinds=["comments"])

        assert [meta.get("comments", n) for n in ("t", "vacia", "sin")] == ["tabla t", "", ""]

    def test_columns_are_not_read_with_own_sql(self) -> None:
        """Los tipos de columna de SQLAlchemy no se reconstruyen: columnas siempre por get_multi_columns."""
        insp = self._inspector()
        insp.get_multi_columns.return_value = {(None, "t"): ["col"]}

        meta = prefetch_table_metadata(insp, None, ["t"], kinds=["columns"])

        assert meta.get("columns", "t") == ["col"]
        insp.bind.connect.assert_not_called()


def test_compare_on_sqlite_gives_same_result_and_query_count_with_prefetch() -> None:
    """SQLite no tiene get_multi_* nativos: la precarga no debe añadir consultas ni cambiar el resultado."""
    engines = [create_engine("sqlite://"), create_engine("sqlite://")]
    for variant, engine in enumerate(engines):
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE p (id INTEGER PRIMARY KEY)"))
            extra = ", extra TEXT" if variant else ""
            conn.execute(text(f"CREATE TABLE c (id INTEGER PRIMARY KEY, p_id INTEGER REFERENCES p(id){extra})"))
            conn.execute(text("CREATE INDEX ix_c ON c(p_id)"))

    def run(prefetch: bool, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, int]:
        counter = {"n": 0}

        def count(*_args: Any, **_kwargs: Any) -> None:
            counter["n"] += 1

        for engine in engines:
            event.listen(engine, "before_cursor_execute", count)
        if not prefetch:
            monkeypatch.setattr(
                "util_bbdd.comparar.comparator.prefetch_table_metadata",
                lambda insp, schema, names, kinds: prefetch_table_metadata(insp, schema, [], kinds=kinds),
            )
        try:
            diff = SchemaComparator().compare(inspect(engines[0]), inspect(engines[1]))
        finally:
            for engine in engines:
                event.remove(engine, "before_cursor_execute", count)
        return diff, counter["n"]

    with pytest.MonkeyPatch.context() as mp:
        with_prefetch, n_with = run(True, mp)
    with pytest.MonkeyPatch.context() as mp:
        without_prefetch, n_without = run(False, mp)

    assert with_prefetch == without_prefetch
    assert with_prefetch.table_diffs[0].column_diffs[0].column_name == "extra"
    assert n_with <= n_without
