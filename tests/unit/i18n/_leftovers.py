"""Detector de texto en español en salidas generadas en inglés (tests de i18n de resultados, 5.10.0).

Busca tildes, ``ñ``, signos de apertura y palabras españolas típicas de las salidas de la librería. Los datos de los
fixtures (nombres de tablas, comentarios…) deben estar en inglés o sin tildes para no dar falsos positivos; lo que no se
traduce a propósito (mensajes de ``EngineReadinessAdvisor``, excepciones del motor) se excluye con ``ignore``.
"""

from __future__ import annotations

import re
import zipfile

from collections.abc import Iterable
from pathlib import Path

_ACCENTS = re.compile(r"[áéíóúñÁÉÍÓÚÑ¿¡]")
_WORDS = re.compile(
    r"\b(Tablas?|Columnas?|Vistas?|Rutinas?|Indice|Filas|Origen|Destino|Estado|Mensaje|Resumen|Generado|Nombre|"
    r"Tipo|Clave|Campo|Nulo|Comentario|Esquema|Cambios|Trazabilidad|Almacenamiento|Condiciones|Fecha|Cantidad|Motivo|"
    r"Procedimientos?|Funciones|Restricci|Hallazgos|Propiedad|Valor|Sin|Ninguna?|Volver|Buscar|Descargar|Copiar|Todos?|"
    r"Inicio|Anterior|Siguiente|Ver|Detalle|Documentaci|Diagrama|Relaciones|Secuencias|Acci|Agregad|Eliminad|"
    r"Modificad|Nuev[oa]s?|Diferencias|Informe|Generaci|Ficheros?|Tama|Espacio|Usuario|Fuente|Ruta|Objetos?)\b"
)


def spanish_hits(text: str, ignore: Iterable[str] = ()) -> list[str]:
    """Líneas de ``text`` con indicios de español (sin las que contienen alguno de ``ignore``)."""
    ignored = tuple(ignore)
    hits: list[str] = []
    for line in text.splitlines():
        if ignored and any(token in line for token in ignored):
            continue
        if _ACCENTS.search(line) or _WORDS.search(line):
            hits.append(line.strip()[:200])
    return hits


def visible_text(path: Path) -> str:
    """Texto visible de una salida: celdas y hojas de Excel, párrafos y tablas de Word, o el fichero tal cual."""
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        import openpyxl

        workbook = openpyxl.load_workbook(path)
        parts: list[str] = []
        for sheet in workbook.worksheets:
            parts.append(sheet.title)
            parts.extend(str(cell.value) for row in sheet.iter_rows() for cell in row if cell.value is not None)
        return "\n".join(parts)
    if suffix == ".docx":
        import docx

        document = docx.Document(str(path))
        parts = [paragraph.text for paragraph in document.paragraphs]
        parts.extend(cell.text for table in document.tables for row in table.rows for cell in row.cells)
        return "\n".join(parts)
    if suffix in {".png", ".zip"} or zipfile.is_zipfile(path):
        return ""
    return path.read_text(encoding="utf-8")


def spanish_hits_in(paths: Iterable[Path], ignore: Iterable[str] = ()) -> dict[str, list[str]]:
    """``{nombre de fichero: líneas con español}`` de las salidas con algún indicio."""
    ignored = tuple(ignore)
    found = {path.name: spanish_hits(visible_text(path), ignored) for path in paths if path.is_file()}
    return {name: hits for name, hits in found.items() if hits}
