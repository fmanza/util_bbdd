"""Capa service de auditoría: estadísticas, filtros y agrupaciones."""

from __future__ import annotations

import logging

from datetime import datetime
from typing import Any

import pandas as pd

from .errors import AuditConfigError, AuditDataError, AuditValidationError
from .repository import AuditCsvRepository


class AuditAnalyticsService:
    """Orquesta lógica analítica sobre los datos de auditoría."""

    def __init__(self, *, repository: AuditCsvRepository, logger: logging.Logger) -> None:
        self.repository: AuditCsvRepository = repository
        self.logger: logging.Logger = logger

    def obtener_estadisticas(self) -> dict[str, Any]:
        """Retorna estadísticas globales de la auditoría."""
        try:
            dataframe = self.repository.leer_auditoria()
        except Exception as error:
            raise AuditConfigError(f"❌ Error obteniendo estadísticas: {error}") from error

        if dataframe.empty:
            raise AuditDataError("❌ No hay datos de auditoría")

        return {
            "total_operaciones": int(len(dataframe)),
            "total_filas_procesadas": int(dataframe["total_filas"].sum()),
            "tiempo_total_segundos": float(dataframe["tiempo_seg"].sum()),
            "tiempo_promedio_segundos": float(dataframe["tiempo_seg"].mean()),
            "tiempo_maximo_segundos": float(dataframe["tiempo_seg"].max()),
            "tiempo_minimo_segundos": float(dataframe["tiempo_seg"].min()),
            "operacion_mas_lenta": str(dataframe.loc[dataframe["tiempo_seg"].idxmax(), "operacion"]),
            "tabla_mas_activa": str(dataframe["tabla"].value_counts().index[0]),
            "motor_mas_usado": str(dataframe["motor"].value_counts().index[0]),
            "fecha_inicio": str(dataframe["timestamp"].min()),
            "fecha_fin": str(dataframe["timestamp"].max()),
        }

    def obtener_operaciones_por_tipo(self) -> dict[str, int]:
        """Retorna conteo de operaciones por tipo."""
        dataframe = self.repository.leer_auditoria()
        return {str(key): int(value) for key, value in dataframe["operacion"].value_counts().to_dict().items()}

    def obtener_operaciones_por_tabla(self) -> dict[str, int]:
        """Retorna conteo de operaciones por tabla."""
        dataframe = self.repository.leer_auditoria()
        return {str(key): int(value) for key, value in dataframe["tabla"].value_counts().to_dict().items()}

    def obtener_operaciones_lentas(self, umbral_segundos: float = 5.0) -> pd.DataFrame:
        """Retorna operaciones que tardaron más del umbral indicado."""
        dataframe = self.repository.leer_auditoria()
        operaciones_lentas = dataframe[dataframe["tiempo_seg"] > umbral_segundos].sort_values(
            "tiempo_seg", ascending=False
        )
        self.logger.info(f"🔍 {len(operaciones_lentas)} operaciones tardaron > {umbral_segundos}s")
        return operaciones_lentas

    def filtrar_por_operacion(self, operacion: str) -> pd.DataFrame:
        """Retorna registros de una operación específica."""
        if operacion not in ("INSERT", "UPDATE", "DELETE"):
            raise AuditValidationError(f"❌ Operación inválida: '{operacion}'. Debe ser INSERT, UPDATE o DELETE")
        dataframe = self.repository.leer_auditoria()
        return dataframe[dataframe["operacion"] == operacion]

    def filtrar_por_tabla(self, tabla: str) -> pd.DataFrame:
        """Retorna registros de una tabla específica."""
        if not tabla or not str(tabla).strip():
            raise AuditValidationError("❌ 'tabla' no puede estar vacío")
        dataframe = self.repository.leer_auditoria()
        return dataframe[dataframe["tabla"] == tabla]

    def filtrar_por_motor(self, motor: str) -> pd.DataFrame:
        """Retorna registros de un motor específico."""
        if not motor or not str(motor).strip():
            raise AuditValidationError("❌ 'motor' no puede estar vacío")
        dataframe = self.repository.leer_auditoria()
        return dataframe[dataframe["motor"] == motor]

    def filtrar_por_rango_tiempo(self, inicio: datetime, fin: datetime) -> pd.DataFrame:
        """Retorna registros dentro de un rango temporal."""
        if inicio > fin:
            raise AuditValidationError(f"❌ Rango inválido: inicio ({inicio}) debe ser anterior a fin ({fin})")
        dataframe = self.repository.leer_auditoria()
        dataframe["timestamp"] = pd.to_datetime(dataframe["timestamp"])
        return dataframe[(dataframe["timestamp"] >= inicio) & (dataframe["timestamp"] <= fin)].sort_values("timestamp")

    def filtrar_multiple(
        self,
        *,
        operacion: str | None = None,
        tabla: str | None = None,
        motor: str | None = None,
        umbral_tiempo: float | None = None,
    ) -> pd.DataFrame:
        """Filtra aplicando múltiples criterios con lógica AND."""
        dataframe = self.repository.leer_auditoria()

        if operacion is not None:
            if operacion not in ("INSERT", "UPDATE", "DELETE"):
                raise AuditValidationError(f"❌ Operación inválida: {operacion}")
            dataframe = dataframe[dataframe["operacion"] == operacion]

        if tabla:
            dataframe = dataframe[dataframe["tabla"] == tabla]

        if motor:
            dataframe = dataframe[dataframe["motor"] == motor]

        if umbral_tiempo is not None:
            dataframe = dataframe[dataframe["tiempo_seg"] >= umbral_tiempo]

        self.logger.info(f"🔍 Filtrado múltiple devolvió {len(dataframe)} registros")
        return dataframe

    def determinar_group_cols(self, agrupar_por: str) -> list[str]:
        """Determina columnas de agrupación para reportes."""
        if agrupar_por == "tabla":
            return ["tabla", "operacion", "sql"]
        if agrupar_por == "fecha":
            return ["fecha", "operacion", "sql"]
        if agrupar_por == "tabla_fecha":
            return ["fecha", "tabla", "operacion", "sql"]
        raise AuditValidationError(
            f"❌ 'agrupar_por' debe ser 'tabla', 'fecha' o 'tabla_fecha', se recibió '{agrupar_por}'."
        )

    def agrupar_y_generar_resumen(self, dataframe_operacion: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
        """Agrupa datos de auditoría y calcula métricas agregadas."""
        resumen = (
            dataframe_operacion.groupby(group_cols, dropna=False)
            .agg(
                total_filas=pd.NamedAgg(column="total_filas", aggfunc="sum"),
                tiempo_total=pd.NamedAgg(column="tiempo_seg", aggfunc="sum"),
                lotes=pd.NamedAgg(column="total_filas", aggfunc="count"),
                tiempo_medio=pd.NamedAgg(column="tiempo_seg", aggfunc="mean"),
            )
            .reset_index()
        )
        resumen["tiempo_total"] = resumen["tiempo_total"].round(3)
        resumen["tiempo_medio"] = resumen["tiempo_medio"].round(3)
        return resumen


__all__: list[str] = ["AuditAnalyticsService"]
