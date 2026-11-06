# PLAN + AUDIT_PLAN — Grupo F (documentación, traspaso a util_bbdd_web y cierre de 5.3.0)

`/new-feature` sobre la sesión `2026-11-05-doc-markdown` (PLAN §7, grupo F). Código cerrado en los grupos A–E
(`fa6af78c` … `b2128968`). Este grupo no cambia `src/`.

## Inputs

| Input | Valor |
|---|---|
| Objetivo | Documentar el formato Markdown y `MermaidRelationshipGraph` según `DOCUMENTATION_STANDARD.md`, dejar a util_bbdd_web un traspaso concreto y cerrar la versión 5.3.0 |
| Ficheros | `docs/api/database_documentation.md`, `docs/functional/database_documentation.md`, `docs/api/analysis.md`, `docs/api/analysis_autodoc.md`, `docs/functional/graph_analysis.md`, `docs/guides/markdown_documentation_guide.md` (nuevo), `docs/examples/markdown_documentation.{py,md}` (nuevos), `docs/guides/troubleshooting.md`, `docs/index.md`, `docs/architecture.md` (pie de figura), `mkdocs.yml`, `.github/SHARED_INSTRUCTIONS.md` y `.ai/*.md` (menciones a los formatos), `tests/unit/test_docs_examples.py` (registro del ejemplo) |
| API pública | Sin cambios (solo documentación) |
| Restricciones | No inventar: cada afirmación, contra el código y los tests de los grupos A–E. `zensical build --strict` limpio. Nombres en minúsculas con `_` en `docs/` |

## PLAN

### F1 · Documentación técnica (arquetipo 2, `docs/api/`)

- `database_documentation.md`:
  - formato `markdown` (alias `md`) en «API pública» y «Contrato de entrada»;
  - tabla del bloque `imprimir["markdown"]` con las 13 claves, sus valores por defecto y su efecto;
  - estructura de salida y garantías (determinismo, staging, limpieza acotada, cancelación) en «Contrato de salida»;
  - errores al construir (`mermaid_js`, `trace_map`, `previous`) y al generar (motor distinto);
  - enlace a ADR-006 y al ejemplo nuevo.
- `analysis.md` y `analysis_autodoc.md`:
  - sección `MermaidRelationshipGraph` / `MermaidErResult` (sin Graphviz, guardas de tamaño, escape);
  - regla de cardinalidad corregida en 5.3.0;
  - bloque mkdocstrings.

### F2 · Documentación funcional (arquetipo 1, `docs/functional/`)

- `database_documentation.md`:
  - descripción y reglas de negocio con el Markdown (para IA, para publicar, versionable);
  - casos de uso: publicar con Zensical (también sin Internet), trazar con el mapa, comparar con la generación
    anterior;
  - criterios de aceptación AC nuevos, cada uno con su test.
- `graph_analysis.md`: Mermaid como tercera salida.

### F3 · Guía (arquetipo 3) `docs/guides/markdown_documentation_guide.md`

1. **Objetivo y requisitos** (sin Graphviz; Zensical o MkDocs Material para publicar).
2. **Generar**: opciones de `imprimir["markdown"]`.
3. **Publicar**: `zensical build`, `nav` corta, Mermaid local con `mermaid_js` y sin Google Fonts.
4. **Versionar con git**: `fichero_salida` fijo; limpieza que respeta los ficheros editados; `manifest.json`.
5. **Trazabilidad**: ejemplo TOML completo, equivalente JSON, reglas de casado y validación, cómo leer
   `traceability.md`.
6. **Cambios entre generaciones**: `previous`, avisos, `changes.json` y visor de la web.
7. **Para IA**: `llms.txt`, `llms-full.txt`, `catalog.json` (ADR-006), front matter e ids estables.
8. **Límites conocidos**:
   - sobrecargas de rutinas en una página (B-3);
   - únicas, identidad y acciones de FK en los cambios (E-1, E-2);
   - `PACKAGE` fuera de `changes.json` (E-3);
   - versión de los metadatos en instalaciones editables antiguas (C-6).
9. **Problemas frecuentes**.

`mkdocs.yml`: nueva subsección «Documentación de BD» en `Guías` con la guía.

### F4 · Ejemplo (arquetipo 4) `docs/examples/markdown_documentation.{py,md}`

- SQLite temporal: genera, aplica un mapa TOML, cambia el esquema, regenera con `previous` e imprime el árbol y
  extractos.
- Ejecutable sin servicios externos; se registra en `SQLITE_EXAMPLES` de `tests/unit/test_docs_examples.py`.
- Enlace bidireccional con la doc técnica (§5).

### F5 · Coherencia

- `docs/index.md`, `.github/SHARED_INSTRUCTIONS.md` (capacidades, árbol y tabla de responsabilidades) y `.ai/*.md`:
  «Word, Excel, HTML **y Markdown**», con fecha «Actualizado».
- `troubleshooting.md`, con tres entradas:
  - diagramas sin dibujar en un sitio sin Internet → `mermaid_js`;
  - `DocumentationConfigError` del mapa → lista de errores;
  - motor distinto en `previous`.
- `docs/architecture.md`: pie de figura con v5.3.0, fecha y número de ficheros medidos.

### F6 · Traspaso a util_bbdd_web (`.ai/sessions/2026-11-05-doc-markdown/WEB_HANDOFF.md`)

No se edita la web desde aquí. El documento propone, con rutas de la web:

- subir a util_bbdd 5.3.0 y añadir `"markdown": "MARKDOWN"` a `_FORMAT_DIRS`;
- en el formulario: casilla Markdown, tope de profundidad, título del sitio;
- pasar siempre `mermaid_js=UBW_MERMAID_JS` (su Mermaid 12), porque la web no sale a Internet;
- mapa de trazabilidad como fichero subido por proyecto, reutilizando la validación de subidas;
- «Comparar con la ejecución…», que pasa la carpeta `MARKDOWN` de una ejecución anterior como `previous`, y
  `docs/changes.json` en su visor de diferencias actual;
- vista previa del Markdown (y, opcionalmente, del sitio construido);
- entrada en el `ROADMAP.md` de la web.

### F7 · Cierre de sesión

- `TRACEABILITY.md` de la sesión con «Directrices para Futuras IAs».
- `INDEX.md` → `CLOSED` tras el cierre de versión.

### F8 · Versión 5.3.0 (después, con `/version-closure`)

`pyproject.toml` 5.3.0, CHANGELOG `[5.3.0] - fecha`, commit `release: v5.3.0 - …` y tag anotado **en local**. El
push lo hace el usuario.

## AUDIT_PLAN

| # | Riesgo | Mitigación |
|---|---|---|
| FF1 | Documentación que inventa o contradice el código | Cada opción y comportamiento se toma del código o de los tests (A–E); revisión con `documentation_review.prompt.md` antes del cierre |
| FF2 | Enlaces rotos o nombres fuera de convención | `zensical build --strict`; `test_docs_links.py`; nombres en minúsculas |
| FF3 | El ejemplo depende del entorno (Zensical o Graphviz) | Solo SQLite y la biblioteca estándar; sin `zensical` en el ejemplo (se explica en la guía) |
| FF4 | Mezclar el cierre de versión con la documentación | F8 va aparte, con `/version-closure`, después de aprobar F1–F7 |
| FF5 | El traspaso a la web se queda en papel | Documento con rutas y funciones concretas de la web (`documentation.py:42`, `runs.py:505`, `domain/runs/diff.py`) y propuesta de entrada en su `ROADMAP.md` |

**Veredicto: `GO`.**
