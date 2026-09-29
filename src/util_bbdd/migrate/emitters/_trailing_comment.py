"""Comentario al final de una línea de definición del ``CREATE TABLE`` (H3).

Los emitters añaden a la línea de columna un comentario ``-- ...`` (aviso de migración, comentario de columna). Si
después se unen las líneas con ``",\\n"``, la coma separadora queda dentro del comentario y el DDL no es válido. Cada
emitter marca con ``TRAILING_COMMENT_MARK`` dónde empieza su comentario y ``join_definitions`` coloca la coma antes.
El marcador (NUL) no puede aparecer en SQL, así que no se confunde con un ``--`` dentro de un literal.
"""

from __future__ import annotations

TRAILING_COMMENT_MARK: str = "\x00"


def one_line(text: str) -> str:
    """Texto para escribir tras ``--``: sin saltos de línea (B1, hotfix 2026-09-30).

    Un comentario ``--`` termina en ``\\n`` o ``\\r``: con un salto dentro del texto (comentario o nombre del catálogo
    origen), lo que seguía quedaba fuera del comentario como SQL.
    """
    return text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")


def with_trailing_comment(definition: str, comment: str) -> str:
    """Devuelve la definición con su comentario final marcado (``comment`` incluye el ``--``)."""
    return f"{definition}{TRAILING_COMMENT_MARK} {comment}"


def join_definitions(lines: list[str]) -> str:
    """Une las definiciones con coma + salto de línea, dejando cada coma antes del comentario final."""
    rendered: list[str] = []
    last: int = len(lines) - 1
    for index, line in enumerate(lines):
        separator: str = "," if index < last else ""
        definition, mark, comment = line.partition(TRAILING_COMMENT_MARK)
        rendered.append(f"{definition}{separator}{comment}" if mark else f"{line}{separator}")
    return "\n".join(rendered)


__all__: list[str] = ["TRAILING_COMMENT_MARK", "join_definitions", "one_line", "with_trailing_comment"]
