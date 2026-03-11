"""
Módulo para gestionar auditoría de operaciones CRUD en base de datos.

AuditManager se encarga de:
- Registrar operaciones (INSERT, UPDATE, DELETE) en archivos CSV
- Leer y procesar archivos de auditoría
- Generar resúmenes exportables a Excel
- Agrupar auditorías por tabla, fecha o ambas
- Análisis avanzado y filtrado de operaciones
"""

import copy
import csv
import json
import logging

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import pandas as pd

# ==================== EXCEPCIONES PERSONALIZADAS ====================


class AuditError(Exception):
    """Excepción base para auditoría."""

    pass


class AuditConfigError(AuditError):
    """Error en configuración de auditoría."""

    pass


class AuditFileError(AuditError):
    """Error en archivo de auditoría."""

    pass


class AuditDataError(AuditError):
    """Error en datos de auditoría."""

    pass


class AuditValidationError(AuditError):
    """Error en validación de parámetros."""

    pass


# ==================== CONTEXT MANAGER PARA TRANSACCIONES ====================


class AuditTransaction:
    """Context manager para gestionar transacciones de auditoría.

    Agrupa múltiples operaciones en una transacción con validación automática
    y logging integrado.

    Ejemplo:
        manager = AuditManager(Path("audit.csv"))
        with AuditTransaction(manager, "Importación masiva") as txn:
            manager.registrar_operacion("usuarios", "mysql", "INSERT", 100, 1.5, genero_sql=False)
            manager.registrar_operacion("permisos", "mysql", "INSERT", 100, 0.8, genero_sql=False)
            # Automáticamente valida, registra tiempo, y loggea la transacción
    """

    def __init__(self, manager: "AuditManager", nombre: str) -> None:
        """
        Inicializa una transacción de auditoría.

        Args:
            manager: Instancia de AuditManager para registrar operaciones.
            nombre: Nombre descriptivo de la transacción.

        Raises:
            AuditValidationError: Si el nombre está vacío o manager es inválido.
        """
        if not nombre or not nombre.strip():
            raise AuditValidationError("❌ El nombre de la transacción no puede estar vacío.")
        if not isinstance(manager, AuditManager):
            raise AuditValidationError("❌ El manager debe ser una instancia de AuditManager.")

        self.manager: AuditManager = manager
        self.nombre: str = nombre.strip()
        self.inicio: datetime | None = None
        self.fin: datetime | None = None
        self.operaciones: list[dict[str, Any]] = []
        self.exito: bool = False
        self.logger: logging.Logger = logging.getLogger(__name__)

    def __enter__(self) -> "AuditTransaction":
        """Inicia la transacción.

        Returns:
            La instancia de AuditTransaction para usar en el contexto.
        """
        self.inicio = datetime.now()
        self.logger.info(f"⏱️  Iniciando transacción: {self.nombre}")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Finaliza la transacción.

        Args:
            exc_type: Tipo de excepción si ocurrió un error.
            exc_val: Valor de la excepción.
            exc_tb: Traceback de la excepción.
        """
        self.fin = datetime.now()
        duracion: timedelta = self.fin - self.inicio if self.inicio else timedelta(0)

        # Determinar éxito
        self.exito = exc_type is None

        # Registrar transacción
        try:
            if self.exito:
                self._registrar_transaccion_exitosa(duracion)
            else:
                self._registrar_transaccion_fallida(duracion, exc_type, exc_val)
        except Exception as e:
            self.logger.error(f"❌ Error al finalizar transacción {self.nombre}: {e}")

    def _registrar_transaccion_exitosa(self, duracion: timedelta) -> None:
        """Registra una transacción exitosa."""
        tiempo_segundos: float = duracion.total_seconds()
        total_ops: int = len(self.operaciones)

        self.logger.info(
            f"✅ Transacción '{self.nombre}' completada: {total_ops} operaciones en {tiempo_segundos:.3f}s"
        )

        # Agregar al historial del manager
        resumen: dict[str, Any] = self.obtener_resumen()
        self.manager._historial_transacciones.append(resumen)

        # Invalidar caché después de transacción exitosa
        if self.manager.cache_enabled:
            self.manager.invalidar_cache()

    def _registrar_transaccion_fallida(self, duracion: timedelta, exc_type: Any, exc_val: Any) -> None:
        """Registra una transacción fallida."""
        tiempo_segundos: float = duracion.total_seconds()
        total_ops: int = len(self.operaciones)

        self.logger.error(
            f"❌ Transacción '{self.nombre}' FALLIDA: {total_ops} operaciones en {tiempo_segundos:.3f}s - Error: {exc_type.__name__}: {exc_val}"
        )

        # Agregar al historial del manager
        resumen: dict[str, Any] = self.obtener_resumen()
        self.manager._historial_transacciones.append(resumen)

        # Invalidar caché también en caso de error
        if self.manager.cache_enabled:
            self.manager.invalidar_cache()

    def agregar_operacion(
        self,
        tabla: str,
        motor: str,
        operacion: str,
        rowcount: int,
        elapsed: float,
        genero_sql: bool = False,
    ) -> None:
        """
        Registra una operación dentro de la transacción.

        Args:
            tabla: Nombre de la tabla.
            motor: Tipo de motor (mysql, oracle, etc).
            operacion: Tipo de operación (INSERT, UPDATE, DELETE).
            rowcount: Número de filas afectadas.
            elapsed: Tiempo en segundos.
            genero_sql: Si True indica que se generó SQL, False si se ejecutó (defecto: False).

        Raises:
            AuditValidationError: Si la transacción no está activa.
        """
        if self.inicio is None or self.fin is not None:
            raise AuditValidationError("❌ No se puede agregar operaciones a una transacción cerrada.")

        op_dict: dict[str, Any] = {
            "tabla": tabla,
            "motor": motor,
            "operacion": operacion,
            "rowcount": rowcount,
            "elapsed": elapsed,
            "genero_sql": genero_sql,
            "timestamp": datetime.now(),
        }
        self.operaciones.append(op_dict)
        self.logger.debug(f"📝 Operación agregada a transacción {self.nombre}: {tabla}.{operacion}")

    @property
    def duracion_segundos(self) -> float:
        """Retorna la duración de la transacción en segundos.

        Returns:
            Duración en segundos o 0 si no ha finalizado.
        """
        if self.inicio and self.fin:
            return (self.fin - self.inicio).total_seconds()
        return 0.0

    @property
    def total_operaciones(self) -> int:
        """Retorna el número total de operaciones en la transacción."""
        return len(self.operaciones)

    @property
    def total_filas(self) -> int:
        """Retorna el total de filas procesadas en la transacción."""
        return sum(op.get("rowcount", 0) for op in self.operaciones)

    def obtener_resumen(self) -> dict[str, Any]:
        """
        Retorna un resumen de la transacción.

        Returns:
            Dict con nombre, estado, duración, operaciones y filas totales.
        """
        return {
            "nombre": self.nombre,
            "exito": self.exito,
            "duracion_segundos": self.duracion_segundos,
            "total_operaciones": self.total_operaciones,
            "total_filas": self.total_filas,
            "operaciones": copy.deepcopy(self.operaciones),
        }


class AuditManager:
    """Gestiona la auditoría de operaciones CRUD en base de datos."""

    ERROR_AUDIT_PATH_REQUIRED: str = "❌ Debes especificar un archivo de auditoría válido."

    def __init__(
        self,
        audit_csv_path: Path | None = None,
        cache_enabled: bool = True,
        cache_ttl_seconds: int = 300,
    ):
        """
        Constructor de AuditManager.

        Args:
            audit_csv_path: Ruta del archivo CSV para auditoría. Si es None, no se audita.
            cache_enabled: Habilitar caché de DataFrames (defecto: True).
            cache_ttl_seconds: Tiempo de vida del caché en segundos (defecto: 300 = 5 min).

        Raises:
            ValueError: Si la ruta es inválida.
        """
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.audit_csv_path: Path | None = audit_csv_path
        self.columnas_auditoria: list[str] = [
            "timestamp",
            "tabla",
            "motor",
            "operacion",
            "total_filas",
            "tiempo_seg",
            "sql",
        ]

        # Configuración de caché
        self.cache_enabled: bool = cache_enabled
        self.cache_ttl_seconds: int = cache_ttl_seconds
        self._cache_df: pd.DataFrame | None = None
        self._cache_timestamp: datetime | None = None

        # Historial de transacciones (Phase 3)
        self._historial_transacciones: list[dict[str, Any]] = []

        if audit_csv_path is not None:
            self._validar_ruta(audit_csv_path)

    def _validar_ruta(self, ruta: Path) -> None:
        """Valida que la ruta sea accesible."""
        try:
            ruta.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ValueError(f"❌ No se puede acceder a la ruta de auditoría: {e}") from e

    def registrar_operacion(
        self,
        tabla: str,
        motor: str,
        operacion: str,
        rowcount: int,
        elapsed: float,
        genero_sql: bool = False,
    ) -> None:
        """
        Registra una operación en el archivo CSV de auditoría.

        Args:
            tabla: Nombre de la tabla afectada (no vacío).
            motor: Tipo de base de datos (mysql, oracle, etc, no vacío).
            operacion: Tipo de operación (INSERT, UPDATE, DELETE).
            rowcount: Número de filas afectadas (>= 0).
            elapsed: Tiempo transcurrido en segundos (>= 0).
            genero_sql: Si True indica que se generó SQL, False si se ejecutó (defecto: False).

        Raises:
            AuditConfigError: Si audit_csv_path no está configurado.
            AuditValidationError: Si los parámetros son inválidos.
        """
        if self.audit_csv_path is None:
            self.logger.warning("⚠️ Auditoría deshabilitada: audit_csv_path es None")
            return

        # Validar parámetros
        self._validar_parametros_operacion(tabla, motor, operacion, rowcount, elapsed)

        self._auditar_lote_csv(self.audit_csv_path, tabla, motor, operacion, rowcount, elapsed, genero_sql)

        # Invalidar caché al registrar operación (Phase 2)
        self.invalidar_cache()

        self.logger.info(f"🟢 {operacion} - filas {rowcount} - {elapsed:.3f}s registrado en auditoría")

    def _validar_parametros_operacion(
        self, tabla: str, motor: str, operacion: str, rowcount: int, elapsed: float
    ) -> None:
        """Valida parámetros de operación."""
        if not tabla or not str(tabla).strip():
            raise AuditValidationError("❌ 'tabla' no puede estar vacío")

        if not motor or not str(motor).strip():
            raise AuditValidationError("❌ 'motor' no puede estar vacío")

        if operacion not in ("INSERT", "UPDATE", "DELETE"):
            raise AuditValidationError(f"❌ Operación inválida: '{operacion}'. Debe ser INSERT, UPDATE o DELETE")

        if not isinstance(rowcount, int) or rowcount < 0:
            raise AuditValidationError(f"❌ 'rowcount' debe ser un entero >= 0, se recibió {rowcount}")

        if not isinstance(elapsed, (int, float)) or elapsed < 0:
            raise AuditValidationError(f"❌ 'elapsed' debe ser un número >= 0, se recibió {elapsed}")

    def _auditar_lote_csv(
        self,
        audit_path: Path,
        tabla: str,
        motor: str,
        operacion: str,
        rowcount: int,
        elapsed: float,
        genero_sql: bool = False,
    ) -> None:
        """
        Escribe un registro de auditoría en el archivo CSV.

        Args:
            audit_path: Ruta del archivo CSV.
            tabla: Nombre de la tabla.
            motor: Tipo de BD.
            operacion: Tipo de operación.
            rowcount: Número de filas.
            elapsed: Tiempo en segundos.
            genero_sql: Si True se generó SQL, False si se ejecutó.
        """
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        file_exists: bool = Path(audit_path).exists()

        with open(audit_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter="\t")
            if not file_exists:
                writer.writerow(self.columnas_auditoria)
            # Formatear tiempo con coma decimal para compatibilidad con Excel
            tiempo_formateado: str = f"{elapsed:.3f}".replace(".", ",")
            sql_texto: str = "Sí" if genero_sql else "No"
            writer.writerow(
                [
                    datetime.now().isoformat(timespec="seconds"),
                    tabla,
                    motor,
                    operacion,
                    rowcount,
                    tiempo_formateado,
                    sql_texto,
                ]
            )

    def leer_auditoria(self, usar_cache: bool = True) -> pd.DataFrame:
        """
        Lee el archivo CSV de auditoría y lo convierte en DataFrame.

        Args:
            usar_cache: Usar caché si está disponible y es válido (defecto: True).

        Returns:
            DataFrame con los datos de auditoría.

        Raises:
            AuditConfigError: Si audit_csv_path no está configurado.
            AuditFileError: Si el archivo no existe.
            AuditDataError: Si hay error al leer los datos.
        """
        # Verificar si tenemos caché válido
        if usar_cache and self.cache_enabled and self._es_cache_valido() and self._cache_df is not None:
            self.logger.debug("📦 Usando caché para lectura de auditoría")
            return self._cache_df.copy()

        if self.audit_csv_path is None:
            raise AuditConfigError("❌ 'audit_csv_path' no está establecido.")

        if not self.audit_csv_path.exists():
            raise AuditFileError(f"❌ Archivo de auditoría no encontrado: {self.audit_csv_path}")

        try:
            df: pd.DataFrame = pd.read_csv(str(self.audit_csv_path), delimiter="\t", parse_dates=["timestamp"])
            # Convertir comas a puntos en columna de tiempo (compatibilidad con Excel)
            if "tiempo_seg" in df.columns:
                df["tiempo_seg"] = df["tiempo_seg"].astype(str).str.replace(",", ".").astype(float)

            # Guardar en caché
            if self.cache_enabled:
                self._cache_df = df.copy()
                self._cache_timestamp = datetime.now()
                self.logger.debug(f"💾 Caché actualizado ({len(df)} filas)")

            return df
        except Exception as e:
            raise AuditDataError(f"❌ Error al leer el archivo CSV de auditoría: {e}") from e

    def _es_cache_valido(self) -> bool:
        """Verifica si el caché es válido y no ha expirado."""
        if self._cache_df is None or self._cache_timestamp is None:
            return False

        tiempo_transcurrido = (datetime.now() - self._cache_timestamp).total_seconds()
        return tiempo_transcurrido < self.cache_ttl_seconds

    def limpiar_cache(self) -> None:
        """Limpia el caché de datos."""
        self._cache_df = None
        self._cache_timestamp = None
        self.logger.info("🧹 Caché limpiado")

    def invalidar_cache(self) -> None:
        """Invalida el caché (alias de limpiar_cache para compatibilidad)."""
        self.limpiar_cache()

    def exportar_resumen_excel(self, agrupar_por: Literal["tabla", "fecha", "tabla_fecha"] = "tabla") -> Path:
        """
        Exporta un resumen de auditoría a Excel con hojas separadas por operación.

        Args:
            agrupar_por: Criterio de agrupación ('tabla', 'fecha' o 'tabla_fecha').

        Returns:
            Ruta del archivo Excel generado.

        Raises:
            AuditConfigError: Si no hay archivo de auditoría configurado.
            AuditDataError: Si no hay datos de auditoría o son inválidos.
        """
        if self.audit_csv_path is None:
            raise AuditConfigError(self.ERROR_AUDIT_PATH_REQUIRED)

        output_excel: Path = self.audit_csv_path.parent / "auditoria.xlsx"
        df: pd.DataFrame = self.leer_auditoria()

        # Validar columnas requeridas
        columnas_faltantes: set[str] = set(self.columnas_auditoria) - set(df.columns)
        if columnas_faltantes:
            raise AuditDataError(f"❌ El CSV no contiene las columnas requeridas: {', '.join(columnas_faltantes)}")

        # Normalizar datos
        df["tiempo_seg"] = df["tiempo_seg"].astype(str).str.replace(",", ".").astype(float)
        df["fecha"] = pd.to_datetime(df["timestamp"]).dt.normalize()
        operaciones: list = df["operacion"].unique().tolist()

        group_cols: list[str] = self._determinar_group_cols(agrupar_por)
        output_excel.parent.mkdir(parents=True, exist_ok=True)
        resumen_global: list[pd.DataFrame] = []

        with pd.ExcelWriter(output_excel, engine="openpyxl") as writer:
            for op in operaciones:
                df_op: pd.DataFrame = df[df["operacion"] == op]
                if df_op.empty:
                    continue

                resumen_op: pd.DataFrame = self._agrupar_y_generar_resumen(df_op, group_cols)
                hoja: str = f"{op.capitalize()}_{agrupar_por}"
                # Excel limita nombres de hoja a 31 caracteres
                resumen_op.to_excel(writer, sheet_name=hoja[:31], index=False)
                resumen_global.append(resumen_op)

            # Crear hoja de resumen global
            if resumen_global:
                df_global: pd.DataFrame = pd.concat(resumen_global, ignore_index=True)
                # Reordenar columnas si existen fecha y tabla
                if "tabla" in df_global.columns and "fecha" in df_global.columns:
                    df_global = df_global[
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
                df_global.to_excel(writer, sheet_name="Resumen_global", index=False)

        self.logger.info(f"✅ Resumen de auditoría exportado a: {output_excel}")
        return output_excel

    # ==================== ANÁLISIS AVANZADO ====================

    def obtener_estadisticas(self) -> dict[str, Any]:
        """
        Retorna estadísticas globales de la auditoría.

        Returns:
            Diccionario con estadísticas agregadas.

        Raises:
            AuditConfigError: Si no hay datos de auditoría.
        """
        try:
            df = self.leer_auditoria()
        except Exception as e:
            raise AuditConfigError(f"❌ Error obteniendo estadísticas: {e}") from e

        if df.empty:
            raise AuditDataError("❌ No hay datos de auditoría")

        return {
            "total_operaciones": int(len(df)),
            "total_filas_procesadas": int(df["total_filas"].sum()),
            "tiempo_total_segundos": float(df["tiempo_seg"].sum()),
            "tiempo_promedio_segundos": float(df["tiempo_seg"].mean()),
            "tiempo_maximo_segundos": float(df["tiempo_seg"].max()),
            "tiempo_minimo_segundos": float(df["tiempo_seg"].min()),
            "operacion_mas_lenta": str(df.loc[df["tiempo_seg"].idxmax(), "operacion"]),
            "tabla_mas_activa": str(df["tabla"].value_counts().index[0]),
            "motor_mas_usado": str(df["motor"].value_counts().index[0]),
            "fecha_inicio": str(df["timestamp"].min()),
            "fecha_fin": str(df["timestamp"].max()),
        }

    def obtener_operaciones_por_tipo(self) -> dict[str, int]:
        """
        Retorna conteo de operaciones por tipo.

        Returns:
            Diccionario con operación como clave y conteo como valor.
        """
        df: pd.DataFrame = self.leer_auditoria()
        return {str(k): int(v) for k, v in df["operacion"].value_counts().to_dict().items()}

    def obtener_operaciones_por_tabla(self) -> dict[str, int]:
        """
        Retorna conteo de operaciones por tabla.

        Returns:
            Diccionario con tabla como clave y conteo como valor.
        """
        df: pd.DataFrame = self.leer_auditoria()
        return {str(k): int(v) for k, v in df["tabla"].value_counts().to_dict().items()}

    def obtener_operaciones_lentas(self, umbral_segundos: float = 5.0) -> pd.DataFrame:
        """
        Retorna operaciones que tardaron más de X segundos.

        Args:
            umbral_segundos: Umbral de tiempo en segundos.

        Returns:
            DataFrame con operaciones lentas ordenadas por tiempo descendente.
        """
        df = self.leer_auditoria()
        operaciones_lentas = df[df["tiempo_seg"] > umbral_segundos].sort_values("tiempo_seg", ascending=False)
        self.logger.info(f"🔍 {len(operaciones_lentas)} operaciones tardaron > {umbral_segundos}s")
        return operaciones_lentas

    # ==================== FILTRADO AVANZADO ====================

    def filtrar_por_operacion(self, operacion: str) -> pd.DataFrame:
        """
        Retorna registros de una operación específica.

        Args:
            operacion: Tipo de operación (INSERT, UPDATE, DELETE).

        Returns:
            DataFrame filtrado.

        Raises:
            AuditValidationError: Si la operación es inválida.
        """
        if operacion not in ("INSERT", "UPDATE", "DELETE"):
            raise AuditValidationError(f"❌ Operación inválida: '{operacion}'. Debe ser INSERT, UPDATE o DELETE")
        df = self.leer_auditoria()
        return df[df["operacion"] == operacion]

    def filtrar_por_tabla(self, tabla: str) -> pd.DataFrame:
        """
        Retorna registros de una tabla específica.

        Args:
            tabla: Nombre de la tabla.

        Returns:
            DataFrame filtrado.
        """
        if not tabla or not str(tabla).strip():
            raise AuditValidationError("❌ 'tabla' no puede estar vacío")
        df = self.leer_auditoria()
        return df[df["tabla"] == tabla]

    def filtrar_por_motor(self, motor: str) -> pd.DataFrame:
        """
        Retorna registros de un motor específico.

        Args:
            motor: Tipo de base de datos (mysql, oracle, etc).

        Returns:
            DataFrame filtrado.
        """
        if not motor or not str(motor).strip():
            raise AuditValidationError("❌ 'motor' no puede estar vacío")
        df = self.leer_auditoria()
        return df[df["motor"] == motor]

    def filtrar_por_rango_tiempo(self, inicio: datetime, fin: datetime) -> pd.DataFrame:
        """
        Retorna registros dentro de un rango de tiempo.

        Args:
            inicio: Fecha/hora de inicio (inclusive).
            fin: Fecha/hora de fin (inclusive).

        Returns:
            DataFrame filtrado ordenado por timestamp.

        Raises:
            AuditValidationError: Si el rango es inválido.
        """
        if inicio > fin:
            raise AuditValidationError(f"❌ Rango inválido: inicio ({inicio}) debe ser anterior a fin ({fin})")
        df = self.leer_auditoria()
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df[(df["timestamp"] >= inicio) & (df["timestamp"] <= fin)].sort_values("timestamp")

    def filtrar_multiple(
        self,
        operacion: str | None = None,
        tabla: str | None = None,
        motor: str | None = None,
        umbral_tiempo: float | None = None,
    ) -> pd.DataFrame:
        """
        Filtra con múltiples criterios (AND).

        Args:
            operacion: Tipo de operación (opcional).
            tabla: Nombre de tabla (opcional).
            motor: Tipo de BD (opcional).
            umbral_tiempo: Tiempo mínimo en segundos (opcional).

        Returns:
            DataFrame filtrado según criterios.

        Raises:
            AuditValidationError: Si algún parámetro es inválido.
        """
        df = self.leer_auditoria()

        if operacion:
            if operacion not in ("INSERT", "UPDATE", "DELETE"):
                raise AuditValidationError(f"❌ Operación inválida: {operacion}")
            df = df[df["operacion"] == operacion]

        if tabla:
            df = df[df["tabla"] == tabla]

        if motor:
            df = df[df["motor"] == motor]

        if umbral_tiempo is not None:
            df = df[df["tiempo_seg"] >= umbral_tiempo]

        self.logger.info(f"🔍 Filtrado múltiple devolvió {len(df)} registros")
        return df

    def _determinar_group_cols(self, agrupar_por: str) -> list[str]:
        """
        Determina las columnas de agrupación según el criterio.

        Args:
            agrupar_por: Criterio de agrupación.

        Returns:
            Lista de columnas para agrupar.

        Raises:
            AuditValidationError: Si el criterio no es válido.
        """
        if agrupar_por == "tabla":
            return ["tabla", "operacion"]
        if agrupar_por == "fecha":
            return ["fecha", "operacion"]
        if agrupar_por == "tabla_fecha":
            return ["fecha", "tabla", "operacion"]
        raise AuditValidationError(
            f"❌ 'agrupar_por' debe ser 'tabla', 'fecha' o 'tabla_fecha', se recibió '{agrupar_por}'."
        )

    def _agrupar_y_generar_resumen(self, df_op: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
        """
        Agrupa datos de auditoría y genera resumen con estadísticas.

        Args:
            df_op: DataFrame con datos de una operación.
            group_cols: Columnas para agrupar.

        Returns:
            DataFrame resumen con estadísticas agregadas.
        """
        resumen_op: pd.DataFrame = (
            df_op.groupby(group_cols)
            .agg(
                total_filas=pd.NamedAgg(column="total_filas", aggfunc="sum"),
                tiempo_total=pd.NamedAgg(column="tiempo_seg", aggfunc="sum"),
                lotes=pd.NamedAgg(column="total_filas", aggfunc="count"),
                tiempo_medio=pd.NamedAgg(column="tiempo_seg", aggfunc="mean"),
            )
            .reset_index()
        )
        resumen_op["tiempo_total"] = resumen_op["tiempo_total"].round(3)
        resumen_op["tiempo_medio"] = resumen_op["tiempo_medio"].round(3)
        return resumen_op

    # ======== MÉTODOS DE EXPORTACIÓN (PHASE 2) ========

    def exportar_resumen_json(self, output_path: Path | None = None) -> Path:
        """
        Exporta un resumen de auditoría a JSON.

        Args:
            output_path: Ruta para guardar el archivo. Si es None, usa directorio del CSV.

        Returns:
            Path al archivo JSON creado.

        Raises:
            AuditConfigError: Si no hay audit_csv_path configurado.
            AuditDataError: Si hay error al exportar.
        """
        if self.audit_csv_path is None:
            raise AuditConfigError(self.ERROR_AUDIT_PATH_REQUIRED)

        df: pd.DataFrame = self.leer_auditoria()
        output_json: Path = output_path or self.audit_csv_path.parent / "auditoria.json"

        try:
            stats = self.obtener_estadisticas()
            operaciones = self.obtener_operaciones_por_tipo()
            tablas = self.obtener_operaciones_por_tabla()

            resumen: dict[str, Any] = {
                "fecha_generacion": datetime.now().isoformat(),
                "estadisticas": {
                    k: (v.isoformat() if isinstance(v, (datetime, pd.Timestamp)) else v) for k, v in stats.items()
                },
                "operaciones_por_tipo": operaciones,
                "operaciones_por_tabla": tablas,
                "registros_totales": len(df),
                "periodo": {
                    "inicio": df["timestamp"].min().isoformat() if len(df) > 0 else None,
                    "fin": df["timestamp"].max().isoformat() if len(df) > 0 else None,
                },
            }

            output_json.parent.mkdir(parents=True, exist_ok=True)
            with open(output_json, "w", encoding="utf-8") as f:
                json.dump(resumen, f, indent=2, ensure_ascii=False)

            self.logger.info(f"✅ Auditoría exportada a JSON: {output_json}")
            return output_json

        except Exception as e:
            raise AuditDataError(f"❌ Error al exportar JSON: {e}") from e

    def exportar_resumen_html(self, output_path: Path | None = None) -> Path:
        """
        Exporta un resumen de auditoría a HTML con tabla interactiva.

        Args:
            output_path: Ruta para guardar el archivo. Si es None, usa directorio del CSV.

        Returns:
            Path al archivo HTML creado.

        Raises:
            AuditConfigError: Si no hay audit_csv_path configurado.
            AuditDataError: Si hay error al exportar.
        """
        if self.audit_csv_path is None:
            raise AuditConfigError(self.ERROR_AUDIT_PATH_REQUIRED)

        df: pd.DataFrame = self.leer_auditoria()
        output_html: Path = output_path or self.audit_csv_path.parent / "auditoria.html"

        try:
            stats = self.obtener_estadisticas()

            # Generar HTML con estilos
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
        {df.tail(20).to_html(classes="audit-table", index=False)}

        <h2>Operaciones por Tipo</h2>
        {pd.DataFrame(self.obtener_operaciones_por_tipo().items(), columns=["Operación", "Cantidad"]).to_html(classes="audit-table", index=False)}

        <h2>Operaciones por Tabla</h2>
        {pd.DataFrame(self.obtener_operaciones_por_tabla().items(), columns=["Tabla", "Cantidad"]).to_html(classes="audit-table", index=False)}

        <div class="footer">
            <p>Este reporte fue generado automáticamente por AuditManager (Phase 2)</p>
        </div>
    </div>
</body>
</html>"""

            output_html.parent.mkdir(parents=True, exist_ok=True)
            with open(output_html, "w", encoding="utf-8") as f:
                f.write(html_content)

            self.logger.info(f"✅ Auditoría exportada a HTML: {output_html}")
            return output_html

        except Exception as e:
            raise AuditDataError(f"❌ Error al exportar HTML: {e}") from e

    # ==================== MÉTODOS DE TRANSACCIÓN (PHASE 3) ====================

    def iniciar_transaccion(self, nombre: str) -> AuditTransaction:
        """
        Inicia una transacción de auditoría.

        Args:
            nombre: Nombre descriptivo de la transacción.

        Returns:
            Instancia de AuditTransaction para usar como context manager.

        Raises:
            AuditValidationError: Si el nombre está vacío.

        Ejemplo:
            txn = manager.iniciar_transaccion("Importación masiva")
            with txn:
                # registrar operaciones
                pass
        """
        return AuditTransaction(self, nombre)

    def crear_transaccion(self, nombre: str) -> AuditTransaction:
        """Alias de iniciar_transaccion() para compatibilidad."""
        return self.iniciar_transaccion(nombre)

    def obtener_historial_transacciones(self) -> list[dict[str, Any]]:
        """
        Retorna el historial de transacciones registradas.

        Returns:
            Lista de transacciones con su información de resumen (copia).

        Raises:
            AuditConfigError: Si audit_csv_path no está configurado.

        Ejemplo:
            historial = manager.obtener_historial_transacciones()
            for txn in historial:
                print(f"{txn['nombre']}: {txn['total_operaciones']} ops en {txn['duracion_segundos']:.2f}s")
        """
        if self.audit_csv_path is None:
            raise AuditConfigError(self.ERROR_AUDIT_PATH_REQUIRED)

        return self._historial_transacciones.copy()
