"""
Clase unificada para generar documentación de bases de datos (MariaDB/Oracle/PostgreSQL/HSQLDB) en Word o Excel.
Versión refactorizada con arquitectura modular.
"""

import logging

from pathlib import Path
from typing import Any

# Importar módulos modulares
from ..analysis.graphviz_ext import GraphvizRelationshipGraphExt
from ..managers import SyncDatabaseManager
from ._documentation_orchestrator import (
    DocumentationBootstrap,
    DocumentationOrchestrator,
    DocumentationOutputPlanner,
    DocumentationSession,
)
from .excel_generator import ExcelGenerator
from .html_generator import HtmlGenerator
from .word_generator import WordGenerator


class DatabaseDocumentation:
    """Clase unificada para generar documentación de bases de datos usando arquitectura modular.

    La fachada pública se limita a orquestar la generación documental. Las consultas
    de metadatos y DDL deben realizarse a través de `SyncDatabaseManager` o de las
    sesiones internas usadas por los generadores.

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

        bootstrap_state = DocumentationBootstrap(
            db_manager=db_manager,
            directorio_salida=directorio_salida,
            fichero_salida=fichero_salida,
            imprimir=imprimir,
            formatos=formatos,
            headers_file=headers_file,
            output_cache=self._LAST_AUTO_OUTPUT_BY_KEY,
            batch_window_seconds=self._AUTO_OUTPUT_BATCH_WINDOW_SECONDS,
        ).build()

        self.db_manager = bootstrap_state.db_manager
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
        self._bind_documentation_session(DocumentationSession.from_documentation(self))
        self._create_documents()

    def _bind_documentation_session(self, session: DocumentationSession) -> None:
        """Sincroniza la sesión documental interna usada por el orquestador."""
        self._documentation_session = session

    def _create_documents(self) -> None:
        """Genera documentación para todos los formatos solicitados."""
        DocumentationOrchestrator(
            session=self._documentation_session,
            planner=DocumentationOutputPlanner(self._documentation_session),
            graph_generator_cls=GraphvizRelationshipGraphExt,
            word_generator_cls=WordGenerator,
            excel_generator_cls=ExcelGenerator,
            html_generator_cls=HtmlGenerator,
        ).generate_documents()

    _AUTO_OUTPUT_BATCH_WINDOW_SECONDS: int = 90
    _LAST_AUTO_OUTPUT_BY_KEY: dict[tuple[str, str], tuple[float, str]] = {}
