"""Estrategias Oracle del runtime de inventario de almacenamiento."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ...._core.exceptions import DatabaseException
from .contracts import StorageInventoryManagerProtocol


class OracleStorageRuntimeProtocol(Protocol):
    """Contrato mínimo del runtime usado por la estrategia Oracle."""

    db_manager: StorageInventoryManagerProtocol
    print_config: dict[str, Any]
    _ORACLE_USER_TABLESPACES_QUERY: str

    def _normalize_storage_rows(self, rows: object) -> list[list[object]]: ...

    def _build_storage_headers(self, query_name: str, rows: list[list[object]]) -> list[str]: ...

    def _format_storage_rows(self, headers: list[str], rows: list[list[object]]) -> list[list[object]]: ...

    def _get_numeric_storage_indices(self, headers: list[str]) -> list[int]: ...

    def _build_section_missing_params(self, query_name: str, query_title: str, message: str) -> dict[str, Any]: ...


@dataclass(slots=True, frozen=True)
class OracleStorageInventoryStrategy:
    """Lógica especializada para consultas de almacenamiento Oracle."""

    def resolve_storage_tablespaces(self, runtime: OracleStorageRuntimeProtocol) -> dict[str, list[str]]:
        """Resuelve tablespaces Oracle separados por tipo."""
        return {
            "data_tablespaces": self.dedup_tablespaces(self.collect_data_tablespaces(runtime)),
            "temp_tablespaces": self.dedup_tablespaces(self.collect_temp_tablespaces(runtime)),
        }

    def collect_data_tablespaces(self, runtime: OracleStorageRuntimeProtocol) -> list[str]:
        """Recolecta tablespaces de datos desde configuración y usuario Oracle."""
        data_candidates: list[str] = []

        storage_cfg: object = runtime.print_config.get("storage", {})
        if isinstance(storage_cfg, dict):
            cfg_tablespace: str = str(storage_cfg.get("tablespace", "") or "").strip()
            if cfg_tablespace:
                data_candidates.append(cfg_tablespace)

        conn_tablespace: str = str(runtime.db_manager.conn_params.get("tablespace", "") or "").strip()
        if conn_tablespace:
            data_candidates.append(conn_tablespace)

        try:
            user_tablespaces: object = runtime.db_manager.execute_custom_one(runtime._ORACLE_USER_TABLESPACES_QUERY)
            normalized_user_rows = runtime._normalize_storage_rows(user_tablespaces)
            if normalized_user_rows and len(normalized_user_rows[0]) > 0:
                default_ts: str = str(normalized_user_rows[0][0] or "").strip()
                if default_ts:
                    data_candidates.append(default_ts)
        except DatabaseException:
            pass

        return data_candidates

    def collect_temp_tablespaces(self, runtime: OracleStorageRuntimeProtocol) -> list[str]:
        """Recolecta tablespaces temporales desde usuario Oracle."""
        temp_candidates: list[str] = []

        try:
            user_tablespaces: object = runtime.db_manager.execute_custom_one(runtime._ORACLE_USER_TABLESPACES_QUERY)
            normalized_user_rows = runtime._normalize_storage_rows(user_tablespaces)
            if normalized_user_rows and len(normalized_user_rows[0]) > 1:
                temp_ts: str = str(normalized_user_rows[0][1] or "").strip()
                if temp_ts:
                    temp_candidates.append(temp_ts)
        except DatabaseException:
            pass

        return temp_candidates

    @staticmethod
    def dedup_tablespaces(values: list[str]) -> list[str]:
        """Deduplica y normaliza lista de tablespaces."""
        unique_values: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized: str = value.upper()
            if normalized not in seen:
                seen.add(normalized)
                unique_values.append(value)
        return unique_values

    def process_storage_query(
        self,
        runtime: OracleStorageRuntimeProtocol,
        query_name: str,
        query_title: str,
        database_name: str,
    ) -> dict[str, Any]:
        """Procesa consulta de almacenamiento específica para Oracle."""
        oracle_targets: dict[str, list[str]] = self.resolve_storage_tablespaces(runtime)
        oracle_tablespaces: list[str] = (
            oracle_targets.get("data_tablespaces", [])
            if query_name == "ficheros_fisicos"
            else oracle_targets.get("temp_tablespaces", [])
        )
        if not oracle_tablespaces:
            return runtime._build_section_missing_params(
                query_name,
                query_title,
                "No se pudieron resolver tablespaces Oracle para la consulta.",
            )

        collected_rows, collected_sql, collected_errors = self.collect_tablespace_data(
            runtime=runtime,
            query_name=query_name,
            database_name=database_name,
            oracle_tablespaces=oracle_tablespaces,
        )
        dedup_rows: list[list[object]] = self.deduplicate_rows(collected_rows)
        headers: list[str] = runtime._build_storage_headers(query_name, dedup_rows)
        dedup_rows = runtime._format_storage_rows(headers, dedup_rows)

        return self.build_oracle_section(
            runtime=runtime,
            query_name=query_name,
            query_title=query_title,
            rows=dedup_rows,
            headers=headers,
            tablespace_count=len(oracle_tablespaces),
            errors=collected_errors,
            sql_list=collected_sql,
        )

    def collect_tablespace_data(
        self,
        *,
        runtime: OracleStorageRuntimeProtocol,
        query_name: str,
        database_name: str,
        oracle_tablespaces: list[str],
    ) -> tuple[list[list[object]], list[str], list[str]]:
        """Recolecta datos de tablespaces Oracle."""
        collected_rows: list[list[object]] = []
        collected_sql: list[str] = []
        collected_errors: list[str] = []

        for tablespace_name in oracle_tablespaces:
            local_params: dict[str, Any] = {"database": database_name, "tablespace": tablespace_name}
            try:
                sql_text: str = str(runtime.db_manager.resolve_query(query_name, **local_params).final_sql or "")
                result_rows: object = runtime.db_manager.execute_query_many(query_name, **local_params)
                rows: list[list[object]] = runtime._normalize_storage_rows(result_rows)
                collected_rows.extend(rows)
                collected_sql.append(sql_text)
            except DatabaseException as error:
                collected_errors.append(f"{tablespace_name}: {error}")

        return collected_rows, collected_sql, collected_errors

    @staticmethod
    def deduplicate_rows(rows: list[list[object]]) -> list[list[object]]:
        """Deduplica filas."""
        dedup_rows: list[list[object]] = []
        seen_rows: set[tuple[object, ...]] = set()
        for row in rows:
            row_key: tuple[object, ...] = tuple(row)
            if row_key not in seen_rows:
                seen_rows.add(row_key)
                dedup_rows.append(row)
        return dedup_rows

    def build_oracle_section(
        self,
        *,
        runtime: OracleStorageRuntimeProtocol,
        query_name: str,
        query_title: str,
        rows: list[list[object]],
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
                "numeric_columns": runtime._get_numeric_storage_indices(headers),
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
            "numeric_columns": runtime._get_numeric_storage_indices(headers),
        }
