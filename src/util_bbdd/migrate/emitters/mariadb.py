"""Emisor DDL para MariaDB.

Responsabilidades:
  - Generar CREATE TABLE con backticks, ENGINE=InnoDB, charset y collation.
  - Ordenar tablas topológicamente (FKs primero la tabla referenciada).
  - Detectar FKs circulares y emitirlas como ALTER TABLE al final.
  - Incluir comentarios -- AVISO: para tipos sin equivalente exacto.
  - Columnas omitidas (ROWID) aparecen como línea comentada en el DDL.
"""

from __future__ import annotations

import re

from collections import deque

from ..charset import validate_storage_engine
from ..ir.models import CanonicalColumn, CanonicalFK, CanonicalRoutine, CanonicalTable, CanonicalView
from ._comment_limits import MYSQL_COLUMN_COMMENT, MYSQL_TABLE_COMMENT, fit_comment
from ._default_fallback import default_fallback_warning
from ._trailing_comment import join_definitions, one_line, with_trailing_comment


def _bt(name: str) -> str:
    """Escapa un identificador MariaDB con backticks."""
    return f"`{name.replace('`', '``')}`"


#: Display width convencional de MariaDB/MySQL por tipo entero, aplicado a columnas
#: AUTO_INCREMENT cuando target_type no trae ya uno propio (p.ej. "BIGINT" sin ancho
#: mapeado por sqlserver_to_mariadb/postgresql_to_mariadb, a diferencia de oracle_to_mariadb
#: que sí aplica _with_int_width a "INT").
_AUTO_INCREMENT_DISPLAY_WIDTH: dict[str, int] = {
    "TINYINT": 4,
    "SMALLINT": 6,
    "MEDIUMINT": 9,
    "INT": 11,
    "INTEGER": 11,
    "BIGINT": 20,
}


def _auto_increment_col_type(target_type: str) -> str:
    """Tipo MariaDB para una columna AUTO_INCREMENT, preservando el ancho del tipo origen.

    Antes de este fix el emitter forzaba ``INT(11)`` para toda columna AUTO_INCREMENT
    sin importar el tipo fuente, lo que descartaba en silencio BIGINT/SMALLINT y
    arriesgaba overflow en PKs grandes migradas desde SQL Server/Oracle/PostgreSQL.

    Si ``target_type`` ya trae un display width propio (p.ej. ``"BIGINT(20)"`` de
    Oracle NUMBER sin precisión, o ``"INT(11)"`` de ``_with_int_width``), se preserva
    tal cual. Si no lo trae (p.ej. ``"BIGINT"``/``"SMALLINT"`` mapeados por los
    transformers de SQL Server/PostgreSQL), se aplica el display width convencional
    de MariaDB para ese tipo entero base. Un ``target_type`` que no sea uno de los
    tipos enteros reconocidos (no debería ocurrir: solo columnas PK/secuencia enteras
    se marcan auto_increment) se devuelve sin modificar.
    """
    if "(" in target_type:
        return target_type
    base = target_type.upper().strip()
    width = _AUTO_INCREMENT_DISPLAY_WIDTH.get(base)
    return f"{base}({width})" if width else target_type


class MariaDBDDLEmitter:
    """Genera DDL MariaDB desde IR canónico.

    Args:
        charset: CHARACTER SET para tablas y columnas de texto (obligatorio).
        collation: COLLATE para tablas (obligatorio).
        engine: Motor de almacenamiento (default: InnoDB).
    """

    def __init__(
        self,
        charset: str,
        collation: str,
        engine: str = "InnoDB",
    ) -> None:
        self._charset = charset
        self._collation = collation
        self._engine = validate_storage_engine(engine)  # A9: va sin comillas en ENGINE=...

    # ─── API pública ──────────────────────────────────────────────────────────

    def emit(
        self,
        tables: list[CanonicalTable],
        views: list[CanonicalView] | None = None,
        routines: list[CanonicalRoutine] | None = None,
    ) -> str:
        """Genera el script DDL completo listo para guardar en fichero .sql.

        Args:
            tables: Tablas canónicas transformadas, ordenadas topológicamente.
            views: Vistas canónicas transformadas. Se emiten después de las tablas.
            routines: Rutinas canónicas transformadas. Se emiten al final.

        Returns:
            Script SQL con sentencias separadas por ';\\n\\n' y terminado en ';\\n'.
        """
        stmts = self.emit_statements(tables, views, routines)
        return ";\n\n".join(stmts) + ";\n"

    def emit_statements(
        self,
        tables: list[CanonicalTable],
        views: list[CanonicalView] | None = None,
        routines: list[CanonicalRoutine] | None = None,
    ) -> list[str]:
        """Genera lista de sentencias DDL individuales sin ';' al final.

        Args:
            tables: Tablas canónicas transformadas, ordenadas topológicamente.
            views: Vistas canónicas transformadas. Se emiten después de las tablas.
            routines: Rutinas canónicas transformadas. Se emiten al final.

        Returns:
            Lista de sentencias DDL (CREATE TABLE, CREATE INDEX, ALTER TABLE,
            CREATE OR REPLACE VIEW, CREATE PROCEDURE/FUNCTION) en el orden
            correcto para ejecución.
        """
        ordered, circular_fk_pairs = _topological_sort(tables)

        # Recopilar FKs externas (a tablas fuera del schema migrado)
        external_fk_pairs: list[tuple[str, CanonicalFK]] = []
        for table in ordered:
            for fk in table.foreign_keys:
                if fk.is_external:
                    external_fk_pairs.append((table.name, fk))

        statements: list[str] = []

        for table in ordered:
            skip_fk_names = {fk.name for _, fk in circular_fk_pairs if _ == table.name}
            stmt = self._emit_create_table(table, skip_fk_names=skip_fk_names)
            statements.append(stmt)

        # Índices separados (no-PK, no-inline-UNIQUE)
        for table in ordered:
            for stmt in self._emit_indexes(table):
                statements.append(stmt)

        # ALTER TABLE para FKs circulares
        for table_name, fk in circular_fk_pairs:
            stmt = self._emit_alter_table_add_fk(table_name, fk)
            statements.append(stmt)

        # ALTER TABLE para FKs externas (al final, con comentario)
        for table_name, fk in external_fk_pairs:
            fk_stmt = self._emit_alter_table_add_fk(table_name, fk)
            stmt = (
                f"-- FK externa: `{one_line(fk.name)}` en `{one_line(table_name)}` referencia "
                f"`{one_line(fk.ref_table)}` (fuera del schema migrado) — verificar que existe\n"
                f"{fk_stmt}"
            )
            statements.append(stmt)

        # Vistas DESPUÉS de todas las tablas
        statements.extend(self._emit_view_statements(views))

        # Rutinas AL FINAL
        statements.extend(self._emit_routine_statements(routines))

        return statements

    def _emit_routine_statements(self, routines: list[CanonicalRoutine] | None) -> list[str]:
        return [self._emit_create_routine(r) for r in (routines or [])]

    def _emit_create_routine(self, routine: CanonicalRoutine) -> str:
        lines: list[str] = []
        if routine.is_package_member:
            pkg = routine.package_name or routine.name
            lines.append(
                f"-- PACKAGE MEMBER: {one_line(pkg)}.{one_line(routine.name)} ({one_line(routine.routine_type)})\n"
                f"-- No direct equivalent in MariaDB; manual migration required"
            )
        lines.append(f"-- {one_line(routine.routine_type)}: {one_line(_bt(routine.name))}")
        if routine.warnings:
            lines.append("-- NOTE: requires manual review (see migration warnings)")
        if routine.comment:
            lines.append(f"-- COMMENT: {one_line(routine.comment)}")
        if not routine.body:
            lines.append(
                f"-- TODO: {one_line(routine.routine_type)} {one_line(_bt(routine.name))} — "
                f"body not available; manual implementation required"
            )
            return "\n".join(lines)
        lines.append(routine.body)
        return "\n".join(lines)

    def _emit_view_statements(self, views: list[CanonicalView] | None) -> list[str]:
        active = [v for v in (views or []) if v.query]
        ordered, circular = _topological_sort_views(active)
        stmts: list[str] = [self._emit_create_view(v) for v in ordered]
        for v in circular:
            aviso = (
                f"-- AVISO: vista '{one_line(v.name)}' participa en una dependencia circular "
                "— verificar orden de ejecución manualmente\n"
            )
            stmts.append(aviso + self._emit_create_view(v))
        return stmts

    # ─── CREATE TABLE ─────────────────────────────────────────────────────────

    def _emit_create_table(self, table: CanonicalTable, skip_fk_names: set[str]) -> str:
        lines: list[str] = [f"CREATE TABLE {_bt(table.name)} ("]
        comment_lines: list[str] = []
        ddl_lines: list[str] = []

        for col in table.columns:
            line = self._emit_column(col, table.name)
            if col.omit:
                comment_lines.append(line)
            else:
                ddl_lines.append(line)

        if table.primary_key:
            pk_cols = ", ".join(_bt(c) for c in table.primary_key)
            ddl_lines.append(f"  PRIMARY KEY ({pk_cols})")

        for fk in table.foreign_keys:
            if fk.is_external:
                continue
            if fk.name in skip_fk_names:
                continue
            ddl_lines.append(self._emit_fk_inline(fk))

        if not ddl_lines:
            comment_lines.append("  -- ERROR: tabla sin columnas activas tras omisión de tipos incompatibles")

        body_parts: list[str] = []
        if comment_lines:
            body_parts.append("\n".join(comment_lines))
        if ddl_lines:
            body_parts.append(join_definitions(ddl_lines))

        lines.append("\n".join(body_parts))
        lines.append(f") ENGINE={self._engine} DEFAULT CHARSET={self._charset} COLLATE={self._collation}")
        if table.comment:
            comment = fit_comment(table.warnings, table.name, None, table.comment, MYSQL_TABLE_COMMENT, "MySQL/MariaDB")
            lines[-1] += f" COMMENT='{_mysql_text(comment)}'"

        return "\n".join(lines)

    def _emit_column(self, col: CanonicalColumn, table_name: str) -> str:
        if col.omit:
            comment = one_line(col.ddl_comment or f"-- AVISO: columna '{col.original_name}' omitida")
            return f"  {comment}"

        col_type = _auto_increment_col_type(col.target_type) if col.auto_increment else col.target_type
        parts = [f"  {_bt(col.name)}", col_type]

        if not col.nullable:
            parts.append("NOT NULL")

        if col.auto_increment:
            parts.append("AUTO_INCREMENT")
        elif col.default is not None:
            default_val = _with_timestamp_precision(_format_default(col.default), col_type)
            parts.append(f"DEFAULT {default_val}")
            fallback_warning = default_fallback_warning(
                raw_value=col.default,
                formatted_value=default_val,
                table=table_name,
                column=col.name,
                source_type=col.source_type,
                target_type=col.target_type,
            )
            if fallback_warning is not None and fallback_warning not in col.warnings:
                col.warnings.append(fallback_warning)

        if col.comment:
            comment = fit_comment(
                col.warnings, table_name, col.name, col.comment, MYSQL_COLUMN_COMMENT, "MySQL/MariaDB"
            )
            parts.append(f"COMMENT '{_mysql_text(comment)}'")

        line = " ".join(parts)

        if col.ddl_comment:
            line = with_trailing_comment(line, col.ddl_comment)

        return line

    def _emit_fk_inline(self, fk: CanonicalFK) -> str:
        cols = ", ".join(_bt(c) for c in fk.columns)
        ref_cols = ", ".join(_bt(c) for c in fk.ref_columns)
        stmt = f"  CONSTRAINT {_bt(fk.name)} FOREIGN KEY ({cols}) REFERENCES {_bt(fk.ref_table)} ({ref_cols})"
        if fk.on_delete and fk.on_delete.upper() not in ("NO ACTION", ""):
            stmt += f" ON DELETE {fk.on_delete.upper()}"
        if fk.on_update and fk.on_update.upper() not in ("NO ACTION", ""):
            stmt += f" ON UPDATE {fk.on_update.upper()}"
        return stmt

    def _emit_alter_table_add_fk(self, table_name: str, fk: CanonicalFK) -> str:
        fk_inline = self._emit_fk_inline(fk).strip()
        return f"ALTER TABLE {_bt(table_name)} ADD {fk_inline}"

    # ─── Vistas ───────────────────────────────────────────────────────────────

    def _emit_create_view(self, view: CanonicalView) -> str:
        lines: list[str] = []
        if view.warnings:
            lines.append("-- NOTE: requires manual review (see migration warnings)")
        if view.comment:
            lines.append(f"-- COMMENT: {one_line(view.comment)}")
        lines.append(f"CREATE OR REPLACE VIEW {_bt(view.name)} AS")
        lines.append(view.query)
        return "\n".join(lines)

    # ─── Índices ──────────────────────────────────────────────────────────────

    def _emit_indexes(self, table: CanonicalTable) -> list[str]:
        pk_set = {c.upper() for c in table.primary_key}
        omitted_cols = {col.name.upper() for col in table.columns if col.omit}
        stmts: list[str] = []

        for idx in table.indexes:
            idx_col_set = {c.upper() for c in idx.columns}
            # Omitir el índice PK (ya en CREATE TABLE)
            if idx_col_set == pk_set and idx.unique:
                continue
            # Omitir índices que referencian columnas omitidas
            if idx_col_set & omitted_cols:
                continue

            unique_kw = "UNIQUE " if idx.unique else ""
            cols = ", ".join(_bt(c) for c in idx.columns)
            stmt = f"CREATE {unique_kw}INDEX {_bt(idx.name)} ON {_bt(table.name)} ({cols})"
            stmts.append(stmt)

        return stmts


# ─── Topological sort ─────────────────────────────────────────────────────────


def _detect_view_deps(view: CanonicalView, all_views: list[CanonicalView]) -> set[str]:
    """Detecta nombres de vistas del schema referenciadas en view.query.

    Comprueba tanto el nombre final (posiblemente truncado) como el
    original_name de Oracle, para cubrir vistas con identificadores truncados.
    """
    deps: set[str] = set()
    query_upper = view.query.upper()
    for candidate in all_views:
        if candidate.name == view.name:
            continue
        for check_name in (candidate.name, candidate.original_name):
            if re.search(r"\b" + re.escape(check_name.upper()) + r"\b", query_upper):
                deps.add(candidate.name)
                break
    return deps


def _topological_sort_views(
    views: list[CanonicalView],
) -> tuple[list[CanonicalView], list[CanonicalView]]:
    """Ordena vistas por dependencias entre sí (algoritmo de Kahn).

    Detecta dependencias buscando nombres de otras vistas del schema como
    identificadores completos (\\bNAME\\b, case-insensitive) en la query
    reescrita. Es best-effort: no usa parser SQL.

    Returns:
        (ordered, circular) — circular contiene vistas en ciclos, que se
        emiten al final con un comentario de aviso.
    """
    if not views:
        return [], []

    name_to_view: dict[str, CanonicalView] = {v.name: v for v in views}
    deps: dict[str, set[str]] = {v.name: _detect_view_deps(v, views) for v in views}
    in_degree: dict[str, int] = {name: len(d) for name, d in deps.items()}

    queue: deque[str] = deque(n for n, d in in_degree.items() if d == 0)
    ordered: list[CanonicalView] = []

    while queue:
        name = queue.popleft()
        ordered.append(name_to_view[name])
        for other_name, other_deps in deps.items():
            if name in other_deps:
                other_deps.discard(name)
                in_degree[other_name] -= 1
                if in_degree[other_name] == 0:
                    queue.append(other_name)

    visited = {v.name for v in ordered}
    circular = [v for v in views if v.name not in visited]
    return ordered, circular


def _topological_sort(
    tables: list[CanonicalTable],
) -> tuple[list[CanonicalTable], list[tuple[str, CanonicalFK]]]:
    """Ordena tablas por dependencias FK (Kahn's algorithm).

    Returns:
        (ordered_tables, circular_fk_pairs)
        circular_fk_pairs: [(table_name, CanonicalFK)] para FKs en ciclos.
    """
    name_to_table: dict[str, CanonicalTable] = {t.name: t for t in tables}
    all_names: set[str] = set(name_to_table.keys())

    deps = _build_deps(tables, all_names)
    in_degree: dict[str, int] = {n: len(d) for n, d in deps.items()}
    result = _kahn_result(deps, in_degree, name_to_table)

    visited = {t.name for t in result}
    circular_tables = [t for t in tables if t.name not in visited]
    result.extend(circular_tables)

    return result, _collect_circular_fk_pairs(circular_tables, visited)


def _build_deps(
    tables: list[CanonicalTable],
    all_names: set[str],
) -> dict[str, set[str]]:
    """Construye mapa de dependencias FK internas entre tablas del schema."""
    deps: dict[str, set[str]] = {t.name: set() for t in tables}
    for table in tables:
        for fk in table.foreign_keys:
            if not fk.is_external and fk.ref_table in all_names and fk.ref_table != table.name:
                deps[table.name].add(fk.ref_table)
    return deps


def _kahn_result(
    deps: dict[str, set[str]],
    in_degree: dict[str, int],
    name_to_table: dict[str, CanonicalTable],
) -> list[CanonicalTable]:
    """Ejecuta el algoritmo de Kahn y devuelve las tablas en orden topológico."""
    queue: deque[str] = deque(n for n in in_degree if in_degree[n] == 0)
    result: list[CanonicalTable] = []
    while queue:
        name = queue.popleft()
        result.append(name_to_table[name])
        for other, other_deps in deps.items():
            if name in other_deps:
                other_deps.discard(name)
                in_degree[other] -= 1
                if in_degree[other] == 0:
                    queue.append(other)
    return result


def _collect_circular_fk_pairs(
    tables: list[CanonicalTable],
    visited: set[str],
) -> list[tuple[str, CanonicalFK]]:
    """Retorna pares (tabla, FK) para las FKs que forman ciclos."""
    return [
        (table.name, fk)
        for table in tables
        for fk in table.foreign_keys
        if not fk.is_external and fk.ref_table not in visited
    ]


_FRACTIONAL_TEMPORAL_RE: re.Pattern[str] = re.compile(r"^(DATETIME|TIMESTAMP)\s*\(\s*([1-6])\s*\)", re.IGNORECASE)


def _with_timestamp_precision(default_val: str, column_type: str) -> str:
    """``CURRENT_TIMESTAMP`` con la precisión de la columna (``DATETIME(6)`` → ``CURRENT_TIMESTAMP(6)``).

    MySQL rechaza ``DATETIME(6) DEFAULT CURRENT_TIMESTAMP`` ("Invalid default value"): la precisión del default debe
    coincidir con la de la columna.
    """
    if default_val.upper() not in {"CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP()", "NOW()"}:
        return default_val
    match = _FRACTIONAL_TEMPORAL_RE.match(column_type.strip())
    return f"CURRENT_TIMESTAMP({match.group(2)})" if match else default_val


def _format_default(value: str) -> str:
    """Formatea un valor DEFAULT para DDL MariaDB."""
    if not value:
        return "NULL"

    v = value.strip()

    # Funciones SQL conocidas (Oracle y MariaDB): pasar sin entrecomillar
    sql_functions = {
        "NOW()",
        "CURRENT_TIMESTAMP",
        "CURRENT_DATE",
        "NULL",
        "0",
        "1",
        "SYSDATE",
        "SYSTIMESTAMP",
        "SYS_GUID()",
        "USER",
    }
    if v.upper() in {f.upper() for f in sql_functions}:
        return v

    # Funciones temporales con argumento de precisión, ej. NOW(3), CURRENT_TIMESTAMP(6)
    if re.match(
        r"^(NOW|CURRENT_TIMESTAMP|CURRENT_DATE|CURRENT_TIME|SYSDATE|SYSTIMESTAMP)\s*\(\s*\d*\s*\)$",
        v,
        re.IGNORECASE,
    ):
        return v

    # Valores numéricos
    try:
        float(v)
        return v
    except ValueError:
        pass

    # String literal ya entrecomillado en forma canónica (comillas internas duplicadas; Oracle almacena DATA_DEFAULT
    # con comillas, p.ej. '6'): en MariaDB/MySQL la barra también escapa (A4)
    if len(v) >= 2 and v.startswith("'") and v.endswith("'"):
        return "'" + v[1:-1].replace("\\", "\\\\") + "'"

    # String literal sin entrecomillar
    return f"'{_mysql_text(v)}'"


def _mysql_text(text: str) -> str:
    """Contenido de un literal de texto MariaDB/MySQL: la barra invertida escapa (A4) y la comilla se duplica."""
    return text.replace("\\", "\\\\").replace("'", "''")


__all__: list[str] = [
    "MariaDBDDLEmitter",
]
