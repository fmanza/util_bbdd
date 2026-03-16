"""
Implementación de generación de grafos usando Matplotlib y NetworkX
"""

import logging
import math

from logging import Logger
from pathlib import Path
from typing import Any

from matplotlib.axes import Axes

try:
    import matplotlib.patches as mpatches
    import matplotlib.pyplot as plt
    import networkx as nx

    from matplotlib.lines import Line2D

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    mpatches = None
    plt = None
    Line2D = None
    nx = None
    MATPLOTLIB_AVAILABLE = False


from ..managers import SyncDatabaseManager
from .base import DatabaseRelationshipGraphBase, TableRelation

MATPLOTLIB_NETWORKX_ERROR = "Matplotlib/NetworkX no disponible. Instale: pip install matplotlib networkx"


class MatplotlibRelationshipGraph(DatabaseRelationshipGraphBase):
    """Generador de grafos usando Matplotlib con layout radial"""

    def __init__(self, db_manager: SyncDatabaseManager):
        super().__init__(db_manager)
        self.logger: Logger = logging.getLogger(__name__)

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
        if not MATPLOTLIB_AVAILABLE or mpatches is None or plt is None or Line2D is None:
            return
        legend_elements = [
            mpatches.Patch(color="lightcoral", label="Tabla Principal"),
            mpatches.Patch(color="lightblue", label="Tablas Relacionadas"),
            Line2D([0], [0], color="gray", linewidth=2, label="Relación FK"),
        ]
        plt.legend(handles=legend_elements, loc="upper right", bbox_to_anchor=(1, 1))

    def generate_matplotlib_graph_paginated(
        self, table_name: str, output_dir: Path, format: str = "png", max_subnodes: int = 10
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
        relations: list[TableRelation] = self.analyze_table_relations(table_name)
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
            generated_file: Path = self._generate_matplotlib_graph_internal(
                table_name, output_path, format, page_relations
            )
            generated_files.append(generated_file)

        return generated_files

    def _generate_matplotlib_graph_internal(
        self, table_name: str, output_file: Path, format: str, relations: list[TableRelation]
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

            # Construir set de tablas para este gráfico
            tables_in_page: set[str] = {table_name}
            for relation in relations:
                tables_in_page.add(relation.source_table)
                tables_in_page.add(relation.target_table)

            G = nx.DiGraph()

            for table in tables_in_page:
                G.add_node(table, is_main=(table == table_name))

            for relation in relations:
                G.add_edge(
                    relation.source_table,
                    relation.target_table,
                    label=f"{relation.source_column} → {relation.target_column}",
                    constraint=relation.constraint_name,
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
                edge_color="gray",
                arrows=True,
                arrowsize=20,
                arrowstyle="->",
                connectionstyle="arc3,rad=0.1",
            )
            nx.draw_networkx_labels(G, pos, font_size=10, font_family="Arial", font_weight="bold")

            edge_labels = nx.get_edge_attributes(G, "label")
            nx.draw_networkx_edge_labels(G, pos, edge_labels, font_size=8, font_family="Arial", alpha=0.7)

            plt.title(
                f"Relaciones de Primer Nivel - Tabla: {table_name}",
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
        except Exception as e:
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
        if output_dir is None:
            output_dir = Path("./grafos_matplotlib")

        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        all_tables = self.db_manager.get_tables()
        table_names = [table[0] for table in all_tables]

        self.logger.info(f"Iniciando generación de grafos Matplotlib para {len(table_names)} tablas")
        self.logger.info(f"Directorio de salida: {output_dir}")
        self.logger.info(f"Formato: {format}, max_subnodes: {max_subnodes}")

        results: dict[str, dict[str, Any]] = {}

        # Filtrar tablas sin relaciones si es necesario
        tables_to_process = table_names
        if skip_tables_without_relations:
            tables_to_process = []
            for table in table_names:
                try:
                    relations: list[TableRelation] = self.analyze_table_relations(table)
                    if relations:
                        tables_to_process.append(table)
                    else:
                        self.logger.debug(f"Omitiendo tabla sin relaciones: {table}")
                except Exception:
                    pass

            self.logger.info(f"Tablas a procesar tras filtrado: {len(tables_to_process)}/{len(table_names)}")

        # Generar grafos para cada tabla
        for idx, table_name in enumerate(tables_to_process, 1):
            try:
                self.logger.info(f"[{idx}/{len(tables_to_process)}] Generando gráfico para tabla: {table_name}")

                # Generar gráfico paginado directamente en output_dir
                generated_files: list[Path] = self.generate_matplotlib_graph_paginated(
                    table_name=table_name,
                    output_dir=output_dir,
                    format=format,
                    max_subnodes=max_subnodes,
                )

                results[table_name] = {
                    "status": "success",
                    "files": [str(f) for f in generated_files],
                    "count": len(generated_files),
                }

                self.logger.debug(f"Gráfico completado para {table_name}: {len(generated_files)} archivo(s)")

            except Exception as e:
                error_msg = str(e)
                self.logger.error(f"Error generando gráfico para tabla {table_name}: {error_msg}")
                results[table_name] = {"status": "error", "error": error_msg, "files": []}

        # Resumen final
        successful: int = sum(1 for r in results.values() if r["status"] == "success")
        self.logger.info(f"Generación completada: {successful}/{len(tables_to_process)} tablas procesadas exitosamente")

        return results
