# AUDIT_PLAN — U-11.1 (G50) y U-11.2 (G51)

Revisión del [PLAN](PLAN.md). Incluye la verificación de T3/T4 que la web dejó pendiente.

## Verificación T3/T4 (hecha en esta fase, 2026-11-06)

Montaje: documentación Markdown de un SQLite de dos tablas con `mermaid_js` (`mermaid@12.2.0` de la web, 5,5 MB);
copia de la carpeta sin `docs/assets/javascripts/mermaid.min.js` (equivale a `mermaid_js_ref` sin poner el
fichero). Zensical 0.0.71, MkDocs 1.6.1 + Material 9.7.7. Script y salida en el scratchpad de la sesión (no se
versionan).

| Caso | `zensical build --strict` | `mkdocs build --strict` | Página publicada |
|---|---|---|---|
| Con el fichero | OK, «No issues found» | OK | `<script src="../../assets/javascripts/mermaid.min.js">` y el fichero en `site/` |
| **Sin el fichero (T3)** | **OK, sin aviso** | **OK, sin aviso** | La misma etiqueta `<script>`, que dará 404 |
| **Comportamiento en el navegador (T4)** | Bundle: `typeof mermaid=="undefined" … ? load("https://unpkg.com/mermaid@11/dist/mermaid.min.js")` | Mismo código en el bundle de Material | Con Internet, los diagramas se dibujan con Mermaid **11** de unpkg; sin Internet se quedan como bloque de código |

Conclusiones que se documentan en `docs/api/database_documentation.md` (condición del usuario):

- El build **no detecta** la referencia rota: quien use `mermaid_js_ref` relativo es responsable de poner el fichero en
  `docs/<ruta>` antes de publicar.
- T4 se verificó leyendo el bundle y el HTML generados, **no** en un navegador; es suficiente porque el código es
  explícito, pero se anota así.
- `theme.font: false` (que se mantiene con ruta relativa) no afecta a esa recarga de unpkg.

## Funcional

- **F1** `mermaid_js_ref` relativo sin el fichero no da error en util_bbdd (no puede saberlo: la ruta es del sitio
  publicado). Correcto, con la documentación de T3/T4.
- **F2** `mermaid_js_ref` con `mkdocs_yml=False`: no hace nada; aviso en el log. Aceptado (error rompería a quien
  tenga una configuración compartida).
- **F3** `pages` incluye `traceability.md` y `changes.md` solo si se generan; `database/*` según sus flags. Las
  secciones vacías (sin vistas) no aparecen, igual que en la `nav`.
- **F4** `changes.json`, `catalog.json`, `llms*.txt` no son páginas: no van en `pages` (siguen en `files`).

## Técnico

- **T1** Capas: la validación de `mermaid_js_ref` vive en `documentation_orchestrator.py` (aplicación), junto a la
  de `mermaid_js`, sin importar la infraestructura. `python scripts/gen_arquitectura_capas.py` no debería cambiar
  (no hay imports nuevos entre paquetes de primer nivel); se ejecuta igualmente.
- **T2** **Huérfanos (hallazgo de esta auditoría)**: una carpeta generada con `mermaid_js` lista la copia en
  `manifest.json`; si se regenera con `mermaid_js_ref` a esa misma ruta, `_remove_orphans` la borraría (está intacta y
  ya no se genera) y el sitio perdería Mermaid justo en el caso de uso de G50. *Condición*: `publish(keep=…)` con
  `docs/<ref>` y test. Tras esa generación el fichero queda fuera del manifiesto, es decir, «ajeno»: no se vuelve a
  tocar. En la web no ocurre (cada ejecución usa una carpeta nueva).
- **T3** `mkdocs_yml` gana `mermaid_ref` con defecto: sin cambio para quien lo llame (módulo privado). Si llegan
  `with_mermaid_js=True` y `mermaid_ref`, gana el error de configuración antes (no es alcanzable).
- **T4** `index_page_titles` comparte la paginación con `index_pages` mediante un helper privado: es extraer código
  (refactor mínimo) en una función tocada por la feature; justificado para no duplicar la regla de paginación.
  Sin cambios de salida: el test existente de `index_pages` debe seguir verde sin tocarlo.
- **T5** Títulos en texto plano: se calculan desde el valor original (`f"Tabla: {name}"` → `plain_text`), no
  desescapando el H1. Test con `_`, `|`, `*`, `<`, `&` y salto de línea. *Condición* del usuario.
- **T6** `format_version` 2: la lectura de un manifiesto anterior solo usa `format` y `files` (`_writer.py`
  `_previous_files`); test con un v1 escrito a mano. *Condición* del usuario («v1 se sigue leyendo»).
- **T7** Determinismo: `pages` sin fechas ni rutas absolutas; ordenado por la librería, no por `sorted()` del path.
- **T8** LSP/ISP: sin cambios en puertos ni en managers sync/async; la API pública solo gana una clave de `imprimir`
  y un campo del manifiesto.
- **T9** Rendimiento: una entrada por página en memoria (~150 B): despreciable frente a `llms-full.txt`.

## Seguridad

- **S1** `mermaid_js_ref` → YAML con `json.dumps` (escalar entre comillas): sin inyección de claves ni de etiquetas
  `!!python/…`. Test con comillas, `#`, `: ` y salto de línea (este último, rechazado antes).
- **S2** Solo `https://` y rutas relativas sin `..`: ni `javascript:` ni `data:` ni rutas que salgan de `docs/`.
- **S3** `title` lleva texto de la BD **sin escapar** (es el propósito de T5): el contrato lo dice expresamente
  («texto plano no confiable; escápalo al pintarlo»). Va en JSON (`json.dumps`), así que el fichero es seguro.
- **S4** `keep` en `publish` solo protege rutas dentro de la carpeta de salida (se reutiliza `_inside`).

## Simplificaciones

- Sin `nav.json` aparte (D11-2 de la web): el manifiesto ya existe y ya es la lista de ficheros.
- Sin comprobar que el fichero de `mermaid_js_ref` existe en la carpeta de salida: la referencia es del sitio
  publicado, no de util_bbdd.

## Veredicto

**GO_CONDICIONAL** — condiciones:

1. T2: `keep` en `publish` con test de regeneración `mermaid_js` → `mermaid_js_ref`.
2. T5: títulos en texto plano con test de caracteres especiales.
3. T6: test con manifiesto v1.
4. T3/T4: documentados en `docs/api/database_documentation.md` con la tabla de arriba (verificados en esta fase).
5. Comandos de desarrollo completos (`ruff`, `mypy`, `pytest`, `zensical build --strict`,
   `gen_arquitectura_capas.py`) antes de cada commit.

Pendiente de tu aprobación para pasar a IMPLEMENT (U-11.1 primero, un commit; luego U-11.2).
