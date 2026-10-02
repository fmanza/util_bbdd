#!/usr/bin/env python3
"""
Verifica que la configuración de GitHub Actions esté correcta.
Uso: python scripts/verify_github_actions.py
"""

import subprocess
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SITE = ROOT / "site"
PYPROJECT = ROOT / "pyproject.toml"


def check_python_version() -> bool:
    """Verifica que Python sea 3.12+."""
    version = sys.version_info
    if version.major == 3 and version.minor >= 12:
        print(f"[X] Python {version.major}.{version.minor}")
        return True
    print(f"[X] Python {version.major}.{version.minor} (se requiere 3.12+)")
    return False


def check_dependencies() -> bool:
    """Verifica que las dependencias de docs estén instaladas."""
    required = ["zensical", "pip"]
    missing = []

    for dep in required:
        try:
            result = subprocess.run([dep, "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"[X] {dep}: {result.stdout.strip().split(chr(10))[0]}")
            else:
                missing.append(dep)
        except FileNotFoundError:
            missing.append(dep)

    if missing:
        print(f"[X] Faltan dependencias: {', '.join(missing)}")
        print("   Ejecuta: pip install -e '.[docs]'")
        return False
    return True


def check_project_config() -> bool:
    """Verifica que pyproject.toml tenga versión."""
    import tomllib

    try:
        with PYPROJECT.open("rb") as f:
            config = tomllib.load(f)
        version = config.get("project", {}).get("version")
        if version:
            print(f"[X] Versión en pyproject.toml: {version}")
            return True
        print("[X] No se encontró [project] version en pyproject.toml")
        return False
    except Exception as e:
        print(f"[X] Error leyendo pyproject.toml: {e}")
        return False


def check_scripts() -> bool:
    """Verifica que los scripts de build existan."""
    scripts = [
        ROOT / "scripts" / "build_docs_zip.py",
    ]

    all_exist = True
    for script in scripts:
        if script.exists():
            print(f"[X] {script.name} existe")
        else:
            print(f"[X] Falta {script}")
            all_exist = False
    return all_exist


def check_workflows() -> bool:
    """Verifica que los workflows existan."""
    workflows = [
        ROOT / ".github" / "workflows" / "docs-zip-release.yml",
        ROOT / ".github" / "workflows" / "docs-release.yml",
    ]

    all_exist = True
    for wf in workflows:
        if wf.exists():
            print(f"[X] {wf.name} existe")
        else:
            print(f"[X] Falta {wf}")
            all_exist = False
    return all_exist


def check_build_locally() -> bool:
    """Intenta buildear docs localmente."""
    print("\n[X][X] Intentando buildear documentación localmente...")
    try:
        result = subprocess.run(
            ["zensical", "build", "--strict"], cwd=ROOT, capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            print("[X] Build de Zensical exitoso")
            if SITE.exists():
                file_count = len(list(SITE.rglob("*")))
                print(f"   [X]� site/ contiene {file_count} archivos")
            return True
        else:
            print("[X] Build falló:")
            print(result.stderr[-500:] if len(result.stderr) > 500 else result.stderr)
            return False
    except subprocess.TimeoutExpired:
        print("[X] Build tardó demasiado (timeout)")
        return False
    except Exception as e:
        print(f"[X] Error al buildear: {e}")
        return False


def check_zip_generation() -> bool:
    """Intenta generar el ZIP localmente."""
    print("\n[X][X] Intentando generar ZIP...")
    try:
        DIST.mkdir(exist_ok=True)
        result = subprocess.run(
            ["python", "scripts/build_docs_zip.py", "--builder", "zensical", "--output-dir", "dist"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            print("[X] ZIP generado exitosamente")
            zips = list(DIST.glob("*.zip"))
            shas = list(DIST.glob("*.sha256"))
            print(f"   [X][X] ZIPs: {len(zips)}")
            print(f"   [X]� SHAs: {len(shas)}")
            if zips:
                for z in zips:
                    print(f"      - {z.name} ({z.stat().st_size / (1024 * 1024):.2f} MB)")
            return True
        else:
            print("[X] Generación de ZIP falló:")
            print(result.stderr[-500:] if len(result.stderr) > 500 else result.stderr)
            return False
    except subprocess.TimeoutExpired:
        print("[X] Generación tardó demasiado (timeout)")
        return False
    except Exception as e:
        print(f"[X] Error: {e}")
        return False


def main() -> int:
    """Ejecuta todos los checks."""
    print("=" * 60)
    print("[VERIFY] GitHub Actions Configuration Check")
    print("=" * 60)

    checks = [
        ("Python version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Project config", check_project_config),
        ("Scripts", check_scripts),
        ("Workflows", check_workflows),
        ("Build local", check_build_locally),
        ("ZIP generation", check_zip_generation),
    ]

    results = []
    for name, check_fn in checks:
        print(f"\n[X]� {name.upper()}")
        print("-" * 40)
        try:
            results.append(check_fn())
        except Exception as e:
            print(f"[X] Excepción: {e}")
            results.append(False)

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"[X]� Resultado: {passed}/{total} checks pasaron")

    if passed == total:
        print("[X] Todo está configurado correctamente!")
        print("\nPróximo paso: Haz push a GitHub y verifica que el workflow se ejecute.")
        return 0
    else:
        print("[X] Hay problemas que resolver. Lee los mensajes arriba.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
