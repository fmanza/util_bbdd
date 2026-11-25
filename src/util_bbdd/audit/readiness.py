"""Hoja «Condiciones del motor» de los Excel de auditoría de ``bulk`` y ``dump`` (``EngineReadinessAdvisor``).

Capa 3 (Regla #6): no importa ``connection``. El informe llega por el contrato estructural :class:`ReadinessReportView`
(lo cumple ``util_bbdd.connection.EngineReadinessReport``) y la hoja se escribe sobre cualquier ``Worksheet`` de
openpyxl: la de ``SafeWorkbook`` (``dump``) o la del ``pd.ExcelWriter`` del resumen de ``bulk``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar, Protocol

from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from .._core.export_safety import neutralize_formulas, safe_value
from .._core.i18n import Translator

_ES = Translator()


class ReadinessFindingView(Protocol):
    """Un hallazgo de la verificación (lo cumple ``util_bbdd.connection.AdvisoryFinding``)."""

    @property
    def level(self) -> str: ...

    @property
    def param(self) -> str: ...

    @property
    def current(self) -> str: ...

    @property
    def recommendation(self) -> str: ...


class ReadinessReportView(Protocol):
    """Informe de la verificación (lo cumple ``util_bbdd.connection.EngineReadinessReport``)."""

    @property
    def db_type(self) -> str: ...

    @property
    def findings(self) -> Sequence[ReadinessFindingView]: ...

    @property
    def checked_at(self) -> datetime: ...

    @property
    def dynamic(self) -> bool: ...

    @property
    def supported(self) -> bool: ...

    @property
    def error(self) -> str | None: ...


#: (título del bloque, informe); ``None`` si no se pudo verificar ese motor.
ReadinessBlock = tuple[str, ReadinessReportView | None]


@dataclass(frozen=True, slots=True)
class ReadinessRows:
    """Contenido de un bloque: hallazgos ordenados, resumen, verificación y avisos.

    Única fuente de esos textos: la usan las hojas de los Excel de ``bulk`` y ``dump`` y la sección «Condiciones del
    motor» de ``doc`` (Word, Excel y HTML). Cambiar un texto aquí cambia todas esas salidas.
    """

    LEVELS: ClassVar[tuple[str, ...]] = ("CRITICAL", "WARNING", "INFO", "OK")
    #: Avisos en español (el idioma por defecto); ``from_report`` usa los del ``translator`` que reciba.
    NOTICE_UNAVAILABLE: ClassVar[str] = _ES.t("audit.readiness.notice.unavailable")
    NOTICE_NO_FINDINGS: ClassVar[str] = _ES.t("audit.readiness.notice.no_findings")

    rows: tuple[tuple[str, str, str, str], ...]
    summary: tuple[tuple[str, int], ...]
    metadata: tuple[tuple[str, str], ...]
    notices: tuple[str, ...]

    @classmethod
    def from_report(cls, report: ReadinessReportView | None, translator: Translator = _ES) -> ReadinessRows:
        """Filas del bloque; ``None`` da un bloque solo con el aviso. Los textos salen en el idioma de ``translator``."""
        tr = translator
        if report is None:
            return cls(rows=(), summary=(), metadata=(), notices=(tr.t("audit.readiness.notice.unavailable"),))

        rank = {level: position for position, level in enumerate(cls.LEVELS)}
        rows = tuple(
            sorted(
                ((f.level, f.param, f.current, f.recommendation) for f in report.findings),
                key=lambda row: (rank.get(row[0], len(cls.LEVELS)), row[0], row[1]),
            )
        )
        counts: dict[str, int] = {}
        for row in rows:
            counts[row[0]] = counts.get(row[0], 0) + 1
        summary = tuple((level, counts.get(level, 0)) for level in cls.LEVELS) + tuple(
            (level, count) for level, count in counts.items() if level not in rank
        )

        notices: list[str] = []
        if not report.supported:
            notices.append(tr.t("audit.readiness.notice.unsupported", db_type=report.db_type))
        else:
            if not report.dynamic:
                reason = f": {report.error}" if report.error else ""
                notices.append(tr.t("audit.readiness.notice.static_only", reason=reason))
            if not rows:
                notices.append(tr.t("audit.readiness.notice.no_findings"))

        checked_at = report.checked_at.astimezone(UTC) if report.checked_at.tzinfo else report.checked_at
        metadata = (
            (tr.t("audit.readiness.meta.engine"), report.db_type),
            (tr.t("audit.readiness.meta.checked_at"), checked_at.strftime("%Y-%m-%d %H:%M:%S")),
            (tr.t("audit.readiness.meta.dynamic"), tr.t("audit.yes") if report.dynamic else tr.t("audit.no")),
        )
        return cls(rows=rows, summary=summary, metadata=metadata, notices=tuple(notices))


class ReadinessSheetWriter:
    """Escribe los bloques de condiciones del motor en una hoja, uno debajo de otro, en el idioma de ``translator``."""

    #: Cabeceras y nota en español (el idioma por defecto); la hoja usa las del ``translator`` de la instancia.
    HEADERS: ClassVar[tuple[str, ...]] = tuple(
        _ES.t(f"audit.readiness.header.{key}") for key in ("level", "param", "current", "recommendation")
    )
    NOTE: ClassVar[str] = _ES.t("audit.readiness.note")
    _HEADER_FILL: ClassVar[str] = "FF4472C4"
    _LEVEL_FILL: ClassVar[dict[str, str]] = {
        "CRITICAL": "FFFF0000",
        "WARNING": "FFFFC000",
        "INFO": "FFDDEBF7",
        "OK": "FF92D050",
    }

    def __init__(self, translator: Translator = _ES) -> None:
        self._tr: Translator = translator
        self._headers: tuple[str, ...] = tuple(
            translator.t(f"audit.readiness.header.{key}") for key in ("level", "param", "current", "recommendation")
        )

    def write(self, ws: Worksheet, blocks: Sequence[ReadinessBlock]) -> None:
        """Escribe ``blocks`` en ``ws`` y guarda como texto lo que parezca fórmula."""
        title = ws.cell(row=1, column=1, value=self._tr.t("audit.readiness.title"))
        title.font = Font(size=14, bold=True)
        ws.cell(row=2, column=1, value=self._tr.t("audit.readiness.note")).font = Font(italic=True)

        row = 4
        for block_title, report in blocks:
            row = self._write_block(ws, row, block_title, ReadinessRows.from_report(report, self._tr)) + 1

        for column in range(1, len(self._headers) + 1):
            ws.column_dimensions[get_column_letter(column)].width = (20, 34, 24, 80)[column - 1]
        neutralize_formulas(ws)

    def _write_block(self, ws: Worksheet, row: int, title: str, content: ReadinessRows) -> int:
        """Escribe un bloque desde ``row``; devuelve la fila siguiente."""
        ws.cell(row=row, column=1, value=safe_value(title)).font = Font(size=12, bold=True)
        row += 1
        for notice in content.notices:
            ws.cell(row=row, column=1, value=safe_value(f"⚠️ {notice}")).font = Font(italic=True)
            row += 1

        if content.metadata:
            headers = (self._tr.t("audit.readiness.header.property"), self._tr.t("audit.readiness.header.value"))
            row = self._write_table(ws, row, headers, content.metadata)
        if content.summary:
            headers = (self._tr.t("audit.readiness.header.level"), self._tr.t("audit.readiness.header.findings"))
            row = self._write_table(ws, row, headers, content.summary, level_column=True)
        if content.rows:
            row = self._write_table(ws, row, self._headers, content.rows, level_column=True)
        return row

    def _write_table(
        self,
        ws: Worksheet,
        row: int,
        headers: Sequence[str],
        rows: Sequence[Sequence[str | int]],
        *,
        level_column: bool = False,
    ) -> int:
        """Cabecera con estilo y filas; la primera columna se colorea por nivel si ``level_column``."""
        for column, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=column, value=header)
            cell.font = Font(bold=True, color="FFFFFFFF")
            cell.fill = PatternFill("solid", fgColor=self._HEADER_FILL)
            cell.alignment = Alignment(horizontal="center")
        row += 1
        for values in rows:
            for column, value in enumerate(values, 1):
                ws.cell(row=row, column=column, value=safe_value(value))
            fill = self._LEVEL_FILL.get(str(values[0])) if level_column else None
            if fill:
                ws.cell(row=row, column=1).fill = PatternFill("solid", fgColor=fill)
            row += 1
        return row + 1


__all__: list[str] = [
    "ReadinessBlock",
    "ReadinessFindingView",
    "ReadinessReportView",
    "ReadinessRows",
    "ReadinessSheetWriter",
]
