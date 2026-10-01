"""
Plugin para generar descarga ZIP de documentación en mkdocs.

Zensical no ejecuta plugins de MkDocs: con Zensical, el ZIP lo genera ``scripts/build_docs_zip.py``, que usa la
misma función :func:`build_offline_zip`.

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

from mkdocs.config.defaults import MkDocsConfig
from mkdocs.plugins import BasePlugin

SITE_ZIP_NAME = "util_bbdd-docs-latest.zip"
# ZIP y .sha256 de un build anterior: Zensical no vacía site/ entre builds y no deben empaquetarse otra vez.
_PREVIOUS_ZIP_PREFIX = "util_bbdd-docs-"
_SERVER_SCRIPT = Path(__file__).parent.parent.parent / "scripts" / "start-server.py"
_OFFLINE_README = Path(__file__).parent / "OFFLINE_README.txt"


def build_offline_zip(site_dir: Path, zip_path: Path) -> str:
    """Empaqueta ``site_dir`` más el servidor local y el README offline en ``zip_path``.

    Se escribe a un fichero temporal FUERA de ``site_dir`` y se mueve al final: escribir directamente en
    ``zip_path`` dentro de ``site_dir`` haría que ``os.walk()`` encontrara el propio ZIP a mitad de escritura y lo
    incluyera en sí mismo (entrada autorreferencial corrupta) — ver AUDIT_CODE DOC-02, 2026-09-22.

    Args:
        site_dir: Directorio del sitio generado.
        zip_path: Ruta final del ZIP (puede estar dentro de ``site_dir``).

    Returns:
        SHA256 en hexadecimal del ZIP generado.
    """
    tmp_fd, tmp_name = tempfile.mkstemp(prefix="util_bbdd-docs-", suffix=".zip.tmp")
    os.close(tmp_fd)
    tmp_path = Path(tmp_name)
    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # 1. Copiar documentación HTML desde site/ (sin el ZIP de un build anterior)
            for root, _, files in os.walk(site_dir):
                for file in files:
                    file_path = Path(root) / file
                    if file_path.parent == site_dir and file.startswith(_PREVIOUS_ZIP_PREFIX):
                        continue
                    arcname = file_path.relative_to(site_dir)
                    zipf.write(file_path, arcname=arcname)

            # 2. Copiar script de servidor local (si existe)
            if _SERVER_SCRIPT.exists():
                print(f"[ZIP] Incluyendo servidor local: {_SERVER_SCRIPT.name}")
                zipf.write(_SERVER_SCRIPT, arcname="start-server.py")

            # 3. Copiar README con instrucciones offline
            if _OFFLINE_README.exists():
                print(f"[ZIP] Incluyendo instrucciones: {_OFFLINE_README.name}")
                zipf.write(_OFFLINE_README, arcname="README_OFFLINE.txt")

        zip_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp_path), str(zip_path))
    finally:
        tmp_path.unlink(missing_ok=True)

    sha256_hash = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


class DocumentationZipPlugin(BasePlugin):
    """Plugin que genera ZIP de la documentación después del build."""

    config_options: ClassVar[dict[str, Any]] = {}

    def on_post_build(self, *, config: MkDocsConfig) -> None:
        """Ejecutado después del build de mkdocs.

        Misma firma que ``BasePlugin.on_post_build`` (``config`` solo por nombre: mkdocs llama ``method(**kwargs)``).
        """
        site_dir = Path(config.get("site_dir", "site"))
        zip_path = site_dir / SITE_ZIP_NAME

        if site_dir.exists():
            print(f"\n[ZIP] Generando descarga de documentacion: {zip_path}")
            sha256_hash = build_offline_zip(site_dir, zip_path)

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
