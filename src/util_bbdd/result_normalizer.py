"""Normalización homogénea de resultados de cursores sync/async."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .result_types import Row, RowOrNone, Rows


class ResultNormalizer:
    """Convierte resultados crudos de drivers a contrato estable Row/Rows."""

    @staticmethod
    def normalize_one(result: Any) -> RowOrNone:
        """Normaliza resultado de fetchone()."""
        if result is None:
            return None
        return ResultNormalizer._as_row(result)

    @staticmethod
    def normalize_many(result: Any) -> Rows:
        """Normaliza resultado de fetchall() a lista materializada de filas."""
        if result is None:
            return []

        if isinstance(result, list):
            return ResultNormalizer._normalize_from_sequence(result)

        if isinstance(result, tuple):
            return ResultNormalizer._normalize_from_sequence(list(result))

        if isinstance(result, Iterable) and not isinstance(result, (str, bytes, bytearray, memoryview, dict)):
            return ResultNormalizer._normalize_from_sequence(list(result))

        return [ResultNormalizer._as_row(result)]

    @staticmethod
    def _normalize_from_sequence(values: list[Any]) -> Rows:
        if not values:
            return []

        first = values[0]
        if ResultNormalizer._is_row_sequence(first):
            return [ResultNormalizer._as_row(value) for value in values]

        # Caso atípico: colección plana (p. ej. [1, 2, 3]) tratada como fila única.
        return [ResultNormalizer._as_row(values)]

    @staticmethod
    def _is_row_sequence(value: Any) -> bool:
        return isinstance(value, (list, tuple))

    @staticmethod
    def _as_row(value: Any) -> Row:
        if isinstance(value, tuple):
            return value
        if isinstance(value, list):
            return tuple(value)
        return (value,)
