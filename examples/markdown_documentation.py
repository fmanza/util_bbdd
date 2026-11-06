"""Ejemplo verificable: documentación Markdown con diagramas Mermaid, trazabilidad y cambios (desde 5.3.0).

Crea una base SQLite local, genera la documentación en Markdown con un mapa de trazabilidad, cambia el esquema y
la regenera en la misma carpeta comparándola con la versión anterior. Sin credenciales, sin Graphviz y sin red.
"""

import json
import sqlite3

from pathlib import Path

from util_bbdd.doc import DatabaseDocumentation
from util_bbdd.managers import SyncDatabaseManager

WORK = Path("demo_markdown")
WORK.mkdir(exist_ok=True)
DB = WORK / "ventas.db"
DB.unlink(missing_ok=True)

# ============================================================================
# 1. ESQUEMA DE DEMOSTRACIÓN
# ============================================================================

with sqlite3.connect(DB) as conn:
    conn.executescript(
        """
        CREATE TABLE clientes (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, email TEXT UNIQUE);
        CREATE TABLE pedidos (
            id INTEGER PRIMARY KEY,
            cliente_id INTEGER NOT NULL REFERENCES clientes(id),
            comercial_id INTEGER REFERENCES clientes(id)
        );
        CREATE TABLE lineas (
            pedido_id INTEGER NOT NULL REFERENCES pedidos(id),
            linea INTEGER NOT NULL,
            importe NUMERIC NOT NULL,
            PRIMARY KEY (pedido_id, linea)
        );
        CREATE VIEW v_pedidos_cliente AS
        SELECT p.id, c.nombre FROM pedidos p JOIN clientes c ON c.id = p.cliente_id;
        """
    )

# ============================================================================
# 2. MAPA DE TRAZABILIDAD (TOML; también vale JSON con la misma estructura)
# ============================================================================

TRACE_MAP = WORK / "trazabilidad.toml"
TRACE_MAP.write_text(
    """
[tables.pedidos]
code = ["src/ventas/pedidos.py#Pedido"]
functional = ["docs/functional/ventas.md#alta-de-pedido"]
requirements = ["REQ-012"]

[tables.pedidos.columns.cliente_id]
code = ["src/ventas/pedidos.py#Pedido.cliente_id"]

[tables.clientes]
requirements = ["REQ-012", "REQ-020"]
""",
    encoding="utf-8",
)

IMPRIMIR = {
    "tablas": {"imprimir_tablas": True, "ddl": True, "columnas": True, "pk": True, "fk": True, "indices": True},
    "vistas": {"imprimir_vistas": True, "columnas": True},
    "grafo": {"enabled": True, "max_depth": 2},
    "markdown": {"site_name": "Ventas (demo)", "trace_map": str(TRACE_MAP)},
}


def generar(imprimir: dict) -> Path:
    """Genera la documentación Markdown en una carpeta fija (versionable con git) y devuelve su ruta."""
    with SyncDatabaseManager("sqlite", {"database": str(DB)}, use_pool=False) as manager:
        result = DatabaseDocumentation(
            manager, WORK / "salida", Path("ventas"), imprimir=imprimir, formatos=["markdown"]
        ).generate()
    return result.outputs["markdown"]


# ============================================================================
# 3. PRIMERA GENERACIÓN
# ============================================================================

root = generar(IMPRIMIR)
print(f"Documentación en {root}")
for path in sorted(p for p in root.rglob("*") if p.is_file()):
    print(f"  {path.relative_to(root).as_posix()}")

pedidos = (root / "docs" / "tables" / "pedidos.md").read_text(encoding="utf-8")
front_matter = json.loads(pedidos.split("\n")[1])
print(f"\nFront matter de pedidos: id={front_matter['id']} fk_in={front_matter['fk_in']}")
print(pedidos[pedidos.index("```mermaid") : pedidos.index("```", pedidos.index("```mermaid") + 3) + 3])

traceability = (root / "docs" / "traceability.md").read_text(encoding="utf-8").split("\n")
print("\n" + "\n".join(traceability[traceability.index("## Cobertura") : traceability.index("## Cobertura") + 7]))

# ============================================================================
# 4. CAMBIO DE ESQUEMA Y REGENERACIÓN COMPARANDO CON LA ANTERIOR (misma carpeta)
# ============================================================================

with sqlite3.connect(DB) as conn:
    conn.executescript(
        """
        ALTER TABLE clientes ADD COLUMN telefono TEXT;
        CREATE INDEX ix_pedidos_cliente ON pedidos (cliente_id);
        CREATE TABLE devoluciones (id INTEGER PRIMARY KEY, pedido_id INTEGER REFERENCES pedidos(id));
        """
    )

root = generar({**IMPRIMIR, "markdown": {**IMPRIMIR["markdown"], "previous": str(root)}})
changes = (root / "docs" / "changes.md").read_text(encoding="utf-8").split("\n")
print("\n" + "\n".join(changes[changes.index("## Resumen") : changes.index("## Resumen") + 7]))
print("Publicar: cd", root, "&& zensical build --strict")
