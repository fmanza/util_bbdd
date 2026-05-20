"""Tests para MariaDBToPostgreSQLTransformer."""

from __future__ import annotations

from util_bbdd.migrate.ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalTable,
    CanonicalView,
)
from util_bbdd.migrate.transformers.mariadb_to_postgresql import MariaDBToPostgreSQLTransformer


def _col(
    name: str = "COL",
    mariadb_type: str = "VARCHAR",
    nullable: bool = True,
    default: str | None = None,
    char_length: int | None = 255,
    precision: int | None = None,
    scale: int | None = None,
    auto_increment: bool = False,
    is_primary_key: bool = False,
) -> CanonicalColumn:
    return CanonicalColumn(
        name=name,
        original_name=name,
        oracle_type=mariadb_type,
        target_type="",
        nullable=nullable,
        default=default,
        comment="",
        ordinal=1,
        char_length=char_length,
        precision=precision,
        scale=scale,
        auto_increment=auto_increment,
        is_primary_key=is_primary_key,
    )


def _table(
    name: str = "MY_TABLE",
    columns: list[CanonicalColumn] | None = None,
    pk: list[str] | None = None,
    fks: list[CanonicalFK] | None = None,
    indexes: list[CanonicalIndex] | None = None,
) -> CanonicalTable:
    return CanonicalTable(
        name=name,
        original_name=name,
        schema="TEST",
        columns=columns or [],
        primary_key=pk or [],
        indexes=indexes or [],
        foreign_keys=fks or [],
        comment="",
        warnings=[],
    )


class TestColumnTypeMappingPostgreSQL:
    def setup_method(self) -> None:
        self.t = MariaDBToPostgreSQLTransformer()

    def test_int_maps_to_integer(self) -> None:
        col = _col(mariadb_type="INT", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "INTEGER"

    def test_bigint_maps_to_bigint(self) -> None:
        col = _col(mariadb_type="BIGINT", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "BIGINT"

    def test_varchar_maps_to_varchar_with_length(self) -> None:
        col = _col(mariadb_type="VARCHAR", char_length=200)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "VARCHAR(200)"

    def test_varchar_default_length(self) -> None:
        col = _col(mariadb_type="VARCHAR", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "VARCHAR(255)"

    def test_char_maps_to_char_with_length(self) -> None:
        col = _col(mariadb_type="CHAR", char_length=10)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "CHAR(10)"

    def test_text_maps_to_text(self) -> None:
        col = _col(mariadb_type="TEXT", char_length=65535)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "TEXT"

    def test_decimal_maps_to_numeric_with_ps(self) -> None:
        col = _col(mariadb_type="DECIMAL", precision=10, scale=2, char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "NUMERIC(10,2)"

    def test_datetime_maps_to_timestamp(self) -> None:
        col = _col(mariadb_type="DATETIME", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "TIMESTAMP"

    def test_timestamp_maps_to_timestamptz(self) -> None:
        col = _col(mariadb_type="TIMESTAMP", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "TIMESTAMPTZ"

    def test_bool_maps_to_boolean(self) -> None:
        col = _col(mariadb_type="BOOL", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "BOOLEAN"

    def test_blob_maps_to_bytea(self) -> None:
        col = _col(mariadb_type="BLOB", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "BYTEA"

    def test_json_maps_to_jsonb(self) -> None:
        col = _col(mariadb_type="JSON", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "JSONB"

    def test_uuid_maps_to_uuid(self) -> None:
        col = _col(mariadb_type="UUID", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "UUID"

    def test_tinyint_maps_to_smallint(self) -> None:
        col = _col(mariadb_type="TINYINT", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "SMALLINT"

    def test_enum_maps_to_text_with_warning(self) -> None:
        col = _col(mariadb_type="ENUM", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "TEXT"
        assert any(w.severity == "WARNING" for w in result.columns[0].warnings)

    def test_bit_maps_to_bit_with_precision(self) -> None:
        col = _col(mariadb_type="BIT", precision=8, char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "BIT(8)"

    def test_bit1_maps_to_bit1(self) -> None:
        col = _col(mariadb_type="BIT", precision=1, char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "BIT(1)"

    def test_unknown_type_maps_to_text_with_warning(self) -> None:
        col = _col(mariadb_type="UNKNOWNTYPE", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "TEXT"
        assert len(result.columns[0].warnings) > 0

    def test_auto_increment_flag_preserved(self) -> None:
        col = _col(mariadb_type="INT", char_length=None, auto_increment=True, is_primary_key=True)
        result = self.t.transform([_table(columns=[col], pk=["COL"])])[0]
        assert result.columns[0].auto_increment is True

    def test_double_maps_to_double_precision(self) -> None:
        col = _col(mariadb_type="DOUBLE", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "DOUBLE PRECISION"


class TestIdentifierTruncationPostgreSQL:
    def setup_method(self) -> None:
        self.t = MariaDBToPostgreSQLTransformer()

    def test_long_table_name_truncated_at_63(self) -> None:
        long_name = "A" * 70
        table = _table(name=long_name)
        result = self.t.transform([table])[0]
        assert len(result.name) <= 63
        assert len(result.warnings) > 0

    def test_short_table_name_unchanged(self) -> None:
        table = _table(name="MY_TABLE")
        result = self.t.transform([table])[0]
        assert result.name == "MY_TABLE"
        assert not any(w.oracle_type == "IDENTIFIER" for w in result.warnings)

    def test_long_column_name_truncated(self) -> None:
        col = _col(name="C" * 70, mariadb_type="INT", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert len(result.columns[0].name) <= 63


class TestFKTransformPostgreSQL:
    def setup_method(self) -> None:
        self.t = MariaDBToPostgreSQLTransformer()

    def test_external_fk_flagged_with_warning(self) -> None:
        fk = CanonicalFK(
            name="FK_EXT",
            original_name="FK_EXT",
            columns=["COL_A"],
            ref_table="EXTERNAL_TABLE",
            ref_columns=["ID"],
            on_delete="NO ACTION",
            on_update="NO ACTION",
            is_external=True,
        )
        table = _table(name="MY_TABLE", fks=[fk])
        result = self.t.transform([table])[0]
        assert result.foreign_keys[0].is_external is True
        assert any("fuera del schema" in w.message for w in result.warnings)

    def test_internal_fk_no_warning(self) -> None:
        fk = CanonicalFK(
            name="FK_OK",
            original_name="FK_OK",
            columns=["COL_A"],
            ref_table="OTHER_TABLE",
            ref_columns=["ID"],
            on_delete="CASCADE",
            on_update="NO ACTION",
            is_external=False,
        )
        table = _table(name="MY_TABLE", fks=[fk])
        result = self.t.transform([table])[0]
        assert not any("fuera del schema" in w.message for w in result.warnings)


class TestViewTransformPostgreSQLPassThrough:
    def setup_method(self) -> None:
        self.t = MariaDBToPostgreSQLTransformer()

    def test_view_query_preserved(self) -> None:
        view = CanonicalView(
            name="MY_VIEW",
            original_name="MY_VIEW",
            schema="TEST",
            query="SELECT id, name FROM users WHERE active = 1",
            columns=["id", "name"],
            comment="",
            warnings=[],
        )
        result = self.t.transform_views([view])[0]
        assert result.query == "SELECT id, name FROM users WHERE active = 1"

    def test_view_gets_pass_through_warning(self) -> None:
        view = CanonicalView(
            name="MY_VIEW",
            original_name="MY_VIEW",
            schema="TEST",
            query="SELECT NOW()",
            columns=[],
            comment="",
            warnings=[],
        )
        result = self.t.transform_views([view])[0]
        assert any("pass-through" in w.message.lower() for w in result.warnings)
        assert any(w.severity == "WARNING" for w in result.warnings)

    def test_long_view_name_truncated(self) -> None:
        view = CanonicalView(
            name="V" * 70,
            original_name="V" * 70,
            schema="TEST",
            query="SELECT 1",
            columns=[],
            comment="",
            warnings=[],
        )
        result = self.t.transform_views([view])[0]
        assert len(result.name) <= 63
