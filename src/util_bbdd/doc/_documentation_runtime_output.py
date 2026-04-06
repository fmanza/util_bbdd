"""Helpers internos para nombres y rutas de salida documental."""

from __future__ import annotations

import time

from datetime import datetime
from pathlib import Path

from ._documentation_runtime_types import ConnectionParams, DocumentationOutputManagerProtocol, OutputCache

_DEFAULT_SUPPORTED_OUTPUT_FORMATS: set[str] = {"word", "excel", "html"}
_DEFAULT_FORMAT_FOLDER_MAP: dict[str, str] = {
    "html": "HTML",
    "word": "WORD",
    "excel": "EXCEL",
}


class DocumentationOutputRuntime:
    """Servicio OO para reglas de nombres y rutas de salida documental."""

    def __init__(
        self,
        *,
        supported_output_formats: set[str] | None = None,
        format_folder_map: dict[str, str] | None = None,
    ) -> None:
        self._supported_output_formats: set[str] = set(supported_output_formats or _DEFAULT_SUPPORTED_OUTPUT_FORMATS)
        self._format_folder_map: dict[str, str] = dict(format_folder_map or _DEFAULT_FORMAT_FOLDER_MAP)

    @property
    def supported_output_formats(self) -> set[str]:
        """Devuelve los formatos de salida soportados."""
        return set(self._supported_output_formats)

    @property
    def format_folder_map(self) -> dict[str, str]:
        """Devuelve el mapeo formato -> carpeta de salida."""
        return dict(self._format_folder_map)

    def normalize_sqlite_identifier(self, identifier: str) -> str:
        """Normaliza un identificador SQLite extrayendo el nombre de fichero."""
        normalized_identifier: str = identifier.replace("\\", "/")
        sqlite_name: str = normalized_identifier.split("/")[-1] if normalized_identifier else ""
        if sqlite_name.lower().endswith(".sqlite"):
            sqlite_name = sqlite_name[:-7]
        elif sqlite_name.lower().endswith(".db"):
            sqlite_name = sqlite_name[:-3]
        return sqlite_name or "sqlite"

    def resolve_output_filename_identifier(self, db_type: str, database: str, conn_params: ConnectionParams) -> str:
        """Resuelve el identificador base del fichero de salida."""
        identifier: str = str(database or "").strip()
        if db_type == "oracle":
            oracle_user: str = str(conn_params.get("user", "") or "").strip()
            identifier = oracle_user or identifier
        elif not identifier:
            fallback_user: str = str(conn_params.get("user", "") or "").strip()
            identifier = fallback_user or identifier

        if not identifier:
            identifier = db_type

        if db_type == "sqlite":
            identifier = self.normalize_sqlite_identifier(identifier)

        return identifier

    def generate_auto_output_filename(
        self,
        *,
        db_type: str,
        database: str,
        conn_params: ConnectionParams,
        output_dir: Path,
        output_cache: OutputCache,
        batch_window_seconds: int,
        current_time: float | None = None,
        current_datetime: datetime | None = None,
    ) -> Path:
        """Genera un nombre automático reutilizable dentro de una ventana temporal corta."""
        resolved_datetime: datetime = current_datetime or datetime.now()
        timestamp: str = resolved_datetime.strftime("%Y%m%d_%H%M%S")
        normalized_conn_params: ConnectionParams = conn_params if isinstance(conn_params, dict) else {}
        identifier: str = self.resolve_output_filename_identifier(db_type, database, normalized_conn_params)
        safe_identifier: str = identifier.replace(" ", "_").replace("/", "_").replace("\\", "_")
        cache_key: tuple[str, str] = (str(output_dir), safe_identifier)
        now: float = current_time if current_time is not None else time.time()
        cached: tuple[float, str] | None = output_cache.get(cache_key)
        if cached is not None:
            cached_at, cached_name = cached
            if now - cached_at <= batch_window_seconds:
                return Path(cached_name)

        generated_name: str = f"{safe_identifier}-{timestamp}"
        output_cache[cache_key] = (now, generated_name)
        return Path(generated_name)

    def resolve_document_output_filename(
        self,
        *,
        fichero_salida: Path | None,
        db_manager: DocumentationOutputManagerProtocol,
        output_dir: Path,
        output_cache: OutputCache,
        batch_window_seconds: int,
    ) -> Path:
        """Resuelve el nombre base de salida, reutilizando autogeneración cuando no se informa uno explícito."""
        if fichero_salida is not None:
            return fichero_salida

        raw_conn_params = getattr(db_manager, "conn_params", None)
        conn_params: ConnectionParams = raw_conn_params if isinstance(raw_conn_params, dict) else {}
        return self.generate_auto_output_filename(
            db_type=str(getattr(db_manager, "db_type", "") or ""),
            database=str(getattr(db_manager, "database", "") or ""),
            conn_params=conn_params,
            output_dir=output_dir,
            output_cache=output_cache,
            batch_window_seconds=batch_window_seconds,
        )

    def normalize_output_formats(self, formatos: list[str] | None) -> list[str]:
        """Normaliza y valida formatos de salida solicitados."""
        if formatos is None:
            return ["word"]

        if not isinstance(formatos, list):
            raise TypeError("formatos debe ser una lista de strings")

        normalized: list[str] = []
        seen: set[str] = set()
        for raw_format in formatos:
            normalized_format: str = str(raw_format or "").strip().lower()
            if not normalized_format:
                continue
            if normalized_format not in self._supported_output_formats:
                raise ValueError(f"Formato no soportado: {raw_format}. Use 'word', 'excel' o 'html'")
            if normalized_format in seen:
                continue
            seen.add(normalized_format)
            normalized.append(normalized_format)

        if not normalized:
            raise ValueError("No se informaron formatos validos en 'formatos'")

        return normalized

    @staticmethod
    def get_execution_root_name(fichero_salida: Path) -> str:
        """Obtiene el nombre de la carpeta raiz por ejecucion."""
        candidate: str = fichero_salida.stem if fichero_salida.suffix else str(fichero_salida)
        safe_name: str = Path(candidate).name.strip()
        return safe_name or "documentacion"

    @staticmethod
    def get_output_base_filename(fichero_salida: Path) -> str:
        """Obtiene el nombre base de archivo para salidas de documento."""
        base_name: str = Path(fichero_salida).stem if fichero_salida.suffix else Path(str(fichero_salida)).name
        normalized: str = str(base_name or "").strip()
        return normalized or "documentacion"

    def ensure_execution_root(self, directorio_salida: Path, fichero_salida: Path) -> Path:
        """Crea si no existe la carpeta raiz por ejecucion."""
        execution_root: Path = directorio_salida / self.get_execution_root_name(fichero_salida)
        execution_root.mkdir(parents=True, exist_ok=True)
        return execution_root

    def get_format_output_dir(self, directorio_salida: Path, fichero_salida: Path, formato: str) -> Path:
        """Resuelve y crea la carpeta del formato solicitado."""
        execution_root: Path = self.ensure_execution_root(directorio_salida, fichero_salida)
        normalized: str = str(formato or "").strip().lower()
        if normalized not in self._format_folder_map:
            raise ValueError(f"Formato no soportado para salida: {formato}")

        output_dir: Path = execution_root / self._format_folder_map[normalized]
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    @staticmethod
    def resolve_generator_database_context(
        *,
        db_type: str,
        database: str,
        conn_params: ConnectionParams,
        query_context_database: str,
    ) -> str:
        """Resuelve el identificador mostrado en generadores y metadatos."""
        resolved_context: str = str(query_context_database or "").strip()
        if resolved_context:
            return resolved_context

        normalized_db_type: str = str(db_type or "").strip().lower() or "unknown"
        database_value: str = str(database or "").strip()
        user_value: str = str(conn_params.get("user", "") or "").strip()
        schema_value: str = str(conn_params.get("schema", "") or "").strip()

        context_resolver: dict[str, str] = {
            "oracle": user_value or database_value or normalized_db_type,
            "postgresql": schema_value or database_value or "public",
            "hsqldb": schema_value or database_value or "PUBLIC",
            "sqlserver": schema_value or database_value or "dbo",
            "sqlite": database_value or normalized_db_type,
        }

        return context_resolver.get(normalized_db_type, database_value or user_value or normalized_db_type)


__all__: list[str] = [
    "DocumentationOutputRuntime",
]
