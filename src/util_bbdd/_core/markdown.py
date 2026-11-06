"""Texto seguro para Markdown común a ``comparar`` (informe de diferencias) y ``doc`` (documentación Markdown).

Los nombres, tipos, valores por defecto y comentarios del catálogo son datos no confiables: dentro de un *code span*,
un backtick lo cerraría y dejaría pasar HTML, y en una tabla GFM un ``|`` parte la fila aunque esté dentro del código.
"""

from __future__ import annotations

import re

_BACKTICK_RUN: re.Pattern[str] = re.compile(r"`+")
_LINE_BREAKS: re.Pattern[str] = re.compile(r"[\r\n\u2028\u2029]+")


def code_span(text: str, *, in_table: bool = False) -> str:
    """*Code span* con más backticks que cualquier racha del texto, en una sola línea.

    Si el texto empieza o acaba en backtick se separa con un espacio (CommonMark §6.1). Dentro de una tabla, ``|`` se
    escapa como ``\\|`` (GFM lo exige también dentro del código). Los saltos de línea pasan a espacio.

    Examples:
        >>> code_span("a`b"), code_span("`x`"), code_span("a|b", in_table=True)
        ('``a`b``', '`` `x` ``', '`a\\\\|b`')
    """
    single_line = _LINE_BREAKS.sub(" ", text)
    longest = max((len(run) for run in _BACKTICK_RUN.findall(single_line)), default=0)
    fence = "`" * (longest + 1)
    padded = f" {single_line} " if single_line.startswith("`") or single_line.endswith("`") else single_line
    span = f"{fence}{padded}{fence}"
    return span.replace("|", "\\|") if in_table else span


def escape_html(text: str) -> str:
    """``&``, ``<`` y ``>`` como entidades (primero ``&``): el HTML en línea del texto no se interpreta."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


__all__: list[str] = ["code_span", "escape_html"]
