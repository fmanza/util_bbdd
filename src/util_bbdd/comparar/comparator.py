"""Comparador de esquemas de base de datos motor-agnóstico sobre SQLAlchemy Inspector."""

from __future__ import annotations

import logging
import re

from collections import Counter
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from util_bbdd._core.exceptions import MetadataIntrospectionError

from ..metadata.reflection import prefetch_table_metadata, schema_routines, view_definitions
from ._ddl import DdlNormalizer
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

type _RoutineType = Literal["PROCEDURE", "FUNCTION"]

_URL_CREDENTIALS_RE: str = r"://[^@]+@"
_URL_CREDENTIALS_MASK: str = "://***@"

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence

    from sqlalchemy.engine import URL, Inspector
    from sqlalchemy.engine.interfaces import (
        ReflectedColumn,
        ReflectedForeignKeyConstraint,
        ReflectedIndex,
        ReflectedPrimaryKeyConstraint,
    )

    from ..metadata.reflection import MetadataKind


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
    #: Las claves de ``_ROUTINE_FETCHERS`` deben usar los valores de este mapa.
    _DB_TYPE_TO_DIALECT: ClassVar[dict[str, str]] = {
        "mariadb": "mariadb",
        "mysql": "mysql",
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
                **Nota**: Solo efectivo cuando ``include_tables=True``.
            include_routines: Comparar procedures/functions vía catálogo del motor.
                **Nota**: No todos los motores soportan introspección de routines.
                - MariaDB, MySQL, Oracle, SQL Server, PostgreSQL: ✓ Soportado
                - HSQLDB: ✗ No soportado (DDL no portable); ``include_routines=True`` será ignorado con warning.
                - SQLite: N/A (sin routines)

        Returns:
            ``SchemaDiff`` con todas las diferencias encontradas.

        Rendimiento:
            Los metadatos de las tablas comunes (columnas, PK, índices, FKs y comentarios) se leen con
            ``Inspector.get_multi_*``: una consulta por schema y tipo en PostgreSQL y Oracle; en SQL Server PK, índices,
            FKs, comentarios y columnas con consultas por schema (``metadata.reflection``); en
            MariaDB/MySQL tabla a tabla (un ``SHOW CREATE TABLE`` por tabla), pero sin una conexión del pool por llamada.

            Vistas y routines: definiciones con una consulta por lado y tipo de objeto desde el catálogo de
            ``metadata/`` (ADR-003, C4); antes una consulta por vista y lado, y un ``SHOW CREATE`` por routine en
            MariaDB/MySQL. ``include_*=False`` evita las consultas de lo que no se compara.
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
        # Índices normalizados: lower(name) → canonical_name para comparación cross-engine
        source_tables_lower: dict[str, str] = {t.lower(): t for t in source.get_table_names(schema=source_schema)}
        target_tables_lower: dict[str, str] = {t.lower(): t for t in target.get_table_names(schema=target_schema)}

        only_source = source_tables_lower.keys() - target_tables_lower.keys()
        only_target = target_tables_lower.keys() - source_tables_lower.keys()
        common_keys = source_tables_lower.keys() & target_tables_lower.keys()

        diffs: list[TableDiff] = []

        # Tablas solo en source (nombre canónico del origen)
        diffs.extend(TableDiff(table_name=source_tables_lower[k], status="added") for k in sorted(only_source))

        # Tablas solo en target (nombre canónico del destino)
        diffs.extend(TableDiff(table_name=target_tables_lower[k], status="removed") for k in sorted(only_target))

        # Tablas comunes: metadatos precargados por schema (get_multi_*); lo no precargado, tabla a tabla.
        common: list[str] = sorted(common_keys)
        kinds: list[MetadataKind] = ["columns", "pk"]
        if include_indices:
            kinds.append("indexes")
        if include_foreign_keys:
            kinds.append("fks")
        if include_comments:
            kinds.append("comments")
        src_meta = prefetch_table_metadata(source, source_schema, [source_tables_lower[k] for k in common], kinds=kinds)
        tgt_meta = prefetch_table_metadata(target, target_schema, [target_tables_lower[k] for k in common], kinds=kinds)

        for key in common:
            src_table = source_tables_lower[key]
            tgt_table = target_tables_lower[key]

            # Columnas una sola vez, para _compare_columns_from_raw y _compare_comments_from_raw
            source_cols_raw: list[ReflectedColumn] = src_meta.get("columns", src_table)
            target_cols_raw: list[ReflectedColumn] = tgt_meta.get("columns", tgt_table)

            col_diffs = self._compare_columns_from_raw(
                source_cols_raw,
                target_cols_raw,
                src_meta.get("pk", src_table),
                tgt_meta.get("pk", tgt_table),
            )
            idx_diffs: tuple[IndexDiff, ...] = ()
            fk_diffs: tuple[ForeignKeyDiff, ...] = ()
            comment_diffs: tuple[CommentDiff, ...] = ()

            if include_indices:
                idx_diffs = self._compare_indices(
                    src_meta.get("indexes", src_table), tgt_meta.get("indexes", tgt_table), src_table
                )
            if include_foreign_keys:
                fk_diffs = self._compare_foreign_keys(
                    src_meta.get("fks", src_table), tgt_meta.get("fks", tgt_table), src_table
                )
            if include_comments:
                comment_diffs = self._compare_comments_from_raw(
                    source_cols_raw,
                    target_cols_raw,
                    src_table,
                    src_meta.get("comments", src_table),
                    tgt_meta.get("comments", tgt_table),
                )

            if col_diffs or idx_diffs or fk_diffs or comment_diffs:
                diffs.append(
                    TableDiff(
                        table_name=src_table,
                        status="modified",
                        column_diffs=col_diffs,
                        index_diffs=idx_diffs,
                        fk_diffs=fk_diffs,
                        comment_diffs=comment_diffs,
                    ),
                )

        return tuple(diffs)

    # ------------------------------------------------------------------
    # Columnas
    # ------------------------------------------------------------------

    @staticmethod
    def _compare_columns_from_raw(
        source_cols_raw: list[ReflectedColumn],
        target_cols_raw: list[ReflectedColumn],
        source_pk: ReflectedPrimaryKeyConstraint | None,
        target_pk: ReflectedPrimaryKeyConstraint | None,
    ) -> tuple[ColumnDiff, ...]:
        """Compara columnas a partir de listas ya cargadas (evita doble consulta).

        La comparación de existencia es case-insensitive para soportar motores con
        convenciones de case distintas (p.ej. Oracle UPPERCASE vs MariaDB lowercase).
        Los nombres canónicos de cada motor se preservan en los ColumnDiff.
        """
        # Mapas lower→col para comparación case-insensitive entre motores distintos
        source_by_lower: dict[str, ReflectedColumn] = {}
        for col in source_cols_raw:
            key = col["name"].lower()
            if key in source_by_lower:
                logger.warning(
                    "Colisión de case en columnas origen: '%s' y '%s' colisionan al normalizar; se usará '%s'.",
                    source_by_lower[key]["name"],
                    col["name"],
                    source_by_lower[key]["name"],
                )
            else:
                source_by_lower[key] = col

        target_by_lower: dict[str, ReflectedColumn] = {}
        for col in target_cols_raw:
            key = col["name"].lower()
            if key in target_by_lower:
                logger.warning(
                    "Colisión de case en columnas destino: '%s' y '%s' colisionan al normalizar; se usará '%s'.",
                    target_by_lower[key]["name"],
                    col["name"],
                    target_by_lower[key]["name"],
                )
            else:
                target_by_lower[key] = col

        source_pks: list[str] = (source_pk.get("constrained_columns") if source_pk else None) or []
        target_pks: list[str] = (target_pk.get("constrained_columns") if target_pk else None) or []

        diffs: list[ColumnDiff] = []

        # Columnas solo en source — nombre canónico del motor origen
        diffs.extend(
            ColumnDiff(
                column_name=source_by_lower[k]["name"],
                attribute="existence",
                source_value="exists",
                target_value="missing",
            )
            for k in sorted(source_by_lower.keys() - target_by_lower.keys())
        )

        # Columnas solo en target — nombre canónico del motor destino
        diffs.extend(
            ColumnDiff(
                column_name=target_by_lower[k]["name"],
                attribute="existence",
                source_value="missing",
                target_value="exists",
            )
            for k in sorted(target_by_lower.keys() - source_by_lower.keys())
        )

        # Columnas comunes — comparar atributos usando nombres canónicos de cada motor
        for lower_key in sorted(source_by_lower.keys() & target_by_lower.keys()):
            s_col = source_by_lower[lower_key]
            t_col = target_by_lower[lower_key]
            diffs.extend(
                SchemaComparator._diff_common_column(
                    s_col["name"],
                    t_col["name"],
                    s_col,
                    t_col,
                    source_pks,
                    target_pks,
                ),
            )

        return tuple(diffs)

    @staticmethod
    def _diff_common_column(
        col_name: str,
        tgt_col_name: str,
        s_col: ReflectedColumn,
        t_col: ReflectedColumn,
        source_pks: list[str],
        target_pks: list[str],
    ) -> list[ColumnDiff]:
        """Devuelve los ColumnDiff para una columna presente en ambos esquemas.

        ``col_name`` es el nombre canónico en el motor origen (usado en todos los ColumnDiff).
        ``tgt_col_name`` es el nombre canónico en el motor destino (usado solo para el check de PK,
        que puede tener distinto case entre motores).
        """
        diffs: list[ColumnDiff] = []

        s_type = str(s_col.get("type", ""))
        t_type = str(t_col.get("type", ""))
        if s_type != t_type:
            diffs.append(ColumnDiff(column_name=col_name, attribute="type", source_value=s_type, target_value=t_type))

        s_nullable = str(s_col.get("nullable", True))
        t_nullable = str(t_col.get("nullable", True))
        if s_nullable != t_nullable:
            diffs.append(
                ColumnDiff(
                    column_name=col_name,
                    attribute="nullable",
                    source_value=s_nullable,
                    target_value=t_nullable,
                ),
            )

        # PK check case-insensitive: Oracle devuelve PKs en UPPER, MariaDB en lower
        source_pks_lower = {pk.lower() for pk in source_pks}
        target_pks_lower = {pk.lower() for pk in target_pks}
        s_pk = str(col_name.lower() in source_pks_lower)
        t_pk = str(tgt_col_name.lower() in target_pks_lower)
        if s_pk != t_pk:
            diffs.append(
                ColumnDiff(column_name=col_name, attribute="primary_key", source_value=s_pk, target_value=t_pk),
            )

        s_default_raw = s_col.get("default")
        t_default_raw = t_col.get("default")
        s_default = "" if s_default_raw is None else str(s_default_raw)
        t_default = "" if t_default_raw is None else str(t_default_raw)
        if s_default != t_default:
            diffs.append(
                ColumnDiff(column_name=col_name, attribute="default", source_value=s_default, target_value=t_default),
            )

        return diffs

    # ------------------------------------------------------------------
    # Índices
    # ------------------------------------------------------------------

    def _compare_indices(
        self,
        source_idx: Iterable[ReflectedIndex],
        target_idx: Iterable[ReflectedIndex],
        src_table: str,
    ) -> tuple[IndexDiff, ...]:
        # Comparación case-insensitive del nombre del índice (igual que tablas/columnas)
        # para soportar motores con convenciones de case distintas.
        source_map: dict[str, ReflectedIndex] = self._case_insensitive_key_map(
            (idx for idx in source_idx if idx.get("name")), self._index_name, kind="índices origen"
        )
        target_map: dict[str, ReflectedIndex] = self._case_insensitive_key_map(
            (idx for idx in target_idx if idx.get("name")), self._index_name, kind="índices destino"
        )

        # Índices con nombre generado (UQ__…, SYS_C… de un UNIQUE sin nombre): emparejados por estructura.
        only_source: list[str] = sorted(source_map.keys() - target_map.keys())
        only_target: list[str] = sorted(target_map.keys() - source_map.keys())
        by_structure: dict[str, str] = self._match_by_structure(
            source_map,
            target_map,
            only_source,
            only_target,
            patterns=self._GENERATED_INDEX_NAME_PATTERNS,
            structure=self._index_structure,
        )
        matched_target: set[str] = set(by_structure.values())

        diffs: list[IndexDiff] = []

        for key in only_source:
            if key in by_structure:
                continue
            source_index_dict = source_map[key]
            diffs.append(
                IndexDiff(
                    index_name=self._index_name(source_index_dict),
                    table_name=src_table,
                    status="added",
                    source_columns=self._join_columns(source_index_dict.get("column_names")),
                    source_unique=bool(source_index_dict.get("unique", False)),
                ),
            )

        for key in only_target:
            if key in matched_target:
                continue
            target_index_dict = target_map[key]
            diffs.append(
                IndexDiff(
                    index_name=self._index_name(target_index_dict),
                    table_name=src_table,
                    status="removed",
                    target_columns=self._join_columns(target_index_dict.get("column_names")),
                    target_unique=bool(target_index_dict.get("unique", False)),
                ),
            )

        for key in sorted(source_map.keys() & target_map.keys()):
            s_idx: ReflectedIndex = source_map[key]
            t_idx: ReflectedIndex = target_map[key]
            s_cols: str = self._join_columns(s_idx.get("column_names"))
            t_cols: str = self._join_columns(t_idx.get("column_names"))
            s_unique = bool(s_idx.get("unique", False))
            t_unique = bool(t_idx.get("unique", False))
            # Columnas case-insensitive (Oracle "ID" frente a PostgreSQL "id"); el diff conserva los nombres reales.
            if s_cols.lower() != t_cols.lower() or s_unique != t_unique:
                diffs.append(
                    IndexDiff(
                        index_name=self._index_name(s_idx),
                        table_name=src_table,
                        status="modified",
                        source_columns=s_cols,
                        target_columns=t_cols,
                        source_unique=s_unique,
                        target_unique=t_unique,
                    ),
                )

        return tuple(diffs)

    # ------------------------------------------------------------------
    # Foreign Keys
    # ------------------------------------------------------------------

    def _compare_foreign_keys(
        self,
        source_fks: Iterable[ReflectedForeignKeyConstraint],
        target_fks: Iterable[ReflectedForeignKeyConstraint],
        src_table: str,
    ) -> tuple[ForeignKeyDiff, ...]:
        # Comparación case-insensitive del nombre/clave de la FK (igual que tablas/columnas)
        # para soportar motores con convenciones de case distintas.
        source_map: dict[str, ReflectedForeignKeyConstraint] = self._case_insensitive_key_map(
            source_fks, SchemaComparator._fk_key, kind="foreign keys origen"
        )
        target_map: dict[str, ReflectedForeignKeyConstraint] = self._case_insensitive_key_map(
            target_fks, SchemaComparator._fk_key, kind="foreign keys destino"
        )

        # FKs con nombre generado por el motor (SYS_C…, FK__…__XXXXXXXX) cambian de nombre entre schemas: las que
        # no casan por nombre se emparejan por estructura (y, al ser igual, no hay diferencia).
        only_source: list[str] = sorted(source_map.keys() - target_map.keys())
        only_target: list[str] = sorted(target_map.keys() - source_map.keys())
        by_structure: dict[str, str] = self._match_by_structure(
            source_map,
            target_map,
            only_source,
            only_target,
            patterns=self._GENERATED_FK_NAME_PATTERNS,
            structure=self._fk_structure,
        )
        matched_target: set[str] = set(by_structure.values())

        diffs: list[ForeignKeyDiff] = []

        for key in only_source:
            if key in by_structure:
                continue
            fk = source_map[key]
            diffs.append(
                ForeignKeyDiff(
                    fk_name=SchemaComparator._fk_key(fk),
                    table_name=src_table,
                    status="added",
                    source_columns=self._join_columns(fk.get("constrained_columns")),
                    source_referred_table=fk.get("referred_table") or "",
                    source_referred_columns=self._join_columns(fk.get("referred_columns")),
                ),
            )

        for key in only_target:
            if key in matched_target:
                continue
            fk = target_map[key]
            diffs.append(
                ForeignKeyDiff(
                    fk_name=SchemaComparator._fk_key(fk),
                    table_name=src_table,
                    status="removed",
                    target_columns=self._join_columns(fk.get("constrained_columns")),
                    target_referred_table=fk.get("referred_table") or "",
                    target_referred_columns=self._join_columns(fk.get("referred_columns")),
                ),
            )

        for key in sorted(source_map.keys() & target_map.keys()):
            s_fk = source_map[key]
            t_fk = target_map[key]
            s_cols: str = self._join_columns(s_fk.get("constrained_columns"))
            t_cols: str = self._join_columns(t_fk.get("constrained_columns"))
            s_ref = s_fk.get("referred_table") or ""
            t_ref = t_fk.get("referred_table") or ""
            s_ref_cols: str = self._join_columns(s_fk.get("referred_columns"))
            t_ref_cols: str = self._join_columns(t_fk.get("referred_columns"))

            # Case-insensitive como el resto de nombres; el diff conserva los nombres reales de cada motor.
            if (s_cols.lower(), s_ref.lower(), s_ref_cols.lower()) != (
                t_cols.lower(),
                t_ref.lower(),
                t_ref_cols.lower(),
            ):
                diffs.append(
                    ForeignKeyDiff(
                        fk_name=SchemaComparator._fk_key(s_fk),
                        table_name=src_table,
                        status="modified",
                        source_columns=s_cols,
                        target_columns=t_cols,
                        source_referred_table=s_ref,
                        target_referred_table=t_ref,
                        source_referred_columns=s_ref_cols,
                        target_referred_columns=t_ref_cols,
                    ),
                )

        return tuple(diffs)

    # ------------------------------------------------------------------
    # Comentarios
    # ------------------------------------------------------------------

    @staticmethod
    def _compare_comments_from_raw(
        source_cols_raw: list[ReflectedColumn],
        target_cols_raw: list[ReflectedColumn],
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
                ),
            )

        # Mapas lower→col para comparación case-insensitive entre motores distintos.
        # El nombre canónico en ColumnDiff usa source si existe, target en caso contrario.
        source_cols_lower: dict[str, ReflectedColumn] = {col["name"].lower(): col for col in source_cols_raw}
        target_cols_lower: dict[str, ReflectedColumn] = {col["name"].lower(): col for col in target_cols_raw}
        for lower_key in sorted(source_cols_lower.keys() | target_cols_lower.keys()):
            s_col: ReflectedColumn | None = source_cols_lower.get(lower_key)
            t_col: ReflectedColumn | None = target_cols_lower.get(lower_key)
            s_col_comment = str((s_col.get("comment") if s_col else None) or "")
            t_col_comment = str((t_col.get("comment") if t_col else None) or "")
            if s_col_comment != t_col_comment:
                canonical = (s_col or target_cols_lower[lower_key])["name"]
                diffs.append(
                    CommentDiff(
                        object_name=table,
                        column_name=canonical,
                        source_comment=s_col_comment,
                        target_comment=t_col_comment,
                    ),
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
        # Case-insensitive como las tablas (Oracle "V_EMP" frente a PostgreSQL "v_emp"); cada lado consulta su
        # definición con su nombre real.
        source_views: dict[str, str] = self._case_insensitive_key_map(
            source.get_view_names(schema=source_schema), str, kind="vistas origen"
        )
        target_views: dict[str, str] = self._case_insensitive_key_map(
            target.get_view_names(schema=target_schema), str, kind="vistas destino"
        )

        # Definiciones con una consulta por lado (ADR-003, C4); antes una por vista y lado
        source_defs = view_definitions(source, source_schema, list(source_views.values()))
        target_defs = view_definitions(target, target_schema, list(target_views.values()))
        diffs: list[ViewDiff] = []

        for key in sorted(source_views.keys() - target_views.keys()):
            view_name = source_views[key]
            diffs.append(ViewDiff(view_name=view_name, status="added", source_definition=source_defs[view_name]))

        for key in sorted(target_views.keys() - source_views.keys()):
            view_name = target_views[key]
            diffs.append(ViewDiff(view_name=view_name, status="removed", target_definition=target_defs[view_name]))

        for key in sorted(source_views.keys() & target_views.keys()):
            view_name = source_views[key]
            source_def_cmp: str = source_defs[view_name]
            target_def_cmp: str = target_defs[target_views[key]]
            s_norm: str = self._normalize_ddl(self._unqualify(source_def_cmp, source_schema))
            t_norm: str = self._normalize_ddl(self._unqualify(target_def_cmp, target_schema))
            if s_norm != t_norm:
                diffs.append(
                    ViewDiff(
                        view_name=view_name,
                        status="modified",
                        source_definition=source_def_cmp,
                        target_definition=target_def_cmp,
                    ),
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
        """Compara procedures/functions si el dialect tiene fetcher registrado en ``_ROUTINE_FETCHERS``.

        Si ningún lado tiene fetcher, devuelve tupla vacía. Si un fetcher no puede listar las routines
        (``MetadataIntrospectionError``), también: una lista vacía o parcial daría falsos "added"/"removed".
        El emparejamiento es case-insensitive y usa ``signature`` (sobrecargas PostgreSQL) solo si todas las routines
        de ambos lados la traen: entre motores distintos (PostgreSQL frente a MariaDB) se empareja por nombre.
        """
        try:
            source_routines: list[dict[str, str]] | None = self._get_routines_safe(source, source_schema)
            target_routines: list[dict[str, str]] | None = self._get_routines_safe(target, target_schema)
        except MetadataIntrospectionError as exc:
            self.logger.warning("Se omite la comparación de routines: %s", exc)
            return ()

        if source_routines is None and target_routines is None:
            self.logger.debug("El dialect no soporta listado de routines; se omite la comparación.")
            return ()

        by_signature: bool = all("signature" in r for r in [*(source_routines or []), *(target_routines or [])])

        def key_fn(routine: Mapping[str, str]) -> str:
            return self._routine_key(routine, by_signature=by_signature)

        source_map: dict[str, dict[str, str]] = self._case_insensitive_key_map(
            source_routines or [], key_fn, kind="routines origen"
        )
        target_map: dict[str, dict[str, str]] = self._case_insensitive_key_map(
            target_routines or [], key_fn, kind="routines destino"
        )

        diffs: list[RoutineDiff] = []

        for key in sorted(set(source_map) - set(target_map)):
            source_routine = source_map[key]
            diffs.append(
                RoutineDiff(
                    routine_name=source_routine["name"],
                    routine_type=cast(_RoutineType, source_routine.get("type", "PROCEDURE")),
                    status="added",
                    source_definition=source_routine.get("definition", ""),
                ),
            )

        for key in sorted(set(target_map) - set(source_map)):
            target_routine: dict[str, str] = target_map[key]
            diffs.append(
                RoutineDiff(
                    routine_name=target_routine["name"],
                    routine_type=cast(_RoutineType, target_routine.get("type", "PROCEDURE")),
                    status="removed",
                    target_definition=target_routine.get("definition", ""),
                ),
            )

        for key in sorted(set(source_map) & set(target_map)):
            s_r: dict[str, str] = source_map[key]
            t_r: dict[str, str] = target_map[key]
            s_norm: str = self._normalize_ddl(self._unqualify(s_r.get("definition", ""), source_schema))
            t_norm: str = self._normalize_ddl(self._unqualify(t_r.get("definition", ""), target_schema))
            if s_norm != t_norm:
                diffs.append(
                    RoutineDiff(
                        routine_name=s_r["name"],
                        routine_type=cast(_RoutineType, s_r.get("type", "PROCEDURE")),
                        status="modified",
                        source_definition=s_r.get("definition", ""),
                        target_definition=t_r.get("definition", ""),
                    ),
                )

        return tuple(diffs)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_url_safe(inspector: Inspector) -> URL | None:
        """Parsea la URL del engine asociado al inspector; devuelve None si no es posible."""
        engine: Any | None = getattr(inspector, "engine", None)
        url_raw: Any = getattr(engine, "url", None)
        if url_raw is None:
            return None
        try:
            return make_url(str(url_raw))
        except (ArgumentError, ValueError):
            return None

    @staticmethod
    def _mask_url(s: str) -> str:
        """Enmascara credenciales de una URL ya convertida a string."""
        return re.sub(_URL_CREDENTIALS_RE, _URL_CREDENTIALS_MASK, s)

    @staticmethod
    def _build_label(inspector: Inspector, schema: str | None) -> str:
        """Construye una etiqueta legible para el inspector."""
        url_obj = SchemaComparator._parse_url_safe(inspector)
        if url_obj is not None:
            try:
                safe_str: str = url_obj.render_as_string(hide_password=True)
            except (AttributeError, ValueError):
                safe_str = str(url_obj)
            url: str = SchemaComparator._mask_url(safe_str)
        else:
            engine: Any | None = getattr(inspector, "engine", None)
            url_raw: Any = getattr(engine, "url", None)
            url = SchemaComparator._mask_url(str(url_raw) if url_raw is not None else "unknown")
        if schema:
            return f"{url} [{schema}]"
        return url

    #: Nombres de FK que genera el motor cuando la FK no se nombra; cambian entre schemas con la misma FK.
    #: Ampliable: ``SchemaComparator._GENERATED_FK_NAME_PATTERNS += (re.compile(...),)``.
    _GENERATED_FK_NAME_PATTERNS: ClassVar[tuple[re.Pattern[str], ...]] = (
        re.compile(r"^SYS_C\d+$", re.IGNORECASE),  # Oracle
        re.compile(r"^FK__.+__[0-9A-F]{8}$", re.IGNORECASE),  # SQL Server: FK__<tabla>__<col>__<hex>
        re.compile(r"_fkey\d*$", re.IGNORECASE),  # PostgreSQL: <tabla>_<cols>_fkey[N]
        re.compile(r"_ibfk_\d+$", re.IGNORECASE),  # MySQL/MariaDB: <tabla>_ibfk_<N>
    )

    #: Nombres de índice que genera el motor (sobre todo para un ``UNIQUE`` sin nombre); verificados en el banco.
    #: MySQL/MariaDB no figuran: nombran el índice como su primera columna (``a``, ``a_2``), indistinguible de un
    #: nombre puesto a mano y estable entre schemas.
    _GENERATED_INDEX_NAME_PATTERNS: ClassVar[tuple[re.Pattern[str], ...]] = (
        re.compile(r"^SYS_C\d+$", re.IGNORECASE),  # Oracle
        re.compile(r"^UQ__.+__[0-9A-F]{16}$", re.IGNORECASE),  # SQL Server: UQ__<tabla>__<hex16>
        re.compile(r"_(key|idx)\d*$", re.IGNORECASE),  # PostgreSQL: <tabla>_<cols>_key / _idx [N]
    )

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
        url_obj = SchemaComparator._parse_url_safe(inspector)
        if url_obj is None:
            return schema or "db"

        dialect = (url_obj.drivername or "").split("+")[0].lower()
        dialect_short = SchemaComparator._DIALECT_ABBREV.get(dialect, dialect[:6] if dialect else "db")
        host = url_obj.host or ""
        # IP → último octeto (parte más específica); nombre DNS → tal cual
        host_short = host.rsplit(".", 1)[-1] if re.match(r"^\d+(\.\d+){3}$", host) else host
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
    def _unqualify(definition: str, schema: str | None) -> str:
        """Quita el prefijo del propio schema (``s.``, ``"s".``, ``[s].``, `` `s`. ``) para comparar definiciones.

        ``pg_get_functiondef``, ``OBJECT_DEFINITION`` y otros guardan el nombre calificado del objeto: sin esto, la misma
        vista o routine en dos schemas distintos salía como modificada (H-30). Solo para comparar; el informe muestra
        la definición tal cual.
        """
        if not schema or not definition:
            return definition
        name = re.escape(schema)
        pattern = rf'(?:"{name}"|\[{name}\]|`{name}`|(?<![\w$#"\]`]){name})\s*\.\s*(?=["\[`\w])'
        return re.sub(pattern, "", definition, flags=re.IGNORECASE)

    @staticmethod
    def _normalize_ddl(definition: str) -> str:
        """Normalización universal de DDL delegada a ``DdlNormalizer.normalize_for_comparison``.

        Para añadir patrones de normalización::

            DdlNormalizer._VIEW_STRIP_PATTERNS.append((r"MY_PATTERN", ""))
            # o bien para patrones de comparación cross-motor:
            DdlNormalizer._COMPARISON_EXTRA_PATTERNS.append((r"MY_PATTERN", ""))
        """
        return DdlNormalizer.normalize_for_comparison(definition)

    @classmethod
    def _match_by_structure[T: (ReflectedForeignKeyConstraint, ReflectedIndex)](
        cls,
        source_map: Mapping[str, T],
        target_map: Mapping[str, T],
        only_source: list[str],
        only_target: list[str],
        *,
        patterns: tuple[re.Pattern[str], ...],
        structure: Callable[[T], tuple[str | bool, ...]],
    ) -> dict[str, str]:
        """Empareja por estructura las FKs o índices sin pareja por nombre cuyo nombre generó el motor en ambos lados.

        Los nombres que genera el motor cuando no se da uno (Oracle ``SYS_C…``, SQL Server ``FK__…``/``UQ__…``)
        cambian entre schemas con el mismo objeto. Solo se emparejan si los dos nombres son generados (o no hay
        nombre): un nombre puesto por el usuario que cambia es una diferencia real. Uno a uno, en el orden de las
        claves.

        Returns:
            Clave del objeto origen → clave del objeto destino emparejado.
        """
        free_target: list[str] = [k for k in only_target if cls._is_generated_name(target_map[k].get("name"), patterns)]
        matches: dict[str, str] = {}
        for s_key in only_source:
            s_obj = source_map[s_key]
            if not cls._is_generated_name(s_obj.get("name"), patterns):
                continue
            wanted = structure(s_obj)
            t_key = next((k for k in free_target if structure(target_map[k]) == wanted), None)
            if t_key is not None:
                matches[s_key] = t_key
                free_target.remove(t_key)
        return matches

    @staticmethod
    def _is_generated_name(name: str | None, patterns: tuple[re.Pattern[str], ...]) -> bool:
        """Si el nombre de una FK o índice lo generó el motor (o no tiene nombre)."""
        return not name or any(pattern.search(name) for pattern in patterns)

    @classmethod
    def _index_structure(cls, index: ReflectedIndex) -> tuple[str, bool]:
        """Columnas (en minúsculas) y unicidad de un índice."""
        return cls._join_columns(index.get("column_names")).lower(), bool(index.get("unique", False))

    @classmethod
    def _fk_structure(cls, fk: ReflectedForeignKeyConstraint) -> tuple[str, str, str]:
        """Columnas, tabla referenciada y columnas referenciadas de una FK, en minúsculas."""
        return (
            cls._join_columns(fk.get("constrained_columns")).lower(),
            (fk.get("referred_table") or "").lower(),
            cls._join_columns(fk.get("referred_columns")).lower(),
        )

    @staticmethod
    def _fk_key(fk: ReflectedForeignKeyConstraint) -> str:
        """Genera una clave única para una FK, incluyendo FKs anónimas (name=None).

        Para FKs con nombre usa el nombre como clave.
        Para FKs anónimas (comunes en SQLite) genera una clave sintética basada en
        columnas restringidas, tabla referenciada y columnas referenciadas.
        """
        name = fk.get("name")
        if name:
            return str(name)
        cols = ",".join(fk.get("constrained_columns") or [])
        ref_table = fk.get("referred_table") or ""
        ref_cols = ",".join(fk.get("referred_columns") or [])
        return f"__anon__{cols}__{ref_table}__{ref_cols}"

    @staticmethod
    def _index_name(index: ReflectedIndex) -> str:
        """Nombre de un índice con nombre (los anónimos se filtran antes de llamar)."""
        return index["name"] or ""

    @staticmethod
    def _routine_key(routine: Mapping[str, str], *, by_signature: bool) -> str:
        """Clave de emparejamiento de una routine: firma (si ``by_signature``) o nombre, y tipo."""
        ident: str = routine["signature"] if by_signature else routine["name"]
        return f"{ident}\x00{routine.get('type', 'PROCEDURE')}"

    @staticmethod
    def _case_insensitive_key_map[T](
        items: Iterable[T],
        key_fn: Callable[[T], str],
        *,
        kind: str,
    ) -> dict[str, T]:
        """Agrupa items en un dict indexado por ``key_fn(item).lower()``.

        Soporta motores con convenciones de case distintas (p.ej. índices/FKs
        UPPERCASE en Oracle vs lowercase en PostgreSQL) evitando falsos
        positivos "added+removed" por diferencia de case únicamente. El nombre
        canónico de cada item se recupera llamando de nuevo a ``key_fn`` sobre
        el item almacenado. Advierte (no falla) si dos items colisionan al
        normalizar el case.
        """
        result: dict[str, T] = {}
        for item in items:
            raw_key = key_fn(item)
            lowered_key = raw_key.lower()
            if lowered_key in result:
                logger.warning(
                    "Colisión de case en %s: '%s' y '%s' colisionan al normalizar; se usará '%s'.",
                    kind,
                    key_fn(result[lowered_key]),
                    raw_key,
                    key_fn(result[lowered_key]),
                )
            else:
                result[lowered_key] = item
        return result

    @staticmethod
    def _join_columns(column_names: Sequence[str | None] | None) -> str:
        """Une nombres de columnas filtrando Nones (columnas de índices por expresión)."""
        if not column_names:
            return ""
        return ",".join(c for c in column_names if c is not None)

    @staticmethod
    def _get_routines_safe(inspector: Inspector, schema: str | None) -> list[dict[str, str]] | None:
        """Routines del schema como ``{"name", "type", "definition"[, "signature"]}``; ``None`` si no hay catálogo.

        Se leen del catálogo de ``metadata/`` con una consulta por schema (``Kind.ROUTINES``, ADR-003 C4). Un fetcher
        registrado en ``_ROUTINE_FETCHERS`` para el **dialect SQLAlchemy** (``"mssql"`` para SQL Server; ver
        ``_DB_TYPE_TO_DIALECT``) tiene prioridad, para motores sin ``CatalogDialect`` o lecturas propias::

            SchemaComparator._ROUTINE_FETCHERS["midialecto"] = mi_fetcher  # (inspector, schema) -> list[dict]

        En PostgreSQL cada routine lleva ``signature`` = ``nombre(argumentos)``, que el comparador usa para emparejar
        sobrecargas aunque solo un lado las tenga; ``name`` incluye los argumentos solo si hay sobrecargas en ese lado.
        """
        # inspector.engine es canónico en SA 2.x (el proyecto exige sqlalchemy>=2.0)
        engine: Any | None = getattr(inspector, "engine", None)
        dialect_name: str = str(getattr(getattr(engine, "dialect", None), "name", ""))
        fetcher: Callable[[Inspector, str | None], list[dict[str, str]]] | None = (
            SchemaComparator._ROUTINE_FETCHERS.get(dialect_name)
        )
        if fetcher is not None:
            return fetcher(inspector, schema)
        routines = schema_routines(inspector, schema)
        if routines is None:
            return None
        if dialect_name != "postgresql":
            return [{"name": r.name, "type": r.routine_type, "definition": r.definition or ""} for r in routines]
        overloads = Counter(r.name for r in routines)
        result: list[dict[str, str]] = []
        for r in routines:
            signature = f"{r.name}({r.signature})"
            result.append(
                {
                    "name": signature if overloads[r.name] > 1 else r.name,
                    "type": r.routine_type,
                    "definition": r.definition or "",
                    "signature": signature,
                }
            )
        return result

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
