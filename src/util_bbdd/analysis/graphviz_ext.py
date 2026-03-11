"""
Implementación extendida de generación de grafos usando Graphviz con detalles de columnas
Muestra columnas, tipos de datos, cardinalidad y colores diferenciales
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

from ..managers import DatabaseManager
from .base import DatabaseRelationshipGraphBase, TableRelation

GRAPHVIZ_MISSING_MSG: str = "Graphviz no disponible. Instale: pip install graphviz"


class GraphvizRelationshipGraphExt(DatabaseRelationshipGraphBase):
    """
    Generador extendido de grafos Graphviz con:
    - Nodos que muestran columnas y tipos de datos
    - Cardinalidad en relaciones
    - Colores diferenciados para tabla principal vs relacionadas
    """

    # Colores pastel
    MAIN_TABLE_COLOR: str = "#FFB3BA"  # Rosa pastel para tabla principal
    RELATED_TABLE_COLOR: str = "#FFFFBA"  # Amarillo pastel para tablas relacionadas
    TEXT_COLOR: str = "#000000"  # Negro para texto

    def __init__(
        self,
        db_manager: DatabaseManager,
        show_columns: bool = True,
        orthogonal_edges: bool = True,
        orthogonal_nodesep: float = 0.75,
        orthogonal_ranksep: float = 0.9,
    ):
        super().__init__(db_manager)
        self.logger: Logger = logging.getLogger(__name__)

        if not GRAPHVIZ_AVAILABLE or graphviz is None:
            raise ImportError(GRAPHVIZ_MISSING_MSG)

        # Configuración para mostrar columnas en nodos
        self.show_columns: bool = show_columns
        # Configuración de estilo de líneas de relación (ángulo recto)
        self.orthogonal_edges: bool = orthogonal_edges
        # Espaciado de layout para líneas ortogonales
        self.orthogonal_nodesep: float = orthogonal_nodesep
        self.orthogonal_ranksep: float = orthogonal_ranksep

        # Cache para columnas de tablas (evitar múltiples consultas)
        self._columns_cache: dict[str, list[tuple[str, str]]] = {}

        # Usar cachés centralizadas desde DatabaseManager para relaciones
        # No necesitamos cachés locales para PKs, UKs ni cardinalidades

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
                    col_type = str(col[1]) if len(col) > 1 else "VARCHAR"
                    result.append((col_name, col_type))
                else:
                    result.append((str(col), "VARCHAR"))

            self._columns_cache[table_name] = result
            return result
        except Exception as e:
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
        except Exception as e:
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
        except Exception as e:
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
                result: str = "M:N"
                self.logger.debug("📊 Detectada relación M:N (ambos son PK)")
                self.db_manager.relationship_cache.set_cardinality(
                    source_col, target_col, source_table, target_table, result
                )
                return result

            # Caso 2: 1:1 (source tiene restricción única)
            if target_is_pk and source_is_uk:
                result: str = "1:1"
                self.logger.debug("📊 Detectada relación 1:1 (target es PK y source es UK)")
                self.db_manager.relationship_cache.set_cardinality(
                    source_col, target_col, source_table, target_table, result
                )
                return result

            # Caso 3: 1:N (target es PK, source es FK)
            if target_is_pk:
                result: str = "1:N"
                self.logger.debug("📊 Detectada relación 1:N (target es PK)")
                self.db_manager.relationship_cache.set_cardinality(
                    source_col, target_col, source_table, target_table, result
                )
                return result

            # Caso 4: N:1 (source es PK, target es FK) - por defecto
            result: str = "N:1"
            self.logger.debug("📊 Detectada relación N:1 (por defecto)")
            self.db_manager.relationship_cache.set_cardinality(
                source_col, target_col, source_table, target_table, result
            )
            return result

        except Exception as e:
            self.logger.warning(f"⚠️ Error determinando cardinalidad: {e}, usando 1:N por defecto")
            return "1:N"

    def _build_table_html_label(self, table_name: str, is_main: bool = False, is_raster: bool = False) -> str:
        """
        Construye una etiqueta HTML para un nodo de tabla con columnas y tipos

        Args:
            table_name: Nombre de la tabla
            is_main: Si es la tabla principal

        Returns:
            String con HTML para Graphviz
        """
        columns: list[tuple[str, str]] = self._get_table_columns_with_types(table_name)

        # Color de fondo
        bg_color: str = self.MAIN_TABLE_COLOR if is_main else self.RELATED_TABLE_COLOR

        title_row_height: str = "46" if is_raster else "40"
        title_font_size: str = "12" if is_raster else "10"
        column_font_size: str = "10" if is_raster else "9"
        type_font_size: str = "9" if is_raster else "8"

        # Iniciar tabla HTML
        html: str = f"""<
        <TABLE BORDER="1" CELLBORDER="1" CELLSPACING="0" CELLPADDING="5" BGCOLOR="{bg_color}">
        <TR HEIGHT="{title_row_height}"><TD COLSPAN="2" BGCOLOR="{bg_color}" BORDER="2" VALIGN="MIDDLE"><B><FONT POINT-SIZE="{title_font_size}">{table_name}</FONT></B></TD></TR>
        """

        # Agregar columnas
        if columns:
            for col_name, col_type in columns:
                # Limitar longitud de tipo de dato para mejor visualización
                type_str: str = col_type.split("(")[0][:20]  # Tomar hasta 20 caracteres del tipo
                html += f'<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="{column_font_size}">{col_name}</FONT></TD><TD ALIGN="LEFT"><FONT POINT-SIZE="{type_font_size}" COLOR="black">{type_str}</FONT></TD></TR>\n'
        else:
            html += f'<TR><TD COLSPAN="2" ALIGN="CENTER"><FONT POINT-SIZE="{type_font_size}" COLOR="black">Sin columnas disponibles</FONT></TD></TR>\n'

        html += "</TABLE>>"
        return html

    def generate_graphviz_graph_paginated_ext(
        self,
        table_name: str,
        output_dir: Path,
        format: str = "png",
        max_subnodes: int = 10,
        show_columns: bool | None = None,
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
        # Usar show_columns de la instancia si no se proporciona
        if show_columns is None:
            show_columns = self.show_columns

        self.logger.info(
            f"Iniciando generación paginada extendida de Graphviz para {table_name} "
            f"(max {max_subnodes} nodos por página)"
        )
        relations: list[TableRelation] = self.analyze_table_relations(table_name)
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
            generated_file: Path = self._generate_graphviz_graph_internal_ext(
                table_name, output_path, format, page_relations, show_columns
            )
            generated_files.append(generated_file)

        return generated_files

    def _generate_graphviz_graph_internal_ext(
        self,
        table_name: str,
        output_file: Path,
        format: str,
        relations: list[TableRelation],
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

            tables_in_page: set[str] = self._collect_tables_in_page(table_name, relations)
            dot, is_raster_format, edge_label_font_size = self._create_configured_graph(
                table_name=table_name,
                format=format,
                show_columns=show_columns,
            )

            self._add_nodes_to_graph(
                dot=dot,
                tables_in_page=tables_in_page,
                table_name=table_name,
                show_columns=show_columns,
                is_raster_format=is_raster_format,
            )
            self._add_edges_to_graph(dot=dot, relations=relations, edge_label_font_size=edge_label_font_size)

            return self._render_graph(dot=dot, output_file=output_file, format=format, table_name=table_name)
        except Exception as e:
            self.logger.error(
                f"Error al generar gráfico Graphviz extendido para tabla {table_name}: {str(e)}",
                exc_info=True,
            )
            raise

    def _collect_tables_in_page(self, table_name: str, relations: list[TableRelation]) -> set[str]:
        """
        Construye el conjunto de tablas que participan en una página del grafo.

        Args:
            table_name: Tabla principal
            relations: Relaciones de la página

        Returns:
            Conjunto de nombres de tablas
        """
        tables_in_page: set[str] = {table_name}
        for relation in relations:
            tables_in_page.add(relation.source_table)
            tables_in_page.add(relation.target_table)
        return tables_in_page

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
            dot.attr("graph", dpi="300")

        node_font_size: str = "12" if is_raster_format else "10"
        edge_font_size: str = "10" if is_raster_format else "9"
        edge_label_font_size: str = "9" if is_raster_format else "8"

        dot.attr("node", shape="plaintext", fontname="Arial", fontsize=node_font_size)
        dot.attr("edge", fontname="Arial", fontsize=edge_font_size, color="#666666")

        return dot, is_raster_format, edge_label_font_size

    def _add_nodes_to_graph(
        self,
        dot: Any,
        tables_in_page: set[str],
        table_name: str,
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
        for table in tables_in_page:
            is_main: bool = table == table_name
            if show_columns:
                html_label: str = self._build_table_html_label(table, is_main, is_raster=is_raster_format)
                dot.node(table, html_label)
                continue

            bg_color = self.MAIN_TABLE_COLOR if is_main else self.RELATED_TABLE_COLOR
            dot.node(
                table,
                table,
                shape="box",
                style="filled",
                fillcolor=bg_color,
                penwidth="2" if is_main else "1",
            )

    def _add_edges_to_graph(self, dot: Any, relations: list[TableRelation], edge_label_font_size: str) -> None:
        """
        Agrega aristas con cardinalidad y etiqueta de columnas.

        Args:
            dot: Grafo Graphviz
            relations: Relaciones a dibujar
            edge_label_font_size: Tamaño de fuente para etiquetas de arista
        """
        for relation in relations:
            cardinality: str = self._determine_cardinality(
                source_col=relation.source_column,
                target_col=relation.target_column,
                source_table=relation.source_table,
                target_table=relation.target_table,
            )
            relation_label: str = f"{relation.source_column} → {relation.target_column} [{cardinality}]"

            dot.edge(
                relation.source_table,
                relation.target_table,
                xlabel=relation_label,
                fontsize=edge_label_font_size,
                color="#666666",
            )

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
        dot.render(output_path_str, cleanup=True)

        expected_file = Path(f"{output_path_str}.{format}")
        if expected_file.exists():
            self.logger.info(f"Gráfico Graphviz extendido generado exitosamente para {table_name}")
            return expected_file

        raise FileNotFoundError(f"Archivo no encontrado: {expected_file}")

    def generate_all_tables_graphs_ext(
        self,
        output_dir: Path | None = None,
        format: str = "png",
        skip_tables_without_relations: bool = True,
        max_subnodes: int = 10,
        show_columns: bool | None = None,
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
        # Usar show_columns de la instancia si no se proporciona
        if show_columns is None:
            show_columns = self.show_columns

        if output_dir is None:
            output_dir = Path("./grafos_graphviz_ext")

        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        all_tables = self.db_manager.get_tables()
        table_names = [table[0] for table in all_tables]

        self.logger.info(f"Iniciando generación de grafos Graphviz extendidos para {len(table_names)} tablas")
        self.logger.info(f"Directorio de salida: {output_dir}")
        self.logger.info(f"Formato: {format}, max_subnodes: {max_subnodes}, mostrar columnas: {show_columns}")

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

            self.logger.info(f"Tablas a procesar tras filtrado: {len(tables_to_process)}/{len(table_names)}")

        # Generar grafos para cada tabla
        for idx, table_name in enumerate(tables_to_process, 1):
            try:
                self.logger.info(
                    f"[{idx}/{len(tables_to_process)}] Generando gráfico extendido para tabla: {table_name}"
                )

                # Generar gráfico paginado extendido
                generated_files: list[Path] = self.generate_graphviz_graph_paginated_ext(
                    table_name=table_name,
                    output_dir=output_dir,
                    format=format,
                    max_subnodes=max_subnodes,
                    show_columns=show_columns,
                )

                results[table_name] = {
                    "status": "success",
                    "files": [str(f) for f in generated_files],
                    "count": len(generated_files),
                }

                self.logger.debug(f"Gráfico extendido completado para {table_name}: {len(generated_files)} archivo(s)")

            except Exception as e:
                error_msg = str(e)
                self.logger.error(f"Error generando gráfico extendido para tabla {table_name}: {error_msg}")
                results[table_name] = {"status": "error", "error": error_msg, "files": []}

        # Resumen final
        successful: int = sum(1 for r in results.values() if r["status"] == "success")
        self.logger.info(
            f"Generación extendida completada: {successful}/{len(tables_to_process)} tablas procesadas exitosamente"
        )

        return results

    def generate_single_table_graph_ext(
        self,
        table_name: str,
        output_file: Path,
        format: str = "png",
        show_columns: bool | None = None,
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
        """  # Usar show_columns de la instancia si no se proporciona
        if show_columns is None:
            show_columns = self.show_columns
        self.logger.info(f"Generando gráfico extendido simple para tabla: {table_name}")

        relations: list[TableRelation] = self.analyze_table_relations(table_name)

        return self._generate_graphviz_graph_internal_ext(
            table_name=table_name,
            output_file=output_file,
            format=format,
            relations=relations,
            show_columns=show_columns,
        )
