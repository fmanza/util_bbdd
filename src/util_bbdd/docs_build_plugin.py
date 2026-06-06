"""
Plugin para generar descarga ZIP de documentación en mkdocs.
Compatible con mkdocs y zensical.

Incluye:
- Documentación HTML generada (site/)
- Servidor local para ejecución offline (start-server.py)
- Instrucciones README para usuarios
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
        zip_path = site_dir / "util_bbdd-docs-latest.zip"

        if site_dir.exists():
            print(f"\n[ZIP] Generando descarga de documentacion: {zip_path}")

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                # 1. Copiar documentación HTML desde site/
                for root, _, files in os.walk(site_dir):
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(site_dir)
                        zipf.write(file_path, arcname=arcname)

                # 2. Copiar script de servidor local (si existe)
                server_script = Path(__file__).parent.parent.parent / "scripts" / "start-server.py"
                if server_script.exists():
                    print(f"[ZIP] Incluyendo servidor local: {server_script.name}")
                    zipf.write(server_script, arcname="start-server.py")

                # 3. Copiar README con instrucciones offline
                readme_offline = Path(__file__).parent / "OFFLINE_README.txt"
                if readme_offline.exists():
                    print(f"[ZIP] Incluyendo instrucciones: {readme_offline.name}")
                    zipf.write(readme_offline, arcname="README_OFFLINE.txt")

            file_size_mb = zip_path.stat().st_size / (1024 * 1024)
            print(f"[OK] ZIP creado: {zip_path.name} ({file_size_mb:.2f} MB)")
        else:
            print(f"[WARN] Directorio {site_dir} no encontrado")
