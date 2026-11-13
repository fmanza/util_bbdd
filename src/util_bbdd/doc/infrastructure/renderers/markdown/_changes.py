"""Cambios de esquema respecto de una generación anterior (``imprimir["markdown"]["previous"]``, desde 5.3.0).

Compara el ``catalog.json`` de una generación anterior (ADR-006) con el de la actual, **sin conexión a la base de
datos**: ``SchemaComparator`` necesita dos ``Inspector`` vivos y el pasado ya no se puede consultar. El resultado es un
``SchemaDiff`` (formato público ``util_bbdd.schema_diff``, el que muestra el visor de util_bbdd_web) y una página
``changes.md`` con el escape y los enlaces del resto del sitio.

Mismas convenciones que ``SchemaComparator``: columnas casadas sin distinguir mayúsculas, ``existence`` con
``exists``/``missing``, ``nullable`` y ``primary_key`` como ``True``/``False``. Diferencias: se compara texto del mismo
motor (sin normalizar tipos ni defaults) y vistas y rutinas solo por el hash de su definición.
"""

from __future__ import annotations

import hashlib
import json

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

from ....._core.exceptions import DocumentationConfigError
from ....._core.markdown import code_span
from .....comparar.models import (
    ColumnDiff,
    CommentDiff,
    ForeignKeyDiff,
    IndexDiff,
    RoutineDiff,
    SchemaDiff,
    TableDiff,
    ViewDiff,
)
from ....domain.table_filter import TableFilter
from ._catalog import CATALOG_FORMAT, CATALOG_FORMAT_VERSION, CatalogEntry
from ._slugs import sort_key
from ._text import admonition, md_link, md_table, md_text
from ._trace import error_reason

MAX_BYTES: int = 50_000_000
_STATUS_ES: dict[str, str] = {"added": "Añadida", "removed": "Eliminada", "modified": "Modificada"}
_ATTRIBUTE_ES: dict[str, str] = {
    "existence": "existencia",
    "type": "tipo",
    "nullable": "admite nulos",
    "primary_key": "clave primaria",
    "default": "por defecto",
}
#: Tipo de objeto del catálogo → clave de ``selection``
_SELECTION_KEY: dict[str, str] = {
    "table": "tables",
    "view": "views",
    "procedure": "procedures",
    "function": "functions",
}


@dataclass(frozen=True)
class PreviousCatalog:
    """Catálogo de la generación anterior y datos de su manifiesto (si estaba junto a él)."""

    catalog: dict[str, Any]
    catalog_sha256: str
    generated_at: str | None = None
    util_bbdd_version: str | None = None

    @property
    def label(self) -> str:
        when = self.generated_at or "fecha desconocida"
        return f"Generación anterior: {self.catalog.get('database', '')} [{self.catalog.get('schema', '')}] ({when})"

    def manifest_entry(self) -> dict[str, Any]:
        """Datos de la generación anterior para ``manifest.json`` (``previous``)."""
        return {
            "catalog_sha256": self.catalog_sha256,
            "generated_at": self.generated_at,
            "util_bbdd_version": self.util_bbdd_version,
        }


def load_previous(path: Path | str) -> PreviousCatalog:
    """Lee el ``catalog.json`` de una generación anterior: el fichero, o una carpeta ``MARKDOWN`` o ``docs``.

    Raises:
        DocumentationConfigError: No se encuentra, no se puede leer, es demasiado grande, o no es un catálogo de un
            formato y versión que esta librería sabe leer.
    """
    given = Path(path).expanduser()
    candidates = [given] if given.is_file() else [given / "docs" / "catalog.json", given / "catalog.json"]
    file = next((c for c in candidates if c.is_file()), None)
    # Los mensajes nombran la carpeta o el fichero, nunca la ruta completa (5.7.0, G49 de util_bbdd_web).
    if file is None:
        raise _config_error(f"markdown.previous: no hay catalog.json en {given.name or given}")
    shown = f"{file.parent.name}/{file.name}"
    try:
        if file.stat().st_size > MAX_BYTES:
            raise _config_error(f"markdown.previous: {shown} supera {MAX_BYTES} bytes")
        raw = file.read_bytes()
        catalog: Any = json.loads(raw)
    except DocumentationConfigError:
        raise
    except (OSError, ValueError) as error:
        raise _config_error(f"markdown.previous: no se puede leer {shown}: {error_reason(error)}") from error
    if not isinstance(catalog, dict) or catalog.get("format") != CATALOG_FORMAT:
        raise _config_error(f"markdown.previous: {shown} no es un catálogo de util_bbdd ({CATALOG_FORMAT})")
    if catalog.get("format_version") != CATALOG_FORMAT_VERSION or not isinstance(catalog.get("objects"), list):
        raise _config_error(
            f"markdown.previous: versión {catalog.get('format_version')!r} del catálogo no soportada "
            f"(esta versión de util_bbdd lee la {CATALOG_FORMAT_VERSION})"
        )
    manifest = _neighbour_manifest(file)
    return PreviousCatalog(
        catalog=catalog,
        catalog_sha256=f"sha256:{hashlib.sha256(raw).hexdigest()}",
        generated_at=_str_or_none(manifest.get("generated_at")),
        util_bbdd_version=_str_or_none(manifest.get("util_bbdd_version")),
    )


def _neighbour_manifest(catalog_file: Path) -> dict[str, Any]:
    for candidate in (catalog_file.parent.parent / "manifest.json", catalog_file.parent / "manifest.json"):
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("format") == "util_bbdd.doc.markdown":
            return data
    return {}


def _str_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _config_error(message: str) -> DocumentationConfigError:
    return DocumentationConfigError(message, operation="DOCUMENTATION")


# --- Comparación ---


@dataclass
class Changes:
    """Resultado de la comparación: el ``SchemaDiff``, avisos y rutinas de otros tipos (fuera del modelo)."""

    diff: SchemaDiff
    notices: list[str] = field(default_factory=list)
    other_routines: list[tuple[str, str, str]] = field(default_factory=list)  # (nombre, tipo, estado)


def build_changes(
    previous: PreviousCatalog,
    current: list[CatalogEntry],
    *,
    engine: str,
    schema: str,
    database: str,
    selection: dict[str, bool],
    table_filter: TableFilter | None = None,
) -> Changes:
    """Compara el catálogo anterior con los objetos de la generación actual.

    Con un filtro de tablas (5.5.0) en alguna de las dos generaciones, las tablas y vistas se comparan solo si las
    documentan los filtros de ambas: lo que una dejó fuera no cuenta como añadido ni como eliminado.

    Raises:
        DocumentationConfigError: El motor de la generación anterior es otro (los tipos no son comparables).
    """
    old = previous.catalog
    if old.get("engine") != engine:
        raise _config_error(
            f"markdown.previous: la generación anterior es de otro motor ({old.get('engine')!r}, ahora {engine!r})"
        )
    notices: list[str] = []
    if old.get("schema") != schema:
        notices.append(f"Los schemas son distintos ({old.get('schema')} → {schema}): se compara por nombre de objeto.")
    old_selection: dict[str, Any] = dict(old.get("selection") or {})
    compared: set[str] = set()
    for kind, key in _SELECTION_KEY.items():
        if selection.get(key) and old_selection.get(key):
            compared.add(kind)
        elif selection.get(key) or old_selection.get(key):
            where = "anterior" if not old_selection.get(key) else "actual"
            notices.append(f"No se comparan los objetos de tipo «{key}»: no se documentaron en la generación {where}.")

    before = _by_kind(cast(list[dict[str, Any]], old["objects"]))
    after = _by_kind([{**entry.record, "path": entry.path} for entry in current])
    old_filter = TableFilter.from_catalog(old.get("filter"))
    # Por patrones: ``frontera`` no cambia lo que se documenta
    if (old_filter and old_filter.to_catalog()) != (table_filter and table_filter.to_catalog()):
        notices.append(
            "Las dos generaciones tienen distinto filtro de tablas: solo se comparan las tablas y vistas que entran en "
            "ambos."
        )
        filters = [f for f in (old_filter, table_filter) if f is not None]
        for kind in ("table", "view"):
            for side in (before, after):
                if kind in side:
                    side[kind] = {
                        name: obj for name, obj in side[kind].items() if all(f.matches(name) for f in filters)
                    }
    changes = Changes(
        diff=SchemaDiff(source_label=previous.label, target_label=f"Generación actual: {database} [{schema}]")
    )
    table_diffs = _compare(before.get("table", {}), after.get("table", {}), _table_diff) if "table" in compared else []
    view_diffs = _compare(before.get("view", {}), after.get("view", {}), _view_diff) if "view" in compared else []
    routine_diffs: list[RoutineDiff] = []
    other_kinds = sorted((set(before) | set(after)) - {"table", "view"})
    for kind in other_kinds:
        if kind in _SELECTION_KEY and kind not in compared:
            continue
        for name, status in _statuses(before.get(kind, {}), after.get(kind, {})):
            if kind in {"procedure", "function"}:
                routine_type = cast(Literal["PROCEDURE", "FUNCTION"], kind.upper())
                routine_diffs.append(RoutineDiff(routine_name=name, routine_type=routine_type, status=status))
            else:
                changes.other_routines.append((name, kind, status))
    changes.diff = SchemaDiff(
        source_label=changes.diff.source_label,
        target_label=changes.diff.target_label,
        table_diffs=tuple(table_diffs),
        view_diffs=tuple(view_diffs),
        routine_diffs=tuple(sorted(routine_diffs, key=lambda r: (sort_key(r.routine_name), r.routine_type))),
    )
    changes.notices = notices
    return changes


Status = Literal["added", "removed", "modified"]


def _by_kind(objects: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for obj in objects:
        grouped.setdefault(str(obj.get("kind")), {})[str(obj.get("name"))] = obj
    return grouped


def _statuses(before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]) -> list[tuple[str, Status]]:
    """Nombre y estado de lo añadido, eliminado o con otro hash, en orden estable."""
    result: list[tuple[str, Status]] = []
    for name in sorted(set(before) | set(after), key=sort_key):
        if name not in before:
            result.append((name, "added"))
        elif name not in after:
            result.append((name, "removed"))
        elif before[name].get("hash") != after[name].get("hash"):
            result.append((name, "modified"))
    return result


def _compare(before: dict[str, Any], after: dict[str, Any], differ: Any) -> list[Any]:
    diffs = [differ(name, status, before.get(name), after.get(name)) for name, status in _statuses(before, after)]
    return [diff for diff in diffs if diff is not None]


def _view_diff(name: str, status: Status, old: dict[str, Any] | None, new: dict[str, Any] | None) -> ViewDiff:
    return ViewDiff(view_name=name, status=status)


def _table_diff(name: str, status: Status, old: dict[str, Any] | None, new: dict[str, Any] | None) -> TableDiff | None:
    if status != "modified" or old is None or new is None:
        return TableDiff(table_name=name, status=status)
    diff = TableDiff(
        table_name=name,
        status="modified",
        column_diffs=tuple(_column_diffs(old, new)),
        index_diffs=tuple(_index_diffs(name, old, new)),
        fk_diffs=tuple(_fk_diffs(name, old, new)),
        comment_diffs=tuple(_comment_diffs(name, old, new)),
    )
    # Cambió el hash pero nada de lo que recoge el modelo (p. ej. identidad o columna calculada): sin entrada
    if not (diff.column_diffs or diff.index_diffs or diff.fk_diffs or diff.comment_diffs):
        return None
    return diff


def _pk(obj: dict[str, Any]) -> set[str]:
    pk = obj.get("pk") or {}
    return {str(c).lower() for c in pk.get("columns", [])} if isinstance(pk, dict) else set()


def _columns(obj: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(c["name"]).lower(): c for c in obj.get("columns", [])}


def _column_diffs(old: dict[str, Any], new: dict[str, Any]) -> list[ColumnDiff]:
    before, after = _columns(old), _columns(new)
    diffs = [
        ColumnDiff(before[k]["name"], "existence", "exists", "missing") for k in sorted(before.keys() - after.keys())
    ]
    diffs += [
        ColumnDiff(after[k]["name"], "existence", "missing", "exists") for k in sorted(after.keys() - before.keys())
    ]
    old_pk, new_pk = _pk(old), _pk(new)
    for key in sorted(before.keys() & after.keys()):
        s, t = before[key], after[key]
        pairs: list[tuple[Literal["type", "nullable", "primary_key", "default"], str, str]] = [
            ("type", str(s.get("type") or ""), str(t.get("type") or "")),
            ("nullable", str(bool(s.get("nullable", True))), str(bool(t.get("nullable", True)))),
            ("primary_key", str(key in old_pk), str(key in new_pk)),
            ("default", str(s.get("default") or ""), str(t.get("default") or "")),
        ]
        diffs += [ColumnDiff(str(t["name"]), attribute, a, b) for attribute, a, b in pairs if a != b]
    return diffs


def _index_diffs(table: str, old: dict[str, Any], new: dict[str, Any]) -> list[IndexDiff]:
    before = {str(i["name"]): i for i in old.get("indexes", [])}
    after = {str(i["name"]): i for i in new.get("indexes", [])}
    diffs: list[IndexDiff] = []
    for name, status in _statuses_plain(before, after):
        s, t = before.get(name, {}), after.get(name, {})
        if status == "modified" and (s.get("columns"), s.get("unique")) == (t.get("columns"), t.get("unique")):
            continue
        diffs.append(
            IndexDiff(
                index_name=name,
                table_name=table,
                status=status,
                source_columns=", ".join(s.get("columns", [])),
                target_columns=", ".join(t.get("columns", [])),
                source_unique=bool(s.get("unique", False)),
                target_unique=bool(t.get("unique", False)),
            )
        )
    return diffs


def _fk_key(fk: dict[str, Any]) -> str:
    """Nombre de la FK o, si no tiene (SQLite), sus columnas y la tabla referenciada."""
    return str(fk.get("name") or f"({', '.join(fk.get('columns', []))}) → {_ref_table(fk)}")


def _ref_table(fk: dict[str, Any]) -> str:
    """Tabla referenciada a partir del id ``table:<schema>.<nombre>``."""
    ref = str(fk.get("ref", ""))
    return ref.split(":", 1)[-1].split(".", 1)[-1]


def _fk_diffs(table: str, old: dict[str, Any], new: dict[str, Any]) -> list[ForeignKeyDiff]:
    before = {_fk_key(fk): fk for fk in old.get("fk_out", [])}
    after = {_fk_key(fk): fk for fk in new.get("fk_out", [])}
    diffs: list[ForeignKeyDiff] = []
    for name, status in _statuses_plain(before, after):
        s, t = before.get(name, {}), after.get(name, {})
        fields_ = ("columns", "ref", "ref_columns", "on_delete", "on_update")
        if status == "modified" and all(s.get(f) == t.get(f) for f in fields_):
            continue
        diffs.append(
            ForeignKeyDiff(
                fk_name=name,
                table_name=table,
                status=status,
                source_columns=", ".join(s.get("columns", [])),
                target_columns=", ".join(t.get("columns", [])),
                source_referred_table=_ref_table(s) if s else "",
                target_referred_table=_ref_table(t) if t else "",
                source_referred_columns=", ".join(s.get("ref_columns", [])),
                target_referred_columns=", ".join(t.get("ref_columns", [])),
            )
        )
    return diffs


def _statuses_plain(before: dict[str, Any], after: dict[str, Any]) -> list[tuple[str, Status]]:
    """Como :func:`_statuses` pero todo lo común es candidato a ``modified`` (quien llama decide)."""
    result: list[tuple[str, Status]] = []
    for name in sorted(set(before) | set(after), key=sort_key):
        status: Status = "added" if name not in before else "removed" if name not in after else "modified"
        result.append((name, status))
    return result


def _comment_diffs(table: str, old: dict[str, Any], new: dict[str, Any]) -> list[CommentDiff]:
    diffs: list[CommentDiff] = []
    if (old.get("comment") or "") != (new.get("comment") or ""):
        diffs.append(CommentDiff(table, None, str(old.get("comment") or ""), str(new.get("comment") or "")))
    before, after = _columns(old), _columns(new)
    for key in sorted(before.keys() & after.keys()):
        s, t = str(before[key].get("comment") or ""), str(after[key].get("comment") or "")
        if s != t:
            diffs.append(CommentDiff(table, str(after[key]["name"]), s, t))
    return diffs


# --- Salida ---


def changes_json(changes: Changes) -> str:
    """``changes.json``: ``SchemaDiff.to_dict()`` (formato ``util_bbdd.schema_diff`` v1)."""
    return json.dumps(changes.diff.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def changes_page(changes: Changes, links: dict[tuple[str, str], str]) -> list[str]:
    """``changes.md``: cabecera, avisos, resumen y una sección por tipo con enlaces a las páginas actuales.

    Args:
        changes: Resultado de :func:`build_changes`.
        links: Página actual de cada objeto, por ``(kind, nombre)`` (relativa a ``docs/``).
    """
    diff = changes.diff
    lines = [
        "# Cambios de esquema",
        "",
        *md_table(["", ""], [["Anterior", diff.source_label], ["Actual", diff.target_label]]),
        "",
    ]
    for notice in changes.notices:
        lines += admonition("warning", notice)
    summary = [
        ["Tablas", *_counts([t.status for t in diff.table_diffs])],
        ["Vistas", *_counts([v.status for v in diff.view_diffs])],
        ["Rutinas", *_counts([r.status for r in diff.routine_diffs] + [s for _, _, s in changes.other_routines])],
    ]
    lines += ["## Resumen", "", *md_table(["Tipo", "Añadidas", "Eliminadas", "Modificadas"], summary), ""]
    if not diff.has_differences and not changes.other_routines:
        return [*lines, "Sin cambios de esquema.", ""]
    for table in diff.table_diffs:
        lines += _object_heading("Tabla", table.table_name, table.status, links.get(("table", table.table_name)))
        lines += _table_details(table)
    for view in diff.view_diffs:
        lines += _object_heading("Vista", view.view_name, view.status, links.get(("view", view.view_name)))
        if view.status == "modified":
            lines += ["La definición o las columnas han cambiado (el catálogo guarda solo su hash).", ""]
    routines = [(r.routine_name, r.routine_type.lower(), r.status) for r in diff.routine_diffs] + changes.other_routines
    for name, kind, status in routines:
        lines += _object_heading(kind.title(), name, status, links.get((kind, name)))
    return lines


def _counts(statuses: list[str]) -> list[int]:
    return [statuses.count("added"), statuses.count("removed"), statuses.count("modified")]


def _object_heading(kind: str, name: str, status: str, link: str | None) -> list[str]:
    title = md_link(name, link) if link and status != "removed" else md_text(name)
    return [f"## {kind} {title}: {_STATUS_ES.get(status, status).lower()}", ""]


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return code_span(text, in_table=True) if text else ""


def _table_details(table: TableDiff) -> list[str]:
    lines: list[str] = []
    if table.column_diffs:
        rows = [[c.column_name, _ATTRIBUTE_ES[c.attribute], c.source_value, c.target_value] for c in table.column_diffs]
        lines += [
            "### Columnas",
            "",
            *md_table(["Columna", "Cambio", "Antes", "Ahora"], rows, cell_renderers=_CODE_COLS),
            "",
        ]
    if table.index_diffs:
        rows = [[i.index_name, _STATUS_ES[i.status], i.source_columns, i.target_columns] for i in table.index_diffs]
        lines += [
            "### Índices",
            "",
            *md_table(["Índice", "Estado", "Antes", "Ahora"], rows, cell_renderers=_CODE_COLS),
            "",
        ]
    if table.fk_diffs:
        rows = [
            [
                f.fk_name,
                _STATUS_ES[f.status],
                _fk_text(f.source_columns, f.source_referred_table, f.source_referred_columns),
                _fk_text(f.target_columns, f.target_referred_table, f.target_referred_columns),
            ]
            for f in table.fk_diffs
        ]
        lines += [
            "### Claves foráneas",
            "",
            *md_table(["FK", "Estado", "Antes", "Ahora"], rows, cell_renderers=_CODE_COLS),
            "",
        ]
    if table.comment_diffs:
        rows = [[c.column_name or "(tabla)", c.source_comment, c.target_comment] for c in table.comment_diffs]
        lines += ["### Comentarios", "", *md_table(["Objeto", "Antes", "Ahora"], rows), ""]
    return lines


def _fk_text(columns: str, table: str, ref_columns: str) -> str:
    return f"({columns}) → {table}({ref_columns})" if columns or table else ""


#: Columnas de las tablas de detalle que se muestran como código (nombres y valores del catálogo)
_CODE_COLS: dict[int, Any] = {0: _cell, 2: _cell, 3: _cell}


__all__: list[str] = [
    "Changes",
    "PreviousCatalog",
    "build_changes",
    "changes_json",
    "changes_page",
    "load_previous",
]
