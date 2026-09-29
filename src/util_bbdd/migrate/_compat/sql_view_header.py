"""Separa la cabecera ``CREATE VIEW ... AS`` de una definición de vista (H7).

SQL Server guarda el texto completo de la vista (``OBJECT_DEFINITION``, ``sys.sql_modules``) y
``INFORMATION_SCHEMA.VIEWS.VIEW_DEFINITION`` lo devolvía igual (y truncado a 4000 caracteres). ``migrate`` emite su
propia cabecera, así que necesita solo la query. Si la definición no empieza por ``CREATE [OR ALTER] VIEW`` (otros
motores ya devuelven solo la query) se devuelve sin cambios.
"""

from __future__ import annotations

import re

from dataclasses import dataclass

_LEADING_COMMENTS_RE: re.Pattern[str] = re.compile(r"^(?:\s+|--[^\n]*(?:\n|$)|/\*.*?\*/)*", re.DOTALL)
#: Parte de un nombre: [corchetes], "comillas", `backticks` o identificador simple.
_NAME_PART: str = r'(?:\[[^\]]+\]|"[^"]+"|`[^`]+`|[\w@#$]+)'
_VIEW_ATTRIBUTE: str = r"(?:SCHEMABINDING|ENCRYPTION|VIEW_METADATA)"
_HEADER_RE: re.Pattern[str] = re.compile(
    rf"CREATE\s+(?:OR\s+ALTER\s+)?VIEW\s+{_NAME_PART}(?:\s*\.\s*{_NAME_PART}){{0,2}}"
    r"\s*(?P<columns>\((?:[^()\[\]]|\[[^\]]*\])*\))?"
    rf"(?:\s*WITH\s+{_VIEW_ATTRIBUTE}(?:\s*,\s*{_VIEW_ATTRIBUTE})*)?"
    r"\s*AS\b\s*",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ViewDefinitionSplit:
    """Query de la vista sin cabecera y, si la cabecera la tenía, su lista explícita de columnas."""

    query: str
    column_list: str | None = None


def split_create_view_header(definition: str) -> ViewDefinitionSplit:
    """Devuelve la query de ``definition`` sin la cabecera ``CREATE [OR ALTER] VIEW nombre [(cols)] [WITH ...] AS``.

    También quita los comentarios que preceden a la cabecera y el ``;`` final.
    """
    text: str = definition.strip()
    body_start: int = _LEADING_COMMENTS_RE.match(text).end()  # type: ignore[union-attr]
    header = _HEADER_RE.match(text, body_start)
    if header is None:
        return ViewDefinitionSplit(query=text)
    query: str = text[header.end() :].strip().rstrip(";").rstrip()
    columns: str | None = header.group("columns")
    return ViewDefinitionSplit(query=query, column_list=columns[1:-1].strip() if columns else None)


__all__: list[str] = ["ViewDefinitionSplit", "split_create_view_header"]
