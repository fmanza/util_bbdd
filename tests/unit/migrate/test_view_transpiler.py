"""Transpilado de vistas con sqlglot (V1, sesión 2026-09-29c-migrate-views).

Los casos salen del spike V0 (``.ai/sessions/2026-09-29c-migrate-views/v0/V0_SPIKE.md``): el SQL de entrada es el
texto que devuelve el catálogo de cada motor, no el que se escribió.
"""

from __future__ import annotations

import pytest

pytest.importorskip("sqlglot")

from util_bbdd.migrate.ir.models import CanonicalView  # noqa: E402
from util_bbdd.migrate.views.transpiler import ViewTranspileContext, transpile_view  # noqa: E402

TYPES: dict[str, dict[str, str]] = {
    "zzv_clientes": {"id": "INT", "nombre": "VARCHAR(50)", "ciudad": "VARCHAR(50)", "alta": "DATE"},
    "zzv_pedidos": {"id": "INT", "cliente_id": "INT", "fecha": "DATE", "importe": "DECIMAL(10,2)"},
}


def _ctx(source: str, target: str) -> ViewTranspileContext:
    upper_source = source == "oracle"

    def src(name: str) -> str:
        return name.upper() if upper_source else name

    return ViewTranspileContext(
        source_engine=source,
        target_engine=target,
        source_schema="zzv",
        object_names={name: src(name) for name in TYPES} | {"zzv_v": "zzv_v"},
        column_names={column: src(column) for columns in TYPES.values() for column in columns},
        column_types={src(t): {src(c): v for c, v in cols.items()} for t, cols in TYPES.items()},
    )


def _transpile(source: str, target: str, sql: str) -> CanonicalView:
    return transpile_view(CanonicalView("zzv_v", "zzv_v", "zzv", sql, [], "", []), _ctx(source, target))


def _messages(view: CanonicalView) -> str:
    return " | ".join(f"{w.severity}:{w.target_type}:{w.message}" for w in view.warnings)


class TestCatalogArtifacts:
    def test_mysql_charset_cast_becomes_text(self) -> None:
        sql = "select cast(`zzv`.`zzv_clientes`.`id` as char charset utf8mb4) AS `t` from `zzv`.`zzv_clientes`"
        query = _transpile("mysql", "postgresql", sql).query
        assert "CAST(" in query and "AS TEXT)" in query
        assert "utf8mb4" not in query and "CHARACTER SET" not in query

    def test_mysql_to_days_difference_becomes_datediff(self) -> None:
        sql = (
            "select (to_days(`p`.`fecha`) - to_days(`c`.`alta`)) AS `dias` from (`zzv`.`zzv_pedidos` `p` "
            "join `zzv`.`zzv_clientes` `c` on((`c`.`id` = `p`.`cliente_id`)))"
        )
        query = _transpile("mysql", "sqlserver", sql).query
        assert "DATEDIFF(DAY, c.[alta], p.[fecha])" in query
        assert "0000-01-01" not in query

    def test_postgres_text_casts_are_removed_for_oracle(self) -> None:
        sql = " SELECT zzv_clientes.id FROM zzv_clientes WHERE ((zzv_clientes.ciudad)::text = 'Madrid'::text);"
        query = _transpile("postgresql", "oracle", sql).query
        assert "CLOB" not in query and "::" not in query
        assert "'Madrid'" in query

    def test_postgres_cast_of_non_text_column_is_kept(self) -> None:
        query = _transpile("postgresql", "mysql", "SELECT (zzv_clientes.id)::text AS t FROM zzv_clientes").query
        assert "CAST(" in query


class TestTypedArithmetic:
    def test_oracle_date_plus_days_is_explicit_in_mysql(self) -> None:
        query = _transpile("oracle", "mysql", "SELECT alta + 30 AS vence FROM zzv_clientes").query
        assert "DATE_ADD(" in query and "INTERVAL 30 DAY" in query

    def test_postgres_date_difference_in_sqlserver(self) -> None:
        sql = "SELECT p.fecha - c.alta AS dias FROM zzv_pedidos p JOIN zzv_clientes c ON c.id = p.cliente_id"
        assert "DATEDIFF(DAY, c.[alta], p.[fecha])" in _transpile("postgresql", "sqlserver", sql).query

    def test_mysql_interval_arithmetic_in_sqlserver(self) -> None:
        sql = "select (`zzv`.`zzv_clientes`.`alta` + interval 30 day) AS `vence` from `zzv`.`zzv_clientes`"
        assert "DATEADD(DAY, 30," in _transpile("mysql", "sqlserver", sql).query

    def test_sqlserver_string_plus_is_concatenation(self) -> None:
        query = _transpile("sqlserver", "postgresql", "SELECT nombre + ' - ' + ciudad AS e FROM zzv_clientes").query
        assert query.count("||") == 2
        assert "+" not in query


class TestOracleTarget:
    def test_year_becomes_extract_and_date_add_arithmetic(self) -> None:
        sql = (
            "select year(`zzv_clientes`.`alta`) AS `anio`, (`zzv_clientes`.`alta` + interval 30 day) AS `v` "
            "from `zzv`.`zzv_clientes`"
        )
        query = _transpile("mysql", "oracle", sql).query
        assert "EXTRACT(YEAR FROM" in query
        assert '."ALTA" + 30)' in query
        assert "DATE_ADD" not in query and "'30'" not in query

    def test_sqlserver_datediff_without_conversion_wrappers(self) -> None:
        sql = "SELECT DATEDIFF(day, c.alta, p.fecha) AS dias FROM zzv_pedidos p JOIN zzv_clientes c ON c.id = p.cliente_id"
        query = _transpile("sqlserver", "oracle", sql).query
        assert "TIME_STR_TO_TIME" not in query and "DATEDIFF" not in query
        assert '."FECHA" - ' in query

    def test_names_are_uppercase_and_quoted(self) -> None:
        query = _transpile(
            "mysql", "oracle", "select `zzv_clientes`.`nombre` AS `nombre` from `zzv`.`zzv_clientes`"
        ).query
        assert 'FROM "ZZV_CLIENTES"' in query and '"NOMBRE"' in query


class TestNamesAndAliases:
    def test_source_schema_is_removed_and_names_quoted_for_target(self) -> None:
        query = _transpile(
            "mysql", "postgresql", "select `zzv`.`zzv_clientes`.`id` AS `id` from `zzv`.`zzv_clientes`"
        ).query
        assert 'FROM "zzv_clientes"' in query
        assert "zzv." not in query.replace("zzv_", "")

    def test_generated_aliases_are_quoted(self) -> None:
        sql = "SELECT c.id FROM zzv_clientes c WHERE EXISTS (SELECT 1 FROM zzv_pedidos p WHERE p.cliente_id = c.id)"
        assert "AS 1" not in _transpile("postgresql", "mysql", sql).query

    def test_external_table_is_kept_and_reported(self) -> None:
        view = _transpile("postgresql", "mysql", "SELECT x.id FROM otro.tabla x")
        assert "VIEW (referencia externa)" in _messages(view)


class TestSafeguardsAndWarnings:
    @pytest.mark.parametrize(
        ("sql", "construct"),
        [
            ("SELECT c.nombre, p.id FROM zzv_clientes c, zzv_pedidos p WHERE p.cliente_id (+) = c.id", "(+)"),
            ("SELECT id FROM zzv_clientes WHERE ROWNUM <= 3", "ROWNUM"),
            ("SELECT LEVEL AS n FROM DUAL CONNECT BY LEVEL <= 3", "CONNECT BY"),
        ],
    )
    def test_oracle_constructs_without_reliable_translation_are_passthrough(self, sql: str, construct: str) -> None:
        view = _transpile("oracle", "mysql", sql)
        assert view.query == sql
        assert construct in _messages(view) and "VIEW (sin reescribir)" in _messages(view)

    def test_unparseable_sql_is_passthrough(self) -> None:
        view = _transpile("mysql", "postgresql", "select from where (")
        assert view.query == "select from where ("
        assert "VIEW (sin reescribir)" in _messages(view)

    def test_rewritten_view_has_info_warning(self) -> None:
        view = _transpile("mysql", "postgresql", "select `zzv_clientes`.`id` AS `id` from `zzv`.`zzv_clientes`")
        assert "INFO:VIEW (reescrita)" in _messages(view)
        assert "semántica Oracle" not in _messages(view)

    def test_oracle_pairs_carry_semantic_warning(self) -> None:
        assert "VIEW (semántica Oracle)" in _messages(_transpile("oracle", "postgresql", "SELECT id FROM zzv_clientes"))
        assert "VIEW (semántica Oracle)" in _messages(
            _transpile("mysql", "oracle", "select `zzv_clientes`.`id` AS `id` from `zzv`.`zzv_clientes`")
        )

    def test_empty_query_is_untouched(self) -> None:
        view = _transpile("sqlserver", "mysql", "")
        assert view.query == "" and view.warnings == []
