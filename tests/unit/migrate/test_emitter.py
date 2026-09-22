"""Tests para MariaDBDDLEmitter."""

from __future__ import annotations

import pytest

from util_bbdd.migrate.emitters.mariadb import MariaDBDDLEmitter, _topological_sort
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
) -> CanonicalColumn:
    return CanonicalColumn(
        name=name,
        original_name=name,
        oracle_type="",
        target_type=target_type,
        nullable=nullable,
        default=default,
        comment="",
        ordinal=1,
        auto_increment=auto_increment,
        is_primary_key=is_pk,
        omit=omit,
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


class TestMariaDBDDLEmitter:
    def setup_method(self) -> None:
        self.emitter = MariaDBDDLEmitter(charset="utf8mb4", collation="utf8mb4_unicode_ci")

    def test_create_table_basic(self) -> None:
        table = _table("USERS", [_col("ID", "BIGINT", nullable=False), _col("NAME")], pk=["ID"])
        ddl = self.emitter.emit([table])
        assert "CREATE TABLE `USERS`" in ddl
        assert "`ID` BIGINT NOT NULL" in ddl
        assert "PRIMARY KEY (`ID`)" in ddl
        assert "ENGINE=InnoDB" in ddl
        assert "utf8mb4" in ddl

    def test_backtick_escaping(self) -> None:
        table = _table("order", [_col("select", "INT")])
        ddl = self.emitter.emit([table])
        assert "`order`" in ddl
        assert "`select`" in ddl

    def test_auto_increment_column(self) -> None:
        # MIG-02: columnas AUTO_INCREMENT preservan el ancho del tipo origen — un PK
        # BIGINT no se colapsa a INT(11) (evita overflow en PKs grandes migradas desde
        # SQL Server/Oracle/PostgreSQL). Ver .ai/sessions/.../02_PLAN_p1_p2.md.
        table = _table(
            "ORDERS",
            [_col("ID", "BIGINT", nullable=False, auto_increment=True, is_pk=True)],
            pk=["ID"],
        )
        ddl = self.emitter.emit([table])
        assert "`ID` BIGINT(20) NOT NULL AUTO_INCREMENT" in ddl

    @pytest.mark.parametrize(
        ("source_mapped_type", "expected_col_type"),
        [
            ("INT", "INT(11)"),  # SQL Server INT IDENTITY / PostgreSQL INTEGER SERIAL
            ("BIGINT", "BIGINT(20)"),  # SQL Server BIGINT IDENTITY / PostgreSQL BIGINT SERIAL
            ("SMALLINT", "SMALLINT(6)"),  # SQL Server SMALLINT IDENTITY / PostgreSQL SMALLINT
            ("TINYINT", "TINYINT(4)"),  # MySQL/MariaDB TINYINT AUTO_INCREMENT
            ("INT(11)", "INT(11)"),  # ya trae display width propio (Oracle _with_int_width)
            ("BIGINT(20)", "BIGINT(20)"),  # Oracle NUMBER sin precisión con display width
        ],
    )
    def test_auto_increment_preserves_source_width(self, source_mapped_type: str, expected_col_type: str) -> None:
        """AUTO_INCREMENT preserva la categoría del tipo fuente con su display width convencional."""
        table = _table(
            "T_AI",
            [_col("id", source_mapped_type, nullable=False, auto_increment=True, is_pk=True)],
            pk=["id"],
        )
        ddl = self.emitter.emit([table])
        assert f"`id` {expected_col_type} NOT NULL AUTO_INCREMENT" in ddl

    def test_non_auto_increment_preserves_original_type(self) -> None:
        """Columnas sin AUTO_INCREMENT NO deben verse afectadas por el fix."""
        table = _table(
            "T_NO_AI",
            [_col("big_col", "BIGINT", nullable=False)],
        )
        ddl = self.emitter.emit([table])
        assert "`big_col` BIGINT NOT NULL" in ddl
        assert "INT(11)" not in ddl

    def test_omitted_column_appears_as_comment(self) -> None:
        table = _table("T1", [_col("ROWID_COL", omit=True)])
        ddl = self.emitter.emit([table])
        assert "--" in ddl  # aparece como comentario SQL
        assert "`ROWID_COL`" not in ddl  # no como columna DDL con backticks

    def test_table_comment_included(self) -> None:
        table = _table("T2", [_col("C1")], comment="Mi tabla de prueba")
        ddl = self.emitter.emit([table])
        assert "Mi tabla de prueba" in ddl

    def test_foreign_key_inline(self) -> None:
        fk = CanonicalFK(
            name="FK_USER",
            original_name="FK_USER",
            columns=["USER_ID"],
            ref_table="USERS",
            ref_columns=["ID"],
            on_delete="CASCADE",
            on_update="NO ACTION",
            is_external=False,
        )
        table = _table("ORDERS", [_col("USER_ID", "BIGINT")], fks=[fk])
        ddl = self.emitter.emit([table])
        assert "FOREIGN KEY" in ddl
        assert "REFERENCES `USERS`" in ddl
        assert "ON DELETE CASCADE" in ddl

    def test_external_fk_not_inline_in_create_table(self) -> None:
        """FK externa no aparece inline en CREATE TABLE; se emite como ALTER TABLE al final."""
        fk = CanonicalFK(
            name="FK_EXT",
            original_name="FK_EXT",
            columns=["EXT_ID"],
            ref_table="EXTERNAL_TABLE",
            ref_columns=["ID"],
            on_delete="NO ACTION",
            on_update="NO ACTION",
            is_external=True,
        )
        table = _table("T3", [_col("EXT_ID", "BIGINT")], fks=[fk])
        stmts = self.emitter.emit_statements([table])
        create_stmt = stmts[0]
        assert "FK_EXT" not in create_stmt  # no inline en CREATE TABLE
        assert any("ALTER TABLE" in s and "FK_EXT" in s for s in stmts)  # presente al final

    def test_external_fk_alter_table_has_comment(self) -> None:
        fk = CanonicalFK(
            name="FK_EXT2",
            original_name="FK_EXT2",
            columns=["EXT_ID"],
            ref_table="REMOTE_TABLE",
            ref_columns=["ID"],
            on_delete="NO ACTION",
            on_update="NO ACTION",
            is_external=True,
        )
        table = _table("T3B", [_col("EXT_ID", "BIGINT")], fks=[fk])
        stmts = self.emitter.emit_statements([table])
        ext_stmt = next(s for s in stmts if "FK_EXT2" in s)
        assert "-- FK externa" in ext_stmt
        assert "REMOTE_TABLE" in ext_stmt

    def test_index_emitted_separately(self) -> None:
        idx = CanonicalIndex(name="IDX_NAME", original_name="IDX_NAME", columns=["NAME"], unique=False)
        table = _table("PRODUCTS", [_col("NAME")], indexes=[idx])
        ddl = self.emitter.emit([table])
        assert "CREATE INDEX `IDX_NAME`" in ddl

    def test_unique_index_emitted(self) -> None:
        idx = CanonicalIndex(name="UQ_EMAIL", original_name="UQ_EMAIL", columns=["EMAIL"], unique=True)
        table = _table("USERS2", [_col("EMAIL")], indexes=[idx])
        ddl = self.emitter.emit([table])
        assert "CREATE UNIQUE INDEX `UQ_EMAIL`" in ddl

    def test_emit_statements_returns_list(self) -> None:
        table = _table("T4", [_col("C1")])
        stmts = self.emitter.emit_statements([table])
        assert isinstance(stmts, list)
        assert len(stmts) >= 1
        # Ninguna sentencia debe terminar en ';'
        for s in stmts:
            assert not s.strip().endswith(";")

    def test_full_script_ends_with_semicolon(self) -> None:
        table = _table("T5", [_col("C1")])
        script = self.emitter.emit([table])
        assert script.strip().endswith(";")

    def test_all_columns_omitted_emits_error_comment(self) -> None:
        table = _table("T_ALL_OMIT", [_col("R1", omit=True), _col("R2", omit=True)])
        ddl = self.emitter.emit([table])
        assert "sin columnas activas" in ddl
        assert "`R1`" not in ddl
        assert "`R2`" not in ddl

    def test_index_with_omitted_column_is_skipped(self) -> None:
        idx = CanonicalIndex(name="IDX_OMIT_COL", original_name="IDX_OMIT_COL", columns=["R1"], unique=False)
        table = _table("T_SKIP_IDX", [_col("R1", omit=True), _col("C1")], indexes=[idx])
        ddl = self.emitter.emit([table])
        assert "IDX_OMIT_COL" not in ddl

    def test_sysdate_default_not_quoted(self) -> None:
        table = _table("T_SYSDATE", [_col("CREATED_AT", "DATETIME", default="SYSDATE")])
        ddl = self.emitter.emit([table])
        assert "DEFAULT SYSDATE" in ddl
        assert "DEFAULT 'SYSDATE'" not in ddl

    def test_sys_guid_default_not_quoted(self) -> None:
        table = _table("T_GUID", [_col("ID", "VARCHAR(36)", default="SYS_GUID()")])
        ddl = self.emitter.emit([table])
        assert "DEFAULT SYS_GUID()" in ddl
        assert "DEFAULT 'SYS_GUID()'" not in ddl

    def test_oracle_quoted_numeric_default_not_double_quoted(self) -> None:
        """Regresión: Oracle almacena DATA_DEFAULT con comillas (p.ej. '6').
        El emitter no debe volver a entrecomillar → evitar DEFAULT '''6'''."""
        table = _table(
            "T_APP",
            [_col("IDAPLICACION", "INT(11)", nullable=False, default="'6'")],
        )
        ddl = self.emitter.emit([table])
        assert "DEFAULT '6'" in ddl
        assert "DEFAULT '''6'''" not in ddl

    def test_oracle_quoted_string_default_not_double_quoted(self) -> None:
        """Regresión: literal de texto Oracle ya entrecomillado ('ACTIVO') no se dobla."""
        table = _table(
            "T_ESTADO",
            [_col("ESTADO", "VARCHAR(10)", nullable=False, default="'ACTIVO'")],
        )
        ddl = self.emitter.emit([table])
        assert "DEFAULT 'ACTIVO'" in ddl
        assert "DEFAULT ''ACTIVO''" not in ddl

    def test_oracle_empty_string_default_preserved(self) -> None:
        """Literal vacío Oracle ('') se preserva tal cual."""
        table = _table(
            "T_EMPTY",
            [_col("NOTA", "VARCHAR(100)", nullable=True, default="''")],
        )
        ddl = self.emitter.emit([table])
        assert "DEFAULT ''" in ddl


class TestTopologicalSort:
    def _fk(self, name: str, ref_table: str) -> CanonicalFK:
        return CanonicalFK(
            name=name,
            original_name=name,
            columns=["ID"],
            ref_table=ref_table,
            ref_columns=["ID"],
            on_delete="NO ACTION",
            on_update="NO ACTION",
            is_external=False,
        )

    def test_independent_tables_any_order(self) -> None:
        t1 = _table("A", [_col("C")])
        t2 = _table("B", [_col("C")])
        ordered, circular = _topological_sort([t1, t2])
        assert len(ordered) == 2
        assert len(circular) == 0

    def test_referenced_table_comes_first(self) -> None:
        parent = _table("PARENT", [_col("ID")])
        child = _table("CHILD", [_col("PID", "BIGINT")], fks=[self._fk("FK1", "PARENT")])
        ordered, circular = _topological_sort([child, parent])
        names = [t.name for t in ordered]
        assert names.index("PARENT") < names.index("CHILD")
        assert len(circular) == 0

    def test_circular_fks_detected(self) -> None:
        t1 = _table("T1", [_col("ID")], fks=[self._fk("FK_T1_T2", "T2")])
        t2 = _table("T2", [_col("ID")], fks=[self._fk("FK_T2_T1", "T1")])
        ordered, circular = _topological_sort([t1, t2])
        assert len(ordered) == 2
        assert len(circular) > 0
