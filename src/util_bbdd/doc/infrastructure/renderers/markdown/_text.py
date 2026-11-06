"""Texto seguro para Markdown (CommonMark/GFM, Python-Markdown de Zensical y MkDocs).

Los nombres, comentarios y valores del catálogo son datos no confiables: Zensical y MkDocs publican el HTML en línea
tal cual (XSS) y el Markdown los interpretaría (``*énfasis*``, enlaces, celdas partidas por ``|``). Reglas validadas en
SPIKE_C3 (sesión ``2026-11-05-doc-markdown``).
"""

from __future__ import annotations

import json
import re

from collections.abc import Callable
from typing import Any

# Saltos de línea y caracteres de control (C0, DEL, C1) y separadores de línea/párrafo de Unicode
_LINE_BREAKS: re.Pattern[str] = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]+")
# Puntuación con significado en Markdown en línea; se escapa con barra invertida (CommonMark §2.4). El «_» entre dos
# caracteres de palabra no abre énfasis (``cliente_id``) y se deja tal cual para que el Markdown en crudo se lea limpio.
_MD_PUNCTUATION: re.Pattern[str] = re.compile(r"([\\`*~\[\]|#]|(?<!\w)_|_(?!\w))")
_BACKTICK_RUN: re.Pattern[str] = re.compile(r"`+")


def md_text(value: Any) -> str:
    """Texto del catálogo en línea (párrafo, título, celda): sin HTML, sin formato Markdown y en una sola línea.

    ``&``, ``<`` y ``>`` pasan a entidades HTML (primero ``&``, para no recodificar las demás); la puntuación de Markdown
    (`` \\ ` * ~ [ ] | # `` y ``_`` en un extremo de palabra) se escapa con barra invertida; los saltos de línea pasan a
    espacio.

    Examples:
        >>> md_text("<b>hola</b> & más")
        '&lt;b&gt;hola&lt;/b&gt; &amp; más'
    """
    text = "" if value is None else str(value)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = _MD_PUNCTUATION.sub(r"\\\1", text)
    return _LINE_BREAKS.sub(" ", text).strip()


def md_table(
    headers: list[str],
    rows: list[list[Any]],
    *,
    raw_first_cell: list[str] | None = None,
    cell_renderers: dict[int, Callable[[Any], str]] | None = None,
) -> list[str]:
    """Tabla GFM con cabeceras y celdas escapadas.

    Args:
        headers: Cabeceras (texto del catálogo o de ``headers_config.json``, también escapadas).
        rows: Filas; cada valor se convierte a texto y se escapa. Las filas más cortas se completan con celdas vacías.
        raw_first_cell: Prefijo HTML ya seguro por fila para la primera celda (anclas ``<a id>`` generadas aquí, nunca
            texto del catálogo).
        cell_renderers: Por índice de columna, función que devuelve Markdown ya seguro para el valor (p. ej. un enlace
            con :func:`md_link`); el resto de columnas, :func:`md_text`.
    """
    width = len(headers)
    renderers = cell_renderers or {}
    lines = [
        "| " + " | ".join(md_text(h) for h in headers) + " |",
        "|" + "---|" * width,
    ]
    for index, row in enumerate(rows):
        cells = [renderers.get(i, md_text)(row[i]) if i < len(row) else "" for i in range(width)]
        if raw_first_cell is not None and width:
            cells[0] = f"{raw_first_cell[index]}{cells[0]}"
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def md_code_block(code: Any, language: str = "") -> list[str]:
    """Bloque de código con una *fence* más larga que cualquier racha de backticks del contenido (mínimo 3)."""
    text = "" if code is None else str(code).replace("\r\n", "\n").replace("\r", "\n")
    longest = max((len(run) for run in _BACKTICK_RUN.findall(text)), default=0)
    fence = "`" * max(3, longest + 1)
    return [f"{fence}{language}", *text.rstrip("\n").split("\n"), fence]


def md_link(label: str, target: str) -> str:
    """Enlace relativo generado por la librería: ``label`` es texto del catálogo (escapado); ``target``, una ruta propia."""
    return f"[{md_text(label)}]({target})"


def front_matter(data: dict[str, Any]) -> list[str]:
    """Front matter YAML en una línea JSON (YAML 1.2 ⊃ JSON): sin PyYAML y sin inyección de claves o documentos."""
    return ["---", json.dumps(data, ensure_ascii=False, sort_keys=True), "---", ""]


def admonition(kind: str, title: str, body: str = "") -> list[str]:
    """Aviso ``!!! kind "título"`` (extensión ``admonition``); en un visor sin ella se lee como texto."""
    lines = [f'!!! {kind} "{md_text(title).replace(chr(34), "&quot;")}"']
    if body:
        lines.append(f"    {md_text(body)}")
    return [*lines, ""]


__all__: list[str] = ["admonition", "front_matter", "md_code_block", "md_link", "md_table", "md_text"]
