"""Traducción de ``:nombre`` al ``paramstyle`` de cada driver (``metadata._paramstyle``)."""

from __future__ import annotations

import pytest

from util_bbdd.metadata._paramstyle import expand_lists, placeholders, to_driver

SQL = "SELECT c.relname FROM pg_class c WHERE c.relnamespace = :schema::regnamespace AND c.relname IN (:tables)"


def test_expand_lists_inside_in() -> None:
    sql, params = expand_lists(SQL, {"schema": "s", "tables": ["a", "b"]})
    assert sql.endswith("IN (:tables_0, :tables_1)")
    assert params == {"schema": "s", "tables_0": "a", "tables_1": "b"}


def test_expand_empty_list_matches_nothing() -> None:
    sql, params = expand_lists("SELECT 1 WHERE x IN (:t)", {"t": []})
    assert sql == "SELECT 1 WHERE x IN (NULL)"
    assert params == {}


@pytest.mark.parametrize(
    ("style", "expected_sql", "expected_args"),
    [
        ("named", "x = :a AND y IN (:t_0, :t_1)", {"a": 1, "t_0": "p", "t_1": "q"}),
        ("pyformat", "x = %(a)s AND y IN (%(t_0)s, %(t_1)s)", {"a": 1, "t_0": "p", "t_1": "q"}),
        ("format", "x = %s AND y IN (%s, %s)", [1, "p", "q"]),
        ("qmark", "x = ? AND y IN (?, ?)", [1, "p", "q"]),
        ("numeric", "x = :1 AND y IN (:2, :3)", [1, "p", "q"]),
        ("dollar", "x = $1 AND y IN ($2, $3)", [1, "p", "q"]),
    ],
)
def test_to_driver_styles(style: str, expected_sql: str, expected_args: object) -> None:
    sql, args = to_driver("x = :a AND y IN (:t)", {"a": 1, "t": ("p", "q"), "unused": 9}, style)  # type: ignore[arg-type]
    assert sql == expected_sql
    assert args == expected_args


def test_casts_and_literals_are_not_parameters() -> None:
    sql = "SELECT 'a:b', '::x', d.classid = 'pg_class'::regclass FROM t WHERE n = :schema"
    out, args = to_driver(sql, {"schema": "s"}, "pyformat")
    assert out == "SELECT 'a:b', '::x', d.classid = 'pg_class'::regclass FROM t WHERE n = %(schema)s"
    assert args == {"schema": "s"}


def test_percent_is_escaped_only_for_percent_styles() -> None:
    sql = "SELECT x FROM t WHERE d LIKE 'nextval(%' AND n = :n AND m % 2 = 0"
    assert to_driver(sql, {"n": 1}, "pyformat")[0] == (
        "SELECT x FROM t WHERE d LIKE 'nextval(%%' AND n = %(n)s AND m %% 2 = 0"
    )
    assert to_driver(sql, {"n": 1}, "qmark")[0] == "SELECT x FROM t WHERE d LIKE 'nextval(%' AND n = ? AND m % 2 = 0"


def test_sql_without_parameters_is_untouched() -> None:
    sql = "SELECT version() WHERE 'a%' LIKE 'a%'"
    assert to_driver(sql, {}, "pyformat") == (sql, None)


def test_missing_parameter_raises() -> None:
    with pytest.raises(KeyError):
        to_driver("x = :a", {}, "named")


def test_quoted_identifiers_and_assignments() -> None:
    assert placeholders('SELECT ":x" FROM t WHERE a := 1 AND b = :b') == ["b"]
