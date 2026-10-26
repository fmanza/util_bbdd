"""Normalización centralizada de configuración de impresión para documentación."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class PrintConfigManager:
    """Centraliza la entrada `imprimir/print_config` para todos los generadores."""

    DEFAULT_TABLES: dict[str, Any] = {
        "imprimir_tablas": False,
        "ddl": False,
        "columnas": False,
        "pk": False,
        "fk": False,
        "unicas": False,
        "indices": False,
        "charset_collation": False,
    }

    DEFAULT_VIEWS: dict[str, Any] = {
        "imprimir_vistas": False,
        "ddl": False,
        "columnas": False,
    }

    DEFAULT_ROUTINES: dict[str, Any] = {
        "imprimir_procedures": False,
        "imprimir_function": False,
    }

    DEFAULT_STORAGE: dict[str, Any] = {
        "imprimir_almacenamiento": False,
    }

    #: Sección «Condiciones del motor» (``EngineReadinessAdvisor``), al final como el almacenamiento.
    DEFAULT_ENGINE_CONDITIONS: dict[str, Any] = {
        "imprimir_condiciones_motor": False,
    }

    DEFAULT_INFO_DATABASE: dict[str, Any] = {
        "imprimir_info_database": False,
        "version": False,
        "charset_collation": False,
    }

    DEFAULT_COLUMNS_CHARSET: dict[str, Any] = {
        "charset_collation": False,
    }

    DEFAULT_GRAPH: dict[str, Any] = {
        "enabled": False,
        "show_columns": True,
        "render_format": "svg",
        "direction": "both",
        "view_policy": "exclude",
        "max_depth": 1,
        "images_paginated": True,
        "max_subnodes": 10,
        "dpi": 150,
        # Aristas ortogonales (splines=ortho); False = curvas (splines=true). El enrutado ortogonal de algunos Graphviz aborta en
        # ciertos grafos (util_bbdd_web G39)
        "orthogonal_edges": True,
        "columns": {
            "mode": "relations",
            "max_items": 8,
            "show_data_types": False,
        },
        "cardinality": {
            "style": "end_markers",
            "show_constraint_name": False,
        },
        "summary": {
            "enabled": True,
        },
    }

    @staticmethod
    def normalize(imprimir: dict[str, Any] | None) -> dict[str, Any]:
        """Normaliza `imprimir` y devuelve una estructura estable."""
        if imprimir is None:
            return PrintConfigManager._build_default_normalized_config()

        if not isinstance(imprimir, dict):
            raise TypeError("imprimir/print_config debe ser de tipo dict")

        # Acepta la estructura documentada con bloque contenedor `imprimir`.
        normalized_input: dict[str, Any] = imprimir
        nested_imprimir: Any = imprimir.get("imprimir")
        if isinstance(nested_imprimir, dict):
            normalized_input = nested_imprimir

        tablas: dict[str, bool] = PrintConfigManager._normalize_boolean_section(
            normalized_input, "tablas", PrintConfigManager.DEFAULT_TABLES
        )
        vistas: dict[str, bool] = PrintConfigManager._normalize_boolean_section(
            normalized_input, "vistas", PrintConfigManager.DEFAULT_VIEWS
        )
        rutinas: dict[str, bool] = PrintConfigManager._normalize_boolean_section(
            normalized_input, "rutinas", PrintConfigManager.DEFAULT_ROUTINES
        )
        almacenamiento: dict[str, bool] = PrintConfigManager._normalize_boolean_section(
            normalized_input, "almacenamiento", PrintConfigManager.DEFAULT_STORAGE
        )
        condiciones_motor: dict[str, bool] = PrintConfigManager._normalize_boolean_section(
            normalized_input, "condiciones_motor", PrintConfigManager.DEFAULT_ENGINE_CONDITIONS
        )
        info_database: dict[str, bool] = PrintConfigManager._normalize_boolean_section(
            normalized_input, "info_database", PrintConfigManager.DEFAULT_INFO_DATABASE
        )
        columnas_charset: dict[str, bool] = PrintConfigManager._normalize_boolean_section(
            normalized_input, "columnas_charset", PrintConfigManager.DEFAULT_COLUMNS_CHARSET
        )

        graph_cfg: Any = normalized_input.get("grafo", normalized_input.get("graph", {}))
        graph: dict[str, Any] = dict(PrintConfigManager.DEFAULT_GRAPH)
        if isinstance(graph_cfg, dict):
            graph.update(graph_cfg)
            if "render_format" not in graph_cfg and "format" in graph_cfg:
                graph["render_format"] = graph_cfg.get("format")

        columns_cfg = graph.get("columns", {})
        if not isinstance(columns_cfg, dict):
            columns_cfg = {}
        columns_cfg = {
            "mode": PrintConfigManager._normalize_graph_column_mode(
                columns_cfg.get("mode", PrintConfigManager.DEFAULT_GRAPH["columns"]["mode"])
            ),
            "max_items": PrintConfigManager._to_positive_int(
                columns_cfg.get("max_items", PrintConfigManager.DEFAULT_GRAPH["columns"]["max_items"]),
                fallback=int(PrintConfigManager.DEFAULT_GRAPH["columns"]["max_items"]),
            ),
            "show_data_types": bool(
                columns_cfg.get(
                    "show_data_types",
                    PrintConfigManager.DEFAULT_GRAPH["columns"]["show_data_types"],
                )
            ),
        }

        cardinality_cfg = graph.get("cardinality", {})
        if not isinstance(cardinality_cfg, dict):
            cardinality_cfg = {}
        cardinality_cfg = {
            "style": str(cardinality_cfg.get("style", PrintConfigManager.DEFAULT_GRAPH["cardinality"]["style"])).strip()
            or str(PrintConfigManager.DEFAULT_GRAPH["cardinality"]["style"]),
            "show_constraint_name": bool(
                cardinality_cfg.get(
                    "show_constraint_name",
                    PrintConfigManager.DEFAULT_GRAPH["cardinality"]["show_constraint_name"],
                )
            ),
        }

        summary_cfg = graph.get("summary", {})
        if not isinstance(summary_cfg, dict):
            summary_cfg = {}
        summary_cfg = {
            "enabled": bool(
                summary_cfg.get(
                    "enabled",
                    PrintConfigManager.DEFAULT_GRAPH["summary"]["enabled"],
                )
            )
        }

        graph["enabled"] = bool(graph.get("enabled", PrintConfigManager.DEFAULT_GRAPH["enabled"]))
        graph["show_columns"] = bool(graph.get("show_columns", PrintConfigManager.DEFAULT_GRAPH["show_columns"]))
        graph["orthogonal_edges"] = bool(
            graph.get("orthogonal_edges", PrintConfigManager.DEFAULT_GRAPH["orthogonal_edges"])
        )
        graph["images_paginated"] = bool(
            graph.get("images_paginated", PrintConfigManager.DEFAULT_GRAPH["images_paginated"])
        )
        graph["direction"] = PrintConfigManager._normalize_graph_direction(
            graph.get("direction", PrintConfigManager.DEFAULT_GRAPH["direction"])
        )
        graph["view_policy"] = PrintConfigManager._normalize_graph_view_policy(
            graph.get("view_policy", PrintConfigManager.DEFAULT_GRAPH["view_policy"])
        )
        graph["render_format"] = PrintConfigManager._normalize_graph_render_format(
            graph.get("render_format", PrintConfigManager.DEFAULT_GRAPH["render_format"]),
            fallback=str(PrintConfigManager.DEFAULT_GRAPH["render_format"]),
        )
        graph["max_depth"] = PrintConfigManager._to_positive_int(
            graph.get("max_depth", PrintConfigManager.DEFAULT_GRAPH["max_depth"]),
            fallback=int(PrintConfigManager.DEFAULT_GRAPH["max_depth"]),
        )
        graph["max_subnodes"] = PrintConfigManager._to_positive_int(
            graph.get("max_subnodes", PrintConfigManager.DEFAULT_GRAPH["max_subnodes"]),
            fallback=int(PrintConfigManager.DEFAULT_GRAPH["max_subnodes"]),
        )
        graph["dpi"] = PrintConfigManager._to_positive_int(
            graph.get("dpi", PrintConfigManager.DEFAULT_GRAPH["dpi"]),
            fallback=int(PrintConfigManager.DEFAULT_GRAPH["dpi"]),
        )
        # Procesos dot simultáneos; None = los núcleos hasta 8 (GraphvizRelationshipGraphExt.prefetch)
        graph["workers"] = (
            None if graph.get("workers") is None else PrintConfigManager._to_positive_int(graph["workers"], fallback=1)
        )
        graph["columns"] = columns_cfg
        graph["cardinality"] = cardinality_cfg
        graph["summary"] = summary_cfg

        return {
            "tablas": tablas,
            "vistas": vistas,
            "rutinas": rutinas,
            "almacenamiento": almacenamiento,
            "condiciones_motor": condiciones_motor,
            "info_database": info_database,
            "columnas_charset": columnas_charset,
            "plantilla_word": PrintConfigManager._normalize_path_value(normalized_input.get("plantilla_word")),
            "plantilla_html": PrintConfigManager._normalize_path_value(normalized_input.get("plantilla_html")),
            "tablas_por_documento": PrintConfigManager._to_positive_int(
                normalized_input.get("tablas_por_documento", 50), fallback=50
            ),
            "table_style": PrintConfigManager._normalize_non_empty_str(
                normalized_input.get("table_style"), fallback="Table Grid"
            ),
            "html_items_por_pagina": PrintConfigManager._to_positive_int(
                normalized_input.get("html_items_por_pagina", 15),
                fallback=15,
            ),
            "grafo": graph,
        }

    @staticmethod
    def _build_default_normalized_config() -> dict[str, Any]:
        """Construye la configuración normalizada por defecto."""
        return {
            "tablas": dict(PrintConfigManager.DEFAULT_TABLES),
            "vistas": dict(PrintConfigManager.DEFAULT_VIEWS),
            "rutinas": dict(PrintConfigManager.DEFAULT_ROUTINES),
            "almacenamiento": dict(PrintConfigManager.DEFAULT_STORAGE),
            "condiciones_motor": dict(PrintConfigManager.DEFAULT_ENGINE_CONDITIONS),
            "info_database": dict(PrintConfigManager.DEFAULT_INFO_DATABASE),
            "columnas_charset": dict(PrintConfigManager.DEFAULT_COLUMNS_CHARSET),
            "plantilla_word": None,
            "plantilla_html": None,
            "tablas_por_documento": 50,
            "table_style": "Table Grid",
            "html_items_por_pagina": 15,
            "grafo": dict(PrintConfigManager.DEFAULT_GRAPH),
        }

    @staticmethod
    def _normalize_boolean_section(
        normalized_input: dict[str, Any],
        section_name: str,
        defaults: dict[str, Any],
    ) -> dict[str, bool]:
        """Normaliza una sección plana cuyos valores se interpretan como booleanos."""
        section_cfg: Any = normalized_input.get(section_name, {})
        if not isinstance(section_cfg, dict):
            section_cfg = {}
        return {key: bool(section_cfg.get(key, default_value)) for key, default_value in defaults.items()}

    @staticmethod
    def get_table_section_flags(config: dict[str, Any]) -> list[bool]:
        """Devuelve banderas de tabla en orden [ddl, columnas, pk, fk, unicas, indices]."""
        tablas: dict[str, Any] = config.get("tablas", {})
        return [
            bool(tablas.get("ddl", False)),
            bool(tablas.get("columnas", False)),
            bool(tablas.get("pk", False)),
            bool(tablas.get("fk", False)),
            bool(tablas.get("unicas", False)),
            bool(tablas.get("indices", False)),
        ]

    @staticmethod
    def get_view_section_flags(config: dict[str, Any]) -> list[bool]:
        """Devuelve banderas de vista en orden [ddl, columnas]."""
        vistas: dict[str, Any] = config.get("vistas", {})
        return [bool(vistas.get("ddl", False)), bool(vistas.get("columnas", False))]

    @staticmethod
    def get_database_info_flags(config: dict[str, Any]) -> list[bool]:
        """Devuelve banderas de información de BD en orden [version, charset_collation]."""
        info_db: dict[str, Any] = config.get("info_database", {})
        return [bool(info_db.get("version", False)), bool(info_db.get("charset_collation", False))]

    @staticmethod
    def include_engine_conditions(config: dict[str, Any]) -> bool:
        """True si la configuración normalizada pide la sección «Condiciones del motor»."""
        return bool(config.get("condiciones_motor", {}).get("imprimir_condiciones_motor", False))

    @staticmethod
    def resolve_for_word(config: dict[str, Any]) -> dict[str, Any]:
        """Resuelve opciones de ejecución para Word."""
        graph_cfg: dict[str, Any] = config.get("grafo", {})
        configured_max_subnodes = graph_cfg.get("max_subnodes")
        default_max_subnodes = PrintConfigManager.DEFAULT_GRAPH["max_subnodes"]
        word_default_max_subnodes = 5
        graph_format = PrintConfigManager._normalize_graph_render_format(
            graph_cfg.get("render_format", graph_cfg.get("format", "png")),
            fallback="png",
        )
        if graph_format == "svg":
            graph_format = "png"
        graph_options: dict[str, Any] = {
            "format": graph_format,
            "output_dir": Path(graph_cfg.get("output_dir", Path.cwd() / "_table_diagrams")),
            "show_columns": bool(graph_cfg.get("show_columns", PrintConfigManager.DEFAULT_GRAPH["show_columns"])),
            "direction": str(graph_cfg.get("direction", PrintConfigManager.DEFAULT_GRAPH["direction"])),
            "view_policy": str(graph_cfg.get("view_policy", PrintConfigManager.DEFAULT_GRAPH["view_policy"])),
            "max_depth": PrintConfigManager._to_positive_int(
                graph_cfg.get("max_depth", PrintConfigManager.DEFAULT_GRAPH["max_depth"]),
                fallback=int(PrintConfigManager.DEFAULT_GRAPH["max_depth"]),
            ),
            "images_paginated": bool(graph_cfg.get("images_paginated", True)),
            "max_subnodes": PrintConfigManager._to_positive_int(
                word_default_max_subnodes
                if configured_max_subnodes == default_max_subnodes
                else configured_max_subnodes,
                fallback=word_default_max_subnodes,
            ),
            "dpi": PrintConfigManager._to_positive_int(graph_cfg.get("dpi", 150), fallback=150),
            "workers": graph_cfg.get("workers"),
            "orthogonal_edges": bool(graph_cfg.get("orthogonal_edges", True)),
            "columns": dict(graph_cfg.get("columns", {})),
            "cardinality": dict(graph_cfg.get("cardinality", {})),
            "summary": dict(graph_cfg.get("summary", {})),
        }
        return {
            "include_tables": bool(config.get("tablas", {}).get("imprimir_tablas", False)),
            "include_views": bool(config.get("vistas", {}).get("imprimir_vistas", False)),
            "include_procedures": bool(config.get("rutinas", {}).get("imprimir_procedures", False)),
            "include_functions": bool(config.get("rutinas", {}).get("imprimir_function", False)),
            "include_storage": bool(config.get("almacenamiento", {}).get("imprimir_almacenamiento", False)),
            "include_engine_conditions": PrintConfigManager.include_engine_conditions(config),
            "include_database_info": bool(config.get("info_database", {}).get("imprimir_info_database", False)),
            "include_columns_charset": bool(config.get("columnas_charset", {}).get("charset_collation", False)),
            "table_section_flags": PrintConfigManager.get_table_section_flags(config),
            "view_section_flags": PrintConfigManager.get_view_section_flags(config),
            "database_info_flags": PrintConfigManager.get_database_info_flags(config),
            "template_path": config.get("plantilla_word"),
            "tables_per_document": int(config.get("tablas_por_documento", 50)),
            "include_diagrams": bool(graph_cfg.get("enabled", False)),
            "graph_options": graph_options,
        }

    @staticmethod
    def resolve_for_excel(config: dict[str, Any]) -> dict[str, Any]:
        """Resuelve opciones de ejecución para Excel."""
        return {
            "include_tables": bool(config.get("tablas", {}).get("imprimir_tablas", False)),
            "include_views": bool(config.get("vistas", {}).get("imprimir_vistas", False)),
            "include_procedures": bool(config.get("rutinas", {}).get("imprimir_procedures", False)),
            "include_functions": bool(config.get("rutinas", {}).get("imprimir_function", False)),
            "include_storage": bool(config.get("almacenamiento", {}).get("imprimir_almacenamiento", False)),
            "include_engine_conditions": PrintConfigManager.include_engine_conditions(config),
            "include_database_info": bool(config.get("info_database", {}).get("imprimir_info_database", False)),
            "include_columns_charset": bool(config.get("columnas_charset", {}).get("charset_collation", False)),
            "table_section_flags": PrintConfigManager.get_table_section_flags(config),
            "view_section_flags": PrintConfigManager.get_view_section_flags(config),
            "database_info_flags": PrintConfigManager.get_database_info_flags(config),
        }

    @staticmethod
    def resolve_for_html(
        config: dict[str, Any],
        output_dir: Path,
        default_template_file: Path,
    ) -> dict[str, Any]:
        """Resuelve opciones de ejecución para HTML."""
        table_section_flags: list[bool] = PrintConfigManager.get_table_section_flags(config)
        view_section_flags: list[bool] = PrintConfigManager.get_view_section_flags(config)
        database_info_flags: list[bool] = PrintConfigManager.get_database_info_flags(config)
        graph_cfg: dict[str, Any] = config.get("grafo", {})

        template_path: Path = config.get("plantilla_html") or default_template_file
        if not isinstance(template_path, Path):
            template_path = Path(str(template_path))

        diagram_options: dict[str, Any] = {
            "format": PrintConfigManager._normalize_graph_render_format(
                graph_cfg.get("render_format", graph_cfg.get("format", "svg")),
                fallback="svg",
            ),
            "output_dir": Path(graph_cfg.get("output_dir", output_dir / "graphs")),
            "show_columns": bool(graph_cfg.get("show_columns", PrintConfigManager.DEFAULT_GRAPH["show_columns"])),
            "direction": str(graph_cfg.get("direction", PrintConfigManager.DEFAULT_GRAPH["direction"])),
            "view_policy": str(graph_cfg.get("view_policy", PrintConfigManager.DEFAULT_GRAPH["view_policy"])),
            "max_depth": PrintConfigManager._to_positive_int(
                graph_cfg.get("max_depth", PrintConfigManager.DEFAULT_GRAPH["max_depth"]),
                fallback=int(PrintConfigManager.DEFAULT_GRAPH["max_depth"]),
            ),
            "images_paginated": bool(graph_cfg.get("images_paginated", True)),
            "max_subnodes": PrintConfigManager._to_positive_int(graph_cfg.get("max_subnodes", 10), fallback=10),
            "dpi": PrintConfigManager._to_positive_int(graph_cfg.get("dpi", 150), fallback=150),
            "workers": graph_cfg.get("workers"),
            "orthogonal_edges": bool(graph_cfg.get("orthogonal_edges", True)),
            "columns": dict(graph_cfg.get("columns", {})),
            "cardinality": dict(graph_cfg.get("cardinality", {})),
            "summary": dict(graph_cfg.get("summary", {})),
        }

        return {
            "include_tables": bool(config.get("tablas", {}).get("imprimir_tablas", False)),
            "include_views": bool(config.get("vistas", {}).get("imprimir_vistas", False)),
            "include_procedures": bool(config.get("rutinas", {}).get("imprimir_procedures", False)),
            "include_functions": bool(config.get("rutinas", {}).get("imprimir_function", False)),
            "include_storage": bool(config.get("almacenamiento", {}).get("imprimir_almacenamiento", False)),
            "include_engine_conditions": PrintConfigManager.include_engine_conditions(config),
            "include_database_info": bool(config.get("info_database", {}).get("imprimir_info_database", False)),
            "include_columns_charset": bool(config.get("columnas_charset", {}).get("charset_collation", False)),
            "table_section_flags": table_section_flags,
            "view_section_flags": view_section_flags,
            "database_info_flags": database_info_flags,
            "include_diagrams": bool(graph_cfg.get("enabled", False)),
            "diagram_options": diagram_options,
            "template_path": template_path,
            "html_items_per_page": PrintConfigManager._to_positive_int(
                config.get("html_items_por_pagina", 15),
                fallback=15,
            ),
        }

    @staticmethod
    def _normalize_path_value(value: Any) -> Path | None:
        if value in (None, ""):
            return None
        if isinstance(value, Path):
            return value
        return Path(str(value))

    @staticmethod
    def _to_positive_int(value: Any, fallback: int) -> int:
        try:
            parsed: int = int(value)
        except (ValueError, TypeError):
            return fallback
        return parsed if parsed > 0 else fallback

    @staticmethod
    def _normalize_non_empty_str(value: Any, fallback: str) -> str:
        text: str = str(value).strip() if value is not None else ""
        return text if text else fallback

    @staticmethod
    def _normalize_graph_direction(value: Any) -> str:
        text = str(value).strip().lower() if value is not None else ""
        return text if text in {"incoming", "outgoing", "both"} else str(PrintConfigManager.DEFAULT_GRAPH["direction"])

    @staticmethod
    def _normalize_graph_view_policy(value: Any) -> str:
        text = str(value).strip().lower() if value is not None else ""
        return text if text in {"exclude"} else str(PrintConfigManager.DEFAULT_GRAPH["view_policy"])

    @staticmethod
    def _normalize_graph_column_mode(value: Any) -> str:
        text = str(value).strip().lower() if value is not None else ""
        return (
            text
            if text in {"compact", "relations", "all"}
            else str(PrintConfigManager.DEFAULT_GRAPH["columns"]["mode"])
        )

    @staticmethod
    def _normalize_graph_render_format(value: Any, fallback: str) -> str:
        text = str(value).strip().lower() if value is not None else ""
        return text if text in {"png", "svg"} else fallback
