"""Validación y constantes de charset/collation para MariaDB."""

from __future__ import annotations

DEFAULT_CHARSET: str = "utf8mb4"
DEFAULT_COLLATION: str = "utf8mb4_unicode_ci"

VALID_CHARSETS: frozenset[str] = frozenset(
    {
        "utf8mb4",
        "utf8",
        "latin1",
        "latin2",
        "ascii",
        "cp1250",
        "cp1251",
        "cp1252",
        "ucs2",
        "utf16",
        "utf32",
        "binary",
    }
)

VALID_COLLATIONS: frozenset[str] = frozenset(
    {
        # utf8mb4 — general
        "utf8mb4_unicode_ci",
        "utf8mb4_unicode_520_ci",
        "utf8mb4_general_ci",
        "utf8mb4_bin",
        "utf8mb4_0900_ai_ci",
        # utf8mb4 — español
        # _spanish2_ci: español moderno (ch y ll NO son letras independientes desde 1994)
        # _spanish_ci:  español tradicional (ch y ll SÍ son letras independientes, pre-1994)
        "utf8mb4_spanish2_ci",
        "utf8mb4_spanish_ci",
        # utf8 — general
        "utf8_general_ci",
        "utf8_unicode_ci",
        "utf8_bin",
        # utf8 — español
        "utf8_spanish2_ci",
        "utf8_spanish_ci",
        # latin1
        "latin1_swedish_ci",
        "latin1_general_ci",
        "latin1_bin",
        "latin1_spanish_ci",
        # otros
        "ascii_general_ci",
        "ascii_bin",
        "binary",
    }
)

# Mapa de compatibilidad charset → collations válidas.
# Solo incluye charsets con collations definidas en VALID_COLLATIONS.
# Para charsets sin entrada (latin2, cp125x, ucs2, utf16, utf32) no se valida la combinación.
CHARSET_COLLATION_MAP: dict[str, frozenset[str]] = {
    "utf8mb4": frozenset(
        {
            "utf8mb4_unicode_ci",
            "utf8mb4_unicode_520_ci",
            "utf8mb4_general_ci",
            "utf8mb4_bin",
            "utf8mb4_0900_ai_ci",
            "utf8mb4_spanish2_ci",
            "utf8mb4_spanish_ci",
        }
    ),
    "utf8": frozenset(
        {
            "utf8_general_ci",
            "utf8_unicode_ci",
            "utf8_bin",
            "utf8_spanish2_ci",
            "utf8_spanish_ci",
        }
    ),
    "latin1": frozenset(
        {
            "latin1_swedish_ci",
            "latin1_general_ci",
            "latin1_bin",
            "latin1_spanish_ci",
        }
    ),
    "ascii": frozenset(
        {
            "ascii_general_ci",
            "ascii_bin",
        }
    ),
    "binary": frozenset({"binary"}),
}


def validate_charset(charset: str) -> str:
    """Valida y normaliza un charset MariaDB.

    Args:
        charset: Nombre del charset (ej. "utf8mb4").

    Returns:
        Charset normalizado en minúsculas.

    Raises:
        ValueError: Si el charset no está en la lista soportada.
    """
    normalized = charset.strip().lower()
    if normalized not in VALID_CHARSETS:
        valid = ", ".join(sorted(VALID_CHARSETS))
        raise ValueError(f"Charset '{charset}' no soportado. Opciones: {valid}")
    return normalized


def validate_collation(collation: str) -> str:
    """Valida y normaliza una collation MariaDB.

    Args:
        collation: Nombre de la collation (ej. "utf8mb4_unicode_ci").

    Returns:
        Collation normalizada en minúsculas.

    Raises:
        ValueError: Si la collation no está en la lista soportada.
    """
    normalized = collation.strip().lower()
    if normalized not in VALID_COLLATIONS:
        valid = ", ".join(sorted(VALID_COLLATIONS))
        raise ValueError(f"Collation '{collation}' no soportada. Opciones: {valid}")
    return normalized


def validate_charset_collation_pair(charset: str, collation: str) -> None:
    """Valida que charset y collation sean compatibles en MariaDB.

    Utiliza ``CHARSET_COLLATION_MAP`` para comprobar compatibilidad. Si el
    charset no tiene entrada en el mapa (charsets exóticos sin collations
    definidas) se verifica que la collation tenga el charset como prefijo,
    siguiendo la convención de nomenclatura de MariaDB.

    Args:
        charset: Charset ya normalizado (resultado de ``validate_charset``).
        collation: Collation ya normalizada (resultado de ``validate_collation``).

    Raises:
        ValueError: Si la collation no es compatible con el charset indicado.
    """
    valid_for_charset = CHARSET_COLLATION_MAP.get(charset)
    if valid_for_charset is not None:
        if collation not in valid_for_charset:
            valid = ", ".join(sorted(valid_for_charset))
            raise ValueError(
                f"Collation '{collation}' no es compatible con charset '{charset}'. Opciones válidas: {valid}"
            )
        return
    # Charsets sin mapa explícito: la collation debe tener el charset como prefijo
    # (ej. latin2 + latin2_general_ci es válido; latin2 + utf8mb4_unicode_ci no lo es)
    if not collation.startswith(charset + "_") and collation != charset:
        raise ValueError(
            f"Collation '{collation}' no es compatible con charset '{charset}'. "
            f"Las collations de '{charset}' deben empezar por '{charset}_'."
        )


__all__: list[str] = [
    "DEFAULT_CHARSET",
    "DEFAULT_COLLATION",
    "VALID_CHARSETS",
    "VALID_COLLATIONS",
    "CHARSET_COLLATION_MAP",
    "validate_charset",
    "validate_collation",
    "validate_charset_collation_pair",
]
