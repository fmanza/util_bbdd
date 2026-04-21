"""Orquestación interna del flujo documental."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

if TYPE_CHECKING:
    from ....analysis.graphviz_ext import GraphvizRelationshipGraphExt

from ...domain.models import DocumentationBootstrapState, DocumentationFormatPlan
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
    DocumentationManagerPort,
    LoggerProtocol,
    OutputCache,
    OutputPolicyPort,
)

_UNSET_DATABASE_CHARSET_COLLATION: object = object()


class DocumentationBootstrap:
    """Construye el estado interno inicial antes de delegar en la fachada pública."""

    def __init__(
        self,
        *,
        db_manager: DocumentationManagerPort,
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

    def build(self) -> DocumentationBootstrapState:
        """Resuelve toda la configuración y metadatos iniciales del documento."""
        print_config = self._print_config_policy.normalize(self._imprimir)
        resolved_formatos = self._output_policy.normalize_output_formats(self._formatos)
        resolved_output = self._output_policy.resolve_document_output_filename(
            fichero_salida=self._fichero_salida,
            db_manager=self._db_manager,
            output_dir=self._directorio_salida,
            output_cache=self._output_cache,
            batch_window_seconds=self._batch_window_seconds,
        )
        headers_config = self._headers_runtime.load_headers_config(self._headers_file)

        return DocumentationBootstrapState(
            print_config=print_config,
            formatos=resolved_formatos,
            directorio_salida=self._directorio_salida,
            fichero_salida=resolved_output,
            table_style=str(print_config.get("table_style", "Table Grid")),
            headers_config=headers_config,
            headers=self._headers_runtime.build_headers(headers_config, self._db_manager.db_type),
            tablas=list(self._db_manager.get_tables()),
            vistas=list(self._db_manager.get_views()),
            rutinas=list(self._db_manager.get_routines()),
        )


class DocumentationFacade(Protocol):
    """Contrato mínimo de la fachada pública consumido por la orquestación interna."""

    logger: LoggerProtocol
    db_manager: DocumentationManagerPort
    imprimir_config: dict[str, Any]
    formatos: list[str]
    directorio_salida: Path
    fichero_salida: Path
    headers: dict[str, list[str]]
    table_style: str
    tablas: list[Any]
    vistas: list[Any]
    rutinas: list[Any]


@dataclass(slots=True)
class DocumentationSession:
    """Estado efímero requerido para una ejecución documental."""

    data_provider: DocumentationFacade
    logger: LoggerProtocol
    db_manager: DocumentationManagerPort
    database: str
    print_config: dict[str, Any]
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
    _ddl_cache: dict[tuple[str, str, str], str] | None = None
    _list_cache: dict[tuple[str, str, str], list[Any]] | None = None
    _database_version_cache: str | None = ""
    _database_charset_collation_cache: dict[str, Any] | None | object = _UNSET_DATABASE_CHARSET_COLLATION
    _columns_charset_collation_cache: dict[str, list[tuple[str, str | None, str | None]] | None] | None = None
    _storage_inventory_report_cache: dict[str, Any] | None = None

    @classmethod
    def from_documentation(
        cls,
        documentation: DocumentationFacade,
        *,
        output_policy: OutputPolicyPort,
        metadata_runtime_factory: MetadataRuntimeFactoryPort,
        storage_report_service: StorageReportServicePort,
    ) -> DocumentationSession:
        """Construye una sesión interna a partir de la fachada pública."""
        query_context_database = documentation.db_manager.get_query_context_database()
        resolved_database = output_policy.resolve_generator_database_context(
            db_type=documentation.db_manager.db_type,
            database=documentation.db_manager.database,
            conn_params=documentation.db_manager.conn_params or {},
            query_context_database=str(query_context_database or "").strip(),
        )
        return cls(
            data_provider=documentation,
            logger=documentation.logger,
            db_manager=documentation.db_manager,
            database=resolved_database,
            print_config=documentation.imprimir_config,
            imprimir_config=documentation.imprimir_config,
            formatos=list(documentation.formatos),
            directorio_salida=documentation.directorio_salida,
            fichero_salida=documentation.fichero_salida,
            headers=documentation.headers,
            table_style=documentation.table_style,
            tablas=documentation.tablas,
            vistas=documentation.vistas,
            rutinas=documentation.rutinas,
            output_policy=output_policy,
            metadata_runtime=metadata_runtime_factory.create(logger=documentation.logger),
            storage_report_service=storage_report_service,
            _ddl_cache={},
            _list_cache={},
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

    def get_view_ddl(self, vista: str) -> str:
        """Obtiene y cachea el DDL de una vista."""
        return self._get_cached_scalar(("ddl", "view", vista), lambda: self.db_manager.get_view_ddl(vista))

    def get_columns(self, tabla: str) -> list[Any]:
        """Obtiene y cachea las columnas de una tabla o vista."""
        return self._get_cached_list(("columns", "entity", tabla), lambda: list(self.db_manager.get_columns(tabla)))

    def get_routine_ddl(self, rutina: str, tipo_rutina: str) -> str:
        """Obtiene y cachea el DDL de una rutina."""
        cache_key = ("ddl", tipo_rutina, rutina)
        return self._get_cached_scalar(cache_key, lambda: self.db_manager.get_routine_ddl(rutina, tipo_rutina))

    def get_routine_parameters(self, rutina: str, tipo_rutina: str) -> list[Any]:
        """Obtiene y cachea los parámetros de una rutina."""
        cache_key = ("routine_parameters", tipo_rutina, rutina)
        return self._get_cached_list(
            cache_key, lambda: list(self.db_manager.get_routine_parameters(rutina, tipo_rutina))
        )

    def get_primary_keys(self, tabla: str) -> list[Any]:
        """Obtiene y cachea las claves primarias de una tabla."""
        return self._get_cached_list(
            ("primary_keys", "table", tabla), lambda: list(self.db_manager.get_primary_keys(tabla))
        )

    def get_foreign_keys(self, tabla: str) -> list[Any]:
        """Obtiene y cachea las claves foráneas de una tabla."""
        return self._get_cached_list(
            ("foreign_keys", "table", tabla), lambda: list(self.db_manager.get_foreign_keys(tabla))
        )

    def get_unique_constraints(self, tabla: str) -> list[Any]:
        """Obtiene y cachea las restricciones únicas de una tabla."""
        return self._get_cached_list(
            ("unique_constraints", "table", tabla),
            lambda: list(self.db_manager.get_unique_constraints(tabla)),
        )

    def get_indices(self, tabla: str) -> list[Any]:
        """Obtiene y cachea los índices de una tabla."""
        return self._get_cached_list(("indices", "table", tabla), lambda: list(self.db_manager.get_indices(tabla)))

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
                print_config=self.print_config,
            )
        return self._storage_inventory_report_cache

    def _get_cached_scalar(self, cache_key: tuple[str, str, str], loader: Callable[[], str]) -> str:
        """Resuelve un valor escalar con cache local por sesión."""
        if self._ddl_cache is None:
            self._ddl_cache = {}
        if cache_key not in self._ddl_cache:
            self._ddl_cache[cache_key] = loader()
        return self._ddl_cache[cache_key]

    def _get_cached_list(self, cache_key: tuple[str, str, str], loader: Callable[[], list[Any]]) -> list[Any]:
        """Resuelve una lista con cache local por sesión."""
        if self._list_cache is None:
            self._list_cache = {}
        if cache_key not in self._list_cache:
            self._list_cache[cache_key] = loader()
        return self._list_cache[cache_key]

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
                raise ValueError(f"Formato no soportado para documentación: {output_format}")
            plans.append(
                DocumentationFormatPlan(
                    output_format=output_format,
                    output_path=self._session.resolve_output_path(output_format, registration.output_extension),
                    include_graph_generator=registration.include_graph_generator,
                )
            )
        return plans

    def should_share_graph_generator(self) -> bool:
        """Indica si Word y HTML pueden reutilizar un único generador de grafos."""
        return DocumentationGraphDomainService.should_share_graph_generator(
            formatos=self._session.formatos,
            print_config=self._session.print_config,
        )


class DocumentationOrchestrator:
    """Coordina planificación, estado de sesión y generación por formato."""

    def __init__(
        self,
        *,
        session: DocumentationSession,
        planner: DocumentationOutputPlanner,
        renderer_registry: RendererRegistryPort,
        graph_generator_cls: type[Any],
    ) -> None:
        self._session = session
        self._planner = planner
        self._renderer_registry = renderer_registry
        self._graph_generator_cls = graph_generator_cls

    @classmethod
    def from_documentation(
        cls,
        documentation: DocumentationFacade,
        *,
        output_policy: OutputPolicyPort,
        metadata_runtime_factory: MetadataRuntimeFactoryPort,
        storage_report_service: StorageReportServicePort,
        renderer_registry: RendererRegistryPort,
        graph_generator_cls: type[Any],
    ) -> DocumentationOrchestrator:
        """Construye el orquestador interno a partir de la fachada pública."""
        session = DocumentationSession.from_documentation(
            documentation,
            output_policy=output_policy,
            metadata_runtime_factory=metadata_runtime_factory,
            storage_report_service=storage_report_service,
        )
        planner = DocumentationOutputPlanner(session, renderer_registry)
        return cls(
            session=session,
            planner=planner,
            renderer_registry=renderer_registry,
            graph_generator_cls=graph_generator_cls,
        )

    def generate_documents(self) -> None:
        """Ejecuta la generación documental completa para la sesión activa."""
        shared_graph_generator: GraphvizRelationshipGraphExt | None = self._build_shared_graph_generator()
        for plan in self._planner.build_plans():
            self._dispatch_plan(plan, shared_graph_generator)

    def _build_shared_graph_generator(self) -> GraphvizRelationshipGraphExt | None:
        """Construye un generador de grafos compartido cuando Word y HTML lo requieren."""
        if not self._planner.should_share_graph_generator():
            return None

        graph_cfg: dict[str, Any] = self._session.print_config.get("grafo", {})
        columns_options: dict[str, Any] = dict(graph_cfg.get("columns", {}))
        cardinality_options: dict[str, Any] = dict(graph_cfg.get("cardinality", {}))

        self._session.logger.debug("🟢 Inicializando generador de grafos compartido para Word y HTML")
        return cast(
            "GraphvizRelationshipGraphExt",
            self._graph_generator_cls(
                db_manager=self._session.db_manager,
                column_mode=str(columns_options.get("mode", "relations")),
                max_columns=int(columns_options.get("max_items", 8)),
                show_data_types=bool(columns_options.get("show_data_types", False)),
                max_depth=int(graph_cfg.get("max_depth", 1)),
                direction=str(graph_cfg.get("direction", "both")),
                show_constraint_name=bool(cardinality_options.get("show_constraint_name", False)),
                render_dpi=int(graph_cfg.get("dpi", 150)),
            ),
        )

    def _dispatch_plan(
        self, plan: DocumentationFormatPlan, shared_graph_generator: GraphvizRelationshipGraphExt | None
    ) -> None:
        """Despacha la ejecución del plan de salida correspondiente."""
        registration = self._renderer_registry.get(plan.output_format)
        if registration is None:
            raise ValueError(f"Formato no soportado para documentación: {plan.output_format}")

        renderer = registration.factory(
            database=self._session.database,
            headers=self._session.headers,
            table_style=self._session.table_style,
        )
        renderer_kwargs: dict[str, Any] = {
            "print_config": self._session.print_config,
        }
        if registration.accepts_graph_generator:
            renderer_kwargs["graph_generator"] = shared_graph_generator if plan.include_graph_generator else None

        renderer.generate_document(
            self._session.tablas,
            self._session.vistas,
            self._session.rutinas,
            self._session,
            plan.output_path,
            **renderer_kwargs,
        )


__all__: list[str] = [
    "DocumentationBootstrap",
    "DocumentationBootstrapState",
    "DocumentationFacade",
    "DocumentationFormatPlan",
    "DocumentationOrchestrator",
    "DocumentationOutputPlanner",
    "DocumentationSession",
]
