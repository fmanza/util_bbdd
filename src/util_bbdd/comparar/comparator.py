"""Comparador de esquemas de base de datos motor-agnóstico sobre SQLAlchemy Inspector."""

from __future__ import annotations

import logging
import re

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

from sqlalchemy import CursorResult, Row, RowMapping
from sqlalchemy.engine.base import Engine
from sqlalchemy.engine.interfaces import ReflectedTableComment

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
    #: **Las claves son nombres de dialect SQLAlchemy**, no nombres de motor internos.
    #: Consultar ``_DB_TYPE_TO_DIALECT`` para la correspondencia motor → dialect.
    #: Ejemplo: SQL Server usa clave ``"mssql"``, no ``"sqlserver"``::
    #:
    #:     SchemaComparator._ROUTINE_FETCHERS["mssql"] = my_mssql_fetcher
    _ROUTINE_FETCHERS: ClassVar[dict[str, Callable[[Inspector, str | None], list[dict[str, str]]]]] = {}

    #: Mapa de PostgreSQL procedure kind codes (pg_proc.prokind) a DDL object type labels.
    #: 'f' = function, 'p' = procedure, 'w' = window function.
    #: Used in ``_get_routines_postgresql`` to normalize prokind → DDL type.
    _PROCEDURE_KIND_MAP: ClassVar[dict[str, str]] = {
        "f": "FUNCTION",
        "p": "PROCEDURE",
        "w": "WINDOW",
    }

    #: Reglas de limpieza DDL dialect-específicas aplicadas antes de la normalización universal.
    #: Cada entrada es ``(patron_regex, reemplazo)``.
    #: Para añadir una regla nueva sin modificar ``_normalize_ddl``::
    #:
    #:     SchemaComparator._DDL_STRIP_RULES.append((r"MY_PATTERN", ""))
    _DDL_STRIP_RULES: ClassVar[list[tuple[str, str]]] = [
        # MariaDB / MySQL — ALGORITHM debe ir antes de DEFINER (orden significativo)
        (r"ALGORITHM\s*=\s*\w+", ""),
        # MariaDB / MySQL — DEFINER todas las variantes de comillado y espacios alrededor de =
        (r"DEFINER\s*=\s*`[^`]+`@`[^`]+`", ""),  # backticks
        (r"DEFINER\s*=\s*'[^']*'@'[^']*'", ""),  # comillas simples
        (r"DEFINER\s*=\s*\S+@\S+", ""),  # sin comillas
        # MariaDB / MySQL — SQL SECURITY (cubre tanto inicio como interior del DDL)
        (r"SQL\s+SECURITY\s+(?:DEFINER|INVOKER)", ""),
        # Oracle
        (r"CREATE OR REPLACE FORCE", "CREATE OR REPLACE"),
        # SQL Server: Escaped square brackets around identifiers [name], including special chars [My Column Name]
        (r"\[([^\]]+)\]", r"\1"),
        # SQL Server: WITH storage hints (FILLFACTOR, etc.)
        (r"\s+WITH\s*\([^)]*\)(?=\s|$)", ""),
        # PostgreSQL: LANGUAGE clause
        (r"\s+LANGUAGE\s+\w+", ""),
        # PostgreSQL: SECURITY clauses
        (r"\s+SECURITY\s+(?:DEFINER|INVOKER)", ""),
        # PostgreSQL: NULL handling clauses
        (r"\s+(STRICT|RETURNS\s+NULL\s+ON\s+NULL\s+INPUT)", ""),
    ]

    #: Mapa canónico de nombre de motor interno → nombre de dialect SQLAlchemy.
    #: Necesario porque ``Inspector.dialect.name`` reporta el nombre de dialect de SA,
    #: que puede diferir del nombre interno de la librería (p.ej. ``sqlserver`` → ``mssql``).
    #: Las claves de ``_ROUTINE_FETCHERS`` y ``_DDL_STRIP_RULES`` deben usar los valores de este mapa.
    _DB_TYPE_TO_DIALECT: ClassVar[dict[str, str]] = {
        "mariadb": "mariadb",
        "oracle": "oracle",
        "postgresql": "postgresql",
        "sqlserver": "mssql",  # SQL Server reporta dialect "mssql" en SQLAlchemy
        "sqlite": "sqlite",
        "hsqldb": "hsqldb",
    }

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
                **Nota**: No todos los motores soportan introspección de routines.
                - MariaDB, Oracle, SQL Server, PostgreSQL: ✓ Soportado
                - HSQLDB: ✗ No soportado (DDL no portable); ``include_routines=True`` será ignorado con warning.
                - SQLite: N/A (sin routines)

        Returns:
            ``SchemaDiff`` con todas las diferencias encontradas.

        Performance Considerations:
            **N+1 Query Cascade Warnings:**
                - Each ``include_*`` flag triggers Inspector queries per schema:

                  * ``include_tables=True``: 1 query per table (columns, constraints, indexes)
                  * ``include_foreign_keys=True``: +1 per table for FK relationships
                  * ``include_indices=True``: +1 per table for index details
                  * ``include_comments=True``: +1 per table+column for comment metadata
                  * ``include_routines=True``: +1-2 per routine for DDL materialization (driver-dependent)

                - **Total queries for 100-table schema with all flags enabled**: ~500+ queries per Inspector
                  This is **expected behavior** but can exceed timeout thresholds for large catalogs.

            **Optimization Guide for Large Schemas (100+ tables):**

                1. **Disable unnecessary flags:**

                   .. code-block:: python

                       # Fast comparison (minimal queries)
                       diff = comparator.compare(
                           source, target,
                           include_tables=True,
                           include_views=False,
                           include_indices=False,
                           include_foreign_keys=False,
                           include_comments=False,
                           include_routines=False
                       )

                2. **Filter by schema where possible:**

                   .. code-block:: python

                       # Only compare 'public' schema, not catalog
                       diff = comparator.compare(
                           source, target,
                           source_schema="public",
                           target_schema="public"
                       )

                3. **Increase Inspector timeout:**

                   .. code-block:: python

                       # Set longer timeout at connection level
                       engine = create_engine(
                           "postgresql://user:pass@host/db",
                           connect_args={"connect_timeout": 30}
                       )
                       inspector = inspect(engine)
                       diff = comparator.compare(source, target)

                4. **Cache Inspector results across comparisons:**

                   .. code-block:: python

                       # Reuse inspectors if comparing same source/target multiple times
                       source_inspector = inspect(source_engine)
                       target_inspector = inspect(target_engine)

                       diff1 = comparator.compare(source_inspector, target_inspector, ...)
                       diff2 = comparator.compare(source_inspector, target_inspector, ...)
                       # No extra Inspector queries; SQLAlchemy caches internally

            **Driver-Specific Overhead:**

                - **PostgreSQL/Oracle/SQL Server**: ``include_routines=True`` materializes full DDL;
                  can be slow if many routines exist. Consider disabling for first pass.
                - **MariaDB**: Uses ``information_schema`` which is fast but locks during ``SHOW CREATE`` fallback.
                - **SQLite**: No significant overhead (single file, no remote I/O).
                - **HSQLDB**: Introspection is synchronous and slower; avoid large schemas.

            **Cost Analysis by Flag Combinations:**

                +-------+-------+-------+---------+----------+----------+
                | Table | Index | FK    | Comment | Routine  | Estimate |
                +=======+=======+=======+=========+==========+==========+
                | ✓     | ✗     | ✗     | ✗       | ✗        | ~200 q   |
                +-------+-------+-------+---------+----------+----------+
                | ✓     | ✓     | ✗     | ✗       | ✗        | ~300 q   |
                +-------+-------+-------+---------+----------+----------+
                | ✓     | ✓     | ✓     | ✗       | ✗        | ~400 q   |
                +-------+-------+-------+---------+----------+----------+
                | ✓     | ✓     | ✓     | ✓       | ✗        | ~500 q   |
                +-------+-------+-------+---------+----------+----------+
                | ✓     | ✓     | ✓     | ✓       | ✓        | ~600+ q  |
                +-------+-------+-------+---------+----------+----------+

                (Estimates for 100-table PostgreSQL schema; actual varies by catalog size and driver)
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
        source_idx: list[Any] = self._get_indexes_safe(source, table, source_schema)
        target_idx: list[Any] = self._get_indexes_safe(target, table, target_schema)

        source_map: dict[str, dict[str, Any]] = {idx["name"]: idx for idx in source_idx if idx.get("name")}
        target_map: dict[str, dict[str, Any]] = {idx["name"]: idx for idx in target_idx if idx.get("name")}

        diffs: list[IndexDiff] = []

        for idx_name in sorted(set(source_map) - set(target_map)):
            source_index_dict = source_map[idx_name]
            diffs.append(
                IndexDiff(
                    index_name=idx_name,
                    table_name=table,
                    status="added",
                    source_columns=self._join_columns(source_index_dict.get("column_names")),
                    source_unique=bool(source_index_dict.get("unique", False)),
                )
            )

        for idx_name in sorted(set(target_map) - set(source_map)):
            target_index_dict = target_map[idx_name]
            diffs.append(
                IndexDiff(
                    index_name=idx_name,
                    table_name=table,
                    status="removed",
                    target_columns=self._join_columns(target_index_dict.get("column_names")),
                    target_unique=bool(target_index_dict.get("unique", False)),
                )
            )

        for idx_name in sorted(set(source_map) & set(target_map)):
            s_idx: dict[str, Any] = source_map[idx_name]
            t_idx: dict[str, Any] = target_map[idx_name]
            s_cols: str = self._join_columns(s_idx.get("column_names"))
            t_cols: str = self._join_columns(t_idx.get("column_names"))
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
            s_cols: str = ",".join(s_fk.get("constrained_columns", []))
            t_cols: str = ",".join(t_fk.get("constrained_columns", []))
            s_ref = s_fk.get("referred_table", "")
            t_ref = t_fk.get("referred_table", "")
            s_ref_cols: str = ",".join(s_fk.get("referred_columns", []))
            t_ref_cols: str = ",".join(t_fk.get("referred_columns", []))

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
            source_def = self._get_view_definition_safe(source, view_name, source_schema)
            diffs.append(ViewDiff(view_name=view_name, status="added", source_definition=source_def))

        for view_name in sorted(target_views - source_views):
            target_def = self._get_view_definition_safe(target, view_name, target_schema)
            diffs.append(ViewDiff(view_name=view_name, status="removed", target_definition=target_def))

        for view_name in sorted(source_views & target_views):
            source_def_cmp: str = self._get_view_definition_safe(source, view_name, source_schema)
            target_def_cmp: str = self._get_view_definition_safe(target, view_name, target_schema)
            s_norm: str = self._normalize_ddl(source_def_cmp)
            t_norm: str = self._normalize_ddl(target_def_cmp)
            if s_norm != t_norm:
                diffs.append(
                    ViewDiff(
                        view_name=view_name,
                        status="modified",
                        source_definition=source_def_cmp,
                        target_definition=target_def_cmp,
                    )
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
        source_routines: list[dict[str, str]] | None = self._get_routines_safe(source, source_schema)
        target_routines: list[dict[str, str]] | None = self._get_routines_safe(target, target_schema)

        if source_routines is None and target_routines is None:
            logger.debug("El dialect no soporta listado de routines; se omite la comparación.")
            return ()

        source_map: dict[str, dict[str, str]] = {r["name"]: r for r in (source_routines or [])}
        target_map: dict[str, dict[str, str]] = {r["name"]: r for r in (target_routines or [])}

        diffs: list[RoutineDiff] = []

        for name in sorted(set(source_map) - set(target_map)):
            source_routine = source_map[name]
            diffs.append(
                RoutineDiff(
                    routine_name=name,
                    routine_type=cast(Literal["PROCEDURE", "FUNCTION"], source_routine.get("type", "PROCEDURE")),
                    status="added",
                    source_definition=source_routine.get("definition", ""),
                )
            )

        for name in sorted(set(target_map) - set(source_map)):
            target_routine: dict[str, str] = target_map[name]
            diffs.append(
                RoutineDiff(
                    routine_name=name,
                    routine_type=cast(Literal["PROCEDURE", "FUNCTION"], target_routine.get("type", "PROCEDURE")),
                    status="removed",
                    target_definition=target_routine.get("definition", ""),
                )
            )

        for name in sorted(set(source_map) & set(target_map)):
            s_r: dict[str, str] = source_map[name]
            t_r: dict[str, str] = target_map[name]
            s_norm: str = self._normalize_ddl(s_r.get("definition", ""))
            t_norm: str = self._normalize_ddl(t_r.get("definition", ""))
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
        # inspector.engine es el atributo canónico en SA 2.x; inspector.bind es el alias
        # deprecated de SA 1.4 que fue eliminado en SA 2.0.
        engine: Any | None = getattr(inspector, "engine", getattr(inspector, "bind", None))
        url_str = str(getattr(engine, "url", "unknown"))
        # Ocultar credenciales si las hay
        url: str = re.sub(r"://[^@]+@", "://***@", url_str)
        if schema:
            return f"{url} [{schema}]"
        return url

    @staticmethod
    def _strip_dialect_artifacts(definition: str) -> str:
        """Aplica las reglas dialect-específicas de limpieza de DDL registradas en ``_DDL_STRIP_RULES``.

        Permite añadir reglas para nuevos motores sin modificar ``_normalize_ddl``.
        """
        result: str = definition
        for pattern, repl in SchemaComparator._DDL_STRIP_RULES:
            result = re.sub(pattern, repl, result, flags=re.IGNORECASE)
        return result

    @staticmethod
    def _normalize_ddl(definition: str) -> str:
        """Normalización universal de DDL: elimina artefactos de motor y colapsa espacios."""
        if not definition:
            return ""
        cleaned: str = SchemaComparator._strip_dialect_artifacts(definition)
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
            result: ReflectedTableComment = inspector.get_table_comment(table, schema=schema)
            return str(result.get("text") or "") if result else ""
        except NotImplementedError:
            return ""

    @staticmethod
    def _get_view_definition_safe(inspector: Inspector, view_name: str, schema: str | None) -> str:
        """Obtiene definición de vista; devuelve cadena vacía si falla."""
        try:
            definition: str = inspector.get_view_definition(view_name, schema=schema)
            return str(definition) if definition else ""
        except NotImplementedError:
            return ""
        except Exception as exc:  # M1: Fallback para dialects sin soporte de vista DDL o permisos insuficientes
            logger.warning("No se pudo obtener definición de vista '%s': %s", view_name, exc)
            return ""

    @staticmethod
    def _get_routines_safe(inspector: Inspector, schema: str | None) -> list[dict[str, str]] | None:
        """Intenta listar routines via reflect/dialect; devuelve None si no es posible.

        Nota: ``Inspector`` de SQLAlchemy no tiene API estándar para routines.
        Esta implementación delega al registro ``_ROUTINE_FETCHERS`` usando el nombre de
        **dialect SQLAlchemy** (p.ej. ``"mssql"`` para SQL Server, no ``"sqlserver"``).
        Consultar ``_DB_TYPE_TO_DIALECT`` para la correspondencia completa motor → dialect.

        Para soportar un nuevo motor sin modificar este método::

            SchemaComparator._ROUTINE_FETCHERS[
                SchemaComparator._DB_TYPE_TO_DIALECT["sqlserver"]  # → "mssql"
            ] = my_mssql_fetcher
        """
        # inspector.engine es canónico en SA 2.x; fallback a bind para SA 1.4.
        engine: Any | None = getattr(inspector, "engine", getattr(inspector, "bind", None))
        dialect_name: str = getattr(getattr(engine, "dialect", None), "name", "")

        fetcher: Callable[[Inspector, str | None], list[dict[str, str]]] | None = (
            SchemaComparator._ROUTINE_FETCHERS.get(dialect_name)
        )
        return fetcher(inspector, schema) if fetcher is not None else None

    @staticmethod
    def _get_routines_mariadb(inspector: Inspector, schema: str | None) -> list[dict[str, str]]:
        """Obtiene routines de MariaDB/MySQL via SHOW PROCEDURE STATUS / SHOW CREATE PROCEDURE.

        **Performance note**: SHOW PROCEDURE STATUS is relatively fast, but large databases
        benefit from pagination or result limiting. For performance-critical scenarios,
        consider:``SchemaComparator.compare(..., include_routines=False)``.
        """
        from sqlalchemy import text

        routines: list[dict[str, str]] = []
        engine: Engine = cast("Engine", getattr(inspector, "engine", getattr(inspector, "bind", None)))
        if engine is None:
            return routines

        db_name: str = schema or str(getattr(engine, "url", None) and getattr(engine.url, "database", "") or "")

        try:
            with engine.connect() as conn:
                # Procedures
                proc_result: CursorResult[Any] = conn.execute(
                    text("SHOW PROCEDURE STATUS WHERE Db=:db"), {"db": db_name}
                )  # noqa: S608
                for row in proc_result.mappings():
                    proc_name = str(row["Name"])
                    proc_safe_name = proc_name.replace("`", "``")  # escapar backticks
                    proc_create_result = conn.execute(text(f"SHOW CREATE PROCEDURE `{proc_safe_name}`"))  # noqa: S608
                    proc_create_row = proc_create_result.mappings().first()
                    proc_definition = str(proc_create_row["Create Procedure"]) if proc_create_row else ""
                    routines.append({"name": proc_name, "type": "PROCEDURE", "definition": proc_definition})
                # Functions
                func_result: CursorResult[Any] = conn.execute(
                    text("SHOW FUNCTION STATUS WHERE Db=:db"), {"db": db_name}
                )  # noqa: S608
                for row in func_result.mappings():
                    func_name = str(row["Name"])
                    func_safe_name: str = func_name.replace("`", "``")  # escapar backticks
                    func_create_result: CursorResult[Any] = conn.execute(
                        text(f"SHOW CREATE FUNCTION `{func_safe_name}`")
                    )  # noqa: S608
                    func_create_row: RowMapping | None = func_create_result.mappings().first()
                    func_definition: str = str(func_create_row["Create Function"]) if func_create_row else ""
                    routines.append({"name": func_name, "type": "FUNCTION", "definition": func_definition})
        except (
            Exception
        ) as exc:  # M1: Fallback si MariaDB rechaza conexión, permisos insuficientes o estado impredecible
            logger.warning("No se pudieron obtener routines MariaDB para schema=%s: %s", schema, exc)

        return routines

    @staticmethod
    def _get_routines_oracle(inspector: Inspector, schema: str | None) -> list[dict[str, str]]:
        """Obtiene routines de Oracle via ALL_PROCEDURES + DBMS_METADATA.

        **Performance note**: DBMS_METADATA.GET_DDL() can be slow on large catalogs (5k+ procedures).
        Index queries on ALL_PROCEDURES and consider result caching for repeated comparisons.
        For performance-critical workloads, disable routine introspection:
        ``SchemaComparator.compare(..., include_routines=False)``."""
        from sqlalchemy import text

        routines: list[dict[str, str]] = []
        engine: Engine = cast("Engine", getattr(inspector, "engine", getattr(inspector, "bind", None)))
        if engine is None:
            return routines
        if not schema:
            logger.warning("_get_routines_oracle requiere 'schema'; se omite la comparación de routines Oracle.")
            return routines

        try:
            with engine.connect() as conn:
                result: CursorResult[Any] = conn.execute(
                    text(
                        "SELECT object_name, object_type FROM all_procedures WHERE owner=:schema AND object_type IN ('PROCEDURE','FUNCTION')"
                    ),
                    {"schema": schema.upper()},
                )
                for row in result.mappings():
                    obj_name = str(row["object_name"])
                    obj_type = str(row["object_type"])
                    try:
                        ddl_result: CursorResult[Any] = conn.execute(
                            text("SELECT DBMS_METADATA.GET_DDL(:obj_type, :obj_name, :schema) AS ddl FROM dual"),
                            {"obj_type": obj_type, "obj_name": obj_name, "schema": schema.upper()},
                        )
                        ddl_row: Row[Any] | None = ddl_result.first()
                        ddl_val: Any = ddl_row[0] if ddl_row else ""
                        definition: Any | str = ddl_val.read() if hasattr(ddl_val, "read") else str(ddl_val)
                    except (
                        Exception
                    ):  # M1: DBMS_METADATA.GET_DDL() falla por objeto corrompido, permisos, memoria insuficiente
                        definition = ""
                    routines.append({"name": obj_name, "type": obj_type, "definition": definition})
        except Exception as exc:  # M1: Fallback si Oracle rechaza conexión o query a all_procedures falla
            logger.warning("No se pudieron obtener routines Oracle para schema=%s: %s", schema, exc)

        return routines

    @staticmethod
    def _get_routines_mssql(inspector: Inspector, schema: str | None) -> list[dict[str, str]]:
        """Obtiene routines de SQL Server via sys.procedures + sys.sql_modules.

        **Performance note**: On large schemas (10k+ procedures), this may be slow.
        Consider disabling routine introspection for performance-critical scenarios:
        ``SchemaComparator.compare(..., include_routines=False)``.
        """
        from sqlalchemy import text

        routines: list[dict[str, str]] = []
        engine: Engine = cast("Engine", getattr(inspector, "engine", getattr(inspector, "bind", None)))
        if engine is None:
            return routines

        schema_name: str = schema or "dbo"

        try:
            with engine.connect() as conn:
                # Procedures (type 'P')
                result: CursorResult[Any] = conn.execute(
                    text("SELECT name FROM sys.procedures WHERE schema_id = SCHEMA_ID(:schema) ORDER BY name"),
                    {"schema": schema_name},
                )
                for row in result.mappings():
                    proc_name = str(row["name"])
                    try:
                        ddl_result: CursorResult[Any] = conn.execute(
                            text(
                                "SELECT definition FROM sys.sql_modules "
                                "WHERE object_id = OBJECT_ID(CONCAT(:schema_name, '.', :proc_name))"
                            ),
                            {"schema_name": schema_name, "proc_name": proc_name},
                        )
                        ddl_row: Row[Any] | None = ddl_result.first()
                        definition: str = str(ddl_row[0]) if ddl_row else ""
                    except (
                        Exception
                    ):  # M1: sys.sql_modules falla por permisos de sys, procedure encriptada o estado impredecible
                        definition = ""
                    routines.append({"name": proc_name, "type": "PROCEDURE", "definition": definition})
        except Exception as exc:  # M1: Fallback si SQL Server rechaza conexión o query a sys.procedures falla
            logger.warning("No se pudieron obtener routines SQL Server para schema=%s: %s", schema, exc)

        return routines

    @staticmethod
    def _get_routines_postgresql(inspector: Inspector, schema: str | None) -> list[dict[str, str]]:
        """Obtiene routines de PostgreSQL via pg_proc + pg_get_functiondef.

        **Performance note**: Uses pg_get_functiondef() which materializes full DDL.
        On schemas with 10k+ functions, this may consume significant memory.
        Consider caching results or disabling routine introspection for large catalogs.
        """
        from sqlalchemy import text

        routines: list[dict[str, str]] = []
        engine: Engine = cast("Engine", getattr(inspector, "engine", getattr(inspector, "bind", None)))
        if engine is None:
            return routines

        schema_name: str = schema or "public"

        try:
            with engine.connect() as conn:
                # Functions and procedures (pg_proc)
                result: CursorResult[Any] = conn.execute(
                    text(
                        "SELECT p.proname, p.prokind "
                        "FROM pg_proc p "
                        "JOIN pg_namespace n ON p.pronamespace = n.oid "
                        "WHERE n.nspname = :schema "
                        "ORDER BY p.proname"
                    ),
                    {"schema": schema_name},
                )
                for row in result.mappings():
                    func_name = str(row["proname"])
                    proc_kind = str(row["prokind"])  # M1: 'f' = function, 'p' = procedure, 'w' = window
                    kind_label: str = SchemaComparator._PROCEDURE_KIND_MAP.get(proc_kind, "PROCEDURE")

                    try:
                        # Try pg_get_functiondef for functions; fall back to empty definition for procedures
                        # M1: Use parameterized query to prevent SQL injection via regprocedure cast
                        ddl_result: CursorResult[Any] = conn.execute(
                            text(
                                "SELECT pg_get_functiondef((:schema_name || '.' || :func_name)::regprocedure) AS definition"
                            ),
                            {"schema_name": schema_name, "func_name": func_name},
                        )
                        ddl_row: Row[Any] | None = ddl_result.first()
                        definition: str = str(ddl_row[0]) if ddl_row and ddl_row[0] else ""
                    except (
                        Exception
                    ):  # M1: pg_get_functiondef() falla si función está en C o lenguaje no soportado internamente
                        definition = ""
                    routines.append({"name": func_name, "type": kind_label, "definition": definition})
        except Exception as exc:  # M1: Fallback si PostgreSQL rechaza conexión o query a pg_proc falla
            logger.warning("No se pudieron obtener routines PostgreSQL para schema=%s: %s", schema, exc)

        return routines

    @staticmethod
    def _get_routines_hsqldb(inspector: Inspector, schema: str | None) -> list[dict[str, str]]:
        """Obtiene routines de HSQLDB (sin soporte de DDL; retorna lista vacía con warning).

        **Limitación**: HSQLDB soporta ``INFORMATION_SCHEMA.ROUTINES``, pero no proporciona
        una forma portable de extraer el DDL (definición) de procedures/functions via JDBC.
        Esta implementación retorna una lista vacía de forma segura, evitando falsos negativos
        en comparaciones de esquemas.

        **Impacto**: Cuando ``SchemaComparator.compare(..., include_routines=True)`` se invoca
        en HSQLDB, las routines simplemente no se comparan (no se reportan diferencias).
        Para comparar DDL de routines en HSQLDB, considere usar una BD de producción compatible
        (PostgreSQL, Oracle, SQL Server o MariaDB).

        **Performance note**: This method returns immediately (O(1)). No database queries are issued."""
        logger.warning(
            "HSQLDB no soporta extracción de DDL de routines; se omite la comparación. "
            "Consulte SchemaComparator.compare(..., include_routines=True) docs para detalles."
        )
        return []

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
            added: int = sum(1 for t in table_diffs if t.status == "added")
            removed: int = sum(1 for t in table_diffs if t.status == "removed")
            modified: int = sum(1 for t in table_diffs if t.status == "modified")
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
        "oracle": SchemaComparator._get_routines_oracle,
        "mssql": SchemaComparator._get_routines_mssql,
        "postgresql": SchemaComparator._get_routines_postgresql,
        "hsqldb": SchemaComparator._get_routines_hsqldb,
    }
)
