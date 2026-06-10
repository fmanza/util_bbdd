# REQUEST

## Session metadata
- id: 2026-06-11-document-project
- fecha: 2026-06-11
- rama: develop
- skill: document-project
- fase solicitada: INVENTARIO → PLAN_DOC → GENERACIÓN → SYNC NAV → BUILD (--verify-build)

## Solicitud original saneada

El usuario invoca `/document-project` para documentar el proyecto `util_bbdd`:

```
Origen:    C:\Desarrollo\python\libs\util_bbdd
Destino:   C:\Desarrollo\python\libs\util_bbdd\docs
Generador: mkdocs-material
Idioma:    es
Flags:     --verify-build
```

El inventario identificó tres símbolos públicos añadidos al código fuente (commits `8964630`,
`ad2fd15`, `5a9f400`) que no estaban documentados en ningún fichero de `docs/`:

- `RangePartitioner` — `src/util_bbdd/bulk/_execution/range_partitioner.py`
- `HashPartitioner` — mismo fichero
- `BulkCrud.maintenance_scope` — `src/util_bbdd/bulk/crud.py:801`

Adicionalmente se detectó la ausencia del Arquetipo 10 (Config Agente IA) pese a que el
proyecto tiene CLAUDE.md, GEMINI.md y `.claude/settings.json` configurados.

## Restricciones operativas

- Sin API keys. Sin invocaciones a servicios IA desde código.
- Generación de contenido ocurre exclusivamente en este chat.
- No modificar código fuente del origen.
- `--verify-build`: el build debe pasar con 0 warnings en strict mode.
