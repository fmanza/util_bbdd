"""Protocol base para emisores DDL."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..ir.models import CanonicalTable


@runtime_checkable
class DDLEmitter(Protocol):
    """Contrato para emisores de DDL hacia un motor destino."""

    def emit(self, tables: list[CanonicalTable]) -> str:
        """Genera el script DDL completo como string.

        Args:
            tables: Tablas transformadas (IR destino).

        Returns:
            Script DDL completo con sentencias separadas por ';\n\n'.
        """
        ...

    def emit_statements(self, tables: list[CanonicalTable]) -> list[str]:
        """Genera lista de sentencias DDL individuales sin ';'.

        Args:
            tables: Tablas transformadas (IR destino).

        Returns:
            Lista de sentencias DDL listas para ejecutar.
        """
        ...


__all__: list[str] = ["DDLEmitter"]
