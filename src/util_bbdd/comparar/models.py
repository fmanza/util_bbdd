"""Modelos de datos para comparación de esquemas de base de datos."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class ColumnDiff:
    """Diferencia detectada en un atributo de una columna."""

    column_name: str
    attribute: Literal["type", "nullable", "primary_key", "default", "existence"]
    source_value: str
    target_value: str


@dataclass(frozen=True)
class IndexDiff:
    """Diferencia detectada en un índice."""

    index_name: str
    table_name: str
    status: Literal["added", "removed", "modified"]
    source_columns: str = ""
    target_columns: str = ""
    source_unique: bool = False
    target_unique: bool = False


@dataclass(frozen=True)
class ForeignKeyDiff:
    """Diferencia detectada en una foreign key."""

    fk_name: str
    table_name: str
    status: Literal["added", "removed", "modified"]
    source_columns: str = ""
    target_columns: str = ""
    source_referred_table: str = ""
    target_referred_table: str = ""
    source_referred_columns: str = ""
    target_referred_columns: str = ""


@dataclass(frozen=True)
class ViewDiff:
    """Diferencia detectada en una vista."""

    view_name: str
    status: Literal["added", "removed", "modified"]
    source_definition: str = ""
    target_definition: str = ""


@dataclass(frozen=True)
class RoutineDiff:
    """Diferencia detectada en una rutina (procedure/function)."""

    routine_name: str
    routine_type: Literal["PROCEDURE", "FUNCTION"]
    status: Literal["added", "removed", "modified"]
    source_definition: str = ""
    target_definition: str = ""


@dataclass(frozen=True)
class CommentDiff:
    """Diferencia detectada en un comentario de tabla o columna."""

    object_name: str
    column_name: str | None  # None => comentario de tabla
    source_comment: str
    target_comment: str


@dataclass(frozen=True)
class TableDiff:
    """Diferencias detectadas en una tabla."""

    table_name: str
    status: Literal["added", "removed", "modified"]
    column_diffs: tuple[ColumnDiff, ...] = ()
    index_diffs: tuple[IndexDiff, ...] = ()
    fk_diffs: tuple[ForeignKeyDiff, ...] = ()
    comment_diffs: tuple[CommentDiff, ...] = ()


@dataclass(frozen=True)
class SchemaDiff:
    """Resultado completo de la comparación entre dos esquemas."""

    source_label: str
    target_label: str
    table_diffs: tuple[TableDiff, ...] = ()
    view_diffs: tuple[ViewDiff, ...] = ()
    routine_diffs: tuple[RoutineDiff, ...] = ()
    summary: str = field(default="", repr=False)
    source_short_label: str = field(default="", repr=False)
    target_short_label: str = field(default="", repr=False)

    @property
    def has_differences(self) -> bool:
        """Indica si se encontraron diferencias entre los esquemas."""
        return bool(self.table_diffs or self.view_diffs or self.routine_diffs)

    @property
    def total_differences(self) -> int:
        """Número total de diferencias de primer nivel."""
        return len(self.table_diffs) + len(self.view_diffs) + len(self.routine_diffs)
