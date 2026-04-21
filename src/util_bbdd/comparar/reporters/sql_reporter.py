"""Reporter de SchemaDiff en formato SQL — script de nivelación de esquemas.

El script generado transforma el esquema **destino** para que coincida con
el esquema **origen**, siguiendo la semántica de ``SchemaDiff``:

- ``status="added"``   → el objeto existe en source, falta en target → **CREATE** en target.
- ``status="removed"`` → el objeto existe en target, falta en source → **DROP** de target.
- ``status="modified"``→ el objeto existe en ambos con diferencias → **ALTER** en target.

Cuando se proporciona un ``source_inspector`` (``sqlalchemy.engine.Inspector``),
el script emite SQL completo y ejecutable:

- Tablas ``added``        → ``CREATE TABLE`` con columnas, tipos, NOT NULL, DEFAULT, PK,
                            FOREIGN KEY constraints e índices secundarios.
- Columnas ``added``      → ``ALTER TABLE … ADD COLUMN col TIPO [NOT NULL] [DEFAULT val]``.
- Nullable / DEFAULT      → ``MODIFY COLUMN`` con tipo real (MariaDB/MySQL/Oracle) o
                            ``ALTER COLUMN SET/DROP`` (PostgreSQL/SQLite/SQL Server/generic).
- ``CommentDiff``         → ``COMMENT ON TABLE/COLUMN`` (PostgreSQL/Oracle/generic),
                            ``ALTER TABLE … COMMENT`` (MariaDB/MySQL),
                            ``-- ⚠`` placeholder (SQLite/SQL Server).

Sin ``source_inspector`` se emiten bloques de comentario ``-- ⚠`` indicando
qué información falta y dónde obtenerla.

El orden de las secciones garantiza la viabilidad de ejecución secuencial:
1. DROP de foreign keys de tablas eliminadas.
2. DROP de tablas eliminadas.
3. CREATE de tablas añadidas.
4. ALTER TABLE de tablas modificadas (columnas, índices, FKs, comentarios).
5. Vistas.
6. Rutinas.
"""

from __future__ import annotations

import logging

from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal, LiteralString

if TYPE_CHECKING:
    from sqlalchemy.engine import Inspector

from util_bbdd._core.exceptions import SchemaDiffValidationError

from ..models import (
    ColumnDiff,
    CommentDiff,
    ForeignKeyDiff,
    IndexDiff,
    RoutineDiff,
    SchemaDiff,
    TableDiff,
    ViewDiff,
)
from ._base import DdlNormalizer

# ---------------------------------------------------------------------------
# Constantes de módulo — compartidas entre varias clases (política _base.py)
# ---------------------------------------------------------------------------

#: Dialectos reconocidos por ``SqlDiffReporter``.
SUPPORTED_DIALECTS: frozenset[str] = frozenset(
    {
        "generic",
        "mariadb",
        "mysql",
        "postgresql",
        "sqlserver",
        "oracle",
        "sqlite",
    }
)


class SqlDiffReporter:
    """Genera un script ``.sql`` de nivelación a partir de un ``SchemaDiff``.

    Implementa ``DiffReporterProtocol``.

    El script producido es **orientado al motor destino**: transforma el
    esquema destino para que refleje el esquema origen.

    Cuando se proporciona ``source_inspector``, el reporter puede generar
    SQL completo y ejecutable para tablas y columnas nuevas, consultando los
    metadatos reales del esquema origen vía ``sqlalchemy.engine.Inspector``.
    Sin inspector, los bloques de creación se emiten como comentarios ``-- ⚠``
    con instrucciones para el operador.

    Args:
        dialect: Motor objetivo del script.  Controla la sintaxis de
            ``ALTER COLUMN``, ``DROP INDEX``, ``DROP FOREIGN KEY``,
            ``ADD COLUMN``, ``MODIFY COLUMN`` y ``COMMENT ON``.
            Valores aceptados: ``"generic"``, ``"mariadb"``, ``"mysql"``,
            ``"postgresql"``, ``"sqlserver"``, ``"oracle"``, ``"sqlite"``.
        source_inspector: Inspector de SQLAlchemy conectado al esquema origen.
            Cuando se proporciona, habilita la generación de ``CREATE TABLE``
            completo (columnas, PK, FK, índices), ``ADD COLUMN tipo_real``,
            ``MODIFY COLUMN`` con tipo real para cambios de nullable/DEFAULT y
            ``MODIFY COLUMN … COMMENT`` para MariaDB/MySQL.
            Si es ``None`` (por defecto), se emiten placeholders ``-- ⚠``.
        source_schema: Nombre del schema origen para ``Inspector.get_columns``
            e ``Inspector.get_pk_constraint``.  Normalmente ``None`` para el
            schema por defecto del motor.

    Raises:
        ValueError: Si ``dialect`` no es uno de los valores reconocidos.
    """

    # ------------------------------------------------------------------
    # Sintaxis dialect-específica (ClassVars de estrategia)
    # ------------------------------------------------------------------

    #: Template estándar para MODIFY COLUMN (generic, mariadb, mysql).
    _MODIFY_COL_TEMPLATE: ClassVar[str] = "MODIFY COLUMN {col} {type}"

    #: Template estándar para DROP INDEX (mariadb, mysql, sqlserver).
    _DROP_INDEX_ON_TABLE_TEMPLATE: ClassVar[str] = "DROP INDEX {name} ON {table};"

    #: Template estándar para DROP TABLE con IF EXISTS.
    _DROP_TABLE_IF_EXISTS_TEMPLATE: ClassVar[str] = "DROP TABLE IF EXISTS {table};"

    #: Template estándar para DROP VIEW con IF EXISTS.
    _DROP_VIEW_IF_EXISTS_TEMPLATE: ClassVar[str] = "DROP VIEW IF EXISTS {name};"

    #: Template estándar para DROP CONSTRAINT.
    _DROP_CONSTRAINT_TEMPLATE: ClassVar[str] = "DROP CONSTRAINT {name}"

    #: Template estándar para DROP ROUTINE con IF EXISTS.
    _DROP_ROUTINE_IF_EXISTS_TEMPLATE: ClassVar[str] = "DROP {rtype} IF EXISTS {name};"

    #: Template base para CREATE TABLE sin IF NOT EXISTS.
    _CREATE_TABLE_TEMPLATE: ClassVar[str] = "CREATE TABLE {table}"

    #: Template para CREATE TABLE IF NOT EXISTS (mariadb, mysql, postgresql, sqlite).
    _CREATE_TABLE_IF_NOT_EXISTS_TEMPLATE: ClassVar[str] = "CREATE TABLE IF NOT EXISTS {table}"

    #: Template base para ADD COLUMN (generic, mariadb, mysql, postgresql, sqlite).
    _ADD_COLUMN_TEMPLATE: ClassVar[str] = "ALTER TABLE {table} ADD COLUMN {col} {definition};"

    #: Template para cambiar el tipo de una columna existente.
    #: Placeholders: {col}, {type}
    _MODIFY_COL_TYPE: ClassVar[dict[str, str]] = {
        "generic": _MODIFY_COL_TEMPLATE,
        "mariadb": _MODIFY_COL_TEMPLATE,
        "mysql": _MODIFY_COL_TEMPLATE,
        "postgresql": "ALTER COLUMN {col} TYPE {type}",
        "sqlserver": "ALTER COLUMN {col} {type}",
        "oracle": "MODIFY ({col} {type})",
        "sqlite": "-- ⚠ SQLite: ALTER COLUMN no soportado; recrear tabla manualmente",
    }

    #: Template para DROP INDEX.  Placeholders: {name}, {table}
    _DROP_INDEX: ClassVar[dict[str, str]] = {
        "generic": "DROP INDEX {name};",
        "mariadb": _DROP_INDEX_ON_TABLE_TEMPLATE,
        "mysql": _DROP_INDEX_ON_TABLE_TEMPLATE,
        "postgresql": "DROP INDEX IF EXISTS {name};",
        "sqlserver": _DROP_INDEX_ON_TABLE_TEMPLATE,
        "oracle": "DROP INDEX {name};",
        "sqlite": "DROP INDEX IF EXISTS {name};",
    }

    #: Template para eliminar una FK dentro de ALTER TABLE.  Placeholder: {name}
    _DROP_FK: ClassVar[dict[str, str]] = {
        "generic": _DROP_CONSTRAINT_TEMPLATE,
        "mariadb": "DROP FOREIGN KEY {name}",
        "mysql": "DROP FOREIGN KEY {name}",
        "postgresql": "DROP CONSTRAINT IF EXISTS {name}",
        "sqlserver": _DROP_CONSTRAINT_TEMPLATE,
        "oracle": _DROP_CONSTRAINT_TEMPLATE,
        "sqlite": "-- ⚠ SQLite: DROP CONSTRAINT no soportado; recrear tabla manualmente",
    }

    #: Prefijo DROP TABLE; los dialectos compatibles añaden IF EXISTS.
    _DROP_TABLE: ClassVar[dict[str, str]] = {
        "generic": "DROP TABLE {table};",
        "mariadb": _DROP_TABLE_IF_EXISTS_TEMPLATE,
        "mysql": _DROP_TABLE_IF_EXISTS_TEMPLATE,
        "postgresql": _DROP_TABLE_IF_EXISTS_TEMPLATE,
        "sqlserver": _DROP_TABLE_IF_EXISTS_TEMPLATE,
        "oracle": "DROP TABLE {table};",
        "sqlite": _DROP_TABLE_IF_EXISTS_TEMPLATE,
    }

    #: DROP VIEW; algunos dialectos soportan IF EXISTS.
    _DROP_VIEW: ClassVar[dict[str, str]] = {
        "generic": "DROP VIEW {name};",
        "mariadb": _DROP_VIEW_IF_EXISTS_TEMPLATE,
        "mysql": _DROP_VIEW_IF_EXISTS_TEMPLATE,
        "postgresql": _DROP_VIEW_IF_EXISTS_TEMPLATE,
        "sqlserver": _DROP_VIEW_IF_EXISTS_TEMPLATE,
        "oracle": "DROP VIEW {name};",
        "sqlite": _DROP_VIEW_IF_EXISTS_TEMPLATE,
    }

    #: DROP PROCEDURE; Oracle y SQL Server no distinguen PROCEDURE de FUNCTION en DROP.
    _DROP_ROUTINE: ClassVar[dict[str, str]] = {
        "generic": "DROP {rtype} {name};",
        "mariadb": _DROP_ROUTINE_IF_EXISTS_TEMPLATE,
        "mysql": _DROP_ROUTINE_IF_EXISTS_TEMPLATE,
        "postgresql": _DROP_ROUTINE_IF_EXISTS_TEMPLATE,
        "sqlserver": _DROP_ROUTINE_IF_EXISTS_TEMPLATE,
        "oracle": "DROP {rtype} {name};",
        "sqlite": "-- ⚠ SQLite: rutinas no soportadas nativamente",
    }

    #: Prefijo CREATE TABLE por dialecto.  Los dialectos que soportan
    #: ``IF NOT EXISTS`` lo incluyen; Oracle y SQL Server no lo tienen.
    _CREATE_TABLE_PREFIX: ClassVar[dict[str, str]] = {
        "generic": _CREATE_TABLE_TEMPLATE,
        "mariadb": _CREATE_TABLE_IF_NOT_EXISTS_TEMPLATE,
        "mysql": _CREATE_TABLE_IF_NOT_EXISTS_TEMPLATE,
        "postgresql": _CREATE_TABLE_IF_NOT_EXISTS_TEMPLATE,
        "sqlserver": _CREATE_TABLE_TEMPLATE,
        "oracle": _CREATE_TABLE_TEMPLATE,
        "sqlite": _CREATE_TABLE_IF_NOT_EXISTS_TEMPLATE,
    }

    #: Template ADD COLUMN por dialecto.
    #: Placeholder ``{definition}`` = tipo + NOT NULL + DEFAULT concatenados.
    #: SQL Server omite la palabra ``COLUMN``; Oracle envuelve en paréntesis.
    _ADD_COLUMN: ClassVar[dict[str, str]] = {
        "generic": _ADD_COLUMN_TEMPLATE,
        "mariadb": _ADD_COLUMN_TEMPLATE,
        "mysql": _ADD_COLUMN_TEMPLATE,
        "postgresql": _ADD_COLUMN_TEMPLATE,
        "sqlserver": "ALTER TABLE {table} ADD {col} {definition};",
        "oracle": "ALTER TABLE {table} ADD ({col} {definition});",
        "sqlite": _ADD_COLUMN_TEMPLATE,
    }

    #: Valores ``source_value`` que indican "columna presente en origen".
    #: Maneja tanto la semántica del ``SchemaComparator`` (``"exists"``) como
    #: valores de fixtures legacy (``"present"``).
    _EXISTS_VALUES: ClassVar[frozenset[str]] = frozenset({"present", "exists"})

    #: Valores ``source_value`` que indican "columna ausente en origen".
    _ABSENT_VALUES: ClassVar[frozenset[str]] = frozenset({"absent", "missing"})

    #: Literal "NOT NULL" para constraints de columna.
    _NOT_NULL: ClassVar[str] = "NOT NULL"

    def __init__(
        self,
        dialect: str = "generic",
        source_inspector: Inspector | None = None,
        source_schema: str | None = None,
    ) -> None:
        normalized: str = dialect.strip().lower()
        if normalized not in SUPPORTED_DIALECTS:
            raise SchemaDiffValidationError(
                f"Dialect '{dialect}' no soportado. Válidos: {sorted(SUPPORTED_DIALECTS)}",
                operation="SqlDiffReporter.init",
                details=f"dialect={normalized}",
            )
        self.logger: logging.Logger = logging.getLogger(__name__)
        self._dialect: str = normalized
        self._source_inspector: Any = source_inspector
        self._source_schema: str | None = source_schema
        #: Caché de columnas SA por nombre de tabla.  Evita consultas repetidas
        #: al Inspector para la misma tabla en un mismo render.
        self._col_cache: dict[str, list[dict[str, Any]]] = {}
        #: Caché de foreign keys SA por nombre de tabla.
        self._fk_cache: dict[str, list[dict[str, Any]]] = {}
        #: Caché de índices SA por nombre de tabla.
        self._idx_cache: dict[str, list[dict[str, Any]]] = {}
        #: Mensaje de error por tabla cuando get_columns() falla.  Permite
        #: incluir la causa exacta del fallback en el placeholder ``-- ⚠``.
        self._col_error_cache: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Contrato público
    # ------------------------------------------------------------------

    def render(self, diff: SchemaDiff, output: Path) -> Path:
        """Genera el script ``.sql`` en la ruta indicada.

        Args:
            diff: Resultado de la comparación de esquemas.
            output: Ruta completa del fichero ``.sql`` a generar.

        Returns:
            La ruta del fichero generado.
        """
        self._col_cache = {}
        self._fk_cache = {}
        self._idx_cache = {}
        self._col_error_cache = {}
        output.parent.mkdir(parents=True, exist_ok=True)
        script: str = self._build_script(diff)
        output.write_text(script, encoding="utf-8")
        self.logger.info("SQL diff script generado: %s", output)
        return output

    # ------------------------------------------------------------------
    # Construcción del script
    # ------------------------------------------------------------------

    def _build_script(self, diff: SchemaDiff) -> str:
        lines: list[str] = []
        lines.extend(self._render_header(diff))

        if not diff.has_differences:
            lines.append("-- Sin diferencias detectadas entre los esquemas.")
            return "\n".join(lines) + "\n"

        removed: list[TableDiff] = [td for td in diff.table_diffs if td.status == "removed"]
        added: list[TableDiff] = [td for td in diff.table_diffs if td.status == "added"]
        modified: list[TableDiff] = [td for td in diff.table_diffs if td.status == "modified"]

        if removed:
            lines.extend(self._section("1. TABLAS ELIMINADAS EN ORIGEN — DROP TABLE en destino"))
            lines.extend(self._render_dropped_tables(removed))

        if added:
            lines.extend(self._section("2. TABLAS AÑADIDAS EN ORIGEN — CREATE TABLE en destino"))
            lines.extend(self._render_added_tables(added))

        if modified:
            lines.extend(self._section("3. TABLAS MODIFICADAS — ALTER TABLE en destino"))
            lines.extend(self._render_modified_tables(modified))

        if diff.view_diffs:
            lines.extend(self._section("4. VISTAS"))
            lines.extend(self._render_view_diffs(diff.view_diffs))

        if diff.routine_diffs:
            lines.extend(self._section("5. RUTINAS"))
            lines.extend(self._render_routine_diffs(diff.routine_diffs))

        lines_str: str = "\n".join(lines)
        return f"{lines_str}\n"

    # ------------------------------------------------------------------
    # Secciones principales
    # ------------------------------------------------------------------

    def _render_dropped_tables(self, tables: list[TableDiff]) -> list[str]:
        lines: list[str] = []
        for td in tables:
            # Eliminar primero las FKs propias que puedan causar violaciones de integridad
            if td.fk_diffs:
                lines.append(f"-- FK constraints en {td.table_name}:")
                for fk in td.fk_diffs:
                    lines.append(f"ALTER TABLE {td.table_name} {self._drop_fk_clause(fk.fk_name)};")
            tpl: str = self._DROP_TABLE.get(self._dialect, self._DROP_TABLE["generic"])
            lines.append(tpl.format(table=td.table_name))
            lines.append("")
        return lines

    def _render_added_tables(self, tables: list[TableDiff]) -> list[str]:
        """Genera SQL para tablas nuevas.

        Con ``source_inspector`` disponible emite ``CREATE TABLE`` completo
        (columnas, PK, FK inline, e índices secundarios post-tabla).
        Sin inspector emite un bloque de comentario ``-- ⚠`` con instrucciones
        y la causa del fallback para facilitar el diagnóstico.
        """
        lines: list[str] = []
        for td in tables:
            if self._source_inspector is not None:
                lines.extend(self._render_create_table_from_inspector(td.table_name))
            else:
                lines.extend(
                    self._render_added_table_placeholder(
                        td.table_name,
                        reason=(
                            "source_inspector no proporcionado — "
                            "pasar source_inspector=inspect(engine_origen) al SqlDiffReporter."
                        ),
                    )
                )
            lines.append("")
        return lines

    def _render_modified_tables(self, tables: list[TableDiff]) -> list[str]:
        lines: list[str] = []
        for td in tables:
            lines.append(f"-- Tabla: {td.table_name}")
            col_lines: list[str] = self._render_column_diffs(td.table_name, td.column_diffs)
            idx_lines: list[str] = self._render_index_diffs(td.table_name, td.index_diffs)
            fk_lines: list[str] = self._render_fk_diffs(td.table_name, td.fk_diffs)
            cmt_lines: list[str] = self._render_comment_diffs(td.table_name, td.comment_diffs)
            if col_lines:
                lines.append("-- Columnas:")
                lines.extend(col_lines)
            if idx_lines:
                lines.append("-- Índices:")
                lines.extend(idx_lines)
            if fk_lines:
                lines.append("-- Foreign Keys:")
                lines.extend(fk_lines)
            if cmt_lines:
                lines.append("-- Comentarios:")
                lines.extend(cmt_lines)
            lines.append("")
        return lines

    # ------------------------------------------------------------------
    # Acceso al Inspector origen
    # ------------------------------------------------------------------

    def _fetch_source_columns(self, table_name: str) -> list[dict[str, Any]]:
        """Obtiene la lista de columnas SA del esquema origen para *table_name*.

        Usa caché interna por nombre de tabla para evitar consultas repetidas
        al Inspector durante un mismo ``render()``.  Si el Inspector no está
        disponible o lanza una excepción, devuelve lista vacía y el llamador
        emite un placeholder ``-- ⚠``.
        """
        if self._source_inspector is None:
            return []
        if table_name not in self._col_cache:
            try:
                self._col_cache[table_name] = self._source_inspector.get_columns(table_name, schema=self._source_schema)
            except Exception as exc:
                error_msg = (
                    f"Inspector.get_columns() falló — {exc}. "
                    "Verificar que source_schema esté configurado si el motor lo requiere "
                    "(p.ej. Oracle, SQL Server multischema)."
                )
                self.logger.warning("Inspector: no se pudieron obtener columnas de '%s': %s", table_name, exc)
                self._col_cache[table_name] = []
                self._col_error_cache[table_name] = error_msg
        return self._col_cache[table_name]

    def _fetch_pk_columns(self, table_name: str) -> list[str]:
        """Devuelve los nombres de columnas PK de *table_name* desde el Inspector.

        Devuelve lista vacía si el Inspector no está disponible o falla.
        """
        if self._source_inspector is None:
            return []
        try:
            pk: dict[str, Any] = self._source_inspector.get_pk_constraint(table_name, schema=self._source_schema)
            return list(pk.get("constrained_columns", []))
        except Exception:
            self.logger.warning(
                "Inspector: no se pudo obtener PK de '%s'.",
                table_name,
            )
            return []

    def _fetch_source_foreign_keys(self, table_name: str) -> list[dict[str, Any]]:
        """Obtiene la lista de foreign keys SA del esquema origen para *table_name*.

        Usa caché interna ``_fk_cache`` para evitar consultas repetidas al Inspector
        durante un mismo ``render()``.  Devuelve lista vacía si el Inspector no está
        disponible o lanza excepción.
        """
        if self._source_inspector is None:
            return []
        if table_name not in self._fk_cache:
            try:
                self._fk_cache[table_name] = list(
                    self._source_inspector.get_foreign_keys(table_name, schema=self._source_schema)
                )
            except Exception:
                self.logger.warning(
                    "Inspector: no se pudieron obtener FKs de '%s'.",
                    table_name,
                )
                self._fk_cache[table_name] = []
        return self._fk_cache[table_name]

    def _fetch_source_indexes(self, table_name: str) -> list[dict[str, Any]]:
        """Obtiene la lista de índices SA del esquema origen para *table_name*.

        Usa caché interna ``_idx_cache``.  Devuelve lista vacía si el Inspector
        no está disponible, el dialecto no soporta índices, o falla.
        """
        if self._source_inspector is None:
            return []
        if table_name not in self._idx_cache:
            try:
                self._idx_cache[table_name] = list(
                    self._source_inspector.get_indexes(table_name, schema=self._source_schema)
                )
            except Exception:
                self.logger.warning(
                    "Inspector: no se pudieron obtener índices de '%s'.",
                    table_name,
                )
                self._idx_cache[table_name] = []
        return self._idx_cache[table_name]

    @staticmethod
    def _format_col_type(col: dict[str, Any]) -> str:
        """Devuelve la representación de cadena del tipo SQLAlchemy de *col*.

        Usa ``str(col["type"])`` que produce p.ej. ``"VARCHAR(100)"``,
        ``"INTEGER"``, ``"TEXT"``.  El resultado es **best-effort**: puede no
        ser 100 % portable entre dialectos distintos al motor origen; el
        operador debe revisar el script antes de ejecutarlo en producción.
        """
        return str(col.get("type", "TEXT"))

    def _render_col_definition(self, col: dict[str, Any]) -> str:
        """Genera la línea de definición de columna para un ``CREATE TABLE``.

        Formato: ``  nombre TIPO [NOT NULL] [DEFAULT valor]``
        """
        name: str = col["name"]
        col_type: str = self._format_col_type(col)
        nullable: bool = col.get("nullable", True)
        default: Any = col.get("default")

        parts: list[str] = [f"  {name} {col_type}"]
        if not nullable:
            parts.append(self._NOT_NULL)
        if default is not None and str(default).strip().upper() not in ("", "NONE"):
            parts.append(f"DEFAULT {default}")
        return " ".join(parts)

    def _get_col_type_for_modify(self, table: str, col: str) -> str:
        """Devuelve el tipo real de la columna *col* en la tabla *table* origen.

        Consulta ``_fetch_source_columns`` (con caché) para obtener el tipo
        SQLAlchemy real.  Devuelve el placeholder ``<TIPO>`` cuando el Inspector
        no está disponible o la columna no se encuentra.

        Usado por ``_render_nullable_diff`` y ``_render_default_diff`` para
        generar ``MODIFY COLUMN col TIPO [NOT NULL/DEFAULT ...]`` en los dialectos
        que requieren el tipo completo (MariaDB/MySQL, Oracle).
        """
        if self._source_inspector is not None:
            cols = self._fetch_source_columns(table)
            col_info = next((c for c in cols if c["name"] == col), None)
            if col_info is not None:
                return self._format_col_type(col_info)
        return "<TIPO>"

    def _render_create_table_from_inspector(self, table_name: str) -> list[str]:
        """Genera un ``CREATE TABLE`` completo para *table_name* usando el Inspector.

        El DDL incluye:
        - Definiciones de columna (tipo, NOT NULL, DEFAULT).
        - Restricción PRIMARY KEY.
        - Restricciones FOREIGN KEY (con nombre de constraint si disponible).
        - ``CREATE INDEX`` / ``CREATE UNIQUE INDEX`` para índices secundarios
          (emitidos tras el cierre de paréntesis de la tabla).

        Si el Inspector no retorna columnas (error o tabla vacía), delega a
        ``_render_added_table_placeholder``.

        Nota: las FKs referencian tablas que deben existir en el momento de
        ejecución.  Si la tabla referenciada es también nueva, reordenar las
        sentencias manualmente o usar ``-- ⚠ verificar orden de ejecución``.
        """
        cols: list[dict[str, Any]] = self._fetch_source_columns(table_name)
        if not cols:
            reason = self._col_error_cache.get(
                table_name,
                "get_columns() retornó lista vacía — verificar que la tabla exista "
                "en el esquema origen y que source_schema sea correcto.",
            )
            return self._render_added_table_placeholder(table_name, reason=reason)

        pk_cols: list[str] = self._fetch_pk_columns(table_name)
        fks: list[dict[str, Any]] = self._fetch_source_foreign_keys(table_name)
        indexes: list[dict[str, Any]] = self._fetch_source_indexes(table_name)
        prefix: str = self._CREATE_TABLE_PREFIX.get(self._dialect, self._CREATE_TABLE_PREFIX["generic"])

        lines: list[str] = [f"{prefix.format(table=table_name)} ("]
        col_defs: list[str] = [self._render_col_definition(col) for col in cols]

        if pk_cols:
            col_defs.append(f"  PRIMARY KEY ({', '.join(pk_cols)})")

        col_defs.extend(self._build_fk_definitions(fks))
        lines.extend(self._build_column_definitions_lines(col_defs))
        lines.append(");")
        lines.extend(self._build_secondary_indexes_lines(indexes, table_name))

        return lines

    def _build_fk_definitions(self, fks: list[dict[str, Any]]) -> list[str]:
        """Construye las definiciones de FOREIGN KEY para la tabla.

        Normaliza cada FK extraído del Inspector: valida que tenga columnas
        origen, tabla referenciada y genera línea ``CONSTRAINT … FOREIGN KEY``
        apropiada.
        """
        fk_defs: list[str] = []
        for fk in fks:
            constrained = fk.get("constrained_columns") or []
            ref_table = fk.get("referred_table", "")
            ref_cols = fk.get("referred_columns") or []
            fk_name = fk.get("name", "")

            if not constrained or not ref_table:
                continue

            constrained_str = ", ".join(constrained)
            ref_cols_str = f" ({', '.join(ref_cols)})" if ref_cols else ""

            if fk_name:
                fk_defs.append(
                    f"  CONSTRAINT {fk_name} FOREIGN KEY ({constrained_str}) REFERENCES {ref_table}{ref_cols_str}"
                )
            else:
                fk_defs.append(f"  FOREIGN KEY ({constrained_str}) REFERENCES {ref_table}{ref_cols_str}")

        return fk_defs

    @staticmethod
    def _build_column_definitions_lines(col_defs: list[str]) -> list[str]:
        """Transforma lista de definiciones de columna en líneas numeradas.

        Añade coma de separación entre columnas (excepto la última).
        """
        lines: list[str] = []
        for i, col_def in enumerate(col_defs):
            sep = "," if i < len(col_defs) - 1 else ""
            lines.append(f"{col_def}{sep}")
        return lines

    @staticmethod
    def _build_secondary_indexes_lines(indexes: list[dict[str, Any]], table_name: str) -> list[str]:
        """Genera las sentencias ``CREATE INDEX`` para índices secundarios.

        Excluye índices sin nombre o sin columnas (típicamente FK implícitos o PK).
        """
        lines: list[str] = []
        for idx in indexes:
            idx_name = idx.get("name", "")
            idx_cols: list[str] = [c for c in (idx.get("column_names") or []) if c]

            if not idx_name or not idx_cols:
                continue

            unique = "UNIQUE " if idx.get("unique", False) else ""
            cols_str = ", ".join(idx_cols)
            lines.append(f"CREATE {unique}INDEX {idx_name} ON {table_name} ({cols_str});")

        return lines

    @staticmethod
    def _render_added_table_placeholder(table_name: str, reason: str = "") -> list[str]:
        """Genera el bloque de comentario placeholder para una tabla añadida sin DDL.

        Args:
            table_name: Nombre de la tabla nueva.
            reason: Causa del fallback (p.ej. "source_inspector no proporcionado"
                o el mensaje de excepción de ``get_columns()``).  Si se proporciona
                se emite como línea ``-- Causa: …`` para facilitar el diagnóstico.
        """
        lines = [f"-- ⚠ TABLA NUEVA: {table_name}"]
        if reason:
            lines.append(f"-- Causa: {reason}")
        lines += [
            "-- La definición completa de columnas no está disponible en SchemaDiff.",
            "-- Consultar el esquema origen para obtener el DDL y ejecutar:",
            f"-- CREATE TABLE {table_name} (",
            "--   <columnas_del_esquema_origen>",
            "-- );",
        ]
        return lines

    def _render_add_column_with_type(self, table: str, col_name: str, col_info: dict[str, Any]) -> list[str]:
        """Genera ``ALTER TABLE … ADD COLUMN`` con tipo y constraints reales.

        Emite un comentario ``-- ⚠`` de advertencia cuando la columna es
        ``NOT NULL`` sin ``DEFAULT``, ya que el statement fallará en una tabla
        que ya contenga filas.
        """
        col_type: str = self._format_col_type(col_info)
        nullable: bool = col_info.get("nullable", True)
        default: Any = col_info.get("default")
        has_default: bool = default is not None and str(default).strip().upper() not in ("", "NONE")

        definition_parts: list[str] = [col_type]
        if not nullable:
            definition_parts.append(self._NOT_NULL)
        if has_default:
            definition_parts.append(f"DEFAULT {default}")

        definition: str = " ".join(definition_parts)
        tpl: str = self._ADD_COLUMN.get(self._dialect, self._ADD_COLUMN["generic"])

        lines: list[str] = []
        if not nullable and not has_default:
            lines.append(f"-- ⚠ {col_name} es NOT NULL sin DEFAULT: verificar que la tabla no tenga filas existentes.")
        if self._dialect == "sqlite" and not nullable:
            lines.append("-- ⚠ SQLite: ADD COLUMN NOT NULL sin DEFAULT no está soportado nativamente.")
        lines.append(tpl.format(table=table, col=col_name, definition=definition))
        return lines

    # ------------------------------------------------------------------
    # Diferencias de columna
    # ------------------------------------------------------------------

    def _render_column_diffs(self, table: str, col_diffs: tuple[ColumnDiff, ...]) -> list[str]:
        lines: list[str] = []
        for cd in col_diffs:
            lines.extend(self._render_single_column_diff(table, cd))
        return lines

    def _render_single_column_diff(self, table: str, cd: ColumnDiff) -> list[str]:
        col: str = cd.column_name

        if cd.attribute == "existence":
            return self._render_existence_diff(table, col, cd)

        if cd.attribute == "type":
            clause: str = self._modify_col_type_clause(col, cd.source_value)
            return [f"ALTER TABLE {table} {clause};  -- tipo: {cd.target_value!r} → {cd.source_value!r}"]

        if cd.attribute == "nullable":
            return self._render_nullable_diff(table, col, cd)

        if cd.attribute == "default":
            return self._render_default_diff(table, col, cd)

        if cd.attribute == "primary_key":
            return [
                f"-- ⚠ PRIMARY KEY cambiada en {table}.{col}: {cd.target_value!r} → {cd.source_value!r}.",
                "-- Gestionar manualmente: DROP PRIMARY KEY + ADD PRIMARY KEY.",
            ]

        return [
            f"-- Atributo '{cd.attribute}' en {table}.{col}: {cd.target_value!r} → {cd.source_value!r}",
        ]

    def _render_existence_diff(self, table: str, col: str, cd: ColumnDiff) -> list[str]:
        """Genera SQL para cambios de existencia de columna (ADD/DROP).

        Normaliza semántica del comparador ("exists"/"missing") y valores
        legacy de fixtures ("present"/"absent") para robustez.
        """
        src_present: bool = cd.source_value in self._EXISTS_VALUES
        src_absent: bool = cd.source_value in self._ABSENT_VALUES

        if src_present:
            # Columna existe en source, falta en target → ADD
            if self._source_inspector is not None:
                cols: list[dict[str, Any]] = self._fetch_source_columns(table)
                col_info: dict[str, Any] | None = next((c for c in cols if c["name"] == col), None)
                if col_info is not None:
                    return self._render_add_column_with_type(table, col, col_info)
            return [
                f"-- ⚠ ADD COLUMN {col}: tipo no disponible en SchemaDiff — verificar en origen.",
                f"ALTER TABLE {table} ADD COLUMN {col} <TIPO_ORIGEN>;  -- ⚠ REVISAR TIPO",
            ]
        if src_absent:
            # Columna existe en target, no en source → DROP
            return [f"ALTER TABLE {table} DROP COLUMN {col};"]
        return [f"-- ⚠ existence diff inesperado en {col}: {cd.source_value!r} → {cd.target_value!r}"]

    def _render_nullable_diff(self, table: str, col: str, cd: ColumnDiff) -> list[str]:
        """Genera cláusula NOT NULL / NULL para cambio de nulabilidad.

        Para MariaDB/MySQL y Oracle, ``MODIFY COLUMN`` requiere el tipo completo.
        Si ``source_inspector`` está disponible se usa el tipo real obtenido vía
        ``_get_col_type_for_modify``; en caso contrario se emite ``<TIPO>`` como
        placeholder que el operador debe completar antes de ejecutar.
        """
        target_null: bool = cd.source_value.upper() in ("YES", "TRUE", "1", "NULL")
        null_kw: str = "NULL" if target_null else self._NOT_NULL

        if self._dialect in ("mariadb", "mysql"):
            col_type: str = self._get_col_type_for_modify(table, col)
            return [f"ALTER TABLE {table} MODIFY COLUMN {col} {col_type} {null_kw};"]

        if self._dialect == "oracle":
            col_type = self._get_col_type_for_modify(table, col)
            if col_type != "<TIPO>":
                return [f"ALTER TABLE {table} MODIFY ({col} {col_type} {null_kw});"]
            return [f"ALTER TABLE {table} MODIFY ({col} {null_kw});"]

        # Standard SQL / PostgreSQL / SQLite / SQL Server
        if target_null:
            return [f"ALTER TABLE {table} ALTER COLUMN {col} DROP NOT NULL;"]
        return [f"ALTER TABLE {table} ALTER COLUMN {col} SET NOT NULL;"]

    def _render_default_diff(self, table: str, col: str, cd: ColumnDiff) -> list[str]:
        """Genera cláusula de cambio de DEFAULT — dialect-aware.

        MariaDB/MySQL requieren ``MODIFY COLUMN col TIPO DEFAULT val`` (el tipo
        es obligatorio en la sintaxis MODIFY).  Oracle usa ``MODIFY (col DEFAULT val)``.
        El resto usa ``ALTER COLUMN col SET/DROP DEFAULT``.

        Si ``source_inspector`` está disponible se obtiene el tipo real para
        MariaDB/MySQL.  Sin inspector se emite ``<TIPO>`` como placeholder.
        """
        src_default: str = cd.source_value
        is_drop: bool = src_default.upper() in ("NONE", "NULL", "")

        if self._dialect in ("mariadb", "mysql"):
            col_type: str = self._get_col_type_for_modify(table, col)
            if is_drop:
                return [f"ALTER TABLE {table} MODIFY COLUMN {col} {col_type};  -- DEFAULT eliminado"]
            return [f"ALTER TABLE {table} MODIFY COLUMN {col} {col_type} DEFAULT {src_default};"]

        if self._dialect == "oracle":
            if is_drop:
                return [f"ALTER TABLE {table} MODIFY ({col} DEFAULT NULL);"]
            return [f"ALTER TABLE {table} MODIFY ({col} DEFAULT {src_default});"]

        # Generic / PostgreSQL / SQLite / SQL Server
        if is_drop:
            return [f"ALTER TABLE {table} ALTER COLUMN {col} DROP DEFAULT;"]
        return [f"ALTER TABLE {table} ALTER COLUMN {col} SET DEFAULT {src_default};"]

    # ------------------------------------------------------------------
    # Diferencias de índice
    # ------------------------------------------------------------------

    def _render_index_diffs(self, table: str, idx_diffs: tuple[IndexDiff, ...]) -> list[str]:
        lines: list[str] = []
        for idx in idx_diffs:
            lines.extend(self._render_single_index_diff(table, idx))
        return lines

    def _render_single_index_diff(self, table: str, idx: IndexDiff) -> list[str]:
        if idx.status == "removed":
            # Índice existe en target, no en source → DROP en target
            return [self._drop_index_sql(idx.index_name, table)]

        if idx.status == "added":
            # Índice existe en source, no en target → CREATE en target
            return [self._create_index_sql(idx, table)]

        # modified → DROP + CREATE con nueva definición
        return [
            self._drop_index_sql(idx.index_name, table),
            self._create_index_sql(idx, table),
        ]

    def _create_index_sql(self, idx: IndexDiff, table: str) -> str:
        unique: Literal["UNIQUE "] | Literal[""] = "UNIQUE " if idx.source_unique else ""
        cols: str = idx.source_columns or idx.target_columns or "<columnas>"
        return f"CREATE {unique}INDEX {idx.index_name} ON {table} ({cols});"

    # ------------------------------------------------------------------
    # Diferencias de Foreign Key
    # ------------------------------------------------------------------

    def _render_fk_diffs(self, table: str, fk_diffs: tuple[ForeignKeyDiff, ...]) -> list[str]:
        lines: list[str] = []
        for fk in fk_diffs:
            lines.extend(self._render_single_fk_diff(table, fk))
        return lines

    def _render_single_fk_diff(self, table: str, fk: ForeignKeyDiff) -> list[str]:
        if fk.status == "removed":
            # FK existe en target, no en source → DROP en target
            return [f"ALTER TABLE {table} {self._drop_fk_clause(fk.fk_name)};"]

        if fk.status == "added":
            # FK existe en source, no en target → ADD en target
            return [self._add_fk_sql(table, fk)]

        # modified → DROP + ADD con nueva definición
        return [
            f"ALTER TABLE {table} {self._drop_fk_clause(fk.fk_name)};",
            self._add_fk_sql(table, fk),
        ]

    def _add_fk_sql(self, table: str, fk: ForeignKeyDiff) -> str:
        cols: str = fk.source_columns or "<columnas_origen>"
        ref_table: str = fk.source_referred_table or "<tabla_referenciada>"
        ref_cols: str = fk.source_referred_columns
        ref_part: str = f" ({ref_cols})" if ref_cols else ""
        return f"ALTER TABLE {table} ADD CONSTRAINT {fk.fk_name} FOREIGN KEY ({cols}) REFERENCES {ref_table}{ref_part};"

    # ------------------------------------------------------------------
    # Diferencias de comentario
    # ------------------------------------------------------------------

    def _render_comment_diffs(self, table: str, comment_diffs: tuple[CommentDiff, ...]) -> list[str]:
        """Genera SQL de actualización de comentarios a partir de los ``CommentDiff``.

        Para cada ``CommentDiff``:
        - ``column_name is None`` → comentario de tabla.
        - ``column_name`` presente → comentario de columna.

        Sintaxis generada por dialecto:

        * ``generic/postgresql/oracle``: ``COMMENT ON TABLE/COLUMN … IS '…'``.
        * ``mariadb/mysql`` tabla: ``ALTER TABLE … COMMENT = '…'``.
        * ``mariadb/mysql`` columna: ``ALTER TABLE … MODIFY COLUMN col TIPO COMMENT '…'``
          (tipo real si hay inspector; ``<TIPO>`` en caso contrario).
        * ``sqlserver``: ``-- ⚠`` placeholder (no soporta ``COMMENT ON``).
        * ``sqlite``: ``-- ⚠`` placeholder (no soporta ``COMMENT ON``).
        """
        lines: list[str] = []
        for cd in comment_diffs:
            lines.extend(self._render_single_comment_diff(table, cd))
        return lines

    def _render_single_comment_diff(self, table: str, cd: CommentDiff) -> list[str]:
        """Genera el SQL para un único ``CommentDiff``, dispatch por dialecto."""
        comment: str = self._escape_sql_string(cd.source_comment)

        if self._dialect == "sqlite":
            target: str = f"{table}.{cd.column_name}" if cd.column_name else table
            return [f"-- ⚠ SQLite: COMMENT ON no soportado — comentario cambiado en {target}"]

        if self._dialect == "sqlserver":
            target = f"{table}.{cd.column_name}" if cd.column_name else table
            return [
                f"-- ⚠ SQL Server: usar sp_addextendedproperty para comentarios — {target}",
                f"-- Nuevo comentario: {cd.source_comment!r}",
            ]

        if self._dialect in ("mariadb", "mysql"):
            if cd.column_name is None:
                # Comentario de tabla
                return [f"ALTER TABLE {table} COMMENT = '{comment}';"]
            # Comentario de columna — requiere tipo
            col_type = self._get_col_type_for_modify(table, cd.column_name)
            return [f"ALTER TABLE {table} MODIFY COLUMN {cd.column_name} {col_type} COMMENT '{comment}';"]

        # generic / postgresql / oracle → COMMENT ON
        if cd.column_name is None:
            return [f"COMMENT ON TABLE {table} IS '{comment}';"]
        return [f"COMMENT ON COLUMN {table}.{cd.column_name} IS '{comment}';"]

    @staticmethod
    def _escape_sql_string(value: str) -> str:
        """Escapa comillas simples en un string para embeber en SQL como literal.

        Sigue la convención SQL estándar: ``'`` → ``''``.
        """
        return value.replace("'", "''")

    # ------------------------------------------------------------------
    # Vistas
    # ------------------------------------------------------------------

    def _build_view_create_sql(self, view_name: str, raw_ddl: str, or_replace: bool = False) -> str:
        """Genera el statement ``CREATE [OR REPLACE] VIEW`` a partir del DDL raw.

        1. Normaliza el DDL (strips ``DEFINER``, ``ALGORITHM``, ``SQL SECURITY``).
        2. Extrae el cuerpo SELECT para evitar double-wrapping cuando el DDL ya
           contiene el header ``CREATE … VIEW name AS``.
        3. Reconstruye el header correcto según dialecto y ``or_replace``.

        Args:
            view_name: Nombre de la vista (sin comillas).
            raw_ddl: DDL crudo procedente de ``ViewDiff.source_definition``.
            or_replace: Si ``True`` genera ``CREATE OR REPLACE VIEW``; útil para
                vistas ``"modified"``.  SQL Server ignora este flag (siempre usa
                ``DROP + CREATE``).

        Returns:
            Statement completo sin punto y coma final.
        """
        body: str = DdlNormalizer.extract_view_body(DdlNormalizer.normalize_view_ddl(raw_ddl))
        if self._dialect == "sqlserver":
            return f"CREATE VIEW {view_name} AS\n{body}"
        if or_replace:
            return f"CREATE OR REPLACE VIEW {view_name} AS\n{body}"
        return f"CREATE VIEW {view_name} AS\n{body}"

    def _render_view_diffs(self, view_diffs: tuple[ViewDiff, ...]) -> list[str]:
        lines: list[str] = []
        for vd in view_diffs:
            lines.extend(self._render_single_view_diff(vd))
        return lines

    def _render_single_view_diff(self, vd: ViewDiff) -> list[str]:
        drop_tpl: str = self._DROP_VIEW.get(self._dialect, self._DROP_VIEW["generic"])

        if vd.status == "removed":
            return [drop_tpl.format(name=vd.view_name), ""]

        if vd.status == "added":
            if vd.source_definition:
                return [f"{self._build_view_create_sql(vd.view_name, vd.source_definition)};", ""]
            return [
                f"-- ⚠ VISTA NUEVA: {vd.view_name}",
                "-- Definición no disponible en SchemaDiff — consultar esquema origen.",
                f"-- CREATE VIEW {vd.view_name} AS <definición_origen>;",
                "",
            ]

        # modified
        lines: list[str] = []
        if vd.source_definition:
            if self._dialect == "sqlserver":
                lines.append(drop_tpl.format(name=vd.view_name))
                lines.append("GO")
                lines.append(f"{self._build_view_create_sql(vd.view_name, vd.source_definition)};")
                lines.append("GO")
            else:
                lines.append(f"{self._build_view_create_sql(vd.view_name, vd.source_definition, or_replace=True)};")
        else:
            lines.append(f"-- ⚠ {vd.view_name}: modificada pero definición origen no disponible en SchemaDiff.")
        lines.append("")
        return lines

    # ------------------------------------------------------------------
    # Rutinas
    # ------------------------------------------------------------------

    def _render_routine_diffs(self, routine_diffs: tuple[RoutineDiff, ...]) -> list[str]:
        lines: list[str] = []
        for rd in routine_diffs:
            lines.extend(self._render_single_routine_diff(rd))
        return lines

    def _render_single_routine_diff(self, rd: RoutineDiff) -> list[str]:
        drop_tpl: str = self._DROP_ROUTINE.get(self._dialect, self._DROP_ROUTINE["generic"])
        rtype: Literal["PROCEDURE"] | Literal["FUNCTION"] = rd.routine_type  # "PROCEDURE" | "FUNCTION"

        if rd.status == "removed":
            return [drop_tpl.format(rtype=rtype, name=rd.routine_name), ""]

        if rd.status == "added":
            if rd.source_definition:
                normalized: str = DdlNormalizer.normalize_routine_ddl(rd.source_definition)
                return [f"{normalized.rstrip(';')};", ""]
            return [
                f"-- ⚠ RUTINA NUEVA: {rd.routine_name} ({rtype})",
                "-- Definición no disponible en SchemaDiff — consultar esquema origen.",
                "",
            ]

        # modified
        lines: list[str] = []
        if rd.source_definition:
            normalized = DdlNormalizer.normalize_routine_ddl(rd.source_definition)
            # Dialectos sin CREATE OR REPLACE PROCEDURE (mariadb, mysql, sqlserver, generic)
            # requieren DROP previo para evitar error si la rutina ya existe en destino.
            if self._dialect in ("mariadb", "mysql", "sqlserver", "generic"):
                lines.append(drop_tpl.format(rtype=rtype, name=rd.routine_name))
            lines.append(f"{normalized.rstrip(';')};")
        else:
            lines.append(f"-- ⚠ {rd.routine_name}: modificada pero definición origen no disponible.")
        lines.append("")
        return lines

    # ------------------------------------------------------------------
    # Helpers de dialecto
    # ------------------------------------------------------------------

    def _modify_col_type_clause(self, col: str, new_type: str) -> str:
        tpl: str = self._MODIFY_COL_TYPE.get(self._dialect, self._MODIFY_COL_TYPE["generic"])
        return f"{tpl.format(col=col, type=new_type)}"

    def _drop_index_sql(self, name: str, table: str) -> str:
        tpl: str = self._DROP_INDEX.get(self._dialect, self._DROP_INDEX["generic"])
        return f"{tpl.format(name=name, table=table)}"

    def _drop_fk_clause(self, name: str) -> str:
        tpl: str = self._DROP_FK.get(self._dialect, self._DROP_FK["generic"])
        return f"{tpl.format(name=name)}"

    # ------------------------------------------------------------------
    # Helpers de formato
    # ------------------------------------------------------------------

    def _render_header(self, diff: SchemaDiff) -> list[str]:
        sep: LiteralString = "-" * 70
        inspector_note = (
            "con metadatos de Inspector origen"
            if self._source_inspector is not None
            else "sin Inspector origen (placeholders ⚠ para DDL incompleto)"
        )
        return [
            f"-- {sep}",
            "-- Script de nivelación de esquemas",
            f"-- Origen : {diff.source_label}",
            f"-- Destino: {diff.target_label}",
            f"-- Motor  : {self._dialect}",
            f"-- Modo   : {inspector_note}",
            "-- Nota   : Este script transforma el esquema DESTINO para que",
            "--          coincida con el esquema ORIGEN.",
            "--          Revisar y adaptar antes de ejecutar en producción.",
            f"-- {sep}",
            "",
        ]

    @staticmethod
    def _section(title: str) -> list[str]:
        return [
            f"-- {'=' * 66}",
            f"-- {title}",
            f"-- {'=' * 66}",
            "",
        ]
