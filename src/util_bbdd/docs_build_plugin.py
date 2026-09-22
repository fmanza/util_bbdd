"""
Plugin para generar descarga ZIP de documentación en mkdocs.
Compatible con mkdocs y zensical.

Incluye:
- Documentación HTML generada (site/)
- Servidor local para ejecución offline (start-server.py)
- Instrucciones README para usuarios
- Checksum SHA256 para validación de integridad
"""

import hashlib
import os
import shutil
import tempfile
import zipfile

from pathlib import Path
from typing import Any, ClassVar

from mkdocs.config import Config
from mkdocs.plugins import BasePlugin


class DocumentationZipPlugin(BasePlugin):
    """Plugin que genera ZIP de la documentación después del build."""

    config_options: ClassVar[dict[str, Any]] = {}

    def on_post_build(self, config: Config) -> None:
        """Ejecutado después del build de mkdocs."""
        site_dir = Path(config.get("site_dir", "site"))
        zip_path = site_dir / "util_bbdd-docs-latest.zip"

        if site_dir.exists():
            print(f"\n[ZIP] Generando descarga de documentacion: {zip_path}")

            # Se escribe a un fichero temporal FUERA de site_dir: escribir directamente en
            # zip_path (dentro de site_dir) hace que zipfile.ZipFile(zip_path, "w") cree/trunque
            # el archivo en disco antes de recorrer site_dir, y el os.walk() de abajo lo
            # encuentra y lo incluye en sí mismo a mitad de escritura (entrada autorreferencial
            # corrupta) — ver AUDIT_CODE DOC-02, 2026-09-22.
            tmp_fd, tmp_name = tempfile.mkstemp(prefix="util_bbdd-docs-", suffix=".zip.tmp")
            os.close(tmp_fd)
            tmp_path = Path(tmp_name)
            try:
                with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zipf:
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

                shutil.move(str(tmp_path), str(zip_path))
            finally:
                tmp_path.unlink(missing_ok=True)

            # Calcular SHA256 del ZIP
            sha256_hash = self._calculate_sha256(zip_path)

            # Guardar SHA256 en archivo .sha256
            sha256_file = zip_path.with_suffix(".zip.sha256")
            with open(sha256_file, "w") as f:
                f.write(f"{sha256_hash}  {zip_path.name}\n")

            file_size_mb = zip_path.stat().st_size / (1024 * 1024)
            print(f"[OK] ZIP creado: {zip_path.name} ({file_size_mb:.2f} MB)")
            print(f"[OK] SHA256: {sha256_hash}")
            print(f"[OK] Checksum guardado: {sha256_file.name}")
        else:
            print(f"[WARN] Directorio {site_dir} no encontrado")

    def _calculate_sha256(self, file_path: Path) -> str:
        """Calcula el hash SHA256 de un archivo."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
