"""La versión que muestran la portada de la documentación y el roadmap es la de ``pyproject.toml``.

Son textos fijos en Markdown: ``docs/index.md`` mostró «0.10.0» hasta la 0.18.4 porque ningún paso de la release lo
actualizaba. Este test convierte el olvido en un fallo de CI.
"""

from __future__ import annotations

import re
import tomllib

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"

# (fichero, patrón con un grupo para la versión)
VERSION_MARKERS = [
    (ROOT / "docs" / "index.md", r"\*\*Version:\*\* (\d+\.\d+\.\d+)"),
    (ROOT / "docs" / "roadmap.md", r"\*\*Versión vigente: v(\d+\.\d+\.\d+)\.\*\*"),
    (ROOT / "README.md", r"\*\*Version:\*\* (\d+\.\d+\.\d+)"),
]


def _project_version() -> str:
    with PYPROJECT.open("rb") as fh:
        return str(tomllib.load(fh)["project"]["version"])


@pytest.mark.parametrize(("path", "pattern"), VERSION_MARKERS, ids=[path.name for path, _ in VERSION_MARKERS])
def test_published_version_matches_pyproject(path: Path, pattern: str) -> None:
    if not path.is_file():
        pytest.skip(f"{path.name} no está en el árbol")
    match = re.search(pattern, path.read_text(encoding="utf-8"))

    assert match is not None, (
        f"{path.relative_to(ROOT).as_posix()}: no se encuentra la versión con el patrón {pattern!r}"
    )
    assert match.group(1) == _project_version(), (
        f"{path.relative_to(ROOT).as_posix()} muestra {match.group(1)}; pyproject.toml dice {_project_version()}"
    )
