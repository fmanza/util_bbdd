"""Precarga de metadatos de tablas para ``SchemaComparator``: una consulta por schema y tipo de objeto.

``Inspector.get_columns``/``get_pk_constraint``/``get_indexes``/``get_foreign_keys``/``get_table_comment`` hacen
una consulta por tabla. Los ``get_multi_*`` de SQLAlchemy 2.0 leen todas las tablas pedidas a la vez: en PostgreSQL y
Oracle con una consulta por schema (≈ 2,1-2,4 s → 0,06-0,09 s por lado con 200 tablas, auditoría de ``comparar``
2026-10-02); en el resto de dialects SQLAlchemy los resuelve tabla a tabla, con el mismo coste que antes.

SQL Server no tiene ``get_multi_foreign_keys`` nativo y su ``get_foreign_keys`` es la llamada más cara (≈ 17 ms por
tabla): las FKs se leen con una consulta por schema de ``metadata.sqlserver.constraints``.

Lo que no se pueda precargar (método inexistente o no soportado, error, tabla ausente del resultado) se queda fuera
del :class:`TableMetadata` y el comparador lo consulta tabla a tabla, como antes: los errores de introspección se
propagan igual que sin precarga.
"""

from __future__ import annotations

import logging

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, overload

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from util_bbdd.metadata.sqlserver.constraints import fetch_schema_fk_details_sql

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from sqlalchemy.engine import Inspector
    from sqlalchemy.engine.interfaces import (
        ReflectedColumn,
        ReflectedForeignKeyConstraint,
        ReflectedIndex,
        ReflectedPrimaryKeyConstraint,
    )

logger: logging.Logger = logging.getLogger(__name__)

type MetadataKind = Literal["columns", "pk", "indexes", "fks", "comments"]

_MULTI_METHODS: dict[MetadataKind, str] = {
    "columns": "get_multi_columns",
    "pk": "get_multi_pk_constraint",
    "indexes": "get_multi_indexes",
    "fks": "get_multi_foreign_keys",
    "comments": "get_multi_table_comment",
}


@dataclass
class TableMetadata:
    """Metadatos de las tablas de un lado de la comparación: precargados o, si no, consultados tabla a tabla."""

    inspector: Inspector
    schema: str | None
    prefetched: dict[MetadataKind, dict[str, Any]] = field(default_factory=dict)

    @overload
    def get(self, kind: Literal["columns"], table: str) -> list[ReflectedColumn]: ...
    @overload
    def get(self, kind: Literal["pk"], table: str) -> ReflectedPrimaryKeyConstraint: ...
    @overload
    def get(self, kind: Literal["indexes"], table: str) -> list[ReflectedIndex]: ...
    @overload
    def get(self, kind: Literal["fks"], table: str) -> list[ReflectedForeignKeyConstraint]: ...
    @overload
    def get(self, kind: Literal["comments"], table: str) -> str: ...

    def get(self, kind: MetadataKind, table: str) -> Any:
        """Metadatos ``kind`` de ``table`` (nombre real del motor); el comentario de tabla, como texto."""
        cached: dict[str, Any] = self.prefetched.get(kind, {})
        if table in cached:
            return cached[table]
        return _FALLBACKS[kind](self.inspector, table, self.schema)


def prefetch_table_metadata(
    inspector: Inspector,
    schema: str | None,
    names: Sequence[str],
    *,
    kinds: Iterable[MetadataKind],
) -> TableMetadata:
    """Precarga los metadatos ``kinds`` de las tablas ``names`` (nombres reales del motor) del ``schema``."""
    meta = TableMetadata(inspector, schema)
    if not names:
        return meta
    for kind in kinds:
        prefetched: dict[str, Any] | None = None
        if kind == "fks" and _dialect_name(inspector) == "mssql":
            prefetched = _mssql_foreign_keys(inspector, schema, names)
        if prefetched is None:
            prefetched = _multi(inspector, _MULTI_METHODS[kind], schema, names)
        if kind == "comments":
            prefetched = {table: _comment_text(comment) for table, comment in prefetched.items()}
        meta.prefetched[kind] = prefetched
    return meta


def _get_indexes(inspector: Inspector, table: str, schema: str | None) -> list[Any]:
    """Índices de una tabla; lista vacía si el dialect no los soporta."""
    try:
        return list(inspector.get_indexes(table, schema=schema))
    except NotImplementedError:
        return []


def _comment_text(comment: Any) -> str:
    """Texto de un ``ReflectedTableComment`` (``{"text": ...}``); cadena vacía si no hay comentario."""
    return str(comment.get("text") or "") if comment else ""


def _get_table_comment(inspector: Inspector, table: str, schema: str | None) -> str:
    """Comentario de una tabla; cadena vacía si el dialect no lo soporta."""
    try:
        return _comment_text(inspector.get_table_comment(table, schema=schema))
    except NotImplementedError:
        return ""


def _get_columns(inspector: Inspector, table: str, schema: str | None) -> list[Any]:
    return list(inspector.get_columns(table, schema=schema))


def _get_pk(inspector: Inspector, table: str, schema: str | None) -> Any:
    return inspector.get_pk_constraint(table, schema=schema)


def _get_foreign_keys(inspector: Inspector, table: str, schema: str | None) -> list[Any]:
    return list(inspector.get_foreign_keys(table, schema=schema))


#: Consulta tabla a tabla de cada tipo de metadato (lo que hacía el comparador antes de la precarga).
_FALLBACKS: dict[MetadataKind, Callable[[Inspector, str, str | None], Any]] = {
    "columns": _get_columns,
    "pk": _get_pk,
    "indexes": _get_indexes,
    "fks": _get_foreign_keys,
    "comments": _get_table_comment,
}


def _dialect_name(inspector: Inspector) -> str:
    return str(getattr(getattr(inspector, "dialect", None), "name", ""))


def _multi(inspector: Inspector, method: str, schema: str | None, names: Sequence[str]) -> dict[str, Any]:
    """``Inspector.get_multi_*`` indexado por nombre de tabla; ``{}`` si no está disponible o falla."""
    fn = getattr(inspector, method, None)
    if fn is None:
        return {}
    try:
        raw = fn(schema=schema, filter_names=list(names))
    except (NotImplementedError, SQLAlchemyError) as exc:
        logger.debug("%s no disponible (%s); se consulta tabla a tabla.", method, exc)
        return {}
    if not isinstance(raw, dict):  # Inspector simulado o incompatible
        return {}
    # Claves (schema, tabla): el schema es el pedido (None para el de por defecto); basta el nombre.
    return {key[1]: value for key, value in raw.items() if isinstance(key, tuple) and len(key) == 2}


def _mssql_foreign_keys(inspector: Inspector, schema: str | None, names: Sequence[str]) -> dict[str, Any] | None:
    """FKs de las tablas ``names`` con el formato de ``Inspector.get_foreign_keys``; ``None`` si no se pueden leer."""
    bind = getattr(inspector, "bind", None)
    if not isinstance(bind, Engine) or (schema is not None and "." in schema):
        # Un schema de varias partes ("bd.owner") no lo resuelve SCHEMA_ID: daría cero FKs sin error.
        return None
    owner: str = schema or inspector.default_schema_name or "dbo"
    try:
        with bind.connect() as conn:
            rows = conn.execute(text(fetch_schema_fk_details_sql()), {"schema": owner}).all()
    except SQLAlchemyError as exc:
        logger.debug("Consulta de FKs por schema falló (%s); se usa get_foreign_keys tabla a tabla.", exc)
        return None

    result: dict[str, list[dict[str, Any]]] = {name: [] for name in names}
    by_name: dict[tuple[str, str], dict[str, Any]] = {}
    for table, fk_name, column, ref_schema, ref_table, ref_column, on_delete, on_update in rows:
        if table not in result:
            continue
        fk = by_name.get((table, fk_name))
        if fk is None:
            fk = {
                "name": fk_name,
                "constrained_columns": [],
                # Como MSDialect.get_foreign_keys: None si se pidió el schema por defecto y la FK no sale de él
                "referred_schema": ref_schema if schema is not None or ref_schema != owner else None,
                "referred_table": ref_table,
                "referred_columns": [],
                "options": _mssql_fk_options(on_delete, on_update),
            }
            by_name[(table, fk_name)] = fk
            result[table].append(fk)
        fk["constrained_columns"].append(column)
        fk["referred_columns"].append(ref_column)
    return result


def _mssql_fk_options(on_delete: str | None, on_update: str | None) -> dict[str, str]:
    """``options`` como las da SQLAlchemy: solo las acciones distintas de ``NO ACTION`` (``SET_NULL`` → ``SET NULL``)."""
    options: dict[str, str] = {}
    for key, action in (("onupdate", on_update), ("ondelete", on_delete)):
        rule = (action or "NO_ACTION").replace("_", " ")
        if rule != "NO ACTION":
            options[key] = rule
    return options
