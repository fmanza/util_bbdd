---
applyTo: "src/util_bbdd/doc/**/*.py"
---
# Renderizado de documentación

> **TL;DR** — Salida determinista (orden alfabético estable). Funciones de render puras: reciben el modelo IR, devuelven contenido sin efectos secundarios. Librería específica por formato (openpyxl, python-docx, Jinja2). Sin servicios externos ni dependencias pesadas. Tests de snapshot o asserts sobre fragmentos clave.

- La salida debe ser determinista: ordena alfabéticamente schemas/tablas/columnas.
- Formatos actuales en `doc/infrastructure/renderers/`: Excel (openpyxl), Word (python-docx) y HTML (Jinja2); cada uno con formato propio.
- Incluye enlaces internos o anchors cuando el formato destino los soporte de forma estable y predecible.
- Evita dependencias pesadas; prioriza soluciones ligeras y sin servicios externos.
- Mantén funciones de renderizado puras, recibiendo el modelo de metadatos y devolviendo el resultado sin efectos secundarios.
- Documenta claramente qué información se incluye en la documentación generada y cómo se estructura.
- Proporciona tests de integración que validen la salida generada contra un modelo de metadatos conocido.
- Si la generación de documentación no puede incluir cierta información (p.ej. comentarios de columnas en SQLite), documenta esta limitación y sugiere alternativas (p.ej. input manual o modelo intermedio).
- Texto de celdas y párrafos: pasa por `_core/export_safety` (caracteres de control y fórmulas) en Excel y Word.

## Estructura por tabla

Cada tabla se documenta con secciones en este orden fijo, en cualquier formato:
Columnas → Clave primaria → Claves foráneas → Índices (y Vistas con su definición SQL, si existe).

- Omite la sección que no aplique; no mezcles secciones.
- Mantén el mismo orden de columnas en todas las tablas documentadas.
- No incluyas información no obtenible por introspección; si un dato falta (tipo, nullabilidad, columna referenciada), muéstralo como «desconocido».
- Un diagrama de relaciones (Mermaid `erDiagram`, Graphviz) solo se genera a partir de metadatos reales.

## Patrones recomendados para render
- `Template Method`: define pipeline común de render y sobreescribe solo pasos específicos por formato.
- `Builder`: construye el documento por secciones para evitar funciones monolíticas.
- `Strategy`: encapsula variaciones por salida (HTML, Word, Excel) sin `if/elif` dispersos.
- `Facade`: expone una API simple de alto nivel para el flujo completo de documentación.
