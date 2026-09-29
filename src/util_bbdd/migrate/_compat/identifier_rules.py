"""Reglas de identificadores para motores de bases de datos.

MariaDB:    max 64 caracteres.
SQL Server: max 128 caracteres.
PostgreSQL: max 63 bytes (ASCII equivalente a 63 chars).
Oracle 12.2+ permite 128; versiones anteriores 30.
Cuando un identificador supera el límite del motor destino, se trunca y se
añade un sufijo hash de 4 caracteres para garantizar unicidad.

CMP-02 (AUDIT_CODE 2026-09-22): los emisores de este módulo entrecomillan
siempre los identificadores (``_dq``/``_qq``), preservando el case exacto del
origen, por lo que el propio DDL generado nunca colisiona internamente. El
riesgo real es en destino: motores con case-folding para identificadores sin
comillas (Oracle pliega a MAYÚSCULAS, PostgreSQL a minúsculas) pueden colapsar
dos identificadores del origen que solo difieren en case en un único nombre
si alguna herramienta o script posterior los referencia sin comillas —
``find_case_insensitive_collisions`` detecta esos pares para poder advertir
antes de emitir el DDL, sin cambiar el case de ningún identificador emitido.
"""

from __future__ import annotations

import hashlib

from collections.abc import Iterable


class ByteLimit(int):
    """Límite de identificador medido en bytes UTF-8, no en caracteres (A6, 2026-09-29).

    PostgreSQL (``NAMEDATALEN - 1`` = 63) y Oracle cuentan bytes: un nombre con tildes o ``ñ`` bajo el límite de
    caracteres puede superarlo en bytes, y el motor lo recortaría en silencio (perdiendo el sufijo hash que garantiza
    la unicidad). Se usa como un ``int`` en todas partes; ``truncate_identifier`` lo reconoce por su tipo.
    """


MAX_MARIADB_IDENTIFIER_LENGTH: int = 64
MAX_SQLSERVER_IDENTIFIER_LENGTH: int = 128
MAX_POSTGRESQL_IDENTIFIER_LENGTH: int = ByteLimit(63)
# Oracle 12.1 y anteriores: 30 bytes. 12.2+ permite 128; se usa 30 como mínimo seguro.
MAX_ORACLE_IDENTIFIER_LENGTH: int = ByteLimit(30)
_HASH_SUFFIX_LENGTH: int = 4


def _size(name: str, max_length: int) -> int:
    return len(name.encode("utf-8")) if isinstance(max_length, ByteLimit) else len(name)


def truncate_identifier(
    name: str,
    max_length: int = MAX_MARIADB_IDENTIFIER_LENGTH,
) -> tuple[str, bool]:
    """Trunca un identificador si supera max_length.

    Si el nombre supera el límite, lo trunca y añade '_XXXX' donde XXXX
    es el hash MD5 de 4 chars del nombre original para garantizar unicidad.

    Args:
        name: Identificador original.
        max_length: Longitud máxima permitida (default: 64 para MariaDB). Si es un :class:`ByteLimit` (PostgreSQL,
            Oracle) se mide en bytes UTF-8 y el corte nunca parte un carácter.

    Returns:
        (new_name, was_truncated): el nuevo nombre y si fue truncado.
    """
    if _size(name, max_length) <= max_length:
        return name, False

    truncate_at = max_length - _HASH_SUFFIX_LENGTH - 1
    hash_suffix = hashlib.md5(name.encode("utf-8")).hexdigest()[:_HASH_SUFFIX_LENGTH]
    if isinstance(max_length, ByteLimit):
        prefix = name.encode("utf-8")[:truncate_at].decode("utf-8", errors="ignore")
    else:
        prefix = name[:truncate_at]
    new_name = f"{prefix}_{hash_suffix}"
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
        unit = "bytes" if isinstance(max_length, ByteLimit) else "chars"
        msg = (
            f"Identificador '{name}' ({_size(name, max_length)} {unit}) truncado a '{adapted}' "
            f"({_size(adapted, max_length)} {unit}) para cumplir límite de {max_length}"
        )
        return adapted, msg
    return adapted, None


def find_case_insensitive_collisions(names: Iterable[str]) -> list[tuple[str, str]]:
    """Detecta pares de identificadores que solo difieren en mayúsculas/minúsculas.

    CMP-02 (AUDIT_CODE 2026-09-22): agnóstico al motor destino — cualquier
    engine con case-folding (Oracle a MAYÚSCULAS, PostgreSQL a minúsculas
    para identificadores sin comillas) colapsaría estos pares en un único
    nombre si se referencian sin comillas, aunque el DDL migrado los
    entrecomille siempre y por tanto no colisione por sí solo.

    Args:
        names: Identificadores a comparar (normalmente ya truncados/adaptados
            para el motor destino, en el orden en que se emiten).

    Returns:
        Pares ``(primero_visto, siguiente)`` que colisionarían bajo
        case-folding, en orden de aparición. Un nombre repetido con el
        mismo case exacto no se reporta (es un duplicado literal, no una
        colisión de folding).
    """
    seen_by_fold: dict[str, str] = {}
    collisions: list[tuple[str, str]] = []
    for name in names:
        folded = name.upper()
        previous = seen_by_fold.get(folded)
        if previous is None:
            seen_by_fold[folded] = name
        elif previous != name:
            collisions.append((previous, name))
    return collisions


__all__: list[str] = [
    "ByteLimit",
    "MAX_MARIADB_IDENTIFIER_LENGTH",
    "MAX_SQLSERVER_IDENTIFIER_LENGTH",
    "MAX_POSTGRESQL_IDENTIFIER_LENGTH",
    "MAX_ORACLE_IDENTIFIER_LENGTH",
    "truncate_identifier",
    "check_identifier",
    "find_case_insensitive_collisions",
]
