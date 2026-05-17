"""Protocol base para transformadores de esquemas."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..ir.models import CanonicalTable


@runtime_checkable
class SchemaTransformer(Protocol):
    """Contrato para transformadores IR origen → IR destino."""

    def transform(self, tables: list[CanonicalTable]) -> list[CanonicalTable]:
        """Transforma una lista de tablas IR al esquema destino.

        Args:
            tables: Tablas extraídas del motor origen.

        Returns:
            Tablas transformadas con tipos destino y warnings poblados.
        """
        ...


__all__: list[str] = ["SchemaTransformer"]
