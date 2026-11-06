# SPIKE C3 — `erDiagram` en Mermaid 11/12 y Zensical (2026-11-06)

Condición C3 del AUDIT_PLAN: validar la gramática, los límites y el escape de `erDiagram` con las versiones reales
antes de implementar. Scripts y resultados en `spike_c3/`. Se ejecutaron desde el scratchpad, por eso las rutas
`out/` son relativas a él; para repetirlo, `python gen_cases.py`, `zensical build --strict` en `out/site` y
`node run_spike.cjs` con dos `http.server`.

## Entorno

| Pieza | Versión |
|---|---|
| Zensical | 0.0.71 (venv del repo) |
| Mermaid que carga Zensical | `https://unpkg.com/mermaid@11/dist/mermaid.min.js` → resuelto a **11.17.2** (petición observada). Está incrustado en `zensical/templates/assets/javascripts/bundle.*.min.js`: **necesita Internet** |
| Mermaid de util_bbdd_web | 12.2.0 (`frontend/node_modules/mermaid`) |
| Navegador | Chromium de Playwright 1.63.0 (`util_bbdd_web/frontend`) |
| Configuración Mermaid | `securityLevel: "strict"`; por defecto `maxTextSize = 50000` y `maxEdges = 500` en ambas versiones; layout ER `elk` en 12 y `dagre` en 11 |

## Resultados

### Sintaxis propuesta en el PLAN §4.2/§4.4: válida en 11.17.2 y 12.2.0

- Alias de entidad `e1["nombre"]` e ids `e<n>`.
- Atributos con `PK`, `FK`, `UK` y `PK, FK`; comentario de atributo entre comillas.
- Cardinalidades `||--o{`, `|o--o{`, `||--o|`, `}o--o{`, `||..o{` y `|o..o|`; etiqueta vacía `""`.
- FK reflexiva y dos FK entre el mismo par de tablas.
- Entidad sin atributos y entidad con bloque vacío.
- Tipos con paréntesis y corchetes: `VARCHAR(255)`, `NUMBER(10)`, `int[]`.
- Unicode en tipos, nombres y alias: `código_postal`, `año`, `日本語テーブル`.

En el sitio Zensical se dibujan todos los diagramas válidos (captura `spike_c3/results/site_base.png`). El SVG queda
en un shadow DOM cerrado de Material.

### Lo que falla en ambas versiones

| Caso | Resultado | Consecuencia para el diseño |
|---|---|---|
| Tipo con espacio (`double precision`, `timestamp(6) with time zone`) | Parse error | Normalizar los espacios (`double_precision`) |
| Columna o tipo llamado `PK`, `FK` o `UK` | Parse error | Palabras reservadas: sufijo `_` (`PK_`) sin distinguir mayúsculas; nombre real en el comentario |
| Id de entidad `end`, `style`, `class` o `erDiagram` | Parse/lexical error | No afecta: los ids son `e<n>` |
| `%` (aunque sea uno solo) o `\` dentro del alias de entidad | Parse error | **`escape_mermaid_label` (G46) no basta para `erDiagram`**: deja `% %`, que rompe el alias |
| Comilla doble cruda en un comentario | Parse error | Ya previsto: escape |

Columnas llamadas `end`, `style`, `class`, `erDiagram`, `string`, `u`, `o` o `x`: válidas.

### Contra la documentación de Mermaid

- `decimal(10,2)` con coma **parsea** en 11.17.2 y en 12.2.0, aunque la documentación no incluye la coma entre los
  caracteres permitidos. Decisión: normalizar igualmente (`decimal(10_2)`), porque el contrato es la documentación.
  El tipo exacto está en la tabla de columnas.
- `maxEdges = 500` **no limita** `erDiagram`: 598 relaciones se dibujan. El límite efectivo es `maxTextSize`
  (50 000 caracteres) y, sobre todo, el tiempo de dibujo.

### Escape por entidades: fiel y seguro

Los códigos de entidad de Mermaid funcionan en alias y en comentarios de las dos versiones, y se muestran como el
carácter original:

| Entrada | Escrito como | Se muestra |
|---|---|---|
| `a%b` | `a#37;b` | `a%b` |
| `a\b` | `a#92;b` | `a\b` |
| `x " y` | `x #quot; y` | `x " y` |
| `%%{init: {'theme':'dark'}}%%` | `#37;#37;{init: …}#37;#37;` | El texto literal, **sin aplicar la directiva** |

Es mejor que el escape actual (`"` → `'`, `%%` → `% %`), que altera el nombre y no evita el fallo en `erDiagram`.
Sin probar todavía, quedan para los tests del grupo A: `#35;` para un `#` literal (si no, un nombre que contenga
`#quot;` se mostraría como `"`) y `#91;`/`#93;` para los corchetes.

En ningún caso apareció HTML ejecutable en el SVG (`<script`, `onerror=`) con `securityLevel: "strict"`.

### Tamaño y tiempo de dibujo

| Diagrama | Caracteres | 12.2.0 (ELK) | 11.17.2 (dagre) |
|---|---|---|---|
| 3 entidades | 273 | 256 ms (primer render) | 57 ms |
| 80 entidades × 8 columnas, 158 relaciones | 30 938 | 1,6 s | 1,4 s |
| 300 entidades, 598 relaciones | 28 523 | **12,6 s** | **27,9 s** |

El tope de profundidad 2 y `max_subnodes` (10 por defecto) mantienen los diagramas pequeños. Hace falta además una
guarda **por número de entidades** (propuesta: 40 por bloque) además de la de caracteres (50 000), porque el
tiempo crece mucho antes de llegar al límite de texto.

### Página Markdown en Zensical (`tables/pedidos.md`)

| Comprobación | Resultado |
|---|---|
| `zensical build --strict` con `mkdocs.yml` + `docs_dir: docs` | ✅ sin incidencias (T8 cerrado para Zensical) |
| Front matter JSON en una línea con `"`, `:` y `---` en el título | ✅ título y navegación correctos |
| `<a id="col-id"></a>` en celda + enlace `#col-id` | ✅ |
| `<script>` e `<img onerror>` del catálogo escapados como entidades | ✅ sin ejecución (0 diálogos, 0 nodos inyectados) |
| *Fence* de 4 backticks con ```` ``` ```` dentro del DDL | ✅ intacto |
| Admonición `!!! warning` | ✅ |
| `catalog.json` y `llms.txt` en `docs/` | ✅ copiados al sitio como estáticos |
| `*y*` en un comentario del catálogo | ❌ se convierte en `<em>`: `escape_markdown_table_cell` no escapa el énfasis. El escape de texto debe incluir `*`, `_`, `~`, `[`, `]` y `` ` `` (ya previsto en PLAN §3.2 `_text.py`; ahora confirmado) |

## Conclusiones para el PLAN

1. **Escape específico de ER** (`_core/mermaid.py`): `escape_mermaid_er_text()` usa entidades: `#` → `#35;` primero,
   luego `%` → `#37;`, `\` → `#92;`, `"` → `#quot;`, `[`/`]` → `#91;`/`#93;`, y saltos/controles → espacio. Se
   aplica a alias, comentarios de atributo y etiquetas de relación. `escape_mermaid_label` (flowchart de
   `comparar`) no cambia.
2. **Normalización de tipos y nombres de atributo**:
   - espacios, comas y caracteres fuera de `[\w\-()\[\]]` → `_` (Unicode permitido: validado);
   - si empieza por algo que no es letra, se antepone `t_`/`c_`;
   - `PK`, `FK` y `UK`, sin distinguir mayúsculas, llevan sufijo `_`;
   - si cambia el nombre, el real va al comentario.
3. **Guardas de tamaño**: como máximo 40 entidades y 50 000 caracteres por bloque. Por encima, primero sin columnas
   y después partiendo el diagrama, siempre con aviso.
4. **Nuevo riesgo (T15): Mermaid con Internet.** Zensical 0.0.71 carga Mermaid de unpkg. Sin Internet (ZIP offline
   de documentación, util_bbdd_web sin salida a Internet, ADR-007), los diagramas no se dibujan y queda el código
   fuente visible. Mitigaciones a evaluar en IMPLEMENT:
   - `mkdocs.yml` generado con un `mermaid_js` local opcional, como `mermaid_src` de `comparar`; hay que verificar
     si Zensical deja de cargar unpkg cuando ya existe `window.mermaid`;
   - en la web, la vista previa con su Mermaid 12 incrustado no tiene este problema.
5. **Diferencia de aspecto 11 frente a 12**: ELK en 12 y dagre en 11, sin efecto en la sintaxis. No se fija versión
   en la salida.

**Veredicto de C3: ✅ cumplida**, con los cambios 1–4 incorporados al PLAN y al AUDIT_PLAN.
