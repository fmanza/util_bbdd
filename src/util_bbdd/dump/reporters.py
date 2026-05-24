"""Generador del informe Excel de auditoría para volcados de datos.

Genera un único fichero ``.xlsx`` con tres hojas:
  - ``Auditoría Tablas``: volumetría origen vs. destino por tabla.
  - ``Tablas Faltantes``: tablas del origen sin correspondencia en destino.
  - ``Columnas Inexistentes``: columnas presentes en origen pero ausentes en destino.
"""

from __future__ import annotations

import logging

from datetime import datetime
from pathlib import Path

import openpyxl

from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from util_bbdd.comparar import SchemaDiff

from ._constraints import ConstraintResult
from .orchestrator import TableDumpResult

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paleta de colores (ARGB)
# ---------------------------------------------------------------------------

_COL_HEADER_BLUE = "FF4472C4"
_COL_HEADER_ORANGE = "FFED7D31"
_COL_GREEN = "FF92D050"
_COL_RED = "FFFF0000"
_COL_YELLOW = "FFFFFF00"
_COL_ORANGE = "FFFFC000"
_COL_LIGHT_BLUE = "FFDCE6F1"
_COL_LIGHT_ORANGE = "FFFCE4D6"
_COL_WHITE_FONT = "FFFFFFFF"

_STATUS_BG: dict[str, str] = {
    "success": _COL_GREEN,
    "error": _COL_RED,
    "skipped": _COL_YELLOW,
    "missing_target": _COL_ORANGE,
    "enabled": _COL_GREEN,
    "failed": _COL_RED,
    "unverified": _COL_YELLOW,
}


# ---------------------------------------------------------------------------
# Helpers de escritura
# ---------------------------------------------------------------------------


def _header(ws: Worksheet, row: int, col: int, value: str, color: str = _COL_HEADER_BLUE) -> None:
    cell = ws.cell(row=row, column=col, value=value)
    cell.font = Font(bold=True, color=_COL_WHITE_FONT)
    cell.fill = PatternFill("solid", fgColor=color)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _cell(ws: Worksheet, row: int, col: int, value: str | int | float | bool | None, bg: str | None = None) -> None:
    cell = ws.cell(row=row, column=col, value=value)
    cell.alignment = Alignment(vertical="center", wrap_text=False)
    if bg:
        cell.fill = PatternFill("solid", fgColor=bg)


def _autowidth(ws: Worksheet) -> None:
    for col_cells in ws.columns:
        width = max((len(str(c.value or "")) for c in col_cells), default=8)
        ws.column_dimensions[get_column_letter(col_cells[0].column or 1)].width = min(width + 4, 65)


def _write_audit_rows(ws: Worksheet, table_results: list[TableDumpResult], cycle_set: set[str]) -> None:
    for row, res in enumerate(table_results, 2):
        bg = _STATUS_BG.get(res.status)
        pos = str(res.load_order_position) if res.load_order_position >= 0 else "—"
        _cell(ws, row, 1, res.table_name)
        _cell(ws, row, 2, pos)
        _cell(ws, row, 3, "Sí" if res.table_name in cycle_set else "No")
        _cell(ws, row, 4, res.source_rows if res.source_rows >= 0 else "—")
        _cell(ws, row, 5, res.target_rows_before if res.target_rows_before >= 0 else "—")
        _cell(ws, row, 6, res.target_rows_after if res.target_rows_after >= 0 else "—")
        _cell(ws, row, 7, res.status.upper(), bg=bg)
        _cell(ws, row, 8, ", ".join(res.skipped_columns) if res.skipped_columns else "—")
        _cell(ws, row, 9, res.error_msg or "—")


def _write_constraint_section(
    ws: Worksheet,
    constraint_results: list[ConstraintResult],
    table_count: int,
) -> None:
    failed = [r for r in constraint_results if r.status in ("failed", "unverified")]
    if not failed:
        return
    offset = table_count + 4
    _header(ws, offset, 1, "Constraints con incidencia al rehabilitar", color=_COL_HEADER_ORANGE)
    for col, h in enumerate(["Tabla", "Constraint", "Dialect", "Estado", "Mensaje"], 2):
        _header(ws, offset, col, h, color=_COL_HEADER_ORANGE)
    for i, cr in enumerate(failed, offset + 1):
        _cell(ws, i, 1, cr.table_name)
        _cell(ws, i, 2, cr.constraint_name)
        _cell(ws, i, 3, cr.dialect)
        _cell(ws, i, 4, cr.status.upper(), bg=_STATUS_BG.get(cr.status))
        _cell(ws, i, 5, cr.error_msg or "—")


# ---------------------------------------------------------------------------
# Reporter principal
# ---------------------------------------------------------------------------


class DumpReporter:
    """Genera el informe Excel de auditoría de un volcado de datos."""

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def generate(
        self,
        table_results: list[TableDumpResult],
        missing_tables: list[str],
        diff: SchemaDiff,
        constraint_results: list[ConstraintResult],
        cycles: list[list[str]],
    ) -> Path:
        """Genera el fichero Excel y retorna su ruta.

        Args:
            table_results: Resultado por tabla volcada.
            missing_tables: Tablas del origen que no existen en el destino.
            diff: Diferencias de esquema (fuente para columnas inexistentes).
            constraint_results: Resultados de rehabilitación de constraints.
            cycles: Grupos de tablas con FK circular.
        """
        self._output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self._output_dir / f"dump_report_{ts}.xlsx"

        wb = openpyxl.Workbook()
        if wb.active is not None:
            wb.remove(wb.active)

        self._sheet_audit(wb, table_results, constraint_results, cycles)
        self._sheet_missing_tables(wb, missing_tables)
        self._sheet_missing_columns(wb, diff)

        wb.save(output_path)
        _log.info("Informe Excel guardado en '%s'.", output_path)
        return output_path

    # ------------------------------------------------------------------
    # Hoja 1: Auditoría de tablas
    # ------------------------------------------------------------------

    def _sheet_audit(
        self,
        wb: openpyxl.Workbook,
        table_results: list[TableDumpResult],
        constraint_results: list[ConstraintResult],
        cycles: list[list[str]],
    ) -> None:
        ws: Worksheet = wb.create_sheet("Auditoría Tablas")

        headers = [
            "Tabla",
            "Posición Carga",
            "FK Circular",
            "Filas Origen",
            "Filas Destino Antes",
            "Filas Destino Después",
            "Estado",
            "Columnas Omitidas",
            "Error",
        ]
        for col, h in enumerate(headers, 1):
            _header(ws, 1, col, h)
        ws.row_dimensions[1].height = 30
        ws.freeze_panes = "A2"

        cycle_set = {t for group in cycles for t in group}
        _write_audit_rows(ws, table_results, cycle_set)
        _write_constraint_section(ws, constraint_results, len(table_results))
        _autowidth(ws)

    # ------------------------------------------------------------------
    # Hoja 2: Tablas faltantes en destino
    # ------------------------------------------------------------------

    def _sheet_missing_tables(
        self,
        wb: openpyxl.Workbook,
        missing_tables: list[str],
    ) -> None:
        ws: Worksheet = wb.create_sheet("Tablas Faltantes")

        headers = ["Tabla Origen", "Motivo", "Acción Sugerida"]
        for col, h in enumerate(headers, 1):
            _header(ws, 1, col, h, color=_COL_HEADER_ORANGE)
        ws.freeze_panes = "A2"

        if not missing_tables:
            cell = ws.cell(row=2, column=1, value="Sin tablas faltantes en destino")
            cell.font = Font(italic=True)
        else:
            for row, table in enumerate(missing_tables, 2):
                _cell(ws, row, 1, table, bg=_COL_LIGHT_ORANGE)
                _cell(ws, row, 2, "La tabla no existe en la BD destino")
                _cell(ws, row, 3, "Crear la tabla en destino con el DDL del origen antes de reintentar")

        _autowidth(ws)

    # ------------------------------------------------------------------
    # Hoja 3: Columnas inexistentes en destino
    # ------------------------------------------------------------------

    def _sheet_missing_columns(
        self,
        wb: openpyxl.Workbook,
        diff: SchemaDiff,
    ) -> None:
        ws: Worksheet = wb.create_sheet("Columnas Inexistentes")

        headers = [
            "Tabla",
            "Columna Origen",
            "Valor/Tipo en Origen",
            "Estado en Destino",
            "Acción Sugerida",
        ]
        for col, h in enumerate(headers, 1):
            _header(ws, 1, col, h, color=_COL_HEADER_ORANGE)
        ws.freeze_panes = "A2"

        row = 2
        for td in diff.table_diffs:
            # Tablas completamente faltantes ya están en Hoja 2
            if td.status == "added":
                continue
            for cd in td.column_diffs:
                # Columna en origen, ausente en destino
                if cd.attribute == "existence" and cd.source_value == "exists":
                    _cell(ws, row, 1, td.table_name)
                    _cell(ws, row, 2, cd.column_name, bg=_COL_YELLOW)
                    _cell(ws, row, 3, cd.source_value)
                    _cell(ws, row, 4, "Columna ausente en BD destino")
                    _cell(ws, row, 5, "Columna omitida del volcado — añadir DDL al destino si se requiere")
                    row += 1

        if row == 2:
            cell = ws.cell(row=2, column=1, value="Sin columnas inexistentes en destino")
            cell.font = Font(italic=True)

        _autowidth(ws)
