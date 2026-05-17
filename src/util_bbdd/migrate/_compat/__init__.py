"""Tablas de compatibilidad Oracle → MariaDB."""

from .identifier_rules import check_identifier, truncate_identifier
from .type_map import TypeMapping, resolve_number_type, resolve_oracle_type

__all__: list[str] = [
    "TypeMapping",
    "resolve_oracle_type",
    "resolve_number_type",
    "truncate_identifier",
    "check_identifier",
]
