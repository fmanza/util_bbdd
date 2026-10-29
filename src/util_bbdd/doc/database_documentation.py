"""Documentación de una base de datos (cualquier motor soportado) en Word, Excel y HTML."""

from __future__ import annotations

import logging
import threading

from pathlib import Path
from typing import Any, ClassVar

from .._core.exceptions import DocumentationConfigError
from ..progress import CancellationToken, ProgressCallback, ProgressReporter
from .application.ports import DocumentationSourcePort, OutputCache
from .application.use_cases.documentation_orchestrator import (
    DocumentationBootstrap,
    DocumentationOrchestrator,
    DocumentationOutputPlanner,
    DocumentationSession,
)
from .domain.models import DocumentationResult, DocumentationSettings
from .infrastructure.adapters.sync_database_manager_adapter import SyncDatabaseManagerAdapter
from .infrastructure.renderers.excel_generator import ExcelGenerator
from .infrastructure.renderers.excel_template import ExcelTemplate
from .infrastructure.renderers.html_generator import HtmlGenerator
from .infrastructure.renderers.registry import build_default_renderer_registry
from .infrastructure.renderers.shared.generator_shared import build_graph_generator_from_options
from .infrastructure.renderers.shared.print_config_manager import PrintConfigManager
from .infrastructure.renderers.word_generator import WordGenerator
from .infrastructure.renderers.word_template import WordTemplateValidator
from .infrastructure.runtime.headers_runtime import DocumentationHeadersRuntime
from .infrastructure.runtime.metadata_runtime import DocumentationMetadataRuntimeFactory
from .infrastructure.runtime.output_runtime import DocumentationOutputRuntime
from .infrastructure.storage.runtime import StorageInventoryReportService

_DEFAULT_HEADERS_FILE: Path = Path(__file__).parent / "data" / "headers_config.json"


class DatabaseDocumentation:
    """Genera la documentación de un schema en Word, Excel y/o HTML a partir de sus metadatos.

    Crear la instancia solo valida la configuración (no consulta la base de datos); :meth:`generate` lee el catálogo
    por lotes (ADR-003) y escribe los documentos.

    Args:
        db_manager: Fuente de metadatos (``DocumentationSourcePort``), normalmente un ``SyncDatabaseManager``.
        directorio_salida: Directorio de salida. Cada generación crea en él una carpeta con una subcarpeta por formato.
        fichero_salida: Nombre base de la salida (sin extensión). Si es None, se genera automático como
            ``<base de datos>-<fecha_hora>``, único por generación (con sufijo ``-2``, ``-3``… si coincide en el mismo
            segundo) o, con ``batch_window_seconds`` > 0, reutilizado por las generaciones lanzadas dentro de la
            ventana para agruparlas en la misma carpeta.
        imprimir: Secciones y opciones (ver ``docs/api/database_documentation.md``), entre ellas:
            - plantilla_word: Ruta opcional a plantilla Word (.docx)
            - plantilla_excel: Ruta opcional a plantilla Excel (.xlsx o .xltx): tema, fuentes, encabezado, pie y
              página (desde 4.1.0)
            - table_style_excel: Estilo de tabla del Excel (``TableStyleMedium2``…); si no se da, ``table_style``
            - tablas_por_documento: Número de tablas por documento Word (default 50)
            - table_style: Estilo de tablas para Word (default "Table Grid")
            - html_items_por_pagina: Número de elementos por página en índice HTML (default 15)
            - grafo.enabled: Diagramas de relaciones (Word y HTML; necesitan Graphviz)
            - grafo.max_depth / grafo.direction: Profundidad y dirección (incoming, outgoing o both)
            - grafo.images_paginated / grafo.max_subnodes: Diagramas de Word partidos en varias imágenes
            - grafo.columns.mode / grafo.columns.max_items: Columnas visibles en los nodos
            - grafo.workers: Procesos ``dot`` simultáneos (por defecto, los núcleos hasta 8)
            - grafo.orthogonal_edges: Aristas ortogonales (por defecto ``True``); ``False`` dibuja curvas, para los
              grafos en los que el enrutado ortogonal de Graphviz falla
        formatos: Formatos a generar: 'word', 'excel', 'html' (por defecto ``["word"]``).
        headers_file: JSON con las cabeceras de cada sección (``{"headers": {"COLUMNAS": {"base": [...]}, ...}}``).
        batch_window_seconds: Ventana temporal en segundos para agrupar generaciones automáticas en la misma carpeta
            (entero ≥ 0). ``0`` (default desde 5.0.0; antes 90, G2 de util_bbdd_web) no agrupa: cada generación tiene
            su carpeta. Con un valor > 0, si ``fichero_salida`` es None y se lanzan dos generaciones de la misma base
            de datos dentro de la ventana, reutilizan el mismo nombre.
        schema: Schema (owner en Oracle, base de datos en MySQL/MariaDB) que documentar; por defecto, el contexto de
            metadatos del manager. Todas las lecturas (catálogo, DDL, diagramas, almacenamiento) van a ese schema
            con la misma conexión (desde 4.1.0); el usuario necesita permiso de lectura sobre sus objetos.
        on_progress: Recibe un ``ProgressEvent`` (operación ``"documentation"``) al empezar la lectura del catálogo
            (fase ``"metadata"``), al empezar cada formato (``"word"``, ``"excel"``, ``"html"``; ``0`` de N tablas) y
            al terminar cada tabla de cada formato. Desde 4.1.0.
        cancel_token: Se comprueba antes de leer el catálogo, antes de cada formato y entre tablas; si está cancelado,
            ``generate()`` lanza ``OperationCancelledError``. Los formatos ya terminados quedan escritos; el que estaba
            en curso puede quedar incompleto (el HTML escribe página a página). Desde 4.1.0.

    Raises:
        DocumentationConfigError: Configuración inválida (formato no soportado, ``imprimir`` que no es un diccionario,
            cabeceras inexistentes o mal formadas, plantilla Word que no existe, ``batch_window_seconds`` que no es un
            entero ≥ 0). También es ``ValueError``.

    Examples:
        >>> with SyncDatabaseManager("postgresql", conn_params) as manager:
        ...     result = DatabaseDocumentation(manager, Path("docs_bd"), formatos=["word", "html"]).generate()
        >>> result.outputs["html"]
    """

    _AUTO_OUTPUT_BATCH_WINDOW_SECONDS: ClassVar[int] = 0  # 5.0.0 (G2): antes 90
    # Nombres automáticos recientes por (directorio, servidor, base de datos): agrupan las generaciones seguidas con
    # ventana > 0 y, sin ventana, numeran las que caen en el mismo segundo
    _LAST_AUTO_OUTPUT_BY_KEY: ClassVar[OutputCache] = {}
    _AUTO_OUTPUT_LOCK: ClassVar[threading.Lock] = threading.Lock()

    def __init__(
        self,
        db_manager: DocumentationSourcePort,
        directorio_salida: Path = Path(""),
        fichero_salida: Path | None = None,
        imprimir: dict[str, Any] | None = None,
        formatos: list[str] | None = None,
        headers_file: Path = _DEFAULT_HEADERS_FILE,
        batch_window_seconds: int | None = None,
        schema: str | None = None,
        on_progress: ProgressCallback | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> None:
        self._logger: logging.Logger = logging.getLogger(__name__)
        self._progress = ProgressReporter("documentation", on_progress, cancel_token, self._logger)
        self._output_policy = DocumentationOutputRuntime()
        self._source = SyncDatabaseManagerAdapter(db_manager, {}, schema=schema)
        resolved_batch_window: int = self._batch_window(batch_window_seconds)
        self._bootstrap = DocumentationBootstrap(
            db_manager=self._source,
            directorio_salida=directorio_salida,
            fichero_salida=fichero_salida,
            imprimir=imprimir,
            formatos=formatos,
            headers_file=headers_file,
            output_cache=self._LAST_AUTO_OUTPUT_BY_KEY,
            batch_window_seconds=resolved_batch_window,
            print_config_policy=PrintConfigManager(),
            headers_runtime=DocumentationHeadersRuntime(),
            output_policy=self._output_policy,
            output_lock=self._AUTO_OUTPUT_LOCK,
            word_template_check=WordTemplateValidator.check,
            excel_template_check=ExcelTemplate.check,
        )
        self._settings: DocumentationSettings = self._bootstrap.settings()
        self._source.imprimir_config = self._settings.print_config

    @classmethod
    def _batch_window(cls, value: int | None) -> int:
        """``batch_window_seconds`` validado: entero ≥ 0 (``0`` no agrupa); ``None``, el valor por defecto (``0``).

        Hasta ahora no se validaba: un negativo no agrupaba nunca y un ``str`` fallaba al comparar, ya en ``generate()``.
        """
        if value is None:
            return cls._AUTO_OUTPUT_BATCH_WINDOW_SECONDS
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise DocumentationConfigError(
                f"batch_window_seconds debe ser un entero ≥ 0, recibido: {value!r}", operation="DOCUMENTATION"
            )
        return value

    def generate(self) -> DocumentationResult:
        """Lee el catálogo y genera los documentos de todos los formatos pedidos.

        Returns:
            Ruta de salida de cada formato y número de tablas, vistas y rutinas documentadas.

        Raises:
            DocumentationRenderError: Falló la preparación de la carpeta de salida o la escritura de un formato (la
                causa queda en ``__cause__``).
            DatabaseException: Error leyendo el catálogo (con su propia clase, p. ej. ``DatabaseOperationError``).
            OperationCancelledError: Se canceló ``cancel_token`` (ver el argumento).

        Examples:
            >>> result = DatabaseDocumentation(manager, Path("out"), formatos=["excel"]).generate()
            >>> result.outputs["excel"].suffix
            '.xlsx'
        """
        self._progress.check("metadata")
        self._progress.emit("metadata", 0, 1, "")
        state = self._bootstrap.build(self._settings)
        self._progress.emit("metadata", 1, 1, "")
        session = DocumentationSession.from_state(
            state,
            db_manager=self._source,
            logger=self._logger,
            output_policy=self._output_policy,
            metadata_runtime_factory=DocumentationMetadataRuntimeFactory(),
            storage_report_service=StorageInventoryReportService(),
        )
        session.progress = self._progress
        renderer_registry = build_default_renderer_registry(
            word_generator_cls=WordGenerator,
            excel_generator_cls=ExcelGenerator,
            html_generator_cls=HtmlGenerator,
        )
        outputs: dict[str, Path] = DocumentationOrchestrator(
            session=session,
            planner=DocumentationOutputPlanner(session, renderer_registry),
            renderer_registry=renderer_registry,
            graph_generator_factory=build_graph_generator_from_options,
        ).generate_documents()
        return DocumentationResult(
            outputs=outputs,
            tables=len(state.tablas),
            views=len(state.vistas),
            routines=len(state.rutinas),
        )
