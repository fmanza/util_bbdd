"""
Implementación de generación de grafos usando Graphviz
"""

import logging

from logging import Logger
from pathlib import Path
from typing import Any

try:
    import graphviz

    GRAPHVIZ_AVAILABLE = True
except ImportError:
    graphviz = None
    GRAPHVIZ_AVAILABLE = False

from ..database_manager import DatabaseManager
from .relationship_graph_base import DatabaseRelationshipGraphBase, TableRelation

GRAPHVIZ_MISSING_MSG: str = "Graphviz no disponible. Instale: pip install graphviz"


class GraphvizRelationshipGraph(DatabaseRelationshipGraphBase):
    """Generador de grafos usando Graphviz con layout circular"""

    def __init__(self, db_manager: DatabaseManager):
        super().__init__(db_manager)
        self.logger: Logger = logging.getLogger(__name__)

        if not GRAPHVIZ_AVAILABLE or graphviz is None:
            raise ImportError(GRAPHVIZ_MISSING_MSG)

    def generate_graphviz_graph_paginated(
        self, table_name: str, output_dir: Path, format: str = "png", max_subnodes: int = 10
    ) -> list[Path]:
        """
        Genera grafos Graphviz dividiendo en múltiples imágenes si es necesario

        Args:
            table_name: Tabla central del grafo
            output_dir: Directorio de salida para los archivos
            format: Formato de salida (png, svg, pdf, etc.)
            max_subnodes: Máximo de sub-nodos por imagen

        Returns:
            Lista de Paths de archivos generados
        """
        self.logger.info(
            f"Iniciando generación paginada de Graphviz para {table_name} (max {max_subnodes} nodos por página)"
        )
        relations: list[TableRelation] = self.analyze_table_relations(table_name)
        split_relations: list[list[TableRelation]] = self._split_relations_for_visualization(
            relations, max_subnodes
        )
        self.logger.debug(f"Tabla {table_name} dividida en {len(split_relations)} página(s)")

        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        generated_files: list[Path] = []

        for page_num, page_relations in enumerate(split_relations, 1):
            # Crear nombre de archivo descriptivo con graphviz y nombre de tabla
            if len(split_relations) > 1:
                # Múltiples páginas: graphviz_tablename_page1.png
                file_name: str = f"graphviz_{table_name}_page{page_num}"
            else:
                # Una sola página: graphviz_tablename.png
                file_name = f"graphviz_{table_name}"

            output_path: Path = output_dir / file_name

            # Generar gráfico para esta página
            generated_file: Path = self._generate_graphviz_graph_internal(
                table_name, output_path, format, page_relations
            )
            generated_files.append(generated_file)

        return generated_files

    def _generate_graphviz_graph_internal(
        self, table_name: str, output_file: Path, format: str, relations: list[TableRelation]
    ) -> Path:
        """
        Genera un gráfico Graphviz interno con relaciones específicas

        Args:
            table_name: Tabla central
            output_file: Ruta de salida
            format: Formato
            relations: Relaciones a incluir en el gráfico

        Returns:
            Path del archivo generado
        """
        if not GRAPHVIZ_AVAILABLE or graphviz is None:
            raise ImportError(GRAPHVIZ_MISSING_MSG)

        try:
            output_file = Path(output_file).resolve()
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Construir set de tablas para este gráfico
            tables_in_page: set[str] = {table_name}
            for relation in relations:
                tables_in_page.add(relation.source_table)
                tables_in_page.add(relation.target_table)

            dot = graphviz.Digraph(
                comment=f"Relaciones de {table_name}", format=format, engine="circo"
            )
            dot.attr(size="20,20", overlap="false")
            dot.attr(
                "node", shape="box", style="rounded,filled", fillcolor="lightblue", fontname="Arial"
            )
            dot.attr("edge", fontname="Arial", fontsize="10")

            for table in tables_in_page:
                if table == table_name:
                    dot.node(table, table, fillcolor="lightcoral", penwidth="2")
                else:
                    dot.node(table, table)

            for relation in relations:
                label: str = f"{relation.source_column} → {relation.target_column}\\n{relation.constraint_name}"
                dot.edge(relation.source_table, relation.target_table, label=label)

            output_path_str = str(output_file)
            dot.render(output_path_str, cleanup=True)

            expected_file = Path(f"{output_path_str}.{format}")
            if expected_file.exists():
                self.logger.info(f"Gráfico Graphviz generado exitosamente para {table_name}")
                return expected_file
            else:
                raise FileNotFoundError(f"Archivo no encontrado: {expected_file}")
        except Exception as e:
            self.logger.error(
                f"Error al generar gráfico Graphviz para tabla {table_name}: {str(e)}",
                exc_info=True,
            )
            raise

    def generate_all_tables_graphs(
        self,
        output_dir: Path | None = None,
        format: str = "png",
        skip_tables_without_relations: bool = True,
        max_subnodes: int = 10,
    ) -> dict[str, dict[str, Any]]:
        """
        Genera grafos Graphviz para todas las tablas de la base de datos

        Args:
            output_dir: Directorio de salida (default: ./grafos_graphviz)
            format: Formato de salida (png, svg, pdf, etc.)
            skip_tables_without_relations: Si True, omite tablas sin relaciones
            max_subnodes: Máximo de sub-nodos por imagen

        Returns:
            Diccionario con los resultados {tabla: {status, files, error}}
        """
        if output_dir is None:
            output_dir = Path("./grafos_graphviz")

        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        all_tables = self.db_manager.get_tables()
        table_names = [table[0] for table in all_tables]

        self.logger.info(f"Iniciando generación de grafos Graphviz para {len(table_names)} tablas")
        self.logger.info(f"Directorio de salida: {output_dir}")
        self.logger.info(f"Formato: {format}, max_subnodes: {max_subnodes}")

        results: dict[str, dict[str, Any]] = {}

        # Filtrar tablas sin relaciones si es necesario
        tables_to_process = table_names
        if skip_tables_without_relations:
            tables_to_process = []
            for table in table_names:
                try:
                    relations = self.analyze_table_relations(table)
                    if relations:
                        tables_to_process.append(table)
                    else:
                        self.logger.debug(f"Omitiendo tabla sin relaciones: {table}")
                except Exception:
                    pass

            self.logger.info(
                f"Tablas a procesar tras filtrado: {len(tables_to_process)}/{len(table_names)}"
            )

        # Generar grafos para cada tabla
        for idx, table_name in enumerate(tables_to_process, 1):
            try:
                self.logger.info(
                    f"[{idx}/{len(tables_to_process)}] Generando gráfico para tabla: {table_name}"
                )

                # Generar gráfico paginado directamente en output_dir
                generated_files: list[Path] = self.generate_graphviz_graph_paginated(
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

                self.logger.debug(
                    f"Gráfico completado para {table_name}: {len(generated_files)} archivo(s)"
                )

            except Exception as e:
                error_msg = str(e)
                self.logger.error(f"Error generando gráfico para tabla {table_name}: {error_msg}")
                results[table_name] = {"status": "error", "error": error_msg, "files": []}

        # Resumen final
        successful: int = sum(1 for r in results.values() if r["status"] == "success")
        self.logger.info(
            f"Generación completada: {successful}/{len(tables_to_process)} tablas procesadas exitosamente"
        )

        return results
