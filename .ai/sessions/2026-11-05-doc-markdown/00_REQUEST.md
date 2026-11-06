# REQUEST

## Session metadata
- id: 2026-11-05-doc-markdown
- fecha: 2026-11-05
- rama: develop
- skill: new_feature (prompt `.github/prompts/doc_markdown_feature.prompt.md`)
- fase solicitada: PLAN y AUDIT_PLAN (sin IMPLEMENT)

## Solicitud original saneada

- Incluir en `src/util_bbdd/doc` la generación de documentación en Markdown.
- El formato de salida sigue las mismas reglas que Word, salvo alternativas propuestas.
- La documentación la usará luego una IA para interpretarla y trazarla con código y documentos funcionales y
  técnicos: dar opciones.
- Diagramas entidad-relación en Mermaid.
- Decidir si la profundidad de las relaciones se queda siempre en uno (avisándolo) o usa la variable de niveles.
- Paginación: hay esquemas de más de 500 tablas. ¿Un fichero por tabla o por paquetes?
- Tener en cuenta `C:\Desarrollo\python\libs\util_bbdd_web` como interfaz visual de la generación.
- Integrable con Zensical/MkDocs.
- Permitir la descarga del fichero o ficheros.
- Versionado de la documentación: proponer alternativas.
- No se implementa nada: PLAN y AUDIT_PLAN.

## Decisiones del usuario (2026-11-05)

| Id | Decisión |
|---|---|
| D3 profundidad | `grafo.max_depth` / `grafo.direction` con tope propio del Markdown, aviso y resumen de niveles ocultos |
| D4 paginación | Un fichero por objeto (tabla, vista, rutina) con índices paginados; sin modo `bundled` |
| D2 IA y trazabilidad | Todo en el MVP: front matter + anclas, `catalog.json`, `llms.txt` / `llms-full.txt` y mapa de trazabilidad de entrada |
| D2 formato del mapa (2026-11-06) | TOML recomendado (a mano) y JSON aceptado con el mismo esquema; se elige por extensión |
| D1, D6, F4, tope (2026-11-06) | Aceptadas las alternativas de formato y el orden alfabético; sin ZIP en la librería; lado padre `\|o` si la FK admite nulos; `max_diagram_depth = 2` |
| D7 versionado | `manifest.json` + salida determinista y, en el MVP, `CHANGES.md` respecto de una generación anterior |

## Objetivo operativo de esta sesión
- PLAN con D1–D7 resueltas (las cuatro decisiones del usuario incorporadas) y rutas, tipos, tests y fases.
- AUDIT_PLAN con riesgos funcionales, técnicos y de seguridad y veredicto.

## Restricciones explícitas
- Solo análisis: no se edita `src/`, `tests/` ni `docs/`.
- `util_bbdd_web` se lee, no se edita; sus cambios se planifican aparte.

## Resultado esperado
- `.ai/sessions/2026-11-05-doc-markdown/{00_REQUEST,00_CONTEXT_SNAPSHOT,PLAN,AUDIT_PLAN}.md`.
