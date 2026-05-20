"""Emisor DDL para Oracle.

Responsabilidades:
  - Generar CREATE TABLE con identificadores en "MAYÚSCULAS" (double-quoted).
  - Emitir CREATE SEQUENCE + CREATE OR REPLACE TRIGGER para columnas AUTO_INCREMENT.
  - Emitir COMMENT ON TABLE / COMMENT ON COLUMN para comentarios.
  - Ordenar tablas topológicamente (FKs primero la tabla referenciada).
  - Detectar FKs circulares y emitirlas como ALTER TABLE al final.
  - Emitir FK externas como ALTER TABLE con comentario al final del script.
  - Omitir ON UPDATE en FKs (Oracle solo soporta ON DELETE CASCADE/SET NULL).
  - Incluir comentarios -- AVISO: para tipos sin equivalente exacto.

Nota sobre identificadores Oracle:
  Los identificadores se emiten en mayúsculas y entre comillas dobles ("NAME")
  para preservar el nombre exacto. Oracle almacena identificadores sin comillas
  en mayúsculas, y entre comillas respetando la capitalización original.
  Usar siempre mayúsculas garantiza comportamiento predecible.

Secuencias y triggers para AUTO_INCREMENT:
  Oracle < 12c no tiene columnas IDENTITY nativas. Se genera el patrón clásico:
    CREATE SEQUENCE "TABLE_SEQ" START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE;
    CREATE OR REPLACE TRIGGER "TRG_TABLE"
      BEFORE INSERT ON "TABLE" FOR EACH ROW
    BEGIN
      IF :NEW."COL" IS NULL THEN
        SELECT "TABLE_SEQ".NEXTVAL INTO :NEW."COL" FROM DUAL;
      END IF;
    END;
  Oracle 12c+ tiene GENERATED AS IDENTITY; v1 usa el patrón clásico por
  compatibilidad con Oracle 11g y versiones anteriores.
"""

from __future__ import annotations

from ..ir.models import CanonicalColumn, CanonicalFK, CanonicalTable, CanonicalView
from .mariadb import _topological_sort, _topological_sort_views

# Límite seguro para nombres de secuencia/trigger derivados del nombre de tabla
# (26 chars prefix + "_SEQ" o "TRG_" = 30 chars, límite Oracle 12.1)
_MAX_ORA_PREFIX: int = 26

# Oracle ON DELETE acciones soportadas
_ORACLE_ON_DELETE_SUPPORTED: frozenset[str] = frozenset({"CASCADE", "SET NULL"})

# Traducción de defaults MariaDB a equivalentes Oracle
_MARIADB_TO_ORA_DEFAULTS: dict[str, str] = {
    "NOW()": "SYSDATE",
    "CURRENT_TIMESTAMP": "SYSDATE",
    "CURRENT_DATE": "TRUNC(SYSDATE)",
    "CURDATE()": "TRUNC(SYSDATE)",
    "CURTIME()": "NULL",
    "NULL": "NULL",
    "0": "0",
    "1": "1",
    "SYSDATE": "SYSDATE",
    "SYSTIMESTAMP": "SYSTIMESTAMP",
    "TRUE": "1",
    "FALSE": "0",
}


def _dq(name: str) -> str:
    """Escapa un identificador Oracle con comillas dobles (uppercase)."""
    return f'"{name.upper().replace(chr(34), chr(34) + chr(34))}"'


def _seq_name(table_name: str) -> str:
    """Genera el nombre de secuencia para una tabla (max 30 chars)."""
    prefix = table_name.upper()[:_MAX_ORA_PREFIX]
    return f"{prefix}_SEQ"


def _trg_name(table_name: str) -> str:
    """Genera el nombre de trigger para una tabla (max 30 chars)."""
    prefix = table_name.upper()[:_MAX_ORA_PREFIX]
    return f"TRG_{prefix}"


class OracleDDLEmitter:
    """Genera DDL Oracle desde IR canónico.

    Emite:
    - CREATE TABLE con columnas, PK inline y FKs internas (no circulares).
    - CREATE SEQUENCE + CREATE OR REPLACE TRIGGER por cada columna AUTO_INCREMENT.
    - COMMENT ON TABLE / COMMENT ON COLUMN para tablas y columnas con comentarios.
    - CREATE INDEX para índices no-PK.
    - ALTER TABLE ... ADD CONSTRAINT para FKs circulares y externas.
    - CREATE OR REPLACE VIEW para vistas.
    """

    # ─── API pública ──────────────────────────────────────────────────────────

    def emit(
        self,
        tables: list[CanonicalTable],
        views: list[CanonicalView] | None = None,
    ) -> str:
        """Genera el script DDL Oracle completo listo para guardar en fichero .sql.

        Returns:
            Script SQL con sentencias separadas por ';\\n\\n' y terminado en ';\\n'.
        """
        stmts = self.emit_statements(tables, views)
        return ";\n\n".join(stmts) + ";\n"

    def emit_statements(
        self,
        tables: list[CanonicalTable],
        views: list[CanonicalView] | None = None,
    ) -> list[str]:
        """Genera lista de sentencias DDL individuales sin ';' al final.

        Orden de emisión:
        1. CREATE TABLE (ordenadas topológicamente)
        2. CREATE SEQUENCE + CREATE OR REPLACE TRIGGER (AUTO_INCREMENT)
        3. COMMENT ON TABLE / COMMENT ON COLUMN
        4. CREATE [UNIQUE] INDEX (no-PK)
        5. ALTER TABLE ADD CONSTRAINT (FKs circulares)
        6. ALTER TABLE ADD CONSTRAINT (FKs externas, con comentario)
        7. CREATE OR REPLACE VIEW (ordenadas topológicamente)
        """
        ordered, circular_fk_pairs = _topological_sort(tables)

        external_fk_pairs: list[tuple[str, CanonicalFK]] = [
            (t.name, fk) for t in ordered for fk in t.foreign_keys if fk.is_external
        ]

        statements: list[str] = []

        # CREATE TABLE
        for table in ordered:
            skip_fk_names = {fk.name for _, fk in circular_fk_pairs if _ == table.name}
            statements.append(self._emit_create_table(table, skip_fk_names=skip_fk_names))

        # SEQUENCE + TRIGGER para AUTO_INCREMENT
        for table in ordered:
            statements.extend(self._emit_sequences_and_triggers(table))

        # COMMENT ON TABLE / COMMENT ON COLUMN
        for table in ordered:
            statements.extend(self._emit_comments(table))

        # CREATE INDEX
        for table in ordered:
            statements.extend(self._emit_indexes(table))

        # ALTER TABLE (FKs circulares)
        for table_name, fk in circular_fk_pairs:
            statements.append(self._emit_alter_table_add_fk(table_name, fk))

        # ALTER TABLE (FKs externas)
        for table_name, fk in external_fk_pairs:
            fk_stmt = self._emit_alter_table_add_fk(table_name, fk)
            stmt = (
                f"-- FK externa: {_dq(fk.name)} en {_dq(table_name)} referencia "
                f"{_dq(fk.ref_table)} (fuera del schema migrado) — verificar que existe\n"
                f"{fk_stmt}"
            )
            statements.append(stmt)

        # Vistas DESPUÉS de todas las tablas
        statements.extend(self._emit_view_statements(views))

        return statements

    # ─── CREATE TABLE ─────────────────────────────────────────────────────────

    def _emit_create_table(self, table: CanonicalTable, skip_fk_names: set[str]) -> str:
        lines: list[str] = [f"CREATE TABLE {_dq(table.name)} ("]
        comment_lines: list[str] = []
        ddl_lines: list[str] = []

        for col in table.columns:
            line = self._emit_column(col)
            if col.omit:
                comment_lines.append(line)
            else:
                ddl_lines.append(line)

        if table.primary_key:
            pk_name = f"PK_{table.name.upper()}"[:30]
            pk_cols = ", ".join(_dq(c) for c in table.primary_key)
            ddl_lines.append(f"    CONSTRAINT {_dq(pk_name)} PRIMARY KEY ({pk_cols})")

        for fk in table.foreign_keys:
            if fk.is_external:
                continue
            if fk.name in skip_fk_names:
                continue
            ddl_lines.append(self._emit_fk_inline(fk))

        if not ddl_lines:
            comment_lines.append("    -- ERROR: tabla sin columnas activas tras omisión de tipos incompatibles")

        body_parts: list[str] = []
        if comment_lines:
            body_parts.append("\n".join(comment_lines))
        if ddl_lines:
            body_parts.append(",\n".join(ddl_lines))

        lines.append("\n".join(body_parts))
        lines.append(")")

        return "\n".join(lines)

    def _emit_column(self, col: CanonicalColumn) -> str:
        if col.omit:
            comment = col.ddl_comment or f"-- AVISO: columna '{col.original_name}' omitida"
            return f"    {comment}"

        parts = [f"    {_dq(col.name)}", col.target_type]

        if not col.nullable:
            parts.append("NOT NULL")

        # Oracle no usa AUTO_INCREMENT en la columna; la secuencia lo gestiona
        if col.default is not None and not col.auto_increment:
            default_val = _format_default_oracle(col.default)
            parts.append(f"DEFAULT {default_val}")

        line = " ".join(parts)

        trailing: list[str] = []
        if col.ddl_comment:
            aviso = col.ddl_comment.lstrip("- ").strip()
            if aviso:
                trailing.append(aviso)

        if trailing:
            line += " -- " + " | ".join(trailing)

        return line

    def _emit_fk_inline(self, fk: CanonicalFK) -> str:
        cols = ", ".join(_dq(c) for c in fk.columns)
        ref_cols = ", ".join(_dq(c) for c in fk.ref_columns)
        stmt = (
            f"    CONSTRAINT {_dq(fk.name)} FOREIGN KEY ({cols}) "
            f"REFERENCES {_dq(fk.ref_table)} ({ref_cols})"
        )
        on_delete = (fk.on_delete or "").strip().upper()
        if on_delete in _ORACLE_ON_DELETE_SUPPORTED:
            stmt += f" ON DELETE {on_delete}"
        return stmt

    def _emit_alter_table_add_fk(self, table_name: str, fk: CanonicalFK) -> str:
        fk_inline = self._emit_fk_inline(fk).strip()
        return f"ALTER TABLE {_dq(table_name)} ADD {fk_inline}"

    # ─── SEQUENCE + TRIGGER (AUTO_INCREMENT) ──────────────────────────────────

    def _emit_sequences_and_triggers(self, table: CanonicalTable) -> list[str]:
        """Genera pares SEQUENCE + TRIGGER para columnas marcadas como AUTO_INCREMENT."""
        stmts: list[str] = []
        for col in table.columns:
            if col.omit or not col.auto_increment:
                continue
            seq = _seq_name(table.name)
            trg = _trg_name(table.name)
            stmts.append(
                f"CREATE SEQUENCE {_dq(seq)}\n"
                f"  START WITH 1\n"
                f"  INCREMENT BY 1\n"
                f"  NOCACHE\n"
                f"  NOCYCLE"
            )
            stmts.append(
                f"CREATE OR REPLACE TRIGGER {_dq(trg)}\n"
                f"  BEFORE INSERT ON {_dq(table.name)}\n"
                f"  FOR EACH ROW\n"
                f"BEGIN\n"
                f"  IF :NEW.{_dq(col.name)} IS NULL THEN\n"
                f"    SELECT {_dq(seq)}.NEXTVAL INTO :NEW.{_dq(col.name)} FROM DUAL;\n"
                f"  END IF;\n"
                f"END"
            )
        return stmts

    # ─── COMMENT ON ───────────────────────────────────────────────────────────

    def _emit_comments(self, table: CanonicalTable) -> list[str]:
        """Genera COMMENT ON TABLE y COMMENT ON COLUMN para comentarios no vacíos."""
        stmts: list[str] = []
        if table.comment:
            escaped = table.comment.replace("'", "''")
            stmts.append(f"COMMENT ON TABLE {_dq(table.name)} IS '{escaped}'")
        for col in table.columns:
            if col.omit or not col.comment:
                continue
            escaped = col.comment.replace("'", "''")
            stmts.append(
                f"COMMENT ON COLUMN {_dq(table.name)}.{_dq(col.name)} IS '{escaped}'"
            )
        return stmts

    # ─── Índices ──────────────────────────────────────────────────────────────

    def _emit_indexes(self, table: CanonicalTable) -> list[str]:
        pk_set = {c.upper() for c in table.primary_key}
        omitted_cols = {col.name.upper() for col in table.columns if col.omit}
        stmts: list[str] = []

        for idx in table.indexes:
            idx_col_set = {c.upper() for c in idx.columns}
            if idx_col_set == pk_set and idx.unique:
                continue
            if idx_col_set & omitted_cols:
                continue

            unique_kw = "UNIQUE " if idx.unique else ""
            cols = ", ".join(_dq(c) for c in idx.columns)
            stmt = f"CREATE {unique_kw}INDEX {_dq(idx.name)} ON {_dq(table.name)} ({cols})"
            stmts.append(stmt)

        return stmts

    # ─── Vistas ───────────────────────────────────────────────────────────────

    def _emit_view_statements(self, views: list[CanonicalView] | None) -> list[str]:
        active = [v for v in (views or []) if v.query]
        ordered, circular = _topological_sort_views(active)
        stmts: list[str] = [self._emit_create_view(v) for v in ordered]
        for v in circular:
            aviso = (
                f"-- AVISO: vista '{v.name}' participa en una dependencia circular "
                "— verificar orden de ejecución manualmente\n"
            )
            stmts.append(aviso + self._emit_create_view(v))
        return stmts

    def _emit_create_view(self, view: CanonicalView) -> str:
        lines: list[str] = []
        if view.warnings:
            lines.append("-- NOTE: requires manual review (see migration warnings)")
        if view.comment:
            lines.append(f"-- COMMENT: {view.comment.replace(chr(10), ' ')}")
        lines.append(f"CREATE OR REPLACE VIEW {_dq(view.name)} AS")
        lines.append(view.query)
        return "\n".join(lines)


def _format_default_oracle(value: str) -> str:
    """Traduce un valor DEFAULT MariaDB a su equivalente Oracle."""
    if not value:
        return "NULL"

    v = value.strip()
    upper_v = v.upper()

    if upper_v in _MARIADB_TO_ORA_DEFAULTS:
        return _MARIADB_TO_ORA_DEFAULTS[upper_v]

    try:
        float(v)
        return v
    except ValueError:
        pass

    escaped = v.replace("'", "''")
    return f"'{escaped}'"


__all__: list[str] = ["OracleDDLEmitter"]
