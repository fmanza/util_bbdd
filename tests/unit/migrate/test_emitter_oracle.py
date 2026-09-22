"""Tests para OracleDDLEmitter."""

from __future__ import annotations

from util_bbdd.migrate.emitters.oracle import OracleDDLEmitter, _format_default_oracle
from util_bbdd.migrate.ir.models import (
    CanonicalColumn,
    CanonicalFK,
    CanonicalIndex,
    CanonicalTable,
    CanonicalView,
)


def _col(
    name: str = "COL",
    target_type: str = "VARCHAR2(100)",
    nullable: bool = True,
    default: str | None = None,
    comment: str = "",
    auto_increment: bool = False,
    omit: bool = False,
) -> CanonicalColumn:
    return CanonicalColumn(
        name=name,
        original_name=name,
        oracle_type="VARCHAR",
        target_type=target_type,
        nullable=nullable,
        default=default,
        comment=comment,
        ordinal=1,
        char_length=100,
        precision=None,
        scale=None,
        auto_increment=auto_increment,
        is_primary_key=False,
        omit=omit,
    )


def _table(
    name: str = "MY_TABLE",
    columns: list[CanonicalColumn] | None = None,
    pk: list[str] | None = None,
    fks: list[CanonicalFK] | None = None,
    indexes: list[CanonicalIndex] | None = None,
    comment: str = "",
) -> CanonicalTable:
    return CanonicalTable(
        name=name,
        original_name=name,
        schema="TEST",
        columns=columns or [],
        primary_key=pk or [],
        indexes=indexes or [],
        foreign_keys=fks or [],
        comment=comment,
        warnings=[],
    )


def _view(
    name: str = "MY_VIEW",
    query: str = "SELECT 1 FROM DUAL",
    comment: str = "",
) -> CanonicalView:
    return CanonicalView(
        name=name,
        original_name=name,
        schema="TEST",
        query=query,
        columns=[],
        comment=comment,
        warnings=[],
    )


class TestOracleDDLEmitterCreateTable:
    def setup_method(self) -> None:
        self.e = OracleDDLEmitter()

    def test_create_table_uppercased_and_quoted(self) -> None:
        col = _col(name="my_col", target_type="NUMBER(10,0)")
        table = _table(name="my_table", columns=[col])
        ddl = self.e.emit([table])
        assert '"MY_TABLE"' in ddl
        assert '"MY_COL"' in ddl

    def test_create_table_with_primary_key(self) -> None:
        col = _col(name="ID", target_type="NUMBER(10,0)", nullable=False)
        table = _table(name="MY_TABLE", columns=[col], pk=["ID"])
        ddl = self.e.emit([table])
        assert "PRIMARY KEY" in ddl
        assert '"PK_MY_TABLE"' in ddl

    def test_not_null_column(self) -> None:
        col = _col(name="NAME", target_type="VARCHAR2(100)", nullable=False)
        table = _table(columns=[col])
        ddl = self.e.emit([table])
        assert "NOT NULL" in ddl

    def test_nullable_column_no_not_null(self) -> None:
        col = _col(name="OPT", target_type="VARCHAR2(100)", nullable=True)
        table = _table(columns=[col])
        ddl = self.e.emit([table])
        assert "NOT NULL" not in ddl

    def test_default_string_value_quoted(self) -> None:
        col = _col(name="STATUS", target_type="VARCHAR2(10)", default="active")
        table = _table(columns=[col])
        ddl = self.e.emit([table])
        assert "DEFAULT 'active'" in ddl

    def test_default_numeric_value_unquoted(self) -> None:
        col = _col(name="SORT_ORDER", target_type="NUMBER(5,0)", default="0")
        table = _table(columns=[col])
        ddl = self.e.emit([table])
        assert "DEFAULT 0" in ddl

    def test_default_now_maps_to_sysdate(self) -> None:
        col = _col(name="CREATED", target_type="DATE", default="NOW()")
        table = _table(columns=[col])
        ddl = self.e.emit([table])
        assert "DEFAULT SYSDATE" in ddl

    def test_omitted_column_as_comment_line(self) -> None:
        col = _col(name="BAD_COL", omit=True)
        table = _table(columns=[col])
        ddl = self.e.emit([table])
        assert "--" in ddl

    def test_fk_inline_with_on_delete_cascade(self) -> None:
        fk = CanonicalFK(
            name="FK_TEST",
            original_name="FK_TEST",
            columns=["COL_A"],
            ref_table="OTHER_TABLE",
            ref_columns=["ID"],
            on_delete="CASCADE",
            on_update="NO ACTION",
            is_external=False,
        )
        col = _col(name="COL_A", target_type="NUMBER(10,0)")
        table = _table(name="MY_TABLE", columns=[col], fks=[fk])
        ddl = self.e.emit([table])
        assert "ON DELETE CASCADE" in ddl

    def test_fk_on_delete_set_null_supported(self) -> None:
        fk = CanonicalFK(
            name="FK_NULL",
            original_name="FK_NULL",
            columns=["COL_A"],
            ref_table="OTHER_TABLE",
            ref_columns=["ID"],
            on_delete="SET NULL",
            on_update="NO ACTION",
            is_external=False,
        )
        col = _col(name="COL_A", target_type="NUMBER(10,0)")
        table = _table(name="MY_TABLE", columns=[col], fks=[fk])
        ddl = self.e.emit([table])
        assert "ON DELETE SET NULL" in ddl

    def test_fk_on_delete_no_action_omitted(self) -> None:
        fk = CanonicalFK(
            name="FK_NOOP",
            original_name="FK_NOOP",
            columns=["COL_A"],
            ref_table="OTHER_TABLE",
            ref_columns=["ID"],
            on_delete="NO ACTION",
            on_update="NO ACTION",
            is_external=False,
        )
        col = _col(name="COL_A", target_type="NUMBER(10,0)")
        table = _table(name="MY_TABLE", columns=[col], fks=[fk])
        ddl = self.e.emit([table])
        assert "ON DELETE" not in ddl

    def test_external_fk_emitted_as_alter_table(self) -> None:
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
        col = _col(name="COL_A", target_type="NUMBER(10,0)")
        table = _table(name="MY_TABLE", columns=[col], fks=[fk])
        ddl = self.e.emit([table])
        assert "ALTER TABLE" in ddl
        assert "FK externa" in ddl


class TestOracleDDLEmitterSequenceTrigger:
    def setup_method(self) -> None:
        self.e = OracleDDLEmitter()

    def test_auto_increment_generates_sequence(self) -> None:
        col = _col(name="ID", target_type="NUMBER(10,0)", auto_increment=True)
        table = _table(name="MY_TABLE", columns=[col], pk=["ID"])
        ddl = self.e.emit([table])
        assert "CREATE SEQUENCE" in ddl
        assert "MY_TABLE_SEQ" in ddl

    def test_auto_increment_generates_trigger(self) -> None:
        col = _col(name="ID", target_type="NUMBER(10,0)", auto_increment=True)
        table = _table(name="MY_TABLE", columns=[col], pk=["ID"])
        ddl = self.e.emit([table])
        assert "CREATE OR REPLACE TRIGGER" in ddl
        assert "TRG_MY_TABLE" in ddl
        assert "BEFORE INSERT" in ddl

    def test_no_auto_increment_no_sequence(self) -> None:
        col = _col(name="ID", target_type="NUMBER(10,0)", auto_increment=False)
        table = _table(name="MY_TABLE", columns=[col], pk=["ID"])
        ddl = self.e.emit([table])
        assert "CREATE SEQUENCE" not in ddl
        assert "CREATE OR REPLACE TRIGGER" not in ddl

    def test_sequence_name_max_30_chars(self) -> None:
        long_name = "VERY_LONG_TABLE_NAME_EXCEEDS_26"  # 31 chars
        col = _col(name="ID", target_type="NUMBER(10,0)", auto_increment=True)
        table = _table(name=long_name, columns=[col], pk=["ID"])
        stmts = self.e.emit_statements([table])
        seq_stmts = [s for s in stmts if "CREATE SEQUENCE" in s]
        assert len(seq_stmts) == 1
        # Extract sequence name — it's double-quoted
        seq_stmt = seq_stmts[0]
        import re

        match = re.search(r'"([^"]+)"', seq_stmt)
        assert match is not None
        assert len(match.group(1)) <= 30

    def test_trigger_name_max_30_chars(self) -> None:
        long_name = "VERY_LONG_TABLE_NAME_EXCEEDS_26"
        col = _col(name="ID", target_type="NUMBER(10,0)", auto_increment=True)
        table = _table(name=long_name, columns=[col], pk=["ID"])
        stmts = self.e.emit_statements([table])
        trg_stmts = [s for s in stmts if "CREATE OR REPLACE TRIGGER" in s]
        assert len(trg_stmts) == 1
        import re

        match = re.search(r'TRIGGER "([^"]+)"', trg_stmts[0])
        assert match is not None
        assert len(match.group(1)) <= 30

    def test_two_auto_increment_columns_emit_one_seq_trg(self) -> None:
        """BUG-06: tabla con 2 columnas auto_increment debe emitir sólo 1 SEQ y 1 TRG."""
        col1 = _col(name="ID", target_type="NUMBER(10,0)", auto_increment=True)
        col2 = _col(name="ALT_ID", target_type="NUMBER(10,0)", auto_increment=True)
        table = _table(name="DUAL_AI", columns=[col1, col2], pk=["ID"])
        stmts = self.e.emit_statements([table])
        seq_stmts = [s for s in stmts if "CREATE SEQUENCE" in s]
        trg_stmts = [s for s in stmts if "CREATE OR REPLACE TRIGGER" in s]
        assert len(seq_stmts) == 1, "Debe haber exactamente 1 CREATE SEQUENCE"
        assert len(trg_stmts) == 1, "Debe haber exactamente 1 CREATE OR REPLACE TRIGGER"


class TestOracleDDLEmitterComments:
    def setup_method(self) -> None:
        self.e = OracleDDLEmitter()

    def test_table_comment_emitted(self) -> None:
        col = _col()
        table = _table(columns=[col], comment="Table description")
        ddl = self.e.emit([table])
        assert "COMMENT ON TABLE" in ddl
        assert "Table description" in ddl

    def test_column_comment_emitted(self) -> None:
        col = _col(name="STATUS", comment="Current status")
        table = _table(columns=[col])
        ddl = self.e.emit([table])
        assert "COMMENT ON COLUMN" in ddl
        assert "Current status" in ddl

    def test_empty_comment_not_emitted(self) -> None:
        col = _col(name="STATUS", comment="")
        table = _table(columns=[col], comment="")
        ddl = self.e.emit([table])
        assert "COMMENT ON" not in ddl

    def test_comment_with_single_quotes_escaped(self) -> None:
        col = _col()
        table = _table(columns=[col], comment="It's a table")
        ddl = self.e.emit([table])
        assert "It''s a table" in ddl


class TestOracleDDLEmitterIndexes:
    def setup_method(self) -> None:
        self.e = OracleDDLEmitter()

    def test_index_emitted(self) -> None:
        col = _col(name="STATUS")
        idx = CanonicalIndex(name="IDX_STATUS", original_name="IDX_STATUS", columns=["STATUS"], unique=False)
        table = _table(columns=[col], indexes=[idx])
        ddl = self.e.emit([table])
        assert "CREATE INDEX" in ddl
        assert '"IDX_STATUS"' in ddl

    def test_unique_index_emitted(self) -> None:
        col = _col(name="EMAIL")
        idx = CanonicalIndex(name="UNQ_EMAIL", original_name="UNQ_EMAIL", columns=["EMAIL"], unique=True)
        table = _table(columns=[col], indexes=[idx])
        ddl = self.e.emit([table])
        assert "CREATE UNIQUE INDEX" in ddl

    def test_pk_index_skipped(self) -> None:
        col = _col(name="ID", target_type="NUMBER(10,0)")
        idx = CanonicalIndex(name="PK_MY_TABLE", original_name="PK_MY_TABLE", columns=["ID"], unique=True)
        table = _table(columns=[col], pk=["ID"], indexes=[idx])
        ddl = self.e.emit([table])
        # PK index (unique, same cols as pk) should not create a separate index
        assert "CREATE UNIQUE INDEX" not in ddl


class TestOracleDDLEmitterViews:
    def setup_method(self) -> None:
        self.e = OracleDDLEmitter()

    def test_create_or_replace_view(self) -> None:
        view = _view(name="MY_VIEW", query="SELECT 1 FROM DUAL")
        ddl = self.e.emit([], views=[view])
        assert "CREATE OR REPLACE VIEW" in ddl
        assert '"MY_VIEW"' in ddl
        assert "SELECT 1 FROM DUAL" in ddl

    def test_view_with_warnings_gets_note_comment(self) -> None:
        from util_bbdd.migrate.ir.models import MigrationWarning

        view = _view(name="MY_VIEW", query="SELECT NOW()")
        view.warnings.append(
            MigrationWarning(
                table="MY_VIEW",
                column=None,
                oracle_type="VIEW",
                target_type="VIEW",
                message="needs manual review",
                severity="WARNING",
            )
        )
        ddl = self.e.emit([], views=[view])
        assert "-- NOTE:" in ddl

    def test_view_with_comment_emitted(self) -> None:
        view = _view(name="MY_VIEW", query="SELECT 1 FROM DUAL", comment="A useful view")
        ddl = self.e.emit([], views=[view])
        assert "-- COMMENT: A useful view" in ddl

    def test_empty_views_list(self) -> None:
        col = _col()
        table = _table(columns=[col])
        ddl = self.e.emit([table], views=[])
        assert "CREATE OR REPLACE VIEW" not in ddl

    def test_views_topological_order(self) -> None:
        # view2 depends on view1; view1 should appear first
        view1 = _view(name="BASE_VIEW", query="SELECT 1 AS id FROM DUAL")
        view2 = _view(name="TOP_VIEW", query="SELECT id FROM BASE_VIEW")
        ddl = self.e.emit([], views=[view2, view1])
        idx1 = ddl.index('"BASE_VIEW"')
        idx2 = ddl.index('"TOP_VIEW"')
        assert idx1 < idx2


class TestOracleDDLEmitterTopologicalSort:
    def setup_method(self) -> None:
        self.e = OracleDDLEmitter()

    def test_referenced_table_emitted_before_referencing(self) -> None:
        col_a = _col(name="ID", target_type="NUMBER(10,0)")
        col_b = _col(name="A_ID", target_type="NUMBER(10,0)")
        fk = CanonicalFK(
            name="FK_B_A",
            original_name="FK_B_A",
            columns=["A_ID"],
            ref_table="TABLE_A",
            ref_columns=["ID"],
            on_delete="NO ACTION",
            on_update="NO ACTION",
            is_external=False,
        )
        table_a = _table(name="TABLE_A", columns=[col_a], pk=["ID"])
        table_b = _table(name="TABLE_B", columns=[col_b], fks=[fk])
        # Pass in reverse order; sort should fix it
        ddl = self.e.emit([table_b, table_a])
        idx_a = ddl.index('"TABLE_A"')
        idx_b = ddl.index('"TABLE_B"')
        assert idx_a < idx_b


class TestFormatDefaultOracle:
    def test_now_maps_to_sysdate(self) -> None:
        assert _format_default_oracle("NOW()") == "SYSDATE"

    def test_current_timestamp_maps_to_sysdate(self) -> None:
        assert _format_default_oracle("CURRENT_TIMESTAMP") == "SYSDATE"

    def test_current_date_maps_to_trunc_sysdate(self) -> None:
        assert _format_default_oracle("CURRENT_DATE") == "TRUNC(SYSDATE)"

    def test_true_maps_to_1(self) -> None:
        assert _format_default_oracle("TRUE") == "1"

    def test_false_maps_to_0(self) -> None:
        assert _format_default_oracle("FALSE") == "0"

    def test_null_maps_to_null(self) -> None:
        assert _format_default_oracle("NULL") == "NULL"

    def test_numeric_value_unquoted(self) -> None:
        assert _format_default_oracle("42") == "42"
        assert _format_default_oracle("3.14") == "3.14"

    def test_string_value_single_quoted(self) -> None:
        result = _format_default_oracle("active")
        assert result == "'active'"

    def test_string_with_single_quote_escaped(self) -> None:
        result = _format_default_oracle("it's")
        assert result == "'it''s'"

    def test_empty_string_maps_to_null(self) -> None:
        assert _format_default_oracle("") == "NULL"


class TestOracleDefaultFallbackWarning:
    """MIG-03 (AUDIT_CODE 2026-09-22): un DEFAULT con forma de llamada a función
    (p.ej. GETDATE() de SQL Server) que el emisor no reconoce cae al fallback y se
    entrecomilla como literal de texto; hasta ahora, sin ningún MigrationWarning."""

    def setup_method(self) -> None:
        self.e = OracleDDLEmitter()

    def test_unrecognized_function_call_default_emits_warning(self) -> None:
        col = _col(name="CREATED_AT", target_type="DATE", default="GETDATE()")
        table = _table(name="T_SQLSERVER_SRC", columns=[col])

        ddl = self.e.emit([table])

        assert "DEFAULT 'GETDATE()'" in ddl
        assert len(col.warnings) == 1
        assert col.warnings[0].severity == "WARNING"
        assert "GETDATE()" in col.warnings[0].message

    def test_recognized_function_default_does_not_emit_warning(self) -> None:
        col = _col(name="CREATED_AT", target_type="DATE", default="NOW()")
        table = _table(name="T_OK", columns=[col])

        self.e.emit([table])

        assert col.warnings == []

    def test_plain_string_default_does_not_emit_warning(self) -> None:
        col = _col(name="STATUS", target_type="VARCHAR2(10)", default="active")
        table = _table(name="T_STATUS", columns=[col])

        self.e.emit([table])

        assert col.warnings == []


class TestOracleDDLEmitterIdentityMode:
    def test_default_mode_generates_sequence_and_trigger(self) -> None:
        e = OracleDDLEmitter()
        col = _col(name="ID", target_type="NUMBER(10,0)", auto_increment=True)
        table = _table(name="ORDERS", columns=[col], pk=["ID"])
        ddl = e.emit([table])
        assert "CREATE SEQUENCE" in ddl
        assert "CREATE OR REPLACE TRIGGER" in ddl

    def test_identity_by_default_on_null_emits_inline_clause(self) -> None:
        e = OracleDDLEmitter(oracle_identity_mode="identity_by_default_on_null")
        col = _col(name="ID", target_type="NUMBER(10,0)", auto_increment=True)
        table = _table(name="ORDERS", columns=[col], pk=["ID"])
        ddl = e.emit([table])
        assert "GENERATED BY DEFAULT ON NULL AS IDENTITY" in ddl

    def test_identity_by_default_on_null_no_sequence_no_trigger(self) -> None:
        e = OracleDDLEmitter(oracle_identity_mode="identity_by_default_on_null")
        col = _col(name="ID", target_type="NUMBER(10,0)", auto_increment=True)
        table = _table(name="ORDERS", columns=[col], pk=["ID"])
        ddl = e.emit([table])
        assert "CREATE SEQUENCE" not in ddl
        assert "CREATE OR REPLACE TRIGGER" not in ddl

    def test_identity_clause_inside_create_table(self) -> None:
        e = OracleDDLEmitter(oracle_identity_mode="identity_by_default_on_null")
        col = _col(name="ID", target_type="NUMBER(10,0)", auto_increment=True)
        table = _table(name="PRODUCTS", columns=[col], pk=["ID"])
        stmts = e.emit_statements([table])
        create_table_stmt = next(s for s in stmts if "CREATE TABLE" in s)
        assert "GENERATED BY DEFAULT ON NULL AS IDENTITY" in create_table_stmt

    def test_non_auto_increment_column_unaffected_in_identity_mode(self) -> None:
        e = OracleDDLEmitter(oracle_identity_mode="identity_by_default_on_null")
        col = _col(name="NAME", target_type="VARCHAR2(100)", auto_increment=False)
        table = _table(name="T", columns=[col])
        ddl = e.emit([table])
        assert "GENERATED BY DEFAULT ON NULL AS IDENTITY" not in ddl
        assert "CREATE SEQUENCE" not in ddl

    def test_invalid_identity_mode_raises_value_error(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="oracle_identity_mode"):
            OracleDDLEmitter(oracle_identity_mode="always")  # type: ignore[arg-type]
