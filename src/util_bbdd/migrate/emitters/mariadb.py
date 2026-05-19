"""Emisor DDL para MariaDB.

Responsabilidades:
  - Generar CREATE TABLE con backticks, ENGINE=InnoDB, charset y collation.
  - Ordenar tablas topológicamente (FKs primero la tabla referenciada).
  - Detectar FKs circulares y emitirlas como ALTER TABLE al final.
  - Incluir comentarios -- AVISO: para tipos sin equivalente exacto.
  - Columnas omitidas (ROWID) aparecen como línea comentada en el DDL.
"""

from __future__ import annotations

from collections import deque

from ..ir.models import CanonicalColumn, CanonicalFK, CanonicalTable


def _bt(name: str) -> str:
    """Escapa un identificador MariaDB con backticks."""
    return f"`{name.replace('`', '``')}`"


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
        self._engine = engine

    # ─── API pública ──────────────────────────────────────────────────────────

    def emit(self, tables: list[CanonicalTable]) -> str:
        """Genera el script DDL completo listo para guardar en fichero .sql.

        Args:
            tables: Tablas canónicas transformadas, ordenadas topológicamente.

        Returns:
            Script SQL con sentencias separadas por ';\\n\\n' y terminado en ';\\n'.
        """
        stmts = self.emit_statements(tables)
        return ";\n\n".join(stmts) + ";\n"

    def emit_statements(self, tables: list[CanonicalTable]) -> list[str]:
        """Genera lista de sentencias DDL individuales sin ';' al final.

        Args:
            tables: Tablas canónicas transformadas, ordenadas topológicamente.

        Returns:
            Lista de sentencias DDL (CREATE TABLE, CREATE INDEX, ALTER TABLE)
            en el orden correcto para ejecución sin desactivar FK_CHECKS.
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
                f"-- FK externa: `{fk.name}` en `{table_name}` referencia "
                f"`{fk.ref_table}` (fuera del schema migrado) — verificar que existe\n"
                f"{fk_stmt}"
            )
            statements.append(stmt)

        return statements

    # ─── CREATE TABLE ─────────────────────────────────────────────────────────

    def _emit_create_table(self, table: CanonicalTable, skip_fk_names: set[str]) -> str:
        lines: list[str] = [f"CREATE TABLE {_bt(table.name)} ("]
        comment_lines: list[str] = []
        ddl_lines: list[str] = []

        for col in table.columns:
            line = self._emit_column(col)
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
            comment_lines.append(
                "  -- ERROR: tabla sin columnas activas tras omisión de tipos incompatibles"
            )

        body_parts: list[str] = []
        if comment_lines:
            body_parts.append("\n".join(comment_lines))
        if ddl_lines:
            body_parts.append(",\n".join(ddl_lines))

        lines.append("\n".join(body_parts))
        lines.append(f") ENGINE={self._engine} DEFAULT CHARSET={self._charset} COLLATE={self._collation}")
        if table.comment:
            escaped = table.comment.replace("'", "''")
            lines[-1] += f" COMMENT='{escaped}'"

        return "\n".join(lines)

    def _emit_column(self, col: CanonicalColumn) -> str:
        if col.omit:
            comment = col.ddl_comment or f"-- AVISO: columna '{col.original_name}' omitida"
            return f"  {comment}"

        parts = [f"  {_bt(col.name)}", col.target_type]

        if not col.nullable:
            parts.append("NOT NULL")

        if col.auto_increment:
            parts.append("AUTO_INCREMENT")
        elif col.default is not None:
            default_val = _format_default(col.default)
            parts.append(f"DEFAULT {default_val}")

        if col.comment:
            escaped = col.comment.replace("'", "''")
            parts.append(f"COMMENT '{escaped}'")

        line = " ".join(parts)

        if col.ddl_comment:
            line = f"{line} {col.ddl_comment}"

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


def _format_default(value: str) -> str:
    """Formatea un valor DEFAULT para DDL MariaDB."""
    if not value:
        return "NULL"

    v = value.strip()

    # Funciones SQL conocidas (Oracle y MariaDB): pasar sin entrecomillar
    sql_functions = {
        "NOW()", "CURRENT_TIMESTAMP", "CURRENT_DATE", "NULL", "0", "1",
        "SYSDATE", "SYSTIMESTAMP", "SYS_GUID()", "USER",
    }
    if v.upper() in {f.upper() for f in sql_functions}:
        return v

    # Valores numéricos
    try:
        float(v)
        return v
    except ValueError:
        pass

    # String literal
    escaped = v.replace("'", "''")
    return f"'{escaped}'"


__all__: list[str] = [
    "MariaDBDDLEmitter",
]
