"""Tests para SQLServerDDLEmitter."""

from __future__ import annotations

from util_bbdd.migrate.emitters.sqlserver import SQLServerDDLEmitter, _format_default_sqlserver
from util_bbdd.migrate.ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalTable,
)


def _col(
    name: str,
    target_type: str = "NVARCHAR(100)",
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


class TestSQLServerDDLEmitter:
    def setup_method(self) -> None:
        self.emitter = SQLServerDDLEmitter()

    def test_create_table_basic(self) -> None:
        table = _table("USERS", [_col("ID", "INT", nullable=False), _col("NAME")])
        ddl = self.emitter.emit([table])
        assert "CREATE TABLE [USERS]" in ddl
        assert "[ID] INT" in ddl
        assert "[NAME] NVARCHAR(100)" in ddl

    def test_bracket_escaping(self) -> None:
        table = _table("order", [_col("select", "INT")])
        ddl = self.emitter.emit([table])
        assert "[order]" in ddl
        assert "[select]" in ddl

    def test_bracket_escaping_closing_bracket_in_name(self) -> None:
        table = _table("T]AB", [_col("COL")])
        ddl = self.emitter.emit([table])
        assert "[T]]AB]" in ddl

    def test_no_engine_clause(self) -> None:
        table = _table("T", [_col("ID", "INT")])
        ddl = self.emitter.emit([table])
        assert "ENGINE=" not in ddl
        assert "CHARSET=" not in ddl
        assert "COLLATE=" not in ddl

    def test_identity_column(self) -> None:
        table = _table(
            "ORDERS",
            [_col("ID", "INT", nullable=False, auto_increment=True, is_pk=True)],
            pk=["ID"],
        )
        ddl = self.emitter.emit([table])
        assert "IDENTITY(1,1)" in ddl
        assert "AUTO_INCREMENT" not in ddl

    def test_identity_not_null(self) -> None:
        table = _table(
            "T",
            [_col("ID", "INT", nullable=False, auto_increment=True, is_pk=True)],
            pk=["ID"],
        )
        ddl = self.emitter.emit([table])
        assert "[ID] INT IDENTITY(1,1) NOT NULL" in ddl

    def test_null_explicit_for_nullable(self) -> None:
        table = _table("T", [_col("COL1", "NVARCHAR(100)", nullable=True)])
        ddl = self.emitter.emit([table])
        assert "[COL1] NVARCHAR(100) NULL" in ddl

    def test_not_null_for_non_nullable(self) -> None:
        table = _table("T", [_col("COL1", "INT", nullable=False)])
        ddl = self.emitter.emit([table])
        assert "[COL1] INT NOT NULL" in ddl

    def test_pk_constraint_named(self) -> None:
        table = _table(
            "ORDERS",
            [_col("ID", "INT", nullable=False)],
            pk=["ID"],
        )
        ddl = self.emitter.emit([table])
        assert "CONSTRAINT [PK_ORDERS] PRIMARY KEY ([ID])" in ddl

    def test_fk_inline(self) -> None:
        fk = CanonicalFK(
            name="FK_ORD_CUST",
            original_name="FK_ORD_CUST",
            columns=["CUSTOMER_ID"],
            ref_table="CUSTOMERS",
            ref_columns=["ID"],
            on_delete="NO ACTION",
            on_update="NO ACTION",
        )
        table = _table(
            "ORDERS",
            [_col("ID", "INT"), _col("CUSTOMER_ID", "INT")],
            fks=[fk],
        )
        ddl = self.emitter.emit([table])
        assert "CONSTRAINT [FK_ORD_CUST] FOREIGN KEY ([CUSTOMER_ID]) REFERENCES [CUSTOMERS] ([ID])" in ddl

    def test_fk_on_delete_cascade(self) -> None:
        fk = CanonicalFK(
            name="FK_DEL",
            original_name="FK_DEL",
            columns=["PARENT_ID"],
            ref_table="PARENT",
            ref_columns=["ID"],
            on_delete="CASCADE",
            on_update="NO ACTION",
        )
        table = _table("CHILD", [_col("PARENT_ID", "INT")], fks=[fk])
        ddl = self.emitter.emit([table])
        assert "ON DELETE CASCADE" in ddl

    def test_omitted_column_as_comment(self) -> None:
        omit_col = _col("RID", omit=True, ddl_comment="-- AVISO: ROWID omitido")
        active_col = _col("ID", "INT")
        table = _table("T", [omit_col, active_col])
        ddl = self.emitter.emit([table])
        assert "-- AVISO: ROWID omitido" in ddl
        assert "[RID]" not in ddl

    def test_table_comment_as_sql_comment_prefix(self) -> None:
        table = _table("T", [_col("ID", "INT")], comment="Tabla de pedidos")
        ddl = self.emitter.emit([table])
        assert "-- COMMENT: Tabla de pedidos" in ddl

    def test_column_ddl_comment_appended(self) -> None:
        col = _col("CREATED", "DATETIME2", ddl_comment="-- AVISO: DATE Oracle contiene hora")
        table = _table("T", [col])
        ddl = self.emitter.emit([table])
        assert "AVISO: DATE Oracle contiene hora" in ddl

    def test_column_comment_oracle_appended(self) -> None:
        col = _col("NAME", "NVARCHAR(100)", comment="Nombre del cliente")
        table = _table("T", [col])
        ddl = self.emitter.emit([table])
        assert "Nombre del cliente" in ddl

    def test_emit_returns_string_ending_semicolon(self) -> None:
        table = _table("T", [_col("ID", "INT")])
        ddl = self.emitter.emit([table])
        assert ddl.endswith(";\n")

    def test_emit_statements_returns_list(self) -> None:
        table = _table("T", [_col("ID", "INT")])
        stmts = self.emitter.emit_statements([table])
        assert isinstance(stmts, list)
        assert len(stmts) >= 1

    def test_create_index(self) -> None:
        idx = CanonicalIndex(
            name="IDX_NAME",
            original_name="IDX_NAME",
            columns=["NAME"],
            unique=False,
        )
        table = _table("T", [_col("NAME", "NVARCHAR(100)")], indexes=[idx])
        ddl = self.emitter.emit([table])
        assert "CREATE INDEX [IDX_NAME] ON [T] ([NAME])" in ddl

    def test_create_unique_index(self) -> None:
        idx = CanonicalIndex(
            name="UQ_EMAIL",
            original_name="UQ_EMAIL",
            columns=["EMAIL"],
            unique=True,
        )
        table = _table("T", [_col("EMAIL", "NVARCHAR(200)")], indexes=[idx])
        ddl = self.emitter.emit([table])
        assert "CREATE UNIQUE INDEX [UQ_EMAIL] ON [T] ([EMAIL])" in ddl

    def test_fk_circular_emitted_as_alter_table(self) -> None:
        fk_ab = CanonicalFK(
            name="FK_A_B",
            original_name="FK_A_B",
            columns=["B_ID"],
            ref_table="B",
            ref_columns=["ID"],
            on_delete="NO ACTION",
            on_update="NO ACTION",
        )
        fk_ba = CanonicalFK(
            name="FK_B_A",
            original_name="FK_B_A",
            columns=["A_ID"],
            ref_table="A",
            ref_columns=["ID"],
            on_delete="NO ACTION",
            on_update="NO ACTION",
        )
        table_a = _table("A", [_col("ID", "INT"), _col("B_ID", "INT")], fks=[fk_ab])
        table_b = _table("B", [_col("ID", "INT"), _col("A_ID", "INT")], fks=[fk_ba])
        stmts = self.emitter.emit_statements([table_a, table_b])
        alter_stmts = [s for s in stmts if s.startswith("ALTER TABLE")]
        assert len(alter_stmts) >= 1

    def test_fk_external_at_end_with_comment(self) -> None:
        fk_ext = CanonicalFK(
            name="FK_EXT",
            original_name="FK_EXT",
            columns=["EXT_ID"],
            ref_table="EXTERNAL_TABLE",
            ref_columns=["ID"],
            on_delete="NO ACTION",
            on_update="NO ACTION",
            is_external=True,
        )
        table = _table("T", [_col("EXT_ID", "INT")], fks=[fk_ext])
        stmts = self.emitter.emit_statements([table])
        # Last statement should be the external FK ALTER TABLE
        last = stmts[-1]
        assert "FK externa" in last
        assert "ALTER TABLE [T]" in last

    def test_table_without_active_columns_has_error_comment(self) -> None:
        omit_col = _col("RID", omit=True)
        table = _table("ONLY_OMIT", [omit_col])
        ddl = self.emitter.emit([table])
        assert "ERROR" in ddl


class TestSQLServerCollation:
    def test_collation_applied_to_nvarchar(self) -> None:
        emitter = SQLServerDDLEmitter(collation="SQL_Latin1_General_CP1_CI_AS")
        col = _col("NAME", "NVARCHAR(100)")
        table = _table("T", [col])
        ddl = emitter.emit([table])
        assert "COLLATE SQL_Latin1_General_CP1_CI_AS" in ddl

    def test_collation_applied_to_varchar(self) -> None:
        emitter = SQLServerDDLEmitter(collation="Latin1_General_CI_AS")
        col = _col("CODE", "VARCHAR(50)")
        table = _table("T", [col])
        ddl = emitter.emit([table])
        assert "COLLATE Latin1_General_CI_AS" in ddl

    def test_collation_not_applied_to_int(self) -> None:
        emitter = SQLServerDDLEmitter(collation="SQL_Latin1_General_CP1_CI_AS")
        col = _col("ID", "INT")
        table = _table("T", [col])
        ddl = emitter.emit([table])
        assert "COLLATE" not in ddl

    def test_collation_not_applied_to_datetime2(self) -> None:
        emitter = SQLServerDDLEmitter(collation="SQL_Latin1_General_CP1_CI_AS")
        col = _col("DT", "DATETIME2")
        table = _table("T", [col])
        ddl = emitter.emit([table])
        assert "COLLATE" not in ddl

    def test_no_collation_no_collate_clause(self) -> None:
        emitter = SQLServerDDLEmitter(collation=None)
        col = _col("NAME", "NVARCHAR(100)")
        table = _table("T", [col])
        ddl = emitter.emit([table])
        assert "COLLATE" not in ddl


class TestFormatDefaultSQLServer:
    def test_sysdate_maps_to_getdate(self) -> None:
        assert _format_default_sqlserver("SYSDATE") == "GETDATE()"

    def test_systimestamp_maps_to_sysdatetime(self) -> None:
        assert _format_default_sqlserver("SYSTIMESTAMP") == "SYSDATETIME()"

    def test_sys_guid_maps_to_newid(self) -> None:
        assert _format_default_sqlserver("SYS_GUID()") == "NEWID()"

    def test_user_maps_to_system_user(self) -> None:
        assert _format_default_sqlserver("USER") == "SYSTEM_USER"

    def test_now_maps_to_getdate(self) -> None:
        assert _format_default_sqlserver("NOW()") == "GETDATE()"

    def test_current_timestamp_preserved(self) -> None:
        assert _format_default_sqlserver("CURRENT_TIMESTAMP") == "CURRENT_TIMESTAMP"

    def test_null_preserved(self) -> None:
        assert _format_default_sqlserver("NULL") == "NULL"

    def test_numeric_literal_preserved(self) -> None:
        assert _format_default_sqlserver("42") == "42"
        assert _format_default_sqlserver("3.14") == "3.14"

    def test_string_literal_quoted(self) -> None:
        assert _format_default_sqlserver("ACTIVE") == "'ACTIVE'"

    def test_single_quote_escaped(self) -> None:
        assert _format_default_sqlserver("O'Brien") == "'O''Brien'"

    def test_empty_string_returns_null(self) -> None:
        assert _format_default_sqlserver("") == "NULL"

    def test_oracle_quoted_numeric_default_not_double_quoted(self) -> None:
        """Regresión: Oracle almacena DATA_DEFAULT con comillas ('6').
        El emitter no debe volver a entrecomillar → evitar DEFAULT '''6'''."""
        assert _format_default_sqlserver("'6'") == "'6'"

    def test_oracle_quoted_string_default_not_double_quoted(self) -> None:
        """Regresión: literal de texto Oracle ya entrecomillado ('ACTIVO') no se dobla."""
        assert _format_default_sqlserver("'ACTIVO'") == "'ACTIVO'"

    def test_oracle_empty_string_default_preserved(self) -> None:
        """Literal vacío Oracle ('') se preserva tal cual."""
        assert _format_default_sqlserver("''") == "''"


class TestSQLServerDefaultFallbackWarning:
    """MIG-03 (AUDIT_CODE 2026-09-22): un DEFAULT con forma de llamada a función
    (p.ej. CURDATE() de MariaDB) que el emisor no reconoce cae al fallback y se
    entrecomilla como literal de texto; hasta ahora, sin ningún MigrationWarning."""

    def setup_method(self) -> None:
        self.e = SQLServerDDLEmitter()

    def test_unrecognized_function_call_default_emits_warning(self) -> None:
        col = _col("CREATED_AT", "DATETIME2", default="CURDATE()")
        table = _table("T_MARIADB_SRC", [col])

        ddl = self.e.emit([table])

        assert "DEFAULT 'CURDATE()'" in ddl
        assert len(col.warnings) == 1
        assert col.warnings[0].severity == "WARNING"
        assert "CURDATE()" in col.warnings[0].message

    def test_recognized_function_default_does_not_emit_warning(self) -> None:
        col = _col("CREATED_AT", "DATETIME2", default="SYSDATE")
        table = _table("T_OK", [col])

        self.e.emit([table])

        assert col.warnings == []

    def test_plain_string_default_does_not_emit_warning(self) -> None:
        col = _col("STATUS", "NVARCHAR(10)", default="ACTIVE")
        table = _table("T_STATUS", [col])

        self.e.emit([table])

        assert col.warnings == []
