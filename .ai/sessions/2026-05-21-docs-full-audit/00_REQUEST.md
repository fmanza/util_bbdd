# REQUEST

## Session metadata
- id: 2026-05-21-docs-full-audit
- fecha: 2026-05-21
- rama: develop
- skill: maturity_assessment + documentation
- fase solicitada: INVENTARIO → FUNCTIONAL → TECHNICAL → EXAMPLES → SYNC → REVIEW (6 fases)

## Solicitud original saneada

Revisa el proyecto completo y actualiza la documentación pública en 6 fases:
1. Inventariar módulos reales en src/util_bbdd/ y clasificarlos.
2. Mapeo funcional con functional_doc.prompt.md por módulo sin doc o desactualizado.
3. Documentación técnica con technical_doc.prompt.md y Mermaid apropiado.
4. Ejemplos verificables en docs/examples/ para módulos sin ejemplo reproducible.
5. Sincronizar mkdocs.yml.
6. Revisión final: Markdown, enlaces y Mermaid; recomendar mkdocs build.
No inventes módulos ni capacidades. No uses APIs externas por ahora.

## Objetivo operativo de esta sesión

- Detectar gaps documentales tras la expansión reciente del módulo `migrate/` (12 flujos: 4 fuentes × 3 destinos)
- Actualizar `migrate-oracle-mariadb.md` (funcional + API + ejemplo) para reflejar Oracle como fuente multi-destino
- Crear documentación funcional, técnica y de ejemplo para MariaDB como fuente de migración
- Sincronizar `mkdocs.yml`, `DOCUMENTATION_STANDARD.md §4.2` y `SHARED_INSTRUCTIONS.md`

## Restricciones explícitas

- No inventar módulos ni capacidades no verificadas en el código real
- No usar APIs externas por el momento
- No tocar código fuente Python ni tests

## Resultado esperado

- `docs/functional/migrate-oracle-mariadb.md` actualizado (Oracle → 3 destinos)
- `docs/functional/migrate-mariadb-source.md` creado
- `docs/api/migrate-oracle-mariadb.md` actualizado
- `docs/api/migrate-mariadb-source.md` creado
- `docs/examples/migrate-oracle-mariadb.md` actualizado
- `docs/examples/migrate-mariadb-source.md` creado
- `mkdocs.yml` nav sincronizado
- `DOCUMENTATION_STANDARD.md §4.2` corregido
- `SHARED_INSTRUCTIONS.md` motores actualizados
