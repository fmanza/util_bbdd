"""Protocol base para extractores de esquemas."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..ir.models import CanonicalRoutine, CanonicalTable, CanonicalView


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

    def extract_routines(self, schema: str) -> list[CanonicalRoutine]:
        """Extrae todas las rutinas del esquema y las retorna como IR canónico.

        Args:
            schema: Nombre del schema/owner en el motor origen.

        Returns:
            Lista de CanonicalRoutine con body y warnings poblados.
        """
        ...

    def extract_views(self, schema: str) -> list[CanonicalView]:
        """Extrae todas las vistas del esquema y las retorna como IR canónico.

        MIG-04 (AUDIT_CODE 2026-09-22): las 4 implementaciones concretas
        (Oracle/MariaDB/PostgreSQL/SQL Server) exponen este método y
        ``migrate/planner.py`` lo invoca incondicionalmente; forma parte del
        contrato real de ``SchemaExtractor`` aunque antes no estuviera
        declarado en el Protocol.

        Args:
            schema: Nombre del schema/owner en el motor origen.

        Returns:
            Lista de CanonicalView con definición y columnas pobladas.
        """
        ...


__all__: list[str] = ["SchemaExtractor"]
