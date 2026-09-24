"""La navegación de ``mkdocs.yml`` y los enlaces relativos entre páginas de ``docs/`` apuntan a ficheros que existen con
el nombre exacto, distinguiendo mayúsculas.

MkDocs y Zensical comparan nombres exactos, igual que Linux en la CI. Windows no distingue mayúsculas, así que un
``installation.md`` que apunta a ``INSTALLATION.md`` funciona en local y rompe ``mkdocs build --strict`` y
``zensical build --strict`` (``.github/workflows/docs-zip-release.yml``). Este test lo detecta desde ``pytest``, en
cualquier sistema.
"""

from __future__ import annotations

import posixpath
import re

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

yaml = pytest.importorskip("yaml")

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
MKDOCS_YML = ROOT / "mkdocs.yml"

# Bloques de código (``` o ~~~, con la misma sangría al cerrar) y código en línea: sus "enlaces" son ejemplos.
_FENCE = re.compile(r"^(\s*)(```|~~~).*?^\1\2", re.S | re.M)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)


def _existing_files() -> set[str]:
    """Rutas relativas a ``docs/`` con el nombre tal como está en disco (``rglob`` lo devuelve así también en Windows)."""
    return {path.relative_to(DOCS).as_posix() for path in DOCS.rglob("*") if path.is_file()}


class _TolerantLoader(yaml.SafeLoader):  # type: ignore[misc,name-defined]
    """``mkdocs.yml`` usa etiquetas de Python (``!!python/name:…``) que ``safe_load`` no admite; aquí se ignoran."""


_TolerantLoader.add_multi_constructor("", lambda loader, suffix, node: None)


def _nav_pages(node: Any) -> Iterator[str]:
    if isinstance(node, str):
        if node.endswith(".md") and "://" not in node:
            yield node
    elif isinstance(node, list):
        for item in node:
            yield from _nav_pages(item)
    elif isinstance(node, dict):
        for value in node.values():
            yield from _nav_pages(value)


def _relative_md_links(page: Path) -> Iterator[tuple[str, str]]:
    """``(enlace tal cual, ruta resuelta relativa a docs/)`` de cada enlace relativo a un ``.md``."""
    text = _INLINE_CODE.sub("", _FENCE.sub("", page.read_text(encoding="utf-8")))
    base = page.relative_to(DOCS).parent.as_posix()
    for match in _LINK.finditer(text):
        target = match.group(1).split("#", 1)[0]
        if target and not _SCHEME.match(target) and target.endswith(".md"):
            yield match.group(1), posixpath.normpath(posixpath.join(base, target))


@pytest.fixture(scope="module")
def existing() -> set[str]:
    if not DOCS.is_dir() or not MKDOCS_YML.is_file():
        pytest.skip("docs/ o mkdocs.yml no están en el árbol")
    return _existing_files()


def test_nav_entries_exist_with_exact_case(existing: set[str]) -> None:
    config = yaml.load(MKDOCS_YML.read_text(encoding="utf-8"), Loader=_TolerantLoader)

    missing = [page for page in _nav_pages(config["nav"]) if page not in existing]

    assert missing == [], f"entradas de nav sin fichero con ese nombre exacto: {missing}"


def test_relative_links_between_pages_exist_with_exact_case(existing: set[str]) -> None:
    broken = [
        f"{page.relative_to(DOCS).as_posix()} -> {link}"
        for page in sorted(DOCS.rglob("*.md"))
        for link, resolved in _relative_md_links(page)
        if resolved not in existing
    ]

    assert broken == [], "enlaces a páginas inexistentes (o con distinto uso de mayúsculas):\n" + "\n".join(broken)
