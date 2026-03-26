"""Unit tests for helper methods in HTML/Excel/Word generators."""

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

pytest.importorskip("docx")
pytest.importorskip("jinja2")
pytest.importorskip("openpyxl")

from util_bbdd.doc.database_documentation import DatabaseDocumentation
from util_bbdd.doc.diagram_legend import (
    build_diagram_direction_help,
    build_diagram_legend_payload,
    build_diagram_legend_rows,
    build_diagram_navigation_tips,
    build_hidden_levels_help,
)
from util_bbdd.doc.diagram_summary import build_diagram_summary_line, build_diagram_summary_payload
from util_bbdd.doc.excel_generator import ExcelGenerator
from util_bbdd.doc.html_generator import HtmlGenerator
from util_bbdd.doc.word_generator import WordGenerator


def test_html_generator_builds_unique_slugs_and_map() -> None:
    generator = HtmlGenerator(database="db", headers={})

    used_slugs: set[str] = set()
    first = generator._build_unique_slug("Users Table", used_slugs)
    second = generator._build_unique_slug("Users_Table", used_slugs)
    slug_map = generator._build_slug_map(["A B", "A-B", "###"])

    assert first == "users-table"
    assert second == "users-table-2"
    assert [slug_map["A B"], slug_map["A-B"], slug_map["###"]] == ["a-b", "a-b-2", "item"]


def test_html_generator_routine_helpers_default_path_and_entity_decode() -> None:
    generator = HtmlGenerator(database="db", headers={})

    default_path = generator._get_default_content_path(
        tables_index=[],
        views_index=[{"path": "views/v_users.html"}],
        procedures_index=[],
        functions_index=[],
        routines_index=[],
        storage_entries=[],
    )
    normalized = generator._normalize_routine_entry(("sp_users", "procedure", None))
    key = generator._build_routine_key(("sp_users", "procedure", ""))
    decoded = generator._decode_html_entities("&amp;amp;lt;h1&amp;amp;gt;Hi&amp;amp;lt;/h1&amp;amp;gt;")

    assert default_path == "views/v_users.html"
    assert normalized == ("sp_users", "PROCEDURE", "")
    assert key == "PROCEDURE:sp_users"
    assert decoded == "<h1>Hi</h1>"


def test_html_generator_inventory_summary_and_storage_collection_rows() -> None:
    generator = HtmlGenerator(database="db", headers={})

    summary = generator._build_inventory_summary(
        tables_index=[{"name": "t1"}],
        views_index=[{"name": "v1"}, {"name": "v2"}],
        procedures_index=[{"name": "p1"}],
        functions_index=[{"name": "f1"}, {"name": "f2"}],
        storage_report={"total_rows": 4},
    )
    storage_headers, storage_rows = generator._build_storage_collection_dataset(
        storage_entries=[{"name": "Ficheros físicos", "comment": "OK", "path": "storage/files.html"}],
        storage_report={"sections": [{"status": "ok", "headers": ["Archivo"], "rows": [["a"], ["b"], ["c"]]}]},
    )

    assert summary == [
        {"label": "Tablas", "count": 1, "accent": "tables", "collection_key": "tables"},
        {"label": "Vistas", "count": 2, "accent": "views", "collection_key": "views"},
        {"label": "Procedures", "count": 1, "accent": "procedures", "collection_key": "procedures"},
        {"label": "Funciones", "count": 2, "accent": "functions", "collection_key": "functions"},
        {"label": "Almacenamiento", "count": 4, "accent": "storage", "collection_key": "storage"},
    ]
    assert storage_headers == ["Sección", "Estado", "Archivo", "Mensaje", "Detalle"]
    assert storage_rows == [
        ["Ficheros físicos", "ok", "a", "OK", "storage/files.html"],
        ["Ficheros físicos", "ok", "b", "OK", "storage/files.html"],
        ["Ficheros físicos", "ok", "c", "OK", "storage/files.html"],
    ]


def test_html_generator_builds_table_collection_dataset_like_excel_flat_sheet() -> None:
    generator = HtmlGenerator(
        database="db",
        headers={
            "FLAT": [
                "Tabla",
                "Comentario",
                "Campo",
                "Tipo",
                "Nulo",
                "Clave",
                "Por defecto",
                "Extra",
                "Comentario columna",
            ]
        },
    )

    class _Provider:
        db_type = "mariadb"

        def get_columns(self, table_name: str) -> list[tuple[str, ...]]:
            assert table_name == "users"
            return [
                ("id", "INT", "NO", "PRI", "", "auto_increment", "Identificador"),
                ("name", "VARCHAR(100)", "YES", "", None, "", "Nombre"),
            ]

    headers, rows = generator._build_table_collection_dataset(
        tables_index=[{"name": "users", "comment": "Usuarios", "path": "tables/users.html"}],
        data_provider=_Provider(),
    )

    assert headers == [
        "Tabla",
        "Comentario",
        "Campo",
        "Tipo",
        "Nulo",
        "Clave",
        "Por defecto",
        "Extra",
        "Comentario columna",
        "Detalle",
    ]
    assert rows == [
        ["users", "Usuarios", "id", "INT", "NO", "PRI", "", "auto_increment", "Identificador", "tables/users.html"],
        ["users", "Usuarios", "name", "VARCHAR(100)", "YES", "", "", "", "Nombre", "tables/users.html"],
    ]


def test_html_generator_get_flat_base_data_uses_expected_shape_per_db_type() -> None:
    generator = HtmlGenerator(database="db", headers={})

    assert generator._get_flat_base_data(
        ("id", "INT", "NO", "PRI", None, "auto_increment", "Identificador", "ignored"),
        "mariadb",
    ) == ["id", "INT", "NO", "PRI", "", "auto_increment", "Identificador"]

    assert generator._get_flat_base_data(
        ("id", "INT", "NO", "PRI", None, "", "100", "0", "Identificador", "ignored"),
        "sqlserver",
    ) == ["id", "INT", "NO", "PRI", "", "", "100", "0", "Identificador"]

    assert generator._get_flat_base_data(
        ("ID", "NUMBER", "N", None, 22, 0, 0, "Comentario", "ignored"),
        "oracle",
    ) == ["ID", "NUMBER", "N", "", "22", "0", "0", "Comentario"]


def test_html_generator_builds_view_collection_dataset_with_one_row_per_column() -> None:
    generator = HtmlGenerator(
        database="db",
        headers={"COLUMNAS": ["Campo", "Tipo", "Nulo", "Por defecto", "Longitud", "Precisión", "Escala", "Comentario"]},
    )

    class _Provider:
        db_type = "oracle"

        def get_columns(self, view_name: str) -> list[tuple[Any, ...]]:
            assert view_name == "v_users"
            return [
                ("ID", "NUMBER", "N", None, 22, 0, 0, "Identificador"),
                ("NAME", "VARCHAR2", "Y", None, 100, None, None, "Nombre"),
            ]

    headers, rows = generator._build_view_collection_dataset(
        views_index=[{"name": "v_users", "comment": "Vista usuarios", "path": "views/v_users.html"}],
        data_provider=_Provider(),
    )

    assert headers == [
        "Vista",
        "Comentario",
        "Campo",
        "Tipo",
        "Nulo",
        "Por defecto",
        "Longitud",
        "Precisión",
        "Escala",
        "Comentario",
        "Detalle",
    ]
    assert rows == [
        ["v_users", "Vista usuarios", "ID", "NUMBER", "N", "", "22", "0", "0", "Identificador", "views/v_users.html"],
        ["v_users", "Vista usuarios", "NAME", "VARCHAR2", "Y", "", "100", "", "", "Nombre", "views/v_users.html"],
    ]


def test_html_generator_builds_routine_collection_dataset_with_one_row_per_parameter() -> None:
    generator = HtmlGenerator(
        database="db",
        headers={"PARAMETROS_RUTINA": ["Modo", "Parámetro", "Tipo", "Valor por defecto", "Posición"]},
    )

    class _Provider:
        def get_routine_parameters(self, routine_name: str, routine_type: str) -> list[tuple[Any, ...]]:
            if routine_name == "sp_sync":
                return [
                    ("IN", "p_id", "INTEGER", None, 1),
                    ("OUT", "p_total", "INTEGER", None, 2),
                ]
            return []

    headers, rows = generator._build_routine_collection_dataset(
        routines_index=[
            {"name": "sp_sync", "routine_type": "PROCEDURE", "comment": "Sincroniza", "path": "routines/sp_sync.html"},
            {"name": "f_total", "routine_type": "FUNCTION", "comment": "Calcula", "path": "routines/f_total.html"},
        ],
        data_provider=_Provider(),
    )

    assert headers == [
        "Rutina",
        "Tipo rutina",
        "Comentario",
        "Modo",
        "Parámetro",
        "Tipo",
        "Valor por defecto",
        "Posición",
        "Detalle",
    ]
    assert rows == [
        ["sp_sync", "PROCEDURE", "Sincroniza", "IN", "p_id", "INTEGER", "", "1", "routines/sp_sync.html"],
        ["sp_sync", "PROCEDURE", "Sincroniza", "OUT", "p_total", "INTEGER", "", "2", "routines/sp_sync.html"],
        ["f_total", "FUNCTION", "Calcula", "", "", "", "", "", "routines/f_total.html"],
    ]


def test_excel_generator_style_normalization_split_and_numeric_conversion() -> None:
    aliased = ExcelGenerator(database="db", headers={}, table_style="Medium Shading 2 Accent 1")
    valid_style = ExcelGenerator(database="db", headers={}, table_style="TableStyleDark1")
    fallback = ExcelGenerator(database="db", headers={}, table_style="MyInvalidStyle")

    routines = [
        ("p_sync", "PROCEDURE", "ok"),
        ("f_total", "function", "ok"),
        ("unknown", "TRIGGER", "ignored"),
        ("default_func", None, ""),
    ]
    procedures, functions = fallback._split_routines_by_type(routines)

    assert aliased.table_style == "TableStyleMedium2"
    assert valid_style.table_style == "TableStyleDark1"
    assert fallback.table_style == "TableStyleMedium2"
    assert procedures == [routines[0]]
    assert functions == [routines[1], routines[3]]
    assert fallback._safe_tuple_value(("A", None), 0) == "A"
    assert fallback._safe_tuple_value(("A", None), 1) == ""
    assert fallback._safe_tuple_value(("A",), 3) == ""
    assert fallback._convert_to_numeric(" 1,50 ") == pytest.approx(1.5)
    assert fallback._convert_to_numeric("abc") == "abc"
    assert fallback._convert_to_numeric(None) == ""


def test_excel_and_word_inventory_summary_helpers_use_storage_totals() -> None:
    excel = ExcelGenerator(database="db", headers={})
    word = WordGenerator(database="db", headers={})

    class _Provider:
        def get_storage_inventory_report(self) -> dict[str, Any]:
            return {"sections": [{"rows": [[1], [2]]}, {"rows": [[3]]}]}

    provider = _Provider()

    assert excel._get_storage_total_rows(provider) == 3
    assert word._get_storage_total_rows(provider) == 3


def test_word_generator_chunking_output_file_and_routine_split() -> None:
    generator = WordGenerator(database="db", headers={})
    tables = [(f"table_{idx}", "") for idx in range(120)]

    chunks = generator._chunk_tables(tables=tables, tables_per_document=0)
    single_output = generator._build_output_file_for_chunk(Path("report.docx"), chunk_index=1, total_chunks=1)
    multi_output = generator._build_output_file_for_chunk(Path("report.docx"), chunk_index=2, total_chunks=3)
    normalized = generator._normalize_routine_entry((None, None, None))
    procedures, functions = generator._split_routines_by_type(
        [("p_sync", "procedure", ""), ("f_total", "FUNCTION", ""), ("x", "TRIGGER", "")]
    )

    assert [len(chunk) for chunk in chunks] == [50, 50, 20]
    assert single_output == Path("report.docx")
    assert multi_output == Path("report_part2.docx")
    assert normalized == ("", "FUNCTION", "")
    assert procedures == [("p_sync", "procedure", "")]
    assert functions == [("f_total", "FUNCTION", "")]


def test_word_generator_builds_diagram_summary_payload_with_hidden_levels() -> None:
    generator = WordGenerator(database="db", headers={})

    class _GraphGenerator:
        class _Document:
            max_depth = 2
            total_outgoing_levels = 3
            total_incoming_levels = 1

            class _Hidden:
                outgoing_hidden_levels = 1
                incoming_hidden_levels = 0

            hidden_levels = _Hidden()

        def build_graph_document(self, **kwargs: Any) -> Any:
            return self._Document()

    summary = generator._build_diagram_summary_payload(
        tabla="users",
        graph_generator=_GraphGenerator(),
        diagram_options={"max_depth": 2, "direction": "both", "summary": {"enabled": True}},
    )

    assert (
        build_diagram_summary_line(summary)
        == "Profundidad visible: 2 | Salida visible: 2 de 3 | Entrada visible: 1 de 1"
    )
    assert summary["has_hidden_outgoing_levels"] is True
    assert summary["outgoing_hidden_help"] == build_hidden_levels_help("outgoing")


def test_word_generator_builds_summary_from_precomputed_document_without_rebuilding() -> None:
    generator = WordGenerator(database="db", headers={})

    class _GraphGenerator:
        def build_graph_document(self, **kwargs: Any) -> Any:
            raise AssertionError("No debe reconstruir el documento si ya fue precalculado")

    class _Document:
        max_depth = 1
        total_outgoing_levels = 2
        total_incoming_levels = 1

        class _Hidden:
            outgoing_hidden_levels = 1
            incoming_hidden_levels = 1

        hidden_levels = _Hidden()

    summary = generator._build_diagram_summary_payload(
        tabla="users",
        graph_generator=_GraphGenerator(),
        diagram_options={"max_depth": 1, "direction": "both", "summary": {"enabled": True}},
        document=_Document(),
    )

    assert (
        build_diagram_summary_line(summary)
        == "Profundidad visible: 1 | Salida visible: 1 de 2 | Entrada visible: 0 de 1"
    )
    assert summary["incoming_hidden_help"] == build_hidden_levels_help("incoming")


def test_word_generator_omits_diagram_summary_when_disabled() -> None:
    generator = WordGenerator(database="db", headers={})

    class _GraphGenerator:
        class _Document:
            max_depth = 1
            total_outgoing_levels = 1
            total_incoming_levels = 0

            class _Hidden:
                outgoing_hidden_levels = 0
                incoming_hidden_levels = 0

            hidden_levels = _Hidden()

        def build_graph_document(self, **kwargs: Any) -> Any:
            return self._Document()

    summary = generator._build_diagram_summary_payload(
        tabla="users",
        graph_generator=_GraphGenerator(),
        diagram_options={"max_depth": 1, "direction": "both", "summary": {"enabled": False}},
    )

    assert summary == {}


def test_word_generator_adds_summary_paragraph_to_document() -> None:
    generator = WordGenerator(database="db", headers={})
    document = generator._initialize_document(template_path=None)

    generator._add_diagram_summary_paragraph(
        document=document,
        summary_payload=build_diagram_summary_payload(
            max_depth=2,
            total_outgoing_levels=3,
            total_incoming_levels=1,
            visible_outgoing_levels=1,
            visible_incoming_levels=1,
            hidden_outgoing_levels=2,
            hidden_incoming_levels=0,
        ),
    )

    paragraph_texts = [paragraph.text for paragraph in document.paragraphs]

    assert any(
        "Profundidad visible: 2 | Salida visible: 1 de 3 | Entrada visible: 1 de 1" in text for text in paragraph_texts
    )
    assert any(build_hidden_levels_help("outgoing") in text for text in paragraph_texts)
    assert any("salida y entrada por separado" in text for text in paragraph_texts)


def test_shared_diagram_summary_payload_matches_html_contract() -> None:
    summary = build_diagram_summary_payload(
        max_depth=3,
        total_outgoing_levels=2,
        total_incoming_levels=1,
        visible_outgoing_levels=1,
        visible_incoming_levels=1,
        hidden_outgoing_levels=1,
        hidden_incoming_levels=0,
    )

    assert summary["title"] == "Resumen de niveles"
    assert (
        build_diagram_summary_line(summary)
        == "Profundidad visible: 3 | Salida visible: 1 de 2 | Entrada visible: 1 de 1"
    )
    assert summary["has_any_hidden_levels"] is True
    assert summary["outgoing_hidden_help"] == build_hidden_levels_help("outgoing")


def test_shared_diagram_reading_helpers_match_html_contract() -> None:
    assert build_diagram_direction_help("outgoing") == (
        "Relaciones de salida hacia tablas hijas o dependientes de la tabla actual."
    )
    assert build_diagram_direction_help("incoming") == (
        "Relaciones de entrada desde tablas padre o referenciadoras hacia la tabla actual."
    )
    assert build_hidden_levels_help("outgoing") == (
        "Salida oculta: niveles de tablas hijas o dependientes que existen en el grafo, "
        "pero no se muestran por el límite de profundidad visible."
    )
    assert build_hidden_levels_help("incoming", hidden_levels=2) == (
        "Entrada oculta: 2 nivel(es) de tablas padre o referenciadoras que existen en el grafo, "
        "pero no se muestran por el límite de profundidad visible."
    )
    assert build_diagram_navigation_tips(
        visible_outgoing_levels=1,
        visible_incoming_levels=1,
        hidden_outgoing_levels=0,
        hidden_incoming_levels=1,
    ) == [
        "Revisa salida y entrada por separado para evitar mezclar dependencias hijas con tablas referenciadoras.",
        "Hay niveles no visibles por límite de profundidad: usa el resumen para decidir si necesitas ampliar el alcance del diagrama.",
    ]


def test_word_generator_adds_diagram_legend_section_with_expected_rows() -> None:
    generator = WordGenerator(database="db", headers={})
    document = generator._initialize_document(template_path=None)

    generator._add_diagram_legend_section(document=document)

    paragraph_texts = [paragraph.text for paragraph in document.paragraphs]
    table_texts = [cell.text for table in document.tables for row in table.rows for cell in row.cells]

    assert any("Leyenda visual" == text for text in paragraph_texts)
    assert "Salida" in table_texts
    assert "Entrada" in table_texts
    assert "Entidad" in table_texts
    assert "Asociación" in table_texts
    assert "Jerarquía" in table_texts
    assert "FK" in table_texts
    assert any("Los marcadores de cardinalidad se muestran separados" in text for text in paragraph_texts)
    assert all("Notas de lectura" != text for text in paragraph_texts)


def test_shared_diagram_legend_rows_match_html_payload_contract() -> None:
    payload = build_diagram_legend_payload()
    rows = build_diagram_legend_rows(payload)

    assert payload["title"] == "Leyenda visual"
    assert rows[0] == [
        "Dirección",
        payload["direction_items"][0]["label"],
        payload["direction_items"][0]["description"],
    ]
    assert rows[1] == [
        "Dirección",
        payload["direction_items"][1]["label"],
        payload["direction_items"][1]["description"],
    ]
    assert rows[-1] == [
        "Tipo de relación",
        payload["relation_type_items"][0]["label"],
        payload["relation_type_items"][0]["description"],
    ]


def test_word_generator_inserts_diagram_legend_before_inventory_and_tables(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    generator = WordGenerator(database="db", headers={})
    call_order: list[str] = []

    class _Provider:
        imprimir_config: dict[str, Any] = {}

    monkeypatch.setattr(generator, "_configure_document_orientation", lambda *args, **kwargs: None)
    monkeypatch.setattr(generator, "_add_diagram_legend_section", lambda *args, **kwargs: call_order.append("legend"))
    monkeypatch.setattr(generator, "_add_inventory_overview", lambda *args, **kwargs: call_order.append("inventory"))
    monkeypatch.setattr(generator, "_add_tables_content", lambda *args, **kwargs: call_order.append("tables"))
    monkeypatch.setattr(generator, "_add_views_content", lambda *args, **kwargs: None)
    monkeypatch.setattr(generator, "_add_routines_content", lambda *args, **kwargs: None)
    monkeypatch.setattr(generator, "_build_output_file_for_chunk", lambda output_file, idx, total_chunks: output_file)

    from util_bbdd.doc.word_generator import DocumentChunkConfig

    generator._generate_single_document_chunk(
        idx=1,
        total_chunks=1,
        all_tables=[("users", "")],
        table_chunk=[("users", "")],
        views=[],
        routines=[],
        data_provider=_Provider(),
        output_file=tmp_path / "report.docx",
        config=DocumentChunkConfig(
            include_tables=True,
            include_views=False,
            include_procedures=False,
            include_functions=False,
            include_storage=False,
            table_section_flags=[False, False, False, False, False, False],
            view_section_flags=[False, False],
            include_diagrams=True,
        ),
        graph_generator=None,
    )

    assert call_order == ["legend", "inventory", "tables"]


def test_html_generator_generate_document_builds_graph_generator_when_none(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    generator = HtmlGenerator(database="db", headers={})
    sentinel = object()
    captured: dict[str, Any] = {}

    class _Provider:
        imprimir_config: dict[str, Any] = {}

    monkeypatch.setattr(
        generator,
        "_resolve_print_config",
        lambda *args, **kwargs: {
            "include_tables": True,
            "include_views": False,
            "include_procedures": False,
            "include_functions": False,
            "include_storage": False,
            "include_database_info": False,
            "template_path": generator.default_template_file,
            "include_diagrams": True,
            "diagram_options": {"max_depth": 2, "direction": "both"},
        },
    )
    monkeypatch.setattr(generator, "_prepare_output_directories", lambda *args, **kwargs: None)
    monkeypatch.setattr(generator, "_setup_templates", lambda *args, **kwargs: (object(), object(), object()))
    monkeypatch.setattr(generator, "_process_database_info", lambda **kwargs: [])
    monkeypatch.setattr(generator, "_build_slug_maps_and_filters", lambda *args, **kwargs: ({}, {}, [], {}, {}))
    monkeypatch.setattr(generator, "_build_graph_generator", lambda *args, **kwargs: sentinel)
    monkeypatch.setattr(
        generator,
        "_process_tables",
        lambda *args, **kwargs: captured.setdefault("graph_generator", kwargs.get("graph_generator") or args[8]) or [],
    )
    monkeypatch.setattr(generator, "_process_views", lambda *args, **kwargs: [])
    monkeypatch.setattr(generator, "_process_routines", lambda *args, **kwargs: [])
    monkeypatch.setattr(generator, "_process_storage", lambda *args, **kwargs: [])
    monkeypatch.setattr(generator, "_render_collection_pages", lambda *args, **kwargs: {})
    monkeypatch.setattr(generator, "_render_index_page", lambda *args, **kwargs: None)

    generator.generate_document([], [], [], _Provider(), tmp_path)

    assert captured["graph_generator"] is sentinel


def test_html_generator_generate_document_reuses_injected_graph_generator(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    generator = HtmlGenerator(database="db", headers={})
    sentinel = object()
    captured: dict[str, Any] = {}

    class _Provider:
        imprimir_config: dict[str, Any] = {}

    def _forbid_graph_builder(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("No debe reconstruir el generador")

    monkeypatch.setattr(
        generator,
        "_resolve_print_config",
        lambda *args, **kwargs: {
            "include_tables": True,
            "include_views": False,
            "include_procedures": False,
            "include_functions": False,
            "include_storage": False,
            "include_database_info": False,
            "template_path": generator.default_template_file,
            "include_diagrams": True,
            "diagram_options": {"max_depth": 2, "direction": "both"},
        },
    )
    monkeypatch.setattr(generator, "_prepare_output_directories", lambda *args, **kwargs: None)
    monkeypatch.setattr(generator, "_setup_templates", lambda *args, **kwargs: (object(), object(), object()))
    monkeypatch.setattr(generator, "_process_database_info", lambda **kwargs: [])
    monkeypatch.setattr(generator, "_build_slug_maps_and_filters", lambda *args, **kwargs: ({}, {}, [], {}, {}))
    monkeypatch.setattr(
        generator,
        "_build_graph_generator",
        _forbid_graph_builder,
    )
    monkeypatch.setattr(
        generator,
        "_process_tables",
        lambda *args, **kwargs: captured.setdefault("graph_generator", kwargs.get("graph_generator") or args[8]) or [],
    )
    monkeypatch.setattr(generator, "_process_views", lambda *args, **kwargs: [])
    monkeypatch.setattr(generator, "_process_routines", lambda *args, **kwargs: [])
    monkeypatch.setattr(generator, "_process_storage", lambda *args, **kwargs: [])
    monkeypatch.setattr(generator, "_render_collection_pages", lambda *args, **kwargs: {})
    monkeypatch.setattr(generator, "_render_index_page", lambda *args, **kwargs: None)

    generator.generate_document([], [], [], _Provider(), tmp_path, graph_generator=cast(Any, sentinel))

    assert captured["graph_generator"] is sentinel


def test_word_generator_generate_document_builds_graph_generator_when_none(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    generator = WordGenerator(database="db", headers={})
    sentinel = object()
    captured: dict[str, Any] = {}

    class _Provider:
        imprimir_config: dict[str, Any] = {}

    monkeypatch.setattr(generator, "_build_graph_generator", lambda *args, **kwargs: sentinel)
    monkeypatch.setattr(
        generator,
        "_generate_single_document_chunk",
        lambda *args, **kwargs: captured.setdefault("graph_generator", kwargs["graph_generator"]),
    )

    generator.generate_document(
        [], [], [], _Provider(), tmp_path / "report.docx", print_config={"grafo": {"enabled": True}}
    )

    assert captured["graph_generator"] is sentinel


def test_word_generator_generate_document_reuses_injected_graph_generator(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    generator = WordGenerator(database="db", headers={})
    sentinel = object()
    captured: dict[str, Any] = {}

    class _Provider:
        imprimir_config: dict[str, Any] = {}

    def _forbid_graph_builder(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("No debe reconstruir el generador")

    monkeypatch.setattr(
        generator,
        "_build_graph_generator",
        _forbid_graph_builder,
    )
    monkeypatch.setattr(
        generator,
        "_generate_single_document_chunk",
        lambda *args, **kwargs: captured.setdefault("graph_generator", kwargs["graph_generator"]),
    )

    generator.generate_document(
        [],
        [],
        [],
        _Provider(),
        tmp_path / "report.docx",
        print_config={"grafo": {"enabled": True}},
        graph_generator=cast(Any, sentinel),
    )

    assert captured["graph_generator"] is sentinel


@pytest.mark.skipif("matplotlib" not in globals(), reason="matplotlib no disponible en entorno de tests")
def test_matplotlib_relationship_graph_uses_multilevel_document() -> None:
    from util_bbdd.analysis.matplotlib_graph import MatplotlibRelationshipGraph
    from util_bbdd.managers import SyncDatabaseManager

    class _FakeDbManager:
        def __init__(self) -> None:
            self.db_type = "postgresql"
            self.database = "db"

        def get_tables(self) -> list[tuple[str]]:
            return [("users",), ("orders",), ("payments",)]

        def get_foreign_keys(self, table_name: str) -> list[tuple[str, str, str, str]]:
            mapping = {
                "users": [],
                "orders": [("fk_orders_user", "user_id", "users", "id")],
                "payments": [("fk_payments_order", "order_id", "orders", "id")],
            }
            return mapping.get(table_name, [])

        def get_query_context_database(self) -> str:
            return self.database

    graph = MatplotlibRelationshipGraph(cast(SyncDatabaseManager, _FakeDbManager()), max_depth=2, direction="incoming")
    document = graph.build_graph_document("users", max_depth=2, direction="incoming")

    assert document.total_incoming_levels == 2
    assert {relation.constraint_name for relation in document.relations} == {"fk_orders_user", "fk_payments_order"}


def test_database_documentation_parses_mariadb_temp_data_file_path() -> None:
    rows = DatabaseDocumentation._parse_mariadb_temp_data_file_path_rows(
        "innodb_temp_data_file_path",
        "ibtmp1:12M:autoextend:max:5G",
    )

    assert rows == [
        [
            "innodb_temp_data_file_path",
            "ibtmp1",
            12.0,
            "Si",
            5120.0,
            "ibtmp1:12M:autoextend:max:5G",
        ]
    ]


def test_database_documentation_parse_mariadb_size_to_mb_accepts_units() -> None:
    assert DatabaseDocumentation._parse_mariadb_size_to_mb("64K") == pytest.approx(0.06)
    assert DatabaseDocumentation._parse_mariadb_size_to_mb("12M") == pytest.approx(12.0)
    assert DatabaseDocumentation._parse_mariadb_size_to_mb("2G") == pytest.approx(2048.0)


def test_database_documentation_formats_mariadb_files_access_error() -> None:
    doc: DatabaseDocumentation = DatabaseDocumentation.__new__(DatabaseDocumentation)
    doc_any = cast(Any, doc)
    build_error_section = cast(
        Callable[[str, str, str], dict[str, Any]],
        object.__getattribute__(doc_any, "_DatabaseDocumentation__build_mariadb_temp_tablespaces_error_section"),
    )

    section: dict[str, Any] = build_error_section(
        "temp_tablespaces",
        "Temp tablespaces",
        "Access denied to information_schema.FILES for user",
    )

    assert section["status"] == "error"
    assert "Sin acceso a information_schema.FILES" in section["message"]


def test_database_documentation_storage_specs_add_sqlite_summary_section() -> None:
    doc: DatabaseDocumentation = DatabaseDocumentation.__new__(DatabaseDocumentation)
    doc.db_manager = cast(Any, type("Manager", (), {"db_type": "sqlite"})())

    specs = doc._build_storage_query_specs()

    assert specs == [
        ("ficheros_fisicos", "Ficheros físicos"),
        ("sqlite_file_summary", "Ficheros físicos - resumen SQLite"),
        ("temp_tablespaces", "Temp tablespaces"),
    ]
