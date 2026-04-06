"""Helpers internos para el inventario de almacenamiento documental."""

from __future__ import annotations

import re

from dataclasses import dataclass
from typing import Any, Protocol

from ..database_exceptions import QueryNotFoundError


class StorageInventoryManagerProtocol(Protocol):
    """Contrato mínimo del manager requerido por el runtime de inventario."""

    db_type: str
    database: str
    conn_params: dict[str, Any]

    def resolve_query(self, query_name: str, **params: Any) -> Any: ...

    def execute_query_many(self, query_name: str, **params: Any) -> Any: ...

    def execute_custom_one(self, query: str) -> Any: ...


class _StorageQueryStrategy(Protocol):
    """Contrato interno para resolver consultas de almacenamiento por motor."""

    def can_handle(self, runtime: StorageInventoryRuntime, query_name: str) -> bool:
        """Indica si la estrategia aplica para la consulta actual."""
        ...

    def process(
        self,
        runtime: StorageInventoryRuntime,
        query_name: str,
        query_title: str,
        database_name: str,
        query_params: dict[str, Any],
    ) -> dict[str, Any]:
        """Procesa la consulta de almacenamiento usando la estrategia seleccionada."""
        ...


@dataclass(slots=True, frozen=True)
class _OracleStorageQueryStrategy:
    """Estrategia para consultas de almacenamiento Oracle."""

    _ORACLE_QUERIES: frozenset[str] = frozenset({"ficheros_fisicos", "temp_tablespaces"})

    def can_handle(self, runtime: StorageInventoryRuntime, query_name: str) -> bool:
        return runtime.db_type == "oracle" and query_name in self._ORACLE_QUERIES

    def process(
        self,
        runtime: StorageInventoryRuntime,
        query_name: str,
        query_title: str,
        database_name: str,
        query_params: dict[str, Any],
    ) -> dict[str, Any]:
        del query_params
        return runtime._process_oracle_storage_query(query_name, query_title, database_name)


@dataclass(slots=True, frozen=True)
class _MariadbTempStorageVariablesStrategy:
    """Estrategia para `temp_storage_variables` en MariaDB."""

    def can_handle(self, runtime: StorageInventoryRuntime, query_name: str) -> bool:
        return runtime.db_type == "mariadb" and query_name == "temp_storage_variables"

    def process(
        self,
        runtime: StorageInventoryRuntime,
        query_name: str,
        query_title: str,
        database_name: str,
        query_params: dict[str, Any],
    ) -> dict[str, Any]:
        del database_name
        return runtime._process_mariadb_temp_storage_variables_query(query_name, query_title, query_params)


@dataclass(slots=True, frozen=True)
class _StandardStorageQueryStrategy:
    """Estrategia de fallback para motores y consultas no específicas."""

    def can_handle(self, runtime: StorageInventoryRuntime, query_name: str) -> bool:
        del runtime, query_name
        return True

    def process(
        self,
        runtime: StorageInventoryRuntime,
        query_name: str,
        query_title: str,
        database_name: str,
        query_params: dict[str, Any],
    ) -> dict[str, Any]:
        del database_name
        return runtime._process_standard_storage_query(query_name, query_title, query_params)


_STORAGE_QUERY_STRATEGIES: tuple[_StorageQueryStrategy, ...] = (
    _OracleStorageQueryStrategy(),
    _MariadbTempStorageVariablesStrategy(),
    _StandardStorageQueryStrategy(),
)


@dataclass(slots=True)
class StorageInventoryRuntime:
    """Construye el informe de almacenamiento consumido por los generadores."""

    db_manager: StorageInventoryManagerProtocol
    logger: Any
    db_type: str
    database: str
    print_config: dict[str, Any]

    _ARCHIVO_FISICO: str = "Archivo fisico"
    _TAMANO_MB: str = "Tamaño (MB)"
    _TIPO_FICHERO: str = "Tipo de fichero"
    _MAXIMO_MB: str = "Maximo (MB)"
    _SIZE_HEADER_HINTS: tuple[str, ...] = ("mb", "tamano", "tamaño", "size")
    _ORACLE_USER_TABLESPACES_QUERY: str = "SELECT default_tablespace, temporary_tablespace FROM user_users"

    def get_storage_inventory_report(self) -> dict[str, Any]:
        """Obtiene informe unificado de almacenamiento para Word/Excel/HTML."""
        query_specs: list[tuple[str, str]] = self._build_storage_query_specs()
        database_name: str = str(self.database or "").strip()
        tablespace: str = self._resolve_storage_tablespace()
        query_params: dict[str, Any] = {"database": database_name, "tablespace": tablespace}

        sections: list[dict[str, Any]] = []
        for query_name, query_title in query_specs:
            section = self._process_storage_query(query_name, query_title, database_name, query_params)
            sections.append(section)

        total_rows: int = sum(len(section.get("rows", [])) for section in sections if section.get("status") == "ok")
        return {
            "db_type": self.db_type,
            "database": self.database,
            "tablespace": tablespace,
            "total_rows": total_rows,
            "sections": sections,
        }

    def _resolve_storage_tablespace(self) -> str:
        """Resuelve el tablespace para consultas de almacenamiento cuando aplica."""
        tablespace: str = self._get_configured_tablespace()
        if tablespace:
            return tablespace
        return self._get_default_database_tablespace()

    def _get_configured_tablespace(self) -> str:
        """Obtiene tablespace desde configuración o parámetros de conexión."""
        storage_cfg: Any = self.print_config.get("storage")
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
        if self.db_type == "oracle":
            return self._get_oracle_default_tablespace()
        if self.db_type == "postgresql":
            return "pg_default"
        return ""

    def _get_oracle_default_tablespace(self) -> str:
        """Intenta obtener tablespace del usuario Oracle conectado."""
        try:
            user_tablespaces: Any = self.db_manager.execute_custom_one(self._ORACLE_USER_TABLESPACES_QUERY)
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
        """Resuelve tablespaces Oracle separados por tipo."""
        return {
            "data_tablespaces": self._dedup_tablespaces(self._collect_oracle_data_tablespaces()),
            "temp_tablespaces": self._dedup_tablespaces(self._collect_oracle_temp_tablespaces()),
        }

    def _collect_oracle_data_tablespaces(self) -> list[str]:
        """Recolecta tablespaces de datos desde configuración y usuario Oracle."""
        data_candidates: list[str] = []

        storage_cfg: dict[str, Any] = self.print_config.get("storage", {})
        cfg_tablespace: str = str(storage_cfg.get("tablespace", "") or "").strip()
        if cfg_tablespace:
            data_candidates.append(cfg_tablespace)

        conn_tablespace: str = str(self.db_manager.conn_params.get("tablespace", "") or "").strip()
        if conn_tablespace:
            data_candidates.append(conn_tablespace)

        try:
            user_tablespaces: Any = self.db_manager.execute_custom_one(self._ORACLE_USER_TABLESPACES_QUERY)
            normalized_user_rows = self._normalize_storage_rows(user_tablespaces)
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
            user_tablespaces: Any = self.db_manager.execute_custom_one(self._ORACLE_USER_TABLESPACES_QUERY)
            normalized_user_rows = self._normalize_storage_rows(user_tablespaces)
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
            row_data = cls._extract_mariadb_temp_data_from_chunk(variable_name, chunk, value)
            if row_data:
                parsed_rows.append(row_data)

        return parsed_rows

    @classmethod
    def _extract_mariadb_temp_data_from_chunk(cls, variable_name: str, chunk: str, raw_value: str) -> list[Any] | None:
        """Extrae datos de un chunk de innodb_temp_data_file_path."""
        tokens: list[str] = [token.strip() for token in chunk.split(":") if token.strip()]
        if not tokens:
            return None

        file_name: str = tokens[0]
        initial_mb: float | str = ""
        max_mb: float | str = ""
        idx: int = 1

        initial_mb, idx = cls._extract_initial_size_and_idx(tokens, idx)
        autoextend, max_mb = cls._extract_optional_mariadb_params(tokens, idx)

        return [variable_name, file_name, initial_mb, autoextend, max_mb, raw_value]

    @classmethod
    def _extract_initial_size_and_idx(cls, tokens: list[str], idx: int) -> tuple[float | str, int]:
        """Extrae tamaño inicial y devuelve el siguiente índice."""
        initial_mb: float | str = ""
        if idx < len(tokens):
            parsed_initial: float | None = cls._parse_mariadb_size_to_mb(tokens[idx])
            if parsed_initial is not None:
                initial_mb = parsed_initial
                idx += 1
        return initial_mb, idx

    @classmethod
    def _extract_optional_mariadb_params(cls, tokens: list[str], start_idx: int) -> tuple[str, float | str]:
        """Extrae parámetros opcionales autoextend y max de MariaDB."""
        autoextend: str = "No"
        max_mb: float | str = ""
        idx: int = start_idx

        while idx < len(tokens):
            current_token: str = tokens[idx].lower()
            if cls._is_autoextend_token(current_token):
                autoextend = "Si"
            elif cls._is_max_token(current_token, tokens, idx):
                max_mb = cls._parse_mariadb_size_to_mb(tokens[idx + 1]) or ""
                idx += 1
            idx += 1

        return autoextend, max_mb

    @staticmethod
    def _is_autoextend_token(token: str) -> bool:
        """Verifica si el token es autoextend."""
        return token == "autoextend"

    @staticmethod
    def _is_max_token(token: str, tokens: list[str], idx: int) -> bool:
        """Verifica si el token es max y hay siguiente elemento."""
        return token == "max" and idx + 1 < len(tokens)

    def _build_storage_query_specs(self) -> list[tuple[str, str]]:
        """Construye secciones de almacenamiento según el motor."""
        query_specs: list[tuple[str, str]] = [("ficheros_fisicos", "Ficheros físicos")]
        if self.db_type == "sqlite":
            query_specs.append(("sqlite_file_summary", "Ficheros físicos - resumen SQLite"))
        query_specs.append(("temp_tablespaces", "Temp tablespaces"))
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
                "sqlite_file_summary": ["Page count", "Page size", "Size bytes"],
                "temp_tablespaces": ["Temp store"],
            },
            "hsqldb": {"temp_tablespaces": ["Temp tablespace"]},
        }
        return headers_map.get(self.db_type, {}).get(query_name, [])

    def _build_storage_headers(self, query_name: str, rows: list[list[Any]]) -> list[str]:
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
        except Exception:
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
        for strategy in _STORAGE_QUERY_STRATEGIES:
            if strategy.can_handle(self, query_name):
                return strategy.process(self, query_name, query_title, database_name, query_params)
        return self._process_standard_storage_query(query_name, query_title, query_params)

    def _process_mariadb_temp_storage_variables_query(
        self,
        query_name: str,
        query_title: str,
        query_params: dict[str, Any],
    ) -> dict[str, Any]:
        """Procesa configuración temporal MariaDB basada en SHOW VARIABLES."""
        try:
            resolved = self.db_manager.resolve_query(query_name, **query_params)
        except QueryNotFoundError:
            return self._build_section_not_supported(query_name, query_title)
        except Exception as error:
            return self._build_section_missing_params(query_name, query_title, f"Parámetros inválidos: {error}")

        try:
            sql_text: str = str(resolved.final_sql or "")
            result_rows: Any = self.db_manager.execute_query_many(query_name, **query_params)
            normalized_rows: list[list[Any]] = self._normalize_storage_rows(result_rows)
            parsed_rows: list[list[Any]] = []
            for row in normalized_rows:
                variable_name: str = str(row[0]) if len(row) > 0 else "innodb_temp_data_file_path"
                raw_value: str = str(row[1]) if len(row) > 1 else ""
                parsed_rows.extend(self._parse_mariadb_temp_data_file_path_rows(variable_name, raw_value))

            headers: list[str] = self._build_storage_headers(query_name, parsed_rows)
            parsed_rows = self._format_storage_rows(headers, parsed_rows)
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
            return self._build_section_error(query_name, query_title, self._flatten_exception_messages(error))

    def _process_oracle_storage_query(self, query_name: str, query_title: str, database_name: str) -> dict[str, Any]:
        """Procesa consulta de almacenamiento específica para Oracle."""
        oracle_targets: dict[str, list[str]] = self._resolve_oracle_storage_tablespaces()
        oracle_tablespaces: list[str] = (
            oracle_targets.get("data_tablespaces", [])
            if query_name == "ficheros_fisicos"
            else oracle_targets.get("temp_tablespaces", [])
        )
        if not oracle_tablespaces:
            return self._build_section_missing_params(
                query_name,
                query_title,
                "No se pudieron resolver tablespaces Oracle para la consulta.",
            )

        collected_rows, collected_sql, collected_errors = self._collect_oracle_tablespace_data(
            query_name,
            database_name,
            oracle_tablespaces,
        )
        dedup_rows: list[list[Any]] = self._deduplicate_rows(collected_rows)
        headers: list[str] = self._build_storage_headers(query_name, dedup_rows)
        dedup_rows = self._format_storage_rows(headers, dedup_rows)

        return self._build_oracle_section(
            query_name,
            query_title,
            dedup_rows,
            headers,
            len(oracle_tablespaces),
            collected_errors,
            collected_sql,
        )

    def _collect_oracle_tablespace_data(
        self,
        query_name: str,
        database_name: str,
        oracle_tablespaces: list[str],
    ) -> tuple[list[list[Any]], list[str], list[str]]:
        """Recolecta datos de tablespaces Oracle."""
        collected_rows: list[list[Any]] = []
        collected_sql: list[str] = []
        collected_errors: list[str] = []

        for tablespace_name in oracle_tablespaces:
            local_params: dict[str, Any] = {"database": database_name, "tablespace": tablespace_name}
            try:
                sql_text: str = str(self.db_manager.resolve_query(query_name, **local_params).final_sql or "")
                result_rows: Any = self.db_manager.execute_query_many(query_name, **local_params)
                rows: list[list[Any]] = self._normalize_storage_rows(result_rows)
                collected_rows.extend(rows)
                collected_sql.append(sql_text)
            except Exception as error:
                collected_errors.append(f"{tablespace_name}: {error}")

        return collected_rows, collected_sql, collected_errors

    def _deduplicate_rows(self, rows: list[list[Any]]) -> list[list[Any]]:
        """Deduplica filas."""
        dedup_rows: list[list[Any]] = []
        seen_rows: set[tuple[Any, ...]] = set()
        for row in rows:
            row_key: tuple[Any, ...] = tuple(row)
            if row_key not in seen_rows:
                seen_rows.add(row_key)
                dedup_rows.append(row)
        return dedup_rows

    def _build_oracle_section(
        self,
        query_name: str,
        query_title: str,
        rows: list[list[Any]],
        headers: list[str],
        tablespace_count: int,
        errors: list[str],
        sql_list: list[str],
    ) -> dict[str, Any]:
        """Construye sección de resultado para Oracle."""
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
        except Exception as error:
            return self._build_section_missing_params(
                query_name,
                query_title,
                f"Parámetros inválidos: {error}",
            )

        if self._is_placeholder_storage_query(query_name, query_params):
            return self._build_section_not_supported(query_name, query_title)

        try:
            sql_text: str = str(resolved.final_sql or "")
            result_rows: Any = self.db_manager.execute_query_many(query_name, **query_params)
            rows: list[list[Any]] = self._normalize_storage_rows(result_rows)
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
        except Exception as error:
            flattened_error_msg: str = self._flatten_exception_messages(error)
            if self.db_type == "mariadb" and query_name == "temp_tablespaces":
                return self._build_mariadb_temp_tablespaces_error_section(query_name, query_title, flattened_error_msg)
            return self._build_section_error(query_name, query_title, flattened_error_msg)

    def _build_mariadb_temp_tablespaces_error_section(
        self,
        query_name: str,
        query_title: str,
        error_msg: str,
    ) -> dict[str, Any]:
        """Construye mensaje explícito para incidencias de information_schema.FILES."""
        normalized_error: str = str(error_msg or "").strip()
        lowered_error: str = normalized_error.lower()

        if "information_schema.files" in lowered_error and any(
            token in lowered_error for token in ("access denied", "permission", "denied", "1142", "1227")
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

        return self._build_section_error(query_name, query_title, normalized_error)

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
    logger: Any,
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
    logger: Any,
    print_config: dict[str, Any],
) -> dict[str, Any]:
    """Obtiene el informe de almacenamiento sin exponer bootstrap en la fachada documental."""
    runtime: StorageInventoryRuntime = build_storage_inventory_runtime(
        db_manager=db_manager,
        logger=logger,
        print_config=print_config,
    )
    return runtime.get_storage_inventory_report()


__all__: list[str] = [
    "StorageInventoryRuntime",
    "build_storage_inventory_runtime",
    "get_storage_inventory_report",
]
