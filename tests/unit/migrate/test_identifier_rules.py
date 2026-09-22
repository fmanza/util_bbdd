"""Tests para reglas de identificadores MariaDB."""

from __future__ import annotations

from util_bbdd.migrate._compat.identifier_rules import (
    MAX_MARIADB_IDENTIFIER_LENGTH,
    check_identifier,
    find_case_insensitive_collisions,
    truncate_identifier,
)


class TestTruncateIdentifier:
    def test_short_name_unchanged(self) -> None:
        name = "my_table"
        result, truncated = truncate_identifier(name)
        assert result == name
        assert truncated is False

    def test_exactly_64_unchanged(self) -> None:
        name = "a" * MAX_MARIADB_IDENTIFIER_LENGTH
        result, truncated = truncate_identifier(name)
        assert result == name
        assert truncated is False

    def test_65_chars_truncated(self) -> None:
        name = "a" * 65
        result, truncated = truncate_identifier(name)
        assert truncated is True
        assert len(result) <= MAX_MARIADB_IDENTIFIER_LENGTH

    def test_long_name_has_hash_suffix(self) -> None:
        name = "x" * 100
        result, truncated = truncate_identifier(name)
        assert truncated is True
        # El sufijo hash debe ser 4 chars precedidos de '_'
        assert "_" in result
        parts = result.rsplit("_", 1)
        assert len(parts[1]) == 4

    def test_same_long_name_produces_same_result(self) -> None:
        name = "table_" + "a" * 70
        r1, _ = truncate_identifier(name)
        r2, _ = truncate_identifier(name)
        assert r1 == r2

    def test_different_long_names_produce_different_results(self) -> None:
        name_a = "table_a_" + "x" * 70
        name_b = "table_b_" + "x" * 70
        r_a, _ = truncate_identifier(name_a)
        r_b, _ = truncate_identifier(name_b)
        assert r_a != r_b


class TestCheckIdentifier:
    def test_short_name_no_warning(self) -> None:
        adapted, warn = check_identifier("short_name")
        assert adapted == "short_name"
        assert warn is None

    def test_long_name_returns_warning(self) -> None:
        long_name = "identifier_" + "z" * 60
        adapted, warn = check_identifier(long_name)
        assert warn is not None
        assert long_name in warn
        assert len(adapted) <= MAX_MARIADB_IDENTIFIER_LENGTH

    def test_empty_string_no_warning(self) -> None:
        adapted, warn = check_identifier("")
        assert adapted == ""
        assert warn is None


class TestFindCaseInsensitiveCollisions:
    """CMP-02 (AUDIT_CODE 2026-09-22): identifier_rules.py no detectaba pares de
    identificadores que solo difieren en case, riesgo bajo case-folding de motor."""

    def test_no_collision_for_distinct_names(self) -> None:
        assert find_case_insensitive_collisions(["users", "orders", "products"]) == []

    def test_detects_case_only_collision(self) -> None:
        collisions = find_case_insensitive_collisions(["Employees", "EMPLOYEES"])
        assert collisions == [("Employees", "EMPLOYEES")]

    def test_exact_duplicate_same_case_not_reported(self) -> None:
        """Un duplicado literal (mismo case) no es una colisión de folding."""
        assert find_case_insensitive_collisions(["users", "users"]) == []

    def test_three_way_collision_reports_pairs_against_first_seen(self) -> None:
        collisions = find_case_insensitive_collisions(["Orders", "ORDERS", "orders"])
        assert collisions == [("Orders", "ORDERS"), ("Orders", "orders")]

    def test_empty_input_no_collisions(self) -> None:
        assert find_case_insensitive_collisions([]) == []

    def test_single_name_no_collisions(self) -> None:
        assert find_case_insensitive_collisions(["users"]) == []
