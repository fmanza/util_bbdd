"""Test para verificar que _copy_offline_assets copia las carpetas de assets."""

from pathlib import Path

from util_bbdd.doc.infrastructure.renderers.html_generator import HtmlGenerator


def test_copy_offline_assets_includes_icons_directory(tmp_path: Path) -> None:
    """Test: Verificar que _copy_offline_assets copia la subcarpeta icons/."""
    generator = HtmlGenerator(database="demo", headers={})
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Llamar el método para copiar assets
    generator._copy_offline_assets(output_dir)

    # Verificar que la carpeta assets existe
    assets_dir = output_dir / "assets"
    assert assets_dir.exists(), f"Carpeta assets no fue creada en {output_dir}"
    assert assets_dir.is_dir(), f"{assets_dir} no es un directorio"

    # Verificar que la subcarpeta icons existe
    icons_dir = assets_dir / "icons"
    assert icons_dir.exists(), f"Carpeta icons no fue creada en {assets_dir}"
    assert icons_dir.is_dir(), f"{icons_dir} no es un directorio"

    # Verificar que los archivos SVG están presentes
    expected_icons = [
        "icon-arrow-left.svg",
        "icon-arrow-right.svg",
        "icon-csv.svg",
        "icon-tsv.svg",
        "icon-excel.svg",
        "icon-pdf.svg",
    ]
    for icon_name in expected_icons:
        icon_path = icons_dir / icon_name
        assert icon_path.exists(), f"Ícono {icon_name} no fue copiado a {icons_dir}"
        assert icon_path.is_file(), f"{icon_name} no es un archivo"
        # Verificar que el archivo no está vacío
        content = icon_path.read_text(encoding="utf-8")
        assert len(content) > 0, f"{icon_name} está vacío"
        assert "<svg" in content, f"{icon_name} no contiene SVG válido"

    # Verificar que los archivos de assets estáticos también fueron copiados
    assert (assets_dir / "sql-highlight.css").exists(), "sql-highlight.css no fue copiado"
    assert (assets_dir / "sql-highlight.js").exists(), "sql-highlight.js no fue copiado"
