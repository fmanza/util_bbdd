"""Sección «Condiciones del motor»: del informe de ``EngineReadinessAdvisor`` a filas neutras para los renderers."""

from __future__ import annotations

from typing import ClassVar

from ....audit.readiness import ReadinessRows
from ...domain.models import EngineConditionsSection
from ..ports import EngineConditionsPort, EngineReadinessReportView


class EngineConditionsSectionBuilder:
    """Prepara la sección una sola vez para Word, Excel y HTML (orden, recuentos, metadatos y avisos)."""

    #: Cabeceras por defecto; ``headers_config.json`` puede cambiarlas con la clave ``CONDICIONES_MOTOR``.
    DEFAULT_HEADERS: ClassVar[tuple[str, ...]] = ("Nivel", "Parámetro", "Valor actual", "Recomendación")
    LEVELS: ClassVar[tuple[str, ...]] = ReadinessRows.LEVELS

    NOTICE_UNAVAILABLE: ClassVar[str] = (
        "La verificación de las condiciones del motor no está disponible para este origen."
    )
    NOTICE_NO_FINDINGS: ClassVar[str] = ReadinessRows.NOTICE_NO_FINDINGS

    def __init__(self, headers: list[str] | tuple[str, ...] | None = None) -> None:
        # Las filas tienen 4 columnas: otras cabeceras recortarían columnas (Word, Excel) o las dejarían sin título (HTML)
        custom = tuple(headers or ())
        self._headers: tuple[str, ...] = custom if len(custom) == len(self.DEFAULT_HEADERS) else self.DEFAULT_HEADERS

    def build(self, report: EngineReadinessReportView | None) -> EngineConditionsSection:
        """Sección a partir del informe; ``None`` (origen sin verificación) da una sección con el aviso.

        Filas, resumen, verificación y avisos son los de ``audit.readiness.ReadinessRows`` (los mismos que las hojas de
        los Excel de ``bulk`` y ``dump``); ``doc`` solo añade sus cabeceras y su aviso de origen no compatible.
        """
        if report is None:
            return self.unavailable(self.NOTICE_UNAVAILABLE)
        content = ReadinessRows.from_report(report)
        return EngineConditionsSection(
            headers=self._headers,
            rows=content.rows,
            summary=content.summary,
            metadata=content.metadata,
            notices=content.notices,
        )

    @classmethod
    def of(cls, data_provider: object) -> EngineConditionsSection:
        """La sección del ``data_provider`` de un renderer; si no la ofrece (``EngineConditionsPort``), el aviso."""
        if isinstance(data_provider, EngineConditionsPort):
            return data_provider.get_engine_conditions()
        return cls().build(None)

    def unavailable(self, notice: str) -> EngineConditionsSection:
        """Sección sin datos, solo con el aviso que explica por qué."""
        return EngineConditionsSection(headers=self._headers, rows=(), summary=(), metadata=(), notices=(notice,))


__all__: list[str] = ["EngineConditionsSectionBuilder"]
