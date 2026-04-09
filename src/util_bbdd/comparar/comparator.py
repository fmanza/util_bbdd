"""Comparador de esquemas de base de datos motor-agnóstico sobre SQLAlchemy Inspector."""

from __future__ import annotations

import logging
import re

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine, Inspector

from .models import (
    ColumnDiff,
    CommentDiff,
    ForeignKeyDiff,
    IndexDiff,
    RoutineDiff,
    SchemaDiff,
    TableDiff,
    ViewDiff,
)

logger: logging.Logger = logging.getLogger(__name__)


class SchemaComparator:
    """Compara dos esquemas de base de datos usando ``sqlalchemy.engine.Inspector``.

    Soporta tablas, columnas, índices, foreign keys, vistas, comentarios y,
    opcionalmente, routines (procedures/functions) cuando el Inspector o el
    engine del caller lo permitan.
    """

    # ------------------------------------------------------------------
    # Registros de extensión (OCP)
    # ------------------------------------------------------------------

    #: Mapeo dialect → función fetcher de routines.
    #: Para añadir soporte a un nuevo motor sin modificar el código base::
    #:
    #:     SchemaComparator._ROUTINE_FETCHERS["mssql"] = my_mssql_fetcher
    _ROUTINE_FETCHERS: ClassVar[dict[str, Callable[[Inspector, str | None], list[dict[str, str]]]]] = {}

    #: Reglas de limpieza DDL dialect-específicas aplicadas antes de la normalización universal.
    #: Cada entrada es ``(patron_regex, reemplazo)``.
    #: Para añadir una regla nueva sin modificar ``_normalize_ddl``::
    #:
    #:     SchemaComparator._DDL_STRIP_RULES.append((r"MY_PATTERN", ""))
    _DDL_STRIP_RULES: ClassVar[list[tuple[str, str]]] = [
        (r"DEFINER=`[^`]+`@`[^`]+`", ""),  # MariaDB / MySQL
        (r"CREATE OR REPLACE FORCE", "CREATE OR REPLACE"),  # Oracle
    ]

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def compare(
        self,
        source: Inspector,
        target: Inspector,
        *,
        source_schema: str | None = None,
        target_schema: str | None = None,
        include_tables: bool = True,
        include_views: bool = True,
        include_indices: bool = True,
        include_foreign_keys: bool = True,
        include_comments: bool = True,
        include_routines: bool = False,
    ) -> SchemaDiff:
        """Compara dos esquemas y devuelve las diferencias encontradas.

        Args:
            source: Inspector del esquema origen.
            target: Inspector del esquema destino.
            source_schema: Nombre del schema origen (``None`` usa el default del engine).
            target_schema: Nombre del schema destino.
            include_tables: Comparar tablas y columnas.
            include_views: Comparar vistas.
            include_indices: Comparar índices (solo si ``include_tables`` también está activo).
            include_foreign_keys: Comparar foreign keys (solo si ``include_tables``).
            include_comments: Comparar comentarios de tablas/columnas.
            include_routines: Comparar procedures/functions vía catálogo del motor.

        Returns:
            ``SchemaDiff`` con todas las diferencias encontradas.
        """
        source_label: str = self._build_label(source, source_schema)
        target_label: str = self._build_label(target, target_schema)
        logger.info("Iniciando comparación: %s ↔ %s", source_label, target_label)

        table_diffs: tuple[TableDiff, ...] = ()
        view_diffs: tuple[ViewDiff, ...] = ()
        routine_diffs: tuple[RoutineDiff, ...] = ()

        if include_tables:
            table_diffs = self._compare_tables(
                source,
                target,
                source_schema=source_schema,
                target_schema=target_schema,
                include_indices=include_indices,
                include_foreign_keys=include_foreign_keys,
                include_comments=include_comments,
            )

        if include_views:
            view_diffs = self._compare_views(source, target, source_schema, target_schema)

        if include_routines:
            routine_diffs = self._compare_routines(source, target, source_schema, target_schema)

        summary = self._build_summary(table_diffs, view_diffs, routine_diffs)
        logger.info("Comparación finalizada: %s", summary)

        return SchemaDiff(
            source_label=source_label,
            target_label=target_label,
            table_diffs=table_diffs,
            view_diffs=view_diffs,
            routine_diffs=routine_diffs,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Tablas
    # ------------------------------------------------------------------

    def _compare_tables(
        self,
        source: Inspector,
        target: Inspector,
        *,
        source_schema: str | None,
        target_schema: str | None,
        include_indices: bool,
        include_foreign_keys: bool,
        include_comments: bool,
    ) -> tuple[TableDiff, ...]:
        source_tables: set[str] = set(source.get_table_names(schema=source_schema))
        target_tables: set[str] = set(target.get_table_names(schema=target_schema))

        diffs: list[TableDiff] = []

        # Tablas solo en source
        for table in sorted(source_tables - target_tables):
            diffs.append(TableDiff(table_name=table, status="added"))

        # Tablas solo en target
        for table in sorted(target_tables - source_tables):
            diffs.append(TableDiff(table_name=table, status="removed"))

        # Tablas comunes
        for table in sorted(source_tables & target_tables):
            # Pre-fetch columnas una sola vez para reutilizar en _compare_columns y _compare_comments
            source_cols_raw: list[Any] = source.get_columns(table, schema=source_schema)
            target_cols_raw: list[Any] = target.get_columns(table, schema=target_schema)

            col_diffs = self._compare_columns_from_raw(
                source_cols_raw,
                target_cols_raw,
                source.get_pk_constraint(table, schema=source_schema),
                target.get_pk_constraint(table, schema=target_schema),
            )
            idx_diffs: tuple[IndexDiff, ...] = ()
            fk_diffs: tuple[ForeignKeyDiff, ...] = ()
            comment_diffs: tuple[CommentDiff, ...] = ()

            if include_indices:
                idx_diffs = self._compare_indices(source, target, table, source_schema, target_schema)
            if include_foreign_keys:
                fk_diffs = self._compare_foreign_keys(source, target, table, source_schema, target_schema)
            if include_comments:
                comment_diffs = self._compare_comments_from_raw(
                    source_cols_raw,
                    target_cols_raw,
                    table,
                    self._get_table_comment_safe(source, table, source_schema),
                    self._get_table_comment_safe(target, table, target_schema),
                )

            if col_diffs or idx_diffs or fk_diffs or comment_diffs:
                diffs.append(
                    TableDiff(
                        table_name=table,
                        status="modified",
                        column_diffs=col_diffs,
                        index_diffs=idx_diffs,
                        fk_diffs=fk_diffs,
                        comment_diffs=comment_diffs,
                    )
                )

        return tuple(diffs)

    # ------------------------------------------------------------------
    # Columnas
    # ------------------------------------------------------------------

    def _compare_columns(
        self,
        source: Inspector,
        target: Inspector,
        table: str,
        source_schema: str | None,
        target_schema: str | None,
    ) -> tuple[ColumnDiff, ...]:
        """Sobrecarga de conveniencia que obtiene columnas y PK desde el inspector."""
        return self._compare_columns_from_raw(
            source.get_columns(table, schema=source_schema),
            target.get_columns(table, schema=target_schema),
            source.get_pk_constraint(table, schema=source_schema),
            target.get_pk_constraint(table, schema=target_schema),
        )

    @staticmethod
    def _compare_columns_from_raw(
        source_cols_raw: list[Any],
        target_cols_raw: list[Any],
        source_pk: Any,
        target_pk: Any,
    ) -> tuple[ColumnDiff, ...]:
        """Compara columnas a partir de listas ya cargadas (evita doble consulta)."""
        source_cols: dict[str, Any] = {col["name"]: col for col in source_cols_raw}
        target_cols: dict[str, Any] = {col["name"]: col for col in target_cols_raw}

        source_pks: list[str] = (source_pk or {}).get("constrained_columns") or []
        target_pks: list[str] = (target_pk or {}).get("constrained_columns") or []

        diffs: list[ColumnDiff] = []

        # Columnas solo en source
        for col_name in sorted(set(source_cols) - set(target_cols)):
            diffs.append(
                ColumnDiff(column_name=col_name, attribute="existence", source_value="exists", target_value="missing")
            )

        # Columnas solo en target
        for col_name in sorted(set(target_cols) - set(source_cols)):
            diffs.append(
                ColumnDiff(column_name=col_name, attribute="existence", source_value="missing", target_value="exists")
            )

        # Columnas comunes — comparar atributos
        for col_name in sorted(set(source_cols) & set(target_cols)):
            diffs.extend(
                SchemaComparator._diff_common_column(
                    col_name,
                    source_cols[col_name],
                    target_cols[col_name],
                    source_pks,
                    target_pks,
                )
            )

        return tuple(diffs)

    @staticmethod
    def _diff_common_column(
        col_name: str,
        s_col: dict[str, Any],
        t_col: dict[str, Any],
        source_pks: list[str],
        target_pks: list[str],
    ) -> list[ColumnDiff]:
        """Devuelve los ColumnDiff para una columna presente en ambos esquemas."""
        diffs: list[ColumnDiff] = []

        s_type = str(s_col.get("type", ""))
        t_type = str(t_col.get("type", ""))
        if s_type != t_type:
            diffs.append(ColumnDiff(column_name=col_name, attribute="type", source_value=s_type, target_value=t_type))

        s_nullable = str(s_col.get("nullable", True))
        t_nullable = str(t_col.get("nullable", True))
        if s_nullable != t_nullable:
            diffs.append(
                ColumnDiff(column_name=col_name, attribute="nullable", source_value=s_nullable, target_value=t_nullable)
            )

        s_pk = str(col_name in source_pks)
        t_pk = str(col_name in target_pks)
        if s_pk != t_pk:
            diffs.append(
                ColumnDiff(column_name=col_name, attribute="primary_key", source_value=s_pk, target_value=t_pk)
            )

        s_default = str(s_col.get("default") or "")
        t_default = str(t_col.get("default") or "")
        if s_default != t_default:
            diffs.append(
                ColumnDiff(column_name=col_name, attribute="default", source_value=s_default, target_value=t_default)
            )

        return diffs

    # ------------------------------------------------------------------
    # Índices
    # ------------------------------------------------------------------

    def _compare_indices(
        self,
        source: Inspector,
        target: Inspector,
        table: str,
        source_schema: str | None,
        target_schema: str | None,
    ) -> tuple[IndexDiff, ...]:
        source_idx = self._get_indexes_safe(source, table, source_schema)
        target_idx = self._get_indexes_safe(target, table, target_schema)

        source_map: dict[str, dict[str, Any]] = {idx["name"]: idx for idx in source_idx if idx.get("name")}
        target_map: dict[str, dict[str, Any]] = {idx["name"]: idx for idx in target_idx if idx.get("name")}

        diffs: list[IndexDiff] = []

        for idx_name in sorted(set(source_map) - set(target_map)):
            idx = source_map[idx_name]
            diffs.append(
                IndexDiff(
                    index_name=idx_name,
                    table_name=table,
                    status="added",
                    source_columns=self._join_columns(idx.get("column_names")),
                    source_unique=bool(idx.get("unique", False)),
                )
            )

        for idx_name in sorted(set(target_map) - set(source_map)):
            idx = target_map[idx_name]
            diffs.append(
                IndexDiff(
                    index_name=idx_name,
                    table_name=table,
                    status="removed",
                    target_columns=self._join_columns(idx.get("column_names")),
                    target_unique=bool(idx.get("unique", False)),
                )
            )

        for idx_name in sorted(set(source_map) & set(target_map)):
            s_idx = source_map[idx_name]
            t_idx = target_map[idx_name]
            s_cols = self._join_columns(s_idx.get("column_names"))
            t_cols = self._join_columns(t_idx.get("column_names"))
            s_unique = bool(s_idx.get("unique", False))
            t_unique = bool(t_idx.get("unique", False))
            if s_cols != t_cols or s_unique != t_unique:
                diffs.append(
                    IndexDiff(
                        index_name=idx_name,
                        table_name=table,
                        status="modified",
                        source_columns=s_cols,
                        target_columns=t_cols,
                        source_unique=s_unique,
                        target_unique=t_unique,
                    )
                )

        return tuple(diffs)

    # ------------------------------------------------------------------
    # Foreign Keys
    # ------------------------------------------------------------------

    def _compare_foreign_keys(
        self,
        source: Inspector,
        target: Inspector,
        table: str,
        source_schema: str | None,
        target_schema: str | None,
    ) -> tuple[ForeignKeyDiff, ...]:
        source_fks = list(source.get_foreign_keys(table, schema=source_schema))
        target_fks = list(target.get_foreign_keys(table, schema=target_schema))

        source_map: dict[str, Any] = {str(fk.get("name", "")): fk for fk in source_fks if fk.get("name")}
        target_map: dict[str, Any] = {str(fk.get("name", "")): fk for fk in target_fks if fk.get("name")}

        diffs: list[ForeignKeyDiff] = []

        for fk_name in sorted(set(source_map) - set(target_map)):
            fk = source_map[fk_name]
            diffs.append(
                ForeignKeyDiff(
                    fk_name=fk_name,
                    table_name=table,
                    status="added",
                    source_columns=",".join(fk.get("constrained_columns", [])),
                    source_referred_table=fk.get("referred_table", ""),
                    source_referred_columns=",".join(fk.get("referred_columns", [])),
                )
            )

        for fk_name in sorted(set(target_map) - set(source_map)):
            fk = target_map[fk_name]
            diffs.append(
                ForeignKeyDiff(
                    fk_name=fk_name,
                    table_name=table,
                    status="removed",
                    target_columns=",".join(fk.get("constrained_columns", [])),
                    target_referred_table=fk.get("referred_table", ""),
                    target_referred_columns=",".join(fk.get("referred_columns", [])),
                )
            )

        for fk_name in sorted(set(source_map) & set(target_map)):
            s_fk = source_map[fk_name]
            t_fk = target_map[fk_name]
            s_cols = ",".join(s_fk.get("constrained_columns", []))
            t_cols = ",".join(t_fk.get("constrained_columns", []))
            s_ref = s_fk.get("referred_table", "")
            t_ref = t_fk.get("referred_table", "")
            s_ref_cols = ",".join(s_fk.get("referred_columns", []))
            t_ref_cols = ",".join(t_fk.get("referred_columns", []))

            if s_cols != t_cols or s_ref != t_ref or s_ref_cols != t_ref_cols:
                diffs.append(
                    ForeignKeyDiff(
                        fk_name=fk_name,
                        table_name=table,
                        status="modified",
                        source_columns=s_cols,
                        target_columns=t_cols,
                        source_referred_table=s_ref,
                        target_referred_table=t_ref,
                        source_referred_columns=s_ref_cols,
                        target_referred_columns=t_ref_cols,
                    )
                )

        return tuple(diffs)

    # ------------------------------------------------------------------
    # Comentarios
    # ------------------------------------------------------------------

    def _compare_comments(
        self,
        source: Inspector,
        target: Inspector,
        table: str,
        source_schema: str | None,
        target_schema: str | None,
    ) -> tuple[CommentDiff, ...]:
        """Sobrecarga de conveniencia que obtiene columnas y comentarios desde el inspector."""
        return self._compare_comments_from_raw(
            source.get_columns(table, schema=source_schema),
            target.get_columns(table, schema=target_schema),
            table,
            self._get_table_comment_safe(source, table, source_schema),
            self._get_table_comment_safe(target, table, target_schema),
        )

    @staticmethod
    def _compare_comments_from_raw(
        source_cols_raw: list[Any],
        target_cols_raw: list[Any],
        table: str,
        s_table_comment: str,
        t_table_comment: str,
    ) -> tuple[CommentDiff, ...]:
        """Compara comentarios de tabla y columnas a partir de datos ya cargados."""
        diffs: list[CommentDiff] = []

        if s_table_comment != t_table_comment:
            diffs.append(
                CommentDiff(
                    object_name=table,
                    column_name=None,
                    source_comment=s_table_comment,
                    target_comment=t_table_comment,
                )
            )

        source_cols: dict[str, Any] = {col["name"]: col for col in source_cols_raw}
        target_cols: dict[str, Any] = {col["name"]: col for col in target_cols_raw}
        for col_name in sorted(set(source_cols) & set(target_cols)):
            s_col_comment = str(source_cols[col_name].get("comment") or "")
            t_col_comment = str(target_cols[col_name].get("comment") or "")
            if s_col_comment != t_col_comment:
                diffs.append(
                    CommentDiff(
                        object_name=table,
                        column_name=col_name,
                        source_comment=s_col_comment,
                        target_comment=t_col_comment,
                    )
                )

        return tuple(diffs)

    # ------------------------------------------------------------------
    # Vistas
    # ------------------------------------------------------------------

    def _compare_views(
        self,
        source: Inspector,
        target: Inspector,
        source_schema: str | None,
        target_schema: str | None,
    ) -> tuple[ViewDiff, ...]:
        source_views: set[str] = set(source.get_view_names(schema=source_schema))
        target_views: set[str] = set(target.get_view_names(schema=target_schema))

        diffs: list[ViewDiff] = []

        for view_name in sorted(source_views - target_views):
            s_def = self._get_view_definition_safe(source, view_name, source_schema)
            diffs.append(ViewDiff(view_name=view_name, status="added", source_definition=s_def))

        for view_name in sorted(target_views - source_views):
            t_def = self._get_view_definition_safe(target, view_name, target_schema)
            diffs.append(ViewDiff(view_name=view_name, status="removed", target_definition=t_def))

        for view_name in sorted(source_views & target_views):
            s_def = self._get_view_definition_safe(source, view_name, source_schema)
            t_def = self._get_view_definition_safe(target, view_name, target_schema)
            s_norm = self._normalize_ddl(s_def)
            t_norm = self._normalize_ddl(t_def)
            if s_norm != t_norm:
                diffs.append(
                    ViewDiff(view_name=view_name, status="modified", source_definition=s_def, target_definition=t_def)
                )

        return tuple(diffs)

    # ------------------------------------------------------------------
    # Routines
    # ------------------------------------------------------------------

    def _compare_routines(
        self,
        source: Inspector,
        target: Inspector,
        source_schema: str | None,
        target_schema: str | None,
    ) -> tuple[RoutineDiff, ...]:
        """Compara procedures/functions si el dialect lo soporta.

        Utiliza ``Inspector.get_multi_indexes`` como indicador de capacidad.
        Si el dialect no soporta listado de routines, devuelve tupla vacía.
        """
        source_routines = self._get_routines_safe(source, source_schema)
        target_routines = self._get_routines_safe(target, target_schema)

        if source_routines is None and target_routines is None:
            logger.debug("El dialect no soporta listado de routines; se omite la comparación.")
            return ()

        source_map: dict[str, dict[str, str]] = {r["name"]: r for r in (source_routines or [])}
        target_map: dict[str, dict[str, str]] = {r["name"]: r for r in (target_routines or [])}

        diffs: list[RoutineDiff] = []

        for name in sorted(set(source_map) - set(target_map)):
            r = source_map[name]
            diffs.append(
                RoutineDiff(
                    routine_name=name,
                    routine_type=cast(Literal["PROCEDURE", "FUNCTION"], r.get("type", "PROCEDURE")),
                    status="added",
                    source_definition=r.get("definition", ""),
                )
            )

        for name in sorted(set(target_map) - set(source_map)):
            r = target_map[name]
            diffs.append(
                RoutineDiff(
                    routine_name=name,
                    routine_type=cast(Literal["PROCEDURE", "FUNCTION"], r.get("type", "PROCEDURE")),
                    status="removed",
                    target_definition=r.get("definition", ""),
                )
            )

        for name in sorted(set(source_map) & set(target_map)):
            s_r = source_map[name]
            t_r = target_map[name]
            s_norm = self._normalize_ddl(s_r.get("definition", ""))
            t_norm = self._normalize_ddl(t_r.get("definition", ""))
            if s_norm != t_norm:
                diffs.append(
                    RoutineDiff(
                        routine_name=name,
                        routine_type=cast(Literal["PROCEDURE", "FUNCTION"], s_r.get("type", "PROCEDURE")),
                        status="modified",
                        source_definition=s_r.get("definition", ""),
                        target_definition=t_r.get("definition", ""),
                    )
                )

        return tuple(diffs)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_label(inspector: Inspector, schema: str | None) -> str:
        """Construye una etiqueta legible para el inspector."""
        url = str(getattr(inspector.bind, "url", "unknown") if hasattr(inspector, "bind") else "unknown")
        # Ocultar credenciales si las hay
        url = re.sub(r"://[^@]+@", "://***@", url)
        if schema:
            return f"{url} [{schema}]"
        return url

    @staticmethod
    def _strip_dialect_artifacts(definition: str) -> str:
        """Aplica las reglas dialect-específicas de limpieza de DDL registradas en ``_DDL_STRIP_RULES``.

        Permite añadir reglas para nuevos motores sin modificar ``_normalize_ddl``.
        """
        result = definition
        for pattern, repl in SchemaComparator._DDL_STRIP_RULES:
            result = re.sub(pattern, repl, result, flags=re.IGNORECASE)
        return result

    @staticmethod
    def _normalize_ddl(definition: str) -> str:
        """Normalización universal de DDL: elimina artefactos de motor y colapsa espacios."""
        if not definition:
            return ""
        cleaned = SchemaComparator._strip_dialect_artifacts(definition)
        return re.sub(r"\s+", " ", cleaned).strip().lower()

    @staticmethod
    def _join_columns(column_names: list[str] | None) -> str:
        """Une nombres de columnas filtrando Nones."""
        if not column_names:
            return ""
        return ",".join(c for c in column_names if c is not None)

    @staticmethod
    def _get_indexes_safe(inspector: Inspector, table: str, schema: str | None) -> list[Any]:
        """Obtiene índices ignorando NotImplementedError de algunos dialects."""
        try:
            return list(inspector.get_indexes(table, schema=schema))
        except NotImplementedError:
            return []

    @staticmethod
    def _get_table_comment_safe(inspector: Inspector, table: str, schema: str | None) -> str:
        """Obtiene comentario de tabla; devuelve cadena vacía si no está soportado."""
        try:
            result = inspector.get_table_comment(table, schema=schema)
            return str(result.get("text") or "") if result else ""
        except NotImplementedError:
            return ""

    @staticmethod
    def _get_view_definition_safe(inspector: Inspector, view_name: str, schema: str | None) -> str:
        """Obtiene definición de vista; devuelve cadena vacía si falla."""
        try:
            definition = inspector.get_view_definition(view_name, schema=schema)
            return str(definition) if definition else ""
        except NotImplementedError:
            return ""
        except Exception as exc:  # noqa: BLE001 — algunos dialects fallan inesperadamente
            logger.warning("No se pudo obtener definición de vista '%s': %s", view_name, exc)
            return ""

    @staticmethod
    def _get_routines_safe(inspector: Inspector, schema: str | None) -> list[dict[str, str]] | None:
        """Intenta listar routines via reflect/dialect; devuelve None si no es posible.

        Nota: ``Inspector`` de SQLAlchemy no tiene API estándar para routines.
        Esta implementación delega al registro ``_ROUTINE_FETCHERS`` por nombre de dialect.
        Para soportar un nuevo motor sin modificar este método::

            SchemaComparator._ROUTINE_FETCHERS["mssql"] = my_mssql_fetcher
        """
        bind = getattr(inspector, "bind", None)
        dialect_name: str = getattr(getattr(bind, "dialect", None), "name", "") or getattr(bind, "name", "")

        fetcher = SchemaComparator._ROUTINE_FETCHERS.get(dialect_name)
        return fetcher(inspector, schema) if fetcher is not None else None

    @staticmethod
    def _get_routines_mariadb(inspector: Inspector, schema: str | None) -> list[dict[str, str]]:
        """Obtiene routines de MariaDB/MySQL via SHOW PROCEDURE STATUS / SHOW CREATE PROCEDURE."""
        from sqlalchemy import text

        routines: list[dict[str, str]] = []
        bind = inspector.bind
        if bind is None:
            return routines

        engine = cast("Engine", bind)
        db_name = schema or str(getattr(engine, "url", None) and getattr(engine.url, "database", "") or "")

        try:
            with engine.connect() as conn:
                # Procedures
                proc_result = conn.execute(text("SHOW PROCEDURE STATUS WHERE Db=:db"), {"db": db_name})  # noqa: S608
                for row in proc_result.mappings():
                    proc_name = str(row["Name"])
                    safe_name = proc_name.replace("`", "``")  # escapar backticks
                    create_result = conn.execute(text(f"SHOW CREATE PROCEDURE `{safe_name}`"))  # noqa: S608
                    create_row = create_result.mappings().first()
                    definition = str(create_row["Create Procedure"]) if create_row else ""
                    routines.append({"name": proc_name, "type": "PROCEDURE", "definition": definition})
                # Functions
                func_result = conn.execute(text("SHOW FUNCTION STATUS WHERE Db=:db"), {"db": db_name})  # noqa: S608
                for row in func_result.mappings():
                    func_name = str(row["Name"])
                    safe_name = func_name.replace("`", "``")  # escapar backticks
                    create_result = conn.execute(text(f"SHOW CREATE FUNCTION `{safe_name}`"))  # noqa: S608
                    create_row = create_result.mappings().first()
                    definition = str(create_row["Create Function"]) if create_row else ""
                    routines.append({"name": func_name, "type": "FUNCTION", "definition": definition})
        except Exception as exc:  # noqa: BLE001
            logger.warning("No se pudieron obtener routines MariaDB para schema=%s: %s", schema, exc)

        return routines

    @staticmethod
    def _get_routines_oracle(inspector: Inspector, schema: str | None) -> list[dict[str, str]]:
        """Obtiene routines de Oracle via ALL_PROCEDURES + DBMS_METADATA."""
        from sqlalchemy import text

        routines: list[dict[str, str]] = []
        bind = inspector.bind
        if bind is None:
            return routines
        if not schema:
            logger.warning("_get_routines_oracle requiere 'schema'; se omite la comparación de routines Oracle.")
            return routines
        engine = cast("Engine", bind)

        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT object_name, object_type FROM all_procedures WHERE owner=:schema AND object_type IN ('PROCEDURE','FUNCTION')"
                    ),
                    {"schema": schema.upper()},
                )
                for row in result.mappings():
                    obj_name = str(row["object_name"])
                    obj_type = str(row["object_type"])
                    try:
                        ddl_result = conn.execute(
                            text("SELECT DBMS_METADATA.GET_DDL(:obj_type, :obj_name, :schema) AS ddl FROM dual"),
                            {"obj_type": obj_type, "obj_name": obj_name, "schema": schema.upper()},
                        )
                        ddl_row = ddl_result.first()
                        ddl_val: Any = ddl_row[0] if ddl_row else ""
                        definition = ddl_val.read() if hasattr(ddl_val, "read") else str(ddl_val)
                    except Exception:  # noqa: BLE001
                        definition = ""
                    routines.append({"name": obj_name, "type": obj_type, "definition": definition})
        except Exception as exc:  # noqa: BLE001
            logger.warning("No se pudieron obtener routines Oracle para schema=%s: %s", schema, exc)

        return routines

    # ------------------------------------------------------------------
    # Resumen
    # ------------------------------------------------------------------

    @staticmethod
    def _build_summary(
        table_diffs: tuple[TableDiff, ...],
        view_diffs: tuple[ViewDiff, ...],
        routine_diffs: tuple[RoutineDiff, ...],
    ) -> str:
        """Construye un resumen textual de las diferencias encontradas."""
        parts: list[str] = []
        if table_diffs:
            added = sum(1 for t in table_diffs if t.status == "added")
            removed = sum(1 for t in table_diffs if t.status == "removed")
            modified = sum(1 for t in table_diffs if t.status == "modified")
            parts.append(f"Tablas: {added} añadidas, {removed} eliminadas, {modified} modificadas")
        if view_diffs:
            parts.append(f"Vistas: {len(view_diffs)} diferencias")
        if routine_diffs:
            parts.append(f"Routines: {len(routine_diffs)} diferencias")
        return " | ".join(parts) if parts else "Sin diferencias"


# ---------------------------------------------------------------------------
# Inicialización del registro de fetchers de routines (OCP — extensible sin editar la clase)
# ---------------------------------------------------------------------------
SchemaComparator._ROUTINE_FETCHERS.update(
    {
        "mariadb": SchemaComparator._get_routines_mariadb,
        "mysql": SchemaComparator._get_routines_mariadb,
        "oracle": SchemaComparator._get_routines_oracle,
    }
)
