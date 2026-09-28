"""Tests de ``scripts/build_docs_zip.py``: el ZIP offline de Releases y el que se publica dentro del sitio.

Antes, el script comprimía solo ``site/`` (``shutil.make_archive``) y el ZIP de GitHub Releases salía sin
``start-server.py`` ni ``README_OFFLINE.txt``, que ``docs/downloads.md`` pide usar. Además, Zensical no ejecuta el
plugin ``documentation_zip``, así que el sitio publicado no llevaba ZIP: ``--in-site`` lo genera tras el build.
"""

from __future__ import annotations

import importlib.util
import sys
import zipfile

from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.unit

pytest.importorskip("mkdocs")  # el script empaqueta con util_bbdd.docs_build_plugin, que depende de mkdocs

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_docs_zip.py"
OFFLINE_EXTRAS = {"start-server.py", "README_OFFLINE.txt"}


@pytest.fixture(scope="module")
def script() -> ModuleType:
    if not SCRIPT.exists():
        pytest.skip("scripts/build_docs_zip.py no está en el árbol")
    spec = importlib.util.spec_from_file_location("build_docs_zip", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_docs_zip"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def site_dir(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    (site / "guides").mkdir(parents=True)
    (site / "index.html").write_text("<html>index</html>", encoding="utf-8")
    (site / "guides" / "onboarding.html").write_text("<html>onboarding</html>", encoding="utf-8")
    return site


def test_release_zip_includes_site_and_offline_extras(script: ModuleType, site_dir: Path, tmp_path: Path) -> None:
    archive = script._zip(site_dir, tmp_path / "dist", "9.9.9")

    assert archive.name == "util_bbdd-docs-9.9.9.zip"
    with zipfile.ZipFile(archive) as zipf:
        names = set(zipf.namelist())
    assert {"index.html", "guides/onboarding.html"} <= names
    assert OFFLINE_EXTRAS <= names


def test_in_site_zip_is_written_inside_site_without_containing_itself(script: ModuleType, site_dir: Path) -> None:
    archive = script._zip_in_site(site_dir)

    assert archive == site_dir / "util_bbdd-docs-latest.zip"
    assert (site_dir / "util_bbdd-docs-latest.zip.sha256").is_file()
    assert not (site_dir / "CHECKSUMS.txt").exists()
    with zipfile.ZipFile(archive) as zipf:
        names = zipf.namelist()
        assert zipf.testzip() is None
    assert OFFLINE_EXTRAS <= set(names)
    assert not any(name.startswith("util_bbdd-docs-") for name in names)
