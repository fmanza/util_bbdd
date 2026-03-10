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
        "format": "png",
        "show_columns": False,
        "first_level_only": True,
        "image_width_inches": 10.5,
        "images_paginated": True,
        "max_subnodes": 10,
    }

    @staticmethod
    def normalize(imprimir: dict[str, Any] | None) -> dict[str, Any]:
        """Normaliza `imprimir` y devuelve una estructura estable."""
        if imprimir is None:
            return {
                "tablas": dict(PrintConfigManager.DEFAULT_TABLES),
                "vistas": dict(PrintConfigManager.DEFAULT_VIEWS),
                "rutinas": dict(PrintConfigManager.DEFAULT_ROUTINES),
                "almacenamiento": dict(PrintConfigManager.DEFAULT_STORAGE),
                "info_database": dict(PrintConfigManager.DEFAULT_INFO_DATABASE),
                "columnas_charset": dict(PrintConfigManager.DEFAULT_COLUMNS_CHARSET),
                "plantilla_word": None,
                "plantilla_html": None,
                "tablas_por_documento": 50,
                "table_style": "Table Grid",
                "html_items_por_pagina": 15,
                "grafo": dict(PrintConfigManager.DEFAULT_GRAPH),
            }

        if not isinstance(imprimir, dict):
            raise TypeError("imprimir/print_config debe ser de tipo dict")

        tablas_cfg: Any = imprimir.get("tablas", {})
        if not isinstance(tablas_cfg, dict):
            tablas_cfg = {}
        tablas: dict[str, bool] = {
            "imprimir_tablas": bool(
                tablas_cfg.get("imprimir_tablas", PrintConfigManager.DEFAULT_TABLES["imprimir_tablas"])
            ),
            "ddl": bool(tablas_cfg.get("ddl", PrintConfigManager.DEFAULT_TABLES["ddl"])),
            "columnas": bool(tablas_cfg.get("columnas", PrintConfigManager.DEFAULT_TABLES["columnas"])),
            "pk": bool(tablas_cfg.get("pk", PrintConfigManager.DEFAULT_TABLES["pk"])),
            "fk": bool(tablas_cfg.get("fk", PrintConfigManager.DEFAULT_TABLES["fk"])),
            "unicas": bool(tablas_cfg.get("unicas", PrintConfigManager.DEFAULT_TABLES["unicas"])),
            "indices": bool(tablas_cfg.get("indices", PrintConfigManager.DEFAULT_TABLES["indices"])),
            "charset_collation": bool(
                tablas_cfg.get("charset_collation", PrintConfigManager.DEFAULT_TABLES["charset_collation"])
            ),
        }

        vistas_cfg: Any = imprimir.get("vistas", {})
        if not isinstance(vistas_cfg, dict):
            vistas_cfg = {}
        vistas: dict[str, bool] = {
            "imprimir_vistas": bool(
                vistas_cfg.get("imprimir_vistas", PrintConfigManager.DEFAULT_VIEWS["imprimir_vistas"])
            ),
            "ddl": bool(vistas_cfg.get("ddl", PrintConfigManager.DEFAULT_VIEWS["ddl"])),
            "columnas": bool(vistas_cfg.get("columnas", PrintConfigManager.DEFAULT_VIEWS["columnas"])),
        }

        rutinas_cfg: Any = imprimir.get("rutinas", {})
        if not isinstance(rutinas_cfg, dict):
            rutinas_cfg = {}
        rutinas: dict[str, bool] = {
            "imprimir_procedures": bool(
                rutinas_cfg.get(
                    "imprimir_procedures",
                    PrintConfigManager.DEFAULT_ROUTINES["imprimir_procedures"],
                )
            ),
            "imprimir_function": bool(
                rutinas_cfg.get("imprimir_function", PrintConfigManager.DEFAULT_ROUTINES["imprimir_function"])
            ),
        }

        almacenamiento_cfg: Any = imprimir.get("almacenamiento", {})
        if not isinstance(almacenamiento_cfg, dict):
            almacenamiento_cfg = {}
        almacenamiento: dict[str, bool] = {
            "imprimir_almacenamiento": bool(
                almacenamiento_cfg.get(
                    "imprimir_almacenamiento",
                    PrintConfigManager.DEFAULT_STORAGE["imprimir_almacenamiento"],
                )
            ),
        }

        info_database_cfg: Any = imprimir.get("info_database", {})
        if not isinstance(info_database_cfg, dict):
            info_database_cfg = {}
        info_database: dict[str, bool] = {
            "imprimir_info_database": bool(
                info_database_cfg.get(
                    "imprimir_info_database",
                    PrintConfigManager.DEFAULT_INFO_DATABASE["imprimir_info_database"],
                )
            ),
            "version": bool(info_database_cfg.get("version", PrintConfigManager.DEFAULT_INFO_DATABASE["version"])),
            "charset_collation": bool(
                info_database_cfg.get(
                    "charset_collation",
                    PrintConfigManager.DEFAULT_INFO_DATABASE["charset_collation"],
                )
            ),
        }

        columnas_charset_cfg: Any = imprimir.get("columnas_charset", {})
        if not isinstance(columnas_charset_cfg, dict):
            columnas_charset_cfg = {}
        columnas_charset: dict[str, bool] = {
            "charset_collation": bool(
                columnas_charset_cfg.get(
                    "charset_collation",
                    PrintConfigManager.DEFAULT_COLUMNS_CHARSET["charset_collation"],
                )
            ),
        }

        graph_cfg: Any = imprimir.get("grafo", imprimir.get("graph", {}))
        graph: dict[str, Any] = dict(PrintConfigManager.DEFAULT_GRAPH)
        if isinstance(graph_cfg, dict):
            graph.update(graph_cfg)

        graph["enabled"] = bool(graph.get("enabled", PrintConfigManager.DEFAULT_GRAPH["enabled"]))
        graph["images_paginated"] = bool(
            graph.get("images_paginated", PrintConfigManager.DEFAULT_GRAPH["images_paginated"])
        )
        graph["max_subnodes"] = PrintConfigManager._to_positive_int(
            graph.get("max_subnodes", PrintConfigManager.DEFAULT_GRAPH["max_subnodes"]),
            fallback=int(PrintConfigManager.DEFAULT_GRAPH["max_subnodes"]),
        )

        return {
            "tablas": tablas,
            "vistas": vistas,
            "rutinas": rutinas,
            "almacenamiento": almacenamiento,
            "info_database": info_database,
            "columnas_charset": columnas_charset,
            "plantilla_word": PrintConfigManager._normalize_path_value(imprimir.get("plantilla_word")),
            "plantilla_html": PrintConfigManager._normalize_path_value(imprimir.get("plantilla_html")),
            "tablas_por_documento": PrintConfigManager._to_positive_int(
                imprimir.get("tablas_por_documento", 50), fallback=50
            ),
            "table_style": PrintConfigManager._normalize_non_empty_str(
                imprimir.get("table_style"), fallback="Table Grid"
            ),
            "html_items_por_pagina": PrintConfigManager._to_positive_int(
                imprimir.get("html_items_por_pagina", 15),
                fallback=15,
            ),
            "grafo": graph,
        }

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
    def resolve_for_word(config: dict[str, Any]) -> dict[str, Any]:
        """Resuelve opciones de ejecución para Word."""
        return {
            "include_tables": bool(config.get("tablas", {}).get("imprimir_tablas", False)),
            "include_views": bool(config.get("vistas", {}).get("imprimir_vistas", False)),
            "include_procedures": bool(config.get("rutinas", {}).get("imprimir_procedures", False)),
            "include_functions": bool(config.get("rutinas", {}).get("imprimir_function", False)),
            "include_storage": bool(config.get("almacenamiento", {}).get("imprimir_almacenamiento", False)),
            "include_database_info": bool(config.get("info_database", {}).get("imprimir_info_database", False)),
            "include_columns_charset": bool(config.get("columnas_charset", {}).get("charset_collation", False)),
            "table_section_flags": PrintConfigManager.get_table_section_flags(config),
            "view_section_flags": PrintConfigManager.get_view_section_flags(config),
            "database_info_flags": PrintConfigManager.get_database_info_flags(config),
            "template_path": config.get("plantilla_word"),
            "tables_per_document": int(config.get("tablas_por_documento", 50)),
            "include_diagrams": bool(config["grafo"].get("enabled", False)),
            "graph_options": dict(config.get("grafo", {})),
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
            "format": "svg",
            "show_columns": bool(graph_cfg.get("show_columns", True)),
            "output_dir": Path(graph_cfg.get("output_dir", output_dir / "graphs")),
            "first_level_only": bool(graph_cfg.get("first_level_only", True)),
            "images_paginated": bool(graph_cfg.get("images_paginated", True)),
            "max_subnodes": PrintConfigManager._to_positive_int(graph_cfg.get("max_subnodes", 10), fallback=10),
        }

        return {
            "include_tables": bool(config.get("tablas", {}).get("imprimir_tablas", False)),
            "include_views": bool(config.get("vistas", {}).get("imprimir_vistas", False)),
            "include_procedures": bool(config.get("rutinas", {}).get("imprimir_procedures", False)),
            "include_functions": bool(config.get("rutinas", {}).get("imprimir_function", False)),
            "include_storage": bool(config.get("almacenamiento", {}).get("imprimir_almacenamiento", False)),
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
        except Exception:
            return fallback
        return parsed if parsed > 0 else fallback

    @staticmethod
    def _normalize_non_empty_str(value: Any, fallback: str) -> str:
        text: str = str(value).strip() if value is not None else ""
        return text if text else fallback
