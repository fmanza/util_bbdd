"""Capa exporters de auditoría: Excel, JSON y HTML."""

from __future__ import annotations

import json
import logging

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from .errors import AuditConfigError, AuditDataError
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
        dataframe["fecha"] = pd.to_datetime(dataframe["timestamp"]).dt.normalize()
        operaciones: list[Any] = dataframe["operacion"].unique().tolist()

        group_cols: list[str] = self.service.determinar_group_cols(agrupar_por)
        output_excel.parent.mkdir(parents=True, exist_ok=True)
        resumen_global: list[pd.DataFrame] = []

        with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
            for op in operaciones:
                dataframe_operacion: pd.DataFrame = dataframe[dataframe["operacion"] == op]
                if dataframe_operacion.empty:
                    continue

                resumen_op = self.service.agrupar_y_generar_resumen(dataframe_operacion, group_cols)
                hoja: str = f"{str(op).capitalize()}_{agrupar_por}"
                resumen_op.to_excel(writer, sheet_name=hoja[:31], index=False)
                resumen_global.append(resumen_op)

            if resumen_global:
                dataframe_global: pd.DataFrame = pd.concat(resumen_global, ignore_index=True)
                if "tabla" in dataframe_global.columns and "fecha" in dataframe_global.columns:
                    dataframe_global = dataframe_global[
                        [
                            "fecha",
                            "tabla",
                            "operacion",
                            "total_filas",
                            "tiempo_total",
                            "lotes",
                            "tiempo_medio",
                        ]
                    ]
                dataframe_global.to_excel(writer, sheet_name="Resumen_global", index=False)

        self.logger.info(f"✅ Resumen de auditoría exportado a: {output_excel}")
        return output_excel

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
            html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Auditoría - {datetime.now().strftime("%Y-%m-%d")}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 3px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; border-left: 4px solid #007bff; padding-left: 10px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; margin: 20px 0; }}
        .stat-box {{ background: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #007bff; }}
        .stat-label {{ font-size: 12px; color: #666; text-transform: uppercase; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #333; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th {{ background-color: #007bff; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        tr:hover {{ background-color: #f0f0f0; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Reporte de Auditoría</h1>
        <p>Generado: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>

        <h2>Estadísticas Generales</h2>
        <div class="stats">
            <div class="stat-box">
                <div class="stat-label">Total Operaciones</div>
                <div class="stat-value">{stats.get("total_operaciones", 0)}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Filas Procesadas</div>
                <div class="stat-value">{stats.get("total_filas_procesadas", 0):,}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Tiempo Total (s)</div>
                <div class="stat-value">{stats.get("tiempo_total_segundos", 0):.2f}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Tiempo Promedio (s)</div>
                <div class="stat-value">{stats.get("tiempo_promedio_segundos", 0):.4f}</div>
            </div>
        </div>

        <h2>Últimas 20 Operaciones</h2>
        {dataframe.tail(20).to_html(classes="audit-table", index=False)}

        <h2>Operaciones por Tipo</h2>
        {pd.DataFrame(self.service.obtener_operaciones_por_tipo().items(), columns=["Operación", "Cantidad"]).to_html(classes="audit-table", index=False)}

        <h2>Operaciones por Tabla</h2>
        {pd.DataFrame(self.service.obtener_operaciones_por_tabla().items(), columns=["Tabla", "Cantidad"]).to_html(classes="audit-table", index=False)}

        <div class="footer">
            <p>Este reporte fue generado automáticamente por AuditManager (Phase 2)</p>
        </div>
    </div>
</body>
</html>"""

            output_html.parent.mkdir(parents=True, exist_ok=True)
            with open(output_html, "w", encoding="utf-8") as file_handle:
                file_handle.write(html_content)

            self.logger.info(f"✅ Auditoría exportada a HTML: {output_html}")
            return output_html
        except Exception as error:
            raise AuditDataError(f"❌ Error al exportar HTML: {error}") from error


__all__: list[str] = ["AuditExporters"]
