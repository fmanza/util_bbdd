"""
Clase unificada para generar documentación de bases de datos (MariaDB/Oracle/PostgreSQL/HSQLDB) en Word o Excel.
Versión refactorizada con arquitectura modular.
"""

import logging
import time

from datetime import datetime
from pathlib import Path
from typing import Any

# Importar módulos modulares
from ..analysis.graphviz_ext import GraphvizRelationshipGraphExt
from ..managers import SyncDatabaseManager
from ._documentation_runtime import (
    build_headers,
    ensure_execution_root,
    get_execution_root_name,
    get_format_output_dir,
    get_output_base_filename,
    load_headers_config,
    normalize_output_formats,
    normalize_sqlite_identifier,
    resolve_generator_database_context,
    resolve_output_filename_identifier,
)
from ._storage_inventory_runtime import StorageInventoryRuntime
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
            - grafo.max_depth: Profundidad máxima visible de relaciones (default 1)
            - grafo.direction: Dirección del recorrido: incoming, outgoing o both
            - grafo.images_paginated: Si True, genera imágenes por paginación
            - grafo.max_subnodes: Máximo de subnodos/tablas por imagen paginada (default 10)
            - grafo.columns.mode: compact, relations o all
            - grafo.columns.max_items: Límite de columnas visibles en modo compact
        formatos: Lista de formatos de salida a generar. Valores soportados: 'word', 'excel', 'html'
        headers_file: Ruta al fichero JSON con configuración de headers
    """

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
        return resolve_output_filename_identifier(self.db_manager.db_type, self.db_manager.database, conn_params)

    def _normalize_sqlite_identifier(self, identifier: str) -> str:
        """Normaliza identificador SQLite extrayendo nombre de archivo.

        Args:
            identifier: Ruta o nombre de archivo SQLite.

        Returns:
            Nombre de archivo SQLite sin extensión.
        """
        return normalize_sqlite_identifier(identifier)

    def _load_headers_config(self, headers_file: Path) -> dict:
        """Carga la configuración de headers desde el fichero JSON."""
        return load_headers_config(headers_file)

    def _build_headers(self) -> dict:
        """Construye los headers dinámicamente según el tipo de base de datos."""
        return build_headers(self.headers_config, self.db_manager.db_type)

    def _normalize_output_formats(self, formatos: list[str] | None) -> list[str]:
        """Normaliza y valida formatos de salida solicitados."""
        return normalize_output_formats(formatos)

    def _create_documents(self) -> None:
        """Genera documentación para todos los formatos solicitados."""
        shared_graph_generator: GraphvizRelationshipGraphExt | None = self._build_shared_graph_generator()
        for output_format in self.formatos:
            if output_format == "word":
                self._create_document_word(graph_generator=shared_graph_generator)
            elif output_format == "excel":
                self._create_document_excel()
            elif output_format == "html":
                self._create_document_html(graph_generator=shared_graph_generator)

    def _build_shared_graph_generator(self) -> GraphvizRelationshipGraphExt | None:
        """Construye un generador de grafos compartido para Word y HTML cuando ambos formatos lo requieren."""
        if not self._should_share_graph_generator():
            return None

        graph_cfg: dict[str, Any] = self.imprimir_config.get("grafo", {})
        columns_options: dict[str, Any] = dict(graph_cfg.get("columns", {}))
        cardinality_options: dict[str, Any] = dict(graph_cfg.get("cardinality", {}))

        self.logger.debug("🟢 Inicializando generador de grafos compartido para Word y HTML")
        return GraphvizRelationshipGraphExt(
            db_manager=self.db_manager,
            column_mode=str(columns_options.get("mode", "relations")),
            max_columns=int(columns_options.get("max_items", 8)),
            show_data_types=bool(columns_options.get("show_data_types", False)),
            max_depth=int(graph_cfg.get("max_depth", 1)),
            direction=str(graph_cfg.get("direction", "both")),
            show_constraint_name=bool(cardinality_options.get("show_constraint_name", False)),
            render_dpi=int(graph_cfg.get("dpi", 150)),
        )

    def _should_share_graph_generator(self) -> bool:
        """Indica si esta ejecución puede reutilizar un único generador de grafos entre formatos."""
        if not {"word", "html"}.issubset(set(self.formatos)):
            return False

        graph_cfg: dict[str, Any] = self.imprimir_config.get("grafo", {})
        return bool(graph_cfg.get("enabled", False))

    def _create_document_word(self, graph_generator: GraphvizRelationshipGraphExt | None = None) -> None:
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
            graph_generator=graph_generator,
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

    def _create_document_html(self, graph_generator: GraphvizRelationshipGraphExt | None = None) -> None:
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
            graph_generator=graph_generator,
        )

    def _get_execution_root_name(self) -> str:
        """Obtiene nombre de carpeta raíz por ejecución (igual al nombre histórico de carpeta HTML)."""
        return get_execution_root_name(self.fichero_salida)

    def _get_output_base_filename(self) -> str:
        """Obtiene nombre base de archivo para salidas Word/Excel."""
        return get_output_base_filename(self.fichero_salida)

    def _ensure_execution_root(self) -> Path:
        """Crea (si no existe) carpeta raíz por ejecución."""
        return ensure_execution_root(self.directorio_salida, self.fichero_salida)

    def _get_format_output_dir(self, formato: str) -> Path:
        """Obtiene y crea solo la subcarpeta del formato solicitado."""
        return get_format_output_dir(self.directorio_salida, self.fichero_salida, formato)

    def _get_generator_database_context(self) -> str:
        """Obtiene identificador de contexto para generadores de documentación.

        Returns:
            Nombre de base/esquema a mostrar en encabezados y metadatos de salida.

        Notes:
            - En Oracle se prioriza `user` (owner/schema) por compatibilidad.
            - En otros motores se usa `database` con fallback a `user` y db_type.
        """
        query_context = str(self.db_manager.get_query_context_database() or "").strip()
        return resolve_generator_database_context(
            db_type=self.db_manager.db_type,
            database=self.db_manager.database,
            conn_params=self.db_manager.conn_params or {},
            query_context_database=query_context,
        )

    def _resolve_context_by_db_type(self) -> str:
        """Resuelve el contexto de base de datos según el tipo de motor.

        Returns:
            Nombre normalizado de base/esquema/usuario según el motor.
        """
        return resolve_generator_database_context(
            db_type=self.db_manager.db_type,
            database=self.db_manager.database,
            conn_params=self.db_manager.conn_params or {},
            query_context_database="",
        )

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

    @staticmethod
    def _parse_mariadb_size_to_mb(size_value: str) -> float | None:
        """Compatibilidad histórica para parseo de tamaños temporales MariaDB."""
        return StorageInventoryRuntime._parse_mariadb_size_to_mb(size_value)

    @classmethod
    def _parse_mariadb_temp_data_file_path_rows(cls, variable_name: str, raw_value: str) -> list[list[Any]]:
        """Compatibilidad histórica para parseo de innodb_temp_data_file_path."""
        return StorageInventoryRuntime._parse_mariadb_temp_data_file_path_rows(variable_name, raw_value)

    def _get_storage_inventory_runtime(self) -> StorageInventoryRuntime:
        """Construye el runtime interno compartido para almacenamiento documental."""
        db_manager: SyncDatabaseManager = self.db_manager
        logger = getattr(self, "logger", logging.getLogger(__name__))
        db_type = str(getattr(db_manager, "db_type", "") or "")
        database = str(getattr(db_manager, "database", "") or "")
        print_config = getattr(self, "imprimir_config", {})
        return StorageInventoryRuntime(
            db_manager=db_manager,
            logger=logger,
            db_type=db_type,
            database=database,
            print_config=print_config,
        )

    def _build_storage_query_specs(self) -> list[tuple[str, str]]:
        """Compatibilidad histórica para el inventario de secciones de almacenamiento."""
        return self._get_storage_inventory_runtime()._build_storage_query_specs()

    def __build_mariadb_temp_tablespaces_error_section(
        self, query_name: str, query_title: str, error_msg: str
    ) -> dict[str, Any]:
        """Compatibilidad histórica para el formateo de errores de information_schema.FILES."""
        return self._get_storage_inventory_runtime()._build_mariadb_temp_tablespaces_error_section(
            query_name,
            query_title,
            error_msg,
        )

    def get_storage_inventory_report(self) -> dict[str, Any]:
        """Obtiene informe unificado de almacenamiento para Word/Excel/HTML.

        Returns:
            Diccionario con resumen y detalle por consulta de almacenamiento.
        """
        return self._get_storage_inventory_runtime().get_storage_inventory_report()

    _AUTO_OUTPUT_BATCH_WINDOW_SECONDS: int = 90
    _LAST_AUTO_OUTPUT_BY_KEY: dict[tuple[str, str], tuple[float, str]] = {}
