"""
Clase base para generación de grafos de relaciones entre tablas
Contiene métodos y atributos compartidos entre implementaciones
"""

import logging

from dataclasses import dataclass
from logging import Logger
from typing import Any

from ..database_manager import DatabaseManager


@dataclass
class TableRelation:
    """Representa una relación entre tablas"""

    source_table: str
    target_table: str
    constraint_name: str
    source_column: str
    target_column: str
    relation_type: str = "FK"  # FK, PK, etc.


class DatabaseRelationshipGraphBase:
    """Clase base para generar grafos de relaciones de bases de datos"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager: DatabaseManager = db_manager
        self.relations: list[TableRelation] = []
        self.tables: set[str] = set()
        self.logger: Logger = logging.getLogger(__name__)

    def analyze_table_relations(self, table_name: str) -> list[TableRelation]:
        """
        Analiza las relaciones de primer nivel de una tabla específica

        Args:
            table_name: Nombre de la tabla a analizar

        Returns:
            Lista de relaciones de la tabla con otras tablas
        """
        self.logger.debug(f"Analizando relaciones para tabla: {table_name}")
        # Limpiar estado anterior para evitar acumulación
        self.relations = []
        self.tables = set()

        relations = []

        # Obtener claves foráneas que salen de la tabla (hijos)
        foreign_keys = self.db_manager.get_foreign_keys(table_name)
        self.logger.debug(f"Encontradas {len(foreign_keys)} claves foráneas salientes en {table_name}")
        for fk in foreign_keys:
            if self.db_manager.db_type == "mariadb":
                # MariaDB: CONSTRAINT_NAME, TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                relation = TableRelation(
                    source_table=table_name,
                    target_table=fk[3],
                    constraint_name=fk[0],
                    source_column=fk[2],
                    target_column=fk[4],
                    relation_type="FK",
                )
            else:
                # Oracle, PostgreSQL, HSQLDB: CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_TABLE, REFERENCED_COLUMN
                relation = TableRelation(
                    source_table=table_name,
                    target_table=fk[2],
                    constraint_name=fk[0],
                    source_column=fk[1],
                    target_column=fk[3],
                    relation_type="FK",
                )
            relations.append(relation)

        # Obtener claves foráneas que apuntan a la tabla (padres)
        parent_relations: list[TableRelation] = self._find_parent_relations(table_name)
        self.logger.debug(f"Encontradas {len(parent_relations)} relaciones entrantes en {table_name}")
        relations.extend(parent_relations)

        # Almacenar tablas involucradas
        self.tables.add(table_name)
        for relation in relations:
            self.tables.add(relation.source_table)
            self.tables.add(relation.target_table)

        self.relations = relations
        self.logger.info(
            f"Análisis completado para {table_name}: {len(relations)} relaciones totales, {len(self.tables)} tablas involucradas"
        )
        return relations

    def _find_parent_relations(self, table_name: str) -> list[TableRelation]:
        """
        Encuentra relaciones donde la tabla dada es el target (tabla padre)
        Esto requiere consultar todas las tablas para encontrar FKs que apunten a nuestra tabla
        """
        self.logger.debug(f"Buscando relaciones entrantes (padres) para: {table_name}")
        parent_relations = []

        # Obtener todas las tablas de la base de datos
        all_tables = self.db_manager.get_tables()

        for table_info in all_tables:
            current_table = table_info[0]  # El primer elemento es siempre el nombre de la tabla

            if current_table == table_name:
                continue  # Saltar la misma tabla

            # Obtener FKs de esta tabla para ver si alguna apunta a nuestra tabla
            foreign_keys = self.db_manager.get_foreign_keys(current_table)
            for fk in foreign_keys:
                target_table: str = self._extract_target_table(fk)

                if target_table == table_name:
                    # Esta tabla tiene una FK que apunta a nuestra tabla
                    if self.db_manager.db_type == "mariadb":
                        relation = TableRelation(
                            source_table=current_table,
                            target_table=table_name,
                            constraint_name=fk[0],
                            source_column=fk[2],
                            target_column=fk[4],
                            relation_type="FK",
                        )
                    else:
                        relation = TableRelation(
                            source_table=current_table,
                            target_table=table_name,
                            constraint_name=fk[0],
                            source_column=fk[1],
                            target_column=fk[3],
                            relation_type="FK",
                        )
                    parent_relations.append(relation)

        return parent_relations

    def _extract_target_table(self, fk_data: tuple) -> str:
        """Extrae el nombre de la tabla target de los datos de FK según el tipo de BD"""
        if self.db_manager.db_type == "mariadb":
            return fk_data[3]  # REFERENCED_TABLE_NAME
        else:
            return fk_data[2]  # REFERENCED_TABLE

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

        # Calcular número de imágenes necesarias
        import math

        num_images: int = math.ceil(total_relations / max_subnodes)

        if num_images <= 1:
            self.logger.debug("Relaciones caben en una sola imagen")
            return [relations]

        # Calcular tamaño de cada imagen
        size_per_image: int = math.ceil(total_relations / num_images)
        self.logger.debug(f"Se crearán {num_images} imágenes con {size_per_image} relaciones por imagen")

        # Dividir relaciones
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
        relations: list[TableRelation] = self.analyze_table_relations(table_name)

        # Separar relaciones por tipo
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
            "related_tables": list(self.tables - {table_name}),
            "database_type": self.db_manager.db_type,
        }

        self.logger.info(f"Reporte completado para {table_name}: {len(relations)} relaciones totales")
        return report
