"""Tests para PostgreSQLDDLEmitter."""

from __future__ import annotations

from util_bbdd.migrate.emitters.postgresql import PostgreSQLDDLEmitter, _format_default_postgresql
from util_bbdd.migrate.ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalTable,
)


def _col(
    name: str,
    target_type: str = "VARCHAR(100)",
    nullable: bool = True,
    auto_increment: bool = False,
    is_pk: bool = False,
    default: str | None = None,
    omit: bool = False,
    comment: str = "",
    ddl_comment: str | None = None,
) -> CanonicalColumn:
    return CanonicalColumn(
        name=name,
        original_name=name,
        oracle_type="",
        target_type=target_type,
        nullable=nullable,
        default=default,
        comment=comment,
        ordinal=1,
        auto_increment=auto_increment,
        is_primary_key=is_pk,
        omit=omit,
        ddl_comment=ddl_comment,
    )


def _table(
    name: str,
    columns: list[CanonicalColumn],
    pk: list[str] | None = None,
    fks: list[CanonicalFK] | None = None,
    indexes: list[CanonicalIndex] | None = None,
    comment: str = "",
) -> CanonicalTable:
    return CanonicalTable(
        name=name,
        original_name=name,
        schema="S",
        columns=columns,
        primary_key=pk or [],
        indexes=indexes or [],
        foreign_keys=fks or [],
        comment=comment,
        warnings=[],
    )


class TestCreateTable:
    def setup_method(self) -> None:
        self.e = PostgreSQLDDLEmitter()

    def test_double_quote_identifiers(self) -> None:
        t = _table("MY_TABLE", [_col("MY_COL")])
        ddl = self.e.emit([t])
        assert '"MY_TABLE"' in ddl
        assert '"MY_COL"' in ddl

    def test_no_engine_or_charset(self) -> None:
        t = _table("T", [_col("C")])
        ddl = self.e.emit([t])
        assert "ENGINE" not in ddl
        assert "CHARSET" not in ddl
        assert "COLLATE" not in ddl

    def test_not_null_column(self) -> None:
        t = _table("T", [_col("C", nullable=False)])
        ddl = self.e.emit([t])
        assert "NOT NULL" in ddl

    def test_null_column(self) -> None:
        t = _table("T", [_col("C", nullable=True)])
        ddl = self.e.emit([t])
        assert "NULL" in ddl

    def test_serial_for_integer_auto_increment(self) -> None:
        t = _table(
            "T",
            [_col("ID", target_type="INTEGER", auto_increment=True, nullable=False)],
            pk=["ID"],
        )
        ddl = self.e.emit([t])
        assert "SERIAL" in ddl
        # No debe emitir DEFAULT ni NOT NULL explícito para SERIAL
        assert "IDENTITY" not in ddl

    def test_bigserial_for_bigint_auto_increment(self) -> None:
        t = _table(
            "T",
            [_col("ID", target_type="BIGINT", auto_increment=True, nullable=False)],
            pk=["ID"],
        )
        ddl = self.e.emit([t])
        assert "BIGSERIAL" in ddl

    def test_smallserial_for_smallint_auto_increment(self) -> None:
        t = _table(
            "T",
            [_col("ID", target_type="SMALLINT", auto_increment=True, nullable=False)],
            pk=["ID"],
        )
        ddl = self.e.emit([t])
        assert "SMALLSERIAL" in ddl

    def test_serial_column_no_extra_not_null(self) -> None:
        """SERIAL implica NOT NULL — no debe emitir NOT NULL adicional."""
        t = _table(
            "T",
            [_col("ID", target_type="INTEGER", auto_increment=True, nullable=False)],
            pk=["ID"],
        )
        ddl = self.e.emit([t])
        assert "NOT NULL" not in ddl

    def test_primary_key_constraint(self) -> None:
        t = _table("T", [_col("ID", target_type="INTEGER")], pk=["ID"])
        ddl = self.e.emit([t])
        assert "PRIMARY KEY" in ddl
        assert '"PK_T"' in ddl

    def test_omitted_column_as_comment(self) -> None:
        col = _col("ROWID_COL", omit=True, ddl_comment="-- AVISO: ROWID omitido")
        t = _table("T", [col, _col("C")])
        ddl = self.e.emit([t])
        assert "AVISO" in ddl

    def test_table_comment_as_sql_comment(self) -> None:
        t = _table("T", [_col("C")], comment="Una tabla de prueba")
        ddl = self.e.emit([t])
        assert "-- COMMENT: Una tabla de prueba" in ddl

    def test_ddl_comment_trailing(self) -> None:
        col = _col("C", ddl_comment="-- AVISO: DATE Oracle contiene hora; usar TIMESTAMP")
        t = _table("T", [col])
        ddl = self.e.emit([t])
        assert "AVISO" in ddl

    def test_column_comment_trailing(self) -> None:
        col = _col("C", comment="Columna de nombre")
        t = _table("T", [col])
        ddl = self.e.emit([t])
        assert "Columna de nombre" in ddl

    def test_default_value_emitted(self) -> None:
        col = _col("C", default="SYSDATE")
        t = _table("T", [col])
        ddl = self.e.emit([t])
        assert "NOW()" in ddl

    def test_no_default_for_serial(self) -> None:
        # El emitter no debe emitir DEFAULT para columnas auto_increment (SERIAL lo implica)
        col = _col("ID", target_type="INTEGER", auto_increment=True, default=None)
        t = _table("T", [col], pk=["ID"])
        ddl = self.e.emit([t])
        assert "DEFAULT" not in ddl

    def test_table_without_active_columns_sentinel(self) -> None:
        col = _col("R", omit=True, ddl_comment="-- AVISO: omitido")
        t = _table("T", [col])
        ddl = self.e.emit([t])
        assert "sin columnas activas" in ddl


class TestSearchPath:
    def test_pg_schema_emits_set_search_path(self) -> None:
        e = PostgreSQLDDLEmitter(pg_schema="mi_schema")
        t = _table("T", [_col("C")])
        stmts = e.emit_statements([t])
        assert stmts[0].startswith("SET search_path")
        assert '"mi_schema"' in stmts[0]

    def test_no_pg_schema_no_set_statement(self) -> None:
        e = PostgreSQLDDLEmitter()
        t = _table("T", [_col("C")])
        stmts = e.emit_statements([t])
        assert not any("search_path" in s for s in stmts)

    def test_pg_schema_is_first_statement(self) -> None:
        e = PostgreSQLDDLEmitter(pg_schema="app")
        t = _table("T", [_col("C")])
        stmts = e.emit_statements([t])
        assert "search_path" in stmts[0]
        assert "CREATE TABLE" in stmts[1]


class TestIndexEmission:
    def setup_method(self) -> None:
        self.e = PostgreSQLDDLEmitter()

    def test_unique_index_emitted(self) -> None:
        idx = CanonicalIndex(name="UQ_T_C", original_name="UQ_T_C", columns=["C"], unique=True)
        t = _table("T", [_col("C"), _col("D")], indexes=[idx])
        ddl = self.e.emit([t])
        assert "UNIQUE INDEX" in ddl
        assert '"UQ_T_C"' in ddl

    def test_non_unique_index_emitted(self) -> None:
        idx = CanonicalIndex(name="IDX_T_C", original_name="IDX_T_C", columns=["C"], unique=False)
        t = _table("T", [_col("C")], indexes=[idx])
        ddl = self.e.emit([t])
        assert "CREATE INDEX" in ddl

    def test_pk_index_skipped(self) -> None:
        idx = CanonicalIndex(name="PK_T", original_name="PK_T", columns=["ID"], unique=True)
        id_col = _col("ID", target_type="INTEGER")
        t = _table("T", [id_col], pk=["ID"], indexes=[idx])
        ddl = self.e.emit([t])
        # El índice PK no debe emitirse como CREATE INDEX, solo como CONSTRAINT en CREATE TABLE
        assert 'CREATE UNIQUE INDEX "PK_T"' not in ddl
        assert 'CREATE INDEX "PK_T"' not in ddl

    def test_index_on_omitted_col_skipped(self) -> None:
        idx = CanonicalIndex(name="IDX_R", original_name="IDX_R", columns=["R"], unique=False)
        omitted = _col("R", omit=True)
        active = _col("C")
        t = _table("T", [omitted, active], indexes=[idx])
        ddl = self.e.emit([t])
        assert '"IDX_R"' not in ddl


class TestFKEmission:
    def setup_method(self) -> None:
        self.e = PostgreSQLDDLEmitter()

    def test_inline_fk_in_create_table(self) -> None:
        fk = CanonicalFK(
            name="FK_T_REF",
            original_name="FK_T_REF",
            columns=["REF_ID"],
            ref_table="REF_TABLE",
            ref_columns=["ID"],
            on_delete="",
            on_update="",
            is_external=False,
        )
        t = _table("T", [_col("REF_ID", target_type="INTEGER")], fks=[fk])
        ddl = self.e.emit([t])
        assert "FOREIGN KEY" in ddl
        assert '"REF_TABLE"' in ddl

    def test_external_fk_as_alter_table(self) -> None:
        fk = CanonicalFK(
            name="FK_EXT",
            original_name="FK_EXT",
            columns=["EXT_ID"],
            ref_table="EXTERNAL_TABLE",
            ref_columns=["ID"],
            on_delete="",
            on_update="",
            is_external=True,
        )
        t = _table("T", [_col("EXT_ID", target_type="INTEGER")], fks=[fk])
        stmts = self.e.emit_statements([t])
        alter = next((s for s in stmts if "ALTER TABLE" in s), None)
        assert alter is not None
        assert "FK externa" in alter

    def test_on_delete_cascade_emitted(self) -> None:
        fk = CanonicalFK(
            name="FK_CASCADE",
            original_name="FK_CASCADE",
            columns=["REF_ID"],
            ref_table="PARENT",
            ref_columns=["ID"],
            on_delete="CASCADE",
            on_update="",
            is_external=False,
        )
        t = _table("T", [_col("REF_ID", target_type="INTEGER")], fks=[fk])
        ddl = self.e.emit([t])
        assert "ON DELETE CASCADE" in ddl


class TestFormatDefaultPostgreSQL:
    def test_sysdate_to_now(self) -> None:
        assert _format_default_postgresql("SYSDATE") == "NOW()"

    def test_systimestamp_to_now(self) -> None:
        assert _format_default_postgresql("SYSTIMESTAMP") == "NOW()"

    def test_sys_guid_to_gen_random_uuid(self) -> None:
        assert _format_default_postgresql("SYS_GUID()") == "gen_random_uuid()"

    def test_user_to_current_user(self) -> None:
        assert _format_default_postgresql("USER") == "CURRENT_USER"

    def test_current_date_preserved(self) -> None:
        assert _format_default_postgresql("CURRENT_DATE") == "CURRENT_DATE"

    def test_numeric_value_preserved(self) -> None:
        assert _format_default_postgresql("42") == "42"

    def test_float_value_preserved(self) -> None:
        assert _format_default_postgresql("3.14") == "3.14"

    def test_string_literal_quoted(self) -> None:
        result = _format_default_postgresql("hola")
        assert result == "'hola'"

    def test_string_with_single_quote_escaped(self) -> None:
        result = _format_default_postgresql("O'Brien")
        assert result == "'O''Brien'"

    def test_null_value(self) -> None:
        assert _format_default_postgresql("NULL") == "NULL"

    def test_empty_string_returns_null(self) -> None:
        assert _format_default_postgresql("") == "NULL"

    def test_current_timestamp_with_precision_passed_through(self) -> None:
        """DEBT-08: CURRENT_TIMESTAMP(6) debe pasar sin entrecomillar."""
        assert _format_default_postgresql("CURRENT_TIMESTAMP(6)") == "CURRENT_TIMESTAMP(6)"

    def test_oracle_quoted_numeric_default_not_double_quoted(self) -> None:
        """Regresión: Oracle almacena DATA_DEFAULT con comillas ('6').
        El emitter no debe volver a entrecomillar → evitar DEFAULT '''6'''."""
        assert _format_default_postgresql("'6'") == "'6'"

    def test_oracle_quoted_string_default_not_double_quoted(self) -> None:
        """Regresión: literal de texto Oracle ya entrecomillado ('ACTIVO') no se dobla."""
        assert _format_default_postgresql("'ACTIVO'") == "'ACTIVO'"

    def test_oracle_empty_string_default_preserved(self) -> None:
        """Literal vacío Oracle ('') se preserva tal cual."""
        assert _format_default_postgresql("''") == "''"

    def test_now_with_precision_passed_through(self) -> None:
        """DEBT-08: NOW(3) debe pasar sin entrecomillar."""
        assert _format_default_postgresql("NOW(3)") == "NOW(3)"


class TestPostgreSQLDefaultFallbackWarning:
    """MIG-03 (AUDIT_CODE 2026-09-22): un DEFAULT con forma de llamada a función
    (p.ej. GETDATE() de SQL Server) que el emisor no reconoce cae al fallback y se
    entrecomilla como literal de texto; hasta ahora, sin ningún MigrationWarning."""

    def setup_method(self) -> None:
        self.e = PostgreSQLDDLEmitter()

    def test_unrecognized_function_call_default_emits_warning(self) -> None:
        col = _col("CREATED_AT", "TIMESTAMP", default="GETDATE()")
        table = _table("T_SQLSERVER_SRC", [col])

        ddl = self.e.emit([table])

        assert "DEFAULT 'GETDATE()'" in ddl
        assert len(col.warnings) == 1
        assert col.warnings[0].severity == "WARNING"
        assert "GETDATE()" in col.warnings[0].message

    def test_recognized_function_default_does_not_emit_warning(self) -> None:
        col = _col("CREATED_AT", "TIMESTAMP", default="SYSDATE")
        table = _table("T_OK", [col])

        self.e.emit([table])

        assert col.warnings == []

    def test_plain_string_default_does_not_emit_warning(self) -> None:
        col = _col("STATUS", "VARCHAR(10)", default="hola")
        table = _table("T_STATUS", [col])

        self.e.emit([table])

        assert col.warnings == []


class TestPKNameTruncation:
    """TEST-05: nombres de PK largos no deben colisionar tras truncado."""

    def setup_method(self) -> None:
        self.e = PostgreSQLDDLEmitter()

    def test_pk_name_above_63_chars_uses_hash(self) -> None:
        # Nombre de tabla de 61 chars → PK_<nombre> = 64 chars → debe truncarse con hash
        long_name = "T" * 61
        col = _col("ID", target_type="INTEGER")
        table = _table(long_name, [col], pk=["ID"])
        stmts = self.e.emit_statements([table])
        create = next(s for s in stmts if "CREATE TABLE" in s)
        # El nombre del constraint PK generado debe caber en 63 chars
        import re

        match = re.search(r'CONSTRAINT "([^"]+)" PRIMARY KEY', create)
        assert match is not None
        assert len(match.group(1)) <= 63

    def test_two_long_tables_same_prefix_no_collision(self) -> None:
        # Dos tablas con el mismo prefijo largo deben generar PK names distintos
        prefix = "T" * 61
        name_a = prefix + "A"
        name_b = prefix + "B"
        col = _col("ID", target_type="INTEGER")
        table_a = _table(name_a, [col], pk=["ID"])
        table_b = _table(name_b, [col], pk=["ID"])
        import re

        def _pk_name(t: CanonicalTable) -> str:
            stmts = self.e.emit_statements([t])
            create = next(s for s in stmts if "CREATE TABLE" in s)
            m = re.search(r'CONSTRAINT "([^"]+)" PRIMARY KEY', create)
            assert m is not None
            return m.group(1)

        pk_a = _pk_name(table_a)
        pk_b = _pk_name(table_b)
        assert pk_a != pk_b, "PK names deben ser distintos para tablas distintas"


class TestTopologicalOrder:
    def setup_method(self) -> None:
        self.e = PostgreSQLDDLEmitter()

    def test_referenced_table_emitted_before_referencing(self) -> None:
        parent = _table("PARENT", [_col("ID", target_type="INTEGER")], pk=["ID"])
        fk = CanonicalFK(
            name="FK_CHILD_PARENT",
            original_name="FK_CHILD_PARENT",
            columns=["PARENT_ID"],
            ref_table="PARENT",
            ref_columns=["ID"],
            on_delete="",
            on_update="",
            is_external=False,
        )
        child = _table("CHILD", [_col("PARENT_ID", target_type="INTEGER")], fks=[fk])
        stmts = self.e.emit_statements([child, parent])
        create_stmts = [s for s in stmts if s.startswith("CREATE TABLE")]
        parent_idx = next(i for i, s in enumerate(create_stmts) if '"PARENT"' in s)
        child_idx = next(i for i, s in enumerate(create_stmts) if '"CHILD"' in s)
        assert parent_idx < child_idx
