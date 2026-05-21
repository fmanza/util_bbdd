"""Comparador de esquemas de base de datos motor-agnóstico sobre SQLAlchemy Inspector."""

from __future__ import annotations

import logging
import re

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

from sqlalchemy.engine import make_url
from sqlalchemy.engine.interfaces import ReflectedTableComment

from ._routine_fetchers import RoutineFetcherRegistry
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
from .reporters._base import DdlNormalizer

logger: logging.Logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sqlalchemy.engine import Inspector


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
    # Inicialización
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        """Inicializa SchemaComparator con logger."""
        self.logger: logging.Logger = logging.getLogger(__name__)

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
        source_short_label: str = self._build_short_label(source, source_schema)
        target_short_label: str = self._build_short_label(target, target_schema)
        self.logger.info("Iniciando comparación: %s ↔ %s", source_label, target_label)

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
        self.logger.info("Comparación finalizada: %s", summary)

        return SchemaDiff(
            source_label=source_label,
            target_label=target_label,
            table_diffs=table_diffs,
            view_diffs=view_diffs,
            routine_diffs=routine_diffs,
            summary=summary,
            source_short_label=source_short_label,
            target_short_label=target_short_label,
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
            self.logger.debug("El dialect no soporta listado de routines; se omite la comparación.")
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
        engine: Any | None = getattr(inspector, "engine", None)
        url_str = str(getattr(engine, "url", "unknown"))
        # Ocultar credenciales si las hay
        url: str = re.sub(r"://[^@]+@", "://***@", url_str)
        if schema:
            return f"{url} [{schema}]"
        return url

    #: Abreviaturas de dialect SQLAlchemy para nombres de fichero de reporte.
    _DIALECT_ABBREV: ClassVar[dict[str, str]] = {
        "postgresql": "pg",
        "mariadb": "maria",
        "mysql": "mysql",
        "oracle": "ora",
        "mssql": "mssql",
        "sqlite": "sqlite",
        "hsqldb": "hsqldb",
    }

    @staticmethod
    def _build_short_label(inspector: Inspector, schema: str | None) -> str:
        """Construye una etiqueta compacta para el nombre de fichero de reporte.

        Selecciona el identificador más relevante según el motor:

        - Oracle: usuario (el usuario es el schema en Oracle)
        - PostgreSQL: schema si se proporciona, si no la base de datos
        - MariaDB / MySQL: nombre de la base de datos
        - SQLite: nombre del fichero sin ruta ni extensión
        - SQL Server (mssql): base de datos, añade schema si se proporciona
        - Resto: schema o base de datos o usuario, en ese orden
        """
        engine: Any | None = getattr(inspector, "engine", None)
        url_raw: Any | None = getattr(engine, "url", None)
        if url_raw is None:
            return schema or "db"

        try:
            url_obj = make_url(str(url_raw))
        except Exception:
            return schema or "db"

        dialect = (url_obj.drivername or "").split("+")[0].lower()
        dialect_short = SchemaComparator._DIALECT_ABBREV.get(dialect, dialect[:6] if dialect else "db")
        host_short = (url_obj.host or "").split(".")[0]
        database = url_obj.database or ""
        username = url_obj.username or ""

        # SQLite database es una ruta de fichero; extraer solo el nombre sin extensión
        if dialect == "sqlite":
            last = database.replace("\\", "/").rsplit("/", 1)[-1]
            db_short = last.rsplit(".", 1)[0].strip(":") if last else "mem"
        else:
            db_short = database.split("/")[-1].split("?")[0]

        identifier = SchemaComparator._pick_identifier(dialect, username, db_short, schema)
        parts = [p for p in [dialect_short, host_short, identifier] if p]
        return "_".join(parts) or schema or "db"

    @staticmethod
    def _pick_identifier(dialect: str, username: str, db_short: str, schema: str | None) -> str:
        """Devuelve el identificador más relevante para el fichero de reporte según el motor."""
        if dialect == "oracle":
            return username or schema or db_short
        if dialect == "postgresql":
            return schema or db_short
        if dialect in ("mariadb", "mysql"):
            return db_short
        if dialect == "sqlite":
            return db_short or "mem"
        if dialect == "mssql":
            return f"{db_short}_{schema}" if db_short and schema else db_short or schema or ""
        return schema or db_short or username

    @staticmethod
    def _normalize_ddl(definition: str) -> str:
        """Normalización universal de DDL delegada a ``DdlNormalizer.normalize_for_comparison``.

        Para añadir patrones de normalización::

            DdlNormalizer._VIEW_STRIP_PATTERNS.append((r"MY_PATTERN", ""))
            # o bien para patrones de comparación cross-motor:
            DdlNormalizer._COMPARISON_EXTRA_PATTERNS.append((r"MY_PATTERN", ""))
        """
        return DdlNormalizer.normalize_for_comparison(definition)

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
        engine: Any | None = getattr(inspector, "engine", None)
        dialect_name: str = getattr(getattr(engine, "dialect", None), "name", "")

        fetcher: Callable[[Inspector, str | None], list[dict[str, str]]] | None = (
            SchemaComparator._ROUTINE_FETCHERS.get(dialect_name)
        )
        return fetcher(inspector, schema) if fetcher is not None else None

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
# Registro de fetchers de routines por defecto (OCP — extensible sin editar la clase).
# La asignación directa evita mutar el dict vacío; mantiene la semántica de
# "fuente de verdad inicial" y permite sobrescritura posterior por motor externo.
# ---------------------------------------------------------------------------
SchemaComparator._ROUTINE_FETCHERS = {
    "mariadb": RoutineFetcherRegistry.get_routines_mariadb,
    "oracle": RoutineFetcherRegistry.get_routines_oracle,
    "mssql": RoutineFetcherRegistry.get_routines_mssql,
    "postgresql": RoutineFetcherRegistry.get_routines_postgresql,
    "hsqldb": RoutineFetcherRegistry.get_routines_hsqldb,
}
