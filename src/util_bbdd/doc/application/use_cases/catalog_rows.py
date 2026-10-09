"""Filas que muestra la documentación, iguales para todos los motores, desde el snapshot de ``metadata/`` (D1, ADR-003).

Antes cada renderer leía por posición las tuplas de ``get_columns``/``get_foreign_keys``/… del manager, con forma
distinta por motor (MySQL con ``Clave``/``Extra``, Oracle con ``DATA_LENGTH``, SQLite la suya…) y cabeceras por motor
que no siempre casaban con los datos. Ahora la documentación lee el schema por lotes (una consulta por tipo de objeto,
no por tabla) y presenta lo mismo en todos los motores. Formas (texto, ``""`` si no hay valor):

- tablas ``(nombre, comentario, collation)`` · vistas ``(nombre, comentario)`` · routines ``(nombre, tipo, comentario)``
  (una sobrecarga se nombra con su firma: ``f(a integer)``);
- columnas ``(campo, tipo declarado, nulo YES/NO, por defecto, generación, comentario)``; la generación es
  ``IDENTITY (ALWAYS|BY DEFAULT)`` o ``CALCULADA: <expresión>``;
- PK ``(columna,)`` · FK ``(restricción, columna, tabla ref., columna ref., ON DELETE, ON UPDATE)`` por par de
  columnas · UNIQUE ``(restricción, columna)`` · índices ``(índice, columna o expresión, Sí/No, método)``;
- parámetros ``(modo, nombre, tipo, por defecto, posición)``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from typing import Any

from ....metadata.model import ColumnMeta, Kind, RoutineMeta, SchemaSnapshot, ViewMeta

Row = tuple[Any, ...]

#: Lo que lee la documentación del catálogo; cada tipo se carga la primera vez que se pide.
DOC_KINDS: frozenset[Kind] = frozenset(
    {
        Kind.TABLES,
        Kind.VIEWS,
        Kind.COLUMNS,
        Kind.PRIMARY_KEYS,
        Kind.FOREIGN_KEYS,
        Kind.UNIQUES,
        Kind.INDEXES,
        Kind.ROUTINES,
        Kind.ROUTINE_PARAMETERS,
    }
)


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _generation(column: ColumnMeta) -> str:
    if column.identity:
        return f"IDENTITY ({column.identity.upper()})"
    if column.generated:
        return f"CALCULADA: {column.generated}"
    return ""


class CatalogRows:
    """Filas neutras de la documentación sobre un lector de snapshots por tipo de objeto.

    Args:
        load: ``load(kinds) -> SchemaSnapshot`` (p. ej. ``manager.get_schema_metadata``); se llama una vez por tipo.
    """

    def __init__(self, load: Callable[[frozenset[Kind]], SchemaSnapshot]) -> None:
        self._load = load
        self._snapshots: dict[Kind, SchemaSnapshot] = {}
        self._routine_names: dict[tuple[str, str], list[RoutineMeta]] | None = None
        self._views_by_name: dict[str, ViewMeta] | None = None

    def _snapshot(self, kind: Kind) -> SchemaSnapshot:
        if kind not in self._snapshots:
            self._snapshots[kind] = self._load(frozenset({kind}))
        return self._snapshots[kind]

    # ── inventario ───────────────────────────────────────────────────────────
    def tables(self) -> list[Row]:
        return [(t.name, _text(t.comment), _text(t.collation)) for t in self._snapshot(Kind.TABLES).tables()]

    def views(self) -> list[Row]:
        return [(v.name, _text(v.comment)) for v in self._snapshot(Kind.VIEWS).views() if not v.materialized]

    def routines(self) -> list[Row]:
        return [(name, kind, _text(r.comment)) for (name, kind), group in self._routines().items() for r in group[:1]]

    def _routines(self) -> dict[tuple[str, str], list[RoutineMeta]]:
        """``{(nombre mostrado, tipo): [routine]}``; las sobrecargas se nombran con su firma."""
        if self._routine_names is None:
            routines = [
                r for r in self._snapshot(Kind.ROUTINES).routines() if r.routine_type in ("FUNCTION", "PROCEDURE")
            ]
            overloads = Counter((r.name, r.routine_type) for r in routines)
            self._routine_names = {}
            for r in routines:
                shown = f"{r.name}({r.signature})" if overloads[(r.name, r.routine_type)] > 1 else r.name
                self._routine_names.setdefault((shown, r.routine_type), []).append(r)
        return self._routine_names

    def _routine(self, name: str, routine_type: str) -> RoutineMeta | None:
        found = self._routines().get((name, routine_type.upper()))
        return found[0] if found else None

    # ── tablas y vistas ──────────────────────────────────────────────────────
    def columns(self, table: str) -> list[Row]:
        return [
            (
                c.name,
                c.data_type,
                "YES" if c.nullable else "NO",
                "" if c.identity else _text(c.default),
                _generation(c),
                _text(c.comment),
            )  # fmt: skip
            for c in self._snapshot(Kind.COLUMNS).columns(table)
        ]

    def primary_keys(self, table: str) -> list[Row]:
        pk = self._snapshot(Kind.PRIMARY_KEYS).primary_key(table)
        return [(column,) for column in pk.columns] if pk else []

    def foreign_keys(self, table: str) -> list[Row]:
        return [
            (fk.name, column, fk.ref_table, ref_column, fk.on_delete, fk.on_update)
            for fk in self._snapshot(Kind.FOREIGN_KEYS).foreign_keys(table)
            for column, ref_column in zip(fk.columns, fk.ref_columns, strict=False)
        ]

    def unique_constraints(self, table: str) -> list[Row]:
        return [(u.name, column) for u in self._snapshot(Kind.UNIQUES).uniques(table) for column in u.columns]

    def indices(self, table: str) -> list[Row]:
        return [
            (index.name, column, "Sí" if index.unique else "No", _text(index.method))
            for index in self._snapshot(Kind.INDEXES).indexes(table)
            for column in index.columns
        ]

    def view_ddl(self, view: str) -> str:
        if self._views_by_name is None:  # P-03: un índice en lugar de recorrer todas las vistas en cada vista
            self._views_by_name = {}
            for item in self._snapshot(Kind.VIEWS).views():
                self._views_by_name.setdefault(item.name.casefold(), item)
        found = self._views_by_name.get(view.casefold())
        definition = _text(found.definition if found else None).strip()
        if not definition or definition[:6].upper() == "CREATE":
            return definition
        return f"CREATE VIEW {found.name if found else view} AS\n{definition}"

    # ── routines ─────────────────────────────────────────────────────────────
    def routine_ddl(self, name: str, routine_type: str) -> str:
        routine = self._routine(name, routine_type)
        return _text(routine.definition if routine else None).strip()

    def routine_parameters(self, name: str, routine_type: str) -> list[Row]:
        routine = self._routine(name, routine_type)
        if routine is None:
            return []
        return [
            (p.mode, _text(p.name), p.data_type, _text(p.default), p.ordinal)
            for p in self._snapshot(Kind.ROUTINE_PARAMETERS).routine_parameters(routine.key)
        ]


__all__: list[str] = ["DOC_KINDS", "CatalogRows"]
