"""Orquestación interna del flujo documental."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ....analysis.graphviz_ext import GraphvizRelationshipGraphExt

from ...._core.exceptions import DatabaseException, DocumentationConfigError, DocumentationRenderError
from ....progress import ProgressReporter
from ...domain.models import (
    DocumentationBootstrapState,
    DocumentationFormatPlan,
    DocumentationSettings,
    EngineConditionsSection,
)
from ...domain.services import DocumentationGraphDomainService
from .._internal_ports import (
    HeadersRuntimePort,
    MetadataRuntimeFactoryPort,
    MetadataRuntimePort,
    PrintConfigPolicyPort,
    RendererRegistryPort,
    StorageReportServicePort,
)
from ..ports import (
    DocumentationBackendPort,
    EngineReadinessSourcePort,
    LoggerProtocol,
    OutputCache,
    OutputPolicyPort,
)
from .catalog_rows import CatalogRows
from .engine_conditions import EngineConditionsSectionBuilder

_UNSET_DATABASE_CHARSET_COLLATION: object = object()


class DocumentationBootstrap:
    """Resuelve la configuración de una documentación y, al generar, su estado inicial.

    :meth:`settings` no consulta la base de datos (valida ``imprimir``, formatos, cabeceras y plantilla Word);
    :meth:`build` resuelve el nombre de salida y lee el inventario del catálogo.
    """

    def __init__(
        self,
        *,
        db_manager: DocumentationBackendPort,
        directorio_salida: Path,
        fichero_salida: Path | None,
        imprimir: dict[str, Any] | None,
        formatos: list[str] | None,
        headers_file: Path,
        output_cache: OutputCache,
        batch_window_seconds: int,
        print_config_policy: PrintConfigPolicyPort,
        headers_runtime: HeadersRuntimePort,
        output_policy: OutputPolicyPort,
        output_lock: AbstractContextManager[Any] | None = None,
        word_template_check: Callable[[Path], None] | None = None,
        excel_template_check: Callable[[Path], None] | None = None,
    ) -> None:
        self._db_manager = db_manager
        self._directorio_salida = directorio_salida
        self._fichero_salida = fichero_salida
        self._imprimir = imprimir
        self._formatos = formatos
        self._headers_file = headers_file
        self._output_cache = output_cache
        self._batch_window_seconds = batch_window_seconds
        self._print_config_policy = print_config_policy
        self._headers_runtime = headers_runtime
        self._output_policy = output_policy
        self._output_lock: AbstractContextManager[Any] = output_lock or nullcontext()
        self._word_template_check = word_template_check
        self._excel_template_check = excel_template_check

    def settings(self) -> DocumentationSettings:
        """Valida y normaliza la configuración.

        Raises:
            DocumentationConfigError: ``imprimir`` no es un diccionario, un formato no está soportado, el fichero de
                cabeceras no existe o está mal formado, o la plantilla Word indicada no es un fichero (o, con
                ``word_template_check``, no se puede abrir o le faltan estilos), o la plantilla Excel no existe o no se
                puede usar (``excel_template_check``).
        """
        try:
            print_config = self._print_config_policy.normalize(self._imprimir)
            formatos = self._output_policy.normalize_output_formats(self._formatos)
            headers_config = self._headers_runtime.load_headers_config(self._headers_file)
            headers = self._headers_runtime.build_headers(headers_config)
        except (TypeError, ValueError, KeyError, OSError) as error:
            raise DocumentationConfigError(str(error), operation="DOCUMENTATION") from error
        template: Any = print_config.get("plantilla_word")
        if "word" in formatos and template is not None:
            template_path = Path(template).expanduser()
            if not template_path.is_file():
                raise DocumentationConfigError(f"Plantilla Word no encontrada: {template}", operation="DOCUMENTATION")
            if self._word_template_check is not None:
                self._word_template_check(template_path)
        excel_template: Any = print_config.get("plantilla_excel")
        if "excel" in formatos and excel_template is not None:
            excel_path = Path(excel_template).expanduser()
            if not excel_path.is_file():
                raise DocumentationConfigError(
                    f"Plantilla Excel no encontrada: {excel_template}", operation="DOCUMENTATION"
                )
            if self._excel_template_check is not None:
                self._excel_template_check(excel_path)
        return DocumentationSettings(
            print_config=print_config,
            formatos=formatos,
            headers_config=headers_config,
            headers=headers,
            table_style=str(print_config.get("table_style", "Table Grid")),
        )

    def build(self, settings: DocumentationSettings) -> DocumentationBootstrapState:
        """Nombre de salida (reutilizado entre generaciones seguidas) e inventario del catálogo (lee la BD)."""
        with self._output_lock:
            resolved_output = self._output_policy.resolve_document_output_filename(
                fichero_salida=self._fichero_salida,
                db_manager=self._db_manager,
                output_dir=self._directorio_salida,
                output_cache=self._output_cache,
                batch_window_seconds=self._batch_window_seconds,
            )
        # D1 (ADR-003): el catálogo se lee por lotes, una consulta por tipo de objeto y no por tabla
        catalog = CatalogRows(lambda kinds: self._db_manager.get_schema_metadata(kinds=kinds))
        return DocumentationBootstrapState(
            settings=settings,
            directorio_salida=self._directorio_salida,
            fichero_salida=resolved_output,
            tablas=catalog.tables(),
            vistas=catalog.views(),
            rutinas=catalog.routines(),
            catalog=catalog,
        )


@dataclass(slots=True)
class DocumentationSession:
    """Estado efímero de una generación: lo que ven los renderers como ``data_provider``."""

    logger: LoggerProtocol
    db_manager: DocumentationBackendPort
    database: str
    imprimir_config: dict[str, Any]
    formatos: list[str]
    directorio_salida: Path
    fichero_salida: Path
    headers: dict[str, list[str]]
    table_style: str
    tablas: list[Any]
    vistas: list[Any]
    rutinas: list[Any]
    output_policy: OutputPolicyPort
    metadata_runtime: MetadataRuntimePort
    storage_report_service: StorageReportServicePort
    catalog: CatalogRows | None = None
    _ddl_cache: dict[tuple[str, str, str], str] | None = None
    _database_version_cache: str | None = ""
    _database_charset_collation_cache: dict[str, Any] | None | object = _UNSET_DATABASE_CHARSET_COLLATION
    _columns_charset_collation_cache: dict[str, list[tuple[str, str | None, str | None]] | None] | None = None
    _storage_inventory_report_cache: dict[str, Any] | None = None
    _engine_conditions_cache: EngineConditionsSection | None = None
    #: Progreso y cancelación de la generación (4.1.0): lo usan el orquestador y los renderers (``TableProgress``)
    progress: ProgressReporter = field(default_factory=lambda: ProgressReporter("documentation"))

    @classmethod
    def from_state(
        cls,
        state: DocumentationBootstrapState,
        *,
        db_manager: DocumentationBackendPort,
        logger: LoggerProtocol,
        output_policy: OutputPolicyPort,
        metadata_runtime_factory: MetadataRuntimeFactoryPort,
        storage_report_service: StorageReportServicePort,
    ) -> DocumentationSession:
        """Construye la sesión de una generación a partir de su estado inicial."""
        query_context_database = db_manager.get_query_context_database()
        resolved_database = output_policy.resolve_generator_database_context(
            db_type=db_manager.db_type,
            database=db_manager.database,
            conn_params=db_manager.conn_params or {},
            query_context_database=str(query_context_database or "").strip(),
        )
        settings: DocumentationSettings = state.settings
        return cls(
            logger=logger,
            db_manager=db_manager,
            database=resolved_database,
            imprimir_config=settings.print_config,
            formatos=list(settings.formatos),
            directorio_salida=state.directorio_salida,
            fichero_salida=state.fichero_salida,
            headers=settings.headers,
            table_style=settings.table_style,
            tablas=state.tablas,
            vistas=state.vistas,
            rutinas=state.rutinas,
            output_policy=output_policy,
            metadata_runtime=metadata_runtime_factory.create(logger=logger),
            storage_report_service=storage_report_service,
            catalog=state.catalog,
            _ddl_cache={},
            _columns_charset_collation_cache={},
        )

    @property
    def db_type(self) -> str:
        """Expone el tipo de motor resuelto para los generadores."""
        return self.db_manager.db_type

    @property
    def conn_params(self) -> dict[str, Any]:
        """Expone parámetros de conexión requeridos por puertos de naming."""
        return self.db_manager.conn_params

    def get_query_context_database(self) -> str:
        """Delega la resolución del contexto de consulta al manager real."""
        return self.db_manager.get_query_context_database()

    def get_tables(self) -> list[tuple[Any, ...]]:
        """Devuelve tablas cargadas en la sesión actual."""
        return list(self.tablas)

    def get_views(self) -> list[tuple[Any, ...]]:
        """Devuelve vistas cargadas en la sesión actual."""
        return list(self.vistas)

    def get_routines(self) -> list[tuple[Any, ...]]:
        """Devuelve rutinas cargadas en la sesión actual."""
        return list(self.rutinas)

    def get_ddl(self, tabla: str) -> str:
        """Obtiene y cachea el DDL de una tabla."""
        return self._get_cached_scalar(("ddl", "table", tabla), lambda: self.db_manager.get_ddl(tabla))

    def _catalog(self) -> CatalogRows:
        if self.catalog is None:
            self.catalog = CatalogRows(lambda kinds: self.db_manager.get_schema_metadata(kinds=kinds))
        return self.catalog

    def get_schema_metadata(self, schema: str | None = None, **kwargs: Any) -> Any:
        """Lectura por lotes del origen (la usa también ``analysis`` para el índice de relaciones)."""
        return self.db_manager.get_schema_metadata(schema, **kwargs)

    def get_view_ddl(self, vista: str) -> str:
        """DDL de una vista (``CREATE VIEW … AS`` + la definición que guarda el motor)."""
        return self._catalog().view_ddl(vista)

    def get_columns(self, tabla: str) -> list[Any]:
        """Columnas neutras de una tabla o vista (ver ``catalog_rows``)."""
        return self._catalog().columns(tabla)

    def get_routine_ddl(self, rutina: str, tipo_rutina: str) -> str:
        """Definición completa de una rutina."""
        return self._catalog().routine_ddl(rutina, tipo_rutina)

    def get_routine_parameters(self, rutina: str, tipo_rutina: str) -> list[Any]:
        """Parámetros ``(modo, nombre, tipo, por defecto, posición)`` de una rutina."""
        return self._catalog().routine_parameters(rutina, tipo_rutina)

    def get_primary_keys(self, tabla: str) -> list[Any]:
        """Columnas de la clave primaria ``[(columna,), …]``."""
        return self._catalog().primary_keys(tabla)

    def get_foreign_keys(self, tabla: str) -> list[Any]:
        """Claves foráneas por par de columnas."""
        return self._catalog().foreign_keys(tabla)

    def get_unique_constraints(self, tabla: str) -> list[Any]:
        """Restricciones únicas ``(restricción, columna)``."""
        return self._catalog().unique_constraints(tabla)

    def get_indices(self, tabla: str) -> list[Any]:
        """Índices ``(índice, columna, Sí/No, método)``."""
        return self._catalog().indices(tabla)

    def get_database_version(self) -> str | None:
        """Obtiene y cachea la versión de la base de datos."""
        if self._database_version_cache == "":
            self._database_version_cache = self.metadata_runtime.get_database_version_metadata(
                db_manager=self.db_manager
            )
        return self._database_version_cache or None

    def get_database_charset_collation(self) -> dict[str, Any] | None:
        """Obtiene y cachea charset/collation de base de datos."""
        if self._database_charset_collation_cache is _UNSET_DATABASE_CHARSET_COLLATION:
            self._database_charset_collation_cache = self.metadata_runtime.get_database_charset_collation_metadata(
                db_manager=self.db_manager,
            )
        return (
            self._database_charset_collation_cache if isinstance(self._database_charset_collation_cache, dict) else None
        )

    def get_columns_charset_collation(self, tabla: str) -> list[tuple[str, str | None, str | None]] | None:
        """Obtiene y cachea charset/collation por columna."""
        if self._columns_charset_collation_cache is None:
            self._columns_charset_collation_cache = {}
        if tabla not in self._columns_charset_collation_cache:
            self._columns_charset_collation_cache[tabla] = self.metadata_runtime.get_columns_charset_collation_metadata(
                db_manager=self.db_manager,
                table_name=tabla,
            )
        return self._columns_charset_collation_cache[tabla]

    def get_storage_inventory_report(self) -> dict[str, Any]:
        """Obtiene y cachea el inventario de almacenamiento."""
        if self._storage_inventory_report_cache is None:
            self._storage_inventory_report_cache = self.storage_report_service.get_storage_inventory_report(
                db_manager=self.db_manager,
                logger=self.logger,
                print_config=self.imprimir_config,
            )
        return self._storage_inventory_report_cache

    def get_engine_conditions(self) -> EngineConditionsSection:
        """Sección «Condiciones del motor», verificada una sola vez por generación (la comparten los formatos).

        Un origen que no cumple ``EngineReadinessSourcePort`` o que falla al verificar no interrumpe la generación:
        la sección lleva el aviso correspondiente.
        """
        if self._engine_conditions_cache is None:
            builder = EngineConditionsSectionBuilder(self.headers.get("CONDICIONES_MOTOR"))
            source = self.db_manager
            if not isinstance(source, EngineReadinessSourcePort):
                section = builder.build(None)
            else:
                try:
                    section = builder.build(source.get_engine_readiness())
                except Exception as exc:
                    self.logger.warning(
                        f"No se pudieron verificar las condiciones del motor: {type(exc).__name__}", exc_info=True
                    )
                    section = builder.unavailable(
                        f"No se pudieron verificar las condiciones del motor ({type(exc).__name__})."
                    )
            self._engine_conditions_cache = section
        return self._engine_conditions_cache

    def _get_cached_scalar(self, cache_key: tuple[str, str, str], loader: Callable[[], str]) -> str:
        """Resuelve un valor escalar con cache local por sesión."""
        if self._ddl_cache is None:
            self._ddl_cache = {}
        if cache_key not in self._ddl_cache:
            self._ddl_cache[cache_key] = loader()
        return self._ddl_cache[cache_key]

    def resolve_output_path(self, output_format: str, extension: str | None = None) -> Path:
        """Resuelve el directorio o fichero de salida para un formato."""
        output_dir: Path = self.output_policy.get_format_output_dir(
            self.directorio_salida,
            self.fichero_salida,
            output_format,
        )
        if extension is None:
            return output_dir

        output_base: Path = output_dir / self.output_policy.get_output_base_filename(self.fichero_salida)
        return output_base.with_suffix(extension)


class DocumentationOutputPlanner:
    """Convierte una sesión documental en planes de salida ejecutables."""

    def __init__(self, session: DocumentationSession, renderer_registry: RendererRegistryPort) -> None:
        self._session = session
        self._renderer_registry = renderer_registry

    def build_plans(self) -> list[DocumentationFormatPlan]:
        """Construye los planes de salida respetando el orden solicitado."""
        plans: list[DocumentationFormatPlan] = []
        for output_format in self._session.formatos:
            registration = self._renderer_registry.get(output_format)
            if registration is None:
                raise DocumentationConfigError(f"Formato no soportado para documentación: {output_format}")
            plans.append(
                DocumentationFormatPlan(
                    output_format=output_format,
                    output_path=self._session.resolve_output_path(output_format, registration.output_extension),
                    include_graph_generator=registration.include_graph_generator,
                )
            )
        return plans

    def needs_graph_generator(self) -> bool:
        """Si algún formato pedido dibuja diagramas y ``grafo.enabled`` está activo."""
        return DocumentationGraphDomainService.needs_graph_generator(
            formatos=self._session.formatos,
            print_config=self._session.imprimir_config,
        )


#: Construye el generador de grafos de la sesión a partir de la fuente y del bloque ``grafo`` (lo inyecta la fachada).
GraphGeneratorFactory = Callable[[DocumentationBackendPort, dict[str, Any]], Any]


class DocumentationOrchestrator:
    """Coordina planificación, estado de sesión y generación por formato."""

    def __init__(
        self,
        *,
        session: DocumentationSession,
        planner: DocumentationOutputPlanner,
        renderer_registry: RendererRegistryPort,
        graph_generator_factory: GraphGeneratorFactory,
    ) -> None:
        self._session = session
        self._planner = planner
        self._renderer_registry = renderer_registry
        self._graph_generator_factory = graph_generator_factory

    def generate_documents(self) -> dict[str, Path]:
        """Ejecuta la generación documental completa para la sesión activa y devuelve la salida de cada formato.

        Un único generador de grafos para todos los formatos: comparte el índice de relaciones y los renders
        precargados, y cada formato produce lo mismo pida o no los demás (B-02).
        """
        graph_generator: GraphvizRelationshipGraphExt | None = None
        if self._planner.needs_graph_generator():
            self._session.logger.debug("🟢 Inicializando generador de grafos de la documentación")
            graph_generator = self._graph_generator_factory(
                self._session.db_manager, dict(self._session.imprimir_config.get("grafo", {}))
            )
        try:
            plans: list[DocumentationFormatPlan] = self._planner.build_plans()
        except OSError as error:
            # Hotfix 2026-10-11: crear las carpetas de salida (mkdir) podía escapar como OSError crudo; el contrato de
            # generate() es DocumentationRenderError, como en los fallos de los renderers.
            raise DocumentationRenderError(
                f"Error preparando la salida de la documentación: {error}", operation="DOCUMENTATION"
            ) from error
        outputs: dict[str, Path] = {}
        progress = self._session.progress
        total_tables: int = len(self._session.tablas)
        for plan in plans:
            progress.check(plan.output_format)
            progress.emit(plan.output_format, 0, total_tables, "")
            self._dispatch_plan(plan, graph_generator)
            outputs[plan.output_format] = plan.output_path
        return outputs

    def _dispatch_plan(
        self, plan: DocumentationFormatPlan, shared_graph_generator: GraphvizRelationshipGraphExt | None
    ) -> None:
        """Despacha la ejecución del plan de salida correspondiente."""
        registration = self._renderer_registry.get(plan.output_format)
        if registration is None:
            raise DocumentationConfigError(f"Formato no soportado para documentación: {plan.output_format}")

        renderer = registration.factory(
            database=self._session.database,
            headers=self._session.headers,
            table_style=self._session.table_style,
        )
        renderer_kwargs: dict[str, Any] = {
            "print_config": self._session.imprimir_config,
        }
        if registration.accepts_graph_generator:
            renderer_kwargs["graph_generator"] = shared_graph_generator if plan.include_graph_generator else None

        try:
            renderer.generate_document(
                self._session.tablas,
                self._session.vistas,
                self._session.rutinas,
                self._session,
                plan.output_path,
                **renderer_kwargs,
            )
        except DatabaseException:
            raise  # errores de la base de datos (o ya documentales): con su propia clase
        except Exception as error:  # noqa: BLE001 - frontera del renderer: se traduce a la jerarquía de la librería
            self._session.logger.error(f"❌ Error generando la documentación {plan.output_format}", exc_info=True)
            raise DocumentationRenderError(
                f"Error generando la documentación {plan.output_format} en {plan.output_path}: {error}",
                operation="DOCUMENTATION",
            ) from error


__all__: list[str] = [
    "DocumentationBootstrap",
    "DocumentationBootstrapState",
    "DocumentationFormatPlan",
    "DocumentationOrchestrator",
    "DocumentationOutputPlanner",
    "DocumentationSession",
]
