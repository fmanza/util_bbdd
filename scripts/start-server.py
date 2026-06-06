#!/usr/bin/env python3
"""
Servidor local para documentación offline de util_bbdd.

Inicia un servidor HTTP simple y abre la documentación en el navegador.
Compatible con Windows, Linux y macOS.

Uso:
    python start-server.py
    # O directamente si está en la raíz del ZIP:
    python start-server.py

Luego abre http://localhost:8000 en tu navegador.
Para detener, presiona Ctrl+C en la terminal.
"""

import http.server
import os
import socketserver
import sys
import time
import webbrowser

from pathlib import Path


def find_site_root() -> Path:
    """Encuentra la raíz del sitio (index.html)."""
    # Si estamos en el directorio raíz del ZIP
    if Path("index.html").exists():
        return Path.cwd()

    # Si estamos en scripts/
    scripts_dir = Path(__file__).parent
    site_root = scripts_dir.parent
    if (site_root / "index.html").exists():
        return site_root

    # Buscar hacia arriba
    current = Path.cwd()
    for _ in range(5):
        if (current / "index.html").exists():
            return current
        current = current.parent

    raise FileNotFoundError(
        "No se encontró index.html. Asegúrate de ejecutar este script desde la raíz del ZIP o desde scripts/."
    )


def start_server(port: int = 8000) -> None:
    """Inicia servidor HTTP local y abre navegador."""
    try:
        site_root = find_site_root()
    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Cambiar al directorio del sitio
    os.chdir(site_root)

    # Configurar handler
    Handler = http.server.SimpleHTTPRequestHandler

    # Intentar diferentes puertos si 8000 está en uso
    actual_port = port
    max_attempts = 5

    for attempt in range(max_attempts):
        try:
            with socketserver.TCPServer(("", actual_port), Handler) as httpd:
                url = f"http://localhost:{actual_port}"

                print("\n" + "=" * 60)
                print("📚 Servidor local de documentación - util_bbdd")
                print("=" * 60)
                print(f"✅ Servidor activo en: {url}")
                print(f"📁 Sirviendo desde: {site_root}")
                print("\n💡 El navegador se abrirá automáticamente...")
                print("⏸️  Para detener el servidor, presiona Ctrl+C")
                print("=" * 60 + "\n")

                # Abrir navegador tras una pequeña pausa
                time.sleep(1)
                try:
                    webbrowser.open(url)
                except Exception as e:
                    print(f"⚠️  No se pudo abrir navegador automáticamente: {e}")
                    print(f"👉 Abre manualmente: {url}\n")

                # Servir indefinidamente
                httpd.serve_forever()

        except OSError as e:
            actual_port = port + attempt + 1
            if attempt < max_attempts - 1:
                print(f"⚠️  Puerto {port + attempt} en uso, intentando {actual_port}...")
                continue
            else:
                print(f"❌ Error: No se pudo iniciar servidor en puertos {port}-{actual_port}", file=sys.stderr)
                print(f"Detalles: {e}", file=sys.stderr)
                sys.exit(1)
        except KeyboardInterrupt:
            print("\n\n⏹️  Servidor detenido.")
            sys.exit(0)


if __name__ == "__main__":
    start_server()
