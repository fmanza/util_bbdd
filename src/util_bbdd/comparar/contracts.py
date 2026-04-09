"""Contratos (Protocols) para el módulo de comparación de esquemas."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from sqlalchemy.engine import Inspector

from .models import SchemaDiff


@runtime_checkable
class SchemaComparatorProtocol(Protocol):
    """Contrato para comparadores de esquemas de base de datos."""

    def compare(
        self,
        source: Inspector,
        target: Inspector,
        *,
        source_schema: str | None = None,
        target_schema: str | None = None,
        include_tables: bool = True,
        include_views: bool = True,
        include_indices: bool = True,
        include_foreign_keys: bool = True,
        include_comments: bool = True,
        include_routines: bool = False,
    ) -> SchemaDiff:
        """Compara dos esquemas y devuelve las diferencias encontradas.

        Args:
            source: Inspector del esquema origen.
            target: Inspector del esquema destino.
            source_schema: Nombre del schema origen (requerido en Oracle, opcional en MariaDB).
            target_schema: Nombre del schema destino.
            include_tables: Comparar tablas y columnas.
            include_views: Comparar vistas.
            include_indices: Comparar índices.
            include_foreign_keys: Comparar foreign keys.
            include_comments: Comparar comentarios de tablas/columnas.
            include_routines: Comparar procedures/functions (requiere engine con acceso al catálogo).

        Returns:
            SchemaDiff con todas las diferencias encontradas.
        """
        ...


@runtime_checkable
class DiffReporterProtocol(Protocol):
    """Contrato para reporters que generan salida a partir de un SchemaDiff."""

    def render(self, diff: SchemaDiff, output: Path) -> Path:
        """Genera un reporte de diferencias en el formato implementado.

        Args:
            diff: Resultado de la comparación.
            output: Ruta de salida del reporte.

        Returns:
            Ruta del archivo generado.
        """
        ...
