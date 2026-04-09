"""Funciones puras y compartidas para normalización y procesamiento de metadatos.

Responsabilidad: encapsular transformaciones agnósticas del motor que se repiten
entre adaptadores. Sin estado, sin I/O, sin logging.

Ejemplo:
    - Mapear tipos SQL nativos a tipos genéricos ('VARCHAR' → 'string').
    - Extraer constraints de DDL.
    - Normalizar nombres de tipos de routines.

Nota: las implementaciones se movieron a `metadata/adapters/shared/` para mejor
organización. Este módulo reexporta las funciones públicas por compatibilidad.
"""

from __future__ import annotations

from .shared import (
    build_generic_columns_hint,
    extract_constraint_from_ddl,
    normalize_column_type,
    normalize_routine_type,
)

__all__: list[str] = [
    "normalize_column_type",
    "normalize_routine_type",
    "extract_constraint_from_ddl",
    "build_generic_columns_hint",
]
