"""Serialización de ``MigrationPlan`` (``to_dict``/``from_dict``, G26 de util_bbdd_web).

El plan se guarda como su IR (tablas, vistas, rutinas y avisos) más las opciones de su emitter, que se deduce de
``target_engine``. ``statements_sha256`` es el SHA-256 de ``emit_statements()``: al reconstruir se vuelve a emitir y,
si el hash no coincide (otra versión de util_bbdd emite otro DDL), el plan no se acepta. Así se ejecuta exactamente lo
que se revisó.
"""

from __future__ import annotations

import hashlib
import types
import typing

from collections.abc import Mapping
from dataclasses import MISSING, fields, is_dataclass
from typing import TYPE_CHECKING, Any, Literal

from ..._core.exceptions import MigrationPlanValidationError
from .models import CanonicalRoutine, CanonicalTable, CanonicalView, MigrationWarning

if TYPE_CHECKING:
    from .models import MigrationPlan

#: Opción del constructor del emitter → atributo donde la guarda, por motor destino.
_EMITTER_OPTIONS: dict[str, dict[str, str]] = {
    "mariadb": {"charset": "_charset", "collation": "_collation", "engine": "_engine"},
    "mysql": {"charset": "_charset", "collation": "_collation", "engine": "_engine"},
    "sqlserver": {"collation": "_collation"},
    "postgresql": {"pg_schema": "_pg_schema"},
    "oracle": {"oracle_identity_mode": "_identity_mode"},
}


def _emitter_class(target_engine: str) -> type:
    from ..emitters.mariadb import MariaDBDDLEmitter
    from ..emitters.mysql import MySQLDDLEmitter
    from ..emitters.oracle import OracleDDLEmitter
    from ..emitters.postgresql import PostgreSQLDDLEmitter
    from ..emitters.sqlserver import SQLServerDDLEmitter

    classes: dict[str, type] = {
        "mariadb": MariaDBDDLEmitter,
        "mysql": MySQLDDLEmitter,
        "sqlserver": SQLServerDDLEmitter,
        "postgresql": PostgreSQLDDLEmitter,
        "oracle": OracleDDLEmitter,
    }
    return classes[target_engine]


def statements_sha256(statements: list[str]) -> str:
    """SHA-256 de las sentencias, separadas por un NUL (no aparece en SQL)."""
    return hashlib.sha256("\x00".join(statements).encode("utf-8")).hexdigest()


def _dump(obj: Any) -> Any:
    """Dataclasses, listas y tuplas como tipos JSON."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _dump(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, list | tuple):
        return [_dump(item) for item in obj]
    return obj


def dump_plan(plan: MigrationPlan, format_name: str, format_version: int) -> dict[str, Any]:
    """Cuerpo de :meth:`MigrationPlan.to_dict`."""
    options = _EMITTER_OPTIONS.get(plan.target_engine)
    if options is None or type(plan.emitter) is not _emitter_class(plan.target_engine):
        raise TypeError(
            f"MigrationPlan.to_dict solo serializa el emitter de util_bbdd de su destino; "
            f"{type(plan.emitter).__name__} con target_engine={plan.target_engine!r} no lo es"
        )
    statements = plan.emit_statements()  # antes de leer los avisos: incluye los que descubre la emisión
    return {
        "format": format_name,
        "format_version": format_version,
        "source_engine": plan.source_engine,
        "target_engine": plan.target_engine,
        "source_schema": plan.source_schema,
        "emitter": {option: getattr(plan.emitter, attribute) for option, attribute in options.items()},
        "tables": _dump(plan.tables),
        "views": _dump(plan.views),
        "routines": _dump(plan.routines),
        "warnings": _dump(plan.warnings),
        "statements_sha256": statements_sha256(statements),
    }


def _load[T](cls: type[T], data: Any, where: str) -> T:
    """Construye la dataclass ``cls`` desde ``data`` validando presencia y tipo de cada campo."""
    if not isinstance(data, Mapping):
        raise MigrationPlanValidationError(f"{where}: se espera un objeto, no {type(data).__name__}")
    hints = typing.get_type_hints(cls)
    kwargs: dict[str, Any] = {}
    for f in fields(cls):  # type: ignore[arg-type]
        if f.name not in data:
            if f.default is MISSING and f.default_factory is MISSING:
                raise MigrationPlanValidationError(f"{where}.{f.name}: campo obligatorio ausente")
            continue
        kwargs[f.name] = _load_value(hints[f.name], data[f.name], f"{where}.{f.name}")
    return cls(**kwargs)


def _load_value(hint: Any, value: Any, where: str) -> Any:
    """Valida ``value`` contra la anotación ``hint`` y convierte listas y dataclasses anidadas."""
    origin = typing.get_origin(hint)
    args = typing.get_args(hint)
    if origin in (types.UnionType, typing.Union):
        if value is None and type(None) in args:
            return None
        arms = [arm for arm in args if arm is not type(None)]
        return _load_value(arms[0], value, where)
    if origin is Literal:
        if value not in args:
            raise MigrationPlanValidationError(f"{where}: {value!r} no es uno de {list(args)}")
        return value
    if origin in (list, tuple):
        if not isinstance(value, list | tuple):
            raise MigrationPlanValidationError(f"{where}: se espera una lista, no {type(value).__name__}")
        items = [_load_value(args[0], item, f"{where}[{i}]") for i, item in enumerate(value)]
        return items if origin is list else tuple(items)
    if is_dataclass(hint):
        return _load(hint, value, where)  # type: ignore[arg-type]
    if type(value) is not hint:
        raise MigrationPlanValidationError(f"{where}: se espera {hint.__name__}, no {type(value).__name__}")
    return value


def load_plan[P: MigrationPlan](cls: type[P], data: Any, format_name: str, format_version: int) -> P:
    """Cuerpo de :meth:`MigrationPlan.from_dict`."""
    if not isinstance(data, Mapping):
        raise MigrationPlanValidationError(f"MigrationPlan.from_dict espera un dict, no {type(data).__name__}")
    if data.get("format") != format_name:
        raise MigrationPlanValidationError(
            f"No es un MigrationPlan serializado: format={data.get('format')!r} (se espera {format_name!r})"
        )
    version = data.get("format_version")
    if version != format_version:
        raise MigrationPlanValidationError(
            f"format_version {version!r} de MigrationPlan no soportada: esta versión de util_bbdd lee la {format_version}"
        )
    for key in ("source_engine", "target_engine", "source_schema", "statements_sha256"):
        if not isinstance(data.get(key), str):
            raise MigrationPlanValidationError(f"{key}: se espera un texto, no {type(data.get(key)).__name__}")
    target_engine: str = data["target_engine"]
    if target_engine not in _EMITTER_OPTIONS:
        raise MigrationPlanValidationError(f"target_engine: {target_engine!r} no es uno de {sorted(_EMITTER_OPTIONS)}")
    options = data.get("emitter")
    if not isinstance(options, Mapping) or set(options) != set(_EMITTER_OPTIONS[target_engine]):
        raise MigrationPlanValidationError(
            f"emitter: se esperan las opciones {sorted(_EMITTER_OPTIONS[target_engine])} del destino {target_engine}"
        )
    try:
        emitter = _emitter_class(target_engine)(**options)
    except (TypeError, ValueError) as exc:
        raise MigrationPlanValidationError(f"emitter: {exc}") from exc
    plan = cls(
        tables=_load_value(list[CanonicalTable], data.get("tables"), "tables"),
        warnings=_load_value(list[MigrationWarning], data.get("warnings"), "warnings"),
        source_schema=data["source_schema"],
        source_engine=data["source_engine"],
        target_engine=target_engine,
        emitter=emitter,
        views=_load_value(list[CanonicalView], data.get("views", []), "views"),
        routines=_load_value(list[CanonicalRoutine], data.get("routines", []), "routines"),
    )
    current = plan.statements_sha256()
    if current != data["statements_sha256"]:
        raise MigrationPlanValidationError(
            f"El plan reconstruido no emite las mismas sentencias (statements_sha256 {current} en lugar de "
            f"{data['statements_sha256']}): se guardó con otra versión de util_bbdd o se modificó. Vuelve a planificar."
        )
    return plan


__all__: list[str] = ["dump_plan", "load_plan", "statements_sha256"]
