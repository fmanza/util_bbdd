"""Mapa de trazabilidad de la documentación Markdown (``imprimir["markdown"]["trace_map"]``, desde 5.3.0).

Un fichero TOML (recomendado, admite comentarios) o JSON (mismo esquema) relaciona cada objeto documentado, y si se
quiere cada columna, con código, documentos funcionales y técnicos y requisitos::

    [tables."PEDIDOS"]
    code = ["src/ventas/pedidos.py#Pedido"]
    requirements = ["REQ-012"]

    [tables."PEDIDOS".columns."CLIENTE_ID"]
    code = ["src/ventas/pedidos.py#Pedido.cliente_id"]

    [routines."PROCEDURE:P_ALTA_PEDIDO"]
    code = ["src/ventas/alta.py"]

La validación es estricta (un campo desconocido es error: una errata no deja la traza vacía en silencio). Las
referencias son **texto**: nunca se leen ni se resuelven contra el disco; solo las URL ``http(s)`` se enlazan.
"""

from __future__ import annotations

import json
import os
import re
import tomllib

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

from ....._core.exceptions import DocumentationConfigError
from ....._core.markdown import code_span  # común con el informe de comparar (5.3.0)
from ._text import md_link, md_table, md_text

#: Tipos de referencia, en el orden en que se muestran
REFERENCE_KINDS: tuple[tuple[str, str], ...] = (
    ("code", "Código"),
    ("functional", "Funcional"),
    ("technical", "Técnico"),
    ("requirements", "Requisitos"),
)
_LIST_FIELDS: frozenset[str] = frozenset({kind for kind, _ in REFERENCE_KINDS} | {"tags"})
_OBJECT_FIELDS: frozenset[str] = _LIST_FIELDS | {"notes", "columns"}
_COLUMN_FIELDS: frozenset[str] = _LIST_FIELDS | {"notes"}
SECTIONS: tuple[str, ...] = ("tables", "views", "routines")
MAX_BYTES: int = 1_000_000
_URL: re.Pattern[str] = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)


@dataclass(frozen=True)
class TraceEntry:
    """Trazas de un objeto o de una columna."""

    refs: dict[str, tuple[str, ...]] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    notes: str = ""
    columns: dict[str, TraceEntry] = field(default_factory=dict)

    @property
    def has_references(self) -> bool:
        return any(self.refs.values()) or any(c.has_references for c in self.columns.values())

    def to_dict(self, columns: dict[str, TraceEntry] | None = None) -> dict[str, Any]:
        """Forma publicada (front matter y ``catalog.json``): solo los campos con contenido."""
        data: dict[str, Any] = {kind: list(values) for kind, values in self.refs.items() if values}
        if self.tags:
            data["tags"] = list(self.tags)
        if self.notes:
            data["notes"] = self.notes
        published = self.columns if columns is None else columns
        if published:
            data["columns"] = {name: entry.to_dict() for name, entry in sorted(published.items())}
        return data


@dataclass(frozen=True)
class Unmatched:
    """Entrada del mapa que no corresponde a ningún objeto (o columna) documentado."""

    section: str
    key: str
    reason: str


@dataclass(frozen=True)
class TraceMap:
    """Mapa de trazabilidad validado: por sección (``tables``, ``views``, ``routines``), clave → trazas."""

    sections: dict[str, dict[str, TraceEntry]]

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> TraceMap:
        """Lee y valida el mapa; el formato sale de la extensión (``.toml`` o ``.json``).

        Los mensajes nombran el fichero, nunca su ruta (5.7.0, G49 de util_bbdd_web): se muestran a usuarios que no
        deben ver la estructura de carpetas del servidor.

        Raises:
            DocumentationConfigError: Extensión no admitida, fichero ilegible, demasiado grande o con sintaxis
                inválida, o contenido que no sigue el esquema (con todos los errores juntos).
        """
        file = Path(path).expanduser()
        suffix = file.suffix.lower()
        if suffix not in {".toml", ".json"}:
            raise _config_error(f"markdown.trace_map debe ser .toml o .json: {file.name}")
        try:
            if file.stat().st_size > MAX_BYTES:
                raise _config_error(f"markdown.trace_map ({file.name}) supera {MAX_BYTES} bytes")
            raw = file.read_bytes()
            data: Any = tomllib.loads(raw.decode("utf-8")) if suffix == ".toml" else json.loads(raw)
        except DocumentationConfigError:  # también es ValueError: se relanza tal cual
            raise
        except (OSError, ValueError) as error:  # incluye UnicodeDecodeError y TOMLDecodeError
            raise _config_error(f"markdown.trace_map no se puede leer ({file.name}): {error_reason(error)}") from error
        errors: list[str] = []
        sections = _parse(data, errors)
        if errors:
            raise _config_error(f"markdown.trace_map ({file.name}) no es válido: " + "; ".join(errors))
        return cls(sections)

    def match(self, section: str, names: list[str]) -> tuple[dict[str, TraceEntry], list[Unmatched]]:
        """Trazas de los objetos documentados ``names`` de una sección y entradas que no casan.

        Casa por nombre exacto y, si no, sin distinguir mayúsculas cuando no es ambiguo (Oracle guarda en mayúsculas).
        """
        matched, unmatched = _match(self.sections.get(section, {}), names)
        return matched, [Unmatched(section, key, reason) for key, reason in unmatched]


def match_columns(entry: TraceEntry, table: str, columns: list[str]) -> tuple[dict[str, TraceEntry], list[Unmatched]]:
    """Trazas por columna de una tabla (con la misma regla de casado que los objetos)."""
    matched, unmatched = _match(entry.columns, columns, missing="la tabla no tiene ninguna columna con ese nombre")
    return matched, [Unmatched("columns", f"{table}.{key}", reason) for key, reason in unmatched]


def _match(
    entries: dict[str, TraceEntry],
    names: list[str],
    *,
    missing: str = "no se documenta ningún objeto con ese nombre",
) -> tuple[dict[str, TraceEntry], list[tuple[str, str]]]:
    by_fold: dict[str, list[str]] = {}
    for name in names:
        by_fold.setdefault(name.casefold(), []).append(name)
    exact = set(names)
    matched: dict[str, TraceEntry] = {}
    unmatched: list[tuple[str, str]] = []
    # Primero las exactas: una exacta gana a una que solo casa sin mayúsculas
    for key in sorted(entries, key=lambda k: (k not in exact, k)):
        if key in exact:
            target: str | None = key
        else:
            candidates = by_fold.get(key.casefold(), [])
            if len(candidates) > 1:
                unmatched.append((key, "ambiguo: varios nombres coinciden sin distinguir mayúsculas"))
                continue
            target = candidates[0] if candidates else None
        if target is None:
            unmatched.append((key, missing))
        elif target in matched:
            unmatched.append((key, f"duplicada: «{target}» ya tiene otra entrada"))
        else:
            matched[target] = entries[key]
    return matched, sorted(unmatched)


# --- Validación ---


def _config_error(message: str) -> DocumentationConfigError:
    return DocumentationConfigError(message, operation="DOCUMENTATION")


def error_reason(error: Exception) -> str:
    """Motivo de un error de lectura sin la ruta del fichero: ``str()`` de un ``OSError`` la incluye."""
    if isinstance(error, OSError):
        return error.strerror or type(error).__name__
    return str(error)


def _parse(data: Any, errors: list[str]) -> dict[str, dict[str, TraceEntry]]:
    if not isinstance(data, dict):
        errors.append("la raíz debe ser una tabla/objeto")
        return {}
    version = data.get("version", 1)
    if version != 1:
        errors.append(f"version {version!r} no soportada (solo 1)")
    unknown = sorted(set(data) - set(SECTIONS) - {"version"})
    if unknown:
        errors.append(f"secciones desconocidas: {', '.join(unknown)} (admitidas: {', '.join(SECTIONS)})")
    sections: dict[str, dict[str, TraceEntry]] = {}
    for section in SECTIONS:
        content = data.get(section, {})
        if not isinstance(content, dict):
            errors.append(f"«{section}» debe ser una tabla/objeto")
            continue
        sections[section] = {
            str(key): _entry(value, f"{section}.{key}", errors, allow_columns=section == "tables")
            for key, value in content.items()
        }
    return sections


def _entry(value: Any, where: str, errors: list[str], *, allow_columns: bool) -> TraceEntry:
    if not isinstance(value, dict):
        errors.append(f"{where}: debe ser una tabla/objeto")
        return TraceEntry()
    allowed = _OBJECT_FIELDS if allow_columns else _COLUMN_FIELDS
    unknown = sorted(set(value) - allowed)
    if unknown:
        errors.append(f"{where}: campos desconocidos {', '.join(unknown)} (admitidos: {', '.join(sorted(allowed))})")
    refs: dict[str, tuple[str, ...]] = {}
    for kind in [*(k for k, _ in REFERENCE_KINDS), "tags"]:
        items = value.get(kind, [])
        if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
            errors.append(f"{where}.{kind}: debe ser una lista de cadenas")
            items = []
        refs[kind] = tuple(item.strip() for item in items if item.strip())
    notes = value.get("notes", "")
    if not isinstance(notes, str):
        errors.append(f"{where}.notes: debe ser una cadena")
        notes = ""
    columns: dict[str, TraceEntry] = {}
    raw_columns = value.get("columns", {}) if allow_columns else {}
    if not isinstance(raw_columns, dict):
        errors.append(f"{where}.columns: debe ser una tabla/objeto")
    else:
        columns = {
            str(name): _entry(column, f"{where}.columns.{name}", errors, allow_columns=False)
            for name, column in raw_columns.items()
        }
    tags = refs.pop("tags")
    return TraceEntry(refs=refs, tags=tags, notes=notes.strip(), columns=columns)


# --- Render ---


def reference(ref: str, *, in_table: bool = False) -> str:
    """Una referencia: enlace si es una URL ``http(s)``; si no, código literal (nunca se resuelve)."""
    if _URL.match(ref):
        return md_link(ref, quote(ref, safe=":/?#[]@!$&'*+,;=%~-._").replace("(", "%28").replace(")", "%29"))
    return code_span(ref, in_table=in_table)


def _reference_rows(entry: TraceEntry) -> list[list[Any]]:
    return [
        [label, ", ".join(reference(ref, in_table=True) for ref in entry.refs.get(kind, ()))]
        for kind, label in REFERENCE_KINDS
        if entry.refs.get(kind)
    ]


def trace_section(entry: TraceEntry, columns: dict[str, TraceEntry], anchors: dict[str, str]) -> list[str]:
    """Sección «Trazabilidad» de una página: referencias, etiquetas, notas y trazas por columna.

    Args:
        entry: Trazas del objeto.
        columns: Trazas de columna ya casadas (nombre real de la columna → trazas).
        anchors: Ancla de cada columna en la página (``col-…``), si las hay.
    """
    lines = ["## Trazabilidad", ""]
    rows = _reference_rows(entry)
    if rows:
        lines += [*md_table(["Tipo", "Referencias"], rows, cell_renderers={1: str}), ""]
    if entry.tags:
        lines += [f"**Etiquetas:** {', '.join(md_text(tag) for tag in entry.tags)}", ""]
    if entry.notes:
        lines += [f"**Notas:** {md_text(entry.notes)}", ""]
    for name in sorted(columns):
        column = columns[name]
        title = md_link(name, f"#{anchors[name]}") if name in anchors else md_text(name)
        lines += [f"### Columna {title}", ""]
        column_rows = _reference_rows(column)
        if column_rows:
            lines += [*md_table(["Tipo", "Referencias"], column_rows, cell_renderers={1: str}), ""]
        if column.tags:
            lines += [f"**Etiquetas:** {', '.join(md_text(tag) for tag in column.tags)}", ""]
        if column.notes:
            lines += [f"**Notas:** {md_text(column.notes)}", ""]
    return lines


@dataclass(frozen=True)
class TracedObject:
    """Objeto documentado para ``traceability.md``: tipo (título de sección), nombre visible, página y trazas."""

    kind: str
    name: str
    path: str
    entry: TraceEntry | None
    columns: dict[str, TraceEntry] = field(default_factory=dict)


def traceability_page(objects: list[TracedObject], unmatched: list[Unmatched]) -> list[str]:
    """``docs/traceability.md``: cobertura, matriz, objetos sin trazar, índices inversos y entradas sin objeto."""
    lines = ["# Trazabilidad", ""]
    kinds = list(dict.fromkeys(o.kind for o in objects))
    traced = [o for o in objects if o.entry is not None and (o.entry.has_references or o.columns)]

    coverage: list[list[Any]] = []
    for kind in kinds:
        of_kind = [o for o in objects if o.kind == kind]
        hits = [o for o in traced if o.kind == kind]
        coverage.append([kind, len(of_kind), len(hits), _percent(len(hits), len(of_kind))])
    lines += ["## Cobertura", "", *md_table(["Tipo", "Documentados", "Trazados", "%"], coverage), ""]
    by_reference = [
        [
            label,
            sum(1 for o in traced if o.entry is not None and o.entry.refs.get(kind)),
            _percent(sum(1 for o in traced if o.entry is not None and o.entry.refs.get(kind)), len(objects)),
        ]
        for kind, label in REFERENCE_KINDS
    ]
    lines += [*md_table(["Referencia", "Objetos", "% del total"], by_reference), ""]

    if traced:
        matrix = [
            [
                (o.name, o.path),
                o.kind,
                *(len(o.entry.refs.get(kind, ())) if o.entry else 0 for kind, _ in REFERENCE_KINDS),
                len(o.columns),
            ]
            for o in traced
        ]
        headers = ["Objeto", "Tipo", *(label for _, label in REFERENCE_KINDS), "Columnas"]
        lines += ["## Matriz", "", *md_table(headers, matrix, cell_renderers={0: _link_cell}), ""]

    traced_ids = {id(o) for o in traced}
    untraced = [o for o in objects if id(o) not in traced_ids]
    if untraced:
        lines += ["## Sin trazar", ""]
        for kind in kinds:
            names = [md_link(o.name, o.path) for o in untraced if o.kind == kind]
            if names:
                lines += [f"**{md_text(kind)}** ({len(names)}): {', '.join(names)}", ""]

    lines += _inverse_index("## Por requisito", traced, "requirements")
    lines += _inverse_index("## Por fichero de código", traced, "code", strip_fragment=True)

    if unmatched:
        rows = [[u.section, u.key, u.reason] for u in unmatched]
        lines += ["## Entradas del mapa sin objeto", "", *md_table(["Sección", "Clave", "Motivo"], rows), ""]
    return lines


def _inverse_index(title: str, traced: list[TracedObject], kind: str, *, strip_fragment: bool = False) -> list[str]:
    index: dict[str, set[tuple[str, str]]] = {}
    for obj in traced:
        targets = [(obj.entry, obj.name, obj.path)] if obj.entry else []
        targets += [(entry, f"{obj.name}.{column}", obj.path) for column, entry in obj.columns.items()]
        for entry, label, path in targets:
            for ref in entry.refs.get(kind, ()):
                key = ref.split("#", 1)[0] if strip_fragment and not _URL.match(ref) else ref
                index.setdefault(key, set()).add((label, path))
    if not index:
        return []
    rows = [
        [reference(key, in_table=True), ", ".join(md_link(label, path) for label, path in sorted(index[key]))]
        for key in sorted(index)
    ]
    return [title, "", *md_table(["Referencia", "Objetos"], rows, cell_renderers={0: str, 1: str}), ""]


def _link_cell(value: tuple[str, str]) -> str:
    label, path = value
    return md_link(label, path)


def _percent(part: int, total: int) -> str:
    return f"{100 * part / total:.0f}" if total else "0"


__all__: list[str] = [
    "MAX_BYTES",
    "REFERENCE_KINDS",
    "SECTIONS",
    "TraceEntry",
    "TraceMap",
    "TracedObject",
    "Unmatched",
    "code_span",
    "match_columns",
    "reference",
    "trace_section",
    "traceability_page",
]
