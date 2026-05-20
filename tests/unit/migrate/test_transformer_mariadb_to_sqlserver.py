"""Tests para MariaDBToSQLServerTransformer."""

from __future__ import annotations

from util_bbdd.migrate.ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalTable,
    CanonicalView,
)
from util_bbdd.migrate.transformers.mariadb_to_sqlserver import MariaDBToSQLServerTransformer


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


class TestColumnTypeMappingSQLServer:
    def setup_method(self) -> None:
        self.t = MariaDBToSQLServerTransformer()

    def test_int_maps_to_int(self) -> None:
        col = _col(mariadb_type="INT", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "INT"

    def test_bigint_maps_to_bigint(self) -> None:
        col = _col(mariadb_type="BIGINT", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "BIGINT"

    def test_varchar_maps_to_nvarchar_with_length(self) -> None:
        col = _col(mariadb_type="VARCHAR", char_length=200)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "NVARCHAR(200)"

    def test_varchar_over_4000_maps_to_nvarchar_max(self) -> None:
        col = _col(mariadb_type="VARCHAR", char_length=5000)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "NVARCHAR(MAX)"

    def test_char_maps_to_nchar_with_length(self) -> None:
        col = _col(mariadb_type="CHAR", char_length=10)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "NCHAR(10)"

    def test_text_maps_to_nvarchar_max(self) -> None:
        col = _col(mariadb_type="TEXT", char_length=65535)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "NVARCHAR(MAX)"

    def test_decimal_maps_to_decimal_with_ps(self) -> None:
        col = _col(mariadb_type="DECIMAL", precision=10, scale=2, char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "DECIMAL(10,2)"

    def test_datetime_maps_to_datetime2(self) -> None:
        col = _col(mariadb_type="DATETIME", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "DATETIME2"

    def test_bool_maps_to_bit(self) -> None:
        col = _col(mariadb_type="BOOL", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "BIT"

    def test_blob_maps_to_varbinary_max(self) -> None:
        col = _col(mariadb_type="BLOB", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "VARBINARY(MAX)"

    def test_tinyint_maps_with_warning(self) -> None:
        col = _col(mariadb_type="TINYINT", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "TINYINT"
        assert any(w.severity == "WARNING" for w in result.columns[0].warnings)

    def test_binary_maps_to_binary_with_length(self) -> None:
        col = _col(mariadb_type="BINARY", char_length=16)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "BINARY(16)"

    def test_varbinary_within_8000_maps_to_varbinary(self) -> None:
        col = _col(mariadb_type="VARBINARY", char_length=500)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "VARBINARY(500)"

    def test_varbinary_over_8000_maps_to_varbinary_max(self) -> None:
        col = _col(mariadb_type="VARBINARY", char_length=9000)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "VARBINARY(MAX)"

    def test_enum_maps_to_nvarchar_255(self) -> None:
        col = _col(mariadb_type="ENUM", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "NVARCHAR(255)"

    def test_json_maps_with_warning(self) -> None:
        col = _col(mariadb_type="JSON", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert any(w.severity == "WARNING" for w in result.columns[0].warnings)

    def test_uuid_maps_to_uniqueidentifier(self) -> None:
        col = _col(mariadb_type="UUID", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "UNIQUEIDENTIFIER"

    def test_timestamp_maps_with_warning(self) -> None:
        col = _col(mariadb_type="TIMESTAMP", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "DATETIME2"
        assert any(w.severity in ("WARNING", "INFO") for w in result.columns[0].warnings)

    def test_unknown_type_maps_to_nvarchar_max_with_warning(self) -> None:
        col = _col(mariadb_type="UNKNOWNTYPE", char_length=None)
        result = self.t.transform([_table(columns=[col])])[0]
        assert result.columns[0].target_type == "NVARCHAR(MAX)"
        assert len(result.columns[0].warnings) > 0

    def test_auto_increment_flag_preserved(self) -> None:
        col = _col(mariadb_type="INT", char_length=None, auto_increment=True, is_primary_key=True)
        result = self.t.transform([_table(columns=[col], pk=["COL"])])[0]
        assert result.columns[0].auto_increment is True


class TestIdentifierTruncationSQLServer:
    def setup_method(self) -> None:
        self.t = MariaDBToSQLServerTransformer()

    def test_long_table_name_not_truncated_under_128(self) -> None:
        # SQL Server allows 128 chars; a 40-char name should pass unchanged
        table = _table(name="A" * 40)
        result = self.t.transform([table])[0]
        assert result.name == "A" * 40
        assert not any(w.oracle_type == "IDENTIFIER" for w in result.warnings)

    def test_very_long_table_name_truncated_at_128(self) -> None:
        long_name = "B" * 140
        table = _table(name=long_name)
        result = self.t.transform([table])[0]
        assert len(result.name) <= 128
        assert len(result.warnings) > 0

    def test_short_table_name_unchanged(self) -> None:
        table = _table(name="MY_TABLE")
        result = self.t.transform([table])[0]
        assert result.name == "MY_TABLE"


class TestFKTransformSQLServer:
    def setup_method(self) -> None:
        self.t = MariaDBToSQLServerTransformer()

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


class TestViewTransformSQLServerPassThrough:
    def setup_method(self) -> None:
        self.t = MariaDBToSQLServerTransformer()

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
            name="V" * 140,
            original_name="V" * 140,
            schema="TEST",
            query="SELECT 1",
            columns=[],
            comment="",
            warnings=[],
        )
        result = self.t.transform_views([view])[0]
        assert len(result.name) <= 128
