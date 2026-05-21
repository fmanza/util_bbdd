"""Tests para OracleSchemaExtractor (sin BD externa — manager mock)."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.migrate.extractors.oracle import OracleSchemaExtractor, _parse_raw_column

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
    """Construye un manager mock que devuelve filas predefinidas por consulta."""
    manager = MagicMock()

    def side_effect(sql: str, params: dict) -> list:
        sql_upper = sql.upper()
        # Vistas: all_views vs columnas de vista (all_tab_columns con :view_name)
        if "ALL_VIEWS" in sql_upper:
            return views or []
        if "ALL_TAB_COLUMNS" in sql_upper and "view_name" in sql.lower():
            return view_columns or []
        # Tablas
        if "ALL_TABLES" in sql_upper:
            return tables or []
        # Columnas de tabla
        if "ALL_TAB_COLUMNS" in sql_upper:
            return columns or []
        # PK
        if "CONSTRAINT_TYPE = 'P'" in sql_upper:
            return pks or []
        # FK
        if "CONSTRAINT_TYPE = 'R'" in sql_upper:
            return fks or []
        # Índices
        if "ALL_INDEXES" in sql_upper:
            return indexes or []
        return []

    manager.execute_custom_many.side_effect = side_effect
    return manager


def _col_row(
    name: str = "COL1",
    data_type: str = "VARCHAR2",
    nullable: str = "YES",
    ordinal: int = 1,
    default: str | None = None,
    data_length: int | None = 100,
    precision: int | None = None,
    scale: int | None = None,
    comment: str = "",
) -> tuple:
    """Construye una fila cruda Oracle de 9 elementos."""
    return (name, data_type, nullable, ordinal, default, data_length, precision, scale, comment)


# ── Tests _parse_raw_column ───────────────────────────────────────────────────


class TestParseRawColumn:
    def test_basic_varchar2_column(self) -> None:
        row = _col_row("NAME", "VARCHAR2", "YES", 1, None, 100)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["name"] == "NAME"
        assert parsed["data_type"] == "VARCHAR2"
        assert parsed["nullable"] is True
        assert parsed["data_length"] == 100

    def test_not_null_column(self) -> None:
        row = _col_row("ID", "NUMBER", "NO", 1, None, None, 10, 0)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["nullable"] is False
        assert parsed["data_type"] == "NUMBER"
        assert parsed["precision"] == 10
        assert parsed["scale"] == 0

    def test_number_with_precision_scale(self) -> None:
        row = _col_row("PRICE", "NUMBER", "YES", 2, None, None, 18, 4)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["precision"] == 18
        assert parsed["scale"] == 4
        assert parsed["data_length"] is None

    def test_default_value_preserved(self) -> None:
        row = _col_row("STATUS", "VARCHAR2", "NO", 3, "ACTIVE", 20)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["default"] == "ACTIVE"

    def test_comment_preserved(self) -> None:
        row = _col_row("ID", "NUMBER", "NO", 1, None, None, 10, 0, "Clave primaria")
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["comment"] == "Clave primaria"

    def test_empty_comment_returns_empty_string(self) -> None:
        row = _col_row("ID", "NUMBER", "NO", 1)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["comment"] == ""

    def test_date_column_no_precision(self) -> None:
        row = _col_row("CREATED", "DATE", "YES", 4, None, 7)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["data_type"] == "DATE"
        assert parsed["precision"] is None
        assert parsed["scale"] is None

    def test_too_short_row_returns_none(self) -> None:
        assert _parse_raw_column(("COL", "NUMBER")) is None

    def test_none_row_returns_none(self) -> None:
        assert _parse_raw_column(None) is None  # type: ignore[arg-type]

    def test_data_type_uppercased(self) -> None:
        row = _col_row("COL", "varchar2", "YES", 1, None, 50)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["data_type"] == "VARCHAR2"

    def test_nullable_any_case(self) -> None:
        row_yes = _col_row("C", "VARCHAR2", "yes", 1)
        row_no = _col_row("C", "VARCHAR2", "no", 1)
        assert _parse_raw_column(row_yes)["nullable"] is True  # type: ignore[index]
        assert _parse_raw_column(row_no)["nullable"] is False  # type: ignore[index]

    def test_ordinal_parsed_correctly(self) -> None:
        row = _col_row("C", "NUMBER", "YES", 5)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["ordinal"] == 5

    def test_precision_scale_none_when_absent(self) -> None:
        row = _col_row("TXT", "VARCHAR2", "YES", 1, None, 200, None, None)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["precision"] is None
        assert parsed["scale"] is None


# ── Tests extract() ───────────────────────────────────────────────────────────


class TestExtract:
    def test_extract_empty_schema(self) -> None:
        manager = _make_manager(tables=[])
        ext = OracleSchemaExtractor(manager)
        result = ext.extract("MY_SCHEMA")
        assert result == []

    def test_extract_single_table(self) -> None:
        manager = _make_manager(
            tables=[("USERS", "TABLE", "Tabla de usuarios")],
            columns=[_col_row("ID", "NUMBER", "NO", 1, None, None, 10, 0, "PK")],
            pks=[("PK_USERS", "ID", 1)],
        )
        ext = OracleSchemaExtractor(manager)
        result = ext.extract("MY_SCHEMA")
        assert len(result) == 1
        assert result[0].name == "USERS"
        assert result[0].comment == "Tabla de usuarios"
        assert result[0].schema == "MY_SCHEMA"
        assert len(result[0].columns) == 1
        assert result[0].columns[0].name == "ID"

    def test_pk_marks_column_is_primary_key(self) -> None:
        manager = _make_manager(
            tables=[("ORDERS", "TABLE", "")],
            columns=[
                _col_row("ID", "NUMBER", "NO", 1, None, None, 10, 0),
                _col_row("CUSTOMER_ID", "NUMBER", "NO", 2, None, None, 10, 0),
            ],
            pks=[("PK_ORDERS", "ID", 1)],
        )
        ext = OracleSchemaExtractor(manager)
        result = ext.extract("SCHEMA")
        pk_col = next(c for c in result[0].columns if c.name == "ID")
        other_col = next(c for c in result[0].columns if c.name == "CUSTOMER_ID")
        assert pk_col.is_primary_key is True
        assert other_col.is_primary_key is False

    def test_primary_key_list_populated(self) -> None:
        manager = _make_manager(
            tables=[("T1", "TABLE", "")],
            columns=[_col_row("ID", "NUMBER", "NO", 1)],
            pks=[("PK_T1", "ID", 1)],
        )
        ext = OracleSchemaExtractor(manager)
        result = ext.extract("SCHEMA")
        assert result[0].primary_key == ["ID"]

    def test_composite_pk_order_preserved(self) -> None:
        manager = _make_manager(
            tables=[("T1", "TABLE", "")],
            columns=[
                _col_row("A", "NUMBER", "NO", 1),
                _col_row("B", "NUMBER", "NO", 2),
            ],
            pks=[("PK_T1", "B", 2), ("PK_T1", "A", 1)],
        )
        ext = OracleSchemaExtractor(manager)
        result = ext.extract("SCHEMA")
        # Ordenado por ordinal_position → A primero
        assert result[0].primary_key == ["A", "B"]

    def test_schema_stored_in_table(self) -> None:
        manager = _make_manager(
            tables=[("T1", "TABLE", "")],
            columns=[_col_row("C", "NUMBER", "NO", 1)],
        )
        ext = OracleSchemaExtractor(manager)
        result = ext.extract("MY_OWNER")
        assert result[0].schema == "MY_OWNER"

    def test_empty_table_row_skipped(self) -> None:
        manager = _make_manager(tables=[None, ("VALID", "TABLE", "")])  # type: ignore[list-item]
        ext = OracleSchemaExtractor(manager)
        result = ext.extract("SCHEMA")
        # La fila None se omite; sólo se extrae VALID
        assert len(result) == 1
        assert result[0].name == "VALID"

    def test_column_precision_scale_in_canonical(self) -> None:
        manager = _make_manager(
            tables=[("T1", "TABLE", "")],
            columns=[_col_row("PRICE", "NUMBER", "NO", 1, None, None, 18, 4)],
        )
        ext = OracleSchemaExtractor(manager)
        result = ext.extract("SCHEMA")
        col = result[0].columns[0]
        assert col.precision == 18
        assert col.scale == 4


# ── Tests extract_views() ────────────────────────────────────────────────────


class TestExtractViews:
    def test_extract_empty_views(self) -> None:
        manager = _make_manager(views=[])
        ext = OracleSchemaExtractor(manager)
        result = ext.extract_views("MY_SCHEMA")
        assert result == []

    def test_extract_single_view(self) -> None:
        manager = _make_manager(
            views=[("V_USERS", "SELECT id, name FROM users", "Vista de usuarios")],
            view_columns=[("ID",), ("NAME",)],
        )
        ext = OracleSchemaExtractor(manager)
        result = ext.extract_views("MY_SCHEMA")
        assert len(result) == 1
        assert result[0].name == "V_USERS"
        assert result[0].query == "SELECT id, name FROM users"
        assert result[0].comment == "Vista de usuarios"
        assert result[0].columns == ["ID", "NAME"]

    def test_view_schema_stored(self) -> None:
        manager = _make_manager(
            views=[("V_TEST", "SELECT 1 FROM DUAL", "")],
            view_columns=[],
        )
        ext = OracleSchemaExtractor(manager)
        result = ext.extract_views("MY_OWNER")
        assert result[0].schema == "MY_OWNER"

    def test_view_empty_row_skipped(self) -> None:
        manager = _make_manager(views=[None, ("V_OK", "SELECT 1 FROM DUAL", "")])  # type: ignore[list-item]
        ext = OracleSchemaExtractor(manager)
        result = ext.extract_views("SCHEMA")
        assert len(result) == 1
        assert result[0].name == "V_OK"


# ── Tests FK extraction ───────────────────────────────────────────────────────


class TestExtractFKs:
    def test_internal_fk(self) -> None:
        fk_rows = [
            ("FK_ORD_CUST", "CUSTOMER_ID", "MY_SCHEMA", "CUSTOMERS", "ID", "NO ACTION", "NO ACTION", 1),
        ]
        manager = _make_manager(
            tables=[("ORDERS", "TABLE", "")],
            columns=[
                _col_row("ID", "NUMBER", "NO", 1, None, None, 10, 0),
                _col_row("CUSTOMER_ID", "NUMBER", "NO", 2, None, None, 10, 0),
            ],
            pks=[("PK_ORDERS", "ID", 1)],
            fks=fk_rows,
        )
        ext = OracleSchemaExtractor(manager)
        result = ext.extract("MY_SCHEMA")
        fks = result[0].foreign_keys
        assert len(fks) == 1
        assert fks[0].name == "FK_ORD_CUST"
        assert fks[0].columns == ["CUSTOMER_ID"]
        assert fks[0].ref_table == "CUSTOMERS"
        assert fks[0].is_external is False

    def test_external_fk(self) -> None:
        fk_rows = [
            ("FK_EXT", "REF_COL", "OTHER_SCHEMA", "EXT_TABLE", "ID", "CASCADE", "NO ACTION", 1),
        ]
        manager = _make_manager(
            tables=[("MY_TABLE", "TABLE", "")],
            columns=[_col_row("REF_COL", "NUMBER", "NO", 1)],
            fks=fk_rows,
        )
        ext = OracleSchemaExtractor(manager)
        result = ext.extract("MY_SCHEMA")
        assert result[0].foreign_keys[0].is_external is True

    def test_fk_on_delete_cascade(self) -> None:
        fk_rows = [
            ("FK_DEL", "COL_A", "MY_SCHEMA", "PARENT", "ID", "CASCADE", "NO ACTION", 1),
        ]
        manager = _make_manager(
            tables=[("CHILD", "TABLE", "")],
            columns=[_col_row("COL_A", "NUMBER", "NO", 1)],
            fks=fk_rows,
        )
        ext = OracleSchemaExtractor(manager)
        result = ext.extract("MY_SCHEMA")
        assert result[0].foreign_keys[0].on_delete == "CASCADE"

    def test_composite_fk(self) -> None:
        fk_rows = [
            ("FK_COMP", "COL_A", "MY_SCHEMA", "PARENT", "A", "NO ACTION", "NO ACTION", 1),
            ("FK_COMP", "COL_B", "MY_SCHEMA", "PARENT", "B", "NO ACTION", "NO ACTION", 2),
        ]
        manager = _make_manager(
            tables=[("CHILD", "TABLE", "")],
            columns=[
                _col_row("COL_A", "NUMBER", "NO", 1),
                _col_row("COL_B", "NUMBER", "NO", 2),
            ],
            fks=fk_rows,
        )
        ext = OracleSchemaExtractor(manager)
        result = ext.extract("MY_SCHEMA")
        fk = result[0].foreign_keys[0]
        assert fk.columns == ["COL_A", "COL_B"]
        assert fk.ref_columns == ["A", "B"]


# ── Tests index extraction ────────────────────────────────────────────────────


class TestExtractIndexes:
    def test_unique_index(self) -> None:
        idx_rows = [
            ("IDX_EMAIL", "EMAIL", "ASC", "UNIQUE", 1),
        ]
        manager = _make_manager(
            tables=[("USERS", "TABLE", "")],
            columns=[
                _col_row("ID", "NUMBER", "NO", 1),
                _col_row("EMAIL", "VARCHAR2", "NO", 2, None, 200),
            ],
            pks=[("PK_USERS", "ID", 1)],
            indexes=idx_rows,
        )
        ext = OracleSchemaExtractor(manager)
        result = ext.extract("SCHEMA")
        idxs = result[0].indexes
        assert len(idxs) == 1
        assert idxs[0].name == "IDX_EMAIL"
        assert idxs[0].unique is True
        assert idxs[0].columns == ["EMAIL"]

    def test_non_unique_index(self) -> None:
        idx_rows = [
            ("IDX_STATUS", "STATUS", "ASC", "NONUNIQUE", 1),
        ]
        manager = _make_manager(
            tables=[("ORDERS", "TABLE", "")],
            columns=[_col_row("STATUS", "VARCHAR2", "YES", 1, None, 20)],
            indexes=idx_rows,
        )
        ext = OracleSchemaExtractor(manager)
        result = ext.extract("SCHEMA")
        assert result[0].indexes[0].unique is False

    def test_composite_index(self) -> None:
        idx_rows = [
            ("IDX_COMP", "FIRST_NAME", "ASC", "NONUNIQUE", 1),
            ("IDX_COMP", "LAST_NAME", "ASC", "NONUNIQUE", 2),
        ]
        manager = _make_manager(
            tables=[("PERSONS", "TABLE", "")],
            columns=[
                _col_row("FIRST_NAME", "VARCHAR2", "YES", 1, None, 100),
                _col_row("LAST_NAME", "VARCHAR2", "YES", 2, None, 100),
            ],
            indexes=idx_rows,
        )
        ext = OracleSchemaExtractor(manager)
        result = ext.extract("SCHEMA")
        assert result[0].indexes[0].columns == ["FIRST_NAME", "LAST_NAME"]

    def test_no_indexes(self) -> None:
        manager = _make_manager(
            tables=[("T1", "TABLE", "")],
            columns=[_col_row("C", "NUMBER", "NO", 1)],
            indexes=[],
        )
        ext = OracleSchemaExtractor(manager)
        result = ext.extract("SCHEMA")
        assert result[0].indexes == []
