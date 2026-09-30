"""Tests para SQLServerSchemaExtractor (sin BD externa — manager mock)."""

from __future__ import annotations

from unittest.mock import MagicMock

from util_bbdd.migrate.extractors.sqlserver import SQLServerSchemaExtractor, _parse_raw_column

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

    # Columnas (también las de vistas), PK, FK e índices se leen por schema (D1): la primera columna es el nombre de
    # la tabla o vista. Como antes con la consulta por tabla, cada tabla del mock recibe las mismas filas.
    table_names = [str(t[0]) for t in tables or [] if t]
    view_names = [str(v[0]) for v in views or [] if v]

    def per_object(names: list[str], rows: list[tuple] | None) -> list[tuple]:
        return [(name, *row) for name in names for row in rows or []]

    def side_effect(sql: str, params: dict) -> list:
        sql_upper = sql.upper()
        if "OBJECT_DEFINITION" in sql_upper:
            return views or []
        if "INFORMATION_SCHEMA.TABLES" in sql_upper:
            return tables or []
        if "COLUMNPROPERTY" in sql_upper:
            return per_object(table_names, columns) + per_object(view_names, view_columns)
        if "CONSTRAINT_TYPE = 'PRIMARY KEY'" in sql_upper:
            return per_object(table_names, pks)
        if "REFERENTIAL_CONSTRAINTS" in sql_upper:
            return per_object(table_names, fks)
        if "SYS.INDEXES" in sql_upper:
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
    is_identity: int = 0,
    ordinal: int = 1,
) -> tuple:
    return (name, data_type, char_length, numeric_precision, numeric_scale, is_nullable, default, is_identity, ordinal)


# ── Tests _parse_raw_column ───────────────────────────────────────────────────


class TestParseRawColumn:
    def test_basic_int_column(self) -> None:
        row = _col_row("ID", "int", None, 10, 0, "NO", None, 0, 1)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["name"] == "ID"
        assert parsed["data_type"] == "INT"
        assert parsed["auto_increment"] is False
        assert parsed["nullable"] is False

    def test_identity_column(self) -> None:
        row = _col_row("ID", "int", None, 10, 0, "NO", None, 1, 1)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["auto_increment"] is True

    def test_varchar_with_length(self) -> None:
        row = _col_row("NAME", "varchar", 100, None, None, "YES", None, 0, 2)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["char_length"] == 100
        assert parsed["nullable"] is True

    def test_varchar_max_sentinel(self) -> None:
        row = _col_row("CONTENT", "nvarchar", -1, None, None, "YES", None, 0, 3)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["char_length"] == -1

    def test_decimal_precision_scale(self) -> None:
        row = _col_row("AMOUNT", "decimal", None, 18, 4, "NO", None, 0, 1)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["precision"] == 18
        assert parsed["scale"] == 4

    def test_too_short_row_returns_none(self) -> None:
        assert _parse_raw_column(("col", "int")) is None

    def test_none_row_returns_none(self) -> None:
        assert _parse_raw_column(None) is None  # type: ignore[arg-type]

    def test_default_value_preserved(self) -> None:
        row = _col_row("STATUS", "int", None, 10, 0, "NO", "1", 0, 1)
        parsed = _parse_raw_column(row)
        assert parsed is not None
        assert parsed["default"] == "1"


# ── Tests extract() ──────────────────────────────────────────────────────────


class TestExtract:
    def test_extract_empty_schema(self) -> None:
        manager = _make_manager(tables=[])
        ext = SQLServerSchemaExtractor(manager)
        result = ext.extract("dbo")
        assert result == []

    def test_extract_single_table(self) -> None:
        manager = _make_manager(
            tables=[("ORDERS",)],
            columns=[_col_row("ID", "int", None, 10, 0, "NO", None, 1, 1)],
            pks=[("ID",)],
        )
        ext = SQLServerSchemaExtractor(manager)
        result = ext.extract("dbo")
        assert len(result) == 1
        assert result[0].name == "ORDERS"
        assert result[0].columns[0].name == "ID"
        assert result[0].columns[0].auto_increment is True
        assert result[0].primary_key == ["ID"]

    def test_pk_marks_column_is_primary_key(self) -> None:
        manager = _make_manager(
            tables=[("PRODUCTS",)],
            columns=[
                _col_row("PRODUCT_ID", "int", None, 10, 0, "NO", None, 1, 1),
                _col_row("NAME", "nvarchar", 200, None, None, "NO", None, 0, 2),
            ],
            pks=[("PRODUCT_ID",)],
        )
        ext = SQLServerSchemaExtractor(manager)
        result = ext.extract("dbo")
        pk_col = next(c for c in result[0].columns if c.name == "PRODUCT_ID")
        other_col = next(c for c in result[0].columns if c.name == "NAME")
        assert pk_col.is_primary_key is True
        assert other_col.is_primary_key is False

    def test_schema_stored_in_table(self) -> None:
        manager = _make_manager(
            tables=[("T1",)],
            columns=[_col_row("C1", "int")],
        )
        ext = SQLServerSchemaExtractor(manager)
        result = ext.extract("myschema")
        assert result[0].schema == "myschema"

    def test_varchar_max_char_length_preserved(self) -> None:
        manager = _make_manager(
            tables=[("DOCS",)],
            columns=[_col_row("BODY", "nvarchar", -1, None, None, "YES", None, 0, 1)],
        )
        ext = SQLServerSchemaExtractor(manager)
        result = ext.extract("dbo")
        assert result[0].columns[0].char_length == -1


# ── Tests extract_views() ────────────────────────────────────────────────────


class TestExtractViews:
    def test_extract_empty_views(self) -> None:
        manager = _make_manager(views=[])
        ext = SQLServerSchemaExtractor(manager)
        result = ext.extract_views("dbo")
        assert result == []

    def test_extract_single_view(self) -> None:
        manager = _make_manager(
            views=[("V_ORDERS", "SELECT id, name FROM orders")],
            view_columns=[("ID",), ("NAME",)],
        )
        ext = SQLServerSchemaExtractor(manager)
        result = ext.extract_views("dbo")
        assert len(result) == 1
        assert result[0].name == "V_ORDERS"
        assert result[0].query == "SELECT id, name FROM orders"

    def test_create_view_header_is_removed(self) -> None:
        """H7: OBJECT_DEFINITION (como VIEW_DEFINITION) incluye la cabecera CREATE VIEW ... AS."""
        manager = _make_manager(
            views=[
                (
                    "V_ORDERS",
                    "CREATE VIEW [dbo].[V_ORDERS] WITH SCHEMABINDING"
                    + chr(10)
                    + "AS"
                    + chr(10)
                    + "SELECT id FROM dbo.orders",
                )
            ],
            view_columns=[("ID",)],
        )
        view = SQLServerSchemaExtractor(manager).extract_views("dbo")[0]
        assert view.query == "SELECT id FROM dbo.orders"
        assert view.warnings == []

    def test_long_definition_is_not_truncated_nor_flagged(self) -> None:
        """Con OBJECT_DEFINITION la definición llega completa: 4000 caracteres ya no indican truncado."""
        body = "SELECT 1 AS a" + "".join(f", {i} AS c{i}" for i in range(900))
        manager = _make_manager(views=[("V_LONG", f"CREATE VIEW dbo.V_LONG AS {body}")], view_columns=[])
        view = SQLServerSchemaExtractor(manager).extract_views("dbo")[0]
        assert view.query == body
        assert len(view.query) > 4000
        assert view.warnings == []

    def test_explicit_column_list_warns(self) -> None:
        manager = _make_manager(
            views=[("V_ALIAS", "CREATE VIEW V_ALIAS (x, y) AS SELECT a, b FROM t")], view_columns=[]
        )
        view = SQLServerSchemaExtractor(manager).extract_views("dbo")[0]
        assert view.query == "SELECT a, b FROM t"
        assert any("(x, y)" in w.message for w in view.warnings)

    def test_unavailable_definition_warns(self) -> None:
        """OBJECT_DEFINITION devuelve NULL para vistas WITH ENCRYPTION o sin permiso VIEW DEFINITION."""
        manager = _make_manager(views=[("V_SECRET", None)], view_columns=[])
        view = SQLServerSchemaExtractor(manager).extract_views("dbo")[0]
        assert view.query == ""
        assert any("no disponible" in w.message for w in view.warnings)

    def test_view_schema_stored(self) -> None:
        manager = _make_manager(
            views=[("V_TEST", "SELECT 1")],
            view_columns=[],
        )
        ext = SQLServerSchemaExtractor(manager)
        result = ext.extract_views("reporting")
        assert result[0].schema == "reporting"


# ── Tests FK extraction ───────────────────────────────────────────────────────


class TestExtractFKs:
    def test_internal_fk(self) -> None:
        fk_rows = [
            ("FK_ORDER_CUSTOMER", "CUSTOMER_ID", "dbo", "CUSTOMERS", "ID", 1, "NO ACTION", "NO ACTION"),
        ]
        manager = _make_manager(
            tables=[("ORDERS",)],
            columns=[
                _col_row("ID", "int", None, 10, 0, "NO", None, 1, 1),
                _col_row("CUSTOMER_ID", "int", None, 10, 0, "NO", None, 0, 2),
            ],
            pks=[("ID",)],
            fks=fk_rows,
        )
        ext = SQLServerSchemaExtractor(manager)
        result = ext.extract("dbo")
        fks = result[0].foreign_keys
        assert len(fks) == 1
        assert fks[0].name == "FK_ORDER_CUSTOMER"
        assert fks[0].columns == ["CUSTOMER_ID"]
        assert fks[0].ref_table == "CUSTOMERS"
        assert fks[0].is_external is False

    def test_external_fk(self) -> None:
        fk_rows = [
            ("FK_EXT", "COL_A", "other_schema", "EXT_TABLE", "ID", 1, "CASCADE", "NO ACTION"),
        ]
        manager = _make_manager(
            tables=[("MY_TABLE",)],
            columns=[_col_row("COL_A", "int")],
            fks=fk_rows,
        )
        ext = SQLServerSchemaExtractor(manager)
        result = ext.extract("dbo")
        assert result[0].foreign_keys[0].is_external is True


# ── Tests index extraction ────────────────────────────────────────────────────


class TestExtractIndexes:
    def test_unique_index(self) -> None:
        idx_rows = [
            ("UQ_EMAIL", "EMAIL", True, 1),
        ]
        manager = _make_manager(
            tables=[("USERS",)],
            columns=[
                _col_row("ID", "int", None, 10, 0, "NO", None, 1, 1),
                _col_row("EMAIL", "nvarchar", 255, None, None, "NO", None, 0, 2),
            ],
            pks=[("ID",)],
            indexes=idx_rows,
        )
        ext = SQLServerSchemaExtractor(manager)
        result = ext.extract("dbo")
        assert len(result[0].indexes) == 1
        assert result[0].indexes[0].name == "UQ_EMAIL"
        assert result[0].indexes[0].unique is True

    def test_non_unique_index(self) -> None:
        idx_rows = [("IX_STATUS", "STATUS", False, 1)]
        manager = _make_manager(
            tables=[("ORDERS",)],
            columns=[_col_row("STATUS", "int")],
            indexes=idx_rows,
        )
        ext = SQLServerSchemaExtractor(manager)
        result = ext.extract("dbo")
        assert result[0].indexes[0].unique is False


# ── Tests extract_routines() ─────────────────────────────────────────────────


def _make_routines_manager(
    routine_rows: list[tuple],
    body_map: dict[str, str] | None = None,
) -> MagicMock:
    """Manager mock para probar extract_routines().

    Args:
        routine_rows: Filas del inventario de rutinas (name, type, object_id, params_count).
        body_map: Mapa routine_name → body DDL; None o ausente → body vacío.
    """
    body_map = body_map or {}
    manager = MagicMock()

    def side_effect(sql: str, params: dict) -> list:
        sql_upper = sql.upper()
        # Chequear SQL_MODULES ANTES que OBJECTS porque el body query hace JOIN a ambas
        if "SYS.SQL_MODULES" in sql_upper:  # D1: el código de todas las rutinas en una consulta
            return [(name, body) for name, body in body_map.items() if body]
        # El query de inventario ahora usa sys.objects (antes sys.procedures)
        if "SYS.OBJECTS" in sql_upper:
            return routine_rows
        return []

    manager.execute_custom_many.side_effect = side_effect
    return manager


class TestExtractRoutines:
    def test_empty_returns_empty(self) -> None:
        manager = _make_routines_manager([])
        ext = SQLServerSchemaExtractor(manager)
        assert ext.extract_routines("dbo") == []

    def test_procedure_with_body(self) -> None:
        manager = _make_routines_manager(
            routine_rows=[("SP_TEST", "PROCEDURE", 1001, 2)],
            body_map={"SP_TEST": "CREATE PROCEDURE SP_TEST AS BEGIN SELECT 1 END"},
        )
        ext = SQLServerSchemaExtractor(manager)
        result = ext.extract_routines("dbo")
        assert len(result) == 1
        r = result[0]
        assert r.name == "SP_TEST"
        assert r.routine_type == "PROCEDURE"
        assert "SELECT 1" in r.body
        assert r.warnings == []

    def test_routine_no_body_emits_warning(self) -> None:
        manager = _make_routines_manager(
            routine_rows=[("SP_EMPTY", "PROCEDURE", 1002, 0)],
            body_map={},
        )
        ext = SQLServerSchemaExtractor(manager)
        result = ext.extract_routines("dbo")
        assert result[0].body == ""
        assert len(result[0].warnings) == 1
        assert "sys.sql_modules" in result[0].warnings[0].message

    def test_schema_propagated(self) -> None:
        manager = _make_routines_manager(
            routine_rows=[("FN_CALC", "FUNCTION", 1003, 1)],
            body_map={"FN_CALC": "CREATE FUNCTION FN_CALC() RETURNS INT AS BEGIN RETURN 1 END"},
        )
        ext = SQLServerSchemaExtractor(manager)
        result = ext.extract_routines("myschema")
        assert result[0].schema == "myschema"

    def test_manager_execute_custom_many_called_not_execute(self) -> None:
        """Verifica que se usa execute_custom_many (no .execute() inexistente)."""
        manager = _make_routines_manager(
            routine_rows=[("SP_TEST", "PROCEDURE", 1001, 0)],
            body_map={"SP_TEST": "CREATE PROCEDURE SP_TEST AS BEGIN END"},
        )
        ext = SQLServerSchemaExtractor(manager)
        ext.extract_routines("dbo")
        assert manager.execute_custom_many.called
        assert not manager.execute.called
