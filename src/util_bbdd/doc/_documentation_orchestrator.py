"""Orquestación interna del flujo documental."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from ._documentation_runtime_headers import DocumentationHeadersRuntime
from ._documentation_runtime_metadata import DocumentationMetadataRuntime
from ._documentation_runtime_output import DocumentationOutputRuntime
from ._documentation_runtime_types import DocumentationRuntimeManagerProtocol, LoggerProtocol
from ._storage_inventory_runtime import (
    StorageInventoryManagerProtocol,
    get_storage_inventory_report as get_storage_inventory_report_runtime,
)
from .print_config_manager import PrintConfigManager

_UNSET_DATABASE_CHARSET_COLLATION: object = object()


@dataclass(slots=True, frozen=True)
class DocumentationBootstrapState:
    """Estado inicial resuelto para la fachada documental."""

    db_manager: DocumentationRuntimeManagerProtocol
    print_config: dict[str, Any]
    formatos: list[str]
    directorio_salida: Path
    fichero_salida: Path
    table_style: str
    headers_config: dict[str, Any]
    headers: dict[str, list[str]]
    tablas: list[Any]
    vistas: list[Any]
    rutinas: list[Any]


class DocumentationBootstrap:
    """Construye el estado interno inicial antes de delegar en la fachada pública."""

    def __init__(
        self,
        *,
        db_manager: DocumentationRuntimeManagerProtocol,
        directorio_salida: Path,
        fichero_salida: Path | None,
        imprimir: dict[str, Any] | None,
        formatos: list[str] | None,
        headers_file: Path,
        output_cache: dict[tuple[str, str], tuple[float, str]],
        batch_window_seconds: int,
        headers_runtime: DocumentationHeadersRuntime | None = None,
        output_runtime: DocumentationOutputRuntime | None = None,
    ) -> None:
        self._db_manager = db_manager
        self._directorio_salida = directorio_salida
        self._fichero_salida = fichero_salida
        self._imprimir = imprimir
        self._formatos = formatos
        self._headers_file = headers_file
        self._output_cache = output_cache
        self._batch_window_seconds = batch_window_seconds
        self._headers_runtime = headers_runtime or DocumentationHeadersRuntime()
        self._output_runtime = output_runtime or DocumentationOutputRuntime()

    def build(self) -> DocumentationBootstrapState:
        """Resuelve toda la configuración y metadatos iniciales del documento."""
        print_config = PrintConfigManager.normalize(self._imprimir)
        resolved_formatos = self._output_runtime.normalize_output_formats(self._formatos)
        resolved_output = self._output_runtime.resolve_document_output_filename(
            fichero_salida=self._fichero_salida,
            db_manager=self._db_manager,
            output_dir=self._directorio_salida,
            output_cache=self._output_cache,
            batch_window_seconds=self._batch_window_seconds,
        )
        headers_config = self._headers_runtime.load_headers_config(self._headers_file)

        return DocumentationBootstrapState(
            db_manager=self._db_manager,
            print_config=print_config,
            formatos=resolved_formatos,
            directorio_salida=self._directorio_salida,
            fichero_salida=resolved_output,
            table_style=str(print_config.get("table_style", "Table Grid")),
            headers_config=headers_config,
            headers=self._headers_runtime.build_headers(headers_config, self._db_manager.db_type),
            tablas=self._db_manager.get_tables(),
            vistas=self._db_manager.get_views(),
            rutinas=self._db_manager.get_routines(),
        )


class DocumentationFacade(Protocol):
    """Contrato mínimo de la fachada pública consumido por la orquestación interna."""

    logger: LoggerProtocol
    db_manager: DocumentationRuntimeManagerProtocol
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
    db_manager: DocumentationRuntimeManagerProtocol
    database: str
    print_config: dict[str, Any]
    formatos: list[str]
    directorio_salida: Path
    fichero_salida: Path
    headers: dict[str, list[str]]
    table_style: str
    tablas: list[Any]
    vistas: list[Any]
    rutinas: list[Any]
    _ddl_cache: dict[tuple[str, str, str], str] | None = None
    _list_cache: dict[tuple[str, str, str], list[Any]] | None = None
    _database_version_cache: str | None = ""
    _database_charset_collation_cache: dict[str, Any] | None | object = _UNSET_DATABASE_CHARSET_COLLATION
    _columns_charset_collation_cache: dict[str, list[tuple[str, str | None, str | None]] | None] | None = None
    _storage_inventory_report_cache: dict[str, Any] | None = None
    _metadata_runtime: DocumentationMetadataRuntime | None = None
    _output_runtime: DocumentationOutputRuntime | None = None

    @classmethod
    def from_documentation(cls, documentation: DocumentationFacade) -> DocumentationSession:
        """Construye una sesión interna a partir de la fachada pública."""
        output_runtime = DocumentationOutputRuntime()
        query_context_database = getattr(documentation.db_manager, "get_query_context_database", lambda: "")()
        resolved_database = output_runtime.resolve_generator_database_context(
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
            formatos=list(documentation.formatos),
            directorio_salida=documentation.directorio_salida,
            fichero_salida=documentation.fichero_salida,
            headers=documentation.headers,
            table_style=documentation.table_style,
            tablas=documentation.tablas,
            vistas=documentation.vistas,
            rutinas=documentation.rutinas,
            _ddl_cache={},
            _list_cache={},
            _columns_charset_collation_cache={},
            _metadata_runtime=DocumentationMetadataRuntime(logger=documentation.logger),
            _output_runtime=output_runtime,
        )

    @property
    def db_type(self) -> str:
        """Expone el tipo de motor resuelto para los generadores."""
        return self.db_manager.db_type

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
            self._database_version_cache = self._get_metadata_runtime().get_database_version_metadata(
                db_manager=self.db_manager
            )
        return self._database_version_cache or None

    def get_database_charset_collation(self) -> dict[str, Any] | None:
        """Obtiene y cachea charset/collation de base de datos."""
        if self._database_charset_collation_cache is _UNSET_DATABASE_CHARSET_COLLATION:
            self._database_charset_collation_cache = self._get_metadata_runtime().get_database_charset_collation_metadata(
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
            self._columns_charset_collation_cache[tabla] = self._get_metadata_runtime().get_columns_charset_collation_metadata(
                db_manager=self.db_manager,
                table_name=tabla,
            )
        return self._columns_charset_collation_cache[tabla]

    def get_storage_inventory_report(self) -> dict[str, Any]:
        """Obtiene y cachea el inventario de almacenamiento."""
        if self._storage_inventory_report_cache is None:
            self._storage_inventory_report_cache = get_storage_inventory_report_runtime(
                db_manager=cast(StorageInventoryManagerProtocol, self.db_manager),
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
        return list(self._list_cache[cache_key])

    def _get_metadata_runtime(self) -> DocumentationMetadataRuntime:
        """Obtiene el runtime OO de metadata con inicialización diferida."""
        if self._metadata_runtime is None:
            self._metadata_runtime = DocumentationMetadataRuntime(logger=self.logger)
        return self._metadata_runtime

    def _get_output_runtime(self) -> DocumentationOutputRuntime:
        """Obtiene el runtime OO de salida con inicialización diferida."""
        if self._output_runtime is None:
            self._output_runtime = DocumentationOutputRuntime()
        return self._output_runtime

    def resolve_output_path(self, output_format: str, extension: str | None = None) -> Path:
        """Resuelve el directorio o fichero de salida para un formato."""
        output_dir: Path = self._get_output_runtime().get_format_output_dir(
            self.directorio_salida,
            self.fichero_salida,
            output_format,
        )
        if extension is None:
            return output_dir

        output_base: Path = output_dir / self._get_output_runtime().get_output_base_filename(self.fichero_salida)
        return output_base.with_suffix(extension)


@dataclass(slots=True, frozen=True)
class DocumentationFormatPlan:
    """Plan de salida para un formato documental concreto."""

    output_format: str
    output_path: Path
    include_graph_generator: bool


class DocumentationOutputPlanner:
    """Convierte una sesión documental en planes de salida ejecutables."""

    def __init__(self, session: DocumentationSession) -> None:
        self._session = session

    def build_plans(self) -> list[DocumentationFormatPlan]:
        """Construye los planes de salida respetando el orden solicitado."""
        plans: list[DocumentationFormatPlan] = []
        for output_format in self._session.formatos:
            if output_format == "word":
                plans.append(
                    DocumentationFormatPlan(
                        output_format="word",
                        output_path=self._session.resolve_output_path("word", ".docx"),
                        include_graph_generator=True,
                    )
                )
            elif output_format == "excel":
                plans.append(
                    DocumentationFormatPlan(
                        output_format="excel",
                        output_path=self._session.resolve_output_path("excel", ".xlsx"),
                        include_graph_generator=False,
                    )
                )
            elif output_format == "html":
                plans.append(
                    DocumentationFormatPlan(
                        output_format="html",
                        output_path=self._session.resolve_output_path("html"),
                        include_graph_generator=True,
                    )
                )
            else:
                raise ValueError(f"Formato no soportado para documentación: {output_format}")
        return plans

    def should_share_graph_generator(self) -> bool:
        """Indica si Word y HTML pueden reutilizar un único generador de grafos."""
        if not {"word", "html"}.issubset(set(self._session.formatos)):
            return False

        graph_cfg: dict[str, Any] = self._session.print_config.get("grafo", {})
        return bool(graph_cfg.get("enabled", False))


class DocumentationOrchestrator:
    """Coordina planificación, estado de sesión y generación por formato."""

    def __init__(
        self,
        *,
        session: DocumentationSession,
        planner: DocumentationOutputPlanner,
        graph_generator_cls: type[Any],
        word_generator_cls: type[Any],
        excel_generator_cls: type[Any],
        html_generator_cls: type[Any],
    ) -> None:
        self._session = session
        self._planner = planner
        self._graph_generator_cls = graph_generator_cls
        self._word_generator_cls = word_generator_cls
        self._excel_generator_cls = excel_generator_cls
        self._html_generator_cls = html_generator_cls

    @classmethod
    def from_documentation(
        cls,
        documentation: DocumentationFacade,
        *,
        graph_generator_cls: type[Any],
        word_generator_cls: type[Any],
        excel_generator_cls: type[Any],
        html_generator_cls: type[Any],
    ) -> DocumentationOrchestrator:
        """Construye el orquestador interno a partir de la fachada pública."""
        session = DocumentationSession.from_documentation(documentation)
        planner = DocumentationOutputPlanner(session)
        return cls(
            session=session,
            planner=planner,
            graph_generator_cls=graph_generator_cls,
            word_generator_cls=word_generator_cls,
            excel_generator_cls=excel_generator_cls,
            html_generator_cls=html_generator_cls,
        )

    def generate_documents(self) -> None:
        """Ejecuta la generación documental completa para la sesión activa."""
        shared_graph_generator: Any | None = self._build_shared_graph_generator()
        for plan in self._planner.build_plans():
            self._dispatch_plan(plan, shared_graph_generator)

    def _build_shared_graph_generator(self) -> Any | None:
        """Construye un generador de grafos compartido cuando Word y HTML lo requieren."""
        if not self._planner.should_share_graph_generator():
            return None

        graph_cfg: dict[str, Any] = self._session.print_config.get("grafo", {})
        columns_options: dict[str, Any] = dict(graph_cfg.get("columns", {}))
        cardinality_options: dict[str, Any] = dict(graph_cfg.get("cardinality", {}))

        self._session.logger.debug("🟢 Inicializando generador de grafos compartido para Word y HTML")
        return self._graph_generator_cls(
            db_manager=self._session.db_manager,
            column_mode=str(columns_options.get("mode", "relations")),
            max_columns=int(columns_options.get("max_items", 8)),
            show_data_types=bool(columns_options.get("show_data_types", False)),
            max_depth=int(graph_cfg.get("max_depth", 1)),
            direction=str(graph_cfg.get("direction", "both")),
            show_constraint_name=bool(cardinality_options.get("show_constraint_name", False)),
            render_dpi=int(graph_cfg.get("dpi", 150)),
        )

    def _dispatch_plan(self, plan: DocumentationFormatPlan, shared_graph_generator: Any | None) -> None:
        """Despacha la ejecución del plan de salida correspondiente."""
        if plan.output_format == "word":
            self._create_word_document(plan, graph_generator=shared_graph_generator)
            return
        if plan.output_format == "excel":
            self._create_excel_document(plan)
            return
        if plan.output_format == "html":
            self._create_html_document(plan, graph_generator=shared_graph_generator)
            return
        raise ValueError(f"Formato no soportado para documentación: {plan.output_format}")

    def _create_word_document(self, plan: DocumentationFormatPlan, *, graph_generator: Any | None) -> None:
        """Genera el documento Word del plan indicado."""
        generator = self._word_generator_cls(
            database=self._session.database,
            headers=self._session.headers,
            table_style=self._session.table_style,
        )
        generator.generate_document(
            self._session.tablas,
            self._session.vistas,
            self._session.rutinas,
            self._session,
            plan.output_path,
            print_config=self._session.print_config,
            graph_generator=graph_generator if plan.include_graph_generator else None,
        )

    def _create_excel_document(self, plan: DocumentationFormatPlan) -> None:
        """Genera el documento Excel del plan indicado."""
        generator = self._excel_generator_cls(
            database=self._session.database,
            headers=self._session.headers,
            table_style=self._session.table_style,
        )
        generator.generate_document(
            self._session.tablas,
            self._session.vistas,
            self._session.rutinas,
            self._session,
            plan.output_path,
            print_config=self._session.print_config,
        )

    def _create_html_document(self, plan: DocumentationFormatPlan, *, graph_generator: Any | None) -> None:
        """Genera la documentación HTML del plan indicado."""
        generator = self._html_generator_cls(database=self._session.database, headers=self._session.headers)
        generator.generate_document(
            self._session.tablas,
            self._session.vistas,
            self._session.rutinas,
            self._session,
            plan.output_path,
            print_config=self._session.print_config,
            graph_generator=graph_generator if plan.include_graph_generator else None,
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
