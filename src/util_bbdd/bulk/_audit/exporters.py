"""Capa exporters de auditoría: Excel, JSON y HTML."""

from __future__ import annotations

import json
import logging

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from .._support.excel import neutralize_formulas as _desactivar_formulas, safe_frame
from .errors import AuditConfigError, AuditDataError, AuditExportError
from .html_template import AUDIT_HTML_TEMPLATE
from .repository import AuditCsvRepository
from .service import AuditAnalyticsService


class AuditExporters:
    """Genera reportes de auditoría en formatos de salida."""

    def __init__(
        self,
        *,
        repository: AuditCsvRepository,
        service: AuditAnalyticsService,
        logger: logging.Logger,
        error_audit_path_required: str,
    ) -> None:
        self.repository: AuditCsvRepository = repository
        self.service: AuditAnalyticsService = service
        self.logger: logging.Logger = logger
        self.error_audit_path_required: str = error_audit_path_required

    def exportar_resumen_excel(self, agrupar_por: Literal["tabla", "fecha", "tabla_fecha"] = "tabla") -> Path:
        """Exporta resumen de auditoría a Excel."""
        if self.repository.audit_csv_path is None:
            raise AuditConfigError(self.error_audit_path_required)

        output_excel: Path = self.repository.audit_csv_path.parent / "auditoria.xlsx"
        dataframe: pd.DataFrame = self.repository.leer_auditoria()

        columnas_faltantes: set[str] = set(self.repository.columnas_auditoria) - set(dataframe.columns)
        if columnas_faltantes:
            raise AuditDataError(f"❌ El CSV no contiene las columnas requeridas: {', '.join(columnas_faltantes)}")

        dataframe["tiempo_seg"] = dataframe["tiempo_seg"].astype(str).str.replace(",", ".").astype(float)
        dataframe["fecha"] = pd.to_datetime(dataframe["timestamp"], format="mixed").dt.normalize()
        operaciones: list[Any] = dataframe["operacion"].unique().tolist()

        group_cols: list[str] = self.service.determinar_group_cols(agrupar_por)
        try:
            output_excel.parent.mkdir(parents=True, exist_ok=True)
            self._escribir_excel(output_excel, dataframe, operaciones, group_cols, agrupar_por)
        except OSError as error:
            # p.ej. auditoria.xlsx abierto en Excel (PermissionError). AuditExportError es también OSError.
            raise AuditExportError(f"❌ Error al exportar Excel '{output_excel}': {error}") from error

        self.logger.info(f"✅ Resumen de auditoría exportado a: {output_excel}")
        return output_excel

    def _escribir_excel(
        self,
        output_excel: Path,
        dataframe: pd.DataFrame,
        operaciones: list[Any],
        group_cols: list[str],
        agrupar_por: str,
    ) -> None:
        """Escribe una hoja por operación y ``Resumen_global`` en ``output_excel``."""
        resumen_global: list[pd.DataFrame] = []

        with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
            for op in operaciones:
                dataframe_operacion: pd.DataFrame = dataframe[dataframe["operacion"] == op]
                if dataframe_operacion.empty:
                    continue

                resumen_op = self.service.agrupar_y_generar_resumen(dataframe_operacion, group_cols)
                hoja: str = f"{str(op).capitalize()}_{agrupar_por}"[:31]
                safe_frame(resumen_op).to_excel(writer, sheet_name=hoja, index=False)
                _desactivar_formulas(writer.sheets[hoja])
                resumen_global.append(resumen_op)

            if resumen_global:
                dataframe_global: pd.DataFrame = pd.concat(resumen_global, ignore_index=True)
                if "tabla" in dataframe_global.columns and "fecha" in dataframe_global.columns:
                    dataframe_global = dataframe_global[
                        [
                            "fecha",
                            "tabla",
                            "operacion",
                            "sql",
                            "total_filas",
                            "tiempo_total",
                            "lotes",
                            "tiempo_medio",
                        ]
                    ]
                safe_frame(dataframe_global).to_excel(writer, sheet_name="Resumen_global", index=False)
                _desactivar_formulas(writer.sheets["Resumen_global"])

    def exportar_resumen_json(self, output_path: Path | None = None) -> Path:
        """Exporta resumen de auditoría a JSON."""
        if self.repository.audit_csv_path is None:
            raise AuditConfigError(self.error_audit_path_required)

        dataframe: pd.DataFrame = self.repository.leer_auditoria()
        output_json: Path = output_path or self.repository.audit_csv_path.parent / "auditoria.json"

        try:
            stats = self.service.obtener_estadisticas()
            operaciones = self.service.obtener_operaciones_por_tipo()
            tablas = self.service.obtener_operaciones_por_tabla()

            resumen: dict[str, Any] = {
                "fecha_generacion": datetime.now().isoformat(),
                "estadisticas": {
                    key: (value.isoformat() if isinstance(value, (datetime, pd.Timestamp)) else value)
                    for key, value in stats.items()
                },
                "operaciones_por_tipo": operaciones,
                "operaciones_por_tabla": tablas,
                "registros_totales": len(dataframe),
                "periodo": {
                    "inicio": dataframe["timestamp"].min().isoformat() if len(dataframe) > 0 else None,
                    "fin": dataframe["timestamp"].max().isoformat() if len(dataframe) > 0 else None,
                },
            }

            output_json.parent.mkdir(parents=True, exist_ok=True)
            with open(output_json, "w", encoding="utf-8") as file_handle:
                json.dump(resumen, file_handle, indent=2, ensure_ascii=False)

            self.logger.info(f"✅ Auditoría exportada a JSON: {output_json}")
            return output_json
        except Exception as error:
            raise AuditDataError(f"❌ Error al exportar JSON: {error}") from error

    def exportar_resumen_html(self, output_path: Path | None = None) -> Path:
        """Exporta resumen de auditoría a HTML."""
        if self.repository.audit_csv_path is None:
            raise AuditConfigError(self.error_audit_path_required)

        dataframe: pd.DataFrame = self.repository.leer_auditoria()
        output_html: Path = output_path or self.repository.audit_csv_path.parent / "auditoria.html"

        try:
            stats = self.service.obtener_estadisticas()
            now = datetime.now()
            html_content = AUDIT_HTML_TEMPLATE.substitute(
                page_title=now.strftime("%Y-%m-%d"),
                generated_datetime=now.strftime("%Y-%m-%d %H:%M:%S"),
                total_operaciones=stats.get("total_operaciones", 0),
                total_filas=f"{stats.get('total_filas_procesadas', 0):,}",
                tiempo_total=f"{stats.get('tiempo_total_segundos', 0):.2f}",
                tiempo_promedio=f"{stats.get('tiempo_promedio_segundos', 0):.4f}",
                tabla_ultimas_ops=dataframe.tail(20).to_html(classes="audit-table", index=False),
                tabla_por_tipo=pd.DataFrame(
                    self.service.obtener_operaciones_por_tipo().items(),
                    columns=["Operación", "Cantidad"],
                ).to_html(classes="audit-table", index=False),
                tabla_por_tabla=pd.DataFrame(
                    self.service.obtener_operaciones_por_tabla().items(),
                    columns=["Tabla", "Cantidad"],
                ).to_html(classes="audit-table", index=False),
            )

            output_html.parent.mkdir(parents=True, exist_ok=True)
            with open(output_html, "w", encoding="utf-8") as file_handle:
                file_handle.write(html_content)

            self.logger.info(f"✅ Auditoría exportada a HTML: {output_html}")
            return output_html
        except Exception as error:
            raise AuditDataError(f"❌ Error al exportar HTML: {error}") from error


__all__: list[str] = ["AuditExporters"]
