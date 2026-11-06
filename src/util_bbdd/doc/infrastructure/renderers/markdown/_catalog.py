"""``catalog.json`` (contrato ADR-006) y ``llms.txt`` / ``llms-full.txt`` (formato de llmstxt.org).

``catalog.json`` es el catálogo máquina-legible de los objetos documentados: el mismo ``id`` y ``hash`` que el front
matter de cada página, más columnas, claves, índices y hashes de definiciones. Sin fechas: es determinista y sirve
para comparar dos generaciones (``CHANGES.md``).
"""

from __future__ import annotations

import json

from dataclasses import dataclass
from typing import Any

from ._text import md_link, md_text

CATALOG_FORMAT = "util_bbdd.doc.catalog"
CATALOG_FORMAT_VERSION = 1

#: Orden de los tipos de objeto en el catálogo y en ``llms*.txt``
_KIND_ORDER: dict[str, int] = {"table": 0, "view": 1}


@dataclass(frozen=True)
class CatalogEntry:
    """Un objeto documentado: su registro (``ObjectRecords``) y su página, relativa a ``docs/``."""

    record: dict[str, Any]
    path: str


def catalog_json(
    entries: list[CatalogEntry], *, engine: str, schema: str, database: str, selection: dict[str, bool]
) -> str:
    """Texto de ``catalog.json`` (UTF-8, claves ordenadas, sangría 2, salto de línea final).

    Args:
        entries: Objetos documentados en el orden de los índices.
        engine: Motor del snapshot.
        schema: Schema documentado.
        database: Nombre que se muestra de la base de datos.
        selection: Qué tipos de objeto se pidieron (``tables``, ``views``, ``procedures``, ``functions``); distingue un
            objeto borrado de uno que no se pidió al comparar generaciones.
    """
    objects = [{**entry.record, "path": entry.path} for entry in _ordered(entries)]
    catalog = {
        "format": CATALOG_FORMAT,
        "format_version": CATALOG_FORMAT_VERSION,
        "engine": engine,
        "schema": schema,
        "database": database,
        "selection": selection,
        "objects": objects,
    }
    return json.dumps(catalog, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _ordered(entries: list[CatalogEntry]) -> list[CatalogEntry]:
    # Estable: dentro de cada tipo se conserva el orden de los índices
    return sorted(entries, key=lambda e: _KIND_ORDER.get(e.record["kind"], 2))


def llms_txt(
    entries: list[CatalogEntry],
    *,
    database: str,
    engine: str,
    schema: str,
    with_catalog: bool,
    with_full: bool,
    with_traceability: bool = False,
) -> str:
    """``llms.txt``: título, resumen, una sección por tipo de objeto con enlaces y la sección ``Optional``."""
    tables = [e for e in entries if e.record["kind"] == "table"]
    views = [e for e in entries if e.record["kind"] == "view"]
    routines = [e for e in entries if e.record["kind"] not in _KIND_ORDER]
    lines = [
        f"# Documentación de la base de datos {md_text(database)}",
        "",
        f"> Schema {md_text(schema)} ({md_text(engine)}): {len(tables)} tablas, {len(views)} vistas, "
        f"{len(routines)} rutinas. Un fichero Markdown por objeto, con front matter (id estable, PK y FK)"
        + (". Catálogo completo en catalog.json." if with_catalog else "."),
        "",
    ]
    for title, items in (("Tablas", tables), ("Vistas", views), ("Rutinas", routines)):
        if items:
            lines += [f"## {title}", "", *(_llms_item(e) for e in items), ""]
    optional = []
    if with_catalog:
        optional.append("- [Catálogo JSON](catalog.json): columnas, claves, índices y hashes de cada objeto")
    if with_full:
        optional.append("- [Documentación completa](llms-full.txt): todas las páginas en un solo fichero")
    if with_traceability:
        optional.append(
            "- [Trazabilidad](traceability.md): objetos ↔ código, documentos funcionales y técnicos y requisitos"
        )
    if optional:
        lines += ["## Optional", "", *optional, ""]
    return "\n".join(lines).rstrip("\n") + "\n"


def _llms_item(entry: CatalogEntry) -> str:
    record = entry.record
    label = record["name"] if record["kind"] in _KIND_ORDER else f"{record['name']} ({record['kind']})"
    comment = md_text(record.get("comment") or "")
    return f"- {md_link(label, entry.path)}" + (f": {comment}" if comment else "")


def llms_full_marker(record: dict[str, Any], path: str) -> str:
    """Marcador que precede a cada página en ``llms-full.txt``: id y ruta del objeto (comentario HTML)."""
    return f"<!-- {record['id'].replace('--', '- -')} · {path} -->"


__all__: list[str] = [
    "CATALOG_FORMAT",
    "CATALOG_FORMAT_VERSION",
    "CatalogEntry",
    "catalog_json",
    "llms_full_marker",
    "llms_txt",
]
