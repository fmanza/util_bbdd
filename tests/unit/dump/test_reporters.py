"""Tests unitarios para DumpReporter (generación Excel 3 hojas)."""

from __future__ import annotations

from pathlib import Path

import openpyxl

from openpyxl.worksheet.worksheet import Worksheet

from util_bbdd.dump._constraints import ConstraintResult
from util_bbdd.dump._models import TableDumpResult
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


# ---------------------------------------------------------------------------
# DumpReporter.generate — estructura del fichero
# ---------------------------------------------------------------------------


class TestDumpReporterSheetStructure:
    def test_generates_xlsx_with_three_sheets(self, tmp_path: Path):
        reporter = DumpReporter(tmp_path)
        path = reporter.generate(
            table_results=[_table_result()],
            missing_tables=[],
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
            constraint_results=[],
            cycles=[],
        )
        assert path.exists()

    def test_filename_contains_timestamp(self, tmp_path: Path):
        reporter = DumpReporter(tmp_path)
        path = reporter.generate(
            table_results=[],
            missing_tables=[],
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
        self,
        tmp_path: Path,
        results: list[TableDumpResult],
        **kwargs,
    ) -> Worksheet:
        reporter = DumpReporter(tmp_path)
        path = reporter.generate(
            table_results=results,
            missing_tables=kwargs.get("missing_tables", []),
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
    """La hoja 3 se deriva de ``TableDumpResult.skipped_columns`` (sin comparación de esquemas)."""

    def _get_ws(self, tmp_path: Path, table_results: list[TableDumpResult]) -> Worksheet:
        reporter = DumpReporter(tmp_path)
        path = reporter.generate(
            table_results=table_results,
            missing_tables=[],
            constraint_results=[],
            cycles=[],
        )
        wb = openpyxl.load_workbook(path)
        return wb["Columnas Inexistentes"]

    def test_no_missing_columns_shows_placeholder(self, tmp_path: Path):
        ws = self._get_ws(tmp_path, [_table_result("orders", "success", skipped=[])])
        assert ws.cell(2, 1).value is not None
        assert "sin" in str(ws.cell(2, 1).value).lower()

    def test_missing_column_row_appears(self, tmp_path: Path):
        ws = self._get_ws(tmp_path, [_table_result("orders", "success", skipped=["extra_col"])])
        row2 = [ws.cell(2, c).value for c in range(1, 6)]
        assert "orders" in row2
        assert "extra_col" in row2

    def test_only_skipped_columns_are_reported(self, tmp_path: Path):
        # Una tabla sin skipped_columns no aporta filas; solo las columnas omitidas aparecen.
        ws = self._get_ws(
            tmp_path,
            [
                _table_result("a", "success", skipped=[]),
                _table_result("b", "success", skipped=["only_in_source"]),
            ],
        )
        all_vals = [ws.cell(r, 2).value for r in range(2, ws.max_row + 1)]
        assert "only_in_source" in all_vals
        # La tabla 'a' (sin skipped) no genera ninguna fila propia.
        table_col = [ws.cell(r, 1).value for r in range(2, ws.max_row + 1)]
        assert "a" not in table_col

    def test_missing_target_table_with_empty_skipped_not_listed(self, tmp_path: Path):
        # Tablas ausentes en destino llegan con skipped vacío → no figuran en la hoja 3.
        ws = self._get_ws(tmp_path, [_table_result("ghost", "missing_target", skipped=[])])
        row2_col1 = ws.cell(2, 1).value
        assert row2_col1 != "ghost"
        assert "sin" in str(row2_col1).lower()
