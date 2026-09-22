"""
Clase unificada para generar documentación de bases de datos (MariaDB/Oracle/PostgreSQL/HSQLDB) en Word o Excel.
Versión refactorizada con arquitectura modular.
"""

import logging

from pathlib import Path
from typing import Any, ClassVar

# Importar módulos modulares
from ..analysis.graphviz_ext import GraphvizRelationshipGraphExt
from .application.ports import DocumentationManagerPort, DocumentationSourcePort, LoggerProtocol
from .application.use_cases.documentation_orchestrator import (
    DocumentationBootstrap,
    DocumentationFacade,
    DocumentationOrchestrator,
    DocumentationOutputPlanner,
    DocumentationSession,
)
from .infrastructure.adapters.sync_database_manager_adapter import SyncDatabaseManagerAdapter
from .infrastructure.renderers.excel_generator import ExcelGenerator
from .infrastructure.renderers.html_generator import HtmlGenerator
from .infrastructure.renderers.registry import DocumentationRendererRegistry, build_default_renderer_registry
from .infrastructure.renderers.shared.print_config_manager import PrintConfigManager
from .infrastructure.renderers.word_generator import WordGenerator
from .infrastructure.runtime.headers_runtime import DocumentationHeadersRuntime
from .infrastructure.runtime.metadata_runtime import DocumentationMetadataRuntimeFactory
from .infrastructure.runtime.output_runtime import DocumentationOutputRuntime
from .infrastructure.storage.runtime import StorageInventoryReportService


class DatabaseDocumentation:
    """Clase unificada para generar documentación de bases de datos usando arquitectura modular.

    La fachada pública se limita a orquestar la generación documental. Las consultas
    de metadatos y DDL deben realizarse a través de `SyncDatabaseManager` o de las
    sesiones internas usadas por los generadores.

    Args:
        db_manager: Fuente de metadatos y consultas (``DocumentationSourcePort``), normalmente una instancia de
            SyncDatabaseManager ya configurada
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

    logger: LoggerProtocol
    db_manager: DocumentationManagerPort
    imprimir_config: dict[str, Any]
    formatos: list[str]
    directorio_salida: Path
    fichero_salida: Path
    table_style: str
    headers_config: dict[str, Any]
    headers: dict[str, list[str]]
    tablas: list[Any]
    vistas: list[Any]
    rutinas: list[Any]
    _documentation_session: DocumentationSession
    _output_policy: DocumentationOutputRuntime
    _headers_runtime: DocumentationHeadersRuntime
    _metadata_runtime_factory: DocumentationMetadataRuntimeFactory
    _storage_report_service: StorageInventoryReportService
    _renderer_registry: DocumentationRendererRegistry

    _AUTO_OUTPUT_BATCH_WINDOW_SECONDS: ClassVar[int] = 90
    _LAST_AUTO_OUTPUT_BY_KEY: ClassVar[dict[tuple[str, str], tuple[float, str]]] = {}

    def __init__(
        self,
        db_manager: DocumentationSourcePort,
        directorio_salida: Path = Path(""),
        fichero_salida: Path | None = None,
        imprimir: dict[str, Any] | None = None,
        formatos: list[str] | None = None,
        headers_file: Path = Path(__file__).parent / "data/headers_config.json",
    ) -> None:
        # Configurar logger
        self.logger: LoggerProtocol = logging.getLogger(__name__)
        self._output_policy = DocumentationOutputRuntime()
        self._headers_runtime = DocumentationHeadersRuntime()
        self._metadata_runtime_factory = DocumentationMetadataRuntimeFactory()
        self._storage_report_service = StorageInventoryReportService()
        self._renderer_registry = build_default_renderer_registry(
            word_generator_cls=WordGenerator,
            excel_generator_cls=ExcelGenerator,
            html_generator_cls=HtmlGenerator,
        )
        adapted_manager = SyncDatabaseManagerAdapter(db_manager, imprimir or {})

        bootstrap_state = DocumentationBootstrap(
            db_manager=adapted_manager,
            directorio_salida=directorio_salida,
            fichero_salida=fichero_salida,
            imprimir=imprimir,
            formatos=formatos,
            headers_file=headers_file,
            output_cache=self._LAST_AUTO_OUTPUT_BY_KEY,
            batch_window_seconds=self._AUTO_OUTPUT_BATCH_WINDOW_SECONDS,
            print_config_policy=PrintConfigManager(),
            headers_runtime=self._headers_runtime,
            output_policy=self._output_policy,
        ).build()

        self.db_manager = adapted_manager
        self.imprimir_config = bootstrap_state.print_config
        self.formatos = bootstrap_state.formatos
        self.directorio_salida = bootstrap_state.directorio_salida
        self.fichero_salida = bootstrap_state.fichero_salida
        self.table_style = bootstrap_state.table_style
        self.headers_config = bootstrap_state.headers_config
        self.headers = bootstrap_state.headers
        self.tablas = bootstrap_state.tablas
        self.vistas = bootstrap_state.vistas
        self.rutinas = bootstrap_state.rutinas
        documentation_facade: DocumentationFacade = self
        self._bind_documentation_session(
            DocumentationSession.from_documentation(
                documentation_facade,
                output_policy=self._output_policy,
                metadata_runtime_factory=self._metadata_runtime_factory,
                storage_report_service=self._storage_report_service,
            )
        )

    def _bind_documentation_session(self, session: DocumentationSession) -> None:
        """Sincroniza la sesión documental interna usada por el orquestador."""
        self._documentation_session = session

    def generate(self) -> None:
        """Genera documentación para todos los formatos solicitados.

        Separado de ``__init__`` para permitir instanciar la clase sin ejecutar I/O.
        Llamar explícitamente después de configurar la instancia.

        Example:
            >>> doc = DatabaseDocumentation(db_manager, output_dir)
            >>> doc.generate()
        """
        DocumentationOrchestrator(
            session=self._documentation_session,
            planner=DocumentationOutputPlanner(self._documentation_session, self._renderer_registry),
            renderer_registry=self._renderer_registry,
            graph_generator_cls=GraphvizRelationshipGraphExt,
        ).generate_documents()
