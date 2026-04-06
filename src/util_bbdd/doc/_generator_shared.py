"""Helpers compartidos para generadores de documentacion (Word/Excel/HTML)."""

from __future__ import annotations

import logging

from typing import Any


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


class GeneratorTabularRuntime:
    """Utilidades compartidas para normalizacion de columnas e indices."""

    _DEFAULT_COLUMN_SPECS: list[tuple[int, bool]] = [
        (0, False),
        (1, False),
        (2, False),
        (3, True),
        (4, True),
        (5, True),
        (6, True),
        (7, True),
    ]

    _COLUMN_SPECS_BY_DB: dict[str, list[tuple[int, bool]]] = {
        "mariadb": [
            (0, False),
            (1, False),
            (2, False),
            (3, False),
            (4, False),
            (5, False),
            (6, False),
        ],
        "oracle": [
            (0, False),
            (1, False),
            (2, False),
            (3, True),
            (4, True),
            (5, True),
            (6, True),
            (7, True),
        ],
        "postgresql": [
            (0, False),
            (1, False),
            (2, False),
            (3, True),
            (4, True),
            (5, True),
            (6, True),
            (7, True),
        ],
        "hsqldb": [
            (0, False),
            (1, False),
            (2, False),
            (3, True),
            (4, True),
            (5, True),
            (6, True),
            (7, True),
        ],
        "sqlserver": [
            (0, False),
            (1, False),
            (2, False),
            (3, True),
            (4, True),
            (5, True),
            (6, True),
            (7, True),
            (8, True),
        ],
    }

    _SQLITE_SHORT_COLUMN_SPECS: list[tuple[int, bool]] = [
        (0, False),
        (1, False),
        (2, False),
        (3, True),
        (4, True),
        (5, True),
        (7, True),
    ]

    @staticmethod
    def is_unique(index_data: tuple[Any, ...], db_type: str) -> bool:
        """Determina si un indice es unico segun el tipo de BD."""
        if db_type == "oracle":
            return bool(index_data[1] == "UNIQUE")
        if db_type == "postgresql":
            return bool(index_data[2] is True)
        if db_type == "hsqldb":
            return bool(index_data[2] == "UNIQUE")
        if db_type == "sqlite":
            return str(index_data[2]).strip().lower() in ("1", "true", "yes", "unique")
        return False

    @staticmethod
    def process_indices_data(indices: list[Any], db_type: str) -> list[list[Any]]:
        """Procesa datos de indices para estandarizar su salida."""
        if db_type == "mariadb":
            return [[idx[0], idx[1], "No" if idx[2] else "Sí", idx[3]] for idx in indices]

        if db_type == "oracle":
            return [
                [idx[0], idx[3], "Sí" if GeneratorTabularRuntime.is_unique(idx, db_type) else "No", idx[2]]
                for idx in indices
            ]

        return [
            [idx[0], idx[1], "Sí" if GeneratorTabularRuntime.is_unique(idx, db_type) else "No", idx[3]]
            for idx in indices
        ]

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
    def format_column_row(col: Any, specs: list[tuple[int, bool]]) -> list[Any]:
        """Formatea una fila de columnas segun especificacion."""
        return [GeneratorTabularRuntime.get_safe_value(col, idx, as_str=as_str) for idx, as_str in specs]

    @staticmethod
    def process_columns_data(
        columnas: list[Any],
        db_type: str,
        *,
        include_sqlite_short_shape: bool,
    ) -> list[list[Any]]:
        """Procesa columnas segun el tipo de motor."""
        specs_by_db = dict(GeneratorTabularRuntime._COLUMN_SPECS_BY_DB)
        if include_sqlite_short_shape:
            specs_by_db["sqlite"] = GeneratorTabularRuntime._SQLITE_SHORT_COLUMN_SPECS

        specs: list[tuple[int, bool]] = specs_by_db.get(db_type, GeneratorTabularRuntime._DEFAULT_COLUMN_SPECS)
        return [GeneratorTabularRuntime.format_column_row(col, specs) for col in columnas]


class GeneratorDatabaseInfoRuntime:
    """Utilidades compartidas para informacion de base de datos."""

    @staticmethod
    def collect_database_info_rows(
        *,
        data_provider: Any,
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
        data_provider: Any,
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
        except Exception as error:
            logger.warning(f"Error obteniendo version: {error}")
            if include_error_rows:
                info_data.append(["Versión", f"Error: {error}"])

    @staticmethod
    def _append_charset_info(
        *,
        data_provider: Any,
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
        except Exception as error:
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
        """Obtiene las plantillas SQL usadas para informacion de base de datos."""
        sql_queries: list[str] = []
        try:
            query_info: dict[str, Any] = data_provider.db_manager.get_query_info()
            queries_map: dict[str, Any] = query_info.get("queries", {})

            include_version: bool = bool(database_info_flags[0]) if len(database_info_flags) > 0 else False
            include_charset: bool = bool(database_info_flags[1]) if len(database_info_flags) > 1 else False

            if include_version:
                version_sql: str = str(queries_map.get("database_version", {}).get("template", "") or "")
                if version_sql.strip():
                    sql_queries.append(version_sql)
                    logger.debug("Query de version agregada")

            if include_charset:
                charset_sql: str = str(queries_map.get("database_charset_collation", {}).get("template", "") or "")
                if charset_sql.strip():
                    sql_queries.append(charset_sql)
                    logger.debug("Query de charset agregada")
        except Exception as error:
            logger.warning(f"Error obteniendo queries SQL: {error}")
        return sql_queries
