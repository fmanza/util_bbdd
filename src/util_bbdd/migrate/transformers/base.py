"""Protocol base para transformadores de esquemas."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..ir.models import CanonicalTable, CanonicalView


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

    def transform_views(self, views: list[CanonicalView]) -> list[CanonicalView]:
        """Transforma una lista de vistas IR al esquema destino.

        Aplica reescritura best-effort del SQL Oracle: sustituye SYSDATE,
        NVL, FROM DUAL, hints y prefijos de schema. Constructs complejos
        (ROWNUM, CONNECT BY, outer-join (+), DECODE) generan MigrationWarning.

        Args:
            views: Vistas extraídas del motor origen.

        Returns:
            Vistas con SQL reescrito y warnings poblados.
        """
        ...


__all__: list[str] = ["SchemaTransformer"]
