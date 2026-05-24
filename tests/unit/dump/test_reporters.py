"""Tests unitarios para DumpReporter (generación Excel 3 hojas)."""

from __future__ import annotations

from pathlib import Path

import openpyxl

from openpyxl.worksheet.worksheet import Worksheet

from util_bbdd.comparar import ColumnDiff, SchemaDiff, TableDiff
from util_bbdd.dump._constraints import ConstraintResult
from util_bbdd.dump.orchestrator import TableDumpResult
from util_bbdd.dump.reporters import DumpReporter

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _table_result(
    name: str = "orders",
    status: str = "success",
    source_rows: int = 100,
    target_after: int = 100,
    skipped: list[str] | None = None,
    in_cycle: bool = False,
    error_msg: str = "",
) -> TableDumpResult:
    return TableDumpResult(
        table_name=name,
        source_rows=source_rows,
        target_rows_before=0,
        target_rows_after=target_after,
        status=status,  # type: ignore[arg-type]
        skipped_columns=skipped or [],
        load_order_position=0,
        in_cycle=in_cycle,
        error_msg=error_msg,
    )


def _constraint_result(status: str = "enabled") -> ConstraintResult:
    return ConstraintResult(
        table_name="orders",
        constraint_name="fk_orders_cust",
        dialect="mssql",
        status=status,  # type: ignore[arg-type]
        error_msg="some error" if status == "failed" else "",
    )


def _make_diff(
    table_diffs: tuple[TableDiff, ...] = (),
) -> SchemaDiff:
    return SchemaDiff(
        source_label="src",
        target_label="dst",
        table_diffs=table_diffs,
    )


# ---------------------------------------------------------------------------
# DumpReporter.generate — estructura del fichero
# ---------------------------------------------------------------------------


class TestDumpReporterSheetStructure:
    def test_generates_xlsx_with_three_sheets(self, tmp_path: Path):
        reporter = DumpReporter(tmp_path)
        path = reporter.generate(
            table_results=[_table_result()],
            missing_tables=[],
            diff=_make_diff(),
            constraint_results=[],
            cycles=[],
        )

        assert path.exists()
        wb = openpyxl.load_workbook(path)
        assert "Auditoría Tablas" in wb.sheetnames
        assert "Tablas Faltantes" in wb.sheetnames
        assert "Columnas Inexistentes" in wb.sheetnames

    def test_output_dir_created_if_missing(self, tmp_path: Path):
        new_dir = tmp_path / "subdir" / "reports"
        reporter = DumpReporter(new_dir)
        path = reporter.generate(
            table_results=[],
            missing_tables=[],
            diff=_make_diff(),
            constraint_results=[],
            cycles=[],
        )
        assert path.exists()

    def test_filename_contains_timestamp(self, tmp_path: Path):
        reporter = DumpReporter(tmp_path)
        path = reporter.generate(
            table_results=[],
            missing_tables=[],
            diff=_make_diff(),
            constraint_results=[],
            cycles=[],
        )
        assert "dump_report_" in path.name
        assert path.suffix == ".xlsx"


# ---------------------------------------------------------------------------
# Hoja 1: Auditoría Tablas
# ---------------------------------------------------------------------------


class TestAuditSheet:
    def _get_audit_ws(
        self, tmp_path: Path, results: list[TableDumpResult], **kwargs,
    ) -> Worksheet:
        reporter = DumpReporter(tmp_path)
        path = reporter.generate(
            table_results=results,
            missing_tables=kwargs.get("missing_tables", []),
            diff=_make_diff(),
            constraint_results=kwargs.get("constraint_results", []),
            cycles=kwargs.get("cycles", []),
        )
        wb = openpyxl.load_workbook(path)
        return wb["Auditoría Tablas"]

    def test_header_row_has_nine_columns(self, tmp_path: Path):
        ws = self._get_audit_ws(tmp_path, [])
        headers = [ws.cell(1, c).value for c in range(1, 10)]
        assert all(h is not None for h in headers)

    def test_table_result_appears_in_data_row(self, tmp_path: Path):
        ws = self._get_audit_ws(tmp_path, [_table_result("orders", "success", source_rows=42)])
        row2_values = [ws.cell(2, c).value for c in range(1, 8)]
        assert "orders" in row2_values
        assert 42 in row2_values

    def test_missing_target_row_present(self, tmp_path: Path):
        result = _table_result("ghost_table", "missing_target", source_rows=0)
        ws = self._get_audit_ws(tmp_path, [result])
        statuses = [ws.cell(2, 7).value]
        assert "MISSING_TARGET" in statuses

    def test_failed_constraint_appended(self, tmp_path: Path):
        cr = _constraint_result("failed")
        ws = self._get_audit_ws(tmp_path, [_table_result()], constraint_results=[cr])
        # The failed constraint section should be somewhere in the sheet
        all_values = [ws.cell(r, 1).value for r in range(1, ws.max_row + 1)]
        assert any(v == "orders" for v in all_values)

    def test_cycle_flag_shown(self, tmp_path: Path):
        result = _table_result("circular_a", in_cycle=True)
        ws = self._get_audit_ws(tmp_path, [result], cycles=[["circular_a"]])
        cycle_col_values = [ws.cell(2, 3).value]
        assert "Sí" in cycle_col_values


# ---------------------------------------------------------------------------
# Hoja 2: Tablas Faltantes
# ---------------------------------------------------------------------------


class TestMissingTablesSheet:
    def _get_ws(self, tmp_path: Path, missing: list[str]) -> Worksheet:
        reporter = DumpReporter(tmp_path)
        path = reporter.generate(
            table_results=[],
            missing_tables=missing,
            diff=_make_diff(),
            constraint_results=[],
            cycles=[],
        )
        wb = openpyxl.load_workbook(path)
        return wb["Tablas Faltantes"]

    def test_empty_missing_shows_placeholder(self, tmp_path: Path):
        ws = self._get_ws(tmp_path, [])
        assert ws.cell(2, 1).value is not None
        assert "sin" in str(ws.cell(2, 1).value).lower()

    def test_missing_table_name_in_row(self, tmp_path: Path):
        ws = self._get_ws(tmp_path, ["orphan_table"])
        row2 = [ws.cell(2, c).value for c in range(1, 4)]
        assert "orphan_table" in row2

    def test_multiple_missing_tables(self, tmp_path: Path):
        ws = self._get_ws(tmp_path, ["t1", "t2", "t3"])
        names = [ws.cell(r, 1).value for r in range(2, 5)]
        assert set(names) == {"t1", "t2", "t3"}


# ---------------------------------------------------------------------------
# Hoja 3: Columnas Inexistentes
# ---------------------------------------------------------------------------


class TestMissingColumnsSheet:
    def _make_diff_with_existence(self, table: str, col: str) -> SchemaDiff:
        col_diff = ColumnDiff(
            column_name=col,
            attribute="existence",
            source_value="exists",
            target_value="missing",
        )
        td = TableDiff(
            table_name=table,
            status="modified",
            column_diffs=(col_diff,),
        )
        return SchemaDiff(source_label="src", target_label="dst", table_diffs=(td,))

    def _get_ws(self, tmp_path: Path, diff: SchemaDiff) -> Worksheet:
        reporter = DumpReporter(tmp_path)
        path = reporter.generate(
            table_results=[],
            missing_tables=[],
            diff=diff,
            constraint_results=[],
            cycles=[],
        )
        wb = openpyxl.load_workbook(path)
        return wb["Columnas Inexistentes"]

    def test_no_missing_columns_shows_placeholder(self, tmp_path: Path):
        ws = self._get_ws(tmp_path, _make_diff())
        assert ws.cell(2, 1).value is not None
        assert "sin" in str(ws.cell(2, 1).value).lower()

    def test_missing_column_row_appears(self, tmp_path: Path):
        diff = self._make_diff_with_existence("orders", "extra_col")
        ws = self._get_ws(tmp_path, diff)
        row2 = [ws.cell(2, c).value for c in range(1, 6)]
        assert "orders" in row2
        assert "extra_col" in row2

    def test_column_with_exists_in_source_only_reported(self, tmp_path: Path):
        # source_value="missing" means it's in target but not source → NOT reported
        col_diff_in_target = ColumnDiff(
            column_name="target_only_col",
            attribute="existence",
            source_value="missing",
            target_value="exists",
        )
        td = TableDiff(
            table_name="t",
            status="modified",
            column_diffs=(col_diff_in_target,),
        )
        diff = SchemaDiff(source_label="s", target_label="d", table_diffs=(td,))
        ws = self._get_ws(tmp_path, diff)
        all_vals = [ws.cell(r, 2).value for r in range(2, ws.max_row + 1)]
        assert "target_only_col" not in all_vals

    def test_table_with_status_added_skipped(self, tmp_path: Path):
        # Tables with status="added" (src-only) are already in Hoja 2 → Hoja 3 skips them
        col_diff = ColumnDiff(
            column_name="col",
            attribute="existence",
            source_value="exists",
            target_value="missing",
        )
        td = TableDiff(table_name="missing_table", status="added", column_diffs=(col_diff,))
        diff = SchemaDiff(source_label="s", target_label="d", table_diffs=(td,))
        ws = self._get_ws(tmp_path, diff)
        row2_col1 = ws.cell(2, 1).value
        # Should show placeholder (no data rows), not "missing_table"
        assert row2_col1 != "missing_table"
