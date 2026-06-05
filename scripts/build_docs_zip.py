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
import shutil
import subprocess
import sys
import tomllib

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
    _zip(output_dir, _version())


if __name__ == "__main__":
    main()
