"""El job ``deploy`` de ``.github/workflows/docs.yml`` construye el sitio antes de publicarlo.

Cada job de GitHub Actions corre en una máquina nueva: el ``site/`` que genera el job ``build`` no llega a ``deploy``, y
``site/`` está en ``.gitignore``. Si ``deploy`` publica ``./site`` sin construirlo, la publicación falla y GitHub
Pages no se actualiza (regresión de ``11fb9f8``, que cambió ``mkdocs gh-deploy`` por ``peaceiris/actions-gh-pages``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

pytestmark = pytest.mark.unit

DOCS_WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "docs.yml"


def test_deploy_job_builds_site_before_publishing_it() -> None:
    if not DOCS_WORKFLOW.is_file():
        pytest.skip(".github/workflows/docs.yml no está en el árbol")
    steps = yaml.safe_load(DOCS_WORKFLOW.read_text(encoding="utf-8"))["jobs"]["deploy"]["steps"]

    publish = next(
        (i for i, step in enumerate(steps) if str(step.get("uses", "")).startswith("peaceiris/actions-gh-pages")), None
    )
    builds = [i for i, step in enumerate(steps) if "zensical build" in str(step.get("run", ""))]

    assert publish is not None, "el job deploy ya no publica con peaceiris/actions-gh-pages: revisa este test"
    assert steps[publish]["with"]["publish_dir"] == "./site"
    assert any(i < publish for i in builds), "el job deploy publica ./site sin ejecutar antes `zensical build`"
