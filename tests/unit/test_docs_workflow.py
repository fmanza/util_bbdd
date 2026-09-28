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

WORKFLOWS_DIR = Path(__file__).resolve().parents[2] / ".github" / "workflows"
DOCS_WORKFLOW = WORKFLOWS_DIR / "docs.yml"


def test_every_workflow_is_valid_yaml() -> None:
    # GitHub no carga un workflow con YAML inválido y no avisa en el push: docs-zip-release.yml nunca se ejecutó por un
    # `name:` sin comillas con «: » dentro (c14ed54).
    workflows = sorted(WORKFLOWS_DIR.glob("*.y*ml"))
    if not workflows:
        pytest.skip(".github/workflows/ no está en el árbol")
    invalid = []
    for workflow in workflows:
        try:
            yaml.safe_load(workflow.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            invalid.append(f"{workflow.name}: {str(exc).splitlines()[0]}")
    assert invalid == [], f"workflows con YAML inválido: {invalid}"


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


def test_deploy_job_adds_offline_zip_between_build_and_publish() -> None:
    # Zensical no ejecuta el plugin documentation_zip: sin este paso el sitio publicado no lleva el ZIP offline.
    if not DOCS_WORKFLOW.is_file():
        pytest.skip(".github/workflows/docs.yml no está en el árbol")
    steps = yaml.safe_load(DOCS_WORKFLOW.read_text(encoding="utf-8"))["jobs"]["deploy"]["steps"]
    runs = [str(step.get("run", "")) for step in steps]

    build = next(i for i, run in enumerate(runs) if "zensical build" in run)
    add_zip = next((i for i, run in enumerate(runs) if "build_docs_zip.py" in run and "--in-site" in run), None)
    publish = next(i for i, step in enumerate(steps) if str(step.get("uses", "")).startswith("peaceiris/"))

    assert add_zip is not None, "el job deploy no añade el ZIP offline al sitio"
    assert build < add_zip < publish
