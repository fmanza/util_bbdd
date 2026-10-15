"""Sección «Condiciones del motor»: del informe de ``EngineReadinessAdvisor`` a filas neutras para los renderers."""

from __future__ import annotations

from datetime import UTC
from typing import ClassVar

from ...domain.models import EngineConditionsSection
from ..ports import EngineConditionsPort, EngineReadinessReportView


class EngineConditionsSectionBuilder:
    """Prepara la sección una sola vez para Word, Excel y HTML (orden, recuentos, metadatos y avisos)."""

    #: Cabeceras por defecto; ``headers_config.json`` puede cambiarlas con la clave ``CONDICIONES_MOTOR``.
    DEFAULT_HEADERS: ClassVar[tuple[str, ...]] = ("Nivel", "Parámetro", "Valor actual", "Recomendación")
    LEVELS: ClassVar[tuple[str, ...]] = ("CRITICAL", "WARNING", "INFO", "OK")

    NOTICE_UNAVAILABLE: ClassVar[str] = (
        "La verificación de las condiciones del motor no está disponible para este origen."
    )
    NOTICE_NO_FINDINGS: ClassVar[str] = "La verificación no ha producido hallazgos."

    def __init__(self, headers: list[str] | tuple[str, ...] | None = None) -> None:
        # Las filas tienen 4 columnas: otras cabeceras recortarían columnas (Word, Excel) o las dejarían sin título (HTML)
        custom = tuple(headers or ())
        self._headers: tuple[str, ...] = custom if len(custom) == len(self.DEFAULT_HEADERS) else self.DEFAULT_HEADERS

    def build(self, report: EngineReadinessReportView | None) -> EngineConditionsSection:
        """Sección a partir del informe; ``None`` (origen sin verificación) da una sección con el aviso."""
        if report is None:
            return self.unavailable(self.NOTICE_UNAVAILABLE)

        level_rank = {level: rank for rank, level in enumerate(self.LEVELS)}
        rows = tuple(
            sorted(
                ((f.level, f.param, f.current, f.recommendation) for f in report.findings),
                key=lambda row: (level_rank.get(row[0], len(self.LEVELS)), row[0], row[1]),
            )
        )
        counts: dict[str, int] = {}
        for row in rows:
            counts[row[0]] = counts.get(row[0], 0) + 1
        summary = tuple((level, counts.get(level, 0)) for level in self.LEVELS) + tuple(
            (level, count) for level, count in counts.items() if level not in level_rank
        )

        notices: list[str] = []
        if not report.supported:
            notices.append(f"El motor '{report.db_type}' no tiene verificaciones de condiciones de ejecución.")
        else:
            if not report.dynamic:
                reason = f": {report.error}" if report.error else ""
                notices.append(
                    f"Solo checks estáticos (configuración de conexión), sin variables del servidor{reason}."
                )
            if not rows:
                notices.append(self.NOTICE_NO_FINDINGS)

        checked_at = report.checked_at.astimezone(UTC) if report.checked_at.tzinfo else report.checked_at
        metadata = (
            ("Motor", report.db_type),
            ("Verificado (UTC)", checked_at.strftime("%Y-%m-%d %H:%M:%S")),
            ("Checks dinámicos", "Sí" if report.dynamic else "No"),
        )
        return EngineConditionsSection(
            headers=self._headers, rows=rows, summary=summary, metadata=metadata, notices=tuple(notices)
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
