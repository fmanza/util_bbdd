"""Modelos de datos para comparación de esquemas de base de datos."""

from __future__ import annotations

import types
import typing

from dataclasses import MISSING, dataclass, field, fields
from typing import Any, ClassVar, Literal, Self

from util_bbdd._core.exceptions import SchemaDiffValidationError


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
    status: Literal["modified"] = "modified"  # siempre modificado; campo por consistencia con otros diffs


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

    #: Identificador y versión del formato de :meth:`to_dict`. La versión sube solo si un lector de la anterior dejaría
    #: de entenderlo (campo renombrado o quitado, valor con otro significado); añadir un campo opcional no la sube.
    FORMAT: ClassVar[str] = "util_bbdd.schema_diff"
    FORMAT_VERSION: ClassVar[int] = 1

    def to_dict(self) -> dict[str, Any]:
        """Serializa el diff a tipos JSON (``dict``, ``list``, ``str``, ``bool``, ``None``).

        El resultado lleva ``format`` y ``format_version`` y se reconstruye exacto con :meth:`from_dict`
        (``SchemaDiff.from_dict(diff.to_dict()) == diff``). Las tuplas se escriben como listas.

        Example:
            >>> import json
            >>> diff = SchemaDiff(source_label="pg [public]", target_label="ora [APP]")
            >>> SchemaDiff.from_dict(json.loads(json.dumps(diff.to_dict()))) == diff
            True
        """
        return {"format": self.FORMAT, "format_version": self.FORMAT_VERSION, **_dump(self)}

    @classmethod
    def from_dict(cls, data: typing.Mapping[str, Any]) -> Self:
        """Reconstruye un diff escrito por :meth:`to_dict`.

        Se ignoran las claves que no son campos (las que añada una versión posterior compatible); los campos con valor
        por defecto pueden faltar.

        Raises:
            SchemaDiffValidationError: ``format`` o ``format_version`` desconocidos, falta un campo obligatorio o un
                valor no tiene el tipo esperado (con la ruta del valor: ``table_diffs[2].status``).
        """
        if not isinstance(data, typing.Mapping):
            raise SchemaDiffValidationError(f"SchemaDiff.from_dict espera un dict, no {type(data).__name__}")
        if data.get("format") != cls.FORMAT:
            raise SchemaDiffValidationError(
                f"No es un SchemaDiff serializado: format={data.get('format')!r} (se espera {cls.FORMAT!r})"
            )
        version = data.get("format_version")
        if version != cls.FORMAT_VERSION:
            raise SchemaDiffValidationError(
                f"format_version {version!r} de SchemaDiff no soportada: esta versión de util_bbdd lee la "
                f"{cls.FORMAT_VERSION}"
            )
        return _load(cls, data, "")

    @property
    def has_differences(self) -> bool:
        """Indica si se encontraron diferencias entre los esquemas."""
        return bool(self.table_diffs or self.view_diffs or self.routine_diffs)

    @property
    def total_differences(self) -> int:
        """Número total de diferencias de primer nivel."""
        return len(self.table_diffs) + len(self.view_diffs) + len(self.routine_diffs)

    @property
    def total_leaf_differences(self) -> int:
        """Número total de diferencias hoja (columnas, índices, FKs, comentarios, vistas, routines)."""
        table_leaves = sum(
            len(t.column_diffs) + len(t.index_diffs) + len(t.fk_diffs) + len(t.comment_diffs) for t in self.table_diffs
        )
        return table_leaves + len(self.view_diffs) + len(self.routine_diffs)


# ----------------------------------------------------------------------
# Serialización (SchemaDiff.to_dict / from_dict)
# ----------------------------------------------------------------------


def _dump(obj: object) -> dict[str, Any]:
    """Campos de un diff como tipos JSON; los diffs anidados, recursivamente."""
    result: dict[str, Any] = {}
    for f in fields(obj):  # type: ignore[arg-type]
        value = getattr(obj, f.name)
        result[f.name] = [_dump(item) for item in value] if isinstance(value, tuple) else value
    return result


def _load[T](cls: type[T], data: typing.Mapping[str, Any], path: str) -> T:
    """Construye ``cls`` desde ``data`` validando presencia y tipo de cada campo."""
    if not isinstance(data, typing.Mapping):
        raise SchemaDiffValidationError(f"{path or 'SchemaDiff'}: se espera un objeto, no {type(data).__name__}")
    hints = typing.get_type_hints(cls)
    kwargs: dict[str, Any] = {}
    for f in fields(cls):  # type: ignore[arg-type]
        where = f"{path}.{f.name}" if path else f.name
        if f.name not in data:
            if f.default is MISSING and f.default_factory is MISSING:
                raise SchemaDiffValidationError(f"{where}: campo obligatorio ausente")
            continue
        kwargs[f.name] = _load_value(hints[f.name], data[f.name], where)
    return cls(**kwargs)


def _load_value(hint: Any, value: Any, where: str) -> Any:
    """Valida ``value`` contra la anotación del campo y convierte listas de diffs en tuplas."""
    origin = typing.get_origin(hint)
    args = typing.get_args(hint)
    if origin is tuple:
        if not isinstance(value, list | tuple):
            raise SchemaDiffValidationError(f"{where}: se espera una lista, no {type(value).__name__}")
        return tuple(_load(args[0], item, f"{where}[{i}]") for i, item in enumerate(value))
    if origin is Literal:
        if value not in args:
            raise SchemaDiffValidationError(f"{where}: {value!r} no es uno de {list(args)}")
        return value
    allowed = args if origin is types.UnionType else (hint,)
    if not any(value is None if t is type(None) else type(value) is t for t in allowed):
        raise SchemaDiffValidationError(f"{where}: tipo {type(value).__name__} no válido")
    return value
