"""Transpilado de vistas entre motores con sqlglot (V1, sesión 2026-09-29c-migrate-views).

Para cada vista: analiza el SQL en el dialecto origen; convierte ``(+)``, ``ROWNUM`` y las jerarquías simples
``CONNECT BY`` de Oracle (CTE recursiva, V4); si quedan construcciones sin traducción fiable o no se puede analizar o
generar, la emite sin reescribir (*pass-through*) con un aviso ``WARNING``. Si no, corrige los artefactos del texto de catálogo, resuelve y anota tipos con el esquema del plan,
hace explícita la aritmética que depende del tipo, recoloca nombres (tablas, vistas y columnas del plan con el nombre
y las comillas del destino; sin el esquema origen) y genera el SQL del destino. Detalle y evidencias:
``.ai/sessions/2026-09-29c-migrate-views/v0/V0_SPIKE.md``.
"""

from __future__ import annotations

import re

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

import sqlglot

from sqlglot import exp
from sqlglot.errors import ErrorLevel
from sqlglot.optimizer.annotate_types import annotate_types
from sqlglot.optimizer.qualify import qualify

from ..ir.models import CanonicalView, MigrationWarning, WarningCode
from . import _rewrites
from ._dialects import SQLGLOT_DIALECT
from ._rewrites import ConnectByOutcome

#: Identificador válido sin comillas en los 5 motores (Oracle no admite empezar por dígito ni por ``_``).
_SIMPLE_IDENTIFIER: re.Pattern[str] = re.compile(r"^[A-Za-z]\w*$", re.ASCII)  # ASCII: sin él, \w admite letras Unicode

_ENGINE_LABEL: dict[str, str] = {
    "mysql": "MySQL",
    "mariadb": "MariaDB",
    "postgresql": "PostgreSQL",
    "sqlserver": "SQL Server",
    "oracle": "Oracle",
}


@dataclass(frozen=True)
class ViewTranspileContext:
    """Lo que el transpilador necesita del plan.

    Attributes:
        source_engine: Motor origen (``"mysql"``, ``"mariadb"``, ``"postgresql"``, ``"sqlserver"``, ``"oracle"``).
        target_engine: Motor destino.
        source_schema: Schema origen migrado (sus referencias explícitas se quitan).
        object_names: Nombre origen en minúsculas → nombre destino, de tablas y vistas del plan.
        column_names: Nombre de columna origen en minúsculas → nombre destino (solo los no ambiguos entre tablas).
        column_types: Tabla origen → columna → tipo origen, para resolver y anotar tipos.
        integer_columns: Tabla origen → columnas enteras (escala 0), para aceptar ``SYS_CONNECT_BY_PATH`` sobre ellas.
    """

    source_engine: str
    target_engine: str
    source_schema: str
    object_names: dict[str, str] = field(default_factory=dict)
    column_names: dict[str, str] = field(default_factory=dict)
    column_types: dict[str, dict[str, str]] = field(default_factory=dict)
    integer_columns: dict[str, frozenset[str]] = field(default_factory=dict)


def _warning(
    view: CanonicalView, code: WarningCode, target_type: str, message: str, severity: str = "WARNING"
) -> MigrationWarning:
    return MigrationWarning(
        table=view.name,
        column=None,
        category="VIEW",
        target_type=target_type,
        message=message,
        severity=severity,  # type: ignore[arg-type]
        code=code,
    )


def _passthrough(view: CanonicalView, reason: str) -> CanonicalView:
    result = deepcopy(view)
    result.warnings.append(
        _warning(
            view,
            "VIEW_NOT_REWRITTEN",
            "VIEW (sin reescribir)",
            f"Vista emitida sin reescribir el SQL ({reason}); revisar manualmente su compatibilidad con el destino",
        )
    )
    return result


def _schema_for_sqlglot(ctx: ViewTranspileContext, dialect: str) -> dict[str, object]:
    """Esquema de tipos para sqlglot; los tipos que no sabe interpretar se omiten (quedan como desconocidos)."""
    schema: dict[str, object] = {}
    for table, columns in ctx.column_types.items():
        parsed: dict[str, str] = {}
        for column, type_name in columns.items():
            try:
                parsed[column] = exp.DataType.build(type_name, dialect=dialect).sql(dialect=dialect)
            except Exception:  # noqa: BLE001 - tipo propio del motor que sqlglot no reconoce
                continue
        if parsed:
            schema[table] = parsed
    return schema


def _external_tables(tree: exp.Expr, ctx: ViewTranspileContext) -> list[str]:
    """Tablas referenciadas de otro schema o que no están en el plan (se dejan como están)."""
    external: list[str] = []
    source_schema = ctx.source_schema.lower()
    ctes = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        if name in ctes or name == "dual":
            continue
        db = table.args.get("db")
        if (db is not None and db.name.lower() != source_schema) or name not in ctx.object_names:
            external.append(table.sql())
    return external


def _apply_names(tree: exp.Expr, ctx: ViewTranspileContext) -> None:
    """Nombres del destino: objetos y columnas del plan con su nombre y comillas; el resto sin comillas.

    Los emitters crean tablas y columnas entrecomilladas con el nombre del plan (Oracle en mayúsculas), así que las
    referencias se entrecomillan igual. Alias, CTE y demás identificadores se dejan sin comillas: cada motor los
    resuelve con su regla de mayúsculas, igual en la definición que en el uso.
    """
    upper = ctx.target_engine == "oracle"
    source_schema = ctx.source_schema.lower()
    table_idents = _apply_table_names(tree, ctx, source_schema, upper)
    for column in tree.find_all(exp.Column):
        db = column.args.get("db")
        if db is not None and db.name.lower() == source_schema:
            column.set("db", None)
            column.set("catalog", None)
    _apply_column_names(tree, ctx, table_idents, upper)


def _apply_table_names(tree: exp.Expr, ctx: ViewTranspileContext, source_schema: str, upper: bool) -> set[int]:
    """Tablas: sin el schema origen; las del plan con su nombre entrecomillado. Devuelve los ``id`` de sus
    identificadores, para que :func:`_apply_column_names` no los trate como columnas."""
    table_idents: set[int] = set()
    for table in tree.find_all(exp.Table):
        db = table.args.get("db")
        if db is None or db.name.lower() == source_schema:
            table.set("db", None)
            table.set("catalog", None)
        ident = table.this
        if not isinstance(ident, exp.Identifier):
            continue
        table_idents.add(id(ident))
        target = ctx.object_names.get(ident.name.lower())
        if target is not None:
            ident.set("this", target.upper() if upper else target)
        ident.set("quoted", target is not None)
    return table_idents


def _apply_column_names(tree: exp.Expr, ctx: ViewTranspileContext, table_idents: set[int], upper: bool) -> None:
    """Columnas del plan (referencia o alias) con su nombre entrecomillado; el resto, sin comillas si se puede."""
    for ident in tree.find_all(exp.Identifier):
        if id(ident) in table_idents:
            continue
        target = ctx.column_names.get(ident.name.lower())
        if (
            target is not None
            and isinstance(ident.parent, (exp.Column, exp.Alias))
            and ident.arg_key in ("this", "alias")
        ):
            ident.set("this", target.upper() if upper else target)
            ident.set("quoted", True)
        else:
            # Alias generados (``SELECT 1 AS 1``, ``_col_0``) solo son válidos entrecomillados en algunos motores.
            ident.set("quoted", not _SIMPLE_IDENTIFIER.match(ident.name))


_HEADER_COLUMNS_CODE: WarningCode = "VIEW_HEADER_COLUMNS"


def _apply_header_columns(tree: exp.Expr, view: CanonicalView) -> bool:
    """Nombres declarados en la cabecera de la vista (``CREATE VIEW v (a, b) AS ...``, SQL Server) como alias.

    ``view.columns`` trae esos nombres (``INFORMATION_SCHEMA.COLUMNS`` de la vista). Solo se aplican si la consulta
    tiene exactamente tantas columnas como nombres; en una unión, en la primera rama (la que da nombre a la vista).
    """
    select: Any = tree
    while isinstance(select, exp.SetOperation):
        select = select.this
    if not isinstance(select, exp.Select) or len(select.expressions) != len(view.columns):
        return False
    for projection, name in zip(list(select.expressions), view.columns, strict=True):
        if projection.alias_or_name != name:
            base = projection.this if isinstance(projection, exp.Alias) else projection
            projection.replace(exp.alias_(base.copy(), name))
    return True


def _hierarchy_message(target_engine: str, *, nocycle: bool = False, siblings: bool = False) -> str:
    """Aviso de una jerarquía CONNECT BY convertida en CTE recursiva: límite de recursión, ciclos y orden."""
    label = _ENGINE_LABEL.get(target_engine, target_engine)
    limit = _rewrites.CONNECT_BY_RECURSION_LIMIT.get(target_engine)
    if nocycle:
        path = "un array" if target_engine == "postgresql" else "un texto separado por CHAR(31), comparado en binario,"
        depth = (
            f"NOCYCLE se traduce con {path} de los valores de la columna de PRIOR en el camino: la fila que cerraría un "
            "ciclo no sale y su padre cuenta como hoja, como en Oracle, si esa columna identifica la fila"
        )
        if limit is not None:
            depth += f"; {label} corta la CTE recursiva a los {limit} niveles y una vista no puede ampliarlo"
    elif limit is not None:
        depth = (
            f"{label} corta la CTE recursiva a los {limit} niveles y una vista no puede ampliarlo; una jerarquía más "
            "profunda o un ciclo en los datos dan error al consultar la vista"
        )
    else:
        depth = (
            f"{label} no limita la CTE recursiva: un ciclo en los datos (que Oracle rechaza con ORA-01436) hace que la "
            "consulta no termine"
        )
    if not siblings:
        order = "Sin ORDER BY, el orden en profundidad de Oracle no se conserva"
    elif target_engine == "sqlserver":
        order = (
            f"{label} no admite ORDER BY en una vista: el orden de ORDER SIBLINGS BY no se conserva (las filas son las "
            "mismas; ordenar al consultar la vista)"
        )
    else:
        order = "ORDER SIBLINGS BY se conserva con una ruta de orden por niveles (cb_order)"
    return f"CONNECT BY convertido en CTE recursiva; {depth}. {order}"


def transpile_view(view: CanonicalView, ctx: ViewTranspileContext) -> CanonicalView:
    """Devuelve ``view`` con el SQL en el dialecto destino, o sin reescribir con aviso si no es fiable."""
    return _transpile_view(view, ctx, {})


def _transpile_view(
    view: CanonicalView, ctx: ViewTranspileContext, schemas: dict[str, dict[str, object]]
) -> CanonicalView:
    """Cuerpo de :func:`transpile_view`; ``schemas`` guarda el esquema de sqlglot por dialecto entre vistas (H-14)."""
    if not view.query:
        return deepcopy(view)
    source_dialect = SQLGLOT_DIALECT[ctx.source_engine]
    target_dialect = SQLGLOT_DIALECT[ctx.target_engine]

    try:
        tree: Any = sqlglot.parse_one(view.query.strip().rstrip(";"), read=source_dialect)
    except Exception as err:  # noqa: BLE001 - cualquier fallo de análisis → pass-through
        return _passthrough(view, f"sqlglot no pudo analizarlo: {str(err).splitlines()[0][:120]}")

    connect_by: ConnectByOutcome = None
    siblings = False
    if ctx.source_engine == "oracle":
        tree, connect_by, siblings = _oracle_source_rewrites(tree, ctx)

    unsupported = _unsupported_reason(tree, ctx, connect_by)
    if unsupported is not None:
        return _passthrough(view, unsupported)

    external = _external_tables(tree, ctx)

    # A. Artefactos del texto de catálogo
    if ctx.source_engine in ("mysql", "mariadb"):
        tree = _rewrites.mysql_charset_casts(tree)
        tree = _rewrites.mysql_to_days_difference(tree)

    if source_dialect not in schemas:
        schemas[source_dialect] = _schema_for_sqlglot(ctx, source_dialect)
    tree = _resolve_types(tree, source_dialect, schemas[source_dialect])

    header_columns_applied = False
    if view.columns and any(w.code == _HEADER_COLUMNS_CODE for w in view.warnings):
        header_columns_applied = _apply_header_columns(tree, view)

    tree = _source_rewrites(tree, ctx.source_engine)
    _apply_names(tree, ctx)
    tree = _target_rewrites(tree, ctx.target_engine)

    try:
        query = tree.sql(dialect=target_dialect, unsupported_level=ErrorLevel.RAISE)
    except Exception as err:  # noqa: BLE001 - UnsupportedError u otro fallo de generación
        return _passthrough(view, f"sqlglot no lo traduce: {str(err).splitlines()[0][:120]}")

    result = deepcopy(view)
    result.query = query
    if header_columns_applied:
        # Los nombres de la cabecera ya van como alias en la consulta: el aviso de pérdida de nombres ya no aplica.
        result.warnings = [w for w in result.warnings if w.code != _HEADER_COLUMNS_CODE]
    result.warnings.extend(_rewritten_warnings(view, ctx, connect_by, siblings, external))
    return result


def _oracle_source_rewrites(tree: Any, ctx: ViewTranspileContext) -> tuple[Any, ConnectByOutcome, bool]:
    """Outer join ``(+)``, ``ROWNUM`` y ``CONNECT BY`` de Oracle: (árbol, resultado de CONNECT BY, ORDER SIBLINGS BY)."""
    try:
        tree = _rewrites.oracle_join_marks(tree)
    except Exception:  # noqa: BLE001 - la salvaguarda de después detecta el (+) que quede
        pass
    tree = _rewrites.oracle_rownum_limit(tree)
    order = tree.args.get("order") if isinstance(tree, exp.Select) else None
    siblings = order is not None and bool(order.args.get("siblings"))
    tree, connect_by = _rewrites.oracle_connect_by(
        tree,
        target_engine=ctx.target_engine,
        column_types=ctx.column_types,
        integer_columns=ctx.integer_columns,
        reserved_names=set(ctx.object_names) | set(ctx.object_names.values()),
    )
    return tree, connect_by, siblings


def _unsupported_reason(tree: Any, ctx: ViewTranspileContext, connect_by: ConnectByOutcome) -> str | None:
    """Motivo del pass-through si la vista tiene construcciones sin traducción fiable; ``None`` si no las tiene."""
    unsupported = _rewrites.unsupported_constructs(tree, ctx.source_engine)
    if not unsupported:
        return None
    if connect_by is not None and connect_by not in _rewrites.CONNECT_BY_CONVERTED:
        unsupported = [f"CONNECT BY ({connect_by})" if item == "CONNECT BY" else item for item in unsupported]
    return f"contiene {', '.join(unsupported)}, sin traducción automática fiable"


def _resolve_types(tree: Any, source_dialect: str, schema: dict[str, object]) -> Any:
    """Columnas y tipos resueltos con el esquema del plan; si falla, se sigue sin tipos."""
    if not schema:
        return tree
    try:
        tree = qualify(
            tree,
            schema=schema,
            dialect=source_dialect,
            validate_qualify_columns=False,
            quote_identifiers=False,
            identify=False,
        )
    except Exception:  # noqa: BLE001 - p. ej. referencias externas no resolubles
        pass
    try:
        tree = annotate_types(tree, schema=schema, dialect=source_dialect)
    except Exception:  # noqa: BLE001
        pass
    return tree


def _source_rewrites(tree: Any, source_engine: str) -> Any:
    """Casts redundantes de PostgreSQL y aritmética que depende del tipo (B), según el motor origen."""
    if source_engine == "postgresql":
        tree = _rewrites.postgres_redundant_text_casts(tree)
    tree = _rewrites.interval_arithmetic(tree)
    if source_engine in ("oracle", "postgresql", "sqlserver"):
        tree = _rewrites.typed_date_arithmetic(tree)
    if source_engine == "sqlserver":
        tree = _rewrites.tsql_string_plus(tree)
    return tree


def _target_rewrites(tree: Any, target_engine: str) -> Any:
    """Ajustes del destino: tipos y fechas (Oracle), DATE + INTERVAL y agregados de texto (PostgreSQL), ILIKE (SQL
    Server)."""
    if target_engine == "oracle":
        tree = _rewrites.oracle_target_types(tree)
        tree = _rewrites.oracle_target_date_functions(tree)
    elif target_engine == "postgresql":
        tree = _rewrites.postgres_target_date_add(tree)
        tree = _rewrites.postgres_target_text_aggregate(tree)
    elif target_engine == "sqlserver":
        tree = _rewrites.tsql_target_ilike(tree)
    return tree


def _rewritten_warnings(
    view: CanonicalView,
    ctx: ViewTranspileContext,
    connect_by: ConnectByOutcome,
    siblings: bool,
    external: list[str],
) -> list[MigrationWarning]:
    """Avisos de una vista reescrita: reescritura, semántica Oracle, jerarquía y referencias externas."""
    source_label = _ENGINE_LABEL.get(ctx.source_engine, ctx.source_engine)
    target_label = _ENGINE_LABEL.get(ctx.target_engine, ctx.target_engine)
    warnings = [
        _warning(
            view,
            "VIEW_REWRITTEN",
            "VIEW (reescrita)",
            f"SQL de la vista reescrito de {source_label} a {target_label} (sqlglot); revisar que la semántica se "
            "conserva (NULL, collation, redondeos)",
            severity="INFO",
        )
    ]
    if "oracle" in (ctx.source_engine, ctx.target_engine):
        warnings.append(
            _warning(
                view,
                "VIEW_ORACLE_SEMANTICS",
                "VIEW (semántica Oracle)",
                "En Oracle la cadena vacía es NULL y '||' ignora los NULL; en el resto de motores no: los filtros "
                "IS NULL, COALESCE, DISTINCT y las concatenaciones pueden dar otro resultado",
            )
        )
    if connect_by in ("hierarchy", "hierarchy_nocycle"):
        warnings.append(
            _warning(
                view,
                "VIEW_HIERARCHY",
                "VIEW (jerarquía)",
                _hierarchy_message(ctx.target_engine, nocycle=connect_by == "hierarchy_nocycle", siblings=siblings),
            )
        )
    if external:
        warnings.append(
            _warning(
                view,
                "VIEW_EXTERNAL_REFERENCE",
                "VIEW (referencia externa)",
                f"La vista usa objetos fuera del schema migrado ({', '.join(sorted(set(external)))}); verificar que "
                "existen en el destino",
            )
        )
    return warnings


def transpile_views(views: list[CanonicalView], ctx: ViewTranspileContext) -> list[CanonicalView]:
    """Transpila todas las vistas (ver :func:`transpile_view`).

    El esquema de tipos de sqlglot se construye una vez para todas las vistas: antes se rehacía por vista, con coste
    O(vistas × columnas del plan) (H-14, sesión 2026-10-03-metadata-centralization: 500 tablas y 50 vistas, 17,7 de
    20,4 s de ``MigrationPlanner.plan()``).
    """
    schemas: dict[str, dict[str, object]] = {}
    return [_transpile_view(view, ctx, schemas) for view in views]


__all__: list[str] = ["ViewTranspileContext", "transpile_view", "transpile_views"]
