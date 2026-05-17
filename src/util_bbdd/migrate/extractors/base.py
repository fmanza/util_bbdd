"""Protocol base para extractores de esquemas."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..ir.models import CanonicalTable


@runtime_checkable
class SchemaExtractor(Protocol):
    """Contrato para extractores de metadatos de esquemas."""

    def extract(self, schema: str) -> list[CanonicalTable]:
        """Extrae todas las tablas del esquema y las retorna como IR canónico.

        Args:
            schema: Nombre del schema/owner en el motor origen.

        Returns:
            Lista de CanonicalTable con columnas, índices y FKs poblados.
        """
        ...


__all__: list[str] = ["SchemaExtractor"]
