"""Reescrituras AST de las vistas antes de generar el SQL del destino (V1, sesión 2026-09-29c-migrate-views).

Cada función recibe y devuelve un árbol de sqlglot. Las correcciones salen del spike V0 (``.ai/sessions/
2026-09-29c-migrate-views/v0/V0_SPIKE.md``): artefactos del texto de catálogo (A), aritmética que depende del tipo
(B) y funciones que sqlglot genera y Oracle no tiene. Este módulo importa sqlglot: solo se carga si está instalado.
"""

from __future__ import annotations

from typing import Any, cast

from sqlglot import exp, transforms

_TEXT_TYPES: frozenset[Any] = frozenset(
    {
        exp.DataType.Type.TEXT,
        exp.DataType.Type.VARCHAR,
        exp.DataType.Type.NVARCHAR,
        exp.DataType.Type.CHAR,
        exp.DataType.Type.NCHAR,
        exp.DataType.Type.BPCHAR,
    }
)
_TEMPORAL_TYPES: frozenset[Any] = frozenset(
    {
        exp.DataType.Type.DATE,
        exp.DataType.Type.DATETIME,
        exp.DataType.Type.DATETIME2,
        exp.DataType.Type.TIMESTAMP,
        exp.DataType.Type.TIMESTAMPNTZ,
        exp.DataType.Type.SMALLDATETIME,
    }
)


def _type_of(node: exp.Expression) -> Any:
    data_type: Any = node.type
    return data_type.this if isinstance(data_type, exp.DataType) else None


def _is_temporal(node: exp.Expression) -> bool:
    return _type_of(node) in _TEMPORAL_TYPES


def _is_numeric(node: exp.Expression) -> bool:
    return _type_of(node) in exp.DataType.NUMERIC_TYPES


def _is_text(node: exp.Expression) -> bool:
    return _type_of(node) in _TEXT_TYPES


def _unparen(node: exp.Expression) -> exp.Expression:
    while isinstance(node, exp.Paren):
        node = node.this
    return node


# ─── A. Artefactos del texto de catálogo ─────────────────────────────────────────


def mysql_charset_casts(tree: exp.Expression) -> exp.Expression:
    """``CAST(x AS CHAR CHARSET utf8mb4)`` (así guarda MySQL ``CAST(x AS CHAR(n))``) → ``CAST(x AS TEXT)``."""
    for data_type in list(tree.find_all(exp.DataType)):
        if data_type.this == exp.DataType.Type.CHARACTER_SET:
            data_type.replace(exp.DataType.build("TEXT"))
    return tree


def _to_days_operand(node: exp.Expression) -> exp.Expression | None:
    """Operando ``x`` de ``TO_DAYS(x)`` tal como lo parsea sqlglot: ``DATEDIFF(x, '0000-01-01') + 1``."""
    node = _unparen(node)
    if not (isinstance(node, exp.Add) and isinstance(node.expression, exp.Literal) and node.expression.name == "1"):
        return None
    diff = _unparen(node.this)
    if not isinstance(diff, exp.DateDiff):
        return None
    origin = diff.expression
    origin = origin.this if isinstance(origin, exp.TsOrDsToDate) else origin
    if not (isinstance(origin, exp.Literal) and origin.name == "0000-01-01"):
        return None
    operand: exp.Expression = diff.this.this if isinstance(diff.this, exp.TsOrDsToDate) else diff.this
    return operand


def mysql_to_days_difference(tree: exp.Expression) -> exp.Expression:
    """``TO_DAYS(a) - TO_DAYS(b)`` (así guarda MySQL ``DATEDIFF(a, b)``) → ``DATEDIFF(a, b)`` en días."""
    for sub in list(tree.find_all(exp.Sub)):
        left, right = _to_days_operand(sub.this), _to_days_operand(sub.expression)
        if left is not None and right is not None:
            sub.replace(exp.DateDiff(this=left.copy(), expression=right.copy(), unit=exp.var("DAY")))
    return tree


def postgres_redundant_text_casts(tree: exp.Expression) -> exp.Expression:
    """Quita los casts a texto que PostgreSQL añade al guardar la vista (``'x'::text``, ``col::character varying``).

    Solo de literales de texto y de columnas ya textuales (tipos anotados): un ``id::text`` sobre un entero se conserva.
    """
    for cast_node in list(tree.find_all(exp.Cast)):
        if cast_node.to.this not in _TEXT_TYPES or cast_node.to.expressions:
            continue
        inner = _unparen(cast_node.this)
        if (isinstance(inner, exp.Literal) and inner.is_string) or (isinstance(inner, exp.Column) and _is_text(inner)):
            cast_node.replace(inner.copy())
    return tree


# ─── B. Aritmética que depende del tipo (requiere annotate_types) ────────────────


def typed_date_arithmetic(tree: exp.Expression) -> exp.Expression:
    """``fecha ± n`` → ``DATE_ADD/DATE_SUB(fecha, n, DAY)`` y ``fecha - fecha`` → ``DATEDIFF(DAY)``.

    En Oracle y PostgreSQL (y ``DATETIME`` de SQL Server) sumar un número a una fecha suma días; en MySQL el mismo
    texto es una suma numérica (V0: ``20240140``). Con los tipos anotados se expresa de forma explícita.
    """
    # De abajo arriba: al reemplazar un nodo, sus ancestros siguen en el árbol y ven el hijo ya reescrito.
    for node in reversed(list(tree.find_all(exp.Add, exp.Sub))):
        left, right = node.this, node.expression
        if _is_temporal(left) and _is_numeric(right):
            cls = exp.DateAdd if isinstance(node, exp.Add) else exp.DateSub
            node.replace(cls(this=left.copy(), expression=right.copy(), unit=exp.var("DAY")))
        elif isinstance(node, exp.Add) and _is_numeric(left) and _is_temporal(right):
            node.replace(exp.DateAdd(this=right.copy(), expression=left.copy(), unit=exp.var("DAY")))
        elif isinstance(node, exp.Sub) and _is_temporal(left) and _is_temporal(right):
            node.replace(exp.DateDiff(this=left.copy(), expression=right.copy(), unit=exp.var("DAY")))
    return tree


def interval_arithmetic(tree: exp.Expression) -> exp.Expression:
    """``x ± INTERVAL n UNIDAD`` → ``DATE_ADD/DATE_SUB(x, n, UNIDAD)`` (así guarda MySQL su ``DATE_ADD``).

    SQL Server no tiene aritmética con ``INTERVAL`` y Oracle la limita; la función se genera bien en todos los destinos.
    """
    for node in reversed(list(tree.find_all(exp.Add, exp.Sub))):
        interval = node.expression
        if not isinstance(interval, exp.Interval) or interval.args.get("unit") is None:
            continue
        amount = interval.this.copy()
        if isinstance(amount, exp.Literal) and amount.is_string:
            amount = exp.Literal.number(amount.name)
        cls = exp.DateAdd if isinstance(node, exp.Add) else exp.DateSub
        node.replace(cls(this=node.this.copy(), expression=amount, unit=exp.var(_unit_name(interval))))
    return tree


def tsql_string_plus(tree: exp.Expression) -> exp.Expression:
    """``a + b`` de SQL Server con operandos de texto → concatenación (``||`` / ``CONCAT`` según el destino)."""
    # De abajo arriba: en ``a + ' - ' + b`` el ``+`` interior se convierte antes que el exterior.
    for node in reversed(list(tree.find_all(exp.Add))):
        if _is_text(node.this) or _is_text(node.expression) or isinstance(node.this, exp.DPipe):
            node.replace(exp.DPipe(this=node.this.copy(), expression=node.expression.copy(), safe=False))
    return tree


# ─── Destino Oracle ──────────────────────────────────────────────────────────────


def oracle_target_types(tree: exp.Expression) -> exp.Expression:
    """Texto sin longitud → ``VARCHAR2(4000)``: sqlglot lo genera como ``CLOB`` (no comparable) o ``VARCHAR2``."""
    for data_type in list(tree.find_all(exp.DataType)):
        if data_type.this in (exp.DataType.Type.TEXT, exp.DataType.Type.CHARACTER_SET) or (
            data_type.this in _TEXT_TYPES and not data_type.expressions
        ):
            data_type.replace(exp.DataType.build("VARCHAR(4000)"))
    return tree


def _unit_name(node: Any) -> str:
    unit: Any = node.args.get("unit")
    return str(unit.name).upper() if unit is not None else "DAY"


def _day_offset(node: Any) -> exp.Expression:
    unit = _unit_name(node)
    amount = node.expression.copy()
    if isinstance(amount, exp.Interval):
        amount = amount.this.copy()
    if isinstance(amount, exp.Literal) and amount.is_string and amount.name.lstrip("+-").replace(".", "", 1).isdigit():
        amount = exp.Literal.number(amount.name)  # MySQL guarda INTERVAL '30' DAY: la cantidad llega como texto
    if unit in ("MONTH", "YEAR"):
        months = amount if unit == "MONTH" else exp.Mul(this=amount, expression=exp.Literal.number(12))
        sign = -1 if isinstance(node, exp.DateSub) else 1
        if sign < 0:
            months = exp.Neg(this=exp.Paren(this=months))
        return exp.Anonymous(this="ADD_MONTHS", expressions=[node.this.copy(), months])
    cls = exp.Add if isinstance(node, exp.DateAdd) else exp.Sub
    return exp.Paren(this=cls(this=node.this.copy(), expression=amount))


def oracle_target_date_functions(tree: exp.Expression) -> exp.Expression:
    """Funciones de fecha que sqlglot genera para Oracle y Oracle no tiene.

    ``DATE_ADD/DATE_SUB`` → ``fecha ± n`` (días) o ``ADD_MONTHS``; ``DATEDIFF(a, b)`` en días → ``(a - b)``;
    ``YEAR/MONTH/DAY(x)`` → ``EXTRACT(... FROM x)``.
    """
    # Envoltorios de conversión que sqlglot añade al parsear fechas (p. ej. DATEDIFF de SQL Server) y Oracle no tiene.
    for wrapper in list(tree.find_all(exp.TimeStrToTime, exp.TsOrDsToDate, exp.TsOrDsToTimestamp)):
        if isinstance(wrapper.this, exp.Column):
            wrapper.replace(wrapper.this.copy())
    for node in list(tree.find_all(exp.DateAdd, exp.DateSub, exp.TsOrDsAdd)):
        node.replace(_day_offset(node))
    for node in list(tree.find_all(exp.DateDiff)):
        if _unit_name(node) == "DAY":
            node.replace(exp.Paren(this=exp.Sub(this=node.this.copy(), expression=node.expression.copy())))
    for cls, part in ((exp.Year, "YEAR"), (exp.Month, "MONTH"), (exp.Day, "DAY")):
        for node in list(tree.find_all(cls)):
            node.replace(exp.Extract(this=exp.var(part), expression=node.this.copy()))
    return tree


# ─── Destino PostgreSQL ──────────────────────────────────────────────────────────


def postgres_target_date_add(tree: exp.Expression) -> exp.Expression:
    """``fecha + INTERVAL`` en PostgreSQL devuelve ``timestamp``: se devuelve a ``DATE`` si el operando era ``DATE``."""
    for node in list(tree.find_all(exp.DateAdd, exp.DateSub)):
        if _type_of(node.this) == exp.DataType.Type.DATE:
            node.replace(exp.Cast(this=node.copy(), to=exp.DataType.build("DATE")))
    return tree


# ─── Oracle origen (V2) ──────────────────────────────────────────────────────────


def oracle_join_marks(tree: exp.Expression) -> exp.Expression:
    """Outer join ``(+)`` de Oracle → ``LEFT JOIN`` (``transforms.eliminate_join_marks`` de sqlglot).

    Sin esto sqlglot emite un join interno y la vista devuelve otro resultado sin error (V0).
    """
    return cast(exp.Expression, transforms.eliminate_join_marks(tree))


def _is_rownum(node: exp.Expression) -> bool:
    return isinstance(node, exp.Column) and not node.table and node.name.upper() == "ROWNUM"


def _rownum_bound(condition: exp.Expression) -> int | None:
    """Límite de filas de ``ROWNUM <= n``, ``ROWNUM < n``, ``n >= ROWNUM``, ``n > ROWNUM`` o ``ROWNUM = 1``."""
    left, right = condition.args.get("this"), condition.args.get("expression")
    if isinstance(condition, (exp.LTE, exp.LT, exp.EQ)) and left is not None and _is_rownum(left):
        bound, strict = right, isinstance(condition, exp.LT)
    elif isinstance(condition, (exp.GTE, exp.GT)) and right is not None and _is_rownum(right):
        bound, strict = left, isinstance(condition, exp.GT)
    else:
        return None
    if not (isinstance(bound, exp.Literal) and not bound.is_string and bound.name.isdigit()):
        return None
    value = int(bound.name) - (1 if strict else 0)
    if isinstance(condition, exp.EQ) and value != 1:
        return None
    return value


def oracle_rownum_limit(tree: exp.Expression) -> exp.Expression:
    """``WHERE ... AND ROWNUM <= n`` en una consulta **sin** ``ORDER BY`` → ``LIMIT n`` (``TOP``/``FETCH FIRST``).

    En Oracle ``ROWNUM`` se aplica antes del ``ORDER BY`` de la misma consulta: solo se traduce cuando esa consulta no
    ordena (incluido el top-N clásico ``SELECT * FROM (... ORDER BY x) WHERE ROWNUM <= n``). Cualquier otro uso se deja
    y la salvaguarda emite la vista sin reescribir.
    """
    for select in list(tree.find_all(exp.Select)):
        where = select.args.get("where")
        if where is None or select.args.get("order") or select.args.get("limit"):
            continue
        conjuncts: list[Any] = list(where.this.flatten()) if isinstance(where.this, exp.And) else [where.this]
        limit: int | None = None
        rest: list[Any] = []
        for condition in conjuncts:
            bound = _rownum_bound(condition) if limit is None else None
            if bound is not None:
                limit = bound
            else:
                rest.append(condition)
        if limit is None or any(_is_rownum(col) for cond in rest for col in cond.find_all(exp.Column)):
            continue
        ordered_inner = _ordered_derived_table(select)
        if ordered_inner is not None:
            # Top-N clásico: el límite va DENTRO de la subconsulta ordenada. Un ORDER BY en una tabla derivada sin
            # límite lo ignora MariaDB (otras filas, sin error) y SQL Server lo rechaza. Con más condiciones fuera no
            # es equivalente: se deja el ROWNUM y la salvaguarda emite la vista sin reescribir.
            if rest:
                continue
            ordered_inner.set("limit", exp.Limit(expression=exp.Literal.number(limit)))
            select.set("where", None)
            continue
        select.set("where", exp.Where(this=exp.and_(*[c.copy() for c in rest])) if rest else None)
        select.set("limit", exp.Limit(expression=exp.Literal.number(limit)))
    return tree


def _ordered_derived_table(select: exp.Select) -> exp.Select | None:
    """Subconsulta ordenada (sin límite) de ``SELECT ... FROM (SELECT ... ORDER BY ...) alias`` sin joins ni agregados.

    Con otra forma (joins, GROUP BY, DISTINCT...) devuelve ``None`` y el límite se aplica a la consulta exterior.
    """
    if select.args.get("joins") or select.args.get("group") or select.args.get("having") or select.args.get("distinct"):
        return None
    source: Any = select.args.get("from_") or select.args.get("from")
    derived = source.this if source is not None else None
    if not isinstance(derived, exp.Subquery):
        return None
    inner = derived.this
    if isinstance(inner, exp.Select) and inner.args.get("order") and not inner.args.get("limit"):
        return inner
    return None


# ─── Destino SQL Server / PostgreSQL (V2) ─────────────────────────────────────────


def tsql_target_ilike(tree: exp.Expression) -> exp.Expression:
    """``a ILIKE b`` (PostgreSQL) → ``LOWER(a) LIKE LOWER(b)``: SQL Server no tiene ``ILIKE``."""
    for node in reversed(list(tree.find_all(exp.ILike))):
        node.replace(exp.Like(this=exp.Lower(this=node.this.copy()), expression=exp.Lower(this=node.expression.copy())))
    return tree


def postgres_target_text_aggregate(tree: exp.Expression) -> exp.Expression:
    """``STRING_AGG`` de PostgreSQL exige texto: el valor agregado (``GROUP_CONCAT``, ``LISTAGG``...) se pasa a texto."""
    for node in list(tree.find_all(exp.GroupConcat)):
        holder: exp.Expression = node.this if isinstance(node.this, exp.Order) else node
        value = holder.this
        if value is not None and not _is_text(value) and not isinstance(value, exp.Cast):
            holder.set("this", exp.Cast(this=value.copy(), to=exp.DataType.build("TEXT")))
    return tree


# ─── Salvaguardas (construcciones sin traducción fiable) ──────────────────────────


def unsupported_constructs(tree: exp.Expression, source_engine: str) -> list[str]:
    """Construcciones del origen que V1 no traduce de forma fiable (V0: error silencioso o fallo)."""
    found: list[str] = []
    if source_engine == "oracle":
        if any(column.args.get("join_mark") for column in tree.find_all(exp.Column)):
            found.append("outer join (+) de Oracle no convertible a LEFT JOIN")
        if any(column.name.upper() == "ROWNUM" and not column.table for column in tree.find_all(exp.Column)):
            found.append("ROWNUM fuera de un límite de filas sin ORDER BY")
        if any(select.args.get("connect") for select in tree.find_all(exp.Select)):
            found.append("CONNECT BY")
    return found


__all__: list[str] = [
    "mysql_charset_casts",
    "mysql_to_days_difference",
    "oracle_join_marks",
    "oracle_rownum_limit",
    "oracle_target_date_functions",
    "oracle_target_types",
    "postgres_redundant_text_casts",
    "postgres_target_text_aggregate",
    "postgres_target_date_add",
    "interval_arithmetic",
    "tsql_string_plus",
    "tsql_target_ilike",
    "typed_date_arithmetic",
    "unsupported_constructs",
]
