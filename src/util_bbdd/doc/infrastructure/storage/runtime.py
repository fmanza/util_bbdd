"""Helpers internos para el inventario de almacenamiento documental."""

from __future__ import annotations

import re

from dataclasses import dataclass, field
from typing import Any, ClassVar, cast

from ...._core.exceptions import DatabaseException, QueryNotFoundError
from ...application.ports import DocumentationManagerPort, LoggerProtocol, StorageReportServicePort
from .contracts import StorageInventoryManagerProtocol, StorageInventoryStrategyPort
from .mariadb_strategy import MariadbStorageInventoryStrategy
from .oracle_strategy import OracleStorageInventoryStrategy
from .payload import StorageInventoryReportPayload, StorageSectionPayload
from .strategy_registry import StorageInventoryEngineStrategy


@dataclass(slots=True)
class StorageInventoryRuntime:
    """Construye el informe de almacenamiento consumido por los generadores."""

    db_manager: StorageInventoryManagerProtocol
    logger: LoggerProtocol
    db_type: str
    database: str
    print_config: dict[str, Any]
    _mariadb_strategy: MariadbStorageInventoryStrategy = field(init=False, repr=False)
    _oracle_strategy: OracleStorageInventoryStrategy = field(init=False, repr=False)
    _default_storage_strategy: StorageInventoryStrategyPort = field(init=False, repr=False)
    _storage_strategy_registry: dict[str, StorageInventoryStrategyPort] = field(init=False, repr=False)

    _ARCHIVO_FISICO: str = "Archivo fisico"
    _FICHEROS_FISICOS: str = "Ficheros físicos"
    _TAMANO_MB: str = "Tamaño (MB)"
    _TIPO_FICHERO: str = "Tipo de fichero"
    _MAXIMO_MB: str = "Maximo (MB)"
    _TEMP_TABLESPACES: str = "Temp tablespaces"
    _SIZE_HEADER_HINTS: tuple[str, ...] = ("mb", "tamano", "tamaño", "size")
    _ORACLE_USER_TABLESPACES_QUERY: str = "SELECT default_tablespace, temporary_tablespace FROM user_users"
    _DEFAULT_STORAGE_QUERY_SPECS: ClassVar[tuple[tuple[str, str], ...]] = (
        ("ficheros_fisicos", _FICHEROS_FISICOS),
        ("temp_tablespaces", _TEMP_TABLESPACES),
    )
    _DB_STORAGE_QUERY_SPECS: ClassVar[dict[str, tuple[tuple[str, str], ...]]] = {
        "mariadb": (
            ("ficheros_fisicos", _FICHEROS_FISICOS),
            ("temp_tablespaces", _TEMP_TABLESPACES),
            ("temp_storage_variables", "Configuración temporales InnoDB"),
        ),
        "sqlite": (
            ("ficheros_fisicos", _FICHEROS_FISICOS),
            ("sqlite_file_summary", f"{_FICHEROS_FISICOS} - resumen SQLite"),
            ("temp_tablespaces", _TEMP_TABLESPACES),
        ),
    }

    def __post_init__(self) -> None:
        """Inicializa estrategias de motor para consultas de almacenamiento."""
        self._mariadb_strategy = MariadbStorageInventoryStrategy()
        self._oracle_strategy = OracleStorageInventoryStrategy()
        self._default_storage_strategy = StorageInventoryEngineStrategy(
            query_specs=self._DEFAULT_STORAGE_QUERY_SPECS,
            resolve_default_tablespace_fn=lambda: "",
        )
        self._storage_strategy_registry = {
            "postgresql": StorageInventoryEngineStrategy(
                query_specs=self._DEFAULT_STORAGE_QUERY_SPECS,
                resolve_default_tablespace_fn=lambda: "pg_default",
            ),
            "sqlite": StorageInventoryEngineStrategy(
                query_specs=self._DB_STORAGE_QUERY_SPECS["sqlite"],
                resolve_default_tablespace_fn=lambda: "",
            ),
            "mariadb": StorageInventoryEngineStrategy(
                query_specs=self._DB_STORAGE_QUERY_SPECS["mariadb"],
                resolve_default_tablespace_fn=lambda: "",
                query_processors={
                    "temp_storage_variables": lambda query_name, query_title, _database_name, query_params: (
                        self._process_mariadb_temp_storage_variables_query(query_name, query_title, query_params)
                    ),
                },
                error_processors={
                    "temp_tablespaces": lambda query_name, query_title, error_msg: (
                        self._build_mariadb_temp_tablespaces_error_section(query_name, query_title, error_msg)
                    ),
                },
            ),
            "oracle": StorageInventoryEngineStrategy(
                query_specs=self._DEFAULT_STORAGE_QUERY_SPECS,
                resolve_default_tablespace_fn=self._get_oracle_default_tablespace,
                query_processors={
                    "ficheros_fisicos": lambda query_name, query_title, database_name, _query_params: (
                        self._process_oracle_storage_query(query_name, query_title, database_name)
                    ),
                    "temp_tablespaces": lambda query_name, query_title, database_name, _query_params: (
                        self._process_oracle_storage_query(query_name, query_title, database_name)
                    ),
                },
            ),
        }

    def get_storage_inventory_report(self) -> dict[str, Any]:
        """Obtiene informe unificado de almacenamiento para Word/Excel/HTML."""
        query_specs: list[tuple[str, str]] = self._build_storage_query_specs()
        database_name: str = str(self.database or "").strip()
        tablespace: str = self._resolve_storage_tablespace()
        query_params: dict[str, Any] = {"database": database_name, "tablespace": tablespace}

        sections_payload: list[StorageSectionPayload] = []
        for query_name, query_title in query_specs:
            section_dict: dict[str, Any] = self._process_storage_query(
                query_name, query_title, database_name, query_params
            )
            sections_payload.append(StorageSectionPayload.from_mapping(section_dict))

        report_payload = StorageInventoryReportPayload(
            db_type=self.db_type,
            database=self.database,
            tablespace=tablespace,
            sections=tuple(sections_payload),
        )
        return report_payload.to_dict()

    def _resolve_storage_tablespace(self) -> str:
        """Resuelve el tablespace para consultas de almacenamiento cuando aplica."""
        tablespace: str = self._get_configured_tablespace()
        if tablespace:
            return tablespace
        return self._get_default_database_tablespace()

    def _get_configured_tablespace(self) -> str:
        """Obtiene tablespace desde configuración o parámetros de conexión."""
        storage_cfg: object = self.print_config.get("storage")
        if not isinstance(storage_cfg, dict):
            storage_cfg = self.print_config.get("almacenamiento", {})
        if not isinstance(storage_cfg, dict):
            storage_cfg = {}

        cfg_tablespace: str = str(storage_cfg.get("tablespace", "") or "").strip()
        if cfg_tablespace:
            return cfg_tablespace

        return str(self.db_manager.conn_params.get("tablespace", "") or "").strip()

    def _get_default_database_tablespace(self) -> str:
        """Obtiene tablespace por defecto según el tipo de motor."""
        return self._resolve_storage_strategy().resolve_default_tablespace()

    def _get_oracle_default_tablespace(self) -> str:
        """Intenta obtener tablespace del usuario Oracle conectado."""
        try:
            user_tablespaces: object = self.db_manager.execute_custom_one(self._ORACLE_USER_TABLESPACES_QUERY)
            return self._extract_tablespace_from_row(user_tablespaces)
        except DatabaseException:
            return ""

    def _extract_tablespace_from_row(self, row_data: object) -> str:
        """Extrae tablespace válido de una fila de datos."""
        normalized_rows: list[list[object]] = self._normalize_storage_rows(row_data)
        if not normalized_rows or not normalized_rows[0]:
            return ""

        row: list[object] = normalized_rows[0]
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
        """Resuelve tablespaces Oracle separados por tipo."""
        return self._oracle_strategy.resolve_storage_tablespaces(self)

    def _collect_oracle_data_tablespaces(self) -> list[str]:
        """Recolecta tablespaces de datos desde configuración y usuario Oracle."""
        return self._oracle_strategy.collect_data_tablespaces(self)

    def _collect_oracle_temp_tablespaces(self) -> list[str]:
        """Recolecta tablespaces temporales desde usuario Oracle."""
        return self._oracle_strategy.collect_temp_tablespaces(self)

    def _dedup_tablespaces(self, values: list[str]) -> list[str]:
        """Deduplica y normaliza lista de tablespaces."""
        return self._oracle_strategy.dedup_tablespaces(values)

    def _normalize_storage_rows(self, rows: object) -> list[list[object]]:
        """Normaliza resultados de consulta a formato tabular homogéneo."""
        if rows is None:
            return []

        if not isinstance(rows, list):
            rows = [rows]

        normalized: list[list[object]] = []
        for row in rows:
            if isinstance(row, (list, tuple)):
                normalized.append(list(row))
            else:
                normalized.append([row])
        return normalized

    @staticmethod
    def _parse_mariadb_size_to_mb(size_value: str) -> float | None:
        """Convierte tamaños MariaDB tipo 12M/5G a MB."""
        return MariadbStorageInventoryStrategy.parse_size_to_mb(size_value)

    @classmethod
    def _parse_mariadb_temp_data_file_path_rows(cls, variable_name: str, raw_value: str) -> list[list[object]]:
        """Parsea innodb_temp_data_file_path a filas tabulares."""
        return MariadbStorageInventoryStrategy.parse_temp_data_file_path_rows(variable_name, raw_value)

    @classmethod
    def _extract_mariadb_temp_data_from_chunk(
        cls, variable_name: str, chunk: str, raw_value: str
    ) -> list[object] | None:
        """Extrae datos de un chunk de innodb_temp_data_file_path."""
        return MariadbStorageInventoryStrategy.extract_temp_data_from_chunk(variable_name, chunk, raw_value)

    @classmethod
    def _extract_initial_size_and_idx(cls, tokens: list[str], idx: int) -> tuple[float | str, int]:
        """Extrae tamaño inicial y devuelve el siguiente índice."""
        return MariadbStorageInventoryStrategy.extract_initial_size_and_idx(tokens, idx)

    @classmethod
    def _extract_optional_mariadb_params(cls, tokens: list[str], start_idx: int) -> tuple[str, float | str]:
        """Extrae parámetros opcionales autoextend y max de MariaDB."""
        return MariadbStorageInventoryStrategy.extract_optional_params(tokens, start_idx)

    @staticmethod
    def _is_autoextend_token(token: str) -> bool:
        """Verifica si el token es autoextend."""
        return MariadbStorageInventoryStrategy.is_autoextend_token(token)

    @staticmethod
    def _is_max_token(token: str, tokens: list[str], idx: int) -> bool:
        """Verifica si el token es max y hay siguiente elemento."""
        return MariadbStorageInventoryStrategy.is_max_token(token, tokens, idx)

    def _build_storage_query_specs(self) -> list[tuple[str, str]]:
        """Construye secciones de almacenamiento según el motor."""
        return self._resolve_storage_strategy().get_query_specs()

    def _resolve_storage_strategy(self) -> StorageInventoryStrategyPort:
        """Resuelve la estrategia por motor o fallback genérico."""
        return self._storage_strategy_registry.get(self.db_type, self._default_storage_strategy)

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
                "ficheros_fisicos": ["DB", "Objeto", "Motor", "Datos (MB)", "Indices (MB)", "Total (MB)"],
                "temp_tablespaces": ["Tablespace", "Archivo", "Extent (MB)", "Inicial (MB)", self._MAXIMO_MB],
                "temp_storage_variables": [
                    "Variable",
                    "Archivo",
                    "Inicial (MB)",
                    "Autoextend",
                    self._MAXIMO_MB,
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
                    self._MAXIMO_MB,
                ],
                "temp_tablespaces": [
                    "Tablespace",
                    "Archivo",
                    self._TAMANO_MB,
                    "Estado",
                    self._TIPO_FICHERO,
                    "Autoextensible",
                    self._MAXIMO_MB,
                ],
            },
            "postgresql": {
                "ficheros_fisicos": ["Tablespace", "Ruta filesystem", "Tamaño total"],
                "temp_tablespaces": [self._TEMP_TABLESPACES],
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
                "sqlite_file_summary": ["Page count", "Page size", "Size bytes"],
                "temp_tablespaces": ["Temp store"],
            },
            "hsqldb": {"temp_tablespaces": ["Temp tablespace"]},
        }
        return headers_map.get(self.db_type, {}).get(query_name, [])

    def _build_storage_headers(self, query_name: str, rows: list[list[object]]) -> list[str]:
        """Construye cabeceras legibles; si no hay mapeo usa fallback genérico."""
        preferred_headers: list[str] = self._get_storage_headers_by_query(query_name)
        if preferred_headers:
            if rows:
                max_cols: int = max(len(row) for row in rows)
                if max_cols > 0:
                    return preferred_headers[:max_cols]
            return preferred_headers
        if not rows:
            return []
        fallback_max_cols: int = max(len(row) for row in rows)
        return [f"Columna {idx}" for idx in range(1, fallback_max_cols + 1)]

    def _is_size_header(self, header: str) -> bool:
        """Indica si una cabecera corresponde a un valor de tamaño."""
        normalized: str = str(header or "").strip().lower()
        return any(hint in normalized for hint in self._SIZE_HEADER_HINTS)

    def _format_spanish_decimal(self, value: object) -> object:
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

    def _format_storage_rows(self, headers: list[str], rows: list[list[object]]) -> list[list[object]]:
        """Formatea filas de almacenamiento aplicando formato español en tamaños."""
        if not rows:
            return rows

        formatted_rows: list[list[object]] = []
        for row in rows:
            formatted_row: list[object] = []
            for idx, value in enumerate(row):
                header: str = headers[idx] if idx < len(headers) else ""
                formatted_row.append(self._format_spanish_decimal(value) if self._is_size_header(header) else value)
            formatted_rows.append(formatted_row)
        return formatted_rows

    def _get_numeric_storage_indices(self, headers: list[str]) -> list[int]:
        """Devuelve índices de columnas numéricas de almacenamiento."""
        return [idx for idx, header in enumerate(headers) if self._is_size_header(header)]

    def _is_placeholder_storage_query(self, query_name: str, query_params: dict[str, Any]) -> bool:
        """Indica si la query de almacenamiento es un placeholder de no soporte."""
        try:
            sql_text: str = str(self.db_manager.resolve_query(query_name, **query_params).final_sql or "")
        except DatabaseException:
            return False
        normalized_sql: str = " ".join(sql_text.strip().lower().split())
        return "where 1=0" in normalized_sql

    def _process_storage_query(
        self,
        query_name: str,
        query_title: str,
        database_name: str,
        query_params: dict[str, Any],
    ) -> dict[str, Any]:
        """Procesa una consulta individual de almacenamiento."""
        resolved_section = self._resolve_storage_strategy().process_query(
            query_name=query_name,
            query_title=query_title,
            database_name=database_name,
            query_params=query_params,
        )
        if resolved_section is not None:
            return resolved_section
        return self._process_standard_storage_query(query_name, query_title, query_params)

    def _process_mariadb_temp_storage_variables_query(
        self,
        query_name: str,
        query_title: str,
        query_params: dict[str, Any],
    ) -> dict[str, Any]:
        """Procesa configuración temporal MariaDB basada en SHOW VARIABLES."""
        return self._mariadb_strategy.process_temp_storage_variables_query(self, query_name, query_title, query_params)

    def _process_oracle_storage_query(self, query_name: str, query_title: str, database_name: str) -> dict[str, Any]:
        """Procesa consulta de almacenamiento específica para Oracle."""
        return self._oracle_strategy.process_storage_query(self, query_name, query_title, database_name)

    def _collect_oracle_tablespace_data(
        self,
        query_name: str,
        database_name: str,
        oracle_tablespaces: list[str],
    ) -> tuple[list[list[object]], list[str], list[str]]:
        """Recolecta datos de tablespaces Oracle."""
        return self._oracle_strategy.collect_tablespace_data(
            runtime=self,
            query_name=query_name,
            database_name=database_name,
            oracle_tablespaces=oracle_tablespaces,
        )

    def _deduplicate_rows(self, rows: list[list[object]]) -> list[list[object]]:
        """Deduplica filas."""
        return self._oracle_strategy.deduplicate_rows(rows)

    def _build_oracle_section(
        self,
        query_name: str,
        query_title: str,
        rows: list[list[object]],
        headers: list[str],
        tablespace_count: int,
        errors: list[str],
        sql_list: list[str],
    ) -> dict[str, Any]:
        """Construye sección de resultado para Oracle."""
        return self._oracle_strategy.build_oracle_section(
            runtime=self,
            query_name=query_name,
            query_title=query_title,
            rows=rows,
            headers=headers,
            tablespace_count=tablespace_count,
            errors=errors,
            sql_list=sql_list,
        )

    def _process_standard_storage_query(
        self,
        query_name: str,
        query_title: str,
        query_params: dict[str, Any],
    ) -> dict[str, Any]:
        """Procesa consulta de almacenamiento estándar."""
        try:
            resolved = self.db_manager.resolve_query(query_name, **query_params)
        except QueryNotFoundError:
            return self._build_section_not_supported(query_name, query_title)
        except DatabaseException as error:
            return self._build_section_missing_params(
                query_name,
                query_title,
                f"Parámetros inválidos: {error}",
            )

        if self._is_placeholder_storage_query(query_name, query_params):
            return self._build_section_not_supported(query_name, query_title)

        try:
            sql_text: str = str(resolved.final_sql or "")
            result_rows: object = self.db_manager.execute_query_many(query_name, **query_params)
            rows: list[list[object]] = self._normalize_storage_rows(result_rows)
            headers: list[str] = self._build_storage_headers(query_name, rows)
            rows = self._format_storage_rows(headers, rows)
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
        except DatabaseException as error:
            flattened_error_msg: str = self._flatten_exception_messages(error)
            return self._build_storage_error_section(query_name, query_title, flattened_error_msg)

    def _build_storage_error_section(self, query_name: str, query_title: str, error_msg: str) -> dict[str, Any]:
        """Construye sección de error usando transformadores por motor."""
        override = self._resolve_storage_strategy().build_error_section(
            query_name=query_name,
            query_title=query_title,
            error_msg=error_msg,
        )
        if override is not None:
            return override
        return self._build_section_error(query_name, query_title, error_msg)

    def _build_mariadb_temp_tablespaces_error_section(
        self,
        query_name: str,
        query_title: str,
        error_msg: str,
    ) -> dict[str, Any]:
        """Construye mensaje explícito para incidencias de information_schema.FILES."""
        return self._mariadb_strategy.build_temp_tablespaces_error_section(self, query_name, query_title, error_msg)

    def _build_section_not_supported(self, query_name: str, query_title: str) -> dict[str, Any]:
        """Construye sección de resultado para consultas no soportadas."""
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

    def _build_section_missing_params(self, query_name: str, query_title: str, message: str) -> dict[str, Any]:
        """Construye sección de resultado para parámetros faltantes."""
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

    def _build_section_error(self, query_name: str, query_title: str, error_msg: str) -> dict[str, Any]:
        """Construye sección de resultado para errores."""
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


def build_storage_inventory_runtime(
    *,
    db_manager: StorageInventoryManagerProtocol,
    logger: LoggerProtocol,
    print_config: dict[str, Any],
) -> StorageInventoryRuntime:
    """Construye el runtime documental de almacenamiento fuera de la fachada pública."""
    return StorageInventoryRuntime(
        db_manager=db_manager,
        logger=logger,
        db_type=db_manager.db_type,
        database=db_manager.database,
        print_config=print_config,
    )


def get_storage_inventory_report(
    *,
    db_manager: StorageInventoryManagerProtocol,
    logger: LoggerProtocol,
    print_config: dict[str, Any],
) -> dict[str, Any]:
    """Obtiene el informe de almacenamiento sin exponer bootstrap en la fachada documental."""
    runtime: StorageInventoryRuntime = build_storage_inventory_runtime(
        db_manager=db_manager,
        logger=logger,
        print_config=print_config,
    )
    return runtime.get_storage_inventory_report()


@dataclass(slots=True, frozen=True)
class StorageInventoryReportService(StorageReportServicePort):
    """Servicio OO de acceso al inventario de almacenamiento."""

    def get_storage_inventory_report(
        self,
        *,
        db_manager: DocumentationManagerPort,
        logger: LoggerProtocol,
        print_config: dict[str, Any],
    ) -> dict[str, Any]:
        return get_storage_inventory_report(
            db_manager=cast(StorageInventoryManagerProtocol, db_manager),
            logger=logger,
            print_config=print_config,
        )


__all__: list[str] = [
    "StorageInventoryRuntime",
    "StorageInventoryReportService",
    "build_storage_inventory_runtime",
    "get_storage_inventory_report",
]
