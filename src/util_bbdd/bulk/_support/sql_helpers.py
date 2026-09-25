"""Helpers internos para serialización y compilación SQL en bulk_crud."""

from __future__ import annotations

import re

from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    BindParameter,
    Delete,
    Insert,
    String,
    Table,
    TableClause,
    Update,
    and_,
    bindparam,
    delete,
    literal,
    literal_column,
    text,
    update,
)
from sqlalchemy.engine import Dialect, make_url
from sqlalchemy.sql import operators
from sqlalchemy.sql.compiler import SQLCompiler
from sqlalchemy.sql.sqltypes import _Binary
from sqlalchemy.types import TypeDecorator, TypeEngine

SqlRecord = dict[str, Any]


class PreSerializedJSON(TypeDecorator[Any]):
    """Tipo de parámetro para columnas JSON cuyo valor ya llega serializado por ``normalize_sql_literal``.

    P-19 (performance-audit de bulk, 2026-09-24): con el tipo ``JSON`` reflejado, SQLAlchemy volvía a serializar el
    texto (se guardaba un *string* JSON) y convertía ``None`` en el literal JSON ``null`` en lugar de ``NULL`` SQL.
    Este tipo no procesa el valor, pero conserva el tipo de la columna para el dialecto, de modo que PostgreSQL sigue
    recibiendo el cast (``::JSONB`` / ``::JSON``).
    """

    impl = JSON
    cache_ok = True

    def __init__(self, target: TypeEngine[Any]) -> None:
        super().__init__()
        self.target = target

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        return dialect.type_descriptor(self.target)

    def bind_processor(self, dialect: Dialect) -> None:
        return None


def restore_binary_values(records: Sequence[SqlRecord], table: Table) -> None:
    """Devuelve a ``bytes`` los valores de columnas binarias que ``normalize_sql_literal`` decodificó a ``str``.

    P-21 (performance-audit de bulk, 2026-09-24): ``normalize_sql_literal`` decodifica los ``bytes`` que son UTF-8 válido
    (``b"q"`` → ``"q"``). En columnas binarias, los parámetros tipados rechazaban ese ``str`` (``TypeError``) y Oracle lo
    guardaba como NULL. Codificar de nuevo en UTF-8 recupera exactamente los bytes originales. Modifica ``records``.
    """
    if not records:
        return
    binary_cols = [name for name in records[0] if name in table.c and isinstance(table.c[name].type, _Binary)]
    for record in records:
        for name in binary_cols:
            value = record[name]
            if isinstance(value, str):
                record[name] = value.encode("utf-8")


def json_passthrough_binds(table: Table, columns: Sequence[str]) -> dict[str, BindParameter[Any]]:
    """Devuelve ``{columna: bindparam}`` con :class:`PreSerializedJSON` para las columnas JSON de ``columns``.

    Pensado para ``insert(tabla).values(...)`` / ``update(tabla).values(...)``: las demás columnas se enlazan como
    siempre. Vacío si ninguna columna es de tipo JSON.
    """
    return {
        name: bindparam(name, type_=PreSerializedJSON(table.c[name].type))
        for name in columns
        if name in table.c and isinstance(table.c[name].type, JSON)
    }


def generate_sql_filename(*, engine_url: str, table: str, operation: str) -> Path:
    """Genera un nombre de fichero SQL a partir de la URL del engine.

    El prefijo es la base de datos de la URL; si no la hay, ``service_name`` o ``sid`` (Oracle) y, en último caso, el
    nombre del motor. P-24 (performance-audit de bulk, 2026-09-24): antes lanzaba ``ValueError`` sin base de datos (p.ej.
    Oracle por ``?service_name=``), y como ``generar_sql=True`` es el valor por defecto rompía ``bulk_insert_from_df``.
    Se usa solo el último componente de la ruta, con los caracteres no válidos en nombres de fichero sustituidos: en
    SQLite una ruta absoluta sustituía a ``path_sql`` al unirlas y ``:memory:`` no era válido en Windows.

    El nombre de la tabla se sanea igual (auditoría de bulk 2026-09-24, hallazgo 6): con ``/`` o ``\\`` el fichero se
    creaba en otra carpeta (``..`` incluido) y con ``:`` u otros caracteres no válidos fallaba en Windows.
    """
    try:
        url = make_url(engine_url)
    except Exception as error:
        raise ValueError(f"No se pudo extraer nombre de BD de engine.url: {engine_url}") from error
    raw_name = url.database or url.query.get("service_name") or url.query.get("sid") or url.get_backend_name()
    if isinstance(raw_name, tuple):  # parámetros de query repetidos
        raw_name = raw_name[0]
    db_name: str = _safe_filename_part(Path(str(raw_name)).name) or url.get_backend_name()
    table_part: str = _safe_filename_part(table) or "tabla"

    timestamp: str = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(f"{db_name}-{table_part}-{operation.lower()}_{timestamp}.sql")


def _safe_filename_part(value: str) -> str:
    """Sustituye por ``_`` los caracteres no válidos en nombres de fichero, incluidos los separadores de ruta."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)


def _json_as_string_literals(table: TableClause, values: SqlRecord) -> SqlRecord:
    """Valores de columnas JSON como literal de cadena para la generación de SQL (P-20).

    ``literal_binds`` necesita un ``literal_processor`` y el tipo ``JSON`` de SQLAlchemy no tiene. El valor ya viene
    serializado por ``normalize_sql_literal``, así que se escribe como cadena, sin volver a serializar (coherente con
    P-19). ``None`` se mantiene para que se genere ``NULL``.
    """
    return {
        name: literal(value, String())
        if value is not None and name in table.c and isinstance(table.c[name].type, JSON)
        else value
        for name, value in values.items()
    }


# C-1 / P-30 (hotfix 2026-09-25): literal hexadecimal de los valores binarios, por dialecto. SQLAlchemy los renderiza
# como cadena ('abc'): SQLite la guarda como TEXT, SQL Server la rechaza (Msg 257) y Oracle la interpreta como hex
# (b"abc" → 0x0ABC, sin error); con bytes no UTF-8 falla y la fila caía a format_sql_param_value, cuyo 0x... solo
# aceptan SQL Server y MySQL. decode(..., 'hex') no depende de standard_conforming_strings en PostgreSQL.
# Un dialecto que no está aquí conserva el comportamiento anterior.
_HEX_STRING_LITERAL: str = "X'{}'"  # SQL estándar
_BINARY_LITERAL_FORMATS: dict[str, str] = {
    "sqlite": _HEX_STRING_LITERAL,
    "postgresql": "decode('{}', 'hex')",
    "mysql": _HEX_STRING_LITERAL,
    "mariadb": _HEX_STRING_LITERAL,
    "mssql": "0x{}",
    "oracle": "HEXTORAW('{}')",
}
_BYTES_TYPES = (bytes, bytearray, memoryview)  # sin anotar: mypy acota el tipo en isinstance


def _binary_or_value(column_type: TypeEngine[Any], value: Any, dialect: Any) -> Any:
    """En el camino por fila: el valor binario como ``literal_column`` con su literal del dialecto (C-1), o el valor."""
    literal_format: str | None = _BINARY_LITERAL_FORMATS.get(dialect.name)
    if literal_format is None or not isinstance(column_type, _Binary) or not isinstance(value, _BYTES_TYPES):
        return value
    return literal_column(literal_format.format(value.hex().upper()))


_MARKER: str = "__util_bbdd_literal_{}__"


@dataclass(frozen=True)
class _Slot:
    """Hueco de la plantilla: clave del registro, tipo de la columna y si está en el WHERE."""

    key: str
    type: TypeEngine[Any]
    json: bool = False
    where: bool = False


class _LiteralTemplate:
    """Sentencia compilada una vez con marcadores; cada fila solo renderiza sus literales (P-06).

    Antes se construía y compilaba una sentencia por fila con ``literal_binds`` (~165 µs/fila). Los literales se
    renderizan con ``render_literal_value`` del compilador del dialecto, la misma función que usa ``literal_binds``
    (o con el ``literal_processor`` al que esta se reduce, P-32), con el mismo tipo de parámetro que SQLAlchemy: el de
    la columna en VALUES/SET (``String`` para JSON, P-20) y ``coerce_compared_value`` en el WHERE. Como los valores no
    pasan por el compilador, SQLAlchemy ya no convierte en ``?`` un texto con forma ``%(nombre)s`` en dialectos
    posicionales (SQLite, SQL Server + pyodbc).

    ``render_block`` renderiza el bloque por columnas (P-31, performance-audit de serialización SQL 2026-09-25): un
    bucle por hueco con el renderizador ya resuelto, y cada línea se ensambla con una cadena de formato precalculada.
    Las filas que no se pueden renderizar igual que antes (``None`` en el WHERE, que SQLAlchemy convierte en
    ``IS NULL``; tipos sin renderizador de literales, como algunos binarios; en el INSERT, claves distintas de las de la
    plantilla) se generan, en su orden, por el camino anterior, que da el mismo resultado o el mismo error.
    """

    def __init__(
        self, stmt: Any, slots: Sequence[_Slot], dialect: Any, *, postprocess: Any = None, exact_keys: bool = False
    ) -> None:
        self._undouble: bool = bool(getattr(dialect.identifier_preparer, "_double_percents", False))
        sql: str = self._undo_percents(str(stmt.compile(dialect=dialect, compile_kwargs={"literal_binds": True})))
        if postprocess is not None:
            sql = postprocess(sql)
        self._parts, self._order, self._tail = self._split(sql, slots)
        self._keys: frozenset[str] | None = frozenset(slot.key for slot in slots) if exact_keys else None
        self._compiler: Any = dialect.statement_compiler(dialect, None)
        # Las partes fijas pueden llevar '%' (identificadores, OVERRIDING...): se escapan para el operador '%'.
        self._format: str = "".join(part.replace("%", "%%") + "%s" for part in self._parts) + self._tail.replace(
            "%", "%%"
        )
        # Tipo de render de VALUES/SET resuelto una vez: el de la columna, o ``String`` para JSON (P-20). En el WHERE
        # (``None``) depende del valor: ``coerce_compared_value``, como SQLAlchemy.
        self._types: list[TypeEngine[Any] | None] = [
            None if slot.where else String() if slot.json else slot.type for slot in self._order
        ]
        direct: bool = type(self._compiler).render_literal_value is SQLCompiler.render_literal_value
        self._processors: list[Callable[[Any], str] | None] = [
            self._processor(slot, type_, dialect, direct=direct)
            for slot, type_ in zip(self._order, self._types, strict=True)
        ]

    def _processor(
        self, slot: _Slot, type_: TypeEngine[Any] | None, dialect: Any, *, direct: bool
    ) -> Callable[[Any], str] | None:
        """Función valor no nulo → literal del hueco, o ``None`` para usar ``render_literal_value(valor, type_)``.

        - WHERE: el tipo depende del valor (``coerce_compared_value``, como SQLAlchemy).
        - P-32 (performance-audit de serialización SQL 2026-09-25): si el compilador no redefine
          ``render_literal_value`` (SQLite, SQL Server y Oracle en SQLAlchemy 2.0.50), para un valor no nulo esta se
          reduce a llamar al ``literal_processor`` del tipo, que se resuelve aquí una vez. PostgreSQL y MySQL/MariaDB la
          redefinen (escape de ``\\``) y siguen por ``render_literal_value``.
        - C-1 / P-30 (hotfix 2026-09-25): en columnas binarias, los ``bytes`` se escriben con el literal hexadecimal del
          dialecto (``_BINARY_LITERAL_FORMATS``); cualquier otro valor sigue el camino de su tipo.
        """
        literal_format: str | None = _BINARY_LITERAL_FORMATS.get(dialect.name)
        if literal_format is not None and isinstance(slot.type, _Binary):
            return self._binary_processor(slot, type_, literal_format)
        if type_ is None:
            render: Callable[[Any, TypeEngine[Any]], str] = self._compiler.render_literal_value
            column_type: TypeEngine[Any] = slot.type

            def where_literal(value: Any) -> str:
                return render(value, column_type.coerce_compared_value(operators.eq, value))

            return where_literal
        if direct:
            processor: Callable[[Any], str] | None = type_.dialect_impl(dialect).literal_processor(dialect)
            return processor
        return None

    def _binary_processor(
        self, slot: _Slot, type_: TypeEngine[Any] | None, literal_format: str
    ) -> Callable[[Any], str]:
        """Literal de un hueco binario: ``bytes`` en hexadecimal según el dialecto; el resto, como SQLAlchemy."""
        render: Callable[[Any, TypeEngine[Any]], str] = self._compiler.render_literal_value
        column_type: TypeEngine[Any] = slot.type

        def binary_literal(value: Any) -> str:
            if isinstance(value, _BYTES_TYPES):
                return literal_format.format(value.hex().upper())
            return render(value, type_ if type_ is not None else column_type.coerce_compared_value(operators.eq, value))

        return binary_literal

    def _undo_percents(self, sql: str) -> str:
        return sql.replace("%%", "%") if self._undouble else sql  # P-23

    @staticmethod
    def _split(sql: str, slots: Sequence[_Slot]) -> tuple[list[str], list[_Slot], str]:
        """Trocea la plantilla por sus marcadores, en el orden en que aparecen."""
        found: list[tuple[int, int]] = []
        for index in range(len(slots)):
            marker = _MARKER.format(index)
            if sql.count(marker) != 1:
                raise ValueError(f"marcador {marker} no encontrado una sola vez en la plantilla")
            found.append((sql.index(marker), index))
        parts: list[str] = []
        order: list[_Slot] = []
        previous = 0
        for position, index in sorted(found):
            parts.append(sql[previous:position])
            order.append(slots[index])
            previous = position + len(_MARKER.format(index))
        return parts, order, sql[previous:] + ";"

    def _render_column(self, index: int, records: Sequence[SqlRecord], fallback: bytearray) -> list[str | None]:
        """Literales del hueco ``index`` en cada fila; marca en ``fallback`` las filas que no se pueden renderizar."""
        slot: _Slot = self._order[index]
        fixed_type: TypeEngine[Any] | None = self._types[index]  # None solo en el WHERE, que siempre tiene processor
        processor: Callable[[Any], str] | None = self._processors[index]
        render: Callable[[Any, TypeEngine[Any] | None], str] = self._compiler.render_literal_value
        key, undouble = slot.key, self._undouble
        # NULL en VALUES/SET; en el WHERE SQLAlchemy genera IS NULL, que la plantilla no tiene: camino anterior.
        null_literal: str | None = None if slot.where else "NULL"
        column: list[str | None] = [None] * len(records)
        for row in [row for row, done in enumerate(fallback) if not done]:
            try:
                value = records[row][key]
                if value is None:
                    column[row] = null_literal
                    fallback[row] = null_literal is None
                    continue
                literal_sql: str = processor(value) if processor is not None else render(value, fixed_type)
            except Exception:  # sin renderizador para el tipo o valor no admitido: camino anterior
                fallback[row] = 1
                continue
            column[row] = literal_sql.replace("%%", "%") if undouble else literal_sql  # P-23
        return column

    def render_block(self, records: Sequence[SqlRecord], per_row: Callable[[SqlRecord], str]) -> list[str]:
        """Una línea por registro, en orden; ``per_row`` genera las filas que la plantilla no puede renderizar."""
        fallback = bytearray(len(records))
        if self._keys is not None:
            for row, record in enumerate(records):
                if record.keys() != self._keys:
                    fallback[row] = 1
        columns = [self._render_column(index, records, fallback) for index in range(len(self._order))]
        rows: Iterable[tuple[str | None, ...]] = zip(*columns, strict=True) if columns else [()] * len(records)
        template: str = self._format
        return [per_row(records[row]) if fallback[row] else template % literals for row, literals in enumerate(rows)]


def _markers(count: int, start: int = 0) -> list[Any]:
    return [literal_column(_MARKER.format(index)) for index in range(start, start + count)]


def _template_or_none(stmt: Any, slots: Sequence[_Slot], dialect: Any, **kwargs: Any) -> _LiteralTemplate | None:
    """Plantilla, o ``None`` si no se puede construir (se usa entonces el camino anterior para todas las filas)."""
    try:
        return _LiteralTemplate(stmt, slots, dialect, **kwargs)
    except Exception:
        return None


def _render_lines(template: _LiteralTemplate | None, records: Sequence[SqlRecord], per_row: Any) -> list[str]:
    if template is None:
        return [per_row(record) for record in records]
    return template.render_block(records, per_row)


def _generate_insert_lines(stmt: Insert, records: Sequence[SqlRecord], dialect: Any, postprocess: Any) -> list[str]:
    """INSERT literales; ``inline()`` evita el RETURNING/OUTPUT de la PK cuando el registro no la trae (P-29)."""
    table = stmt.table
    inline_stmt: Insert = stmt.inline()

    def per_row(record: SqlRecord) -> str:
        values: SqlRecord = {
            name: _binary_or_value(table.c[name].type, value, dialect) if name in table.c else value
            for name, value in _json_as_string_literals(table, record).items()
        }
        sql = compile_stmt_with_binary_support(inline_stmt.values(values), dialect)
        return postprocess(sql) if postprocess is not None else sql

    if not records:
        return []
    keys: list[str] = list(records[0])
    template: _LiteralTemplate | None = None
    if all(key in table.c for key in keys):
        slots = [_Slot(key, table.c[key].type, json=isinstance(table.c[key].type, JSON)) for key in keys]
        template_stmt = inline_stmt.values(dict(zip(keys, _markers(len(keys)), strict=True)))
        template = _template_or_none(template_stmt, slots, dialect, postprocess=postprocess, exact_keys=True)
    return _render_lines(template, records, per_row)


def _override_system_value(sql: str) -> str:
    return re.sub(r"\)\s+VALUES\b", ") OVERRIDING SYSTEM VALUE VALUES", sql, count=1, flags=re.IGNORECASE)


def generate_insert_sql(stmt: Insert, records: Sequence[SqlRecord], dialect: Any) -> list[str]:
    """Genera SQL INSERT literal para una secuencia de registros."""
    return _generate_insert_lines(stmt, records, dialect, None)


def generate_insert_sql_override_identity(stmt: Insert, records: Sequence[SqlRecord], dialect: Any) -> list[str]:
    """Genera SQL INSERT PostgreSQL con OVERRIDING SYSTEM VALUE para columnas identity always."""
    return _generate_insert_lines(stmt, records, dialect, _override_system_value)


def build_override_identity_text_stmt(table: Table, columns: Sequence[str], dialect: Any) -> Any:
    """Construye un text() INSERT con OVERRIDING SYSTEM VALUE para ejecución en PostgreSQL."""
    preparer = dialect.identifier_preparer
    quoted_table: str = preparer.format_table(table)
    quoted_cols: list[str] = [preparer.quote(col) for col in columns]
    params: list[str] = [f":{col}" for col in columns]
    sql: str = (
        f"INSERT INTO {quoted_table} ({', '.join(quoted_cols)}) OVERRIDING SYSTEM VALUE VALUES ({', '.join(params)})"
    )
    return text(sql)


def should_wrap_identity_insert(table: Table, insert_cols: Sequence[str], dialect: Any) -> bool:
    """Devuelve True si hay que envolver los INSERT con SET IDENTITY_INSERT ON/OFF.

    Solo aplica en MSSQL cuando alguna columna de insert_cols tiene IDENTITY definida
    en la tabla (getattr(col, 'identity', None) is not None).
    """
    if dialect.name != "mssql":
        return False
    col_set: set[str] = set(insert_cols)
    return any(col.name in col_set and getattr(col, "identity", None) is not None for col in table.columns)


def iter_identity_insert_sql(sql_lines: Iterable[str], table: Table, dialect: Any) -> Iterator[str]:
    """Como :func:`wrap_identity_insert_sql`, sin materializar las líneas (generación por bloques, P-07)."""
    quoted_table: str = dialect.identifier_preparer.format_table(table)
    yield f"SET IDENTITY_INSERT {quoted_table} ON;"
    yield from sql_lines
    yield f"SET IDENTITY_INSERT {quoted_table} OFF;"


def wrap_identity_insert_sql(sql_lines: list[str], table: Table, dialect: Any) -> list[str]:
    """Envuelve una lista de INSERT con SET IDENTITY_INSERT <tabla> ON/OFF para SQL Server."""
    return list(iter_identity_insert_sql(sql_lines, table, dialect))


def generate_update_sql(
    *,
    table: Table,
    records: Sequence[SqlRecord],
    update_cols: Sequence[str],
    pk_param_map: dict[str, str],
    pk_cols: Sequence[str],
    dialect: Any,
) -> list[str]:
    """Genera SQL UPDATE literal para una secuencia de registros."""

    def per_row(record: SqlRecord) -> str:
        update_values: dict[str, Any] = {
            column: _binary_or_value(table.c[column].type, value, dialect)
            for column, value in _json_as_string_literals(
                table, {column: record[column] for column in update_cols}
            ).items()
        }
        pk_conditions: dict[str, Any] = {
            pk_param_map[column]: _binary_or_value(table.c[column].type, record[pk_param_map[column]], dialect)
            for column in pk_cols
        }
        stmt: Update = (
            update(table)
            .where(and_(*(table.c[column] == pk_conditions[pk_param_map[column]] for column in pk_cols)))
            .values(update_values)
        )
        return compile_stmt_with_binary_support(stmt, dialect)

    set_markers = _markers(len(update_cols))
    where_markers = _markers(len(pk_cols), start=len(update_cols))
    template_stmt: Update = (
        update(table)
        .where(and_(*(table.c[column] == marker for column, marker in zip(pk_cols, where_markers, strict=True))))
        .values(dict(zip(update_cols, set_markers, strict=True)))
    )
    slots: list[_Slot] = [
        *(_Slot(c, table.c[c].type, json=isinstance(table.c[c].type, JSON)) for c in update_cols),
        *(_Slot(pk_param_map[c], table.c[c].type, where=True) for c in pk_cols),
    ]
    # El registro lleva además las columnas PK originales junto a sus alias: solo se leen las claves de los huecos.
    return _render_lines(_template_or_none(template_stmt, slots, dialect), records, per_row)


def generate_delete_sql(
    *,
    records: Sequence[SqlRecord],
    table: Table,
    pk_cols: Sequence[str],
    dialect: Any,
) -> list[str]:
    """Genera SQL DELETE literal para una secuencia de claves primarias."""

    def per_row(record: SqlRecord) -> str:
        conditions = [
            table.c[column] == _binary_or_value(table.c[column].type, record[column], dialect) for column in pk_cols
        ]
        stmt: Delete = delete(table).where(and_(*conditions))
        return compile_stmt_with_binary_support(stmt, dialect)

    where_markers = _markers(len(pk_cols))
    template_stmt: Delete = delete(table).where(
        and_(*(table.c[column] == marker for column, marker in zip(pk_cols, where_markers, strict=True)))
    )
    slots = [_Slot(column, table.c[column].type, where=True) for column in pk_cols]
    return _render_lines(_template_or_none(template_stmt, slots, dialect), records, per_row)


def _substitute_ordered_params(sql_text: str, ordered_params: list[Any]) -> str:
    """Sustituye parámetros ordenados usando placeholders %s o ?.

    BLK-05 (AUDIT_CODE 2026-09-22): localiza las posiciones de los placeholders
    en el ``sql_text`` original antes de sustituir, en vez de encadenar
    ``str.replace(..., 1)`` sobre el resultado parcial. Un valor de parámetro
    que contenga literalmente "%s" o "?" (p.ej. un BLOB/texto de usuario)
    podía ser reescaneado por la sustitución del siguiente parámetro y
    corromper el SQL generado.
    """
    if "%s" in sql_text:
        placeholder = "%s"
    elif "?" in sql_text:
        placeholder = "?"
    else:
        return sql_text

    positions: list[int] = [match.start() for match in re.finditer(re.escape(placeholder), sql_text)]
    if not positions:
        return sql_text

    placeholder_len = len(placeholder)
    result_parts: list[str] = []
    previous_end = 0
    for position, param_value in zip(positions, ordered_params, strict=False):
        result_parts.append(sql_text[previous_end:position])
        result_parts.append(format_sql_param_value(param_value))
        previous_end = position + placeholder_len
    result_parts.append(sql_text[previous_end:])
    return "".join(result_parts)


def _substitute_named_params(sql_text: str, params: dict[str, Any]) -> str:
    """Sustituye parámetros nombrados usando formatos %(name)s o :name.

    BLK-05 (AUDIT_CODE 2026-09-22): localiza todas las posiciones de
    placeholders en el ``sql_text`` original antes de sustituir, en vez de
    aplicar ``re.sub`` de forma incremental sobre el resultado parcial. Un
    valor ya sustituido que contuviera literalmente ":otro_param" o
    "%(otro_param)s" podía ser reescaneado y corromper sustituciones
    posteriores.
    """
    if not params:
        return sql_text

    matches: list[tuple[int, int, str]] = []
    for param_name in params:
        pattern = re.compile(rf"%\({re.escape(param_name)}\)s|:{re.escape(param_name)}\b")
        matches.extend((match.start(), match.end(), param_name) for match in pattern.finditer(sql_text))
    matches.sort(key=lambda item: item[0])

    result_parts: list[str] = []
    previous_end = 0
    for start, end, param_name in matches:
        if start < previous_end:
            continue
        result_parts.append(sql_text[previous_end:start])
        result_parts.append(format_sql_param_value(params[param_name]))
        previous_end = end
    result_parts.append(sql_text[previous_end:])
    return "".join(result_parts)


def _get_ordered_params(compiled: Any, params: dict[str, Any]) -> list[Any]:
    """Obtiene parámetros en orden desde positiontup o como lista de valores."""
    positiontup = getattr(compiled, "positiontup", None)
    if positiontup:
        return [params[name] for name in positiontup if name in params]
    return list(params.values())


def compile_stmt_with_binary_support(stmt: Any, dialect: Any) -> str:
    """Compila un statement con fallback para binarios no renderizables."""
    try:
        compiled = stmt.compile(dialect=dialect, compile_kwargs={"literal_binds": True})
        sql = str(compiled)
        # P-23 (performance-audit de bulk): con paramstyle format/pyformat (psycopg, PyMySQL...) SQLAlchemy duplica cada
        # '%' del texto (literales, identificadores) pensando en el driver; el fichero se ejecuta sin parámetros, así
        # que 'a%b' se guardaba como 'a%%b'. Con literal_binds no quedan placeholders: deshacer la duplicación es exacto.
        if getattr(dialect.identifier_preparer, "_double_percents", False):
            sql = sql.replace("%%", "%")
        return f"{sql};"
    except Exception as error:
        if "BLOB" not in str(error) and "binary" not in str(error).lower():
            raise

        compiled = stmt.compile(dialect=dialect)
        sql_text = str(compiled)
        params = compiled.params or {}
        if not params:
            return f"{sql_text};"

        ordered_params = _get_ordered_params(compiled, params)
        sql_text = _substitute_ordered_params(sql_text, ordered_params)
        if sql_text != str(compiled):
            return f"{sql_text};"

        sql_result = _substitute_named_params(sql_text, params)
        return f"{sql_result};"


def format_sql_param_value(value: Any) -> str:
    """Convierte un valor Python a su literal SQL."""
    if value is None:
        return "NULL"
    if isinstance(value, bytes):
        return f"0x{value.hex().upper()}"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (datetime, date, time)):
        return f"'{str(value)}'"
    if isinstance(value, str):
        escaped_value: str = value.replace("'", "''")
        return f"'{escaped_value}'"
    if isinstance(value, (int, float)):
        return str(value)

    string_value: str = str(value)
    escaped_string: str = string_value.replace("'", "''")
    return f"'{escaped_string}'"


__all__: list[str] = [
    "PreSerializedJSON",
    "SqlRecord",
    "build_override_identity_text_stmt",
    "compile_stmt_with_binary_support",
    "format_sql_param_value",
    "generate_delete_sql",
    "generate_insert_sql",
    "generate_insert_sql_override_identity",
    "generate_sql_filename",
    "generate_update_sql",
    "iter_identity_insert_sql",
    "json_passthrough_binds",
    "restore_binary_values",
    "should_wrap_identity_insert",
    "wrap_identity_insert_sql",
]
