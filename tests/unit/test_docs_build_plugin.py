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

    plugin.on_post_build(config={"site_dir": str(site_dir)})

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

    plugin.on_post_build(config={"site_dir": str(site_dir)})

    zip_path = site_dir / "util_bbdd-docs-latest.zip"
    with zipfile.ZipFile(zip_path) as zipf:
        names = set(zipf.namelist())

    assert "index.html" in names
    assert str(Path("guides") / "onboarding.html") in names or "guides/onboarding.html" in names


def test_sha256_checksum_file_is_written_alongside_zip(tmp_path: Path) -> None:
    site_dir = _make_fake_site(tmp_path)
    plugin = DocumentationZipPlugin()

    plugin.on_post_build(config={"site_dir": str(site_dir)})

    zip_path = site_dir / "util_bbdd-docs-latest.zip"
    sha256_file = zip_path.with_suffix(".zip.sha256")
    assert sha256_file.exists()

    content = sha256_file.read_text(encoding="utf-8")
    assert zip_path.name in content
    assert len(content.split()[0]) == 64  # longitud de un hash SHA256 en hexadecimal


def test_generated_zip_includes_offline_server_and_readme(tmp_path: Path) -> None:
    site_dir = _make_fake_site(tmp_path)

    DocumentationZipPlugin().on_post_build(config={"site_dir": str(site_dir)})

    with zipfile.ZipFile(site_dir / "util_bbdd-docs-latest.zip") as zipf:
        names = set(zipf.namelist())
    assert {"start-server.py", "README_OFFLINE.txt"} <= names


def test_zip_from_a_previous_build_is_not_packaged_again(tmp_path: Path) -> None:
    # Zensical no vacía site/ entre builds: el ZIP y el .sha256 del build anterior siguen ahí.
    site_dir = _make_fake_site(tmp_path)
    (site_dir / "util_bbdd-docs-latest.zip").write_bytes(b"zip anterior")
    (site_dir / "util_bbdd-docs-latest.zip.sha256").write_text("hash anterior", encoding="utf-8")

    DocumentationZipPlugin().on_post_build(config={"site_dir": str(site_dir)})

    with zipfile.ZipFile(site_dir / "util_bbdd-docs-latest.zip") as zipf:
        names = zipf.namelist()
    assert not any(name.startswith("util_bbdd-docs-") for name in names)


def test_missing_site_dir_does_not_raise(tmp_path: Path) -> None:
    plugin = DocumentationZipPlugin()

    # No debe lanzar ni crear nada si site_dir no existe (build fallido/cancelado antes).
    plugin.on_post_build(config={"site_dir": str(tmp_path / "does_not_exist")})


def test_on_post_build_matches_the_mkdocs_signature() -> None:
    """Hotfix (0.23.1): ``config`` es solo por nombre y de tipo ``MkDocsConfig``, como en ``BasePlugin``.

    Antes era posicional y ``Config``: Pylance lo marcaba como sobrescritura incompatible
    (``reportIncompatibleMethodOverride``); mypy no lo veía porque ``pyproject.toml`` excluye este módulo.
    """
    import inspect

    from mkdocs.config.defaults import MkDocsConfig

    # En mkdocs, BasePlugin.on_post_build solo existe para el comprobador de tipos (bajo TYPE_CHECKING); su firma es
    # ``on_post_build(self, *, config: MkDocsConfig) -> None`` (mkdocs/plugins.py).
    ours = inspect.signature(DocumentationZipPlugin.on_post_build).parameters
    assert list(ours) == ["self", "config"]
    assert ours["config"].kind is inspect.Parameter.KEYWORD_ONLY
    assert ours["config"].annotation in (MkDocsConfig, "MkDocsConfig")


def test_on_post_build_runs_through_the_mkdocs_dispatcher(tmp_path: Path) -> None:
    """mkdocs invoca los eventos con ``method(**kwargs)``: el plugin debe aceptar ``config=`` por nombre."""
    from mkdocs.plugins import PluginCollection

    site_dir = _make_fake_site(tmp_path)
    plugins = PluginCollection()
    plugins["documentation_zip"] = DocumentationZipPlugin()
    plugins.run_event("post_build", config={"site_dir": str(site_dir)})
    assert (site_dir / "util_bbdd-docs-latest.zip").exists()
