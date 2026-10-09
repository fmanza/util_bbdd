"""
Módulo para generación de documentación en formato Excel
"""

import logging

from pathlib import Path
from typing import Any

# Excel imports
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.worksheet import Worksheet

from ...._core.exceptions import DatabaseException
from ...._core.export_safety import SafeWorkbook
from ...application.ports import DocumentationManagerPort, HeadersConfig
from .shared.generator_shared import (
    GeneratorDatabaseInfoRuntime,
    GeneratorInventoryRuntime,
    GeneratorRoutineRuntime,
    GeneratorTableRuntime,
    GeneratorTabularRuntime,
)
from .shared.print_config_manager import PrintConfigManager


class ExcelGenerator:
    """Clase para generar documentación en formato Excel"""

    def __init__(self, database: str, headers: HeadersConfig, table_style: str = "Medium Shading 2 Accent 1"):
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.database: str = database
        self.headers: HeadersConfig = headers
        self.table_style: str = self._normalize_table_style(table_style)
        self._table_counter: int = 0

    def _normalize_table_style(self, table_style: str) -> str:
        """Normaliza el estilo de tabla a un valor compatible con Excel."""
        style_map: dict[str, str] = {
            "Medium Shading 2 Accent 1": "TableStyleMedium2",
            # Valor por defecto de imprimir.table_style (un estilo de Word): sin aviso en cada ejecución (A-11)
            "Table Grid": "TableStyleMedium2",
        }
        normalized_style: str = style_map.get(table_style, table_style)

        valid_prefixes: tuple[str, ...] = (
            "TableStyleLight",
            "TableStyleMedium",
            "TableStyleDark",
            "PivotStyleLight",
            "PivotStyleMedium",
            "PivotStyleDark",
        )
        fallback_style: str = "TableStyleMedium2"

        if normalized_style.startswith(valid_prefixes):
            return normalized_style

        self.logger.warning(f"⚠️  Estilo de tabla Excel '{table_style}' no reconocido. Se usará '{fallback_style}'.")
        return fallback_style

    def generate_document(
        self,
        tables: list[tuple],
        views: list[tuple],
        routines: list[tuple],
        data_provider: DocumentationManagerPort,
        output_target: Path,
        print_config: dict[str, Any] | None = None,
        graph_generator: Any | None = None,
    ) -> None:
        """Genera el documento Excel completo con tablas y vistas."""
        _ = graph_generator
        self.logger.info(f"🟢 Iniciando generación de documentación Excel para base de datos: {self.database}")
        self._validate_required_headers()
        try:
            routines = routines or []
            output_target.parent.mkdir(parents=True, exist_ok=True)

            # SafeWorkbook: comentarios y DDL del catálogo sin caracteres de control ni fórmulas.
            wb = SafeWorkbook()
            ws1 = wb.active
            if not ws1:
                return

            ws1.title = "Documentación"
            fila = 1

            config = self._resolve_print_config(print_config, data_provider)
            fila = self._create_main_header(ws1, fila)
            fila = self._add_inventory_summary(
                ws=ws1,
                fila=fila,
                tables=tables if config["include_tables"] else [],
                views=views if config["include_views"] else [],
                routines=GeneratorRoutineRuntime.filter_by_flags(
                    routines,
                    include_procedures=config["include_procedures"],
                    include_functions=config["include_functions"],
                    include_non_procedure_as_function=True,
                ),
                include_storage=config["include_storage"],
                data_provider=data_provider,
            )

            data_flat: list[list[Any]] = []
            fila = self._build_overview_sections(ws1, fila, tables, views, routines, data_provider, data_flat, config)
            self._create_supplementary_sheets(wb, data_flat, tables, routines, data_provider, config)

            wb.save(str(output_target))
            self.logger.info(f"✅ Documento Excel generado: {output_target}")
        except Exception as error:
            self.logger.exception(f"❌ Error generando documentación Excel: {error}")
            raise

    def _resolve_print_config(
        self, print_config: dict[str, Any] | None, data_provider: DocumentationManagerPort
    ) -> dict[str, Any]:
        """Resuelve la configuración de impresión normalizada."""
        normalized_config: dict[str, Any] = PrintConfigManager.normalize(print_config or data_provider.imprimir_config)
        resolved: dict[str, Any] = PrintConfigManager.resolve_for_excel(normalized_config)
        include_database_info: bool = resolved.get("include_database_info", False)
        self.logger.debug(
            "⚙️  Configuración Excel resuelta: "
            f"tables={resolved['include_tables']}, views={resolved['include_views']}, "
            f"procedures={resolved['include_procedures']}, functions={resolved['include_functions']}, "
            f"storage={resolved['include_storage']}, database_info={include_database_info}, "
            f"database_info_flags={resolved.get('database_info_flags', [False, False])}"
        )

        # Diagnóstico: verificar si la información de BD está deshabilitada
        if not include_database_info:
            self.logger.info(
                "ℹ️  La información de la base de datos NO se incluirá en el documento. "
                "Si desea incluirla, configure [imprimir.info_database] en el archivo TOML con imprimir_info_database = true"
            )

        return resolved

    def _build_overview_sections(
        self,
        ws: Worksheet,
        fila: int,
        tables: list[tuple],
        views: list[tuple],
        routines: list[tuple],
        data_provider: DocumentationManagerPort,
        data_flat: list,
        config: dict[str, Any],
    ) -> int:
        """Construye todas las secciones de descripción general del documento."""
        if config["include_tables"]:
            fila = self._add_tables_overview(
                ws=ws,
                fila=fila,
                tables=tables,
                data_provider=data_provider,
                data_flat=data_flat,
                section_flags=config["table_section_flags"],
            )
        if config["include_views"]:
            fila = self._add_views_overview(
                ws=ws,
                fila=fila,
                views=views,
                data_provider=data_provider,
                section_flags=config["view_section_flags"],
            )
        if config["include_procedures"] or config["include_functions"]:
            selected_routines: list[tuple] = GeneratorRoutineRuntime.filter_by_flags(
                routines,
                include_procedures=config["include_procedures"],
                include_functions=config["include_functions"],
                include_non_procedure_as_function=True,
            )
            fila = self._add_routines_overview(
                ws=ws,
                fila=fila,
                routines=selected_routines,
                data_provider=data_provider,
            )
        return fila

    def _create_supplementary_sheets(
        self,
        wb: Workbook,
        data_flat: list,
        tables: list[tuple],
        routines: list[tuple],
        data_provider: DocumentationManagerPort,
        config: dict[str, Any],
    ) -> None:
        """Crea las hojas suplementarias (columnas, rutinas, almacenamiento, información BD)."""
        if config["include_tables"]:
            # D1: hoja enriquecida (PK, FK, índices) en todos los motores
            self._create_enriched_sheet(wb, data_provider, tables)

        if config["include_procedures"] or config["include_functions"]:
            self._create_routines_sheets(
                wb=wb,
                routines=routines,
                data_provider=data_provider,
                include_procedures=config["include_procedures"],
                include_functions=config["include_functions"],
            )
        if config["include_storage"]:
            self._create_storage_sheet(wb=wb, data_provider=data_provider)

        if config.get("include_columns_charset", False):
            self._create_columns_charset_collation_sheet(
                wb=wb,
                tables=tables,
                data_provider=data_provider,
            )

        if config.get("include_database_info", False):
            database_info_flags: list[bool] = config.get("database_info_flags", [False, False])
            self._create_database_info_sheet(
                wb=wb,
                data_provider=data_provider,
                database_info_flags=database_info_flags,
            )

    def _validate_required_headers(self) -> None:
        """Valida que existan los headers obligatorios para generar Excel."""
        required_headers: list[str] = ["FLAT", "RUTINAS"]
        missing_headers: list[str] = [header for header in required_headers if header not in self.headers]

        if missing_headers:
            missing_text: str = ", ".join(missing_headers)
            raise KeyError(f"Faltan headers requeridos para Excel: {missing_text}")

    def _add_tables_overview(
        self,
        ws: Worksheet,
        fila: int,
        tables: list[tuple],
        data_provider: DocumentationManagerPort,
        data_flat: list,
        section_flags: list[bool],
    ) -> int:
        """Agrega el bloque de tablas al documento Excel."""
        if not tables:
            return fila

        self.logger.info(f"📄 Procesando {len(tables)} tabla(s) para Excel")
        ws[f"A{fila}"] = "TABLAS"
        ws[f"A{fila}"].font = Font(size=12, bold=True, color="FFFFFF")
        ws[f"A{fila}"].fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        fila += 1

        for row in tables:
            tabla, comentario, charset_collation = GeneratorTableRuntime.extract_table_row_data(row)

            fila = self._process_table(
                ws,
                fila,
                tabla,
                comentario,
                charset_collation,
                data_provider,
                data_flat,
                section_flags,
            )

        return fila

    def _add_views_overview(
        self,
        ws: Worksheet,
        fila: int,
        views: list[tuple],
        data_provider: DocumentationManagerPort,
        section_flags: list[bool],
    ) -> int:
        """Agrega el bloque de vistas al documento Excel."""
        if not views:
            return fila

        self.logger.info(f"📄 Procesando {len(views)} vista(s) para Excel")
        ws[f"A{fila}"] = "VISTAS"
        ws[f"A{fila}"].font = Font(size=12, bold=True, color="FFFFFF")
        ws[f"A{fila}"].fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        fila += 1

        for vista, comentario in views:
            fila = self._process_view(ws, fila, vista, comentario, data_provider, section_flags)

        return fila

    def _add_routines_overview(
        self,
        ws: Worksheet,
        fila: int,
        routines: list[tuple],
        data_provider: DocumentationManagerPort,
    ) -> int:
        """Agrega el bloque de procedures/funciones al documento Excel."""
        if not routines:
            return fila

        self.logger.info(f"📄 Procesando {len(routines)} rutina(s) para Excel")
        ws[f"A{fila}"] = "RUTINAS"
        ws[f"A{fila}"].font = Font(size=12, bold=True, color="FFFFFF")
        ws[f"A{fila}"].fill = PatternFill(start_color="5B9BD5", end_color="5B9BD5", fill_type="solid")
        fila += 1

        procedures, functions = GeneratorRoutineRuntime.split_by_type(routines)
        fila = self._process_routines_section(ws, fila, procedures, "PROCEDURES", "2F75B5", data_provider)
        fila = self._process_routines_section(ws, fila, functions, "FUNCIONES", "4F81BD", data_provider)
        fila = self._process_unclassified_routines(ws, fila, routines, procedures, functions, data_provider)

        return fila

    def _process_routines_section(
        self,
        ws: Worksheet,
        fila: int,
        routines: list[tuple],
        section_title: str,
        color: str,
        data_provider: DocumentationManagerPort,
    ) -> int:
        """Procesa una sección de rutinas (procedures o funciones)."""
        if not routines:
            return fila

        ws[f"A{fila}"] = section_title
        ws[f"A{fila}"].font = Font(size=11, bold=True, color="FFFFFF")
        ws[f"A{fila}"].fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
        fila += 1

        for routine in routines:
            fila = self._process_routine(ws, fila, routine, data_provider)

        return fila

    def _process_unclassified_routines(
        self,
        ws: Worksheet,
        fila: int,
        routines: list[tuple],
        procedures: list[tuple],
        functions: list[tuple],
        data_provider: DocumentationManagerPort,
    ) -> int:
        """Procesa rutinas no clasificadas."""
        unclassified = GeneratorRoutineRuntime.get_unclassified(
            routines=routines,
            procedures=procedures,
            functions=functions,
        )
        for routine in unclassified:
            routine_name, routine_type, routine_comment = GeneratorRoutineRuntime.normalize_entry(
                routine,
                uppercase_type=False,
            )
            fila = self._process_routine(
                ws,
                fila,
                (routine_name, routine_type, routine_comment),
                data_provider,
            )

        return fila

    def _create_routines_sheets(
        self,
        wb: Workbook,
        routines: list[tuple],
        data_provider: DocumentationManagerPort,
        include_procedures: bool,
        include_functions: bool,
    ) -> None:
        """Crea hojas separadas para procedures y functions."""
        procedures, functions = GeneratorRoutineRuntime.split_by_type(routines)
        unclassified = self._get_unclassified_routines(routines=routines, procedures=procedures, functions=functions)

        if include_procedures:
            self._create_single_routine_sheet(
                wb=wb,
                title="Procedures",
                routines=procedures,
                data_provider=data_provider,
            )
        if include_functions:
            self._create_single_routine_sheet(
                wb=wb,
                title="Functions",
                routines=functions + unclassified,
                data_provider=data_provider,
            )

    def _create_single_routine_sheet(
        self,
        wb: Workbook,
        title: str,
        routines: list[tuple],
        data_provider: DocumentationManagerPort,
    ) -> None:
        """Crea una hoja de rutinas por tipo en formato tabular."""
        ws = wb.create_sheet(title)
        headers: list[str] = self.headers["RUTINAS"]
        ws.append(headers)

        for cell in ws[1]:
            cell.font = Font(bold=True)

        if not routines:
            ws.append(["No se encontraron rutinas."] + [""] * (len(headers) - 1))
            self._apply_table_style_to_range(
                ws=ws,
                start_row=1,
                end_row=ws.max_row,
                column_count=len(headers),
                prefix=title,
            )
            return

        for routine in routines:
            ws.append(self._build_routine_sheet_row(routine=routine, data_provider=data_provider))

        self._apply_table_style_to_range(
            ws=ws,
            start_row=1,
            end_row=ws.max_row,
            column_count=len(headers),
            prefix=title,
        )

    def _build_routine_sheet_row(self, routine: tuple, data_provider: DocumentationManagerPort) -> list[str]:
        """Construye una fila tabular para la hoja de rutinas."""
        routine_name, routine_type, routine_comment = GeneratorRoutineRuntime.normalize_entry(
            routine,
            uppercase_type=False,
        )

        routine_ddl: str = ""
        try:
            ddl: str = data_provider.get_routine_ddl(routine_name, routine_type)
            routine_ddl = ddl if ddl is not None else ""
        except DatabaseException:
            routine_ddl = "⚠️ No se pudo obtener el DDL de la rutina"

        parameters_text: str = self._get_routine_parameters_text(
            routine_name=routine_name,
            routine_type=routine_type,
            data_provider=data_provider,
        )

        return [routine_name, routine_type.title(), routine_comment, routine_ddl, parameters_text]

    def _get_routine_parameters_text(
        self, routine_name: str, routine_type: str, data_provider: DocumentationManagerPort
    ) -> str:
        """Obtiene los parámetros de la rutina en formato texto para la hoja tabular."""
        try:
            parameters = data_provider.get_routine_parameters(routine_name, routine_type)
        except DatabaseException:
            return "⚠️ No se pudieron obtener los parámetros de la rutina"

        if not parameters:
            return ""

        parameters_rows: list[str] = [self._format_routine_parameter_row(row) for row in parameters]

        return "\n".join(parameters_rows)

    def _format_routine_parameter_row(self, row: tuple) -> str:
        """Formatea una fila de parámetro de rutina a texto legible."""
        position: str = self._safe_tuple_value(row, 4)
        mode: str = self._safe_tuple_value(row, 0)
        name: str = self._safe_tuple_value(row, 1)
        data_type: str = self._safe_tuple_value(row, 2)
        default_value: str = self._safe_tuple_value(row, 3)

        raw_text: str = f"{position}. {mode} {name} {data_type} {default_value}".strip()
        return raw_text.lstrip(".").strip()

    def _safe_tuple_value(self, row: tuple, index: int) -> str:
        """Obtiene un valor de tuple en forma segura y lo devuelve como texto."""
        if len(row) <= index:
            return ""

        value = row[index]
        return str(value) if value is not None else ""

    def _get_unclassified_routines(
        self, routines: list[tuple], procedures: list[tuple], functions: list[tuple]
    ) -> list[tuple]:
        """Obtiene rutinas no clasificadas como procedures/functions."""
        return GeneratorRoutineRuntime.get_unclassified(
            routines=routines,
            procedures=procedures,
            functions=functions,
        )

    def _create_main_header(self, ws: Worksheet, fila: int) -> int:
        """Crea el encabezado principal del documento Excel."""
        ws[f"A{fila}"] = f"Documentación de la Base de Datos - {self.database}"
        ws[f"A{fila}"].font = Font(size=14, bold=True)
        return fila + 2

    def _add_inventory_summary(
        self,
        *,
        ws: Worksheet,
        fila: int,
        tables: list[tuple],
        views: list[tuple],
        routines: list[tuple],
        include_storage: bool,
        data_provider: DocumentationManagerPort,
    ) -> int:
        """Agrega un resumen inicial con conteos del inventario."""
        ws[f"A{fila}"] = "RESUMEN DE INVENTARIO"
        ws[f"A{fila}"].font = Font(size=12, bold=True)
        fila += 1

        summary_rows: list[tuple[str, int]] = GeneratorInventoryRuntime.build_summary_rows_from_entities(
            tables=tables,
            views=views,
            routines=routines,
            include_storage=include_storage,
            data_provider=data_provider,
            include_routines=True,
        )

        header_row: int = fila
        ws.append(["Sección", "Total"])
        for cell in ws[header_row]:
            cell.font = Font(bold=True)

        for label, count in summary_rows:
            ws.append([label, count])
            ws.cell(row=ws.max_row, column=2).alignment = Alignment(horizontal="right")

        self._apply_colored_range_style(
            ws=ws,
            start_row=header_row,
            end_row=ws.max_row,
            column_count=2,
        )
        return int(ws.max_row) + 2

    def _process_table(
        self,
        ws: Worksheet,
        fila: int,
        tabla: str,
        comentario: str,
        charset_collation: str | None,
        data_provider: DocumentationManagerPort,
        data_flat: list,
        table_section_flags: list[bool],
    ) -> int:
        """Procesa la información de una tabla individual."""
        # Encabezado de tabla
        ws[f"A{fila}"] = f"Tabla: {tabla}"
        ws[f"A{fila}"].font = Font(size=12, bold=True)
        fila += 1
        ws[f"A{fila}"] = f"Comentario: {comentario if comentario else ''}"
        if charset_collation and str(charset_collation).strip():
            fila += 1
            ws[f"A{fila}"] = f"Charset & Collation: {charset_collation}"
        fila += 2

        # DDL
        if table_section_flags[0]:
            fila = self._add_ddl_section(ws, fila, tabla, data_provider)

        # Columnas
        if table_section_flags[1]:
            fila = self._add_columns_section(
                ws, fila, tabla, comentario, data_provider, data_flat, create_excel_table=False
            )

        return fila

    def _process_routine(
        self,
        ws: Worksheet,
        fila: int,
        routine: tuple,
        data_provider: DocumentationManagerPort,
    ) -> int:
        """Procesa la información de una rutina (procedure/función)."""
        routine_name, routine_type, routine_comment = GeneratorRoutineRuntime.normalize_entry(
            routine,
            uppercase_type=False,
        )

        ws[f"A{fila}"] = f"{routine_type.title()}: {routine_name}"
        ws[f"A{fila}"].font = Font(size=12, bold=True)
        fila += 1
        ws[f"A{fila}"] = f"Tipo: {routine_type.title()}"
        fila += 1
        ws[f"A{fila}"] = f"Comentario: {routine_comment}"
        fila += 2

        try:
            ddl: str = data_provider.get_routine_ddl(routine_name, routine_type)
            text_ddl: str = ddl if ddl is not None else ""
            ws[f"A{fila}"] = "DDL"
            ws[f"A{fila}"].font = Font(bold=True)
            fila += 1
            ws[f"A{fila}"] = text_ddl
            fila += 2
        except DatabaseException:
            ws[f"A{fila}"] = "⚠️ No se pudo obtener el DDL de la rutina"
            fila += 2

        fila = self._add_routine_parameters_section(
            ws=ws,
            fila=fila,
            routine_name=routine_name,
            routine_type=routine_type,
            data_provider=data_provider,
            create_excel_table=False,
        )
        return fila

    def _add_routine_parameters_section(
        self,
        ws: Worksheet,
        fila: int,
        routine_name: str,
        routine_type: str,
        data_provider: DocumentationManagerPort,
        create_excel_table: bool = True,
    ) -> int:
        """Agrega la sección de parámetros de rutina a la hoja Excel."""
        ws[f"A{fila}"] = "Parámetros"
        ws[f"A{fila}"].font = Font(bold=True)
        fila += 1

        headers = self.headers.get("PARAMETROS_RUTINA", ["Modo", "Parámetro", "Tipo", "Valor por defecto", "Posición"])
        header_row: int = fila
        ws.append(headers)

        for cell in ws[fila]:
            cell.font = Font(bold=True)

        try:
            parameters = data_provider.get_routine_parameters(routine_name, routine_type)
        except DatabaseException:
            ws[f"A{fila + 1}"] = "⚠️ No se pudieron obtener los parámetros de la rutina"
            return fila + 3

        if not parameters:
            ws[f"A{fila + 1}"] = "No se encontraron parámetros."
            return fila + 3

        for row in parameters:
            ws.append(GeneratorRoutineRuntime.parameter_rows([row])[0])

        if create_excel_table:
            self._apply_table_style_to_range(
                ws=ws,
                start_row=header_row,
                end_row=ws.max_row,
                column_count=len(headers),
                prefix="RoutineParams",
                show_filters=False,
            )
        else:
            self._apply_colored_range_style(
                ws=ws,
                start_row=header_row,
                end_row=ws.max_row,
                column_count=len(headers),
            )

        return int(ws.max_row) + 2

    def _process_view(
        self,
        ws: Worksheet,
        fila: int,
        vista: str,
        comentario: str,
        data_provider: DocumentationManagerPort,
        view_section_flags: list[bool],
    ) -> int:
        """Procesa la información de una vista individual."""
        # Encabezado de vista
        ws[f"A{fila}"] = f"Vista: {vista}"
        ws[f"A{fila}"].font = Font(size=12, bold=True)
        fila += 1
        ws[f"A{fila}"] = f"Comentario: {comentario if comentario else ''}"
        fila += 2

        # Vistas típicamente solo tienen DDL y Columnas
        if view_section_flags[0]:
            try:
                fila = self._add_ddl_section(ws, fila, vista, data_provider, is_view=True)
            except DatabaseException:
                ws[f"A{fila}"] = "⚠️ No se pudo obtener el DDL de la vista"
                fila += 2

        if view_section_flags[1]:
            try:
                # Crear lista temporal para data_flat (no se usa para vistas)
                data_flat_tmp: list = []
                fila = self._add_columns_section(
                    ws,
                    fila,
                    vista,
                    comentario,
                    data_provider,
                    data_flat_tmp,
                    create_excel_table=False,
                )
            except DatabaseException:
                ws[f"A{fila}"] = "⚠️ No se pudieron obtener las columnas de la vista"
                fila += 2

        return fila

    def _add_ddl_section(
        self,
        ws: Worksheet,
        fila: int,
        tabla: str,
        data_provider: DocumentationManagerPort,
        is_view: bool = False,
    ) -> int:
        """Agrega la sección DDL a la hoja Excel."""
        ws[f"A{fila}"] = "DDL"
        ws[f"A{fila}"].font = Font(bold=True)
        fila += 1

        ddl: str = data_provider.get_view_ddl(tabla) if is_view else data_provider.get_ddl(tabla)
        text_ddl: str = ddl if ddl is not None else ""
        ws[f"A{fila}"] = text_ddl
        return fila + 2

    def _add_columns_section(
        self,
        ws: Worksheet,
        fila: int,
        tabla: str,
        comentario: str,
        data_provider: DocumentationManagerPort,
        data_flat: list,
        create_excel_table: bool = True,
    ) -> int:
        """Agrega la sección de Columnas a la hoja Excel."""
        ws[f"A{fila}"] = "Columnas"
        ws[f"A{fila}"].font = Font(bold=True)
        fila += 1

        # Headers
        headers = self.headers["COLUMNAS"]

        header_row: int = fila
        ws.append(headers)

        # Poner en negrita la fila de cabecera
        for cell in ws[fila]:
            cell.font = Font(bold=True)

        # Datos de columnas
        columnas = data_provider.get_columns(tabla)

        for col in columnas:
            row = GeneratorTabularRuntime.build_flat_base_data(col)
            ws.append(row)
            data_flat.append([tabla, comentario if comentario else ""] + row)

        if create_excel_table:
            self._apply_table_style_to_range(
                ws=ws,
                start_row=header_row,
                end_row=ws.max_row,
                column_count=len(headers),
                prefix="Cols",
            )
        else:
            self._apply_colored_range_style(
                ws=ws,
                start_row=header_row,
                end_row=ws.max_row,
                column_count=len(headers),
            )

        return int(ws.max_row) + 2

    def _apply_colored_range_style(
        self,
        ws: Worksheet,
        start_row: int,
        end_row: int,
        column_count: int,
    ) -> None:
        """Aplica estilo de color manual (cabecera y bandas) a un rango tabular."""
        if column_count <= 0 or end_row < start_row:
            return

        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        row_fill_even = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")

        for col in range(1, column_count + 1):
            cell = ws.cell(row=start_row, column=col)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = header_fill

        for row in range(start_row + 1, end_row + 1):
            if (row - start_row) % 2 == 0:
                for col in range(1, column_count + 1):
                    ws.cell(row=row, column=col).fill = row_fill_even

    def _create_flat_sheet(self, wb: Workbook, data_flat: list) -> None:
        """Crea la hoja plana con todas las columnas (MariaDB)."""
        ws2 = wb.create_sheet("Columnas")
        headers = self.headers["FLAT"]
        ws2.append(headers)

        # Poner en negrita la cabecera
        for cell in ws2[1]:
            cell.font = Font(bold=True)

        for row in data_flat:
            ws2.append(row)

        self._apply_table_style_to_range(
            ws=ws2,
            start_row=1,
            end_row=ws2.max_row,
            column_count=len(headers),
            prefix="Flat",
        )

    def _create_enriched_sheet(
        self, wb: Workbook, data_provider: DocumentationManagerPort, tables: list[tuple]
    ) -> None:
        """Crea la hoja enriquecida con PK, FK e Índices (Oracle, PostgreSQL, HSQLDB)."""
        ws2 = wb.create_sheet("Columnas")
        headers = self.headers["FLAT"]
        ws2.append(headers)

        # Poner en negrita la cabecera
        for cell in ws2[1]:
            cell.font = Font(bold=True)

        # Procesar cada tabla para datos enriquecidos
        for row in tables:
            # Desempacar: tabla, comentario, [charset_collation opcional]
            tabla = row[0]
            comentario = row[1] if len(row) > 1 else ""
            data_enriquecida = self._prepare_enriched_data(tabla, comentario, data_provider)
            for row_data in data_enriquecida:
                ws2.append(row_data)

        self._apply_table_style_to_range(
            ws=ws2,
            start_row=1,
            end_row=ws2.max_row,
            column_count=len(headers),
            prefix="Enriched",
        )

    def _create_storage_sheet(self, wb: Workbook, data_provider: DocumentationManagerPort) -> None:
        """Crea hoja de almacenamiento con resumen y detalle de consultas disponibles."""
        ws = wb.create_sheet("Almacenamiento")
        ws["A1"] = "Inventario de almacenamiento"
        ws["A1"].font = Font(size=14, bold=True)
        ws["A2"] = f"Base de datos: {self.database}"

        try:
            report: dict[str, Any] = data_provider.get_storage_inventory_report()
        except DatabaseException as error:
            ws["A4"] = f"⚠️ No se pudo obtener el inventario de almacenamiento: {error}"
            return

        sections: list[dict[str, Any]] = report.get("sections", [])
        current_row: int = self._add_storage_summary(ws, sections)
        current_row += 1
        self._add_storage_details(ws, sections, current_row)

    def _add_storage_summary(self, ws: Worksheet, sections: list[dict[str, Any]]) -> int:
        """Agrega el resumen de almacenamiento a la hoja."""
        summary_headers: list[str] = ["Consulta", "Estado", "Filas", "Mensaje"]
        summary_start_row: int = 4
        for col_idx, header in enumerate(summary_headers, start=1):
            ws.cell(row=summary_start_row, column=col_idx, value=header).font = Font(bold=True)

        current_row: int = summary_start_row + 1
        for section in sections:
            ws.cell(row=current_row, column=1, value=str(section.get("title", "")))
            ws.cell(row=current_row, column=2, value=str(section.get("status", "")))
            ws.cell(row=current_row, column=3, value=len(section.get("rows", [])))
            ws.cell(row=current_row, column=4, value=str(section.get("message", "")))
            ws.cell(row=current_row, column=3).alignment = Alignment(horizontal="right")
            current_row += 1

        self._apply_table_style_to_range(
            ws=ws,
            start_row=summary_start_row,
            end_row=max(summary_start_row + 1, current_row - 1),
            column_count=len(summary_headers),
            prefix="StorageSummary",
        )
        return current_row

    def _add_storage_details(self, ws: Worksheet, sections: list[dict[str, Any]], current_row: int) -> None:
        """Agrega los detalles de almacenamiento a la hoja."""
        for section in sections:
            current_row = self._process_storage_section(ws, section, current_row)

    def _process_storage_section(self, ws: Worksheet, section: dict[str, Any], current_row: int) -> int:
        """Procesa una sección individual de almacenamiento."""
        title: str = str(section.get("title", "Consulta"))
        status: str = str(section.get("status", ""))
        ws.cell(row=current_row, column=1, value=f"{title} ({status})").font = Font(size=12, bold=True)
        current_row += 1

        headers: list[str] = self._get_storage_headers(section)
        rows: list[list[Any]] = section.get("rows", [])

        if not rows:
            ws.cell(row=current_row, column=1, value=str(section.get("message", "Sin datos")))
            return current_row + 2

        header_row: int = current_row
        ws.append(headers)
        for cell in ws[header_row]:
            cell.font = Font(bold=True)

        current_row = self._add_storage_rows(ws, rows, section, header_row, len(headers))
        return current_row + 2

    def _get_storage_headers(self, section: dict[str, Any]) -> list[str]:
        """Obtiene los headers para una sección de almacenamiento."""
        headers: list[str] = [str(h) for h in section.get("headers", [])]
        rows: list[list[Any]] = section.get("rows", [])

        if not headers and rows:
            max_cols: int = max(len(row) for row in rows)
            headers = [f"Columna {idx}" for idx in range(1, max_cols + 1)]

        return headers

    def _add_storage_rows(
        self,
        ws: Worksheet,
        rows: list[list[Any]],
        section: dict[str, Any],
        header_row: int,
        column_count: int,
    ) -> int:
        """Agrega las filas de datos a la hoja de almacenamiento."""
        numeric_columns: list[int] = [int(idx) for idx in section.get("numeric_columns", [])]

        for row in rows:
            excel_row = self._build_storage_row(row, numeric_columns)
            ws.append(excel_row)
            self._format_storage_row_numerics(ws, numeric_columns)

        self._apply_table_style_to_range(
            ws=ws,
            start_row=header_row,
            end_row=ws.max_row,
            column_count=column_count,
            prefix="StorageDetail",
        )
        return int(ws.max_row)

    def _build_storage_row(self, row: list[Any], numeric_columns: list[int]) -> list[Any]:
        """Construye una fila de almacenamiento con conversiones de tipo."""
        excel_row: list[Any] = []
        for col_idx, value in enumerate(row):
            if col_idx in numeric_columns:
                excel_row.append(self._convert_to_numeric(value))
            else:
                excel_row.append(str(value) if value is not None else "")
        return excel_row

    def _convert_to_numeric(self, value: Any) -> float | str:
        """Convierte un valor a numérico si es posible."""
        text_value: str = str(value) if value is not None else ""
        normalized_numeric: str = text_value.replace(",", ".").strip()
        try:
            return float(normalized_numeric)
        except ValueError:
            return text_value

    def _format_storage_row_numerics(self, ws: Worksheet, numeric_columns: list[int]) -> None:
        """Formatea las columnas numéricas de la última fila agregada."""
        for col_idx in numeric_columns:
            num_cell = ws.cell(row=ws.max_row, column=col_idx + 1)
            num_cell.alignment = Alignment(horizontal="right")
            if isinstance(num_cell.value, (int, float)):
                num_cell.number_format = "0.00"

    def _apply_table_style_to_range(
        self,
        ws: Worksheet,
        start_row: int,
        end_row: int,
        column_count: int,
        prefix: str,
        show_filters: bool = True,
    ) -> None:
        """Crea una tabla Excel y aplica el estilo configurado sobre un rango."""
        if column_count <= 0 or end_row <= start_row:
            return

        end_col: str = get_column_letter(column_count)
        ref: str = f"A{start_row}:{end_col}{end_row}"
        table_name: str = self._next_table_name(prefix)

        table = Table(displayName=table_name, ref=ref)
        table.tableStyleInfo = TableStyleInfo(
            name=self.table_style,
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=False,
        )

        if not show_filters:
            table.autoFilter = None

        ws.add_table(table)

    def _next_table_name(self, prefix: str) -> str:
        """Genera un nombre de tabla único y válido para Excel."""
        self._table_counter += 1
        safe_prefix: str = "".join(ch for ch in prefix if ch.isalnum()) or "Tbl"
        return f"{safe_prefix}{self._table_counter}"

    def _create_database_info_sheet(
        self,
        wb: Workbook,
        data_provider: DocumentationManagerPort,
        database_info_flags: list[bool],
    ) -> None:
        """Crea hoja con información de la base de datos (versión, charset, collation).

        Args:
            wb: Workbook de Excel
            data_provider: Proveedor de metadatos
            database_info_flags: [version_flag, charset_collation_flag]
        """
        self.logger.info(f"📊 Creando hoja de información de BD con flags: {database_info_flags}")
        ws = wb.create_sheet("Base de Datos")
        ws["A1"] = "Información de la Base de Datos"
        ws["A1"].font = Font(size=14, bold=True)
        ws["A2"] = f"Base de datos: {self.database}"

        try:
            info_data = GeneratorDatabaseInfoRuntime.collect_database_info_rows(
                data_provider=data_provider,
                database_info_flags=database_info_flags,
                logger=self.logger,
                include_error_rows=True,
                debug_context="para Excel",
            )
            if info_data:
                self._populate_database_info_sheet(ws, info_data)
            else:
                ws["A4"] = "No se configuró información de base de datos para mostrar"
        except DatabaseException as error:
            self.logger.exception(f"❌ Error creando hoja de información de BD: {error}")
            ws["A4"] = f"Error al obtener información: {error}"

    def _populate_database_info_sheet(self, ws: Worksheet, info_data: list[list[str]]) -> None:
        """Puebla la hoja de información de base de datos con los datos recopilados."""
        headers: list[str] = ["Propiedad", "Valor"]
        start_row: int = 4
        for col_idx, header in enumerate(headers, start=1):
            ws.cell(row=start_row, column=col_idx, value=header).font = Font(bold=True)

        current_row: int = start_row + 1
        for property_name, value in info_data:
            ws.cell(row=current_row, column=1, value=property_name)
            ws.cell(row=current_row, column=2, value=value)
            current_row += 1

        self._apply_table_style_to_range(
            ws=ws,
            start_row=start_row,
            end_row=current_row - 1,
            column_count=len(headers),
            prefix="DatabaseInfo",
        )

        ws.column_dimensions["A"].width = 25
        ws.column_dimensions["B"].width = 50

    def _prepare_enriched_data(self, tabla: str, comentario: str, data_provider: DocumentationManagerPort) -> list:
        """Prepara los datos enriquecidos de una tabla (PK, FK, Índices)."""
        columns: list[tuple[Any, ...]] = list(data_provider.get_columns(tabla))
        return GeneratorTabularRuntime.build_enriched_flat_rows_for_table(
            table_name=tabla,
            table_comment=comentario if comentario else "",
            columns=columns,
            data_provider=data_provider,
            detail_path=None,
            fk_arrow="→",
        )

    def _create_columns_charset_collation_sheet(
        self, wb: Workbook, tables: list[tuple], data_provider: DocumentationManagerPort
    ) -> None:
        """Crea hoja consolidada Charset/Collation de todas las columnas."""
        self.logger.info("Creando hoja consolidada de Charset & Collation")
        ws = wb.create_sheet("Charset & Collation")
        ws["A1"] = "Charset & Collation de Columnas"
        ws["A1"].font = Font(size=14, bold=True)
        try:
            headers: list[str] = ["Tabla", "Columna", "Charset", "Collation"]
            start_row: int = 3
            for col_idx, header in enumerate(headers, start=1):
                cell = ws.cell(row=start_row, column=col_idx, value=header)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            current_row: int = start_row + 1
            for table_row in tables:
                tabla = table_row[0]
                try:
                    charset_collation_data = data_provider.get_columns_charset_collation(tabla)
                    for col_name, charset, collation in charset_collation_data:
                        ws.cell(row=current_row, column=1, value=str(tabla))
                        ws.cell(row=current_row, column=2, value=str(col_name))
                        ws.cell(row=current_row, column=3, value=str(charset) if charset else "")
                        ws.cell(row=current_row, column=4, value=str(collation) if collation else "")
                        current_row += 1
                except DatabaseException as e:
                    self.logger.warning(f"Error obteniendo charset/collation para tabla {tabla}: {e}")
            if current_row > start_row + 1:
                self._apply_table_style_to_range(
                    ws=ws,
                    start_row=start_row,
                    end_row=current_row - 1,
                    column_count=len(headers),
                    prefix="CharsetCollation",
                )
                ws.column_dimensions["A"].width = 20
                ws.column_dimensions["B"].width = 25
                ws.column_dimensions["C"].width = 20
                ws.column_dimensions["D"].width = 20
            else:
                ws["A4"] = "No hay información de charset/collation disponible"
        except DatabaseException as error:
            self.logger.exception(f"Error creando hoja de charset/collation: {error}")
            ws["A4"] = f"Error al obtener información: {error}"
