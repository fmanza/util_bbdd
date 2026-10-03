"""Tests para MariaDBSchemaExtractor (sin BD externa — manager mock)."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.migrate.extractors.mariadb import MariaDBSchemaExtractor, _parse_raw_column

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_manager(
    tables: list[tuple] | None = None,
    columns: list[tuple] | None = None,
    pks: list[tuple] | None = None,
    fks: list[tuple] | None = None,
    indexes: list[tuple] | None = None,
    views: list[tuple] | None = None,
    view_columns: list[tuple] | None = None,
) -> MagicMock:
    """Construye un manager mock que devuelve filas predefinidas por consulta.

    Columnas (también las de vistas), PK, FK e índices se leen por schema (D1): la primera columna es el nombre de la
    tabla o vista. Como antes con la consulta por tabla, cada tabla del mock recibe las mismas filas.
    """
    manager = MagicMock()
    table_names = [str(t[0]) for t in tables or [] if t]
    view_names = [str(v[0]) for v in views or [] if v]

    def per_object(names: list[str], rows: list[tuple] | None) -> list[tuple]:
        return [(name, *row) for name in names for row in rows or []]

    def side_effect(sql: str, params: dict) -> list:
        sql_upper = sql.upper()
        if "INFORMATION_SCHEMA.VIEWS" in sql_upper:
            return views or []
        if "INFORMATION_SCHEMA.TABLES" in sql_upper:
            return tables or []
        if "INFORMATION_SCHEMA.COLUMNS" in sql_upper:
            return per_object(table_names, columns) + per_object(view_names, view_columns)
        if "CONSTRAINT_NAME = 'PRIMARY'" in sql_upper:
            return per_object(table_names, pks)
        if "REFERENTIAL_CONSTRAINTS" in sql_upper:  # reglas ON DELETE/ON UPDATE (H-16: consulta aparte)
            return [(name, fk[0], fk[6], fk[7]) for name in table_names for fk in fks or []]
        if "REFERENCED_TABLE_NAME IS NOT NULL" in sql_upper:  # columnas de las FK
            return per_object(table_names, [fk[:6] for fk in fks or []])
        if "INFORMATION_SCHEMA.STATISTICS" in sql_upper:
            return per_object(table_names, indexes)
        return []

    manager.execute_custom_many.side_effect = side_effect
    return manager


def _col_row(
    name: str = "col1",
    data_type: str = "int",
    char_length: int | None = None,
    numeric_precision: int | None = None,
    numeric_scale: int | None = None,
    is_nullable: str = "YES",
    default: str | None = None,
    extra: str = "",
    comment: str = "",
    ordinal: int = 1,
) -> tuple:
    """Construye una fila cruda MariaDB de 10 elementos (INFORMATION_SCHEMA.COLUMNS)."""
    return (
        name,
        data_type,
        char_length,
        numeric_precision,
        numeric_scale,
        is_nullable,
        default,
        extra,
        comment,
        ordinal,
    )


# ── Tests _parse_raw_column ───────────────────────────────────────────────────


class TestParseRawColumn:
    def test_basic_int_column(self) -> None:
        row = _col_row("id", "int", None, 10, 0, "NO", None, "", "", 1)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["name"] == "id"
        assert parsed["data_type"] == "INT"
        assert parsed["auto_increment"] is False
        assert parsed["nullable"] is False

    def test_auto_increment_column(self) -> None:
        row = _col_row("id", "int", None, 10, 0, "NO", None, "auto_increment", "", 1)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["auto_increment"] is True

    def test_auto_increment_case_insensitive(self) -> None:
        row = _col_row("id", "int", None, 10, 0, "NO", None, "AUTO_INCREMENT", "", 1)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["auto_increment"] is True

    def test_varchar_with_length(self) -> None:
        row = _col_row("name", "varchar", 200, None, None, "YES", None, "", "", 2)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["char_length"] == 200
        assert parsed["nullable"] is True

    def test_decimal_precision_scale(self) -> None:
        row = _col_row("amount", "decimal", None, 18, 4, "NO", None, "", "", 1)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["precision"] == 18
        assert parsed["scale"] == 4

    def test_default_value_preserved(self) -> None:
        row = _col_row("status", "int", None, None, None, "NO", "1", "", "", 1)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["default"] == "1"

    def test_comment_preserved(self) -> None:
        row = _col_row("id", "int", None, 10, 0, "NO", None, "", "Clave primaria", 1)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["comment"] == "Clave primaria"

    def test_text_column_no_char_length(self) -> None:
        row = _col_row("body", "text", None, None, None, "YES", None, "", "", 3)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["data_type"] == "TEXT"
        assert parsed["char_length"] is None

    def test_data_type_uppercased(self) -> None:
        row = _col_row("col", "tinyint", None, None, None, "YES", None, "", "", 1)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["data_type"] == "TINYINT"

    def test_nullable_any_case(self) -> None:
        row_yes = _col_row("c", "int", None, None, None, "YES")
        row_no = _col_row("c", "int", None, None, None, "NO")
        assert _parse_raw_column(row_yes)["nullable"] is True  # type: ignore[index]
        assert _parse_raw_column(row_no)["nullable"] is False  # type: ignore[index]

    def test_ordinal_preserved(self) -> None:
        row = _col_row("c", "int", None, None, None, "YES", None, "", "", 7)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["ordinal"] == 7

    def test_too_short_row_returns_none(self) -> None:
        assert _parse_raw_column(("col", "int")) is None

    def test_none_row_returns_none(self) -> None:
        assert _parse_raw_column(None) is None  # type: ignore[arg-type]

    def test_non_auto_increment_extra_ignored(self) -> None:
        row = _col_row("col", "int", None, None, None, "NO", None, "DEFAULT_GENERATED", "", 1)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["auto_increment"] is False


# ── Tests extract() ───────────────────────────────────────────────────────────


class TestExtract:
    def test_extract_empty_schema(self) -> None:
        manager = _make_manager(tables=[])
        ext = MariaDBSchemaExtractor(manager)
        result = ext.extract("mydb")
        assert result == []

    def test_extract_single_table(self) -> None:
        manager = _make_manager(
            tables=[("orders", "Pedidos")],
            columns=[_col_row("id", "int", None, 10, 0, "NO", None, "auto_increment", "", 1)],
            pks=[("id",)],
        )
        ext = MariaDBSchemaExtractor(manager)
        result = ext.extract("mydb")
        assert len(result) == 1
        assert result[0].name == "orders"
        assert result[0].comment == "Pedidos"
        assert result[0].schema == "mydb"
        assert result[0].columns[0].auto_increment is True

    def test_pk_marks_column_is_primary_key(self) -> None:
        manager = _make_manager(
            tables=[("products", "")],
            columns=[
                _col_row("product_id", "int", None, 10, 0, "NO", None, "auto_increment", "", 1),
                _col_row("name", "varchar", 200, None, None, "NO", None, "", "", 2),
            ],
            pks=[("product_id",)],
        )
        ext = MariaDBSchemaExtractor(manager)
        result = ext.extract("mydb")
        pk_col = next(c for c in result[0].columns if c.name == "product_id")
        other_col = next(c for c in result[0].columns if c.name == "name")
        assert pk_col.is_primary_key is True
        assert other_col.is_primary_key is False

    def test_primary_key_list_populated(self) -> None:
        manager = _make_manager(
            tables=[("t1", "")],
            columns=[_col_row("id", "int", None, 10, 0, "NO")],
            pks=[("id",)],
        )
        ext = MariaDBSchemaExtractor(manager)
        result = ext.extract("mydb")
        assert result[0].primary_key == ["id"]

    def test_schema_stored_in_table(self) -> None:
        manager = _make_manager(
            tables=[("t1", "")],
            columns=[_col_row("c", "int")],
        )
        ext = MariaDBSchemaExtractor(manager)
        result = ext.extract("myschema")
        assert result[0].schema == "myschema"

    def test_empty_table_row_skipped(self) -> None:
        manager = _make_manager(tables=[None, ("valid_table", "")])  # type: ignore[list-item]
        ext = MariaDBSchemaExtractor(manager)
        result = ext.extract("mydb")
        assert len(result) == 1
        assert result[0].name == "valid_table"

    def test_column_char_length_in_canonical(self) -> None:
        manager = _make_manager(
            tables=[("t1", "")],
            columns=[_col_row("email", "varchar", 250, None, None, "NO")],
        )
        ext = MariaDBSchemaExtractor(manager)
        result = ext.extract("mydb")
        assert result[0].columns[0].char_length == 250

    def test_no_comment_returns_empty_string(self) -> None:
        manager = _make_manager(
            tables=[("t1", None)],  # type: ignore[list-item]
            columns=[_col_row("c", "int")],
        )
        ext = MariaDBSchemaExtractor(manager)
        result = ext.extract("mydb")
        assert result[0].comment == ""


# ── Tests extract_views() ────────────────────────────────────────────────────


class TestExtractViews:
    def test_extract_empty_views(self) -> None:
        manager = _make_manager(views=[])
        ext = MariaDBSchemaExtractor(manager)
        result = ext.extract_views("mydb")
        assert result == []

    def test_extract_single_view(self) -> None:
        manager = _make_manager(
            views=[("v_orders", "SELECT id, total FROM orders")],
            view_columns=[("id",), ("total",)],
        )
        ext = MariaDBSchemaExtractor(manager)
        result = ext.extract_views("mydb")
        assert len(result) == 1
        assert result[0].name == "v_orders"
        assert result[0].query == "SELECT id, total FROM orders"
        assert result[0].columns == ["id", "total"]

    def test_view_schema_stored(self) -> None:
        manager = _make_manager(
            views=[("v_test", "SELECT 1")],
            view_columns=[],
        )
        ext = MariaDBSchemaExtractor(manager)
        result = ext.extract_views("reporting")
        assert result[0].schema == "reporting"

    def test_view_empty_row_skipped(self) -> None:
        manager = _make_manager(views=[None, ("v_ok", "SELECT 1")])  # type: ignore[list-item]
        ext = MariaDBSchemaExtractor(manager)
        result = ext.extract_views("mydb")
        assert len(result) == 1
        assert result[0].name == "v_ok"


# ── Tests FK extraction ───────────────────────────────────────────────────────


class TestExtractFKs:
    def test_internal_fk(self) -> None:
        fk_rows = [
            ("fk_order_customer", "customer_id", "mydb", "customers", "id", 1, "NO ACTION", "NO ACTION"),
        ]
        manager = _make_manager(
            tables=[("orders", "")],
            columns=[
                _col_row("id", "int", None, 10, 0, "NO", None, "auto_increment", "", 1),
                _col_row("customer_id", "int", None, 10, 0, "NO", None, "", "", 2),
            ],
            pks=[("id",)],
            fks=fk_rows,
        )
        ext = MariaDBSchemaExtractor(manager)
        result = ext.extract("mydb")
        fks = result[0].foreign_keys
        assert len(fks) == 1
        assert fks[0].name == "fk_order_customer"
        assert fks[0].columns == ["customer_id"]
        assert fks[0].ref_table == "customers"
        assert fks[0].is_external is False

    def test_external_fk(self) -> None:
        fk_rows = [
            ("fk_ext", "col_a", "other_db", "ext_table", "id", 1, "CASCADE", "NO ACTION"),
        ]
        manager = _make_manager(
            tables=[("my_table", "")],
            columns=[_col_row("col_a", "int")],
            fks=fk_rows,
        )
        ext = MariaDBSchemaExtractor(manager)
        result = ext.extract("mydb")
        assert result[0].foreign_keys[0].is_external is True

    def test_fk_on_delete_cascade(self) -> None:
        fk_rows = [
            ("fk_del", "col_a", "mydb", "parent", "id", 1, "CASCADE", "NO ACTION"),
        ]
        manager = _make_manager(
            tables=[("child", "")],
            columns=[_col_row("col_a", "int")],
            fks=fk_rows,
        )
        ext = MariaDBSchemaExtractor(manager)
        result = ext.extract("mydb")
        assert result[0].foreign_keys[0].on_delete == "CASCADE"

    def test_composite_fk(self) -> None:
        fk_rows = [
            ("fk_comp", "col_a", "mydb", "parent", "a", 1, "NO ACTION", "NO ACTION"),
            ("fk_comp", "col_b", "mydb", "parent", "b", 2, "NO ACTION", "NO ACTION"),
        ]
        manager = _make_manager(
            tables=[("child", "")],
            columns=[
                _col_row("col_a", "int", None, None, None, "NO", None, "", "", 1),
                _col_row("col_b", "int", None, None, None, "NO", None, "", "", 2),
            ],
            fks=fk_rows,
        )
        ext = MariaDBSchemaExtractor(manager)
        result = ext.extract("mydb")
        fk = result[0].foreign_keys[0]
        assert fk.columns == ["col_a", "col_b"]
        assert fk.ref_columns == ["a", "b"]


# ── Tests index extraction ────────────────────────────────────────────────────


class TestExtractIndexes:
    def test_unique_index(self) -> None:
        idx_rows = [
            ("idx_email", "email", "0", 1),  # NON_UNIQUE=0 → unique
        ]
        manager = _make_manager(
            tables=[("users", "")],
            columns=[
                _col_row("id", "int", None, 10, 0, "NO", None, "auto_increment", "", 1),
                _col_row("email", "varchar", 200, None, None, "NO", None, "", "", 2),
            ],
            pks=[("id",)],
            indexes=idx_rows,
        )
        ext = MariaDBSchemaExtractor(manager)
        result = ext.extract("mydb")
        idxs = result[0].indexes
        assert len(idxs) == 1
        assert idxs[0].name == "idx_email"
        assert idxs[0].unique is True
        assert idxs[0].columns == ["email"]

    def test_non_unique_index(self) -> None:
        idx_rows = [
            ("idx_status", "status", "1", 1),  # NON_UNIQUE=1 → non-unique
        ]
        manager = _make_manager(
            tables=[("orders", "")],
            columns=[_col_row("status", "varchar", 20, None, None, "YES")],
            indexes=idx_rows,
        )
        ext = MariaDBSchemaExtractor(manager)
        result = ext.extract("mydb")
        assert result[0].indexes[0].unique is False

    def test_composite_index(self) -> None:
        idx_rows = [
            ("idx_comp", "first_name", "1", 1),
            ("idx_comp", "last_name", "1", 2),
        ]
        manager = _make_manager(
            tables=[("persons", "")],
            columns=[
                _col_row("first_name", "varchar", 100, None, None, "YES", None, "", "", 1),
                _col_row("last_name", "varchar", 100, None, None, "YES", None, "", "", 2),
            ],
            indexes=idx_rows,
        )
        ext = MariaDBSchemaExtractor(manager)
        result = ext.extract("mydb")
        assert result[0].indexes[0].columns == ["first_name", "last_name"]

    def test_no_indexes(self) -> None:
        manager = _make_manager(
            tables=[("t1", "")],
            columns=[_col_row("c", "int")],
            indexes=[],
        )
        ext = MariaDBSchemaExtractor(manager)
        result = ext.extract("mydb")
        assert result[0].indexes == []
