#!/usr/bin/env python3
"""Build the documentation site and package it as a ZIP for offline distribution.

Usage:
    python scripts/build_docs_zip.py
    python scripts/build_docs_zip.py --builder mkdocs
    python scripts/build_docs_zip.py --no-build          # only zip an existing site/
    python scripts/build_docs_zip.py --output-dir /tmp
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tomllib

from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = ROOT / "site"
PYPROJECT = ROOT / "pyproject.toml"


def _version() -> str:
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def _build(builder: str, strict: bool) -> None:
    cmd = [builder, "build"]
    if strict:
        cmd.append("--strict")
    print(f"[build_docs_zip] Building with: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        sys.exit(result.returncode)


def _zip(output_dir: Path, version: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_stem = output_dir / f"util_bbdd-docs-{version}"
    archive = Path(shutil.make_archive(str(zip_stem), "zip", SITE_DIR))
    print(f"[build_docs_zip] Created: {archive}")
    return archive


def _sha256_file(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


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
    print(f"\n[build_docs_zip] ✅ ZIP created: {archive.name} ({file_size_mb:.2f} MB)")
    print(f"[build_docs_zip] 🔐 SHA256: {sha256_hash}")
    print(f"[build_docs_zip] 📄 Checksum saved to: {sha256_file.name}")
    print(f"[build_docs_zip] 📋 All checksums in: {checksums_file.name}")

    return sha256_hash


def main() -> None:
    parser = argparse.ArgumentParser(description="Build docs and package as offline ZIP.")
    parser.add_argument(
        "--builder",
        choices=["zensical", "mkdocs"],
        default="zensical",
        help="Doc builder to use (default: zensical)",
    )
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
    args = parser.parse_args()

    if not args.no_build:
        _build(args.builder, args.strict)
    elif not SITE_DIR.exists():
        print(f"[build_docs_zip] ERROR: {SITE_DIR} does not exist. Run without --no-build first.", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir) if Path(args.output_dir).is_absolute() else ROOT / args.output_dir
    archive = _zip(output_dir, _version())
    _create_checksum_files(archive)


if __name__ == "__main__":
    main()
