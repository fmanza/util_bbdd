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
        if select.args.get("connect"):
            # En una consulta jerárquica ROWNUM numera en el orden en profundidad de Oracle, que la CTE recursiva no
            # reproduce: se deja y la vista queda sin reescribir (V4).
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


# ─── Jerarquías de Oracle: CONNECT BY → CTE recursiva (V4) ────────────────────────

CONNECT_BY_CTE: str = "connect_by_tree"
_CONNECT_BY_PARENT: str = "connect_by_parent"
_CONNECT_BY_LEVEL: str = "cb_level"
# Tipo de SYS_CONNECT_BY_PATH por destino: el mismo en las dos ramas de la CTE (SQL Server exige tipo y longitud
# idénticos; MySQL toma el de la rama ancla). 4000 = límite de SYS_CONNECT_BY_PATH en Oracle.
_CONNECT_BY_PATH_TYPE: dict[str, str] = {
    "postgresql": "VARCHAR(4000)",
    "sqlserver": "NVARCHAR(4000)",
    "mysql": "CHAR(4000)",
    "mariadb": "CHAR(4000)",
}
# Recursiones máximas por defecto de una CTE, que una vista no puede ampliar (SQL Server: OPTION (MAXRECURSION) no se
# admite en vistas; MySQL: cte_max_recursion_depth es de sesión). PostgreSQL y MariaDB no tienen un límite práctico.
CONNECT_BY_RECURSION_LIMIT: dict[str, int] = {"sqlserver": 100, "mysql": 1000}
# CHAR/NCHAR quedan fuera: Oracle conserva el relleno en la ruta y PostgreSQL lo quita al convertir a VARCHAR.
_CONNECT_BY_PATH_TEXT_TYPES: frozenset[str] = frozenset({"VARCHAR2", "NVARCHAR2", "VARCHAR"})
_HIERARCHY_PSEUDOCOLUMNS: frozenset[str] = frozenset({"ROWNUM"})
_CONNECT_BY_ISLEAF: str = "CONNECT_BY_ISLEAF"
# F2 (0.23.0): 1 si la fila tiene un hijo que la jerarquía visitaría (LEVEL <= n incluido) y que ya está en el camino,
# ella misma incluida; solo existe con NOCYCLE (sin él, Oracle da ORA-30930). Comprobado contra Oracle en el banco.
_CONNECT_BY_ISCYCLE: str = "CONNECT_BY_ISCYCLE"
# NOCYCLE (solo destino PostgreSQL): array con la columna de PRIOR de la fila y sus antepasados. La rama recursiva no
# baja a una fila cuyo valor ya está en el array (Oracle la omite) y CONNECT_BY_ISLEAF no cuenta ese hijo (Oracle da 1).
# La cláusula CYCLE de PostgreSQL 14+ no sirve: marca la fila del ciclo, pero ISLEAF necesita los antepasados.
# Los valores van como TEXT (C1, auditoría 0.22.0): un ARRAY de VARCHAR(n) o NUMERIC(p,s) conserva la longitud en la
# rama ancla y la pierde al concatenar, y PostgreSQL rechaza la CTE por tipos distintos. Los tipos que produce la
# migración desde Oracle (VARCHAR, NUMERIC con escala fija, BIGINT, fechas) dan un texto único por valor.
_CONNECT_BY_KEYS: str = "cb_keys"

ConnectByOutcome = str | None
"""``"hierarchy"``, ``"hierarchy_nocycle"`` o ``"generator"`` si se convirtió; otro texto = motivo para no convertir;
``None`` = sin CONNECT BY."""
CONNECT_BY_CONVERTED: frozenset[str] = frozenset({"hierarchy", "hierarchy_nocycle", "generator"})


def _is_level(node: exp.Expression) -> bool:
    return isinstance(node, exp.Column) and not node.table and node.name.upper() == "LEVEL"


def _is_star(node: exp.Expression) -> bool:
    """``*`` o ``alias.*`` en la lista de columnas."""
    return isinstance(node, exp.Star) or (isinstance(node, exp.Column) and isinstance(node.this, exp.Star))


def _is_connect_by_path(node: exp.Expression) -> bool:
    return isinstance(node, exp.Anonymous) and str(node.this).upper() == "SYS_CONNECT_BY_PATH"


def _free_name(base: str, taken: set[str]) -> str:
    name, suffix = base, 2
    while name.lower() in taken:
        name, suffix = f"{base}_{suffix}", suffix + 1
    return name


def _level_bound(condition: exp.Expression) -> int | None:
    """Número de filas de ``LEVEL <= n``, ``LEVEL < n``, ``n >= LEVEL`` o ``n > LEVEL`` con ``n`` entero literal."""
    left, right = condition.this, condition.expression
    if isinstance(condition, (exp.LTE, exp.LT)) and _is_level(left):
        literal, strict = right, isinstance(condition, exp.LT)
    elif isinstance(condition, (exp.GTE, exp.GT)) and right is not None and _is_level(right):
        literal, strict = left, isinstance(condition, exp.GT)
    else:
        return None
    if not isinstance(literal, exp.Literal) or literal.is_string or not str(literal.this).isdigit():
        return None
    return int(literal.this) - (1 if strict else 0)


def _replace_level(select: exp.Select, qualifier: str | None) -> None:
    for column in list(select.find_all(exp.Column)):
        if _is_level(column):
            column.replace(exp.column(_CONNECT_BY_LEVEL, table=qualifier))


def _connect_by_generator(select: exp.Select, target_engine: str, taken: set[str]) -> exp.Expression | str:
    """``SELECT ... LEVEL ... FROM dual CONNECT BY LEVEL <= n`` → CTE recursiva que cuenta de 1 a n."""
    connect: Any = select.args["connect"]
    rows = _level_bound(connect.args["connect"])
    if rows is None:
        return "condición CONNECT BY distinta de LEVEL <= n con n literal"
    if connect.args.get("start") is not None:
        return "START WITH en un generador de filas"
    if any(_is_star(projection) for projection in select.expressions):
        return "SELECT * en un generador de filas (Oracle devuelve la columna DUMMY de dual)"
    limit = CONNECT_BY_RECURSION_LIMIT.get(target_engine)
    if limit is not None and rows - 1 > limit:
        return f"{rows} filas superan el límite de {limit} recursiones de una CTE en {target_engine}"
    aliases = {alias.alias.lower() for alias in select.expressions if isinstance(alias, exp.Alias)}
    for column in select.find_all(exp.Column):
        if not _is_level(column) and column.name.lower() not in aliases:
            return f"columna {column.sql(dialect='oracle')} de dual en un generador de filas"

    cte_name = _free_name(CONNECT_BY_CTE, taken)
    anchor = exp.select(exp.alias_(exp.Literal.number(1), _CONNECT_BY_LEVEL))
    recursive = (
        exp.select(exp.alias_(exp.column(_CONNECT_BY_LEVEL, table=cte_name) + exp.Literal.number(1), _CONNECT_BY_LEVEL))
        .from_(cte_name)
        .where(exp.column(_CONNECT_BY_LEVEL, table=cte_name) < exp.Literal.number(rows))
    )
    outer = select.copy()
    outer.set("connect", None)
    outer.set("from_", exp.From(this=exp.to_table(cte_name)))
    _replace_level(outer, None)
    outer.set(
        "with_",
        exp.With(
            expressions=[
                exp.CTE(
                    this=exp.union(anchor, recursive, distinct=False),
                    alias=exp.TableAlias(this=exp.to_identifier(cte_name)),
                )
            ],
            recursive=True,
        ),
    )
    return outer


def _prior_pair(condition: exp.Expression) -> tuple[exp.Column, exp.Column] | None:
    """``PRIOR padre = hijo`` o ``hijo = PRIOR padre`` entre columnas simples → (padre, hijo)."""
    if not isinstance(condition, exp.EQ):
        return None
    left, right = condition.this, condition.expression
    if isinstance(left, exp.Prior) and isinstance(left.this, exp.Column) and isinstance(right, exp.Column):
        return left.this, right
    if isinstance(right, exp.Prior) and isinstance(right.this, exp.Column) and isinstance(left, exp.Column):
        return right.this, left
    return None


def _connect_condition(condition: exp.Expression) -> tuple[exp.Column, exp.Column, int | None] | None:
    """``PRIOR padre = hijo`` con ``AND LEVEL <= n`` opcionales → (padre, hijo, nivel máximo o ``None``)."""
    parts: list[Any] = list(condition.flatten()) if isinstance(condition, exp.And) else [condition]
    pairs = [pair for pair in (_prior_pair(part) for part in parts) if pair is not None]
    bounds = [bound for bound in (_level_bound(part) for part in parts) if bound is not None]
    if len(pairs) != 1 or len(pairs) + len(bounds) != len(parts):
        return None
    return pairs[0][0], pairs[0][1], min(bounds) if bounds else None


def _key_text(column: exp.Column) -> exp.Expression:
    """Valor de la columna de PRIOR como TEXT para ``cb_keys`` (C1, auditoría 0.22.0)."""
    return exp.Cast(this=column, to=exp.DataType.build("TEXT"))


def _in_keys(column: exp.Column, keys_table: str) -> exp.Expression:
    """``COALESCE(CAST(columna AS TEXT) = ANY(tabla.cb_keys), FALSE)``: la fila actual o un antepasado.

    ``COALESCE`` (C2, auditoría 0.22.0): con NULL en la columna, o en el array, la comparación da NULL; un NULL nunca
    cierra un ciclo en Oracle, así que cuenta como «no está».
    """
    in_keys = exp.EQ(
        this=_key_text(column),
        expression=exp.Any(this=exp.Paren(this=exp.column(_CONNECT_BY_KEYS, table=keys_table))),
    )
    return exp.Coalesce(this=in_keys, expressions=[exp.false()])


def _not_in_keys(column: exp.Column, keys_table: str) -> exp.Expression:
    """Negación de :func:`_in_keys`: ni la fila actual ni un antepasado."""
    return exp.not_(_in_keys(column, keys_table))


def _has_child(
    source: exp.Table,
    qualifier: str,
    parent_col: str,
    child_col: str,
    max_level: int | None,
    on_path: bool | None,
    taken: set[str],
) -> exp.Expression:
    """Hay una fila de la tabla que cuelga de esta y que la jerarquía podría visitar (``LEVEL <= n`` incluido).

    ``on_path``: ``None`` = cualquier hijo; ``False`` = hijos que **no** están en el camino (``NOCYCLE``); ``True`` =
    hijos que **sí** están (cierran un ciclo). Se evalúa contra la tabla, no contra el resultado: en Oracle el ``WHERE``
    de la consulta no cambia ``CONNECT_BY_ISLEAF`` ni ``CONNECT_BY_ISCYCLE``.
    """
    alias = _free_name("cb_child", taken | {qualifier.lower()})
    child_table = source.copy()
    child_table.set("alias", exp.TableAlias(this=exp.to_identifier(alias)))
    child_filter: Any = exp.EQ(
        this=exp.column(child_col, table=alias), expression=exp.column(parent_col, table=qualifier)
    )
    if on_path is not None:
        membership = _in_keys(exp.column(parent_col, table=alias), qualifier)
        child_filter = exp.and_(child_filter, membership if on_path else exp.not_(membership))
    has_child: Any = exp.Exists(this=exp.select(exp.Literal.number(1)).from_(child_table).where(child_filter))
    if max_level is not None:
        has_child = exp.and_(exp.column(_CONNECT_BY_LEVEL, table=qualifier) < exp.Literal.number(max_level), has_child)
    return has_child


def _flag(condition: exp.Expression, when_true: int) -> exp.Expression:
    """``CASE WHEN condición THEN when_true ELSE 1 - when_true END``."""
    return exp.Case(
        ifs=[exp.If(this=condition, true=exp.Literal.number(when_true))], default=exp.Literal.number(1 - when_true)
    )


def _connect_by_hierarchy(
    select: exp.Select,
    target_engine: str,
    column_types: dict[str, dict[str, str]],
    integer_columns: dict[str, frozenset[str]],
    taken: set[str],
) -> exp.Expression | str:
    """Jerarquía simple (``START WITH`` + ``CONNECT BY PRIOR a = b``) → CTE recursiva; el ``WHERE`` va fuera."""
    connect: Any = select.args["connect"]
    nocycle = bool(connect.args.get("nocycle"))
    if nocycle and target_engine != "postgresql":
        return f"NOCYCLE, que solo se convierte con destino PostgreSQL (arrays), no {target_engine}"
    order: Any = select.args.get("order")
    if order is not None and order.args.get("siblings"):
        return "ORDER SIBLINGS BY"
    if select.args.get("joins") or select.args.get("laterals"):
        return "joins en la consulta jerárquica"
    source: Any = select.args["from_"].this
    if not isinstance(source, exp.Table):
        return "origen que no es una tabla"
    parsed = _connect_condition(connect.args["connect"])
    if parsed is None:
        return "condición CONNECT BY distinta de PRIOR columna = columna [AND LEVEL <= n]"
    parent_col, child_col, max_level = parsed
    start: Any = connect.args.get("start")
    if start is not None and any(_is_level(c) for c in start.find_all(exp.Column)):
        return "LEVEL en START WITH"
    pseudo = sorted(
        {
            c.name.upper()
            for c in select.find_all(exp.Column)
            if c.name.upper() in _HIERARCHY_PSEUDOCOLUMNS and not c.table
        }
    )
    if pseudo:
        return ", ".join(pseudo)
    if not nocycle and any(not c.table and c.name.upper() == _CONNECT_BY_ISCYCLE for c in select.find_all(exp.Column)):
        return "CONNECT_BY_ISCYCLE sin NOCYCLE (Oracle da ORA-30930)"
    priors = list(select.find_all(exp.Prior))
    if len(priors) != 1:
        return "PRIOR fuera de la condición CONNECT BY"

    table_name = source.name
    qualifier = source.alias_or_name
    types = next((cols for name, cols in column_types.items() if name.lower() == table_name.lower()), None)
    if types is None:
        return f"tabla {table_name} fuera del plan"
    table_columns = {name.lower(): name for name in types}
    integers = next((cols for name, cols in integer_columns.items() if name.lower() == table_name.lower()), frozenset())
    integer_names = {name.lower() for name in integers}
    for column in select.find_all(exp.Column):
        if column.table and column.table.lower() != qualifier.lower():
            return f"columna {column.sql(dialect='oracle')} de otro origen"
    if any(name.lower().startswith("cb_") for name in table_columns):
        return "columnas cb_* en la tabla (nombres reservados para la CTE)"
    if any(_is_star(projection) for projection in select.expressions):
        # H1 (auditoría 0.22.0): la CTE solo lleva las columnas nombradas; sin expandir, SELECT * devolvería esas y
        # las internas (cb_level, cb_keys) en lugar de las de la tabla. Se expande en el orden del plan (el de Oracle).
        select = select.copy()
        expanded: list[exp.Expression] = []
        for projection in select.expressions:
            if _is_star(projection):
                expanded.extend(exp.column(name, table=qualifier) for name in types)
            else:
                expanded.append(projection)
        select.set("expressions", expanded)

    # Columnas de la tabla que usa la consulta (los alias de salida, p. ej. en ORDER BY, no están en la tabla).
    used: list[str] = []
    for column in select.find_all(exp.Column):
        name = column.name.lower()
        if name in table_columns and name not in used and not _is_level(column):
            used.append(name)
    if parent_col.name.lower() not in table_columns or child_col.name.lower() not in table_columns:
        return "columnas de PRIOR fuera de la tabla"
    if parent_col.name.lower() not in used:
        used.append(parent_col.name.lower())

    path_type = exp.DataType.build(_CONNECT_BY_PATH_TYPE[target_engine])
    cte_name = _free_name(CONNECT_BY_CTE, taken)
    parent = _CONNECT_BY_PARENT
    anchor_extra: list[Any] = [exp.alias_(exp.Literal.number(1), _CONNECT_BY_LEVEL)]
    recursive_extra: list[Any] = [
        exp.alias_(exp.column(_CONNECT_BY_LEVEL, table=parent) + exp.Literal.number(1), _CONNECT_BY_LEVEL)
    ]
    if nocycle:
        prior_key = exp.column(table_columns[parent_col.name.lower()], table=qualifier)
        anchor_extra.append(exp.alias_(exp.Array(expressions=[_key_text(prior_key.copy())]), _CONNECT_BY_KEYS))
        recursive_extra.append(
            exp.alias_(
                exp.DPipe(
                    this=exp.column(_CONNECT_BY_KEYS, table=parent),
                    expression=exp.Array(expressions=[_key_text(prior_key.copy())]),
                ),
                _CONNECT_BY_KEYS,
            )
        )
    replacements: dict[str, str] = {}

    for root_node in list(select.find_all(exp.ConnectByRoot)):
        target = root_node.this
        if not isinstance(target, exp.Column) or target.name.lower() not in table_columns:
            return "CONNECT_BY_ROOT de algo que no es una columna de la tabla"
        key = root_node.sql(dialect="oracle").lower()
        if key not in replacements:
            name = f"cb_root_{len([k for k in replacements if k.startswith('connect_by_root')]) + 1}"
            replacements[key] = name
            anchor_extra.append(exp.alias_(exp.column(target.name, table=qualifier), name))
            recursive_extra.append(exp.alias_(exp.column(name, table=parent), name))

    for path_node in list(select.find_all(exp.Anonymous)):
        if not _is_connect_by_path(path_node):
            continue
        args = path_node.expressions
        if (
            len(args) != 2
            or not isinstance(args[0], exp.Column)
            or not (isinstance(args[1], exp.Literal) and args[1].is_string)
        ):
            return "SYS_CONNECT_BY_PATH con argumentos que no son columna y separador literal"
        column_name = args[0].name.lower()
        if column_name not in table_columns:
            return "SYS_CONNECT_BY_PATH de algo que no es una columna de la tabla"
        type_name = types[table_columns[column_name]].upper().split("(")[0].strip()
        if type_name not in _CONNECT_BY_PATH_TEXT_TYPES and column_name not in integer_names:
            return f"SYS_CONNECT_BY_PATH sobre una columna {type_name} (solo texto variable o enteros)"
        key = path_node.sql(dialect="oracle").lower()
        if key in replacements:
            continue
        name = f"cb_path_{len([k for k in replacements if k.startswith('sys_connect_by_path')]) + 1}"
        replacements[key] = name
        separator = args[1].copy()
        value = exp.Coalesce(
            this=exp.Cast(this=exp.column(args[0].name, table=qualifier), to=path_type.copy()),
            expressions=[exp.Literal.string("")],
        )
        anchor_extra.append(
            exp.alias_(exp.Cast(this=exp.DPipe(this=separator, expression=value), to=path_type.copy()), name)
        )
        recursive_extra.append(
            exp.alias_(
                exp.Cast(
                    this=exp.DPipe(
                        this=exp.DPipe(this=exp.column(name, table=parent), expression=separator.copy()),
                        expression=value.copy(),
                    ),
                    to=path_type.copy(),
                ),
                name,
            )
        )

    carried = [exp.column(table_columns[name], table=qualifier) for name in used]
    # Copia completa (conserva schema/catálogo: _apply_names quita el del origen y avisa de los externos).
    source_table = source.copy()
    source_table.set("alias", exp.TableAlias(this=exp.to_identifier(qualifier)))
    anchor = exp.select(*[c.copy() for c in carried], *anchor_extra).from_(source_table.copy())
    if start is not None:
        anchor = anchor.where(start.copy())
    join_condition = exp.EQ(
        this=exp.column(table_columns[child_col.name.lower()], table=qualifier),
        expression=exp.column(table_columns[parent_col.name.lower()], table=parent),
    )
    recursive = (
        exp.select(*[c.copy() for c in carried], *recursive_extra)
        .from_(source_table.copy())
        .join(
            exp.Table(this=exp.to_identifier(cte_name), alias=exp.TableAlias(this=exp.to_identifier(parent))),
            on=join_condition,
        )
    )
    if max_level is not None:
        # En CONNECT BY, LEVEL es el nivel del hijo: nivel del padre + 1 <= n.
        recursive = recursive.where(exp.column(_CONNECT_BY_LEVEL, table=parent) < exp.Literal.number(max_level))
    if nocycle:
        recursive = recursive.where(
            _not_in_keys(exp.column(table_columns[parent_col.name.lower()], table=qualifier), parent)
        )

    outer = select.copy()
    outer.set("connect", None)
    outer.set(
        "from_",
        exp.From(
            this=exp.Table(this=exp.to_identifier(cte_name), alias=exp.TableAlias(this=exp.to_identifier(qualifier)))
        ),
    )
    for replaced in list(outer.find_all(exp.ConnectByRoot, exp.Anonymous)):
        column_alias = replacements.get(replaced.sql(dialect="oracle").lower())
        if column_alias is not None:
            replaced.replace(exp.column(column_alias, table=qualifier))
    # CONNECT_BY_ISLEAF: 0 si hay un hijo visitable (con NOCYCLE, fuera del camino); CONNECT_BY_ISCYCLE (F2): 1 si hay
    # un hijo visitable que ya está en el camino.
    pseudocolumns: dict[str, tuple[bool | None, int]] = {
        _CONNECT_BY_ISLEAF: (False if nocycle else None, 0),
        _CONNECT_BY_ISCYCLE: (True, 1),
    }
    for pseudo_column in [c for c in outer.find_all(exp.Column) if not c.table and c.name.upper() in pseudocolumns]:
        on_path, when_child = pseudocolumns[pseudo_column.name.upper()]
        value = _flag(
            _has_child(
                source,
                qualifier,
                table_columns[parent_col.name.lower()],
                table_columns[child_col.name.lower()],
                max_level,
                on_path,
                taken,
            ),
            when_child,
        )
        # Proyección sin alias: conserva el nombre de columna que da Oracle.
        pseudo_column.replace(exp.alias_(value, pseudo_column.name.lower()) if pseudo_column.parent is outer else value)
    _replace_level(outer, qualifier)
    cte = exp.CTE(
        this=exp.union(anchor, recursive, distinct=False), alias=exp.TableAlias(this=exp.to_identifier(cte_name))
    )
    outer.set("with_", exp.With(expressions=[cte], recursive=True))
    return outer


def oracle_connect_by(
    tree: exp.Expression,
    *,
    target_engine: str,
    column_types: dict[str, dict[str, str]],
    integer_columns: dict[str, frozenset[str]],
    reserved_names: set[str],
) -> tuple[exp.Expression, ConnectByOutcome]:
    """``CONNECT BY`` de Oracle → CTE recursiva, solo en el subconjunto con traducción fiable.

    Convierte la consulta principal de la vista si es una jerarquía simple (un solo origen, ``START WITH`` opcional,
    ``CONNECT BY PRIOR a = b`` con ``AND LEVEL <= n`` opcional, ``LEVEL``, ``SYS_CONNECT_BY_PATH`` sobre texto variable
    o enteros con separador literal, ``CONNECT_BY_ROOT``, ``CONNECT_BY_ISLEAF``; ``NOCYCLE`` solo con destino
    PostgreSQL) o el generador ``FROM dual CONNECT BY LEVEL <= n``. El ``WHERE`` de la consulta va en la consulta
    exterior porque Oracle filtra **después** de recorrer la jerarquía. Cualquier otro caso devuelve el árbol sin
    tocar y el motivo; la salvaguarda deja entonces la vista sin reescribir.

    Returns:
        (árbol, resultado): resultado ``"hierarchy"``/``"hierarchy_nocycle"``/``"generator"`` si se convirtió, el
        motivo si no, ``None`` si la vista no tiene ``CONNECT BY``.
    """
    selects = [select for select in tree.find_all(exp.Select) if select.args.get("connect")]
    if not selects:
        return tree, None
    if target_engine not in _CONNECT_BY_PATH_TYPE:
        return tree, f"destino {target_engine}"
    if selects != [tree] or not isinstance(tree, exp.Select):
        return tree, "CONNECT BY dentro de una subconsulta, CTE o UNION"
    if tree.args.get("with_") is not None:
        return tree, "vista con WITH propio"
    taken = {name.lower() for name in reserved_names}
    source: Any = tree.args["from_"].this if tree.args.get("from_") else None
    if isinstance(source, exp.Table) and source.name.upper() == "DUAL" and not tree.args.get("joins"):
        result = _connect_by_generator(tree, target_engine, taken)
        kind = "generator"
    else:
        result = _connect_by_hierarchy(tree, target_engine, column_types, integer_columns, taken)
        kind = "hierarchy_nocycle" if tree.args["connect"].args.get("nocycle") else "hierarchy"
    if isinstance(result, str):
        return tree, result
    return result, kind


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
    "CONNECT_BY_CTE",
    "CONNECT_BY_RECURSION_LIMIT",
    "ConnectByOutcome",
    "mysql_charset_casts",
    "mysql_to_days_difference",
    "oracle_connect_by",
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
