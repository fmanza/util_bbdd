"""Modelo neutro de metadatos de un schema (ADR-003).

Tipos inmutables (``frozen``, ``slots``) e independientes del motor: los produce el ``CatalogDialect`` de cada motor
a partir de su catálogo y los consumen managers, ``doc``, ``analysis``, ``migrate``, ``dump``, ``bulk`` y ``comparar``.

Un :class:`SchemaSnapshot` contiene solo los tipos de objeto (:class:`Kind`) que se pidieron: pedir uno que no se cargó
es un error explícito (:class:`KindNotLoadedError`), nunca una lista vacía silenciosa. Los nombres se guardan tal como
los devuelve el motor; las búsquedas por tabla aceptan otra capitalización si no hay ambigüedad.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .._core.exceptions import MetadataError


class Kind(StrEnum):
    """Tipo de objeto del catálogo que se lee con una consulta por schema."""

    TABLES = "tables"
    VIEWS = "views"
    COLUMNS = "columns"
    PRIMARY_KEYS = "primary_keys"
    UNIQUES = "uniques"
    CHECKS = "checks"
    FOREIGN_KEYS = "foreign_keys"
    INDEXES = "indexes"
    IDENTITY = "identity"
    ROUTINES = "routines"
    ROUTINE_PARAMETERS = "routine_parameters"
    DATABASE = "database"


ALL_KINDS: frozenset[Kind] = frozenset(Kind)

#: Tipos de objeto que pertenecen a una tabla (o vista) y admiten filtrar la lectura por nombre de tabla.
TABLE_SCOPED_KINDS: frozenset[Kind] = frozenset(
    {
        Kind.TABLES,
        Kind.VIEWS,
        Kind.COLUMNS,
        Kind.PRIMARY_KEYS,
        Kind.UNIQUES,
        Kind.CHECKS,
        Kind.FOREIGN_KEYS,
        Kind.INDEXES,
        Kind.IDENTITY,
    }
)


class KindNotLoadedError(MetadataError):
    """Se pidió al snapshot un tipo de objeto que no se cargó (``snapshot(kinds=...)``)."""


@dataclass(frozen=True, slots=True)
class TableMeta:
    """Tabla del schema; ``collation`` es la de la tabla donde el motor la tiene por tabla (MySQL/MariaDB)."""

    name: str
    comment: str | None = None
    collation: str | None = None


@dataclass(frozen=True, slots=True)
class ViewMeta:
    """Vista del schema con su definición tal como la guarda el motor.

    ``definition`` es el ``SELECT`` en PostgreSQL, Oracle y MySQL/MariaDB, y la sentencia ``CREATE VIEW`` completa en
    SQL Server y SQLite; ``None`` si el motor no la expone (permisos, vistas cifradas). En PostgreSQL,
    ``pg_get_viewdef`` omite el schema de las tablas que están en el ``search_path`` de la sesión: la misma vista puede
    leerse con o sin nombres calificados según la conexión.
    """

    name: str
    definition: str | None = None
    comment: str | None = None
    materialized: bool = False


@dataclass(frozen=True, slots=True)
class ColumnMeta:
    """Columna de una tabla o vista.

    Attributes:
        table: Tabla o vista a la que pertenece.
        data_type: Tipo completo como lo escribe el motor (``character varying(50)``, ``numeric(12,2)``).
        base_type: Tipo sin modificadores con el nombre de ``information_schema.columns.data_type`` donde el motor
            lo tiene (``character varying``, ``numeric``; en PostgreSQL ``ARRAY``/``USER-DEFINED`` y el tipo base de
            los dominios; en SQL Server el tipo de sistema de los tipos alias; en Oracle ``TIMESTAMP WITH TIME ZONE``).
        length: Longitud en caracteres de los tipos de texto con longitud declarada (en bits en ``bit(n)`` de
            PostgreSQL).
        precision: Precisión declarada de los tipos numéricos exactos.
        scale: Escala declarada de los tipos numéricos exactos.
        default: Expresión SQL por defecto tal como la devuelve el catálogo (en MySQL, los literales entre comillas
            como en el resto de motores).
        identity: ``"always"``/``"by default"`` en columnas identidad; ``None`` en el resto.
        generated: Expresión de las columnas calculadas; ``None`` en el resto.
        on_update: Expresión ``ON UPDATE`` de la columna (solo MySQL/MariaDB, p.ej. ``current_timestamp()``).
    """

    table: str
    name: str
    ordinal: int
    data_type: str
    base_type: str
    nullable: bool
    length: int | None = None
    precision: int | None = None
    scale: int | None = None
    default: str | None = None
    comment: str | None = None
    collation: str | None = None
    identity: str | None = None
    generated: str | None = None
    on_update: str | None = None


@dataclass(frozen=True, slots=True)
class PrimaryKeyMeta:
    """Clave primaria de una tabla (columnas en orden de la clave)."""

    table: str
    name: str
    columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UniqueMeta:
    """Restricción ``UNIQUE`` (no incluye los índices únicos sin restricción: ver :class:`IndexMeta`)."""

    table: str
    name: str
    columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CheckMeta:
    """Restricción ``CHECK``."""

    table: str
    name: str
    expression: str


@dataclass(frozen=True, slots=True)
class ForeignKeyMeta:
    """Clave foránea; ``on_delete``/``on_update`` con el nombre SQL de la regla (``NO ACTION``, ``CASCADE``…)."""

    table: str
    name: str
    columns: tuple[str, ...]
    ref_schema: str
    ref_table: str
    ref_columns: tuple[str, ...]
    on_delete: str = "NO ACTION"
    on_update: str = "NO ACTION"


@dataclass(frozen=True, slots=True)
class IndexMeta:
    """Índice; ``columns`` contiene nombres de columna o expresiones (índices funcionales)."""

    table: str
    name: str
    columns: tuple[str, ...]
    unique: bool
    primary: bool = False
    method: str | None = None
    predicate: str | None = None


@dataclass(frozen=True, slots=True)
class IdentityMeta:
    """Generador de valores de una columna: identidad o secuencia asociada (``serial``)."""

    table: str
    column: str
    kind: str  # "identity" | "sequence"
    sequence: str | None = None
    sequence_schema: str | None = None


@dataclass(frozen=True, slots=True)
class RoutineKey:
    """Identifica una routine aunque haya sobrecargas: nombre + firma de argumentos (vacía si el motor no tiene)."""

    name: str
    signature: str = ""


@dataclass(frozen=True, slots=True)
class RoutineMeta:
    """Función o procedure del schema con su definición completa (``CREATE …``) si el motor la expone."""

    name: str
    routine_type: str  # "FUNCTION" | "PROCEDURE" | "PACKAGE" (Oracle, sin definición)
    signature: str = ""
    return_type: str | None = None
    definition: str | None = None
    comment: str | None = None
    language: str | None = None

    @property
    def key(self) -> RoutineKey:
        return RoutineKey(self.name, self.signature)


@dataclass(frozen=True, slots=True)
class RoutineParameterMeta:
    """Parámetro de una routine (``mode``: ``IN``/``OUT``/``INOUT``/``VARIADIC``/``TABLE``)."""

    routine: RoutineKey
    ordinal: int
    name: str | None
    mode: str
    data_type: str
    default: str | None = None


@dataclass(frozen=True, slots=True)
class DatabaseMeta:
    """Información de la base de datos: versión del servidor, juego de caracteres y collation por defecto."""

    version: str
    charset: str | None = None
    collation: str | None = None


def _group(items: Iterable[Any], attr: str) -> dict[str, tuple[Any, ...]]:
    grouped: dict[str, list[Any]] = {}
    for item in items:
        grouped.setdefault(getattr(item, attr), []).append(item)
    return {key: tuple(values) for key, values in grouped.items()}


@dataclass(frozen=True)
class SchemaSnapshot:
    """Metadatos de un schema leídos con una consulta por tipo de objeto.

    Attributes:
        engine: ``db_type`` de la librería (``postgresql``, ``oracle``…).
        schema: Schema, owner o base de datos leído.
        loaded: Tipos de objeto cargados; los demás lanzan :class:`KindNotLoadedError`.
        tables_filter: Si la lectura se limitó a unas tablas, cuáles (``None`` = schema completo).

    Example:
        >>> snapshot = source.snapshot("ventas", kinds={Kind.TABLES, Kind.COLUMNS})
        >>> [c.name for c in snapshot.columns("clientes")]
        ['id', 'nombre']
    """

    engine: str
    schema: str
    data: Mapping[Kind, tuple[Any, ...]]
    tables_filter: frozenset[str] | None = None
    _by_table: dict[Kind, dict[str, tuple[Any, ...]]] = field(default_factory=dict, init=False, repr=False)
    _folded: dict[Kind, dict[str, str]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        for kind, items in self.data.items():
            if kind in TABLE_SCOPED_KINDS and kind not in (Kind.TABLES, Kind.VIEWS):
                grouped = _group(items, "table")
                self._by_table[kind] = grouped
                folded: dict[str, str] = {}
                for name in grouped:
                    folded.setdefault(name.casefold(), name)
                    if folded[name.casefold()] != name:
                        folded[name.casefold()] = ""  # ambiguo: solo búsqueda exacta
                self._folded[kind] = folded

    @property
    def loaded(self) -> frozenset[Kind]:
        return frozenset(self.data)

    def _all(self, kind: Kind) -> tuple[Any, ...]:
        if kind not in self.data:
            raise KindNotLoadedError(
                f"El snapshot de '{self.schema}' no cargó '{kind.value}' (kinds={sorted(self.data)})"
            )
        return self.data[kind]

    def _for_table(self, kind: Kind, table: str) -> tuple[Any, ...]:
        self._all(kind)
        grouped = self._by_table[kind]
        if table in grouped:
            return grouped[table]
        exact = self._folded[kind].get(table.casefold())
        return grouped[exact] if exact else ()

    # ── listados del schema ──────────────────────────────────────────────────
    def tables(self) -> tuple[TableMeta, ...]:
        return self._all(Kind.TABLES)

    def views(self) -> tuple[ViewMeta, ...]:
        return self._all(Kind.VIEWS)

    def routines(self) -> tuple[RoutineMeta, ...]:
        return self._all(Kind.ROUTINES)

    def database(self) -> DatabaseMeta | None:
        items = self._all(Kind.DATABASE)
        return items[0] if items else None

    def all_foreign_keys(self) -> tuple[ForeignKeyMeta, ...]:
        return self._all(Kind.FOREIGN_KEYS)

    # ── por tabla ────────────────────────────────────────────────────────────
    def columns(self, table: str) -> tuple[ColumnMeta, ...]:
        return self._for_table(Kind.COLUMNS, table)

    def primary_key(self, table: str) -> PrimaryKeyMeta | None:
        items = self._for_table(Kind.PRIMARY_KEYS, table)
        return items[0] if items else None

    def uniques(self, table: str) -> tuple[UniqueMeta, ...]:
        return self._for_table(Kind.UNIQUES, table)

    def checks(self, table: str) -> tuple[CheckMeta, ...]:
        return self._for_table(Kind.CHECKS, table)

    def foreign_keys(self, table: str) -> tuple[ForeignKeyMeta, ...]:
        return self._for_table(Kind.FOREIGN_KEYS, table)

    def indexes(self, table: str) -> tuple[IndexMeta, ...]:
        return self._for_table(Kind.INDEXES, table)

    def identity(self, table: str) -> tuple[IdentityMeta, ...]:
        return self._for_table(Kind.IDENTITY, table)

    def routine_parameters(self, routine: RoutineKey) -> tuple[RoutineParameterMeta, ...]:
        return tuple(p for p in self._all(Kind.ROUTINE_PARAMETERS) if p.routine == routine)


__all__: list[str] = [
    "ALL_KINDS",
    "TABLE_SCOPED_KINDS",
    "CheckMeta",
    "ColumnMeta",
    "DatabaseMeta",
    "ForeignKeyMeta",
    "IdentityMeta",
    "IndexMeta",
    "Kind",
    "KindNotLoadedError",
    "PrimaryKeyMeta",
    "RoutineKey",
    "RoutineMeta",
    "RoutineParameterMeta",
    "SchemaSnapshot",
    "TableMeta",
    "UniqueMeta",
    "ViewMeta",
]
