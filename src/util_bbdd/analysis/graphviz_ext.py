"""Renderer Graphviz sobre el nuevo modelo multinivel de relaciones."""

from __future__ import annotations

import html
import logging
import os
import subprocess
import tempfile

from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor
from logging import Logger
from pathlib import Path
from typing import Any

try:
    import graphviz

    GRAPHVIZ_AVAILABLE = True
except ImportError:
    graphviz = None
    GRAPHVIZ_AVAILABLE = False

from .._core.exceptions import DatabaseException
from .._core.filenames import safe_file_stem
from ..metadata.model import Kind
from .base import (
    CardinalityEndMarker,
    ColumnVisualizationMode,
    DatabaseRelationshipGraphBase,
    GraphDocument,
    GraphEdge,
    LevelDirection,
    TableRelation,
    TableVisualType,
)
from .contracts import RelationshipGraphSource

GRAPHVIZ_MISSING_MSG: str = "Graphviz no disponible. Instale: pip install graphviz"
_MAX_DEFAULT_RENDER_WORKERS: int = 8
# Grafos por proceso ``dot -O`` (acota la línea de comandos; arrancar dot cuesta ~0,25 s y renderizar ~0,01 s)
_MAX_GRAPHS_PER_DOT_PROCESS: int = 200

# (formato, motor, fuente DOT): identifica un render; dos llamadas con la misma clave producen los mismos bytes
_PipeKey = tuple[str, str, str]


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
        db_manager: RelationshipGraphSource,
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
        render_workers: int | None = None,
    ):
        """Configura el generador.

        Args:
            render_workers: Procesos ``dot`` simultáneos de :meth:`prefetch` (por defecto, los núcleos hasta 8;
                con ``1`` los lotes se renderizan de uno en uno).
        """
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
        self.render_workers: int = (
            max(1, int(render_workers))
            if render_workers is not None
            else min(_MAX_DEFAULT_RENDER_WORKERS, os.cpu_count() or 1)
        )
        # Renders lanzados por prefetch(); los recoge la llamada real con la misma clave
        self._prefetched: dict[_PipeKey, Future[bytes]] = {}
        # Durante prefetch(): los dot que se habrían lanzado, en lugar de lanzarlos
        self._captured: dict[_PipeKey, Any] | None = None

        # Sin cachés locales: columnas, PK y UNIQUE salen del snapshot del manager, que ya está cacheado por schema
        # (una caché por nombre de tabla mezclaría tablas homónimas de schemas distintos, MDC-02).

    def _normalize_column_mode(self, mode: ColumnVisualizationMode | str) -> ColumnVisualizationMode:
        """Normaliza el modo de visualización de columnas."""
        if isinstance(mode, ColumnVisualizationMode):
            return mode

        try:
            return ColumnVisualizationMode(str(mode).strip().lower())
        except ValueError as exc:
            raise ValueError(f"Modo de columnas no soportado: {mode}") from exc

    def _get_table_columns_with_types(self, table_name: str) -> list[tuple[str, str]]:
        """Columnas de la tabla con su tipo declarado ``(nombre, tipo)``, del schema leído por lotes."""
        return [(c.name, c.data_type) for c in self._snapshot({Kind.COLUMNS}).columns(table_name)]

    def _get_primary_keys(self, table_name: str) -> list[str]:
        """Columnas de la clave primaria de la tabla, en minúsculas."""
        primary_key = self._snapshot({Kind.PRIMARY_KEYS}).primary_key(table_name)
        return [column.lower() for column in primary_key.columns] if primary_key else []

    def _get_unique_columns(self, table_name: str) -> list[str]:
        """Columnas con restricción ``UNIQUE`` de un solo campo, en minúsculas.

        Antes se leía la primera posición de cada fila de ``get_unique_constraints`` (el nombre de la restricción en la
        mayoría de motores), así que ninguna columna salía como única y no se detectaban relaciones 1:1.
        """
        uniques = self._snapshot({Kind.UNIQUES}).uniques(table_name)
        return [u.columns[0].lower() for u in uniques if len(u.columns) == 1]

    def _is_primary_key(self, table_name: str, column_name: str) -> bool:
        """Si la columna es (parte de) la clave primaria."""
        return column_name.lower() in self._get_primary_keys(table_name)

    def _is_unique_column(self, table_name: str, column_name: str) -> bool:
        """Si la columna tiene una restricción ``UNIQUE`` propia."""
        return column_name.lower() in self._get_unique_columns(table_name)

    def _determine_cardinality(self, source_col: str, target_col: str, source_table: str, target_table: str) -> str:
        """Determina la cardinalidad de una relación.

        Lógica de detección:
        - Si ambos son PK: M:N (tabla de unión)
        - Si target_col es PK y source_col es UNIQUE: 1:1
        - Si target_col es PK: 1:N
        - En otros casos: N:1

        Returns:
            String con cardinalidad (``"1:N"``, ``"N:1"``, ``"1:1"``, ``"M:N"``).
        """
        try:
            target_is_pk: bool = self._is_primary_key(target_table, target_col)
            source_is_pk: bool = self._is_primary_key(source_table, source_col)
            source_is_uk: bool = self._is_unique_column(source_table, source_col)
        except DatabaseException as e:
            self.logger.warning(f"⚠️ Error determinando cardinalidad: {e}, usando 1:N por defecto")
            return "1:N"
        if source_is_pk and target_is_pk:
            result = "M:N"
        elif target_is_pk and source_is_uk:
            result = "1:1"
        elif target_is_pk:
            result = "1:N"
        else:
            result = "N:1"
        self.logger.debug(f"📊 Cardinalidad {source_table}.{source_col} → {target_table}.{target_col}: {result}")
        return result

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
        """Genera un diagrama independiente por nivel y por sentido (:meth:`pipe_level_graphs_ext` escrito a disco).

        Returns:
            La estructura de :meth:`pipe_level_graphs_ext` con ``"path"`` en lugar de ``"bytes"`` en cada nivel.
        """
        piped: dict[str, Any] = self.pipe_level_graphs_ext(
            table_name=table_name,
            format=format,
            show_columns=show_columns,
            max_depth=max_depth,
            direction=direction,
            document=document,
        )
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        results: dict[str, Any] = {"summary": piped["summary"], "outgoing": [], "incoming": []}
        stem: str = safe_file_stem(table_name)
        for direction_key in ("outgoing", "incoming"):
            for item in piped[direction_key]:
                output_file: Path = output_dir / f"graphviz_ext_{stem}_{direction_key}_level{item['depth']}"
                results[direction_key].append(
                    {
                        "depth": item["depth"],
                        "path": self._write_graph(item["bytes"], output_file, format),
                        "title": item["title"],
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
        pages: list[bytes] = self.pipe_paginated_graph_ext(
            table_name=table_name,
            format=format,
            max_subnodes=max_subnodes,
            show_columns=show_columns,
            max_depth=max_depth,
            direction=direction,
            document=document,
        )
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        stem: str = f"graphviz_ext_{safe_file_stem(table_name)}"
        return [
            self._write_graph(page_bytes, output_dir / (f"{stem}_page{page_num}" if len(pages) > 1 else stem), format)
            for page_num, page_bytes in enumerate(pages, 1)
        ]

    def _build_dot(self, table_name: str, format: str, document: GraphDocument, show_columns: bool) -> Any:
        """El grafo Graphviz de ``document`` listo para renderizar: layout, pie, nodos y aristas."""
        if not GRAPHVIZ_AVAILABLE or graphviz is None:
            raise ImportError(GRAPHVIZ_MISSING_MSG)
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
        return dot

    @staticmethod
    def _write_graph(content: bytes, output_file: Path, format: str) -> Path:
        """Escribe un render en ``<output_file>.<format>`` (el nombre que daba ``dot.render``)."""
        target: Path = Path(f"{Path(output_file).resolve()}.{format}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return target

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

    def clear_cache(self) -> None:
        """Invalida las cachés del grafo (ver la clase base) y los renders precargados por :meth:`prefetch`."""
        super().clear_cache()
        self._prefetched.clear()

    def prefetch(self, render: Callable[[str], object], table_names: Iterable[str]) -> int:
        """Renderiza por lotes y en paralelo lo que ``render(tabla)`` va a pedir después para cada tabla.

        Llama a ``render`` por cada tabla sin lanzar ``dot`` (solo construye los grafos) y renderiza todos los grafos
        resultantes con pocos procesos ``dot -O`` (uno por lote, ``render_workers`` lotes a la vez): casi todo el coste
        de ``dot`` es arrancar (~0,25 s por proceso frente a ~0,01 s por grafo), así que lanzar un proceso por grafo
        era lo que hacía lenta la documentación con diagramas. Las llamadas reales posteriores con los mismos argumentos
        recogen el resultado en lugar de lanzar ``dot``; un grafo que falla en el lote se renderiza aparte, y su
        llamada real recibe la misma excepción que habría recibido sin precarga. Cada llamada sustituye lo precargado
        por la anterior.

        Args:
            render: La misma llamada que hará el renderer, p. ej.
                ``lambda t: gen.pipe_level_graphs_ext(table_name=t, format="svg")``.
            table_names: Tablas a precargar.

        Returns:
            Número de grafos renderizados.

        Example:
            >>> gen.prefetch(lambda t: gen.pipe_single_table_graph_ext(table_name=t, format="png"), ["a", "b"])
            >>> png = gen.pipe_single_table_graph_ext(table_name="a", format="png")  # ya renderizado
        """
        self._prefetched.clear()
        self._captured = {}
        try:
            for table_name in table_names:
                try:
                    render(table_name)
                except (DatabaseException, OSError, RuntimeError, ValueError, KeyError) as error:
                    # La llamada real repetirá el error y lo tratará como siempre
                    self.logger.debug(f"Precarga de grafo omitida para {table_name}: {error}")
        finally:
            captured, self._captured = self._captured, None
        if not captured:
            return 0

        batches: list[list[tuple[_PipeKey, Any]]] = []
        by_command: dict[tuple[str, str], list[tuple[_PipeKey, Any]]] = {}
        for key, dot in captured.items():
            self._prefetched[key] = Future()
            by_command.setdefault((key[0], key[1]), []).append((key, dot))
        for items in by_command.values():
            parts: int = max(min(self.render_workers, len(items)), -(-len(items) // _MAX_GRAPHS_PER_DOT_PROCESS))
            batches.extend(items[index::parts] for index in range(parts))
        with ThreadPoolExecutor(max_workers=min(self.render_workers, len(batches))) as executor:
            list(executor.map(self._render_batch, batches))
        self.logger.info(
            f"🎨 Precargados {len(captured)} grafos Graphviz en {len(batches)} procesos dot "
            f"({self.render_workers} a la vez)"
        )
        return len(captured)

    def _render_batch(self, items: list[tuple[_PipeKey, Any]]) -> None:
        """Renderiza un lote con un solo ``dot -K<motor> -T<formato> -O`` y resuelve el ``Future`` de cada grafo.

        Los grafos sin salida (error de sintaxis, ``dot`` ausente…) se renderizan uno a uno con ``dot.pipe`` para que su
        ``Future`` guarde el resultado o la excepción exacta de una llamada sin precarga. Ningún ``Future`` del lote queda
        sin resolver, ni con un error inesperado: la llamada real esperaría para siempre en ``prefetched.result()``.
        """
        try:
            if graphviz is None:
                self._fail_pending(items, ImportError(GRAPHVIZ_MISSING_MSG))
                return
            format_ = items[0][0][0]
            rendered = self._render_with_dot(items, graphviz.DOT_BINARY)
            for key, dot in items:
                future: Future[bytes] = self._prefetched[key]
                if key in rendered:
                    future.set_result(rendered[key])
                    continue
                try:
                    future.set_result(dot.pipe(format=format_))
                except Exception as error:  # noqa: BLE001 - se entrega tal cual a la llamada real
                    future.set_exception(error)
        except BaseException as error:
            self._fail_pending(items, error)
            raise

    def _render_with_dot(self, items: list[tuple[_PipeKey, Any]], dot_binary: Any) -> dict[_PipeKey, bytes]:
        """Salida de cada grafo del lote con un solo proceso ``dot``; los que no la tienen no aparecen."""
        format_, engine = items[0][0][0], items[0][0][1]
        rendered: dict[_PipeKey, bytes] = {}
        try:
            with tempfile.TemporaryDirectory(prefix="util_bbdd_dot_") as work_dir:
                names: list[str] = []
                for index, (_, dot) in enumerate(items):
                    name = f"{index}.gv"
                    Path(work_dir, name).write_text(dot.source, encoding=dot.encoding or "utf-8")
                    names.append(name)
                command: list[str] = [str(dot_binary), f"-K{engine}", f"-T{format_}", "-O", *names]
                subprocess.run(command, cwd=work_dir, capture_output=True, check=False)
                for (key, _), name in zip(items, names, strict=True):
                    output = Path(work_dir, f"{name}.{format_}")
                    if output.is_file() and output.stat().st_size > 0:
                        rendered[key] = output.read_bytes()
        except Exception as error:  # noqa: BLE001 - dot ausente o un .gv no representable en su codificación…
            self.logger.debug(f"Lote dot no disponible ({error}); se renderiza grafo a grafo")
        return rendered

    def _fail_pending(self, items: list[tuple[_PipeKey, Any]], error: BaseException) -> None:
        """Resuelve con ``error`` los ``Future`` del lote que aún no tienen resultado."""
        for key, _ in items:
            future: Future[bytes] = self._prefetched[key]
            if not future.done():
                future.set_exception(error)

    def _pipe_graph_bytes(self, dot: Any, format: str, table_name: str) -> bytes:
        """Renderiza el grafo en memoria y devuelve los bytes sin escribir a disco.

        Si :meth:`prefetch` ya lanzó este mismo render (mismo formato y fuente DOT), devuelve su resultado.

        Args:
            dot: Grafo Graphviz configurado y con nodos/aristas ya añadidos
            format: Formato de salida (png, svg, pdf, etc.)
            table_name: Tabla principal (solo para logging)

        Returns:
            bytes: Contenido del gráfico renderizado en el formato indicado (vacío durante la captura de prefetch)

        Raises:
            OSError: Si el ejecutable dot no está disponible o falla durante el pipe
            RuntimeError: Si Graphviz produce una salida vacía o inválida

        Example:
            >>> png_bytes = self._pipe_graph_bytes(dot, "png", "orders")
            >>> len(png_bytes) > 0
            True
        """
        key: _PipeKey = (format, str(dot.engine), dot.source)
        if self._captured is not None:
            self._captured[key] = dot
            return b""
        prefetched: Future[bytes] | None = self._prefetched.get(key)
        if prefetched is not None:
            return prefetched.result()
        self.logger.debug(f"🎨 Pipe Graphviz para {table_name}: formato={format}")
        result: bytes = dot.pipe(format=format)
        self.logger.debug(f"🎨 Pipe Graphviz completado para {table_name} ({len(result)} bytes)")
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
        return self._pipe_graph_internal_ext(
            table_name=table_name, format=format, document=document, show_columns=include_columns
        )

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
        try:
            dot = self._build_dot(table_name=table_name, format=format, document=document, show_columns=show_columns)
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
            Path del archivo generado (``<output_file>.<format>``)
        """
        content: bytes = self.pipe_single_table_graph_ext(
            table_name=table_name,
            format=format,
            show_columns=show_columns,
            max_depth=max_depth,
            direction=direction,
            document=document,
        )
        return self._write_graph(content, output_file, format)
