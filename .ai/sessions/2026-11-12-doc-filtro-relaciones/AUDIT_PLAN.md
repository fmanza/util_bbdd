# AUDIT_PLAN — 2026-11-12-doc-filtro-relaciones

| # | Riesgo | Medida | Estado |
|---|---|---|---|
| A1 | Con filtro y `markdown.previous`, lo filtrado aparece como «eliminado» | `filter` en `catalog.json`; si los filtros difieren, se compara solo lo que entra en ambos y se avisa | Cubierto (`test_changes_ignore_objects_left_out_by_either_filter`) |
| A2 | HTML/Word con enlaces a tablas no documentadas | Revisado: los enlaces del SVG salen de `table_slug_map` (solo documentadas); Word y Excel no enlazan tablas | Sin cambios necesarios |
| A3 | Patrones mal formados | Validación: cadenas no vacías, imprimibles, ≤ 128 caracteres, ≤ 100 por lista → `DocumentationConfigError` al construir; aviso si no queda nada | Cubierto |
| A4 | Datos de referencia (datos personales) | Aplazado a 5.6.0 con opt-in, límites y revisión de seguridad | Fuera de alcance |
| A5 | Contratos | Campos opcionales solo con filtro: `catalog` v1 y `manifest` v2 sin cambios; ADR-006 enmendado; MINOR | Cubierto |
| A6 | README con rutas locales o fecha | Determinista, sin rutas (test) | Cubierto |
| A7 | Versión incorrecta en la salida por `egg-info` antiguo | `pip install -e . --no-deps` antes de generar | Hecho |

Veredicto: GO_CONDICIONAL → decisiones del usuario recogidas en `00_REQUEST.md`.
