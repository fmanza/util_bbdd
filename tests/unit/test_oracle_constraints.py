"""Tests para constraints y índices Oracle."""

from __future__ import annotations

from util_bbdd.metadata.oracle.constraints import (
    decode_oracle_fk_rows,
    decode_oracle_pk_rows,
    normalize_oracle_delete_rule,
)
from util_bbdd.metadata.oracle.indexes import decode_oracle_index_rows


class TestNormalizeOracleDeleteRule:
    """Tests para normalize_oracle_delete_rule()."""

    def test_normalize_cascade(self) -> None:
        assert normalize_oracle_delete_rule("CASCADE") == "CASCADE"

    def test_normalize_no_action(self) -> None:
        assert normalize_oracle_delete_rule("NO ACTION") == "NO ACTION"

    def test_normalize_restrict(self) -> None:
        assert normalize_oracle_delete_rule("RESTRICT") == "RESTRICT"

    def test_normalize_set_null(self) -> None:
        assert normalize_oracle_delete_rule("SET NULL") == "SET NULL"

    def test_normalize_lowercase(self) -> None:
        assert normalize_oracle_delete_rule("cascade") == "CASCADE"

    def test_normalize_empty_string(self) -> None:
        assert normalize_oracle_delete_rule("") == "NO ACTION"

    def test_normalize_none(self) -> None:
        assert normalize_oracle_delete_rule(None) == "NO ACTION"


class TestDecodePKRows:
    """Tests para decode_oracle_pk_rows()."""

    def test_decode_empty_rows(self) -> None:
        result = decode_oracle_pk_rows([])
        assert result == []

    def test_decode_single_pk(self) -> None:
        rows = [
            ("PK_ORDERS_ID", "ID", 1),
        ]
        result = decode_oracle_pk_rows(rows)
        assert len(result) == 1
        assert result[0][0] == "PK_ORDERS_ID"
        assert result[0][1] == "ID"
        assert result[0][2] == 1

    def test_decode_composite_pk(self) -> None:
        rows = [
            ("PK_COMPOSITE", "COL1", 1),
            ("PK_COMPOSITE", "COL2", 2),
        ]
        result = decode_oracle_pk_rows(rows)
        assert len(result) == 2
        assert result[0][1] == "COL1"
        assert result[1][1] == "COL2"

    def test_decode_pk_with_spaces_in_names(self) -> None:
        rows = [
            ("  PK_ID  ", "  ID  ", 1),
        ]
        result = decode_oracle_pk_rows(rows)
        assert result[0][0] == "PK_ID"
        assert result[0][1] == "ID"

    def test_decode_invalid_rows_skipped(self) -> None:
        rows = [
            ("PK_ID", "ID"),  # Too short
            ("PK_VALID", "COL1", 1),
        ]
        result = decode_oracle_pk_rows(rows)
        assert len(result) == 1

    def test_decode_pk_with_none_values(self) -> None:
        rows = [
            ("PK_ID", None, 1),
        ]
        result = decode_oracle_pk_rows(rows)
        assert result[0][1] == ""


class TestDecodeFKRows:
    """Tests para decode_oracle_fk_rows()."""

    def test_decode_empty_rows(self) -> None:
        result = decode_oracle_fk_rows([])
        assert result == []

    def test_decode_single_fk(self) -> None:
        rows = [
            ("FK_ORDERS_USERS", "USER_ID", "USERS", "USERS", "ID", "CASCADE", "", 1),
        ]
        result = decode_oracle_fk_rows(rows)
        assert len(result) == 1
        assert result[0][0] == "FK_ORDERS_USERS"
        assert result[0][1] == "USER_ID"
        assert result[0][5] == "CASCADE"

    def test_decode_fk_with_no_action(self) -> None:
        rows = [
            ("FK_TEST", "COL1", "REF_SCHEMA", "REF_TABLE", "REF_COL", "NO ACTION", "", 1),
        ]
        result = decode_oracle_fk_rows(rows)
        assert result[0][5] == "NO ACTION"

    def test_decode_composite_fk(self) -> None:
        rows = [
            ("FK_COMPOSITE", "COL1", "SCHEMA1", "TABLE1", "REFCOL1", "CASCADE", "", 1),
            ("FK_COMPOSITE", "COL2", "SCHEMA1", "TABLE1", "REFCOL2", "CASCADE", "", 2),
        ]
        result = decode_oracle_fk_rows(rows)
        assert len(result) == 2

    def test_decode_fk_cross_schema_ref(self) -> None:
        rows = [
            ("FK_CROSS", "ID", "OTHER_SCHEMA", "OTHER_TABLE", "ID", "RESTRICT", "", 1),
        ]
        result = decode_oracle_fk_rows(rows)
        assert result[0][2] == "OTHER_SCHEMA"
        assert result[0][3] == "OTHER_TABLE"

    def test_decode_invalid_fk_rows_skipped(self) -> None:
        rows = [
            ("FK_SHORT",),  # Too short
            ("FK_VALID", "COL1", "SCHEMA", "TABLE", "COL", "CASCADE", "", 1),
        ]
        result = decode_oracle_fk_rows(rows)
        assert len(result) == 1

    def test_decode_fk_set_null(self) -> None:
        rows = [
            ("FK_OPTIONAL", "COL1", "SCHEMA", "TABLE", "COL", "SET NULL", "", 1),
        ]
        result = decode_oracle_fk_rows(rows)
        assert result[0][5] == "SET NULL"


class TestDecodeIndexRows:
    """Tests para decode_oracle_index_rows()."""

    def test_decode_empty_rows(self) -> None:
        result = decode_oracle_index_rows([])
        assert result == []

    def test_decode_single_index(self) -> None:
        rows = [
            ("IDX_USERS_NAME", "NAME", "ASC", "NONUNIQUE", 1),
        ]
        result = decode_oracle_index_rows(rows)
        assert len(result) == 1
        assert result[0][0] == "IDX_USERS_NAME"
        assert result[0][1] == "NAME"
        assert result[0][2] == "ASC"

    def test_decode_unique_index(self) -> None:
        rows = [
            ("IDX_EMAIL", "EMAIL", "ASC", "UNIQUE", 1),
        ]
        result = decode_oracle_index_rows(rows)
        assert result[0][3] == "UNIQUE"

    def test_decode_descending_index(self) -> None:
        rows = [
            ("IDX_DATE_DESC", "CREATED_DATE", "DESC", "NONUNIQUE", 1),
        ]
        result = decode_oracle_index_rows(rows)
        assert result[0][2] == "DESC"

    def test_decode_composite_index(self) -> None:
        rows = [
            ("IDX_COMPOSITE", "COL1", "ASC", "NONUNIQUE", 1),
            ("IDX_COMPOSITE", "COL2", "DESC", "NONUNIQUE", 2),
        ]
        result = decode_oracle_index_rows(rows)
        assert len(result) == 2
        assert result[0][0] == result[1][0]
        assert result[0][4] == 1
        assert result[1][4] == 2

    def test_decode_index_preserves_column_order(self) -> None:
        rows = [
            ("IDX_MULTI", "COL_A", "ASC", "NONUNIQUE", 1),
            ("IDX_MULTI", "COL_B", "ASC", "NONUNIQUE", 2),
            ("IDX_MULTI", "COL_C", "DESC", "NONUNIQUE", 3),
        ]
        result = decode_oracle_index_rows(rows)
        assert result[0][1] == "COL_A"
        assert result[1][1] == "COL_B"
        assert result[2][1] == "COL_C"

    def test_decode_invalid_index_rows_skipped(self) -> None:
        rows = [
            ("IDX_SHORT", "COL"),  # Too short
            ("IDX_VALID", "COL1", "ASC", "NONUNIQUE", 1),
        ]
        result = decode_oracle_index_rows(rows)
        assert len(result) == 1

    def test_decode_index_with_none_values(self) -> None:
        rows = [
            ("IDX_TEST", None, None, "NONUNIQUE", None),
        ]
        result = decode_oracle_index_rows(rows)
        assert result[0][1] == ""
        assert result[0][2] == "ASC"
        assert result[0][4] == 0
