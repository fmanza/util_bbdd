"""Reglas de identificadores para motores de bases de datos.

MariaDB:    max 64 caracteres.
SQL Server: max 128 caracteres.
Oracle 12.2+ permite 128; versiones anteriores 30.
Cuando un identificador supera el límite del motor destino, se trunca y se
añade un sufijo hash de 4 caracteres para garantizar unicidad.
"""

from __future__ import annotations

import hashlib

MAX_MARIADB_IDENTIFIER_LENGTH: int = 64
MAX_SQLSERVER_IDENTIFIER_LENGTH: int = 128
_HASH_SUFFIX_LENGTH: int = 4


def truncate_identifier(
    name: str,
    max_length: int = MAX_MARIADB_IDENTIFIER_LENGTH,
) -> tuple[str, bool]:
    """Trunca un identificador si supera max_length.

    Si el nombre supera el límite, lo trunca y añade '_XXXX' donde XXXX
    es el hash MD5 de 4 chars del nombre original para garantizar unicidad.

    Args:
        name: Identificador original.
        max_length: Longitud máxima permitida (default: 64 para MariaDB).

    Returns:
        (new_name, was_truncated): el nuevo nombre y si fue truncado.
    """
    if len(name) <= max_length:
        return name, False

    truncate_at = max_length - _HASH_SUFFIX_LENGTH - 1
    hash_suffix = hashlib.md5(name.encode("utf-8")).hexdigest()[:_HASH_SUFFIX_LENGTH]
    new_name = f"{name[:truncate_at]}_{hash_suffix}"
    return new_name, True


def check_identifier(
    name: str,
    max_length: int = MAX_MARIADB_IDENTIFIER_LENGTH,
) -> tuple[str, str | None]:
    """Verifica y adapta un identificador para el motor destino.

    Args:
        name: Identificador a verificar.
        max_length: Longitud máxima del motor destino (default: 64 para MariaDB).

    Returns:
        (adapted_name, warning_message_or_None)
    """
    adapted, truncated = truncate_identifier(name, max_length)
    if truncated:
        msg = (
            f"Identificador '{name}' ({len(name)} chars) truncado a '{adapted}' "
            f"({len(adapted)} chars) para cumplir límite de {max_length}"
        )
        return adapted, msg
    return adapted, None


__all__: list[str] = [
    "MAX_MARIADB_IDENTIFIER_LENGTH",
    "MAX_SQLSERVER_IDENTIFIER_LENGTH",
    "truncate_identifier",
    "check_identifier",
]
