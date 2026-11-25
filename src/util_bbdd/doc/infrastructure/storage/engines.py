"""Qué inventaría la documentación del almacenamiento de cada motor: consultas, títulos, cabeceras y tratamiento.

Una entrada por motor (A-01). Las consultas son las de ``metadata.storage``; aquí solo se decide cuáles se muestran, en
qué orden, con qué cabeceras y, si hace falta, cómo se transforman sus filas o sus errores:

- MySQL/MariaDB: ``temp_storage_variables`` trae ``innodb_temp_data_file_path`` en bruto y se desglosa en columnas; los
  errores de ``information_schema.FILES`` (sin permiso, no existe) se explican.
- Oracle: ``ficheros_fisicos``/``temp_tablespaces`` se piden por tablespace (los de datos o temporales del usuario,
  además del configurado) y se juntan.

Un motor que no está aquí recibe un aviso de inventario genérico (HSQLDB, que no tiene consultas de almacenamiento).
"""

from __future__ import annotations

import re

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ...._core.exceptions import DatabaseException
from ...._core.i18n import Translator

if TYPE_CHECKING:
    from .runtime import StorageInventoryRuntime

Section = dict[str, Any]
Rows = list[list[object]]

FICHEROS_FISICOS: str = "Ficheros físicos"
TEMP_TABLESPACES: str = "Temp tablespaces"
_TAMANO_MB: str = "Tamaño (MB)"
_MAXIMO_MB: str = "Maximo (MB)"
_TIPO_FICHERO: str = "Tipo de fichero"


@dataclass(frozen=True, slots=True)
class StorageQuerySpec:
    """Una sección del inventario.

    Attributes:
        name: Consulta de ``metadata.storage``.
        title: Título de la sección.
        headers: Cabeceras legibles (se recortan a las columnas devueltas).
        process: Sustituye al tratamiento estándar (ejecutar, formatear) de la consulta.
        on_error: Sección propia para un error de base de datos (``None`` = la sección de error estándar); recibe el
            ``Translator`` del informe para su mensaje.

    El título y las cabeceras se declaran en español: el informe los pasa al idioma de salida con ``localize_label``.
    """

    name: str
    title: str
    headers: tuple[str, ...] = ()
    process: Callable[[StorageInventoryRuntime, StorageQuerySpec, str], Section] | None = None
    on_error: Callable[[StorageQuerySpec, str, Translator], Section | None] | None = None


@dataclass(frozen=True, slots=True)
class StorageEngineSpec:
    """Inventario de un motor: sus secciones, en orden, y el tablespace por defecto (si lo hay)."""

    queries: tuple[StorageQuerySpec, ...]
    default_tablespace: Callable[[StorageInventoryRuntime], str] = field(default=lambda _runtime: "")


# ── MySQL / MariaDB ──────────────────────────────────────────────────────────


def parse_size_to_mb(size_value: str) -> float | None:
    """Convierte tamaños de MySQL/MariaDB tipo ``12M``/``5G`` a MB (sin unidad = MB)."""
    normalized: str = str(size_value or "").strip().upper()
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([KMGT])?B?", normalized)
    if not match:
        return None
    factor_by_unit: dict[str, float] = {"K": 1 / 1024, "M": 1, "G": 1024, "T": 1024 * 1024}
    return round(float(match.group(1)) * factor_by_unit[match.group(2) or "M"], 2)


def parse_temp_data_file_path_rows(variable_name: str, raw_value: str, translator: Translator | None = None) -> Rows:
    """Desglosa ``innodb_temp_data_file_path`` (``ibtmp1:12M:autoextend:max:5G;…``) en una fila por fichero.

    Returns:
        ``[variable, fichero, inicial MB, Si/No autoextend, máximo MB, valor bruto]`` por cada fichero (``Si``/``No``
        en el idioma de ``translator``; español por defecto).
    """
    tr = translator or Translator()
    value: str = str(raw_value or "").strip()
    rows: Rows = []
    for chunk in (part.strip() for part in value.split(";")):
        tokens: list[str] = [token.strip() for token in chunk.split(":") if token.strip()]
        if not tokens:
            continue
        index: int = 1
        initial_mb: float | str = ""
        if index < len(tokens) and (parsed := parse_size_to_mb(tokens[index])) is not None:
            initial_mb = parsed
            index += 1
        autoextend: str = tr.t("doc.common.no")
        max_mb: float | str = ""
        while index < len(tokens):
            token: str = tokens[index].lower()
            if token == "autoextend":
                autoextend = tr.t("doc.storage.value.yes")
            elif token == "max" and index + 1 < len(tokens):
                max_mb = parse_size_to_mb(tokens[index + 1]) or ""
                index += 1
            index += 1
        rows.append([variable_name, tokens[0], initial_mb, autoextend, max_mb, value])
    return rows


def _process_innodb_temp_variables(runtime: StorageInventoryRuntime, spec: StorageQuerySpec, database: str) -> Section:
    """``SHOW VARIABLES`` de los temporales InnoDB, con ``innodb_temp_data_file_path`` desglosado."""
    outcome = runtime.run_query(spec, database=database)
    if isinstance(outcome, dict):
        return outcome
    sql_text, raw_rows = outcome
    rows: Rows = []
    for row in raw_rows:
        variable_name: str = str(row[0]) if len(row) > 0 else "innodb_temp_data_file_path"
        rows.extend(
            parse_temp_data_file_path_rows(variable_name, str(row[1]) if len(row) > 1 else "", runtime.translator)
        )
    message: str = runtime.translator.t("doc.storage.message.innodb_ok" if rows else "doc.storage.message.innodb_empty")
    return runtime.ok_section(spec, sql_text, rows, message=message)


def _explain_files_error(spec: StorageQuerySpec, error_msg: str, translator: Translator) -> Section | None:
    """Explica los errores de ``information_schema.FILES`` (sin permiso / no existe en el servidor)."""
    lowered: str = error_msg.lower()
    if "information_schema.files" not in lowered:
        return None
    if any(token in lowered for token in ("access denied", "permission", "denied", "1142", "1227")):
        return section(spec, "error", translator.t("doc.storage.message.files_denied"))
    if any(token in lowered for token in ("doesn't exist", "does not exist", "unknown table", "unknown column")):
        return section(spec, "not_supported", translator.t("doc.storage.message.files_missing"))
    return None


# ── Oracle ───────────────────────────────────────────────────────────────────


def _oracle_user_tablespaces(runtime: StorageInventoryRuntime) -> tuple[str, str]:
    """``(tablespace por defecto, tablespace temporal)`` del usuario conectado (vacíos si no se pueden leer)."""
    try:
        rows: Rows = runtime.normalize_rows(runtime.db_manager.get_storage_rows("user_tablespaces"))
    except DatabaseException:
        return "", ""
    first: list[object] = rows[0] if rows else []
    default_ts: str = str(first[0] or "").strip() if len(first) > 0 else ""
    temp_ts: str = str(first[1] or "").strip() if len(first) > 1 else ""
    return default_ts, temp_ts


def _oracle_default_tablespace(runtime: StorageInventoryRuntime) -> str:
    default_ts, temp_ts = _oracle_user_tablespaces(runtime)
    return default_ts or temp_ts


def _unique_ignoring_case(values: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value.upper() not in seen:
            seen.add(value.upper())
            unique.append(value)
    return unique


def _process_oracle_tablespaces(runtime: StorageInventoryRuntime, spec: StorageQuerySpec, database: str) -> Section:
    """Ejecuta la consulta por cada tablespace de datos (``ficheros_fisicos``) o temporal del usuario y las junta."""
    default_ts, temp_ts = _oracle_user_tablespaces(runtime)
    tablespaces: list[str] = _unique_ignoring_case(
        [*runtime.configured_tablespaces(), default_ts] if spec.name == "ficheros_fisicos" else [temp_ts]
    )
    if not tablespaces:
        return section(spec, "missing_params", runtime.translator.t("doc.storage.message.oracle_no_tablespaces"))

    rows: Rows = []
    sql_list: list[str] = []
    errors: list[str] = []
    for tablespace in tablespaces:
        try:
            sql_text, tablespace_rows = runtime.execute(spec.name, database=database, tablespace=tablespace)
        except DatabaseException as error:
            errors.append(f"{tablespace}: {error}")
            continue
        rows.extend(row for row in tablespace_rows if row not in rows)
        sql_list.append(sql_text)

    sql_joined: str = "\n\n".join(sql_list)
    tr: Translator = runtime.translator
    if rows:
        message: str = tr.t("doc.storage.message.oracle_ok", count=len(tablespaces))
        if errors:
            message = tr.t("doc.storage.message.partial_errors", message=message, errors=" | ".join(errors))
        return runtime.ok_section(spec, sql_joined, rows, message=message)
    if errors:
        return runtime.ok_section(
            spec,
            sql_joined,
            rows,
            message=tr.t("doc.storage.message.query_error", error=" | ".join(errors)),
            status="error",
        )
    return runtime.ok_section(spec, sql_joined, rows, message=tr.t("doc.storage.message.no_data"))


# ── Tabla por motor ──────────────────────────────────────────────────────────


def section(spec: StorageQuerySpec, status: str, message: str) -> Section:
    """Sección sin filas (no disponible, faltan parámetros, error…)."""
    return {
        "query": spec.name,
        "title": spec.title,
        "status": status,
        "message": message,
        "sql": "",
        "headers": [],
        "rows": [],
        "numeric_columns": [],
    }


_MYSQL_FAMILY = StorageEngineSpec(
    queries=(
        StorageQuerySpec(
            "ficheros_fisicos",
            FICHEROS_FISICOS,
            ("DB", "Objeto", "Motor", "Datos (MB)", "Indices (MB)", "Total (MB)"),
        ),
        StorageQuerySpec(
            "temp_tablespaces",
            TEMP_TABLESPACES,
            ("Tablespace", "Archivo", "Extent (MB)", "Inicial (MB)", _MAXIMO_MB),
            on_error=_explain_files_error,
        ),
        StorageQuerySpec(
            "temp_storage_variables",
            "Configuración temporales InnoDB",
            ("Variable", "Archivo", "Inicial (MB)", "Autoextend", _MAXIMO_MB, "Valor bruto"),
            process=_process_innodb_temp_variables,
        ),
    )
)

_ORACLE_HEADERS: tuple[str, ...] = (
    "Tablespace",
    "Archivo",
    _TAMANO_MB,
    "Estado",
    _TIPO_FICHERO,
    "Autoextensible",
    _MAXIMO_MB,
)
_SQLSERVER_HEADERS: tuple[str, ...] = (
    "Database",
    "Nombre logico",
    _TIPO_FICHERO,
    "Archivo fisico",
    _TAMANO_MB,
    "Tamano maximo (MB)",
    "Crecimiento en porcentaje",
    "Configuracion crecimiento",
)

ENGINE_SPECS: dict[str, StorageEngineSpec] = {
    "mysql": _MYSQL_FAMILY,
    "mariadb": _MYSQL_FAMILY,
    "postgresql": StorageEngineSpec(
        queries=(
            StorageQuerySpec("ficheros_fisicos", FICHEROS_FISICOS, ("Tablespace", "Ruta filesystem", "Tamaño total")),
            StorageQuerySpec("temp_tablespaces", TEMP_TABLESPACES, (TEMP_TABLESPACES,)),
        ),
        default_tablespace=lambda _runtime: "pg_default",
    ),
    "oracle": StorageEngineSpec(
        queries=(
            StorageQuerySpec(
                "ficheros_fisicos", FICHEROS_FISICOS, _ORACLE_HEADERS, process=_process_oracle_tablespaces
            ),
            StorageQuerySpec(
                "temp_tablespaces", TEMP_TABLESPACES, _ORACLE_HEADERS, process=_process_oracle_tablespaces
            ),
        ),
        default_tablespace=_oracle_default_tablespace,
    ),
    # B-01: antes faltaba aquí y cada documento de SQL Server avisaba de un inventario «genérico»
    "sqlserver": StorageEngineSpec(
        queries=(
            StorageQuerySpec("ficheros_fisicos", FICHEROS_FISICOS, _SQLSERVER_HEADERS),
            StorageQuerySpec("temp_tablespaces", TEMP_TABLESPACES, _SQLSERVER_HEADERS),
        )
    ),
    "sqlite": StorageEngineSpec(
        queries=(
            StorageQuerySpec("ficheros_fisicos", FICHEROS_FISICOS, ("Seq", "Nombre", "Archivo")),
            StorageQuerySpec(
                "sqlite_file_summary", f"{FICHEROS_FISICOS} - resumen SQLite", ("Page count", "Page size", "Size bytes")
            ),
            StorageQuerySpec("temp_tablespaces", TEMP_TABLESPACES, ("Temp store",)),
        )
    ),
}

#: Secciones de un motor sin entrada en ``ENGINE_SPECS`` (precedidas de un aviso).
GENERIC_SPEC = StorageEngineSpec(
    queries=(
        StorageQuerySpec("ficheros_fisicos", FICHEROS_FISICOS),
        StorageQuerySpec("temp_tablespaces", TEMP_TABLESPACES),
    )
)

GENERIC_NOTICE_TITLE: str = "Aviso: estrategia de almacenamiento genérica"

#: Títulos y cabeceras en español de las secciones → clave del catálogo ``doc``; los que no están aquí son iguales en
#: todos los idiomas (``Tablespace``, ``DB``, ``Page size``…).
_LABEL_KEYS: dict[str, str] = {
    FICHEROS_FISICOS: "doc.storage.title.physical_files",
    f"{FICHEROS_FISICOS} - resumen SQLite": "doc.storage.title.sqlite_file_summary",
    "Configuración temporales InnoDB": "doc.storage.title.innodb_temp",
    GENERIC_NOTICE_TITLE: "doc.storage.title.generic_notice",
    "Objeto": "doc.storage.header.object",
    "Motor": "doc.storage.header.engine",
    "Datos (MB)": "doc.storage.header.data_mb",
    "Indices (MB)": "doc.storage.header.indexes_mb",
    "Archivo": "doc.storage.header.file",
    "Inicial (MB)": "doc.storage.header.initial_mb",
    _MAXIMO_MB: "doc.storage.header.max_mb",
    "Valor bruto": "doc.storage.header.raw_value",
    _TAMANO_MB: "doc.storage.header.size_mb",
    "Estado": "doc.storage.header.status",
    _TIPO_FICHERO: "doc.storage.header.file_type",
    "Autoextensible": "doc.storage.header.autoextensible",
    "Nombre logico": "doc.storage.header.logical_name",
    "Archivo fisico": "doc.storage.header.physical_file",
    "Tamano maximo (MB)": "doc.storage.header.max_size_mb",
    "Crecimiento en porcentaje": "doc.storage.header.growth_percent",
    "Configuracion crecimiento": "doc.storage.header.growth_settings",
    "Ruta filesystem": "doc.storage.header.filesystem_path",
    "Tamaño total": "doc.storage.header.total_size",
    "Nombre": "doc.storage.header.name",
}


def localize_label(text: str, translator: Translator) -> str:
    """Título o cabecera de una sección (declarados en español) en el idioma de ``translator``."""
    key: str | None = _LABEL_KEYS.get(text)
    return translator.t(key) if key else text


__all__: list[str] = [
    "ENGINE_SPECS",
    "GENERIC_SPEC",
    "StorageEngineSpec",
    "StorageQuerySpec",
    "localize_label",
    "parse_size_to_mb",
    "parse_temp_data_file_path_rows",
    "section",
]
