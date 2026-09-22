"""Renderer Matplotlib alineado con el nuevo modelo multinivel."""

from __future__ import annotations

import logging
import math

from logging import Logger
from pathlib import Path
from typing import Any

from matplotlib.axes import Axes

from .base import DatabaseRelationshipGraphBase, GraphDocument, LevelDirection, TableRelation
from .contracts import RelationshipGraphSource

mpatches: Any | None = None
plt: Any | None = None
nx: Any | None = None
Line2DFactory: Any | None = None

try:
    import matplotlib.patches as _mpatches
    import matplotlib.pyplot as _plt
    import networkx as _nx

    from matplotlib.lines import Line2D as _Line2D

    mpatches = _mpatches
    plt = _plt
    nx = _nx
    Line2DFactory = _Line2D

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
MATPLOTLIB_NETWORKX_ERROR = "Matplotlib/NetworkX no disponible. Instale: pip install matplotlib networkx"


class MatplotlibRelationshipGraph(DatabaseRelationshipGraphBase):
    """Generador de grafos usando Matplotlib con layout radial"""

    def __init__(
        self,
        db_manager: RelationshipGraphSource,
        max_depth: int = 1,
        direction: LevelDirection | str = LevelDirection.BOTH,
    ):
        super().__init__(db_manager)
        self.logger: Logger = logging.getLogger(__name__)
        self.max_depth: int = max(1, int(max_depth))
        self.direction: LevelDirection = self._normalize_direction(direction)

        if not MATPLOTLIB_AVAILABLE or plt is None or nx is None:
            raise ImportError(MATPLOTLIB_NETWORKX_ERROR)

    def _create_radial_layout(self, graph: Any, central_node: str) -> dict[str, tuple]:
        """
        Crea un layout radial donde el nodo central está en el centro
        y los demás nodos se distribuyen alrededor en círculo

        Args:
            graph: Grafo de NetworkX
            central_node: Nombre del nodo principal

        Returns:
            Diccionario con posiciones {nodo: (x, y)}
        """
        self.logger.debug(f"Creando layout radial para {central_node}")

        pos: dict[str, tuple] = {}
        nodes = list(graph.nodes())

        # El nodo principal en el centro
        pos[central_node] = (0, 0)

        # Nodos secundarios en círculo alrededor
        secondary_nodes = [n for n in nodes if n != central_node]
        num_secondary: int = len(secondary_nodes)

        if num_secondary > 0:
            # Radio del círculo - aumentado para aprovechar más espacio
            radius = 3.0
            # Ángulo entre nodos
            angle_step: float = 2 * math.pi / num_secondary
            self.logger.debug(f"Distribuyendo {num_secondary} nodos en círculo con radio {radius}")

            for i, node in enumerate(secondary_nodes):
                angle: float = i * angle_step
                x: float = radius * math.cos(angle)
                y: float = radius * math.sin(angle)
                pos[node] = (x, y)

        return pos

    def _add_legend(self) -> None:
        """Agrega una leyenda al grafo de matplotlib"""
        self.logger.debug("Agregando leyenda al gráfico")
        if not MATPLOTLIB_AVAILABLE or mpatches is None or plt is None or Line2DFactory is None:
            return
        legend_elements = [
            mpatches.Patch(color="lightcoral", label="Tabla Principal"),
            mpatches.Patch(color="lightblue", label="Tablas Relacionadas"),
            Line2DFactory([0], [0], color="gray", linewidth=2, label="Relación FK"),
        ]
        plt.legend(handles=legend_elements, loc="upper right", bbox_to_anchor=(1, 1))

    def generate_matplotlib_graph_paginated(
        self,
        table_name: str,
        output_dir: Path,
        format: str = "png",
        max_subnodes: int = 10,
        max_depth: int | None = None,
        direction: LevelDirection | str | None = None,
    ) -> list[Path]:
        """
        Genera grafos Matplotlib dividiendo en múltiples imágenes si es necesario

        Args:
            table_name: Tabla central del grafo
            output_dir: Directorio de salida para los archivos
            format: Formato de salida (png, svg, pdf, etc.)
            max_subnodes: Máximo de sub-nodos por imagen

        Returns:
            Lista de Paths de archivos generados
        """
        self.logger.info(
            f"Iniciando generación paginada de Matplotlib para {table_name} (max {max_subnodes} nodos por página)"
        )
        effective_depth = self.max_depth if max_depth is None else max(1, int(max_depth))
        effective_direction = self.direction if direction is None else self._normalize_direction(direction)
        document = self.build_graph_document(
            table_name=table_name,
            max_depth=effective_depth,
            direction=effective_direction,
        )
        relations: list[TableRelation] = list(document.relations)
        split_relations: list[list[TableRelation]] = self._split_relations_for_visualization(relations, max_subnodes)
        self.logger.debug(f"Tabla {table_name} dividida en {len(split_relations)} página(s)")

        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        generated_files: list[Path] = []

        for page_num, page_relations in enumerate(split_relations, 1):
            # Crear nombre de archivo descriptivo con matplotlib y nombre de tabla
            if len(split_relations) > 1:
                # Múltiples páginas: matplotlib_tablename_page1.png
                file_name: str = f"matplotlib_{table_name}_page{page_num}"
            else:
                # Una sola página: matplotlib_tablename.png
                file_name = f"matplotlib_{table_name}"

            output_path: Path = output_dir / file_name

            # Generar gráfico para esta página
            page_document = self._build_subset_document(document, page_relations)
            generated_file: Path = self._generate_matplotlib_graph_internal(
                table_name, output_path, format, page_document
            )
            generated_files.append(generated_file)

        return generated_files

    def _generate_matplotlib_graph_internal(
        self, table_name: str, output_file: Path, format: str, document: GraphDocument
    ) -> Path:
        """
        Genera un gráfico Matplotlib interno con relaciones específicas

        Args:
            table_name: Tabla central
            output_file: Ruta de salida
            format: Formato
            relations: Relaciones a incluir en el gráfico

        Returns:
            Path del archivo generado
        """
        if not MATPLOTLIB_AVAILABLE or plt is None or nx is None:
            raise ImportError(MATPLOTLIB_NETWORKX_ERROR)

        try:
            output_file = Path(output_file).resolve()
            output_file.parent.mkdir(parents=True, exist_ok=True)

            G: Any = nx.DiGraph()

            for table in document.tables:
                G.add_node(table, is_main=(table == table_name))

            for edge in document.edges:
                relation = edge.relation
                G.add_edge(
                    relation.source_table,
                    relation.target_table,
                    label=f"{relation.source_column} → {relation.target_column} (L{edge.depth})",
                    constraint=relation.constraint_name,
                    edge_direction=edge.direction.value,
                )

            plt.figure(figsize=(20, 16))
            # Usar layout radial con nodo principal centrado
            pos = self._create_radial_layout(G, table_name)

            # Importar Patch para dibujar rectángulos personalizados
            from matplotlib.patches import FancyBboxPatch

            ax: Axes = plt.gca()

            for table, (x, y) in pos.items():
                # Calcular dimensiones del rectángulo basadas en la longitud del nombre
                # Muy compacto, ajustado al tamaño del texto
                width: float = len(table) * 0.035 + 0.05  # Escala más pequeña
                height = 0.09  # Altura más pequeña

                # Ajustar para tabla principal
                if table == table_name:
                    width += 0.08
                    height += 0.01
                    color = "lightcoral"
                else:
                    color = "lightblue"

                # Dibujar rectángulo redondeado
                bbox = FancyBboxPatch(
                    (x - width / 2, y - height / 2),
                    width,
                    height,
                    boxstyle="round,pad=0.01",
                    facecolor=color,
                    edgecolor="black",
                    linewidth=2 if table == table_name else 1,
                    alpha=0.8,
                    zorder=2,
                )
                ax.add_patch(bbox)

            nx.draw_networkx_edges(
                G,
                pos,
                alpha=0.6,
                edge_color=[
                    "#1D70B8" if data.get("edge_direction") == LevelDirection.OUTGOING.value else "#A61C00"
                    for _, _, data in G.edges(data=True)
                ],
                arrows=True,
                arrowsize=20,
                arrowstyle="->",
                connectionstyle="arc3,rad=0.1",
            )
            nx.draw_networkx_labels(G, pos, font_size=10, font_family="Arial", font_weight="bold")

            edge_labels = nx.get_edge_attributes(G, "label")
            nx.draw_networkx_edge_labels(G, pos, edge_labels, font_size=8, font_family="Arial", alpha=0.7)

            plt.title(
                (
                    f"Relaciones multinivel - Tabla: {table_name}\n"
                    f"Profundidad visible={document.max_depth} | "
                    f"Salida={document.total_outgoing_levels} | Entrada={document.total_incoming_levels}"
                ),
                fontsize=16,
                fontweight="bold",
                pad=20,
            )
            plt.axis("off")

            self._add_legend()

            output_path: Path = output_file.with_suffix(f".{format}")
            if not output_path.is_absolute():
                output_path = output_path.resolve()

            plt.tight_layout()
            plt.savefig(str(output_path), dpi=300, bbox_inches="tight")
            plt.close()

            if output_path.exists():
                self.logger.info(f"Gráfico Matplotlib generado exitosamente para {table_name}")
                return output_path
            else:
                raise FileNotFoundError(f"Archivo no encontrado: {output_path}")
        except (OSError, ValueError, RuntimeError) as e:
            self.logger.error(
                f"Error al generar gráfico Matplotlib para tabla {table_name}: {str(e)}",
                exc_info=True,
            )
            plt.close()
            raise

    def generate_all_tables_graphs(
        self,
        output_dir: Path | None = None,
        format: str = "png",
        skip_tables_without_relations: bool = True,
        max_subnodes: int = 10,
        max_depth: int | None = None,
        direction: LevelDirection | str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Genera grafos Matplotlib para todas las tablas de la base de datos

        Args:
            output_dir: Directorio de salida (default: ./grafos_matplotlib)
            format: Formato de salida (png, svg, pdf, etc.)
            skip_tables_without_relations: Si True, omite tablas sin relaciones
            max_subnodes: Máximo de sub-nodos por imagen

        Returns:
            Diccionario con los resultados {tabla: {status, files, error}}
        """
        output_dir = self._resolve_matplotlib_output_dir(output_dir)
        table_names = self._get_all_table_names()

        self.logger.info(f"Iniciando generación de grafos Matplotlib para {len(table_names)} tablas")
        self.logger.info(f"Directorio de salida: {output_dir}")
        self.logger.info(f"Formato: {format}, max_subnodes: {max_subnodes}")

        def _generate_for_table(table_name: str) -> list[Path]:
            return self.generate_matplotlib_graph_paginated(
                table_name=table_name,
                output_dir=output_dir,
                format=format,
                max_subnodes=max_subnodes,
                max_depth=max_depth,
                direction=direction,
            )

        return self._generate_all_tables_batch(
            table_names=table_names,
            skip_tables_without_relations=skip_tables_without_relations,
            max_depth=max_depth,
            direction=direction,
            generate_for_table=_generate_for_table,
            error_prefix="Error generando gráfico para tabla",
        )

    def _resolve_matplotlib_output_dir(self, output_dir: Path | None) -> Path:
        """Normaliza y crea el directorio de salida para grafos Matplotlib."""
        return self._resolve_output_dir(output_dir=output_dir, default_dir="./grafos_matplotlib")
