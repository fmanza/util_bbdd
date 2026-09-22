"""Tests de regresión DOC-02 (AUDIT_CODE 2026-09-22).

``DocumentationZipPlugin.on_post_build`` escribía el ZIP directamente en ``site_dir`` mientras
recorría ese mismo directorio con ``os.walk()``: el propio ZIP (creado/truncado en el momento de
abrir ``zipfile.ZipFile(zip_path, "w")``) quedaba dentro del árbol recorrido y se incluía a sí
mismo, produciendo una entrada autorreferencial corrupta. No existía ningún test para este plugin.
"""

from __future__ import annotations

import zipfile

from pathlib import Path

from util_bbdd.docs_build_plugin import DocumentationZipPlugin


def _make_fake_site(tmp_path: Path) -> Path:
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "index.html").write_text("<html>index</html>", encoding="utf-8")
    sub_dir = site_dir / "guides"
    sub_dir.mkdir()
    (sub_dir / "onboarding.html").write_text("<html>onboarding</html>", encoding="utf-8")
    return site_dir


def test_generated_zip_does_not_contain_itself(tmp_path: Path) -> None:
    site_dir = _make_fake_site(tmp_path)
    plugin = DocumentationZipPlugin()

    plugin.on_post_build({"site_dir": str(site_dir)})

    zip_path = site_dir / "util_bbdd-docs-latest.zip"
    assert zip_path.exists()

    with zipfile.ZipFile(zip_path) as zipf:
        names = zipf.namelist()
        assert zip_path.name not in names
        assert not any(name.endswith(".zip") for name in names)
        # No hay ninguna advertencia de zipfile sobre el propio archivo (integridad garantizada
        # por construcción: se escribió fuera de site_dir y se movió al final).
        assert zipf.testzip() is None


def test_generated_zip_contains_expected_site_files(tmp_path: Path) -> None:
    site_dir = _make_fake_site(tmp_path)
    plugin = DocumentationZipPlugin()

    plugin.on_post_build({"site_dir": str(site_dir)})

    zip_path = site_dir / "util_bbdd-docs-latest.zip"
    with zipfile.ZipFile(zip_path) as zipf:
        names = set(zipf.namelist())

    assert "index.html" in names
    assert str(Path("guides") / "onboarding.html") in names or "guides/onboarding.html" in names


def test_sha256_checksum_file_is_written_alongside_zip(tmp_path: Path) -> None:
    site_dir = _make_fake_site(tmp_path)
    plugin = DocumentationZipPlugin()

    plugin.on_post_build({"site_dir": str(site_dir)})

    zip_path = site_dir / "util_bbdd-docs-latest.zip"
    sha256_file = zip_path.with_suffix(".zip.sha256")
    assert sha256_file.exists()

    content = sha256_file.read_text(encoding="utf-8")
    assert zip_path.name in content
    assert len(content.split()[0]) == 64  # longitud de un hash SHA256 en hexadecimal


def test_missing_site_dir_does_not_raise(tmp_path: Path) -> None:
    plugin = DocumentationZipPlugin()

    # No debe lanzar ni crear nada si site_dir no existe (build fallido/cancelado antes).
    plugin.on_post_build({"site_dir": str(tmp_path / "does_not_exist")})
