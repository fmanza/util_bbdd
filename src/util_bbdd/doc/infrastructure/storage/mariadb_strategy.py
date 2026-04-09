"""Estrategias MariaDB del runtime de inventario de almacenamiento."""

from __future__ import annotations

import re

from dataclasses import dataclass
from typing import Any, Protocol

from ...._foundation.exceptions import DatabaseError, QueryNotFoundError
from .contracts import StorageInventoryManagerProtocol


class MariadbStorageRuntimeProtocol(Protocol):
    """Contrato mínimo del runtime usado por la estrategia MariaDB."""

    db_manager: StorageInventoryManagerProtocol

    @staticmethod
    def _flatten_exception_messages(error: Exception) -> str: ...

    def _normalize_storage_rows(self, rows: object) -> list[list[object]]: ...

    def _build_storage_headers(self, query_name: str, rows: list[list[object]]) -> list[str]: ...

    def _format_storage_rows(self, headers: list[str], rows: list[list[object]]) -> list[list[object]]: ...

    def _get_numeric_storage_indices(self, headers: list[str]) -> list[int]: ...

    def _build_section_not_supported(self, query_name: str, query_title: str) -> dict[str, Any]: ...

    def _build_section_missing_params(self, query_name: str, query_title: str, message: str) -> dict[str, Any]: ...

    def _build_section_error(self, query_name: str, query_title: str, error_msg: str) -> dict[str, Any]: ...


@dataclass(slots=True, frozen=True)
class MariadbStorageInventoryStrategy:
    """Lógica especializada para consultas de almacenamiento MariaDB."""

    _DEFAULT_VARIABLE_NAME: str = "innodb_temp_data_file_path"

    def process_temp_storage_variables_query(
        self,
        runtime: MariadbStorageRuntimeProtocol,
        query_name: str,
        query_title: str,
        query_params: dict[str, Any],
    ) -> dict[str, Any]:
        """Procesa configuración temporal MariaDB basada en ``SHOW VARIABLES``."""
        try:
            resolved = runtime.db_manager.resolve_query(query_name, **query_params)
        except QueryNotFoundError:
            return runtime._build_section_not_supported(query_name, query_title)
        except DatabaseError as error:
            return runtime._build_section_missing_params(query_name, query_title, f"Parámetros inválidos: {error}")

        try:
            sql_text: str = str(resolved.final_sql or "")
            result_rows: object = runtime.db_manager.execute_query_many(query_name, **query_params)
            normalized_rows: list[list[object]] = runtime._normalize_storage_rows(result_rows)
            parsed_rows: list[list[object]] = []
            for row in normalized_rows:
                variable_name: str = str(row[0]) if len(row) > 0 else self._DEFAULT_VARIABLE_NAME
                raw_value: str = str(row[1]) if len(row) > 1 else ""
                parsed_rows.extend(self.parse_temp_data_file_path_rows(variable_name, raw_value))

            headers: list[str] = runtime._build_storage_headers(query_name, parsed_rows)
            parsed_rows = runtime._format_storage_rows(headers, parsed_rows)
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
                "numeric_columns": runtime._get_numeric_storage_indices(headers),
            }
        except DatabaseError as error:
            return runtime._build_section_error(query_name, query_title, runtime._flatten_exception_messages(error))

    def build_temp_tablespaces_error_section(
        self,
        runtime: MariadbStorageRuntimeProtocol,
        query_name: str,
        query_title: str,
        error_msg: str,
    ) -> dict[str, Any]:
        """Construye mensaje explícito para incidencias de ``information_schema.FILES``."""
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

        return runtime._build_section_error(query_name, query_title, normalized_error)

    @staticmethod
    def parse_size_to_mb(size_value: str) -> float | None:
        """Convierte tamaños MariaDB tipo ``12M``/``5G`` a MB."""
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
    def parse_temp_data_file_path_rows(cls, variable_name: str, raw_value: str) -> list[list[object]]:
        """Parsea ``innodb_temp_data_file_path`` a filas tabulares."""
        value: str = str(raw_value or "").strip()
        if not value:
            return []

        parsed_rows: list[list[object]] = []
        for chunk in [part.strip() for part in value.split(";") if part.strip()]:
            row_data = cls.extract_temp_data_from_chunk(variable_name, chunk, value)
            if row_data:
                parsed_rows.append(row_data)

        return parsed_rows

    @classmethod
    def extract_temp_data_from_chunk(cls, variable_name: str, chunk: str, raw_value: str) -> list[object] | None:
        """Extrae datos de un chunk de ``innodb_temp_data_file_path``."""
        tokens: list[str] = [token.strip() for token in chunk.split(":") if token.strip()]
        if not tokens:
            return None

        file_name: str = tokens[0]
        initial_mb: float | str = ""
        max_mb: float | str = ""
        idx: int = 1

        initial_mb, idx = cls.extract_initial_size_and_idx(tokens, idx)
        autoextend, max_mb = cls.extract_optional_params(tokens, idx)

        return [variable_name, file_name, initial_mb, autoextend, max_mb, raw_value]

    @classmethod
    def extract_initial_size_and_idx(cls, tokens: list[str], idx: int) -> tuple[float | str, int]:
        """Extrae tamaño inicial y devuelve el siguiente índice."""
        initial_mb: float | str = ""
        if idx < len(tokens):
            parsed_initial: float | None = cls.parse_size_to_mb(tokens[idx])
            if parsed_initial is not None:
                initial_mb = parsed_initial
                idx += 1
        return initial_mb, idx

    @classmethod
    def extract_optional_params(cls, tokens: list[str], start_idx: int) -> tuple[str, float | str]:
        """Extrae parámetros opcionales ``autoextend`` y ``max`` de MariaDB."""
        autoextend: str = "No"
        max_mb: float | str = ""
        idx: int = start_idx

        while idx < len(tokens):
            current_token: str = tokens[idx].lower()
            if cls.is_autoextend_token(current_token):
                autoextend = "Si"
            elif cls.is_max_token(current_token, tokens, idx):
                max_mb = cls.parse_size_to_mb(tokens[idx + 1]) or ""
                idx += 1
            idx += 1

        return autoextend, max_mb

    @staticmethod
    def is_autoextend_token(token: str) -> bool:
        """Verifica si el token corresponde a ``autoextend``."""
        return token == "autoextend"

    @staticmethod
    def is_max_token(token: str, tokens: list[str], idx: int) -> bool:
        """Verifica si el token corresponde a ``max`` y hay valor siguiente."""
        return token == "max" and idx + 1 < len(tokens)
