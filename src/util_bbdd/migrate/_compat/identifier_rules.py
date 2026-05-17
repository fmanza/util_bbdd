"""Reglas de identificadores para MariaDB.

MariaDB permite identificadores de hasta 64 caracteres.
Oracle 12.2+ permite 128; versiones anteriores 30.
Cuando un identificador Oracle supera los 64 caracteres, se trunca a 60 y se
añade un sufijo hash de 4 caracteres para garantizar unicidad.
"""

from __future__ import annotations

import hashlib

MAX_MARIADB_IDENTIFIER_LENGTH: int = 64
_HASH_SUFFIX_LENGTH: int = 4
_TRUNCATE_AT: int = MAX_MARIADB_IDENTIFIER_LENGTH - _HASH_SUFFIX_LENGTH - 1  # 59


def truncate_identifier(name: str) -> tuple[str, bool]:
    """Trunca un identificador si supera MAX_MARIADB_IDENTIFIER_LENGTH.

    Si el nombre supera el límite, lo trunca a 59 caracteres y añade
    '_XXXX' donde XXXX es el hash MD5 de 4 chars del nombre original.

    Args:
        name: Identificador original.

    Returns:
        (new_name, was_truncated): el nuevo nombre y si fue truncado.
    """
    if len(name) <= MAX_MARIADB_IDENTIFIER_LENGTH:
        return name, False

    hash_suffix = hashlib.md5(name.encode("utf-8")).hexdigest()[:_HASH_SUFFIX_LENGTH]
    new_name = f"{name[:_TRUNCATE_AT]}_{hash_suffix}"
    return new_name, True


def check_identifier(name: str) -> tuple[str, str | None]:
    """Verifica y adapta un identificador para MariaDB.

    Args:
        name: Identificador a verificar.

    Returns:
        (adapted_name, warning_message_or_None)
    """
    adapted, truncated = truncate_identifier(name)
    if truncated:
        msg = (
            f"Identificador '{name}' ({len(name)} chars) truncado a '{adapted}' "
            f"({len(adapted)} chars) para cumplir límite MariaDB de {MAX_MARIADB_IDENTIFIER_LENGTH}"
        )
        return adapted, msg
    return adapted, None


__all__: list[str] = [
    "MAX_MARIADB_IDENTIFIER_LENGTH",
    "truncate_identifier",
    "check_identifier",
]
