"""Inventario de almacenamiento de la documentación: ejecuta las secciones de ``engines.ENGINE_SPECS`` de un motor."""

from __future__ import annotations

import re

from dataclasses import dataclass, field
from typing import Any, cast

from ...._core.exceptions import DatabaseException, QueryNotFoundError, QueryParameterError
from ...._core.i18n import Translator
from ....metadata.storage import storage_query, storage_query_params
from ...application._internal_ports import StorageReportServicePort
from ...application.ports import DocumentationBackendPort, LoggerProtocol
from .contracts import StorageInventoryManagerProtocol
from .engines import (
    ENGINE_SPECS,
    GENERIC_NOTICE_TITLE,
    GENERIC_SPEC,
    Rows,
    Section,
    StorageEngineSpec,
    StorageQuerySpec,
    localize_label,
    section,
)
from .payload import StorageInventoryReportPayload, StorageSectionPayload

# Cabeceras de tamaño: «(MB)», «Size…», «Tamaño…» como palabra (B-03: «mb» suelto marcaba «Nombre lógico»)
_SIZE_HEADER = re.compile(r"\b(?:mb|size|tama[nñ]o)\b", re.IGNORECASE)


@dataclass(slots=True)
class StorageInventoryRuntime:
    """Construye el informe de almacenamiento consumido por los generadores.

    Títulos, cabeceras, mensajes y tamaños salen en el idioma de ``translator`` (español por defecto); las columnas de
    tamaño se detectan sobre las cabeceras declaradas (en español), así que no dependen del idioma.

    Examples:
        >>> runtime = StorageInventoryRuntime(manager, logger, "mariadb", "ventas", print_config={})
        >>> runtime.get_storage_inventory_report()["sections"][0]["title"]
        'Ficheros físicos'
    """

    db_manager: StorageInventoryManagerProtocol
    logger: LoggerProtocol
    db_type: str
    database: str
    print_config: dict[str, Any]
    translator: Translator = field(default_factory=Translator)
    _tablespace: str = field(default="", init=False, repr=False)

    @property
    def engine_spec(self) -> StorageEngineSpec:
        """Secciones del motor; un motor sin entrada usa las genéricas."""
        return ENGINE_SPECS.get(self.db_type, GENERIC_SPEC)

    def get_storage_inventory_report(self) -> dict[str, Any]:
        """Obtiene informe unificado de almacenamiento para Word/Excel/HTML."""
        database_name: str = str(self.database or "").strip()
        configured: list[str] = self.configured_tablespaces()
        self._tablespace = configured[0] if configured else self.engine_spec.default_tablespace(self)

        sections: list[StorageSectionPayload] = []
        if self.db_type not in ENGINE_SPECS:
            self.logger.warning(
                f"Motor '{self.db_type}' sin estrategia de almacenamiento dedicada; usando fallback genérico"
            )
            notice = StorageQuerySpec("generic_storage_fallback_notice", GENERIC_NOTICE_TITLE)
            message: str = self.translator.t("doc.storage.message.generic_fallback")
            sections.append(
                StorageSectionPayload.from_mapping(self._localize(section(notice, "not_supported", message)))
            )
        for spec in self.engine_spec.queries:
            processed: Section = (
                spec.process(self, spec, database_name) if spec.process else self._process_standard(spec, database_name)
            )
            sections.append(StorageSectionPayload.from_mapping(self._localize(processed)))

        return StorageInventoryReportPayload(
            db_type=self.db_type,
            database=self.database,
            tablespace=self._tablespace,
            sections=tuple(sections),
        ).to_dict()

    # ── API para las secciones (engines.py) ──────────────────────────────────
    def configured_tablespaces(self) -> list[str]:
        """Tablespaces indicados por el usuario: ``imprimir.storage``/``almacenamiento.tablespace`` y ``conn_params``."""
        storage_cfg: object = self.print_config.get("storage")
        if not isinstance(storage_cfg, dict):
            storage_cfg = self.print_config.get("almacenamiento", {})
        values: list[str] = [
            str(storage_cfg.get("tablespace", "") or "").strip() if isinstance(storage_cfg, dict) else "",
            str(self.db_manager.conn_params.get("tablespace", "") or "").strip(),
        ]
        return [value for value in values if value]

    def execute(self, query_name: str, *, database: str, tablespace: str) -> tuple[str, Rows]:
        """SQL (de ``metadata.storage``, con ``:nombre``) y filas de una consulta de almacenamiento.

        Raises:
            QueryNotFoundError: El motor no tiene la consulta.
            QueryParameterError: Falta un parámetro que la consulta necesita (``tablespace``).
            DatabaseException: Error del motor al ejecutarla.
        """
        sql = storage_query(self.db_type, query_name)
        if sql is None:
            raise QueryNotFoundError(f"'{query_name}' no existe para {self.db_type}")
        params: dict[str, Any] = {"schema": database or None, "tablespace": tablespace or None}
        missing = [
            name for name in storage_query_params(self.db_type, query_name) if name != "schema" and not params[name]
        ]
        if missing:
            raise QueryParameterError(f"falta {', '.join(missing)}")
        rows = self.db_manager.get_storage_rows(query_name, **{k: v for k, v in params.items() if v is not None})
        return sql, self.normalize_rows(rows)

    def run_query(self, spec: StorageQuerySpec, *, database: str) -> tuple[str, Rows] | Section:
        """Ejecuta la consulta de ``spec`` con el tablespace del informe; si falla, la sección que lo explica."""
        try:
            return self.execute(spec.name, database=database, tablespace=self._tablespace)
        except QueryNotFoundError:
            return section(spec, "not_supported", self.translator.t("doc.storage.message.not_supported"))
        except QueryParameterError as error:
            return section(spec, "missing_params", self.translator.t("doc.storage.message.invalid_params", error=error))
        except DatabaseException as error:
            message: str = _flatten_exception_messages(error)
            explained: Section | None = spec.on_error(spec, message, self.translator) if spec.on_error else None
            return explained or section(
                spec, "error", self.translator.t("doc.storage.message.query_error", error=message)
            )

    def ok_section(
        self, spec: StorageQuerySpec, sql: str, rows: Rows, *, message: str | None = None, status: str = "ok"
    ) -> Section:
        """Sección con filas: cabeceras de ``spec`` (o genéricas) y tamaños con el separador decimal del idioma."""
        headers: list[str] = _headers_for(spec, rows, self.translator)
        if message is None:
            message = self.translator.t("doc.storage.message.ok" if rows else "doc.storage.message.no_data")
        return {
            "query": spec.name,
            "title": spec.title,
            "status": status,
            "message": message,
            "sql": sql,
            "headers": headers,
            "rows": _format_rows(headers, rows, self.translator),
            "numeric_columns": [index for index, header in enumerate(headers) if _is_size_header(header)],
        }

    def _localize(self, raw_section: Section) -> Section:
        """Título y cabeceras de la sección en el idioma de salida (tras detectar las columnas de tamaño)."""
        localized: Section = dict(raw_section)
        localized["title"] = localize_label(str(raw_section.get("title", "")), self.translator)
        localized["headers"] = [localize_label(str(header), self.translator) for header in raw_section["headers"]]
        return localized

    @staticmethod
    def normalize_rows(rows: object) -> Rows:
        """Filas como listas (una fila suelta o un escalar se envuelven)."""
        if rows is None:
            return []
        items: list[object] = rows if isinstance(rows, list) else [rows]
        return [list(row) if isinstance(row, (list, tuple)) else [row] for row in items]

    def _process_standard(self, spec: StorageQuerySpec, database: str) -> Section:
        outcome = self.run_query(spec, database=database)
        if isinstance(outcome, dict):
            return outcome
        sql_text, rows = outcome
        return self.ok_section(spec, sql_text, rows)


def _flatten_exception_messages(error: BaseException) -> str:
    """Concatena los mensajes de la cadena de excepciones."""
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


def _headers_for(spec: StorageQuerySpec, rows: Rows, translator: Translator) -> list[str]:
    """Cabeceras de ``spec`` recortadas a las columnas devueltas; ``Columna N`` si la consulta no tiene."""
    widest: int = max((len(row) for row in rows), default=0)
    if spec.headers:
        return list(spec.headers[:widest] if widest > 0 else spec.headers)
    return [translator.t("doc.storage.col.generic", index=index) for index in range(1, widest + 1)]


def _is_size_header(header: str) -> bool:
    return _SIZE_HEADER.search(str(header or "")) is not None


def _format_size(value: object, translator: Translator) -> object:
    """Tamaño con dos decimales y el separador decimal del idioma (sin miles); enteros y booleanos sin cambios."""
    if value is None:
        return ""
    if isinstance(value, (int, bool)):
        return value
    if isinstance(value, float):
        return translator.format_decimal(value, 2)
    normalized_numeric: str = str(value).replace(",", ".")
    if re.fullmatch(r"-?\d+(\.\d+)?", normalized_numeric):
        return translator.format_decimal(float(normalized_numeric), 2)
    return value


def _format_rows(headers: list[str], rows: Rows, translator: Translator) -> Rows:
    size_columns: set[int] = {index for index, header in enumerate(headers) if _is_size_header(header)}
    return [
        [_format_size(value, translator) if index in size_columns else value for index, value in enumerate(row)]
        for row in rows
    ]


def get_storage_inventory_report(
    *,
    db_manager: StorageInventoryManagerProtocol,
    logger: LoggerProtocol,
    print_config: dict[str, Any],
    translator: Translator | None = None,
) -> dict[str, Any]:
    """Obtiene el informe de almacenamiento sin exponer bootstrap en la fachada documental (en el idioma de
    ``translator``; español por defecto)."""
    return StorageInventoryRuntime(
        db_manager=db_manager,
        logger=logger,
        db_type=db_manager.db_type,
        database=db_manager.database,
        print_config=print_config,
        translator=translator or Translator(),
    ).get_storage_inventory_report()


@dataclass(slots=True, frozen=True)
class StorageInventoryReportService(StorageReportServicePort):
    """Servicio OO de acceso al inventario de almacenamiento (textos y números en el idioma de ``translator``)."""

    translator: Translator = field(default_factory=Translator)

    def get_storage_inventory_report(
        self,
        *,
        db_manager: DocumentationBackendPort,
        logger: LoggerProtocol,
        print_config: dict[str, Any],
    ) -> dict[str, Any]:
        return get_storage_inventory_report(
            db_manager=cast(StorageInventoryManagerProtocol, db_manager),
            logger=logger,
            print_config=print_config,
            translator=self.translator,
        )


__all__: list[str] = [
    "StorageInventoryReportService",
    "StorageInventoryRuntime",
    "get_storage_inventory_report",
]
