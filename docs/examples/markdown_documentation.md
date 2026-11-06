# Ejemplo: Documentación Markdown

## 1. Contexto del Ejemplo

Genera la documentación de una base de datos en Markdown (desde 5.3.0): una página por tabla, vista y rutina, con
diagramas entidad-relación de Mermaid. Después añade un mapa de trazabilidad hacia el código y los requisitos y, tras
cambiar el esquema, la regenera en la misma carpeta con un informe de cambios respecto de la versión anterior.

Usa SQLite, sin credenciales, sin Graphviz y sin red. Resuelve la necesidad de tener la documentación del modelo de
datos versionada en git, publicable con Zensical y legible por una IA.

## 2. Implementación de Referencia

```python
--8<-- "examples/markdown_documentation.py"
```

## 3. Explicación del Código

Aspectos críticos:

- **`formatos=["markdown"]`**: la salida es la carpeta `MARKDOWN` (`result.outputs["markdown"]`), con `docs/`,
  `manifest.json` y un `mkdocs.yml` listo para `zensical build`.
- **Diagramas sin Graphviz**: con `grafo.enabled`, cada tabla lleva bloques `erDiagram`.
  - `||..o{`: FK obligatoria y no identificante.
  - `|o..o{`: la FK admite nulos.
  - `||--o{`: la FK forma parte de la PK de la tabla hija (relación identificante, aquí `lineas`).
  - La profundidad `grafo.max_depth: 2` cabe en el tope `markdown.max_diagram_depth`, que por defecto es 2.
- **`fichero_salida` fijo** (`Path("ventas")`): se regenera siempre en la misma carpeta. La salida es determinista y
  solo se borran los ficheros generados que ya no se producen, así que se puede versionar con git.
- **`markdown.trace_map`**: el TOML relaciona tablas y columnas con código, documentos y requisitos. Cada página lleva
  su sección «Trazabilidad» y `docs/traceability.md` muestra la cobertura y los índices por requisito y por fichero.
  Un campo desconocido haría fallar la construcción de `DatabaseDocumentation`.
- **`markdown.previous`**: apunta a la misma carpeta que se regenera, porque el catálogo anterior se lee antes de
  publicar. Genera `docs/changes.md` y `docs/changes.json` (formato `SchemaDiff`).

Variante para un sitio sin Internet (Mermaid local y sin Google Fonts):

```python
imprimir["markdown"]["mermaid_js"] = "node_modules/mermaid/dist/mermaid.min.js"
```

Variante con un Mermaid ya publicado, sin copiarlo en cada generación (desde 5.4.0; pon el fichero en esa ruta antes de
publicar):

```python
imprimir["markdown"]["mermaid_js_ref"] = "assets/javascripts/mermaid.min.js"
```

## 4. Ejecución y Pruebas

```bash
python docs/examples/markdown_documentation.py
```

Salida esperada (resumida):

```text
Documentación en demo_markdown/salida/ventas/MARKDOWN
  docs/catalog.json
  docs/index.md
  ...
  docs/tables/pedidos.md
  docs/traceability.md
  manifest.json
  mkdocs.yml

Front matter de pedidos: id=table:main.pedidos fk_in=['table:main.lineas']
```

Le siguen, en este orden:

- el diagrama `erDiagram` de `pedidos`;
- la cobertura de `traceability.md` (2 de 3 tablas trazadas);
- el resumen de `changes.md` (1 tabla añadida y 2 modificadas).

El ejemplo se ejecuta en `tests/unit/test_docs_examples.py`. Para publicar:
`cd demo_markdown/salida/ventas/MARKDOWN && zensical build --strict`.

## 5. Referencias Relacionadas

- [Generador de Documentación de BD](../api/database_documentation.md#documentacion-markdown-markdown) — opciones del
  bloque `markdown`
- [Grafos de Relaciones](../api/analysis.md) — `MermaidRelationshipGraph`
- [Guía: Documentación Markdown](../guides/markdown_documentation_guide.md) — publicar, versionar, trazar y usarla con IA
