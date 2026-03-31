"""Helpers internos de formateo para rutinas MariaDB."""

from __future__ import annotations


def format_mariadb_definer(definer: str) -> str:
    """Renderiza DEFINER con quoting MariaDB."""
    normalized: str = str(definer or "").strip()
    if not normalized:
        return ""
    if normalized.startswith("`") and "`@" in normalized:
        return normalized
    if "@" in normalized:
        user, host = normalized.split("@", 1)
        safe_user: str = user.replace("`", "``")
        safe_host: str = host.replace("`", "``")
        return f"`{safe_user}`@`{safe_host}`"
    safe_definer: str = normalized.replace("`", "``")
    return f"`{safe_definer}`"


def format_mariadb_routine_parameter(
    *, routine_type: str, mode: str, name: str, data_type: str, default_value: str
) -> str:
    """Renderiza un parametro de rutina MariaDB."""
    pieces: list[str] = []
    normalized_routine_type: str = str(routine_type or "").strip().upper()
    normalized_mode: str = str(mode or "").strip().upper()
    if normalized_mode and not (normalized_routine_type == "FUNCTION" and normalized_mode == "IN"):
        pieces.append(normalized_mode)
    if name:
        pieces.append(name)
    if data_type:
        pieces.append(data_type)
    if default_value:
        pieces.append(f"DEFAULT {default_value}")
    return " ".join(pieces)


def format_mariadb_return_type(*, data_type: str, charset: str, collation: str) -> str:
    """Renderiza RETURNS de FUNCTION MariaDB."""
    rendered: str = str(data_type or "").strip()
    if charset:
        rendered += f" CHARSET {charset}"
    if collation:
        rendered += f" COLLATE {collation}"
    return rendered


__all__: list[str] = [
    "format_mariadb_definer",
    "format_mariadb_return_type",
    "format_mariadb_routine_parameter",
]
