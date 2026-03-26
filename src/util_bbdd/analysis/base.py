"""Núcleo de análisis de grafos de relaciones entre tablas."""

from __future__ import annotations

import logging
import math

from dataclasses import dataclass, field
from enum import Enum
from logging import Logger
from typing import Any

from ..managers import SyncDatabaseManager


class LevelDirection(str, Enum):
    """Dirección de recorrido del grafo."""

    INCOMING = "incoming"
    OUTGOING = "outgoing"
    BOTH = "both"


class ColumnVisualizationMode(str, Enum):
    """Política de columnas visibles en nodos."""

    COMPACT = "compact"
    RELATIONS = "relations"
    ALL = "all"


class TableVisualType(str, Enum):
    """Tipología visual aproximada de una tabla para renderers."""

    ENTITY = "entity"
    ASSOCIATION = "association"
    HIERARCHY = "hierarchy"


@dataclass(frozen=True)
class TableRelation:
    """Representa una relación entre tablas."""

    source_table: str
    target_table: str
    constraint_name: str
    source_column: str
    target_column: str
    relation_type: str = "FK"


@dataclass(frozen=True)
class ColumnDisplayConfig:
    """Configuración de visualización de columnas."""

    mode: ColumnVisualizationMode = ColumnVisualizationMode.RELATIONS
    max_items: int = 8
    show_data_types: bool = False


@dataclass(frozen=True)
class CardinalityEndMarker:
    """Marcadores de cardinalidad por extremo."""

    source_marker: str
    target_marker: str
    label: str


@dataclass
class GraphNode:
    """Nodo enriquecido del grafo."""

    table_name: str
    is_root: bool = False
    outgoing_depth: int | None = None
    incoming_depth: int | None = None
    visual_type: TableVisualType = TableVisualType.ENTITY


@dataclass(frozen=True)
class GraphEdge:
    """Arista enriquecida del grafo."""

    relation: TableRelation
    depth: int
    direction: LevelDirection


@dataclass
class GraphLevel:
    """Agrupación de aristas por nivel y dirección."""

    depth: int
    direction: LevelDirection
    edges: list[GraphEdge] = field(default_factory=list)
    tables: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class HiddenLevelsSummary:
    """Niveles ocultos por superar la profundidad visible."""

    incoming_hidden_levels: int = 0
    outgoing_hidden_levels: int = 0


@dataclass
class GraphDocument:
    """Modelo agnóstico de formato para renderers."""

    root_table: str
    nodes: dict[str, GraphNode]
    levels: list[GraphLevel]
    edges: list[GraphEdge]
    relations: list[TableRelation]
    tables: set[str]
    max_depth: int
    direction: LevelDirection
    hidden_levels: HiddenLevelsSummary
    total_incoming_levels: int
    total_outgoing_levels: int


class DatabaseRelationshipGraphBase:
    """Clase base para generar grafos de relaciones de bases de datos."""

    def __init__(self, db_manager: SyncDatabaseManager):
        self.db_manager: SyncDatabaseManager = db_manager
        self.relations: list[TableRelation] = []
        self.tables: set[str] = set()
        self.logger: Logger = logging.getLogger(__name__)
        self._parent_relations_index_by_context: dict[str, dict[str, list[TableRelation]]] = {}
        self._graph_document_cache_by_context: dict[tuple[str, str, int, str], GraphDocument] = {}
        self._table_visual_type_cache_by_context: dict[tuple[str, str], TableVisualType] = {}

    def analyze_table_relations(self, table_name: str) -> list[TableRelation]:
        """Devuelve relaciones visibles del primer nivel."""
        document = self.build_graph_document(table_name=table_name, max_depth=1, direction=LevelDirection.BOTH)
        return list(document.relations)

    def build_graph_document(
        self,
        table_name: str,
        max_depth: int = 1,
        direction: LevelDirection | str = LevelDirection.BOTH,
    ) -> GraphDocument:
        """Construye un documento de grafo multinivel agnóstico al formato."""
        normalized_depth = max(1, int(max_depth))
        normalized_direction = self._normalize_direction(direction)
        context = self._get_relationship_context()
        cache_key = (context, table_name, normalized_depth, normalized_direction.value)
        cached = self._graph_document_cache_by_context.get(cache_key)
        if cached is not None:
            self.relations = list(cached.relations)
            self.tables = set(cached.tables)
            return cached

        nodes: dict[str, GraphNode] = {table_name: GraphNode(table_name=table_name, is_root=True)}
        levels: list[GraphLevel] = []

        if normalized_direction in {LevelDirection.OUTGOING, LevelDirection.BOTH}:
            levels.extend(
                self._traverse_levels(
                    root_table=table_name,
                    max_depth=normalized_depth,
                    direction=LevelDirection.OUTGOING,
                    nodes=nodes,
                    seen_relations=set(),
                )
            )

        if normalized_direction in {LevelDirection.INCOMING, LevelDirection.BOTH}:
            levels.extend(
                self._traverse_levels(
                    root_table=table_name,
                    max_depth=normalized_depth,
                    direction=LevelDirection.INCOMING,
                    nodes=nodes,
                    seen_relations=set(),
                )
            )

        unique_edges_by_relation: dict[tuple[str, str, str, str, str], GraphEdge] = {}
        for level in levels:
            for edge in level.edges:
                unique_edges_by_relation.setdefault(self._build_relation_key(edge.relation), edge)

        edges: list[GraphEdge] = list(unique_edges_by_relation.values())
        relations: list[TableRelation] = [edge.relation for edge in edges]
        tables: set[str] = {table_name}
        for relation in relations:
            tables.add(relation.source_table)
            tables.add(relation.target_table)

        total_outgoing_levels = (
            self._compute_total_levels(table_name, LevelDirection.OUTGOING)
            if normalized_direction in {LevelDirection.OUTGOING, LevelDirection.BOTH}
            else 0
        )
        total_incoming_levels = (
            self._compute_total_levels(table_name, LevelDirection.INCOMING)
            if normalized_direction in {LevelDirection.INCOMING, LevelDirection.BOTH}
            else 0
        )
        visible_outgoing_levels = max(
            (level.depth for level in levels if level.direction == LevelDirection.OUTGOING),
            default=0,
        )
        visible_incoming_levels = max(
            (level.depth for level in levels if level.direction == LevelDirection.INCOMING),
            default=0,
        )
        self._assign_node_visual_types(context=context, nodes=nodes)

        document = GraphDocument(
            root_table=table_name,
            nodes=nodes,
            levels=levels,
            edges=edges,
            relations=relations,
            tables=tables,
            max_depth=normalized_depth,
            direction=normalized_direction,
            hidden_levels=HiddenLevelsSummary(
                incoming_hidden_levels=max(0, total_incoming_levels - visible_incoming_levels),
                outgoing_hidden_levels=max(0, total_outgoing_levels - visible_outgoing_levels),
            ),
            total_incoming_levels=total_incoming_levels,
            total_outgoing_levels=total_outgoing_levels,
        )

        self.relations = relations
        self.tables = tables
        self._graph_document_cache_by_context[cache_key] = document
        self.logger.info(
            "Análisis multinivel completado para %s: %s relaciones, %s tablas, profundidad visible=%s",
            table_name,
            len(relations),
            len(tables),
            normalized_depth,
        )
        return document

    def _traverse_levels(
        self,
        root_table: str,
        max_depth: int,
        direction: LevelDirection,
        nodes: dict[str, GraphNode],
        seen_relations: set[tuple[str, str, str, str, str]],
    ) -> list[GraphLevel]:
        """Recorre el grafo por niveles para una dirección concreta."""
        levels: list[GraphLevel] = []
        frontier: set[str] = {root_table}
        visited_tables: set[str] = {root_table}

        for depth in range(1, max_depth + 1):
            if not frontier:
                break

            next_frontier, level_edges, level_tables = self._build_level_data(
                frontier=frontier,
                visited_tables=visited_tables,
                seen_relations=seen_relations,
                nodes=nodes,
                depth=depth,
                direction=direction,
            )

            if not level_edges:
                break

            levels.append(GraphLevel(depth=depth, direction=direction, edges=level_edges, tables=level_tables))
            frontier = next_frontier

        return levels

    def _build_level_data(
        self,
        frontier: set[str],
        visited_tables: set[str],
        seen_relations: set[tuple[str, str, str, str, str]],
        nodes: dict[str, GraphNode],
        depth: int,
        direction: LevelDirection,
    ) -> tuple[set[str], list[GraphEdge], set[str]]:
        """Construye la información de un nivel concreto del recorrido."""
        next_frontier: set[str] = set()
        level_edges: list[GraphEdge] = []
        level_tables: set[str] = set()

        for current_table in frontier:
            for relation in self._get_direct_relations(current_table, direction):
                relation_key = self._build_relation_key(relation)
                if relation_key in seen_relations:
                    continue

                seen_relations.add(relation_key)
                edge = GraphEdge(relation=relation, depth=depth, direction=direction)
                level_edges.append(edge)
                level_tables.update({relation.source_table, relation.target_table})

                next_table = self._get_next_table_for_direction(relation, direction)
                self._register_node_depth(nodes, next_table, depth, direction)
                if next_table not in visited_tables:
                    visited_tables.add(next_table)
                    next_frontier.add(next_table)

        return next_frontier, level_edges, level_tables

    def _register_node_depth(
        self,
        nodes: dict[str, GraphNode],
        table_name: str,
        depth: int,
        direction: LevelDirection,
    ) -> None:
        """Registra la profundidad mínima visible de un nodo."""
        node = nodes.get(table_name)
        if node is None:
            node = GraphNode(table_name=table_name)
            nodes[table_name] = node

        if direction == LevelDirection.OUTGOING:
            if node.outgoing_depth is None or depth < node.outgoing_depth:
                node.outgoing_depth = depth
            return

        if node.incoming_depth is None or depth < node.incoming_depth:
            node.incoming_depth = depth

    def _assign_node_visual_types(self, context: str, nodes: dict[str, GraphNode]) -> None:
        """Calcula y asigna la tipología visual de cada nodo del documento."""
        for node in nodes.values():
            node.visual_type = self._classify_table_visual_type(context=context, table_name=node.table_name)

    def _classify_table_visual_type(self, context: str, table_name: str) -> TableVisualType:
        """Clasifica una tabla para representación visual usando heurísticas mínimas y cacheadas."""
        cache_key: tuple[str, str] = (context, table_name)
        cached: TableVisualType | None = self._table_visual_type_cache_by_context.get(cache_key)
        if cached is not None:
            return cached

        foreign_keys: list[tuple] = list(self.db_manager.get_foreign_keys(table_name))
        if any(self._extract_target_table(fk) == table_name for fk in foreign_keys):
            self._table_visual_type_cache_by_context[cache_key] = TableVisualType.HIERARCHY
            return TableVisualType.HIERARCHY

        foreign_key_columns: set[str] = {self._extract_source_column(fk).lower() for fk in foreign_keys}
        primary_key_columns: set[str] = set(self._get_primary_key_column_names(table_name))
        column_names: list[str] = self._get_table_column_names(table_name)
        business_columns_count: int = max(0, len(column_names) - len(foreign_key_columns))
        has_composite_fk_primary_key: bool = bool(primary_key_columns) and primary_key_columns.issubset(
            foreign_key_columns
        )

        if len(foreign_keys) >= 2 and (business_columns_count <= 1 or has_composite_fk_primary_key):
            self._table_visual_type_cache_by_context[cache_key] = TableVisualType.ASSOCIATION
            return TableVisualType.ASSOCIATION

        self._table_visual_type_cache_by_context[cache_key] = TableVisualType.ENTITY
        return TableVisualType.ENTITY

    def _get_table_column_names(self, table_name: str) -> list[str]:
        """Obtiene nombres de columnas normalizados para heurísticas visuales."""
        try:
            columns: list[Any] = list(self.db_manager.get_columns(table_name))
        except Exception:
            return []

        result: list[str] = []
        for column in columns:
            if isinstance(column, (tuple, list)) and column:
                result.append(str(column[0]).strip().lower())
                continue
            result.append(str(column).strip().lower())
        return [name for name in result if name]

    def _get_primary_key_column_names(self, table_name: str) -> list[str]:
        """Obtiene nombres de PK normalizados para heurísticas visuales."""
        try:
            primary_keys: list[Any] = list(self.db_manager.get_primary_keys(table_name))
        except Exception:
            return []

        result: list[str] = []
        for primary_key in primary_keys:
            if isinstance(primary_key, (tuple, list)) and primary_key:
                result.append(str(primary_key[0]).strip().lower())
                continue
            result.append(str(primary_key).strip().lower())
        return [name for name in result if name]

    def _compute_total_levels(self, table_name: str, direction: LevelDirection) -> int:
        """Calcula los niveles totales alcanzables en una dirección."""
        frontier: set[str] = {table_name}
        visited_tables: set[str] = {table_name}
        seen_relations: set[tuple[str, str, str, str, str]] = set()
        total_levels = 0

        while frontier:
            next_frontier, level_has_edges = self._collect_next_level_tables(
                frontier=frontier,
                visited_tables=visited_tables,
                seen_relations=seen_relations,
                direction=direction,
            )

            if not level_has_edges:
                break

            total_levels += 1
            frontier = next_frontier

        return total_levels

    def _collect_next_level_tables(
        self,
        frontier: set[str],
        visited_tables: set[str],
        seen_relations: set[tuple[str, str, str, str, str]],
        direction: LevelDirection,
    ) -> tuple[set[str], bool]:
        """Recorre el frontier actual y devuelve la siguiente frontera alcanzable."""
        next_frontier: set[str] = set()
        level_has_edges = False

        for current_table in frontier:
            for relation in self._get_direct_relations(current_table, direction):
                relation_key: tuple[str, str, str, str, str] = self._build_relation_key(relation)
                if relation_key in seen_relations:
                    continue

                seen_relations.add(relation_key)
                level_has_edges = True
                next_table: str = self._get_next_table_for_direction(relation, direction)
                if next_table not in visited_tables:
                    visited_tables.add(next_table)
                    next_frontier.add(next_table)

        return next_frontier, level_has_edges

    def _get_next_table_for_direction(self, relation: TableRelation, direction: LevelDirection) -> str:
        """Devuelve la tabla vecina a explorar según la dirección del recorrido."""
        if direction == LevelDirection.OUTGOING:
            return relation.target_table
        return relation.source_table

    def _get_direct_relations(self, table_name: str, direction: LevelDirection) -> list[TableRelation]:
        """Obtiene relaciones directas según la dirección."""
        if direction == LevelDirection.OUTGOING:
            return self._find_child_relations(table_name)
        if direction == LevelDirection.INCOMING:
            return self._find_parent_relations(table_name)
        return self._find_child_relations(table_name) + self._find_parent_relations(table_name)

    def _find_child_relations(self, table_name: str) -> list[TableRelation]:
        """Obtiene relaciones salientes de una tabla."""
        foreign_keys = self.db_manager.get_foreign_keys(table_name)
        self.logger.debug("Encontradas %s claves foráneas salientes en %s", len(foreign_keys), table_name)
        return [self._build_relation_from_fk(table_name, fk) for fk in foreign_keys]

    def _find_parent_relations(self, table_name: str) -> list[TableRelation]:
        """
        Encuentra relaciones donde la tabla dada es el target (tabla padre)
        Esto requiere consultar todas las tablas para encontrar FKs que apunten a nuestra tabla
        """
        self.logger.debug(f"Buscando relaciones entrantes (padres) para: {table_name}")
        context: str = self._get_relationship_context()
        index: dict[str, list[TableRelation]] | None = self._parent_relations_index_by_context.get(context)
        if index is None:
            index = self._build_parent_relations_index(context)
            self._parent_relations_index_by_context[context] = index

        return list(index.get(table_name, []))

    def _build_relation_from_fk(self, current_table: str, fk: tuple) -> TableRelation:
        """Normaliza una FK en el modelo TableRelation."""
        if self.db_manager.db_type == "mariadb":
            return TableRelation(
                source_table=current_table,
                target_table=fk[3],
                constraint_name=fk[0],
                source_column=fk[2],
                target_column=fk[4],
                relation_type="FK",
            )

        return TableRelation(
            source_table=current_table,
            target_table=fk[2],
            constraint_name=fk[0],
            source_column=fk[1],
            target_column=fk[3],
            relation_type="FK",
        )

    def _get_relationship_context(self) -> str:
        """Obtiene una clave de contexto estable para cachear relaciones entrantes."""
        get_context = getattr(self.db_manager, "get_query_context_database", None)
        if callable(get_context):
            result = get_context()
            if isinstance(result, str) and result.strip():
                return result

        for attr_name in ("database", "schema", "owner"):
            value = getattr(self.db_manager, attr_name, None)
            if isinstance(value, str) and value.strip():
                return value

        return f"{self.db_manager.db_type}:default"

    def _build_parent_relations_index(self, context: str) -> dict[str, list[TableRelation]]:
        """Construye un índice target_table -> relaciones entrantes para el contexto actual."""
        self.logger.info(f"🧭 Construyendo índice de relaciones entrantes para contexto: {context}")
        parent_relations_by_target: dict[str, list[TableRelation]] = {}

        all_tables = self.db_manager.get_tables()
        for table_info in all_tables:
            current_table = table_info[0]
            foreign_keys = self.db_manager.get_foreign_keys(current_table)
            for fk in foreign_keys:
                relation = self._build_relation_from_fk(current_table, fk)
                target_table: str = relation.target_table
                parent_relations_by_target.setdefault(target_table, []).append(relation)

        self.logger.debug(
            f"🧭 Índice de relaciones entrantes construido para {context}: "
            f"{len(parent_relations_by_target)} tablas destino"
        )
        return parent_relations_by_target

    def _extract_target_table(self, fk_data: tuple) -> str:
        """Extrae el nombre de la tabla target de los datos de FK según el tipo de BD"""
        if self.db_manager.db_type == "mariadb":
            return fk_data[3]
        return fk_data[2]

    def _extract_source_column(self, fk_data: tuple) -> str:
        """Extrae la columna local de la FK según el tipo de BD."""
        if self.db_manager.db_type == "mariadb":
            return str(fk_data[2])
        return str(fk_data[1])

    def _build_relation_key(self, relation: TableRelation) -> tuple[str, str, str, str, str]:
        """Clave estable para deduplicar relaciones."""
        return (
            relation.source_table,
            relation.target_table,
            relation.constraint_name,
            relation.source_column,
            relation.target_column,
        )

    def _normalize_direction(self, direction: LevelDirection | str) -> LevelDirection:
        """Normaliza la dirección de recorrido."""
        if isinstance(direction, LevelDirection):
            return direction

        try:
            return LevelDirection(str(direction).strip().lower())
        except ValueError as exc:
            raise ValueError(f"Dirección de grafo no soportada: {direction}") from exc

    def _split_relations_for_visualization(
        self, relations: list[TableRelation], max_subnodes: int = 10
    ) -> list[list[TableRelation]]:
        """
        Divide las relaciones en múltiples grupos para visualización pagada

        Algoritmo:
        - 1-10 nodos: 1 imagen
        - 11-20 nodos: 2 imágenes (mayor en primera)
        - 21-30 nodos: 3 imágenes (mayores en primeras)
        - 31-40 nodos: 4 imágenes (mayores en primeras)

        Args:
            relations: Lista de relaciones a dividir
            max_subnodes: Máximo de sub-nodos por imagen (default 10)

        Returns:
            Lista de listas de relaciones, una por cada imagen
        """
        total_relations: int = len(relations)
        self.logger.debug(f"Dividiendo {total_relations} relaciones para visualización (máx {max_subnodes} por página)")

        num_images: int = math.ceil(total_relations / max_subnodes)

        if num_images <= 1:
            self.logger.debug("Relaciones caben en una sola imagen")
            return [relations]

        size_per_image: int = math.ceil(total_relations / num_images)
        self.logger.debug(f"Se crearán {num_images} imágenes con {size_per_image} relaciones por imagen")

        split_relations: list[list[TableRelation]] = []
        for i in range(num_images):
            start_idx: int = i * size_per_image
            end_idx: int = min(start_idx + size_per_image, total_relations)
            split_relations.append(relations[start_idx:end_idx])

        return split_relations

    def generate_relationship_report(self, table_name: str) -> dict[str, Any]:
        """
        Genera un reporte detallado de las relaciones de una tabla

        Args:
            table_name: Tabla a analizar

        Returns:
            Diccionario con información detallada de relaciones
        """
        self.logger.info(f"Generando reporte de relaciones para tabla: {table_name}")
        document = self.build_graph_document(table_name=table_name, max_depth=1, direction=LevelDirection.BOTH)
        relations: list[TableRelation] = list(document.relations)

        outgoing_relations: list[TableRelation] = [r for r in relations if r.source_table == table_name]
        incoming_relations: list[TableRelation] = [r for r in relations if r.target_table == table_name]

        self.logger.debug(
            f"Relaciones salientes: {len(outgoing_relations)}, Relaciones entrantes: {len(incoming_relations)}"
        )

        report: dict[str, Any] = {
            "table_name": table_name,
            "total_relations": len(relations),
            "outgoing_relations": {
                "count": len(outgoing_relations),
                "details": [
                    {
                        "target_table": r.target_table,
                        "constraint_name": r.constraint_name,
                        "source_column": r.source_column,
                        "target_column": r.target_column,
                    }
                    for r in outgoing_relations
                ],
            },
            "incoming_relations": {
                "count": len(incoming_relations),
                "details": [
                    {
                        "source_table": r.source_table,
                        "constraint_name": r.constraint_name,
                        "source_column": r.source_column,
                        "target_column": r.target_column,
                    }
                    for r in incoming_relations
                ],
            },
            "related_tables": list(document.tables - {table_name}),
            "database_type": self.db_manager.db_type,
            "graph_depth": 1,
            "total_outgoing_levels": document.total_outgoing_levels,
            "total_incoming_levels": document.total_incoming_levels,
        }

        self.logger.info(f"Reporte completado para {table_name}: {len(relations)} relaciones totales")
        return report


__all__: list[str] = [
    "CardinalityEndMarker",
    "ColumnDisplayConfig",
    "ColumnVisualizationMode",
    "DatabaseRelationshipGraphBase",
    "GraphDocument",
    "GraphEdge",
    "GraphLevel",
    "GraphNode",
    "HiddenLevelsSummary",
    "LevelDirection",
    "TableRelation",
]
