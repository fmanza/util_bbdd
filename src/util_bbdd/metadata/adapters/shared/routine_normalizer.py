"""Normalización genérica de tipos y elementos de routines."""

from __future__ import annotations

__all__: list[str] = [
    "normalize_routine_type",
]


# Mapeos genéricos de tipos de routines
_ROUTINE_TYPE_MAPPING: dict[str, str] = {
    "procedure": "PROCEDURE",
    "function": "FUNCTION",
    "trigger": "TRIGGER",
    "event": "EVENT",
}


def normalize_routine_type(raw_type: str) -> str:
    """Normaliza el tipo de una routine.

    Args:
        raw_type: Tipo nativo (p.ej. 'PROCEDURE', 'procedure', 'FUNCTION').

    Returns:
        str: Tipo normalizado en mayúsculas (p.ej. 'PROCEDURE', 'FUNCTION').
             Si no hay mapeo, devuelve el tipo en mayúsculas como fallback.

    Ejemplo:
        >>> normalize_routine_type('procedure')
        'PROCEDURE'
        >>> normalize_routine_type('FUNCTION')
        'FUNCTION'
    """
    normalized = raw_type.upper()
    return _ROUTINE_TYPE_MAPPING.get(normalized, normalized)
