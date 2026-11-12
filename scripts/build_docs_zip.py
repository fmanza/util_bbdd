#!/usr/bin/env python3
"""Build the documentation site with Zensical and package it as a ZIP for offline distribution.

The ZIP holds site/ plus the local server (start-server.py) and README_OFFLINE.txt. Zensical does not run MkDocs
plugins, so this script is the only place that builds the offline ZIP (the old ``documentation_zip`` plugin was
removed in the move to Zensical-only).

Usage:
    python scripts/build_docs_zip.py
    python scripts/build_docs_zip.py --no-build          # only zip an existing site/
    python scripts/build_docs_zip.py --output-dir /tmp
    python scripts/build_docs_zip.py --no-build --in-site # site/util_bbdd-docs-latest.zip, published with the site
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile

from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = ROOT / "site"
PYPROJECT = ROOT / "pyproject.toml"

SITE_ZIP_NAME = "util_bbdd-docs-latest.zip"
# ZIP and .sha256 from a previous build: Zensical does not empty site/ between builds, so they must not be re-packaged.
_PREVIOUS_ZIP_PREFIX = "util_bbdd-docs-"
_SERVER_SCRIPT = Path(__file__).resolve().parent / "start-server.py"
_OFFLINE_README = Path(__file__).resolve().parent / "OFFLINE_README.txt"


def _version() -> str:
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def _sha256_file(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def build_offline_zip(site_dir: Path, zip_path: Path) -> str:
    """Package ``site_dir`` plus the local server and the offline README into ``zip_path``.

    The ZIP is written to a temporary file OUTSIDE ``site_dir`` and moved at the end: writing ``zip_path`` directly
    inside ``site_dir`` would let ``os.walk()`` find the half-written ZIP and include it in itself (corrupt
    self-referencing entry, AUDIT_CODE DOC-02, 2026-09-22).

    Args:
        site_dir: Generated site directory.
        zip_path: Final ZIP path (may be inside ``site_dir``).

    Returns:
        SHA256 of the generated ZIP, in hexadecimal.
    """
    tmp_fd, tmp_name = tempfile.mkstemp(prefix="util_bbdd-docs-", suffix=".zip.tmp")
    os.close(tmp_fd)
    tmp_path = Path(tmp_name)
    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(site_dir):
                for file in files:
                    file_path = Path(root) / file
                    if file_path.parent == site_dir and file.startswith(_PREVIOUS_ZIP_PREFIX):
                        continue
                    zipf.write(file_path, arcname=file_path.relative_to(site_dir))
            if _SERVER_SCRIPT.exists():
                zipf.write(_SERVER_SCRIPT, arcname="start-server.py")
            if _OFFLINE_README.exists():
                zipf.write(_OFFLINE_README, arcname="README_OFFLINE.txt")
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(tmp_path), str(zip_path))
    finally:
        tmp_path.unlink(missing_ok=True)
    return _sha256_file(zip_path)


def _build(strict: bool) -> None:
    cmd = ["zensical", "build"]
    if strict:
        cmd.append("--strict")
    print(f"[build_docs_zip] Building with: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        sys.exit(result.returncode)


def _zip(site_dir: Path, output_dir: Path, version: str) -> Path:
    archive = output_dir / f"util_bbdd-docs-{version}.zip"
    build_offline_zip(site_dir, archive)
    print(f"[build_docs_zip] Created: {archive}")
    return archive


def _zip_in_site(site_dir: Path) -> Path:
    """ZIP + .sha256 inside site/ so the published site offers the download (no CHECKSUMS.txt history)."""
    archive = site_dir / SITE_ZIP_NAME
    sha256_hash = build_offline_zip(site_dir, archive)
    archive.with_suffix(".zip.sha256").write_text(f"{sha256_hash}  {archive.name}\n", encoding="utf-8")
    print(f"[build_docs_zip] Created inside site: {archive} (SHA256 {sha256_hash})")
    return archive


def _create_checksum_files(archive: Path) -> str:
    """Create .sha256 and CHECKSUMS.txt files for integrity validation."""
    sha256_hash = _sha256_file(archive)

    # Create .sha256 file (single line with hash and filename)
    sha256_file = archive.with_suffix(".zip.sha256")
    with open(sha256_file, "w") as f:
        f.write(f"{sha256_hash}  {archive.name}\n")

    # Create/append to CHECKSUMS.txt in the same directory
    checksums_file = archive.parent / "CHECKSUMS.txt"
    timestamp = datetime.now().isoformat()
    with open(checksums_file, "a") as f:
        f.write(f"{sha256_hash}  {archive.name}  ({timestamp})\n")

    # Display checksums
    file_size_mb = archive.stat().st_size / (1024 * 1024)
    print(f"\n[build_docs_zip] [OK] ZIP created: {archive.name} ({file_size_mb:.2f} MB)")
    print(f"[build_docs_zip] [HASH] SHA256: {sha256_hash}")
    print(f"[build_docs_zip] [FILE] Checksum saved to: {sha256_file.name}")
    print(f"[build_docs_zip] [LIST] All checksums in: {checksums_file.name}")

    return sha256_hash


def main() -> None:
    parser = argparse.ArgumentParser(description="Build docs with Zensical and package them as an offline ZIP.")
    parser.add_argument(
        "--no-strict",
        dest="strict",
        action="store_false",
        default=True,
        help="Skip --strict flag when building",
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        default=False,
        help="Skip the build step; zip whatever is already in site/",
    )
    parser.add_argument(
        "--output-dir",
        default="dist",
        metavar="DIR",
        help="Directory for the output ZIP (default: dist/)",
    )
    parser.add_argument(
        "--in-site",
        action="store_true",
        default=False,
        help=f"Write site/{SITE_ZIP_NAME} (+ .sha256) instead of the versioned ZIP in --output-dir",
    )
    args = parser.parse_args()

    if not args.no_build:
        _build(args.strict)
    elif not SITE_DIR.exists():
        print(f"[build_docs_zip] ERROR: {SITE_DIR} does not exist. Run without --no-build first.", file=sys.stderr)
        sys.exit(1)

    if args.in_site:
        _zip_in_site(SITE_DIR)
        return

    output_dir = Path(args.output_dir) if Path(args.output_dir).is_absolute() else ROOT / args.output_dir
    archive = _zip(SITE_DIR, output_dir, _version())
    _create_checksum_files(archive)


if __name__ == "__main__":
    main()
