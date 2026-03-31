"""Helpers internos para bootstrap y layout de DatabaseDocumentation."""

from __future__ import annotations

import json

from pathlib import Path
from typing import Any, cast

HeadersConfig = dict[str, Any]
ConnectionParams = dict[str, Any]

_SUPPORTED_OUTPUT_FORMATS: set[str] = {"word", "excel", "html"}
_FORMAT_FOLDER_MAP: dict[str, str] = {
    "html": "HTML",
    "word": "WORD",
    "excel": "EXCEL",
}


def normalize_sqlite_identifier(identifier: str) -> str:
    """Normaliza un identificador SQLite extrayendo el nombre de fichero."""
    normalized_identifier: str = identifier.replace("\\", "/")
    sqlite_name: str = normalized_identifier.split("/")[-1] if normalized_identifier else ""
    if sqlite_name.lower().endswith(".sqlite"):
        sqlite_name = sqlite_name[:-7]
    elif sqlite_name.lower().endswith(".db"):
        sqlite_name = sqlite_name[:-3]
    return sqlite_name or "sqlite"


def resolve_output_filename_identifier(db_type: str, database: str, conn_params: ConnectionParams) -> str:
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
        identifier = normalize_sqlite_identifier(identifier)

    return identifier


def load_headers_config(headers_file: Path) -> HeadersConfig:
    """Carga la configuracion JSON de cabeceras."""
    try:
        with headers_file.open(encoding="utf-8") as file_handle:
            loaded_headers: Any = json.load(file_handle)
            return cast(HeadersConfig, loaded_headers)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Fichero de headers no encontrado: {headers_file}") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"Error al leer fichero JSON de headers: {e}") from e


def build_headers(headers_config: HeadersConfig, db_type: str) -> dict[str, list[str]]:
    """Construye cabeceras legibles combinando base y overrides por motor."""
    headers: dict[str, list[str]] = {}
    headers_cfg = cast(dict[str, dict[str, Any]], headers_config["headers"])
    labels_cfg = cast(dict[str, dict[str, dict[str, str]]], headers_config["labels"])

    for section, config in headers_cfg.items():
        base_headers: list[str] = list(config["base"])
        db_specific_headers: list[str] = list(config.get(db_type, []))
        labels: dict[str, str] = labels_cfg.get(section, {}).get(db_type, {})
        header_list: list[str] = base_headers + db_specific_headers
        headers[section] = [labels.get(header, header) for header in header_list]

    return headers


def normalize_output_formats(formatos: list[str] | None) -> list[str]:
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
        if normalized_format not in _SUPPORTED_OUTPUT_FORMATS:
            raise ValueError(f"Formato no soportado: {raw_format}. Use 'word', 'excel' o 'html'")
        if normalized_format in seen:
            continue
        seen.add(normalized_format)
        normalized.append(normalized_format)

    if not normalized:
        raise ValueError("No se informaron formatos validos en 'formatos'")

    return normalized


def get_execution_root_name(fichero_salida: Path) -> str:
    """Obtiene el nombre de la carpeta raiz por ejecucion."""
    candidate: str = fichero_salida.stem if fichero_salida.suffix else str(fichero_salida)
    safe_name: str = Path(candidate).name.strip()
    return safe_name or "documentacion"


def get_output_base_filename(fichero_salida: Path) -> str:
    """Obtiene el nombre base de archivo para salidas de documento."""
    base_name: str = Path(fichero_salida).stem if fichero_salida.suffix else Path(str(fichero_salida)).name
    normalized: str = str(base_name or "").strip()
    return normalized or "documentacion"


def ensure_execution_root(directorio_salida: Path, fichero_salida: Path) -> Path:
    """Crea si no existe la carpeta raiz por ejecucion."""
    execution_root: Path = directorio_salida / get_execution_root_name(fichero_salida)
    execution_root.mkdir(parents=True, exist_ok=True)
    return execution_root


def get_format_output_dir(directorio_salida: Path, fichero_salida: Path, formato: str) -> Path:
    """Resuelve y crea la carpeta del formato solicitado."""
    execution_root: Path = ensure_execution_root(directorio_salida, fichero_salida)
    normalized: str = str(formato or "").strip().lower()
    if normalized not in _FORMAT_FOLDER_MAP:
        raise ValueError(f"Formato no soportado para salida: {formato}")

    output_dir: Path = execution_root / _FORMAT_FOLDER_MAP[normalized]
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


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
    "build_headers",
    "ensure_execution_root",
    "get_execution_root_name",
    "get_format_output_dir",
    "get_output_base_filename",
    "load_headers_config",
    "normalize_output_formats",
    "normalize_sqlite_identifier",
    "resolve_generator_database_context",
    "resolve_output_filename_identifier",
]
