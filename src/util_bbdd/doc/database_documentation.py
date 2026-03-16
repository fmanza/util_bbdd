"""
Clase unificada para generar documentación de bases de datos (MariaDB/Oracle/PostgreSQL/HSQLDB) en Word o Excel.
Versión refactorizada con arquitectura modular.
"""

import json
import logging
import re
import time

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

# Importar módulos modulares
from ..database_exceptions import QueryNotFoundError
from ..managers import SyncDatabaseManager
from .excel_generator import ExcelGenerator
from .html_generator import HtmlGenerator
from .print_config_manager import PrintConfigManager
from .word_generator import WordGenerator


class DatabaseDocumentation:
    """Clase unificada para generar documentación de bases de datos usando arquitectura modular.

    Args:
        db_manager: Instancia de SyncDatabaseManager ya configurada
        directorio_salida: Directorio de salida para los archivos
        fichero_salida: Path del archivo de salida (sin extensión). Si es None, se genera automáticamente
        imprimir: Diccionario de configuración para secciones y gráficos.
            - plantilla_word: Ruta opcional a plantilla Word (.docx)
            - tablas_por_documento: Número de tablas por documento Word (default 50)
            - table_style: Estilo de tablas para Word/Excel (default "Table Grid")
            - html_items_por_pagina: Número de elementos por página en índice HTML (default 15)
            - grafo.images_paginated: Si True, genera imágenes por paginación
            - grafo.max_subnodes: Máximo de subnodos/tablas por imagen paginada (default 10)
        formatos: Lista de formatos de salida a generar. Valores soportados: 'word', 'excel', 'html'
        headers_file: Ruta al fichero JSON con configuración de headers
    """

    # Constantes para strings reutilizados
    _ARCHIVO_FISICO: str = "Archivo fisico"
    _TAMANO_MB: str = "Tamaño (MB)"
    _TIPO_FICHERO: str = "Tipo de fichero"

    def __init__(
        self,
        db_manager: SyncDatabaseManager,
        directorio_salida: Path = Path(""),
        fichero_salida: Path | None = None,
        imprimir: dict[str, Any] | None = None,
        formatos: list[str] | None = None,
        headers_file: Path = Path(__file__).parent / "data/headers_config.json",
    ) -> None:
        # Validar que db_manager sea una instancia sync.
        if not isinstance(db_manager, SyncDatabaseManager):
            raise TypeError("db_manager debe ser una instancia de SyncDatabaseManager")

        # Configurar logger
        self.logger: logging.Logger = logging.getLogger(__name__)

        # Configuración básica
        self.db_manager: SyncDatabaseManager = db_manager
        self.imprimir_config: dict[str, Any] = PrintConfigManager.normalize(imprimir)
        self.formatos: list[str] = self._normalize_output_formats(formatos)
        self.directorio_salida: Path = directorio_salida

        # Generar nombre de archivo si no se proporciona
        if fichero_salida is None:
            fichero_salida = self._generate_output_filename()

        self.fichero_salida: Path = fichero_salida
        self.table_style: str = str(self.imprimir_config.get("table_style", "Table Grid"))

        # Cargar y construir headers
        self.headers_config = self._load_headers_config(headers_file)
        self.headers = self._build_headers()

        # Obtener tablas y vistas y generar documento
        self.tablas: list = self.db_manager.get_tables()
        self.vistas: list = self.db_manager.get_views()
        self.rutinas: list = self.db_manager.get_routines()
        self._create_documents()

    def _generate_output_filename(self) -> Path:
        """Genera un nombre de archivo automático basado en la base de datos y timestamp.

        Formato: {identificador}-{YYYYMMDD_HHMMSS}

        Notas:
        - En Oracle se prioriza el usuario de conexión como identificador.
        - En otros motores se usa `database`.
        - Si no hay identificador disponible, usa el tipo de motor.

        Returns:
            Path con el nombre del archivo sin extensión
        """
        timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        identifier: str = self._resolve_output_filename_identifier()
        safe_identifier: str = identifier.replace(" ", "_").replace("/", "_").replace("\\", "_")
        cache_key: tuple[str, str] = (str(self.directorio_salida), safe_identifier)
        now: float = time.time()
        cached: tuple[float, str] | None = self._LAST_AUTO_OUTPUT_BY_KEY.get(cache_key)
        if cached is not None:
            cached_at, cached_name = cached
            if now - cached_at <= self._AUTO_OUTPUT_BATCH_WINDOW_SECONDS:
                return Path(cached_name)

        generated_name: str = f"{safe_identifier}-{timestamp}"
        self._LAST_AUTO_OUTPUT_BY_KEY[cache_key] = (now, generated_name)
        return Path(generated_name)

    def _resolve_output_filename_identifier(self) -> str:
        """Resuelve el identificador para el nombre de archivo de salida.

        Returns:
            Identificador normalizado (database, user, o db_type).
        """
        try:
            raw_conn_params: Any = self.db_manager.conn_params
        except AttributeError:
            raw_conn_params = None
        conn_params: dict[str, Any] = raw_conn_params if isinstance(raw_conn_params, dict) else {}

        identifier: str = (self.db_manager.database or "").strip()
        if self.db_manager.db_type == "oracle":
            oracle_user: str = str(conn_params.get("user", "")).strip()
            identifier = oracle_user or identifier
        elif not identifier:
            fallback_user: str = str(conn_params.get("user", "")).strip()
            identifier = fallback_user or identifier

        if not identifier:
            identifier = self.db_manager.db_type

        if self.db_manager.db_type == "sqlite":
            identifier = self._normalize_sqlite_identifier(identifier)

        return identifier

    def _normalize_sqlite_identifier(self, identifier: str) -> str:
        """Normaliza identificador SQLite extrayendo nombre de archivo.

        Args:
            identifier: Ruta o nombre de archivo SQLite.

        Returns:
            Nombre de archivo SQLite sin extensión.
        """
        normalized_identifier: str = identifier.replace("\\", "/")
        sqlite_name: str = normalized_identifier.split("/")[-1] if normalized_identifier else ""
        if sqlite_name.lower().endswith(".sqlite"):
            sqlite_name = sqlite_name[:-7]
        elif sqlite_name.lower().endswith(".db"):
            sqlite_name = sqlite_name[:-3]
        return sqlite_name or "sqlite"

    def _load_headers_config(self, headers_file: Path) -> dict:
        """Carga la configuración de headers desde el fichero JSON."""
        try:
            with open(headers_file, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Fichero de headers no encontrado: {headers_file}") from e
        except json.JSONDecodeError as e:
            raise ValueError(f"Error al leer fichero JSON de headers: {e}") from e

    def _build_headers(self) -> dict:
        """Construye los headers dinámicamente según el tipo de base de datos."""
        headers = {}
        headers_cfg = self.headers_config["headers"]
        labels_cfg = self.headers_config["labels"]

        for section, config in headers_cfg.items():
            # Combinar headers base + específicos del tipo de BD
            base_headers = config["base"]
            db_specific_headers = config.get(self.db_manager.db_type, [])

            # Construir lista de headers
            header_list = base_headers + db_specific_headers

            # Obtener las etiquetas específicas para el tipo de BD
            labels = labels_cfg.get(section, {}).get(self.db_manager.db_type, {})

            # Reemplazar nombres de headers con etiquetas si existen
            final_headers = []
            for header in header_list:
                if header in labels:
                    final_headers.append(labels[header])
                else:
                    final_headers.append(header)

            headers[section] = final_headers

        return headers

    def _normalize_output_formats(self, formatos: list[str] | None) -> list[str]:
        """Normaliza y valida formatos de salida solicitados."""
        if formatos is None:
            return ["word"]

        if not isinstance(formatos, list):
            raise TypeError("formatos debe ser una lista de strings")

        supported_formats: set[str] = {"word", "excel", "html"}
        normalized: list[str] = []
        seen: set[str] = set()
        for raw_format in formatos:
            normalized_format: str = str(raw_format or "").strip().lower()
            if not normalized_format:
                continue
            if normalized_format not in supported_formats:
                raise ValueError(f"Formato no soportado: {raw_format}. Use 'word', 'excel' o 'html'")
            if normalized_format in seen:
                continue
            seen.add(normalized_format)
            normalized.append(normalized_format)

        if not normalized:
            raise ValueError("No se informaron formatos válidos en 'formatos'")

        return normalized

    def _create_documents(self) -> None:
        """Genera documentación para todos los formatos solicitados."""
        for output_format in self.formatos:
            if output_format == "word":
                self._create_document_word()
            elif output_format == "excel":
                self._create_document_excel()
            elif output_format == "html":
                self._create_document_html()

    def _create_document_word(self) -> None:
        """Crea el documento Word usando el generador modular."""
        context_database: str = self._get_generator_database_context()
        word_generator = WordGenerator(database=context_database, headers=self.headers, table_style=self.table_style)

        output_dir: Path = self._get_format_output_dir("word")
        output_file: Path = (output_dir / self._get_output_base_filename()).with_suffix(".docx")
        word_generator.generate_document(
            self.tablas,
            self.vistas,
            self.rutinas,
            self,
            output_file,
            print_config=self.imprimir_config,
        )

    def _create_document_excel(self) -> None:
        """Crea el documento Excel usando el generador modular."""
        context_database: str = self._get_generator_database_context()
        excel_generator = ExcelGenerator(database=context_database, headers=self.headers, table_style=self.table_style)

        output_dir: Path = self._get_format_output_dir("excel")
        output_file: Path = (output_dir / self._get_output_base_filename()).with_suffix(".xlsx")
        excel_generator.generate_document(
            self.tablas,
            self.vistas,
            self.rutinas,
            self,
            output_file,
            print_config=self.imprimir_config,
        )

    def _create_document_html(self) -> None:
        """Crea la documentación HTML en una carpeta dedicada usando el generador modular."""
        context_database: str = self._get_generator_database_context()
        html_generator = HtmlGenerator(database=context_database, headers=self.headers)

        output_dir: Path = self._get_format_output_dir("html")

        html_generator.generate_document(
            self.tablas,
            self.vistas,
            self.rutinas,
            self,
            output_dir,
            print_config=self.imprimir_config,
        )

    def _get_execution_root_name(self) -> str:
        """Obtiene nombre de carpeta raíz por ejecución (igual al nombre histórico de carpeta HTML)."""
        candidate: str = self.fichero_salida.stem if self.fichero_salida.suffix else str(self.fichero_salida)
        safe_name: str = Path(candidate).name.strip()
        return safe_name or "documentacion"

    def _get_output_base_filename(self) -> str:
        """Obtiene nombre base de archivo para salidas Word/Excel."""
        base_name: str = (
            Path(self.fichero_salida).stem if self.fichero_salida.suffix else Path(str(self.fichero_salida)).name
        )
        normalized: str = str(base_name or "").strip()
        return normalized or "documentacion"

    def _ensure_execution_root(self) -> Path:
        """Crea (si no existe) carpeta raíz por ejecución."""
        execution_root: Path = self.directorio_salida / self._get_execution_root_name()
        execution_root.mkdir(parents=True, exist_ok=True)
        return execution_root

    def _get_format_output_dir(self, formato: str) -> Path:
        """Obtiene y crea solo la subcarpeta del formato solicitado."""
        execution_root: Path = self._ensure_execution_root()
        normalized: str = str(formato or "").strip().lower()
        format_folder_map: dict[str, str] = {
            "html": "HTML",
            "word": "WORD",
            "excel": "EXCEL",
        }
        if normalized not in format_folder_map:
            raise ValueError(f"Formato no soportado para salida: {formato}")

        output_dir: Path = execution_root / format_folder_map[normalized]
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def _get_generator_database_context(self) -> str:
        """Obtiene identificador de contexto para generadores de documentación.

        Returns:
            Nombre de base/esquema a mostrar en encabezados y metadatos de salida.

        Notes:
            - En Oracle se prioriza `user` (owner/schema) por compatibilidad.
            - En otros motores se usa `database` con fallback a `user` y db_type.
        """
        resolved_context: str = str(self.db_manager.get_query_context_database() or "").strip()
        if resolved_context:
            return resolved_context

        return self._resolve_context_by_db_type()

    def _resolve_context_by_db_type(self) -> str:
        """Resuelve el contexto de base de datos según el tipo de motor.

        Returns:
            Nombre normalizado de base/esquema/usuario según el motor.
        """
        conn_params: dict[str, Any] = self.db_manager.conn_params or {}
        db_type: str = str(self.db_manager.db_type or "").strip().lower()
        if not db_type:
            db_type = "unknown"

        database_value: str = str(self.db_manager.database or "").strip()
        user_value: str = str(conn_params.get("user", "") or "").strip()
        schema_value: str = str(conn_params.get("schema", "") or "").strip()

        context_resolver: dict[str, Callable[[], str]] = {
            "oracle": lambda: user_value or database_value or db_type,
            "postgresql": lambda: schema_value or database_value or "public",
            "hsqldb": lambda: schema_value or database_value or "PUBLIC",
            "sqlserver": lambda: schema_value or database_value or "dbo",
            "sqlite": lambda: database_value or db_type,
        }

        resolver = context_resolver.get(db_type)
        if resolver:
            return resolver()

        return database_value or user_value or db_type

    # ==================== MÉTODOS DE COMPATIBILIDAD ====================
    # Estos métodos mantienen compatibilidad con la interfaz original
    # para que los generadores puedan acceder a la información necesaria

    @property
    def db_type(self) -> str:
        """Devuelve el tipo de base de datos (para compatibilidad)."""
        return self.db_manager.db_type

    @property
    def database(self) -> str:
        """Devuelve el nombre de la base de datos (para compatibilidad)."""
        return self._get_generator_database_context()

    def get_ddl(self, tabla: str) -> str:
        """Obtiene el DDL de una tabla (para compatibilidad)."""
        return self.db_manager.get_ddl(tabla)

    def get_view_ddl(self, vista: str) -> str:
        """Obtiene el DDL de una vista (para compatibilidad)."""
        return self.db_manager.get_view_ddl(vista)

    def get_columns(self, tabla: str) -> list:
        """Obtiene las columnas de una tabla (para compatibilidad)."""
        return self.db_manager.get_columns(tabla)

    def get_routine_ddl(self, rutina: str, tipo_rutina: str) -> str:
        """Obtiene el DDL de una rutina (para compatibilidad)."""
        return self.db_manager.get_routine_ddl(rutina, tipo_rutina)

    def get_routine_parameters(self, rutina: str, tipo_rutina: str) -> list:
        """Obtiene los parámetros de una rutina (para compatibilidad)."""
        return self.db_manager.get_routine_parameters(rutina, tipo_rutina)

    def get_primary_keys(self, tabla: str) -> list:
        """Obtiene las claves primarias de una tabla (para compatibilidad)."""
        return self.db_manager.get_primary_keys(tabla)

    def get_foreign_keys(self, tabla: str) -> list:
        """Obtiene las claves foráneas de una tabla (para compatibilidad)."""
        return self.db_manager.get_foreign_keys(tabla)

    def get_unique_constraints(self, tabla: str) -> list:
        """Obtiene las restricciones únicas de una tabla (para compatibilidad)."""
        return self.db_manager.get_unique_constraints(tabla)

    def get_indices(self, tabla: str) -> list:
        """Obtiene los índices de una tabla (para compatibilidad)."""
        return self.db_manager.get_indices(tabla)

    def get_database_version(self) -> str | None:
        """Obtiene la versión de la base de datos (para compatibilidad con generadores)."""
        try:
            result: str = self.db_manager.get_database_version()
            self.logger.info(f"📋 Versión de BD obtenida: {result}")
            return result
        except Exception as e:
            self.logger.error(f"❌ Error al obtener versión de BD: {e}")
            return None

    def get_database_charset_collation(self) -> dict[str, Any] | None:
        """Obtiene charset y collation de la base de datos (para compatibilidad con generadores)."""
        try:
            result = self.db_manager.get_database_charset_collation()
            self.logger.info(f"📋 Charset/Collation de BD obtenido: {result}")
            return result
        except Exception as e:
            self.logger.error(f"❌ Error al obtener charset/collation de BD: {e}")
            return None

    def get_columns_charset_collation(self, tabla: str) -> list[tuple[str, str | None, str | None]] | None:
        """Obtiene charset y collation de las columnas de una tabla (para compatibilidad con generadores)."""
        try:
            result = self.db_manager.get_columns_charset_collation(tabla)
            self.logger.debug(f"📋 Charset/Collation de columnas de {tabla} obtenido")
            return result
        except Exception as e:
            self.logger.warning(f"⚠️  Error al obtener charset/collation de columnas de {tabla}: {e}")
            return None

    def _resolve_storage_tablespace(self) -> str:
        """Resuelve el tablespace para consultas de almacenamiento cuando aplica."""
        # Try configuration sources in order
        tablespace: str = self._get_configured_tablespace()
        if tablespace:
            return tablespace

        # Try database-specific defaults
        tablespace = self._get_default_database_tablespace()
        return tablespace

    def _get_configured_tablespace(self) -> str:
        """Obtiene tablespace desde configuración o parámetros de conexión."""
        storage_cfg: Any = self.imprimir_config.get("storage")
        if not isinstance(storage_cfg, dict):
            storage_cfg = self.imprimir_config.get("almacenamiento", {})
        if not isinstance(storage_cfg, dict):
            storage_cfg = {}

        cfg_tablespace: str = str(storage_cfg.get("tablespace", "") or "").strip()
        if cfg_tablespace:
            return cfg_tablespace

        conn_tablespace: str = str(self.db_manager.conn_params.get("tablespace", "") or "").strip()
        return conn_tablespace

    def _get_default_database_tablespace(self) -> str:
        """Obtiene tablespace por defecto según el tipo de motor."""
        if self.db_type == "oracle":
            return self._get_oracle_default_tablespace()
        elif self.db_type == "postgresql":
            return "pg_default"
        return ""

    def _get_oracle_default_tablespace(self) -> str:
        """Intenta obtener tablespace del usuario Oracle conectado."""
        try:
            user_tablespaces: Any = self.db_manager.execute_custom_one(
                self._ORACLE_USER_TABLESPACES_QUERY,
            )
            return self._extract_tablespace_from_row(user_tablespaces)
        except Exception:
            return ""

    def _extract_tablespace_from_row(self, row_data: Any) -> str:
        """Extrae tablespace válido de una fila de datos."""
        normalized_rows: list[list[Any]] = self._normalize_storage_rows(row_data)
        if not normalized_rows or not normalized_rows[0]:
            return ""

        row: list[Any] = normalized_rows[0]
        if len(row) > 0:
            default_ts: str = str(row[0] or "").strip()
            if default_ts:
                return default_ts

        if len(row) > 1:
            temp_ts: str = str(row[1] or "").strip()
            if temp_ts:
                return temp_ts

        return ""

    def _resolve_oracle_storage_tablespaces(self) -> dict[str, list[str]]:
        """Resuelve tablespaces Oracle separados por tipo (datos y temporales)."""
        data_candidates: list[str] = self._collect_oracle_data_tablespaces()
        temp_candidates: list[str] = self._collect_oracle_temp_tablespaces()

        return {
            "data_tablespaces": self._dedup_tablespaces(data_candidates),
            "temp_tablespaces": self._dedup_tablespaces(temp_candidates),
        }

    def _collect_oracle_data_tablespaces(self) -> list[str]:
        """Recolecta tablespaces de datos desde configuración y usuario Oracle."""
        data_candidates: list[str] = []

        storage_cfg: dict[str, Any] = self.imprimir_config.get("storage", {})
        cfg_tablespace: str = str(storage_cfg.get("tablespace", "") or "").strip()
        if cfg_tablespace:
            data_candidates.append(cfg_tablespace)

        conn_tablespace: str = str(self.db_manager.conn_params.get("tablespace", "") or "").strip()
        if conn_tablespace:
            data_candidates.append(conn_tablespace)

        try:
            user_tablespaces: Any = self.db_manager.execute_custom_one(
                self._ORACLE_USER_TABLESPACES_QUERY,
            )
            normalized_user_rows: list[list[Any]] = self._normalize_storage_rows(user_tablespaces)
            if normalized_user_rows and len(normalized_user_rows[0]) > 0:
                default_ts: str = str(normalized_user_rows[0][0] or "").strip()
                if default_ts:
                    data_candidates.append(default_ts)
        except Exception:
            pass

        return data_candidates

    def _collect_oracle_temp_tablespaces(self) -> list[str]:
        """Recolecta tablespaces temporales desde usuario Oracle."""
        temp_candidates: list[str] = []

        try:
            user_tablespaces: Any = self.db_manager.execute_custom_one(
                self._ORACLE_USER_TABLESPACES_QUERY,
            )
            normalized_user_rows: list[list[Any]] = self._normalize_storage_rows(user_tablespaces)
            if normalized_user_rows and len(normalized_user_rows[0]) > 1:
                temp_ts: str = str(normalized_user_rows[0][1] or "").strip()
                if temp_ts:
                    temp_candidates.append(temp_ts)
        except Exception:
            pass

        return temp_candidates

    def _dedup_tablespaces(self, values: list[str]) -> list[str]:
        """Deduplica y normaliza lista de tablespaces."""
        unique_values: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized: str = value.upper()
            if normalized not in seen:
                seen.add(normalized)
                unique_values.append(value)
        return unique_values

    def _normalize_storage_rows(self, rows: Any) -> list[list[Any]]:
        """Normaliza resultados de consulta a formato tabular homogéneo."""
        if rows is None:
            return []

        if not isinstance(rows, list):
            rows = [rows]

        normalized: list[list[Any]] = []
        for row in rows:
            if isinstance(row, (list, tuple)):
                normalized.append(list(row))
            else:
                normalized.append([row])
        return normalized

    @staticmethod
    def _parse_mariadb_size_to_mb(size_value: str) -> float | None:
        """Convierte tamaños MariaDB tipo 12M/5G a MB."""
        normalized: str = str(size_value or "").strip().upper()
        if not normalized:
            return None

        match = re.fullmatch(r"(\d+(?:\.\d+)?)([KMGT])?B?", normalized)
        if not match:
            return None

        magnitude: float = float(match.group(1))
        unit: str = str(match.group(2) or "M")
        factor_by_unit: dict[str, float] = {
            "K": 1 / 1024,
            "M": 1,
            "G": 1024,
            "T": 1024 * 1024,
        }
        return round(magnitude * factor_by_unit.get(unit, 1), 2)

    @classmethod
    def _parse_mariadb_temp_data_file_path_rows(cls, variable_name: str, raw_value: str) -> list[list[Any]]:
        """Parsea innodb_temp_data_file_path a filas tabulares."""
        value: str = str(raw_value or "").strip()
        if not value:
            return []

        parsed_rows: list[list[Any]] = []
        for chunk in [part.strip() for part in value.split(";") if part.strip()]:
            tokens: list[str] = [token.strip() for token in chunk.split(":") if token.strip()]
            if not tokens:
                continue

            file_name: str = tokens[0]
            initial_mb: float | str = ""
            autoextend: str = "No"
            max_mb: float | str = ""
            idx: int = 1

            if idx < len(tokens):
                parsed_initial: float | None = cls._parse_mariadb_size_to_mb(tokens[idx])
                if parsed_initial is not None:
                    initial_mb = parsed_initial
                    idx += 1

            while idx < len(tokens):
                current_token: str = tokens[idx].lower()
                if current_token == "autoextend":
                    autoextend = "Si"
                elif current_token == "max" and idx + 1 < len(tokens):
                    parsed_max: float | None = cls._parse_mariadb_size_to_mb(tokens[idx + 1])
                    if parsed_max is not None:
                        max_mb = parsed_max
                    idx += 1
                idx += 1

            parsed_rows.append([variable_name, file_name, initial_mb, autoextend, max_mb, value])

        return parsed_rows

    def _build_storage_query_specs(self) -> list[tuple[str, str]]:
        """Construye secciones de almacenamiento según el motor."""
        query_specs: list[tuple[str, str]] = [
            ("ficheros_fisicos", "Ficheros físicos"),
            ("ficheros_fisicos_adicional", "Ficheros físicos adicionales"),
            ("temp_tablespaces", "Temp tablespaces"),
        ]
        if self.db_type == "mariadb":
            query_specs.append(("temp_storage_variables", "Configuración temporales InnoDB"))
        return query_specs

    @staticmethod
    def _flatten_exception_messages(error: Exception) -> str:
        """Concatena mensajes de la cadena de excepciones."""
        messages: list[str] = []
        current: BaseException | None = error
        seen: set[int] = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            current_message: str = str(current).strip()
            if current_message:
                messages.append(current_message)
            current = current.__cause__ or current.__context__
        return " | ".join(messages)

    def _get_storage_headers_by_query(self, query_name: str) -> list[str]:
        """Devuelve cabeceras legibles por motor y consulta de almacenamiento."""
        headers_map: dict[str, dict[str, list[str]]] = {
            "mariadb": {
                "ficheros_fisicos": [
                    "DB",
                    "Objeto",
                    "Motor",
                    "Datos (MB)",
                    "Indices (MB)",
                    "Total (MB)",
                ],
                "ficheros_fisicos_adicional": [
                    "Tablespace",
                    self._ARCHIVO_FISICO,
                    "Tamano fichero (MB)",
                    "Tamano asignado (MB)",
                ],
                "temp_tablespaces": [
                    "Tablespace",
                    "Archivo",
                    "Extent (MB)",
                    "Inicial (MB)",
                    "Maximo (MB)",
                ],
                "temp_storage_variables": [
                    "Variable",
                    "Archivo",
                    "Inicial (MB)",
                    "Autoextend",
                    "Maximo (MB)",
                    "Valor bruto",
                ],
            },
            "oracle": {
                "ficheros_fisicos": [
                    "Tablespace",
                    "Archivo",
                    self._TAMANO_MB,
                    "Estado",
                    self._TIPO_FICHERO,
                    "Autoextensible",
                    "Maximo (MB)",
                ],
                "temp_tablespaces": [
                    "Tablespace",
                    "Archivo",
                    self._TAMANO_MB,
                    "Estado",
                    self._TIPO_FICHERO,
                    "Autoextensible",
                    "Maximo (MB)",
                ],
            },
            "postgresql": {
                "ficheros_fisicos": ["Tablespace", "Ruta filesystem", "Tamaño total"],
                "temp_tablespaces": ["Temp tablespaces"],
            },
            "sqlserver": {
                "ficheros_fisicos": [
                    "Database",
                    "Nombre logico",
                    self._TIPO_FICHERO,
                    self._ARCHIVO_FISICO,
                    self._TAMANO_MB,
                    "Tamano maximo (MB)",
                    "Crecimiento en porcentaje",
                    "Configuracion crecimiento",
                ],
                "temp_tablespaces": [
                    "Database",
                    "Nombre logico",
                    self._TIPO_FICHERO,
                    self._ARCHIVO_FISICO,
                    self._TAMANO_MB,
                    "Tamano maximo (MB)",
                    "Crecimiento en porcentaje",
                    "Configuracion crecimiento",
                ],
            },
            "sqlite": {
                "ficheros_fisicos": ["Seq", "Nombre", "Archivo"],
                "ficheros_fisicos_adicional": ["Page count", "Page size", "Size bytes"],
                "temp_tablespaces": ["Temp store"],
            },
            "hsqldb": {
                "temp_tablespaces": ["Temp tablespace"],
            },
        }
        return headers_map.get(self.db_type, {}).get(query_name, [])

    def _build_storage_headers(self, query_name: str, rows: list[list[Any]]) -> list[str]:
        """Construye cabeceras legibles; si no hay mapeo usa fallback genérico."""
        preferred_headers: list[str] = self._get_storage_headers_by_query(query_name=query_name)
        if preferred_headers:
            if rows:
                max_cols: int = max(len(row) for row in rows)
                if max_cols > 0:
                    return preferred_headers[:max_cols]
            return preferred_headers
        if not rows:
            return []
        max_cols: int = max(len(row) for row in rows)
        return [f"Columna {idx}" for idx in range(1, max_cols + 1)]

    def _is_size_header(self, header: str) -> bool:
        """Indica si una cabecera corresponde a un valor de tamaño."""
        normalized: str = str(header or "").strip().lower()
        return any(hint in normalized for hint in self._SIZE_HEADER_HINTS)

    def _format_spanish_decimal(self, value: Any) -> Any:
        """Convierte separador decimal de punto a coma en valores numéricos."""
        if value is None:
            return ""

        if isinstance(value, (int, bool)):
            return value

        if isinstance(value, float):
            return f"{value:.2f}".replace(".", ",")

        text_value: str = str(value)
        normalized_numeric: str = text_value.replace(",", ".")
        if re.fullmatch(r"-?\d+(\.\d+)?", normalized_numeric):
            return f"{float(normalized_numeric):.2f}".replace(".", ",")
        return value

    def _format_storage_rows(self, headers: list[str], rows: list[list[Any]]) -> list[list[Any]]:
        """Formatea filas de almacenamiento aplicando formato español en tamaños."""
        if not rows:
            return rows

        formatted_rows: list[list[Any]] = []
        for row in rows:
            formatted_row: list[Any] = []
            for idx, value in enumerate(row):
                header: str = headers[idx] if idx < len(headers) else ""
                if self._is_size_header(header):
                    formatted_row.append(self._format_spanish_decimal(value))
                else:
                    formatted_row.append(value)
            formatted_rows.append(formatted_row)
        return formatted_rows

    def _get_numeric_storage_indices(self, headers: list[str]) -> list[int]:
        """Devuelve índices de columnas numéricas de almacenamiento."""
        return [idx for idx, header in enumerate(headers) if self._is_size_header(header)]

    def _is_placeholder_storage_query(self, query_name: str, query_params: dict[str, Any]) -> bool:
        """Indica si la query de almacenamiento es un placeholder de no soporte."""
        try:
            sql_text: str = str(self.db_manager.resolve_query(query_name, **query_params).final_sql or "")
        except Exception:
            return False
        normalized_sql: str = " ".join(sql_text.strip().lower().split())
        return "where 1=0" in normalized_sql

    def get_storage_inventory_report(self) -> dict[str, Any]:
        """Obtiene informe unificado de almacenamiento para Word/Excel/HTML.

        Returns:
            Diccionario con resumen y detalle por consulta de almacenamiento.
        """
        query_specs: list[tuple[str, str]] = self._build_storage_query_specs()
        database_name: str = str(self.database or "").strip()
        tablespace: str = self._resolve_storage_tablespace()
        query_params: dict[str, Any] = {"database": database_name, "tablespace": tablespace}

        sections: list[dict[str, Any]] = []
        for query_name, query_title in query_specs:
            section: dict[str, Any] = self.__process_storage_query(query_name, query_title, database_name, query_params)
            sections.append(section)

        total_rows: int = sum(len(section.get("rows", [])) for section in sections if section.get("status") == "ok")
        return {
            "db_type": self.db_type,
            "database": self.database,
            "tablespace": tablespace,
            "total_rows": total_rows,
            "sections": sections,
        }

    def __process_storage_query(
        self, query_name: str, query_title: str, database_name: str, query_params: dict[str, Any]
    ) -> dict[str, Any]:
        """Procesa una consulta individual de almacenamiento.

        Args:
            query_name: Nombre de la consulta
            query_title: Título descriptivo
            database_name: Nombre de base de datos
            query_params: Parámetros de consulta

        Returns:
            Sección de resultado con estructura de informe.
        """
        if self.db_type == "oracle" and query_name in {"ficheros_fisicos", "temp_tablespaces"}:
            return self.__process_oracle_storage_query(query_name, query_title, database_name)
        if self.db_type == "mariadb" and query_name == "temp_storage_variables":
            return self.__process_mariadb_temp_storage_variables_query(query_name, query_title, query_params)

        return self.__process_standard_storage_query(query_name, query_title, query_params)

    def __process_mariadb_temp_storage_variables_query(
        self, query_name: str, query_title: str, query_params: dict[str, Any]
    ) -> dict[str, Any]:
        """Procesa configuración temporal MariaDB basada en SHOW VARIABLES."""
        try:
            resolved = self.db_manager.resolve_query(query_name, **query_params)
        except QueryNotFoundError:
            return self.__build_section_not_supported(query_name, query_title)
        except Exception as error:
            return self.__build_section_missing_params(
                query_name,
                query_title,
                f"Parámetros inválidos: {error}",
            )

        try:
            sql_text: str = str(resolved.final_sql or "")
            result_rows: Any = self.db_manager.execute_query_many(query_name, **query_params)
            normalized_rows: list[list[Any]] = self._normalize_storage_rows(result_rows)
            parsed_rows: list[list[Any]] = []
            for row in normalized_rows:
                variable_name: str = str(row[0]) if len(row) > 0 else "innodb_temp_data_file_path"
                raw_value: str = str(row[1]) if len(row) > 1 else ""
                parsed_rows.extend(self._parse_mariadb_temp_data_file_path_rows(variable_name, raw_value))

            headers: list[str] = self._build_storage_headers(query_name=query_name, rows=parsed_rows)
            parsed_rows = self._format_storage_rows(headers=headers, rows=parsed_rows)
            message: str = (
                "OK. La variable describe tamano inicial, autoextend y maximo del temporal InnoDB."
                if parsed_rows
                else "La variable innodb_temp_data_file_path no devolvio datos utilizables."
            )
            return {
                "query": query_name,
                "title": query_title,
                "status": "ok",
                "message": message,
                "sql": sql_text,
                "headers": headers,
                "rows": parsed_rows,
                "numeric_columns": self._get_numeric_storage_indices(headers),
            }
        except Exception as error:
            return self.__build_section_error(query_name, query_title, self._flatten_exception_messages(error))

    def __process_oracle_storage_query(self, query_name: str, query_title: str, database_name: str) -> dict[str, Any]:
        """Procesa consulta de almacenamiento específica para Oracle.

        Args:
            query_name: Nombre de la consulta
            query_title: Título descriptivo
            database_name: Nombre de base de datos

        Returns:
            Sección de resultado.
        """
        oracle_targets: dict[str, list[str]] = self._resolve_oracle_storage_tablespaces()
        oracle_tablespaces: list[str] = (
            oracle_targets.get("data_tablespaces", [])
            if query_name == "ficheros_fisicos"
            else oracle_targets.get("temp_tablespaces", [])
        )
        if not oracle_tablespaces:
            return self.__build_section_missing_params(
                query_name,
                query_title,
                "No se pudieron resolver tablespaces Oracle para la consulta.",
            )

        collected_rows, collected_sql, collected_errors = self.__collect_oracle_tablespace_data(
            query_name, database_name, oracle_tablespaces
        )
        dedup_rows: list[list[Any]] = self.__deduplicate_rows(collected_rows)
        headers: list[str] = self._build_storage_headers(query_name=query_name, rows=dedup_rows)
        dedup_rows = self._format_storage_rows(headers=headers, rows=dedup_rows)

        return self.__build_oracle_section(
            query_name,
            query_title,
            dedup_rows,
            headers,
            len(oracle_tablespaces),
            collected_errors,
            collected_sql,
        )

    def __collect_oracle_tablespace_data(
        self, query_name: str, database_name: str, oracle_tablespaces: list[str]
    ) -> tuple[list[list[Any]], list[str], list[str]]:
        """Recolecta datos de tablespaces Oracle.

        Args:
            query_name: Nombre de la consulta
            database_name: Nombre de base de datos
            oracle_tablespaces: Lista de tablespaces

        Returns:
            Tupla (filas recolectadas, SQL ejecutado, errores).
        """
        collected_rows: list[list[Any]] = []
        collected_sql: list[str] = []
        collected_errors: list[str] = []

        for tablespace_name in oracle_tablespaces:
            local_params: dict[str, Any] = {
                "database": database_name,
                "tablespace": tablespace_name,
            }
            try:
                sql_text: str = str(self.db_manager.resolve_query(query_name, **local_params).final_sql or "")
                result_rows: Any = self.db_manager.execute_query_many(query_name, **local_params)
                rows: list[list[Any]] = self._normalize_storage_rows(result_rows)
                collected_rows.extend(rows)
                collected_sql.append(sql_text)
            except Exception as error:
                collected_errors.append(f"{tablespace_name}: {error}")

        return collected_rows, collected_sql, collected_errors

    def __deduplicate_rows(self, rows: list[list[Any]]) -> list[list[Any]]:
        """Deduplica filas.

        Args:
            rows: Filas a deduplicar

        Returns:
            Filas sin duplicados.
        """
        dedup_rows: list[list[Any]] = []
        seen_rows: set[tuple[Any, ...]] = set()
        for row in rows:
            row_key: tuple[Any, ...] = tuple(row)
            if row_key not in seen_rows:
                seen_rows.add(row_key)
                dedup_rows.append(row)
        return dedup_rows

    def __build_oracle_section(
        self,
        query_name: str,
        query_title: str,
        rows: list[list[Any]],
        headers: list[str],
        tablespace_count: int,
        errors: list[str],
        sql_list: list[str],
    ) -> dict[str, Any]:
        """Construye sección de resultado para Oracle.

        Args:
            query_name: Nombre de la consulta
            query_title: Título descriptivo
            rows: Filas de datos
            headers: Cabeceras
            tablespace_count: Número de tablespaces procesados
            errors: Errores recolectados
            sql_list: Sentencias SQL ejecutadas

        Returns:
            Sección de resultado.
        """
        if rows:
            message: str = f"OK ({tablespace_count} tablespace(s) consultado(s))"
            if errors:
                message = f"{message}. Con incidencias parciales: {' | '.join(errors)}"
            return {
                "query": query_name,
                "title": query_title,
                "status": "ok",
                "message": message,
                "sql": "\n\n".join(sql_list),
                "headers": headers,
                "rows": rows,
                "numeric_columns": self._get_numeric_storage_indices(headers),
            }
        else:
            status: str = "error" if errors else "ok"
            message = "Sin datos"
            if errors:
                message = f"Error ejecutando consulta: {' | '.join(errors)}"
            return {
                "query": query_name,
                "title": query_title,
                "status": status,
                "message": message,
                "sql": "\n\n".join(sql_list),
                "headers": headers,
                "rows": rows,
                "numeric_columns": self._get_numeric_storage_indices(headers),
            }

    def __process_standard_storage_query(
        self, query_name: str, query_title: str, query_params: dict[str, Any]
    ) -> dict[str, Any]:
        """Procesa consulta de almacenamiento estándar (no Oracle).

        Args:
            query_name: Nombre de la consulta
            query_title: Título descriptivo
            query_params: Parámetros de consulta

        Returns:
            Sección de resultado.
        """
        try:
            resolved = self.db_manager.resolve_query(query_name, **query_params)
        except QueryNotFoundError:
            return self.__build_section_not_supported(query_name, query_title)
        except Exception as e:
            # Si falla la validación, retornar sección de parámetros faltantes
            error_msg: str = str(e)
            return self.__build_section_missing_params(
                query_name,
                query_title,
                f"Parámetros inválidos: {error_msg}",
            )

        if self._is_placeholder_storage_query(query_name=query_name, query_params=query_params):
            return self.__build_section_not_supported(query_name, query_title)

        try:
            sql_text: str = str(resolved.final_sql or "")
            result_rows: Any = self.db_manager.execute_query_many(query_name, **query_params)
            rows: list[list[Any]] = self._normalize_storage_rows(result_rows)
            headers: list[str] = self._build_storage_headers(query_name=query_name, rows=rows)
            rows = self._format_storage_rows(headers=headers, rows=rows)
            return {
                "query": query_name,
                "title": query_title,
                "status": "ok",
                "message": "OK" if rows else "Sin datos",
                "sql": sql_text,
                "headers": headers,
                "rows": rows,
                "numeric_columns": self._get_numeric_storage_indices(headers),
            }
        except Exception as error:
            error_msg: str = self._flatten_exception_messages(error)
            if self.db_type == "mariadb" and query_name == "temp_tablespaces":
                return self.__build_mariadb_temp_tablespaces_error_section(query_name, query_title, error_msg)
            return self.__build_section_error(query_name, query_title, error_msg)

    def __build_mariadb_temp_tablespaces_error_section(
        self, query_name: str, query_title: str, error_msg: str
    ) -> dict[str, Any]:
        """Construye mensaje explícito para incidencias de information_schema.FILES."""
        normalized_error: str = str(error_msg or "").strip()
        lowered_error: str = normalized_error.lower()

        if (
            "information_schema.files" in lowered_error
            and any(token in lowered_error for token in ("access denied", "permission", "denied", "1142", "1227"))
        ):
            return {
                "query": query_name,
                "title": query_title,
                "status": "error",
                "message": (
                    "Sin acceso a information_schema.FILES. No se puede inventariar el almacenamiento temporal "
                    "detallado con el usuario actual."
                ),
                "sql": "",
                "headers": [],
                "rows": [],
                "numeric_columns": [],
            }

        if "information_schema.files" in lowered_error and any(
            token in lowered_error for token in ("doesn't exist", "does not exist", "unknown table", "unknown column")
        ):
            return {
                "query": query_name,
                "title": query_title,
                "status": "not_supported",
                "message": (
                    "MariaDB no expone information_schema.FILES en este entorno. No se dispone de inventario "
                    "detallado de ficheros temporales."
                ),
                "sql": "",
                "headers": [],
                "rows": [],
                "numeric_columns": [],
            }

        return self.__build_section_error(query_name, query_title, normalized_error)

    def __build_section_not_supported(self, query_name: str, query_title: str) -> dict[str, Any]:
        """Construye sección de resultado para consultas no soportadas.

        Args:
            query_name: Nombre de la consulta
            query_title: Título descriptivo

        Returns:
            Sección de resultado.
        """
        return {
            "query": query_name,
            "title": query_title,
            "status": "not_supported",
            "message": "No disponible para este motor de base de datos.",
            "sql": "",
            "headers": [],
            "rows": [],
            "numeric_columns": [],
        }

    def __build_section_missing_params(self, query_name: str, query_title: str, message: str) -> dict[str, Any]:
        """Construye sección de resultado para parámetros faltantes.

        Args:
            query_name: Nombre de la consulta
            query_title: Título descriptivo
            message: Mensaje de error

        Returns:
            Sección de resultado.
        """
        return {
            "query": query_name,
            "title": query_title,
            "status": "missing_params",
            "message": message,
            "sql": "",
            "headers": [],
            "rows": [],
            "numeric_columns": [],
        }

    def __build_section_error(self, query_name: str, query_title: str, error_msg: str) -> dict[str, Any]:
        """Construye sección de resultado para errores.

        Args:
            query_name: Nombre de la consulta
            query_title: Título descriptivo
            error_msg: Mensaje de error

        Returns:
            Sección de resultado.
        """
        return {
            "query": query_name,
            "title": query_title,
            "status": "error",
            "message": f"Error ejecutando consulta: {error_msg}",
            "sql": "",
            "headers": [],
            "rows": [],
            "numeric_columns": [],
        }

    _SIZE_HEADER_HINTS: tuple[str, ...] = ("mb", "tamano", "tamaño", "size")
    _AUTO_OUTPUT_BATCH_WINDOW_SECONDS: int = 90
    _LAST_AUTO_OUTPUT_BY_KEY: dict[tuple[str, str], tuple[float, str]] = {}
    _ORACLE_USER_TABLESPACES_QUERY: str = "SELECT default_tablespace, temporary_tablespace FROM user_users"
