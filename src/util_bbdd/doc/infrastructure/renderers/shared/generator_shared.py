"""Helpers compartidos para generadores de documentacion (Word/Excel/HTML)."""

from __future__ import annotations

import logging

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from ....._core.exceptions import DatabaseException
from .....metadata.catalog_registry import get_catalog_dialect
from .....metadata.model import Kind

if TYPE_CHECKING:
    from .....analysis.graphviz_ext import GraphvizRelationshipGraphExt
    from ....application.ports import DocumentationManagerPort

# Fila de datos devuelta por driver de BD (posicional, puede variar por motor).
DbRow = tuple[Any, ...]


class GeneratorTableRuntime:
    """Utilidades compartidas para parseo de filas de tablas."""

    @staticmethod
    def extract_table_row_data(row: tuple[Any, ...]) -> tuple[str, str, str | None]:
        """Extrae tabla, comentario y charset/collation desde una fila de inventario."""
        table_name: str = str(row[0]) if len(row) > 0 and row[0] is not None else ""
        comment: str = str(row[1]) if len(row) > 1 and row[1] is not None else ""

        # MariaDB: [tabla, comentario, charset, collation]
        if len(row) > 3:
            charset = row[2]
            collation = row[3]
            charset_collation = f"{charset} {collation}".strip() if charset or collation else None
            return table_name, comment, charset_collation

        # Resto: [tabla, comentario, charset_collation?]
        charset_collation = row[2] if len(row) > 2 else None
        return table_name, comment, charset_collation

    @staticmethod
    def get_storage_total_rows(data_provider: DocumentationManagerPort) -> int:
        """Obtiene el total agregado de filas del inventario de almacenamiento."""
        try:
            report: dict[str, Any] = data_provider.get_storage_inventory_report()
        except DatabaseException:
            return 0

        total: int = 0
        for section in report.get("sections", []):
            total += len(section.get("rows", []))
        return total


class GeneratorRoutineRuntime:
    """Utilidades compartidas para normalizacion y filtrado de rutinas."""

    @staticmethod
    def normalize_entry(routine: tuple[Any, ...], *, uppercase_type: bool = True) -> tuple[str, str, str]:
        """Normaliza una fila de rutina al formato (nombre, tipo, comentario)."""
        routine_name: str = str(routine[0]) if len(routine) > 0 and routine[0] is not None else ""
        routine_type: str = str(routine[1]) if len(routine) > 1 and routine[1] is not None else "FUNCTION"
        routine_comment: str = str(routine[2]) if len(routine) > 2 and routine[2] is not None else ""
        return routine_name, routine_type.upper() if uppercase_type else routine_type, routine_comment

    @staticmethod
    def split_by_type(routines: list[tuple[Any, ...]]) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
        """Separa routines en procedures y functions."""
        procedures: list[tuple[Any, ...]] = []
        functions: list[tuple[Any, ...]] = []
        for routine in routines:
            _, routine_type, _ = GeneratorRoutineRuntime.normalize_entry(routine, uppercase_type=True)
            if routine_type == "PROCEDURE":
                procedures.append(routine)
            elif routine_type == "FUNCTION":
                functions.append(routine)
        return procedures, functions

    @staticmethod
    def filter_by_flags(
        routines: list[tuple[Any, ...]],
        *,
        include_procedures: bool,
        include_functions: bool,
        include_non_procedure_as_function: bool = True,
    ) -> list[tuple[Any, ...]]:
        """Filtra rutinas segun flags de impresion."""
        if include_procedures and include_functions:
            return routines

        filtered: list[tuple[Any, ...]] = []
        for routine in routines:
            _, routine_type, _ = GeneratorRoutineRuntime.normalize_entry(routine, uppercase_type=True)
            if routine_type == "PROCEDURE" and include_procedures:
                filtered.append(routine)
            elif routine_type == "FUNCTION" and include_functions:
                filtered.append(routine)
            elif routine_type not in {"PROCEDURE", "FUNCTION"} and include_non_procedure_as_function:
                if include_functions:
                    filtered.append(routine)
        return filtered

    @staticmethod
    def get_unclassified(
        *,
        routines: list[tuple[Any, ...]],
        procedures: list[tuple[Any, ...]],
        functions: list[tuple[Any, ...]],
    ) -> list[tuple[Any, ...]]:
        """Devuelve rutinas no clasificadas como procedure/function."""
        classified_set = set(procedures) | set(functions)
        return [routine for routine in routines if routine not in classified_set]


class GeneratorInventoryRuntime:
    """Utilidades compartidas para construir resúmenes de inventario."""

    @staticmethod
    def build_summary_rows(
        *,
        tables_count: int,
        views_count: int,
        routines_count: int,
        procedures_count: int,
        functions_count: int,
        storage_count: int,
        include_routines: bool = True,
    ) -> list[tuple[str, int]]:
        """Construye filas de resumen en orden estable para renderers documentales."""
        rows: list[tuple[str, int]] = [
            ("Tablas", int(tables_count)),
            ("Vistas", int(views_count)),
        ]
        if include_routines:
            rows.append(("Rutinas", int(routines_count)))
        rows.extend(
            [
                ("Procedures", int(procedures_count)),
                ("Funciones", int(functions_count)),
                ("Almacenamiento", int(storage_count)),
            ]
        )
        return rows

    @staticmethod
    def build_summary_rows_from_entities(
        *,
        tables: list[tuple[Any, ...]],
        views: list[tuple[Any, ...]],
        routines: list[tuple[Any, ...]],
        include_storage: bool,
        data_provider: DocumentationManagerPort,
        include_routines: bool = True,
    ) -> list[tuple[str, int]]:
        """Construye filas de resumen desde colecciones de entidades ya filtradas."""
        procedures, functions = GeneratorRoutineRuntime.split_by_type(routines)
        storage_count: int = GeneratorTableRuntime.get_storage_total_rows(data_provider) if include_storage else 0
        return GeneratorInventoryRuntime.build_summary_rows(
            tables_count=len(tables),
            views_count=len(views),
            routines_count=len(routines),
            procedures_count=len(procedures),
            functions_count=len(functions),
            storage_count=storage_count,
            include_routines=include_routines,
        )


class GeneratorTabularRuntime:
    """Utilidades compartidas para normalizacion de columnas e indices."""

    _DEFAULT_UNIQUE_HEADERS: tuple[str, str] = ("Nombre Restricción", "Campo")

    @staticmethod
    def process_indices_data(indices: list[DbRow]) -> list[list[Any]]:
        """Filas de índices ``[índice, columna, Sí/No, método]`` (formato neutro de ``catalog_rows``)."""
        return [[GeneratorTabularRuntime._to_text(value) for value in index] for index in indices]

    @staticmethod
    def normalize_unique_headers(headers: list[Any] | tuple[Any, ...] | None) -> list[str]:
        """Normaliza cabeceras de UNIQUE al contrato estable de dos columnas."""
        if headers is None:
            return list(GeneratorTabularRuntime._DEFAULT_UNIQUE_HEADERS)

        normalized_headers: list[str] = []
        for header in headers:
            text = str(header).strip()
            if text:
                normalized_headers.append(text)

        if len(normalized_headers) >= 2:
            return normalized_headers[:2]
        if len(normalized_headers) == 1:
            return [normalized_headers[0], GeneratorTabularRuntime._DEFAULT_UNIQUE_HEADERS[1]]
        return list(GeneratorTabularRuntime._DEFAULT_UNIQUE_HEADERS)

    @staticmethod
    def process_unique_constraints_data(unique_constraints: list[DbRow]) -> list[list[str]]:
        """Normaliza filas de restricciones únicas a [constraint_name, column_name]."""
        return [list(GeneratorTabularRuntime._extract_unique_constraint_pair(item)) for item in unique_constraints]

    @staticmethod
    def _extract_unique_constraint_pair(unique_row: Any) -> tuple[str, str]:
        """Extrae de forma robusta (constraint_name, column_name)."""
        row_mapping = GeneratorTabularRuntime._as_mapping(unique_row)
        if row_mapping is not None:
            constraint_name = GeneratorTabularRuntime._get_mapping_value_case_insensitive(
                row_mapping,
                [
                    "constraint_name",
                    "constraint",
                    "name",
                    "nombre_restriccion",
                    "nombre_restricción",
                ],
            )
            column_name = GeneratorTabularRuntime._get_mapping_value_case_insensitive(
                row_mapping,
                [
                    "column_name",
                    "column",
                    "field",
                    "campo",
                    "columna",
                ],
            )
            return constraint_name, column_name

        if isinstance(unique_row, (list, tuple)):
            if len(unique_row) >= 2:
                return (
                    GeneratorTabularRuntime._to_text(unique_row[0]),
                    GeneratorTabularRuntime._resolve_unique_column_value(unique_row),
                )
            if len(unique_row) == 1:
                return GeneratorTabularRuntime._to_text(unique_row[0]), ""
            return "", ""

        if unique_row is None:
            return "", ""
        return GeneratorTabularRuntime._to_text(unique_row), ""

    @staticmethod
    def _to_text(value: Any) -> str:
        """Convierte valor arbitrario a texto seguro para render tabular."""
        return "" if value is None else str(value)

    @staticmethod
    def _as_mapping(value: Any) -> Mapping[Any, Any] | None:
        """Devuelve un mapping uniforme cuando la fila lo soporta."""
        if isinstance(value, Mapping):
            return value
        mapping_attr = getattr(value, "_mapping", None)
        if isinstance(mapping_attr, Mapping):
            return mapping_attr
        return None

    @staticmethod
    def _get_mapping_value_case_insensitive(mapping: Mapping[Any, Any], keys: list[str]) -> str:
        """Obtiene un valor de mapping sin depender del casing de la clave."""
        normalized_keys: dict[str, Any] = {str(raw_key).strip().casefold(): raw_key for raw_key in mapping.keys()}
        for key in keys:
            found_key = normalized_keys.get(key.casefold())
            if found_key is None:
                continue
            value = mapping.get(found_key)
            text = GeneratorTabularRuntime._to_text(value).strip()
            if text:
                return text
        return ""

    @staticmethod
    def _resolve_unique_column_value(unique_row: list[Any] | tuple[Any, ...]) -> str:
        """Resuelve el valor de campo/columna en filas posicionales."""
        candidate = GeneratorTabularRuntime._to_text(unique_row[1]).strip()
        if GeneratorTabularRuntime._is_likely_column_identifier(candidate):
            return candidate

        for value in unique_row[2:]:
            probe = GeneratorTabularRuntime._to_text(value).strip()
            if GeneratorTabularRuntime._is_likely_column_identifier(probe):
                return probe
        return candidate

    @staticmethod
    def _is_likely_column_identifier(value: str) -> bool:
        """Heurística ligera para detectar si un valor parece nombre de columna."""
        if not value:
            return False
        lowered = value.casefold()
        if lowered in {"true", "false"}:
            return False
        if value.isdigit():
            return False
        return True

    @staticmethod
    def get_safe_value(row: Any, index: int, *, as_str: bool = False) -> Any:
        """Lee un valor por indice de forma segura."""
        if len(row) <= index:
            return ""
        value = row[index]
        if as_str:
            return str(value) if value is not None else ""
        return value if value is not None else ""

    @staticmethod
    def process_columns_data(columnas: list[DbRow]) -> list[list[Any]]:
        """Filas de columnas ``[campo, tipo, nulo, por defecto, generación, comentario]``, iguales en todos los motores."""
        return [[GeneratorTabularRuntime._to_text(value) for value in column] for column in columnas]

    @staticmethod
    def build_flat_base_data(column: Any) -> list[str]:
        """Fila base plana de una columna (la de ``process_columns_data``; el comentario va al final)."""
        return [GeneratorTabularRuntime._to_text(value) for value in column]

    @staticmethod
    def map_foreign_keys_by_column(*, foreign_keys: list[DbRow], arrow: str) -> dict[str, str]:
        """``{columna: "restricción -> tabla(columna)"}`` desde filas ``(restricción, columna, tabla ref., col. ref., …)``."""
        mapped: dict[str, str] = {}
        for foreign_key in foreign_keys:
            constraint_name, source_column, target_table, target_column = (
                GeneratorTabularRuntime._to_text(value) for value in foreign_key[:4]
            )
            mapped[source_column] = f"{constraint_name} {arrow} {target_table}({target_column})"
        return mapped

    @staticmethod
    def map_indices_by_column(*, indices: list[DbRow]) -> dict[str, list[str]]:
        """``{columna: [índices]}`` desde filas ``(índice, columna, …)``."""
        mapped: dict[str, list[str]] = {}
        for index_data in indices:
            mapped.setdefault(GeneratorTabularRuntime._to_text(index_data[1]), []).append(
                GeneratorTabularRuntime._to_text(index_data[0])
            )
        return mapped

    @staticmethod
    def build_enriched_flat_rows(
        *,
        table_name: str,
        table_comment: str,
        columns: list[DbRow],
        db_type: str,
        primary_keys: set[str],
        foreign_keys_by_column: dict[str, str],
        indices_by_column: dict[str, list[str]],
        detail_path: str | None,
    ) -> list[list[str]]:
        """Construye filas enriquecidas con PK/FK/índices y detalle opcional."""
        rows: list[list[str]] = []
        for column in columns:
            column_name: str = GeneratorTabularRuntime._to_text(column[0]) if len(column) > 0 else ""
            base_data: list[str] = GeneratorTabularRuntime.build_flat_base_data(column)
            base_without_comment: list[str] = base_data[:-1]
            column_comment: str = base_data[-1] if base_data else ""
            enriched_attributes: list[str] = [
                "Sí" if column_name in primary_keys else "No",
                foreign_keys_by_column.get(column_name, "No"),
                ", ".join(indices_by_column.get(column_name, [])),
            ]
            row: list[str] = [table_name, table_comment] + base_without_comment + enriched_attributes + [column_comment]
            if detail_path is not None:
                row.append(detail_path)
            rows.append(row)
        return rows

    @staticmethod
    def build_enriched_flat_rows_for_table(
        *,
        table_name: str,
        table_comment: str,
        columns: list[DbRow],
        data_provider: DocumentationManagerPort,
        detail_path: str | None,
        fk_arrow: str,
    ) -> list[list[str]]:
        """Construye filas enriquecidas de una tabla usando metadata del proveedor."""
        db_type: str = str(getattr(data_provider, "db_type", "") or "").lower()
        primary_keys: set[str] = {
            GeneratorTabularRuntime._to_text(primary_key[0])
            for primary_key in data_provider.get_primary_keys(table_name)
            if len(primary_key) > 0
        }
        foreign_keys_by_column: dict[str, str] = GeneratorTabularRuntime.map_foreign_keys_by_column(
            foreign_keys=list(data_provider.get_foreign_keys(table_name)),
            arrow=fk_arrow,
        )
        indices_by_column: dict[str, list[str]] = GeneratorTabularRuntime.map_indices_by_column(
            indices=list(data_provider.get_indices(table_name)),
        )
        return GeneratorTabularRuntime.build_enriched_flat_rows(
            table_name=table_name,
            table_comment=table_comment,
            columns=columns,
            db_type=db_type,
            primary_keys=primary_keys,
            foreign_keys_by_column=foreign_keys_by_column,
            indices_by_column=indices_by_column,
            detail_path=detail_path,
        )


class GeneratorDatabaseInfoRuntime:
    """Utilidades compartidas para informacion de base de datos."""

    @staticmethod
    def collect_database_info_rows(
        *,
        data_provider: DocumentationManagerPort,
        database_info_flags: list[bool],
        logger: logging.Logger,
        include_error_rows: bool,
        debug_context: str = "",
    ) -> list[list[str]]:
        """Recolecta filas [propiedad, valor] para version y charset/collation."""
        include_version: bool = bool(database_info_flags[0]) if len(database_info_flags) > 0 else False
        include_charset: bool = bool(database_info_flags[1]) if len(database_info_flags) > 1 else False

        info_data: list[list[str]] = []

        if include_version:
            GeneratorDatabaseInfoRuntime._append_version_info(
                data_provider=data_provider,
                info_data=info_data,
                logger=logger,
                include_error_rows=include_error_rows,
                debug_context=debug_context,
            )
        if include_charset:
            GeneratorDatabaseInfoRuntime._append_charset_info(
                data_provider=data_provider,
                info_data=info_data,
                logger=logger,
                include_error_rows=include_error_rows,
                debug_context=debug_context,
            )
        return info_data

    @staticmethod
    def _append_version_info(
        *,
        data_provider: DocumentationManagerPort,
        info_data: list[list[str]],
        logger: logging.Logger,
        include_error_rows: bool,
        debug_context: str,
    ) -> None:
        context_suffix = f" {debug_context}" if debug_context else ""
        try:
            version = data_provider.get_database_version()
            if version and str(version).strip() != "Unknown":
                info_data.append(["Versión", str(version)])
                logger.debug(f"Version de BD obtenida{context_suffix}: {version}")
            else:
                logger.debug("No hay informacion de version disponible")
        except DatabaseException as error:
            logger.warning(f"Error obteniendo version: {error}")
            if include_error_rows:
                info_data.append(["Versión", f"Error: {error}"])

    @staticmethod
    def _append_charset_info(
        *,
        data_provider: DocumentationManagerPort,
        info_data: list[list[str]],
        logger: logging.Logger,
        include_error_rows: bool,
        debug_context: str,
    ) -> None:
        context_suffix = f" {debug_context}" if debug_context else ""
        try:
            charset_info = data_provider.get_database_charset_collation()
            if charset_info and isinstance(charset_info, dict):
                for key, value in charset_info.items():
                    if value and str(value).strip():
                        info_data.append([key.replace("_", " ").title(), str(value)])
                logger.debug(f"Charset/Collation obtenido{context_suffix}: {charset_info}")
            else:
                logger.debug("No hay informacion de charset/collation disponible")
        except DatabaseException as error:
            logger.warning(f"Error obteniendo charset/collation: {error}")
            if include_error_rows:
                info_data.append(["Charset/Collation", f"Error: {error}"])

    @staticmethod
    def collect_database_info_query_templates(
        *,
        data_provider: Any,
        database_info_flags: list[bool],
        logger: logging.Logger,
    ) -> list[str]:
        """SQL con el que se leen versión y charset/collation de la base de datos (``Kind.DATABASE`` del catálogo)."""
        include_version: bool = bool(database_info_flags[0]) if len(database_info_flags) > 0 else False
        include_charset: bool = bool(database_info_flags[1]) if len(database_info_flags) > 1 else False
        if not (include_version or include_charset):
            return []
        try:
            query = get_catalog_dialect(str(data_provider.db_manager.db_type)).query(Kind.DATABASE)
        except DatabaseException as error:
            logger.warning(f"Error obteniendo la consulta de base de datos: {error}")
            return []
        return [query.sql] if query is not None else []


def build_graph_generator_from_options(source: Any, options: dict[str, Any]) -> GraphvizRelationshipGraphExt:
    """Crea el ``GraphvizRelationshipGraphExt`` de la documentación a partir del bloque ``grafo`` de ``imprimir``.

    Único punto de construcción (lo usan el orquestador y, si no reciben uno, Word y HTML), para que todos los
    formatos dibujen con las mismas opciones (A-02: antes el generador compartido ignoraba ``show_columns``).

    Args:
        source: Fuente de metadatos (``RelationshipGraphSource``), p. ej. el manager adaptado de la sesión.
        options: Sub-diccionario ``grafo`` de ``print_config`` normalizado.

    Example:
        >>> gen = build_graph_generator_from_options(session.db_manager, {"max_depth": 2, "workers": 4})
    """
    from .....analysis.graphviz_ext import GraphvizRelationshipGraphExt as _Ext

    columns_options: dict[str, Any] = options.get("columns", {})
    cardinality_options: dict[str, Any] = options.get("cardinality", {})
    workers: Any = options.get("workers")
    return _Ext(
        db_manager=source,
        show_columns=bool(options.get("show_columns", True)),
        column_mode=str(columns_options.get("mode", "relations")),
        max_columns=int(columns_options.get("max_items", 8)),
        show_data_types=bool(columns_options.get("show_data_types", False)),
        max_depth=int(options.get("max_depth", 1)),
        direction=str(options.get("direction", "both")),
        show_constraint_name=bool(cardinality_options.get("show_constraint_name", False)),
        render_dpi=int(options.get("dpi", 150)),
        render_workers=None if workers is None else int(workers),
    )
