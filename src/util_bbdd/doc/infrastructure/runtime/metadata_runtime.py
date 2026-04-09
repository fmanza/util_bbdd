"""Helpers internos para metadata opcional usada por generadores documentales."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ...._foundation.exceptions import DatabaseError
from ...application.ports import (
    LoggerProtocol,
    MetadataReaderPort,
    MetadataRuntimeFactoryPort,
    MetadataRuntimePort,
)


class DocumentationMetadataRuntime(MetadataRuntimePort):
    """Servicio OO para recuperación de metadata documental opcional."""

    def __init__(self, *, logger: LoggerProtocol) -> None:
        self._logger: LoggerProtocol = logger

    def _call_optional_metadata(
        self,
        *,
        operation: Callable[[], Any],
        success_message: str,
        error_message: str,
        success_level: str = "info",
        error_level: str = "error",
    ) -> Any | None:
        """Ejecuta una consulta de metadatos opcional con logging homogéneo."""
        try:
            result: Any = operation()
            getattr(self._logger, success_level)(success_message.format(result=result))
            return result
        except DatabaseError as error:
            getattr(self._logger, error_level)(error_message.format(error=error))
            return None

    def get_database_version_metadata(
        self,
        *,
        db_manager: MetadataReaderPort,
    ) -> str | None:
        """Obtiene la versión de BD usada por los generadores documentales."""
        result = self._call_optional_metadata(
            operation=db_manager.get_database_version,
            success_message="📋 Versión de BD obtenida: {result}",
            error_message="❌ Error al obtener versión de BD: {error}",
        )
        return None if result is None else str(result)

    def get_database_charset_collation_metadata(
        self,
        *,
        db_manager: MetadataReaderPort,
    ) -> dict[str, Any] | None:
        """Obtiene charset y collation de la base de datos para los generadores."""
        result = self._call_optional_metadata(
            operation=db_manager.get_database_charset_collation,
            success_message="📋 Charset/Collation de BD obtenido: {result}",
            error_message="❌ Error al obtener charset/collation de BD: {error}",
        )
        return result if isinstance(result, dict) else None

    def get_columns_charset_collation_metadata(
        self,
        *,
        db_manager: MetadataReaderPort,
        table_name: str,
    ) -> list[tuple[str, str | None, str | None]] | None:
        """Obtiene charset y collation de columnas para una tabla concreta."""
        result = self._call_optional_metadata(
            operation=lambda: db_manager.get_columns_charset_collation(table_name),
            success_message=f"📋 Charset/Collation de columnas de {table_name} obtenido",
            error_message=f"⚠️  Error al obtener charset/collation de columnas de {table_name}: {{error}}",
            success_level="debug",
            error_level="warning",
        )
        return result if isinstance(result, list) else None


@dataclass(slots=True, frozen=True)
class DocumentationMetadataRuntimeFactory(MetadataRuntimeFactoryPort):
    """Fábrica concreta del runtime de metadata."""

    def create(self, *, logger: LoggerProtocol) -> MetadataRuntimePort:
        return DocumentationMetadataRuntime(logger=logger)


__all__: list[str] = [
    "DocumentationMetadataRuntimeFactory",
    "DocumentationMetadataRuntime",
]
