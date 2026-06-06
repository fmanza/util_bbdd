"""
Plugin para generar descarga ZIP de documentación en mkdocs.
Compatible con mkdocs y zensical.
"""

import os
import zipfile

from pathlib import Path

from mkdocs.config import Config
from mkdocs.plugins import BasePlugin


class DocumentationZipPlugin(BasePlugin):
    """Plugin que genera ZIP de la documentación después del build."""

    config_options = {}

    def on_post_build(self, config: Config) -> None:  # type: ignore[override]
        """Ejecutado después del build de mkdocs."""
        site_dir = Path(config.get("site_dir", "site"))
        project_name = config.get("site_name", "documentation").replace(" ", "_")
        zip_path = site_dir / f"{project_name}.zip"

        if site_dir.exists():
            print(f"\n[ZIP] Generando descarga de documentacion: {zip_path}")

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(site_dir):
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(site_dir)
                        zipf.write(file_path, arcname=arcname)

            file_size_mb = zip_path.stat().st_size / (1024 * 1024)
            print(f"[OK] ZIP creado: {zip_path.name} ({file_size_mb:.2f} MB)")
        else:
            print(f"[WARN] Directorio {site_dir} no encontrado")
