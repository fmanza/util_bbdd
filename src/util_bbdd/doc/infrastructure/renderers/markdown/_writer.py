"""Escritura de la documentación Markdown: staging, publicación, limpieza de huérfanos y ``manifest.json``.

Se escribe todo en una carpeta temporal junto a la de salida (mismo volumen) y solo al terminar se publica. Si la
generación se cancela o falla, la versión anterior queda intacta. Al regenerar en la misma carpeta se borran **solo**
los ficheros que el ``manifest.json`` anterior lista y la nueva generación ya no produce (p. ej. el ``.md`` de una
tabla eliminada); los ficheros ajenos (documentación propia del usuario junto a la generada) no se tocan nunca.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time
import uuid

from collections.abc import Callable
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

MANIFEST_NAME = "manifest.json"
MANIFEST_FORMAT = "util_bbdd.doc.markdown"
MANIFEST_FORMAT_VERSION = 1

_REPLACE_ATTEMPTS = 3
_REPLACE_PAUSE_SECONDS = 0.2


def library_version() -> str:
    """Versión instalada de util_bbdd (``desconocida`` si no está instalada como paquete)."""
    try:
        return version("util_bbdd")
    except PackageNotFoundError:
        return "desconocida"


class StagedWriter:
    """Escribe ficheros en staging y los publica en ``output_dir`` al final.

    Args:
        output_dir: Carpeta de salida del formato (``…/MARKDOWN``); se crea si no existe.
        logger: Logger del renderer.

    Example:
        >>> writer = StagedWriter(Path("out/MARKDOWN"), logger)
        >>> try:
        ...     writer.write("docs/index.md", "# Hola\\n")
        ...     writer.publish({"engine": "sqlite"})
        ... finally:
        ...     writer.discard()
    """

    def __init__(self, output_dir: Path, logger: logging.Logger) -> None:
        self.output_dir: Path = output_dir
        self._logger = logger
        self._staging: Path = output_dir.parent / f".{output_dir.name}.tmp-{uuid.uuid4().hex}"
        self._staging.mkdir(parents=True)
        self._hashes: dict[str, str] = {}

    def write(self, relative: str, text: str) -> None:
        """Escribe ``text`` (UTF-8, saltos ``\\n``) en ``relative`` dentro del staging, sin salir de él."""
        target = self._target(relative)
        data = text.encode("utf-8")
        target.write_bytes(data)
        self._hashes[Path(relative).as_posix()] = f"sha256:{hashlib.sha256(data).hexdigest()}"

    def copy(self, relative: str, source: Path) -> None:
        """Copia el fichero ``source`` (p. ej. el Mermaid local) a ``relative`` dentro del staging."""
        target = self._target(relative)
        shutil.copyfile(source, target)
        self._hashes[Path(relative).as_posix()] = _file_hash(target)

    def open_stream(self, relative: str) -> TextStream:
        """Fichero de texto que se escribe por partes (``llms-full.txt``), sin guardarlo entero en memoria.

        Se registra en el manifiesto al cerrarlo (``with writer.open_stream(...) as stream: stream.write(...)``).
        """
        return TextStream(self._target(relative), lambda hash_value: self._register(relative, hash_value))

    def _register(self, relative: str, hash_value: str) -> None:
        self._hashes[Path(relative).as_posix()] = hash_value

    def _target(self, relative: str) -> Path:
        target = self._inside(self._staging, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def publish(self, metadata: dict[str, Any]) -> Path:
        """Escribe ``manifest.json``, borra los huérfanos de la generación anterior y mueve lo nuevo a su sitio.

        Args:
            metadata: Datos de la generación para el manifiesto (motor, schema, base de datos).

        Returns:
            La carpeta de salida.
        """
        manifest: dict[str, Any] = {
            **metadata,
            "format": MANIFEST_FORMAT,
            "format_version": MANIFEST_FORMAT_VERSION,
            "util_bbdd_version": library_version(),
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "files": dict(sorted(self._hashes.items())),
        }
        (self._staging / MANIFEST_NAME).write_bytes(
            (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._remove_orphans(set(self._hashes))
        for relative in sorted(self._hashes):
            self._move(relative)
        # El manifiesto, el último: si algo falla antes, el anterior sigue describiendo la carpeta
        self._move(MANIFEST_NAME)
        self.discard()
        return self.output_dir

    def discard(self) -> None:
        """Elimina el staging (tras publicar, o si la generación se cancela o falla)."""
        shutil.rmtree(self._staging, ignore_errors=True)

    # --- Internos ---

    @staticmethod
    def _inside(root: Path, relative: str) -> Path:
        target = (root / relative).resolve()
        if not target.is_relative_to(root.resolve()):
            raise ValueError(f"Ruta fuera de la carpeta de salida: {relative}")
        return target

    def _previous_files(self) -> dict[str, str]:
        """Ficheros (y su hash) que lista el manifiesto anterior, si existe y es de este formato; si no, ninguno."""
        path = self.output_dir / MANIFEST_NAME
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(previous, dict) or previous.get("format") != MANIFEST_FORMAT:
            return {}
        files = previous.get("files")
        return {str(name): str(value) for name, value in files.items()} if isinstance(files, dict) else {}

    def _remove_orphans(self, current: set[str]) -> None:
        """Borra lo que generó la vez anterior y ya no se genera, solo si sigue intacto (mismo hash que entonces).

        Un fichero generado que el usuario ha modificado (p. ej. ``mkdocs.yml``) se conserva aunque deje de generarse.
        """
        root = self.output_dir.resolve()
        previous = self._previous_files()
        for relative in sorted(set(previous) - current):
            target = (root / relative).resolve()
            if not target.is_relative_to(root) or target == root / MANIFEST_NAME:
                self._logger.warning(f"⚠️ Manifiesto anterior con una ruta fuera de la carpeta, se ignora: {relative}")
                continue
            if not target.is_file():
                continue
            if _file_hash(target) != previous[relative]:
                self._logger.warning(f"⚠️ {relative} ya no se genera pero se ha modificado: se conserva")
                continue
            target.unlink()
            self._remove_empty_parents(target.parent, root)

    @staticmethod
    def _remove_empty_parents(folder: Path, root: Path) -> None:
        while folder != root and folder.is_relative_to(root):
            try:
                folder.rmdir()  # solo si está vacía
            except OSError:
                return
            folder = folder.parent

    def _move(self, relative: str) -> None:
        source = self._staging / relative
        target = self.output_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(1, _REPLACE_ATTEMPTS + 1):
            try:
                os.replace(source, target)
                return
            except PermissionError:
                # Windows: el fichero destino abierto en otro programa (visor, antivirus); se reintenta un momento
                if attempt == _REPLACE_ATTEMPTS:
                    raise
                time.sleep(_REPLACE_PAUSE_SECONDS)


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


class TextStream:
    """Fichero de texto UTF-8 con saltos ``\\n`` que calcula su hash mientras se escribe."""

    def __init__(self, path: Path, on_close: Callable[[str], None]) -> None:
        self._handle = path.open("wb")
        self._digest = hashlib.sha256()
        self._on_close = on_close

    def write(self, text: str) -> None:
        data = text.encode("utf-8")
        self._digest.update(data)
        self._handle.write(data)

    def __enter__(self) -> TextStream:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._handle.close()
        self._on_close(f"sha256:{self._digest.hexdigest()}")


__all__: list[str] = ["MANIFEST_FORMAT", "MANIFEST_NAME", "StagedWriter", "TextStream", "library_version"]
