"""``README.md`` de la documentación Markdown (5.5.0): cómo verla y qué contiene cada fichero.

Va en la raíz de la carpeta ``MARKDOWN`` (junto a ``zensical.toml``), fuera de ``docs/``: no es una página del sitio. Es
determinista (sin fecha ni rutas locales) para que la carpeta siga siendo versionable con git; solo describe los
ficheros que se han generado.
"""

from __future__ import annotations

from dataclasses import dataclass

from ....._core.i18n import Translator
from ._site import MERMAID_JS_PATH


@dataclass(frozen=True)
class ReadmeContents:
    """Qué se ha generado: el ``README.md`` describe solo eso."""

    version: str
    zensical_toml: bool
    mkdocs_yml: bool
    catalog_json: bool
    llms_txt: bool
    llms_full_txt: bool
    traceability: bool
    changes: bool
    local_mermaid: bool
    mermaid_ref: str | None
    filtered: bool


def readme_md(contents: ReadmeContents, translator: Translator | None = None) -> str:
    """Texto del ``README.md`` en el idioma de ``translator`` (5.10.0; por defecto, español)."""
    tr = translator or Translator()

    def t(key: str, **params: object) -> str:
        return tr.t(f"doc_md.readme.{key}", **params)

    lines = [
        f"# {t('title')}",
        "",
        t("intro", version=contents.version),
        "",
        f"## {t('how')}",
        "",
        f"### {t('option_editor')}",
        "",
        t("step_open"),
        t("step_preview"),
        t("step_mermaid"),
        "",
        t("hosting"),
        "",
    ]
    if contents.zensical_toml or contents.mkdocs_yml:
        lines += _site_section(contents, tr)
    file_header = f"| {tr.t('doc_md.col.file')} | {tr.t('doc_md.col.contents')} |"
    lines += [f"## {t('contents')}", "", file_header, "|---|---|"]
    lines += [f"| {path} | {text} |" for path, text in _files(contents, tr)]
    lines += ["", t("footer"), ""]
    return "\n".join(lines)


def _site_section(contents: ReadmeContents, tr: Translator) -> list[str]:
    config = "zensical.toml" if contents.zensical_toml else "mkdocs.yml"
    lines = [
        f"### {tr.t('doc_md.readme.option_site')}",
        "",
        tr.t("doc_md.readme.site_intro", config=config),
        "",
        "```bash",
        "pip install zensical",
        f"zensical serve        # {tr.t('doc_md.readme.cmd_serve')}",
        f"zensical build        # {tr.t('doc_md.readme.cmd_build')}",
        "```",
        "",
    ]
    if contents.local_mermaid:
        lines += [tr.t("doc_md.readme.mermaid_local", path=MERMAID_JS_PATH), ""]
    elif contents.mermaid_ref is not None:
        lines += [tr.t("doc_md.readme.mermaid_ref", ref=contents.mermaid_ref), ""]
    else:
        lines += [tr.t("doc_md.readme.mermaid_online"), ""]
    return lines


def _files(contents: ReadmeContents, tr: Translator) -> list[tuple[str, str]]:
    def t(key: str) -> str:
        return tr.t(f"doc_md.readme.file.{key}")

    files = [
        ("`docs/index.md`", t("index_filtered" if contents.filtered else "index")),
        ("`docs/tables/`, `docs/views/`, `docs/routines/`", t("objects")),
        ("`docs/database/`", t("database")),
    ]
    if contents.traceability:
        files.append(("`docs/traceability.md`", t("traceability")))
    if contents.changes:
        files.append(("`docs/changes.md`, `docs/changes.json`", t("changes")))
    if contents.catalog_json:
        files.append(("`docs/catalog.json`", t("catalog")))
    if contents.llms_txt:
        files.append(("`docs/llms.txt`", t("llms")))
    if contents.llms_full_txt:
        files.append(("`docs/llms-full.txt`", t("llms_full")))
    if contents.zensical_toml:
        files.append(("`zensical.toml`", t("zensical")))
    if contents.mkdocs_yml:
        files.append(("`mkdocs.yml`", t("mkdocs")))
    files.append(("`manifest.json`", t("manifest")))
    return files


__all__: list[str] = ["ReadmeContents", "readme_md"]
