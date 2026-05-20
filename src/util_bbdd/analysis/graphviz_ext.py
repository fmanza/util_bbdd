"""Renderer Graphviz sobre el nuevo modelo multinivel de relaciones."""

from __future__ import annotations

import html
import logging

from logging import Logger
from pathlib import Path
from typing import Any

from util_bbdd.analysis.base import GraphEdge

try:
    import graphviz

    GRAPHVIZ_AVAILABLE = True
except ImportError:
    graphviz = None
    GRAPHVIZ_AVAILABLE = False

from .._core.exceptions import DatabaseException
from ..managers import SyncDatabaseManager
from .base import (
    CardinalityEndMarker,
    ColumnVisualizationMode,
    DatabaseRelationshipGraphBase,
    GraphDocument,
    LevelDirection,
    TableRelation,
    TableVisualType,
)

GRAPHVIZ_MISSING_MSG: str = "Graphviz no disponible. Instale: pip install graphviz"


class GraphvizRelationshipGraphExt(DatabaseRelationshipGraphBase):
    """
    Generador extendido de grafos Graphviz con:
    - Nodos que muestran columnas y tipos de datos
    - Cardinalidad en relaciones
    - Colores diferenciados para tabla principal vs relacionadas
    """

    # Colores pastel
    ENTITY_TABLE_COLOR: str = "#CFE8FF"  # Azul pastel para tablas entidad
    ASSOCIATION_TABLE_COLOR: str = "#D8F3DC"  # Verde pastel para tablas de asociación
    HIERARCHY_TABLE_COLOR: str = "#FFE5C2"  # Naranja pastel para tablas jerárquicas
    TEXT_COLOR: str = "#000000"  # Negro para texto
    DEFAULT_TABLE_WIDTH: str = "180"
    DEFAULT_NAME_COLUMN_WIDTH: str = "120"
    DEFAULT_TYPE_COLUMN_WIDTH: str = "60"
    DEFAULT_TITLE_MAX_CHARS: int = 21
    DEFAULT_COLUMN_MAX_CHARS: int = 18
    DEFAULT_TYPE_MAX_CHARS: int = 13
    CARDINALITY_LABEL_DISTANCE: str = "2.2"
    CARDINALITY_LABEL_ANGLE: str = "28"

    def __init__(
        self,
        db_manager: SyncDatabaseManager,
        show_columns: bool | None = None,
        column_mode: ColumnVisualizationMode | str = ColumnVisualizationMode.RELATIONS,
        max_columns: int = 8,
        show_data_types: bool = False,
        max_depth: int = 1,
        direction: LevelDirection | str = LevelDirection.BOTH,
        show_constraint_name: bool = False,
        orthogonal_edges: bool = True,
        orthogonal_nodesep: float = 0.75,
        orthogonal_ranksep: float = 0.9,
        render_dpi: int = 300,
    ):
        super().__init__(db_manager)
        self.logger: Logger = logging.getLogger(__name__)

        if not GRAPHVIZ_AVAILABLE or graphviz is None:
            raise ImportError(GRAPHVIZ_MISSING_MSG)

        # Configuración de columnas
        self.include_columns: bool = True if show_columns is None else bool(show_columns)
        self.column_mode: ColumnVisualizationMode = self._normalize_column_mode(column_mode)
        self.max_columns: int = max(1, int(max_columns))
        self.show_data_types: bool = bool(show_data_types)
        self.max_depth: int = max(1, int(max_depth))
        self.direction: LevelDirection = self._normalize_direction(direction)
        self.show_constraint_name: bool = bool(show_constraint_name)
        # Configuración de estilo de líneas de relación (ángulo recto)
        self.orthogonal_edges: bool = orthogonal_edges
        # Espaciado de layout para líneas ortogonales
        self.orthogonal_nodesep: float = orthogonal_nodesep
        self.orthogonal_ranksep: float = orthogonal_ranksep
        self.render_dpi: int = render_dpi

        # Cache para columnas de tablas (evitar múltiples consultas)
        self._columns_cache: dict[str, list[tuple[str, str]]] = {}

        # Usar cachés centralizadas desde SyncDatabaseManager para relaciones
        # No necesitamos cachés locales para PKs, UKs ni cardinalidades

    def _normalize_column_mode(self, mode: ColumnVisualizationMode | str) -> ColumnVisualizationMode:
        """Normaliza el modo de visualización de columnas."""
        if isinstance(mode, ColumnVisualizationMode):
            return mode

        try:
            return ColumnVisualizationMode(str(mode).strip().lower())
        except ValueError as exc:
            raise ValueError(f"Modo de columnas no soportado: {mode}") from exc

    def _get_table_columns_with_types(self, table_name: str) -> list[tuple[str, str]]:
        """
        Obtiene las columnas de una tabla con sus tipos de datos (cacheado)

        Args:
            table_name: Nombre de la tabla

        Returns:
            Lista de tuplas (nombre_columna, tipo_dato)
        """
        if table_name in self._columns_cache:
            return self._columns_cache[table_name]

        try:
            columns = self.db_manager.get_columns(table_name)
            self.logger.debug(f"Obtenidas {len(columns)} columnas para tabla {table_name}")
            # Asumiendo que get_columns devuelve lista de tuplas (nombre, tipo, ...)
            # Normalizamos a (nombre, tipo)
            result = []
            for col in columns:
                if isinstance(col, (tuple, list)):
                    col_name = str(col[0])
                    col_type: str = str(col[1]) if len(col) > 1 else "VARCHAR"
                    result.append((col_name, col_type))
                else:
                    result.append((str(col), "VARCHAR"))

            self._columns_cache[table_name] = result
            return result
        except DatabaseException as e:
            self.logger.warning(f"Error obteniendo columnas de {table_name}: {e}")
            return []

    def _get_primary_keys(self, table_name: str) -> list[str]:
        """
        Obtiene las claves primarias de una tabla (cacheado centralizado)

        Args:
            table_name: Nombre de la tabla

        Returns:
            Lista de nombres de columnas que son claves primarias
        """
        # Construir clave de tabla con contexto
        context: str = self.db_manager.get_query_context_database()
        table_key: tuple[str, str] = (context, table_name)

        # Verificar caché centralizada primero
        cached_result: list[str] | None = self.db_manager.relationship_cache.get_primary_keys_list(table_key)
        if cached_result is not None:
            self.logger.debug(f"♻️  PKs cacheadas: {table_name} = {len(cached_result)} columnas")
            return cached_result

        try:
            pks = self.db_manager.get_primary_keys(table_name)
            # Normalizar formato: si son tuplas, extraer nombre de columna
            pk_list = []
            for pk in pks:
                if isinstance(pk, (tuple, list)):
                    pk_list.append(str(pk[0]).lower())
                else:
                    pk_list.append(str(pk).lower())

            # Guardar en caché centralizada
            self.db_manager.relationship_cache.set_primary_keys_list(table_key, pk_list)
            self.logger.debug(f"💾 PKs calculadas: {table_name} = {pk_list}")
            return pk_list
        except DatabaseException as e:
            self.logger.warning(f"Error obteniendo claves primarias de {table_name}: {e}")
            return []

    def _get_unique_columns(self, table_name: str) -> list[str]:
        """
        Obtiene las columnas con restricciones UNIQUE (cacheado centralizado)

        Args:
            table_name: Nombre de la tabla

        Returns:
            Lista de nombres de columnas con restricción única
        """
        # Construir clave de tabla con contexto
        context: str = self.db_manager.get_query_context_database()
        table_key: tuple[str, str] = (context, table_name)

        # Verificar caché centralizada primero
        cached_result: list[str] | None = self.db_manager.relationship_cache.get_unique_constraints_list(table_key)
        if cached_result is not None:
            self.logger.debug(f"♻️  UCs cacheadas: {table_name} = {len(cached_result)} columnas")
            return cached_result

        try:
            ucs = self.db_manager.get_unique_constraints(table_name)
            # Normalizar formato: si son tuplas, extraer nombre de columna
            unique_list = []
            for uc in ucs:
                if isinstance(uc, (tuple, list)):
                    unique_list.append(str(uc[0]).lower())
                else:
                    unique_list.append(str(uc).lower())

            # Guardar en caché centralizada
            self.db_manager.relationship_cache.set_unique_constraints_list(table_key, unique_list)
            self.logger.debug(f"💾 UCs calculadas: {table_name} = {unique_list}")
            return unique_list
        except DatabaseException as e:
            self.logger.warning(f"Error obteniendo restricciones únicas de {table_name}: {e}")
            return []

    def _is_primary_key(self, table_name: str, column_name: str) -> bool:
        """Verifica si una columna es clave primaria (cacheado compartido)

        Args:
            table_name: Nombre de la tabla
            column_name: Nombre de la columna

        Returns:
            True si es clave primaria
        """
        # Verificar caché centralizada primero
        cached_result: bool | None = self.db_manager.relationship_cache.get_is_primary_key(table_name, column_name)
        if cached_result is not None:
            self.logger.debug(f"♻️  PK cacheado: {table_name}.{column_name} = {cached_result}")
            return cached_result

        pks: list[str] = self._get_primary_keys(table_name)
        result: bool = column_name.lower() in pks
        self.db_manager.relationship_cache.set_is_primary_key(table_name, column_name, result)
        self.logger.debug(f"💾 PK calculado: {table_name}.{column_name} = {result}")
        return result

    def _is_unique_column(self, table_name: str, column_name: str) -> bool:
        """Verifica si una columna tiene restricción UNIQUE (cacheado compartido)

        Args:
            table_name: Nombre de la tabla
            column_name: Nombre de la columna

        Returns:
            True si tiene restricción única
        """
        # Verificar caché centralizada primero
        cached_result: bool | None = self.db_manager.relationship_cache.get_is_unique_column(table_name, column_name)
        if cached_result is not None:
            self.logger.debug(f"♻️  UK cacheado: {table_name}.{column_name} = {cached_result}")
            return cached_result

        ucs: list[str] = self._get_unique_columns(table_name)
        result: bool = column_name.lower() in ucs
        self.db_manager.relationship_cache.set_is_unique_column(table_name, column_name, result)
        self.logger.debug(f"💾 UK calculado: {table_name}.{column_name} = {result}")
        return result

    def _determine_cardinality(self, source_col: str, target_col: str, source_table: str, target_table: str) -> str:
        """Determina la cardinalidad de una relación usando caché compartida

        Lógica de detección:
        - Si target_col es PK y source_col NO es PK/UK: 1:N (uno a muchos)
        - Si target_col es PK y source_col es UK: 1:1 (uno a uno)
        - Si ambos son PK: M:N (muchos a muchos en tabla junction)
        - En otros casos: N:1 (muchos a uno)

        Args:
            source_col: Columna de origen
            target_col: Columna de destino
            source_table: Tabla origen
            target_table: Tabla destino

        Returns:
            String con cardinalidad (ej: "1:N", "N:1", "1:1", "M:N")
        """
        # Verificar caché centralizada primero
        cached_result: str | None = self.db_manager.relationship_cache.get_cardinality(
            source_col, target_col, source_table, target_table
        )
        if cached_result is not None:
            self.logger.debug(
                f"♻️  Cardinalidad cacheada para {source_table}.{source_col} → {target_table}.{target_col}: {cached_result}"
            )
            return cached_result

        try:
            target_is_pk: bool = self._is_primary_key(target_table, target_col)
            source_is_pk: bool = self._is_primary_key(source_table, source_col)
            source_is_uk: bool = self._is_unique_column(source_table, source_col)

            self.logger.debug(
                f"🔍 Analizando cardinalidad: {source_table}.{source_col} → {target_table}.{target_col} "
                f"| source_PK={source_is_pk}, source_UK={source_is_uk}, target_PK={target_is_pk}"
            )

            # Caso 1: M:N (tabla many-to-many - ambos son PK)
            if source_is_pk and target_is_pk:
                result = "M:N"
                self.logger.debug("📊 Detectada relación M:N (ambos son PK)")
                self.db_manager.relationship_cache.set_cardinality(
                    source_col, target_col, source_table, target_table, result
                )
                return result

            # Caso 2: 1:1 (source tiene restricción única)
            if target_is_pk and source_is_uk:
                result = "1:1"
                self.logger.debug("📊 Detectada relación 1:1 (target es PK y source es UK)")
                self.db_manager.relationship_cache.set_cardinality(
                    source_col, target_col, source_table, target_table, result
                )
                return result

            # Caso 3: 1:N (target es PK, source es FK)
            if target_is_pk:
                result = "1:N"
                self.logger.debug("📊 Detectada relación 1:N (target es PK)")
                self.db_manager.relationship_cache.set_cardinality(
                    source_col, target_col, source_table, target_table, result
                )
                return result

            # Caso 4: N:1 (source es PK, target es FK) - por defecto
            result = "N:1"
            self.logger.debug("📊 Detectada relación N:1 (por defecto)")
            self.db_manager.relationship_cache.set_cardinality(
                source_col, target_col, source_table, target_table, result
            )
            return result

        except DatabaseException as e:
            self.logger.warning(f"⚠️ Error determinando cardinalidad: {e}, usando 1:N por defecto")
            return "1:N"

    def _build_cardinality_markers(self, cardinality: str) -> CardinalityEndMarker:
        """Convierte la cardinalidad textual a marcadores por extremo."""
        raw_parts = [part.strip() for part in cardinality.split(":", maxsplit=1)]
        if len(raw_parts) != 2:
            return CardinalityEndMarker(source_marker="N", target_marker="1", label=cardinality)

        target_marker, source_marker = raw_parts
        return CardinalityEndMarker(source_marker=source_marker, target_marker=target_marker, label=cardinality)

    def _build_related_columns_lookup(self, document: GraphDocument) -> dict[str, set[str]]:
        """Precalcula columnas relacionadas por tabla para evitar recorrer todas las aristas por nodo."""
        related_columns_by_table: dict[str, set[str]] = {table_name: set() for table_name in document.nodes}
        for edge in document.edges:
            relation: TableRelation = edge.relation
            related_columns_by_table.setdefault(relation.source_table, set()).add(relation.source_column.lower())
            related_columns_by_table.setdefault(relation.target_table, set()).add(relation.target_column.lower())
        return related_columns_by_table

    def _select_columns_for_table(
        self,
        table_name: str,
        related_columns: set[str],
    ) -> tuple[list[tuple[str, str]], int]:
        """Selecciona columnas visibles según la política configurada y devuelve cuántas quedan ocultas."""
        all_columns: list[tuple[str, str]] = self._get_table_columns_with_types(table_name)
        if not self.include_columns:
            return [], 0

        if self.column_mode == ColumnVisualizationMode.ALL:
            visible_columns: list[tuple[str, str]] = list(all_columns[: self.max_columns])
            return visible_columns, max(0, len(all_columns) - len(visible_columns))

        if self.column_mode == ColumnVisualizationMode.RELATIONS:
            filtered: list[tuple[str, str]] = [column for column in all_columns if column[0].lower() in related_columns]
            visible_columns = filtered[: self.max_columns]
            return visible_columns, max(0, len(filtered) - len(visible_columns))

        priority_columns: list[tuple[str, str]] = [
            column for column in all_columns if column[0].lower() in related_columns
        ]
        seen_names: set[str] = {column[0].lower() for column in priority_columns}
        for column in all_columns:
            if len(priority_columns) >= self.max_columns:
                break
            if column[0].lower() in seen_names:
                continue
            priority_columns.append(column)
            seen_names.add(column[0].lower())
        return priority_columns, max(0, len(all_columns) - len(priority_columns))

    def _truncate_label_text(self, value: str, max_chars: int) -> str:
        """Trunca texto largo para mantener nodos con tamaño visual estable."""
        normalized: str = str(value).strip()
        if max_chars <= 3 or len(normalized) <= max_chars:
            return normalized[:max_chars]
        return f"{normalized[: max_chars - 3]}..."

    def _build_table_html_label(
        self,
        table_name: str,
        related_columns: set[str] | None = None,
        is_main: bool = False,
        visual_type: TableVisualType | str = TableVisualType.ENTITY,
        is_raster: bool = False,
    ) -> str:
        """
        Construye una etiqueta HTML para un nodo de tabla con columnas y tipos

        Args:
            table_name: Nombre de la tabla
            is_main: Si es la tabla principal

        Returns:
            String con HTML para Graphviz
        """
        resolved_related_columns: set[str] = related_columns or set()
        columns, hidden_columns_count = self._select_columns_for_table(table_name, resolved_related_columns)
        bg_color: str = self._resolve_node_fill_color(visual_type)
        label_styles: dict[str, str] = self._get_table_label_styles(is_raster)
        html_parts: list[str] = [
            self._build_table_header_html(
                table_name=table_name,
                bg_color=bg_color,
                table_border_width="2" if is_main else "1",
                title_border_width="3" if is_main else "2",
                title_row_height=label_styles["title_row_height"],
                title_font_size=label_styles["title_font_size"],
                table_width=label_styles["table_width"],
                title_max_chars=int(label_styles["title_max_chars"]),
            )
        ]

        # Agregar columnas solo si están habilitadas
        if self.include_columns:
            if columns:
                html_parts.extend(
                    self._build_column_rows_html(
                        table_name=table_name,
                        columns=columns,
                        related_columns=resolved_related_columns,
                        column_font_size=label_styles["column_font_size"],
                        type_font_size=label_styles["type_font_size"],
                        name_column_width=label_styles["name_column_width"],
                        type_column_width=label_styles["type_column_width"],
                        column_name_max_chars=int(label_styles["column_name_max_chars"]),
                        type_max_chars=int(label_styles["type_max_chars"]),
                    )
                )
            else:
                html_parts.append(
                    self._build_message_row_html(
                        message="Sin columnas visibles",
                        font_size=label_styles["type_font_size"],
                        table_width=label_styles["table_width"],
                    )
                )

            # Agregar mensaje de columnas ocultas si las hay
            if hidden_columns_count > 0:
                html_parts.append(
                    self._build_message_row_html(
                        message=f"... {hidden_columns_count} columna(s) mas",
                        font_size=label_styles["type_font_size"],
                        table_width=label_styles["table_width"],
                    )
                )

        # Retorno único al final
        html_content = "".join(html_parts)
        return f"{html_content}</TABLE>>"

    def _get_table_label_styles(self, is_raster: bool) -> dict[str, str]:
        """Devuelve las medidas tipográficas del label según el formato de salida."""
        return {
            "title_row_height": "46" if is_raster else "40",
            "title_font_size": "12" if is_raster else "10",
            "column_font_size": "10" if is_raster else "9",
            "type_font_size": "9" if is_raster else "8",
            "table_width": "280" if is_raster else self.DEFAULT_TABLE_WIDTH,
            "name_column_width": "185" if is_raster else self.DEFAULT_NAME_COLUMN_WIDTH,
            "type_column_width": "95" if is_raster else self.DEFAULT_TYPE_COLUMN_WIDTH,
            "title_max_chars": str(34 if is_raster else self.DEFAULT_TITLE_MAX_CHARS),
            "column_name_max_chars": str(28 if is_raster else self.DEFAULT_COLUMN_MAX_CHARS),
            "type_max_chars": str(22 if is_raster else self.DEFAULT_TYPE_MAX_CHARS),
        }

    def _build_table_header_html(
        self,
        table_name: str,
        bg_color: str,
        table_border_width: str,
        title_border_width: str,
        title_row_height: str,
        title_font_size: str,
        table_width: str,
        title_max_chars: int,
    ) -> str:
        """Construye la cabecera HTML del nodo de tabla."""
        title_colspan = "2" if self.show_data_types and self.include_columns else "1"
        title_text: str = self._truncate_label_text(table_name, title_max_chars)
        return (
            f'<<TABLE BORDER="{table_border_width}" CELLBORDER="1" CELLSPACING="0" CELLPADDING="5" BGCOLOR="{bg_color}">'
            f'<TR HEIGHT="{title_row_height}"><TD COLSPAN="{title_colspan}" WIDTH="{table_width}" '
            f'BGCOLOR="{bg_color}" BORDER="{title_border_width}" VALIGN="MIDDLE">'
            f'<B><FONT POINT-SIZE="{title_font_size}">{html.escape(title_text)}</FONT></B></TD></TR>'
        )

    def _resolve_node_fill_color(self, visual_type: TableVisualType | str) -> str:
        """Devuelve el color de relleno según la tipología visual de la tabla."""
        if isinstance(visual_type, TableVisualType):
            normalized_visual_type = visual_type.value
        else:
            normalized_visual_type = str(visual_type).strip().lower()
        color_by_type: dict[str, str] = {
            TableVisualType.ENTITY.value: self.ENTITY_TABLE_COLOR,
            TableVisualType.ASSOCIATION.value: self.ASSOCIATION_TABLE_COLOR,
            TableVisualType.HIERARCHY.value: self.HIERARCHY_TABLE_COLOR,
        }
        return color_by_type.get(normalized_visual_type, self.ENTITY_TABLE_COLOR)

    def _build_column_rows_html(
        self,
        table_name: str,
        columns: list[tuple[str, str]],
        related_columns: set[str],
        column_font_size: str,
        type_font_size: str,
        name_column_width: str,
        type_column_width: str,
        column_name_max_chars: int,
        type_max_chars: int,
    ) -> list[str]:
        """Construye las filas HTML de las columnas visibles."""
        return [
            self._build_column_row_html(
                table_name=table_name,
                col_name=col_name,
                col_type=col_type,
                related_columns=related_columns,
                column_font_size=column_font_size,
                type_font_size=type_font_size,
                name_column_width=name_column_width,
                type_column_width=type_column_width,
                column_name_max_chars=column_name_max_chars,
                type_max_chars=type_max_chars,
            )
            for col_name, col_type in columns
        ]

    def _build_column_row_html(
        self,
        table_name: str,
        col_name: str,
        col_type: str,
        related_columns: set[str],
        column_font_size: str,
        type_font_size: str,
        name_column_width: str,
        type_column_width: str,
        column_name_max_chars: int,
        type_max_chars: int,
    ) -> str:
        """Construye la fila HTML de una columna."""
        escaped_name: str = html.escape(self._truncate_label_text(col_name, column_name_max_chars))
        escaped_type: str = html.escape(self._truncate_label_text(col_type.split("(")[0], type_max_chars))
        badge_prefix, name_color = self._build_column_badge_prefix(
            table_name=table_name,
            col_name=col_name,
            related_columns=related_columns,
        )
        html_row: str = (
            f'<TR><TD ALIGN="LEFT" WIDTH="{name_column_width}"><FONT POINT-SIZE="{column_font_size}" COLOR="{name_color}">'
            f"{html.escape(badge_prefix)}{escaped_name}</FONT></TD>"
        )
        if self.show_data_types:
            html_row += (
                f'<TD ALIGN="LEFT" WIDTH="{type_column_width}"><FONT POINT-SIZE="{type_font_size}" '
                f'COLOR="black">{escaped_type}</FONT></TD>'
            )
        return html_row + "</TR>"

    def _build_column_badge_prefix(
        self,
        table_name: str,
        col_name: str,
        related_columns: set[str],
    ) -> tuple[str, str]:
        """Calcula badges y color para una columna del nodo."""
        is_pk: bool = self._is_primary_key(table_name, col_name)
        is_unique: bool = self._is_unique_column(table_name, col_name)
        is_related: bool = col_name.lower() in related_columns
        badges: list[str] = []
        if is_pk:
            badges.append("PK")
        elif is_related:
            badges.append("REL")
        if is_unique and not is_pk:
            badges.append("UQ")
        badge_prefix: str = f"[{'/'.join(badges)}] " if badges else ""
        name_color: str = "#A61C00" if is_pk else self.TEXT_COLOR
        return badge_prefix, name_color

    def _build_message_row_html(self, message: str, font_size: str, table_width: str | None = None) -> str:
        """Construye una fila HTML de mensaje centrado."""
        message_colspan = "2" if self.show_data_types else "1"
        width_attr: str = f' WIDTH="{table_width}"' if table_width else ""
        return (
            f'<TR><TD COLSPAN="{message_colspan}" ALIGN="CENTER"{width_attr}><FONT POINT-SIZE="{font_size}" COLOR="black">'
            f"{html.escape(message)}"
            "</FONT></TD></TR>"
        )

    def _build_level_documents(
        self,
        table_name: str,
        max_depth: int | None = None,
        direction: LevelDirection | str | None = None,
        document: GraphDocument | None = None,
    ) -> tuple[GraphDocument, dict[LevelDirection, list[GraphDocument]]]:
        """Construye subdocumentos independientes por nivel y por sentido."""
        if document is None:
            effective_depth = self.max_depth if max_depth is None else max(1, int(max_depth))
            effective_direction = self.direction if direction is None else self._normalize_direction(direction)
            document = self.build_graph_document(
                table_name=table_name,
                max_depth=effective_depth,
                direction=effective_direction,
            )

        grouped_documents: dict[LevelDirection, list[GraphDocument]] = {
            LevelDirection.OUTGOING: [],
            LevelDirection.INCOMING: [],
        }
        for level in sorted(document.levels, key=lambda item: (item.direction.value, item.depth)):
            grouped_documents[level.direction].append(
                self._build_subset_document(document, [edge.relation for edge in level.edges])
            )

        return document, grouped_documents

    def generate_graphviz_level_graphs_ext(
        self,
        table_name: str,
        output_dir: Path,
        format: str = "svg",
        show_columns: bool | None = None,
        max_depth: int | None = None,
        direction: LevelDirection | str | None = None,
        document: GraphDocument | None = None,
    ) -> dict[str, Any]:
        """Genera un diagrama independiente por nivel y por sentido."""
        include_columns: bool = self.include_columns if show_columns is None else bool(show_columns)
        document, grouped_documents = self._build_level_documents(
            table_name=table_name,
            max_depth=max_depth,
            direction=direction,
            document=document,
        )

        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        results: dict[str, Any] = {
            "summary": {
                "root_table": document.root_table,
                "max_depth": document.max_depth,
                "total_outgoing_levels": document.total_outgoing_levels,
                "total_incoming_levels": document.total_incoming_levels,
                "hidden_outgoing_levels": document.hidden_levels.outgoing_hidden_levels,
                "hidden_incoming_levels": document.hidden_levels.incoming_hidden_levels,
            },
            "outgoing": [],
            "incoming": [],
        }

        for group_direction, direction_key in (
            (LevelDirection.OUTGOING, "outgoing"),
            (LevelDirection.INCOMING, "incoming"),
        ):
            for level_document in grouped_documents[group_direction]:
                if not level_document.levels:
                    continue
                level_depth_candidates: list[int] = [
                    level.depth for level in level_document.levels if level.direction == group_direction
                ]
                level_depth: int = (
                    min(level_depth_candidates) if level_depth_candidates else level_document.levels[0].depth
                )
                output_file: Path = output_dir / f"graphviz_ext_{table_name}_{direction_key}_level{level_depth}"
                generated_path: Path = self._generate_graphviz_graph_internal_ext(
                    table_name=table_name,
                    output_file=output_file,
                    format=format,
                    document=level_document,
                    show_columns=include_columns,
                )
                results[direction_key].append(
                    {
                        "depth": level_depth,
                        "path": generated_path,
                        "title": f"Nivel {level_depth}",
                    }
                )

        return results

    def generate_graphviz_graph_paginated_ext(
        self,
        table_name: str,
        output_dir: Path,
        format: str = "png",
        max_subnodes: int = 10,
        show_columns: bool | None = None,
        max_depth: int | None = None,
        direction: LevelDirection | str | None = None,
        document: GraphDocument | None = None,
    ) -> list[Path]:
        """
        Genera grafos Graphviz extendidos dividiendo en múltiples imágenes si es necesario

        Args:
            table_name: Tabla central del grafo
            output_dir: Directorio de salida para los archivos
            format: Formato de salida (png, svg, pdf, etc.)
            max_subnodes: Máximo de sub-nodos por imagen
            show_columns: Si True, muestra columnas en los nodos

        Returns:
            Lista de Paths de archivos generados
        """
        include_columns = self.include_columns if show_columns is None else bool(show_columns)
        effective_depth = self.max_depth if max_depth is None else max(1, int(max_depth))
        effective_direction = self.direction if direction is None else self._normalize_direction(direction)

        self.logger.info(
            f"Iniciando generación paginada extendida de Graphviz para {table_name} "
            f"(max {max_subnodes} nodos por página)"
        )
        if document is None:
            document = self.build_graph_document(
                table_name=table_name,
                max_depth=effective_depth,
                direction=effective_direction,
            )
        relations: list[TableRelation] = list(document.relations)
        self.logger.info(f"📈 Relaciones analizadas para {table_name}: {len(relations)}")
        split_relations: list[list[TableRelation]] = self._split_relations_for_visualization(relations, max_subnodes)
        self.logger.debug(f"Tabla {table_name} dividida en {len(split_relations)} página(s)")

        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        generated_files: list[Path] = []

        for page_num, page_relations in enumerate(split_relations, 1):
            # Crear nombre de archivo descriptivo
            if len(split_relations) > 1:
                file_name: str = f"graphviz_ext_{table_name}_page{page_num}"
            else:
                file_name = f"graphviz_ext_{table_name}"

            output_path: Path = output_dir / file_name

            # Generar gráfico para esta página
            page_document: GraphDocument = self._build_subset_document(document, page_relations)
            generated_file: Path = self._generate_graphviz_graph_internal_ext(
                table_name=table_name,
                output_file=output_path,
                format=format,
                document=page_document,
                show_columns=include_columns,
            )
            self.logger.info(
                f"🖼️  Página Graphviz {page_num}/{len(split_relations)} de {table_name} generada "
                f"con {len(page_relations)} relaciones"
            )
            generated_files.append(generated_file)

        return generated_files

    def _generate_graphviz_graph_internal_ext(
        self,
        table_name: str,
        output_file: Path,
        format: str,
        document: GraphDocument,
        show_columns: bool = True,
    ) -> Path:
        """
        Genera un gráfico Graphviz interno extendido con detalles de columnas y cardinalidad

        Args:
            table_name: Tabla central
            output_file: Ruta de salida
            format: Formato
            relations: Relaciones a incluir en el gráfico
            show_columns: Si mostrar columnas en nodos

        Returns:
            Path del archivo generado
        """
        if not GRAPHVIZ_AVAILABLE or graphviz is None:
            raise ImportError(GRAPHVIZ_MISSING_MSG)

        try:
            output_file = Path(output_file).resolve()
            output_file.parent.mkdir(parents=True, exist_ok=True)

            dot, is_raster_format, edge_label_font_size = self._create_configured_graph(
                table_name=table_name,
                format=format,
                show_columns=show_columns,
            )
            self._add_graph_footer(dot=dot, document=document)

            self._add_nodes_to_graph(
                dot=dot,
                document=document,
                show_columns=show_columns,
                is_raster_format=is_raster_format,
            )
            self._add_edges_to_graph(dot=dot, document=document, edge_label_font_size=edge_label_font_size)

            return self._render_graph(dot=dot, output_file=output_file, format=format, table_name=table_name)
        except (OSError, RuntimeError) as e:
            self.logger.error(
                f"Error al generar gráfico Graphviz extendido para tabla {table_name}: {str(e)}",
                exc_info=True,
            )
            raise

    def _add_graph_footer(self, dot: Any, document: GraphDocument) -> None:
        """Agrega metadatos del recorrido al pie del grafo."""
        footer_lines: list[str] = [
            f"Profundidad visible: {document.max_depth}",
            f"Niveles salida: {document.total_outgoing_levels}",
            f"Niveles entrada: {document.total_incoming_levels}",
        ]
        if document.hidden_levels.outgoing_hidden_levels > 0:
            footer_lines.append(
                f"Salida oculta: {document.hidden_levels.outgoing_hidden_levels} nivel(es) no visibles por profundidad"
            )
        if document.hidden_levels.incoming_hidden_levels > 0:
            footer_lines.append(
                f"Entrada oculta: {document.hidden_levels.incoming_hidden_levels} nivel(es) no visibles por profundidad"
            )

        dot.attr("graph", label=" | ".join(footer_lines), labelloc="b", labeljust="l")

    def _create_configured_graph(self, table_name: str, format: str, show_columns: bool) -> tuple[Any, bool, str]:
        """
        Crea y configura la instancia de Graphviz con layout y tipografías base.

        Args:
            table_name: Tabla principal
            format: Formato de salida
            show_columns: Si se muestran columnas

        Returns:
            Tupla (dot, is_raster_format, edge_label_font_size)
        """
        if graphviz is None:
            raise ImportError(GRAPHVIZ_MISSING_MSG)

        engine_name: str = "dot" if show_columns else "circo"
        splines_value: str = "ortho" if self.orthogonal_edges and engine_name == "dot" else "true"
        dot = graphviz.Digraph(
            comment=f"Relaciones extendidas de {table_name}",
            format=format,
            engine=engine_name,
        )
        nodesep_value: str = str(self.orthogonal_nodesep) if self.orthogonal_edges and engine_name == "dot" else "0.5"
        ranksep_value: str = str(self.orthogonal_ranksep) if self.orthogonal_edges and engine_name == "dot" else "0.7"
        dot.attr(
            "graph",
            overlap="false",
            splines=splines_value,
            pad="0.3",
            nodesep=nodesep_value,
            ranksep=ranksep_value,
            forcelabels="true",
        )

        is_raster_format: bool = format.lower() in {"png", "jpg", "jpeg"}
        if is_raster_format:
            dot.attr("graph", dpi=str(self.render_dpi))

        node_font_size: str = "12" if is_raster_format else "10"
        edge_font_size: str = "10" if is_raster_format else "9"
        edge_label_font_size: str = "9" if is_raster_format else "8"

        # `plain` elimina el margen implícito del nodo y ajusta mejor la arista al borde visual del label HTML.
        dot.attr("node", shape="plain", margin="0", fontname="Arial", fontsize=node_font_size)
        dot.attr("edge", fontname="Arial", fontsize=edge_font_size, color="#666666")

        return dot, is_raster_format, edge_label_font_size

    def _add_nodes_to_graph(
        self,
        dot: Any,
        document: GraphDocument,
        show_columns: bool,
        is_raster_format: bool,
    ) -> None:
        """
        Agrega los nodos al grafo con estilo simple o etiqueta HTML extendida.

        Args:
            dot: Grafo Graphviz
            tables_in_page: Tablas a dibujar
            table_name: Tabla principal
            show_columns: Si mostrar columnas
            is_raster_format: Si el formato es raster
        """
        related_columns_by_table: dict[str, set[str]] = (
            self._build_related_columns_lookup(document) if show_columns else {}
        )
        for table, node in document.nodes.items():
            is_main: bool = node.is_root
            if show_columns:
                html_label: str = self._build_table_html_label(
                    table,
                    related_columns_by_table.get(table, set()),
                    is_main,
                    node.visual_type,
                    is_raster=is_raster_format,
                )
                dot.node(table, html_label)
                continue

            bg_color: str = self._resolve_node_fill_color(node.visual_type)
            dot.node(
                table,
                table,
                shape="box",
                style="filled",
                fillcolor=bg_color,
                color="#1F1F1F" if is_main else "#666666",
                penwidth="2" if is_main else "1",
            )

    def _add_edges_to_graph(self, dot: Any, document: GraphDocument, edge_label_font_size: str) -> None:
        """
        Agrega aristas con cardinalidad y etiqueta de columnas.

        Args:
            dot: Grafo Graphviz
            relations: Relaciones a dibujar
            edge_label_font_size: Tamaño de fuente para etiquetas de arista
        """
        for edge in document.edges:
            relation = edge.relation
            edge_attributes = self._build_edge_attributes(edge=edge, edge_label_font_size=edge_label_font_size)
            dot.edge(relation.source_table, relation.target_table, **edge_attributes)

    def _build_edge_attributes(self, edge: GraphEdge, edge_label_font_size: str) -> dict[str, str]:
        """Construye los atributos de render de una arista, incluyendo cardinalidad legible."""
        relation: TableRelation = edge.relation
        cardinality: str = self._determine_cardinality(
            source_col=relation.source_column,
            target_col=relation.target_column,
            source_table=relation.source_table,
            target_table=relation.target_table,
        )
        relation_label: str = f"{relation.source_column} -> {relation.target_column}"
        if self.show_constraint_name:
            relation_label = f"{relation.constraint_name}: {relation_label}"

        cardinality_markers: CardinalityEndMarker = self._build_cardinality_markers(cardinality)
        edge_color: str = "#1D70B8" if edge.direction == LevelDirection.OUTGOING else "#A61C00"
        return {
            "xlabel": relation_label,
            "taillabel": cardinality_markers.source_marker,
            "headlabel": cardinality_markers.target_marker,
            "fontsize": edge_label_font_size,
            "labelfontsize": edge_label_font_size,
            "labeldistance": self.CARDINALITY_LABEL_DISTANCE,
            "labelangle": self.CARDINALITY_LABEL_ANGLE,
            "color": edge_color,
        }

    def _render_graph(self, dot: Any, output_file: Path, format: str, table_name: str) -> Path:
        """
        Renderiza el grafo y valida que el archivo de salida exista.

        Args:
            dot: Grafo Graphviz
            output_file: Ruta de salida sin extensión
            format: Formato de salida
            table_name: Tabla principal

        Returns:
            Ruta del archivo generado

        Raises:
            FileNotFoundError: Si Graphviz no genera el archivo esperado
        """
        output_path_str: str = str(output_file)
        self.logger.info(f"🎨 Renderizando Graphviz para {table_name}: formato={format}, archivo={output_path_str}")
        dot.render(output_path_str, cleanup=True)
        self.logger.info(f"🎨 Render Graphviz completado para {table_name}")

        expected_file = Path(f"{output_path_str}.{format}")
        if expected_file.exists():
            self.logger.info(f"Gráfico Graphviz extendido generado exitosamente para {table_name}")
            return expected_file

        raise FileNotFoundError(f"Archivo no encontrado: {expected_file}")

    def _pipe_graph_bytes(self, dot: Any, format: str, table_name: str) -> bytes:
        """Renderiza el grafo en memoria y devuelve los bytes sin escribir a disco.

        Args:
            dot: Grafo Graphviz configurado y con nodos/aristas ya añadidos
            format: Formato de salida (png, svg, pdf, etc.)
            table_name: Tabla principal (solo para logging)

        Returns:
            bytes: Contenido del gráfico renderizado en el formato indicado

        Raises:
            OSError: Si el ejecutable dot no está disponible o falla durante el pipe
            RuntimeError: Si Graphviz produce una salida vacía o inválida

        Example:
            >>> png_bytes = self._pipe_graph_bytes(dot, "png", "orders")
            >>> len(png_bytes) > 0
            True
        """
        self.logger.info(f"🎨 Pipe Graphviz para {table_name}: formato={format}")
        result: bytes = dot.pipe(format=format)
        self.logger.info(f"🎨 Pipe Graphviz completado para {table_name} ({len(result)} bytes)")
        return result

    def pipe_single_table_graph_ext(
        self,
        table_name: str,
        format: str = "png",
        show_columns: bool | None = None,
        max_depth: int | None = None,
        direction: LevelDirection | str | None = None,
        document: GraphDocument | None = None,
    ) -> bytes:
        """Genera el gráfico de una tabla en memoria y devuelve los bytes sin escribir a disco.

        Variante en memoria de generate_single_table_graph_ext. Útil para insertarlos
        directamente en documentos Word o incrustarlos inline en HTML sin I/O de disco.

        Args:
            table_name: Nombre de la tabla
            format: Formato de salida (png, svg, pdf, etc.)
            show_columns: Si mostrar columnas en nodos (None = usar valor del generador)
            max_depth: Profundidad máxima de relaciones (None = usar valor del generador)
            direction: Dirección de relaciones (None = usar valor del generador)
            document: GraphDocument preconstruido (None = construir internamente)

        Returns:
            bytes: Contenido del gráfico renderizado en el formato indicado

        Raises:
            ImportError: Si graphviz no está instalado
            OSError: Si el ejecutable dot no está disponible
            RuntimeError: Si la generación falla

        Example:
            >>> png_bytes = generator.pipe_single_table_graph_ext("orders", format="png")
            >>> len(png_bytes) > 0
            True
        """
        if not GRAPHVIZ_AVAILABLE or graphviz is None:
            raise ImportError(GRAPHVIZ_MISSING_MSG)

        include_columns: bool = self.include_columns if show_columns is None else bool(show_columns)
        effective_depth: int = self.max_depth if max_depth is None else max(1, int(max_depth))
        effective_direction: LevelDirection = (
            self.direction if direction is None else self._normalize_direction(direction)
        )
        self.logger.info(f"Generando gráfico en memoria para tabla: {table_name}")

        if document is None:
            document = self.build_graph_document(
                table_name=table_name,
                max_depth=effective_depth,
                direction=effective_direction,
            )

        try:
            dot, is_raster_format, edge_label_font_size = self._create_configured_graph(
                table_name=table_name,
                format=format,
                show_columns=include_columns,
            )
            self._add_graph_footer(dot=dot, document=document)
            self._add_nodes_to_graph(
                dot=dot,
                document=document,
                show_columns=include_columns,
                is_raster_format=is_raster_format,
            )
            self._add_edges_to_graph(dot=dot, document=document, edge_label_font_size=edge_label_font_size)
            return self._pipe_graph_bytes(dot=dot, format=format, table_name=table_name)
        except (OSError, RuntimeError) as e:
            self.logger.error(
                f"Error al generar gráfico en memoria para tabla {table_name}: {str(e)}",
                exc_info=True,
            )
            raise

    def _pipe_graph_internal_ext(
        self,
        table_name: str,
        format: str,
        document: GraphDocument,
        show_columns: bool = True,
    ) -> bytes:
        """Genera un gráfico Graphviz en memoria sin escribir a disco.

        Versión pipe de _generate_graphviz_graph_internal_ext: misma lógica
        pero llama a dot.pipe() en vez de dot.render(), evitando I/O de disco.

        Args:
            table_name: Tabla central del grafo
            format: Formato de salida (png, svg, pdf, etc.)
            document: GraphDocument con relaciones y niveles ya construidos
            show_columns: Si mostrar columnas en los nodos

        Returns:
            bytes: Contenido del gráfico en el formato indicado

        Raises:
            ImportError: Si graphviz no está instalado
            OSError: Si el ejecutable dot no está disponible
            RuntimeError: Si Graphviz falla durante el pipe

        Example:
            >>> svg_bytes = generator._pipe_graph_internal_ext("orders", "svg", doc)
            >>> len(svg_bytes) > 0
            True
        """
        if not GRAPHVIZ_AVAILABLE or graphviz is None:
            raise ImportError(GRAPHVIZ_MISSING_MSG)
        try:
            dot, is_raster_format, edge_label_font_size = self._create_configured_graph(
                table_name=table_name,
                format=format,
                show_columns=show_columns,
            )
            self._add_graph_footer(dot=dot, document=document)
            self._add_nodes_to_graph(
                dot=dot,
                document=document,
                show_columns=show_columns,
                is_raster_format=is_raster_format,
            )
            self._add_edges_to_graph(dot=dot, document=document, edge_label_font_size=edge_label_font_size)
            return self._pipe_graph_bytes(dot=dot, format=format, table_name=table_name)
        except (OSError, RuntimeError) as e:
            self.logger.error(
                f"Error al generar gráfico en memoria para tabla {table_name}: {str(e)}",
                exc_info=True,
            )
            raise

    def pipe_paginated_graph_ext(
        self,
        table_name: str,
        format: str = "png",
        max_subnodes: int = 10,
        show_columns: bool | None = None,
        max_depth: int | None = None,
        direction: LevelDirection | str | None = None,
        document: GraphDocument | None = None,
    ) -> list[bytes]:
        """Genera grafos Graphviz paginados en memoria sin I/O de disco.

        Versión pipe de generate_graphviz_graph_paginated_ext: divide las
        relaciones en páginas igual que el método original pero renderiza
        cada página con dot.pipe() devolviendo bytes en vez de archivos.

        Args:
            table_name: Tabla central del grafo
            format: Formato de salida (png, svg, etc.)
            max_subnodes: Máximo de sub-nodos por página
            show_columns: Si mostrar columnas; None usa self.include_columns
            max_depth: Profundidad máxima; None usa self.max_depth
            direction: Dirección de relaciones; None usa self.direction
            document: GraphDocument preconstruido; None lo construye internamente

        Returns:
            list[bytes]: Un elemento por página, en el formato indicado

        Raises:
            ImportError: Si graphviz no está instalado
            OSError: Si el ejecutable dot no está disponible
            RuntimeError: Si Graphviz falla durante el pipe

        Example:
            >>> pages = generator.pipe_paginated_graph_ext("orders", format="png")
            >>> len(pages) >= 1
            True
            >>> len(pages[0]) > 0
            True
        """
        include_columns = self.include_columns if show_columns is None else bool(show_columns)
        effective_depth = self.max_depth if max_depth is None else max(1, int(max_depth))
        effective_direction = self.direction if direction is None else self._normalize_direction(direction)

        self.logger.info(
            f"Iniciando generación paginada en memoria para {table_name} (max {max_subnodes} nodos por página)"
        )
        if document is None:
            document = self.build_graph_document(
                table_name=table_name,
                max_depth=effective_depth,
                direction=effective_direction,
            )
        relations: list[TableRelation] = list(document.relations)
        self.logger.info(f"📈 Relaciones analizadas para {table_name}: {len(relations)}")
        split_relations: list[list[TableRelation]] = self._split_relations_for_visualization(relations, max_subnodes)
        self.logger.debug(f"Tabla {table_name} dividida en {len(split_relations)} página(s) para pipe")

        result: list[bytes] = []
        for page_num, page_relations in enumerate(split_relations, 1):
            page_document: GraphDocument = self._build_subset_document(document, page_relations)
            page_bytes: bytes = self._pipe_graph_internal_ext(
                table_name=table_name,
                format=format,
                document=page_document,
                show_columns=include_columns,
            )
            self.logger.info(
                f"🖼️  Página {page_num}/{len(split_relations)} de {table_name} generada en memoria "
                f"({len(page_bytes)} bytes)"
            )
            result.append(page_bytes)

        return result

    def pipe_level_graphs_ext(
        self,
        table_name: str,
        format: str = "svg",
        show_columns: bool | None = None,
        max_depth: int | None = None,
        direction: LevelDirection | str | None = None,
        document: GraphDocument | None = None,
    ) -> dict[str, Any]:
        """Genera grafos por nivel en memoria sin I/O de disco.

        Versión pipe de generate_graphviz_level_graphs_ext: misma estructura
        de retorno pero con clave "bytes" (bytes) en vez de "path" (Path) en
        cada item de nivel, y sin crear archivos temporales.

        Args:
            table_name: Tabla central del grafo
            format: Formato de salida (svg, png, etc.)
            show_columns: Si mostrar columnas; None usa self.include_columns
            max_depth: Profundidad máxima; None usa self.max_depth
            direction: Dirección de relaciones; None usa self.direction
            document: GraphDocument preconstruido; None lo construye internamente

        Returns:
            dict[str, Any]: Misma estructura que generate_graphviz_level_graphs_ext
                pero cada item lleva "bytes": bytes en vez de "path": Path.
                Ejemplo::

                    {
                        "summary": {"root_table": "orders", "max_depth": 2, ...},
                        "outgoing": [{"depth": 1, "bytes": b"...", "title": "Nivel 1"}],
                        "incoming": [{"depth": 1, "bytes": b"...", "title": "Nivel 1"}],
                    }

        Raises:
            ImportError: Si graphviz no está instalado
            OSError: Si el ejecutable dot no está disponible
            RuntimeError: Si Graphviz falla durante el pipe

        Example:
            >>> groups = generator.pipe_level_graphs_ext("orders", format="svg")
            >>> len(groups["outgoing"]) >= 1
            True
            >>> len(groups["outgoing"][0]["bytes"]) > 0
            True
        """
        include_columns: bool = self.include_columns if show_columns is None else bool(show_columns)
        document, grouped_documents = self._build_level_documents(
            table_name=table_name,
            max_depth=max_depth,
            direction=direction,
            document=document,
        )

        results: dict[str, Any] = {
            "summary": {
                "root_table": document.root_table,
                "max_depth": document.max_depth,
                "total_outgoing_levels": document.total_outgoing_levels,
                "total_incoming_levels": document.total_incoming_levels,
                "hidden_outgoing_levels": document.hidden_levels.outgoing_hidden_levels,
                "hidden_incoming_levels": document.hidden_levels.incoming_hidden_levels,
            },
            "outgoing": [],
            "incoming": [],
        }

        for group_direction, direction_key in (
            (LevelDirection.OUTGOING, "outgoing"),
            (LevelDirection.INCOMING, "incoming"),
        ):
            for level_document in grouped_documents[group_direction]:
                if not level_document.levels:
                    continue
                level_depth_candidates: list[int] = [
                    level.depth for level in level_document.levels if level.direction == group_direction
                ]
                level_depth: int = (
                    min(level_depth_candidates) if level_depth_candidates else level_document.levels[0].depth
                )
                svg_bytes: bytes = self._pipe_graph_internal_ext(
                    table_name=table_name,
                    format=format,
                    document=level_document,
                    show_columns=include_columns,
                )
                results[direction_key].append(
                    {
                        "depth": level_depth,
                        "bytes": svg_bytes,
                        "title": f"Nivel {level_depth}",
                    }
                )

        return results

    def generate_all_tables_graphs_ext(
        self,
        output_dir: Path | None = None,
        format: str = "png",
        skip_tables_without_relations: bool = True,
        max_subnodes: int = 10,
        show_columns: bool | None = None,
        max_depth: int | None = None,
        direction: LevelDirection | str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Genera grafos Graphviz extendidos para todas las tablas de la base de datos

        Args:
            output_dir: Directorio de salida (default: ./grafos_graphviz_ext)
            format: Formato de salida (png, svg, pdf, etc.)
            skip_tables_without_relations: Si True, omite tablas sin relaciones
            max_subnodes: Máximo de sub-nodos por imagen
            show_columns: Si mostrar columnas en los nodos

        Returns:
            Diccionario con los resultados {tabla: {status, files, error}}
        """
        include_columns: bool = self.include_columns if show_columns is None else bool(show_columns)
        output_dir = self._resolve_graph_output_dir(output_dir)
        table_names: list[str] = self._get_all_table_names()

        self.logger.info(f"Iniciando generación de grafos Graphviz extendidos para {len(table_names)} tablas")
        self.logger.info(f"Directorio de salida: {output_dir}")
        self.logger.info(f"Formato: {format}, max_subnodes: {max_subnodes}, mostrar columnas: {show_columns}")

        def _generate_for_table(table_name: str) -> list[Path]:
            return self.generate_graphviz_graph_paginated_ext(
                table_name=table_name,
                output_dir=output_dir,
                format=format,
                max_subnodes=max_subnodes,
                show_columns=include_columns,
                max_depth=max_depth,
                direction=direction,
            )

        return self._generate_all_tables_batch(
            table_names=table_names,
            skip_tables_without_relations=skip_tables_without_relations,
            max_depth=max_depth,
            direction=direction,
            generate_for_table=_generate_for_table,
            error_prefix="Error generando gráfico extendido para tabla",
        )

    def _resolve_graph_output_dir(self, output_dir: Path | None) -> Path:
        """Normaliza y crea el directorio de salida para grafos Graphviz."""
        return self._resolve_output_dir(output_dir=output_dir, default_dir="./grafos_graphviz_ext")

    def generate_single_table_graph_ext(
        self,
        table_name: str,
        output_file: Path,
        format: str = "png",
        show_columns: bool | None = None,
        max_depth: int | None = None,
        direction: LevelDirection | str | None = None,
        document: GraphDocument | None = None,
    ) -> Path:
        """
        Genera un gráfico extendido para una única tabla sin paginación

        Args:
            table_name: Nombre de la tabla
            output_file: Ruta del archivo de salida
            format: Formato de salida
            show_columns: Si mostrar columnas

        Returns:
            Path del archivo generado
        """
        include_columns: bool = self.include_columns if show_columns is None else bool(show_columns)
        effective_depth: int = self.max_depth if max_depth is None else max(1, int(max_depth))
        effective_direction: LevelDirection = (
            self.direction if direction is None else self._normalize_direction(direction)
        )
        self.logger.info(f"Generando gráfico extendido simple para tabla: {table_name}")
        if document is None:
            document = self.build_graph_document(
                table_name=table_name,
                max_depth=effective_depth,
                direction=effective_direction,
            )

        return self._generate_graphviz_graph_internal_ext(
            table_name=table_name,
            output_file=output_file,
            format=format,
            document=document,
            show_columns=include_columns,
        )
