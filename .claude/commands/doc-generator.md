# doc_generator

Genera o actualiza documentación funcional, técnica y de ejemplos de util_bbdd (con Mermaid), manteniendo `docs/` y
`mkdocs.yml` alineados con el código real. Modo escritura, con las restricciones del agente (§ «Restricciones»).

## Contexto obligatorio

Lee y aplica, en este orden:
1. `.github/agents/documentation-generator.agent.md` — rol, flujo por fases, restricciones y formato de salida
2. `.github/DOCUMENTATION_STANDARD.md` — arquetipos (§3), `mkdocs.yml` (§4) y flujo de agentes (§5)
3. `.github/prompts/functional_doc.prompt.md` y/o `.github/prompts/technical_doc.prompt.md` — según el tipo pedido
4. `.github/prompts/mkdocs_nav_update.prompt.md` — al crear, mover o retirar páginas

## Reglas de ejecución

- **⚠️ VALIDACIÓN**: si no se especifica módulo (o «proyecto completo») ni tipo de documentación, DETENTE y pídelos.
- Opciones: `--verify-build` (build `--strict` + inspección de `site/`), `--verify-build --serve` (confirmar antes de
  arrancar el servidor), `--verify-tools` (consulta de notas de versión; no edita nada).
- Proyecto completo: agente § «Cobertura de proyecto completo».
- Para auditar sin editar, usa el agente Documentation Reviewer (`.github/prompts/documentation_review.prompt.md`).

## Ejemplo de entrada

```text
/doc-generator

Módulo: src/util_bbdd/dump/
Tipo: both (functional + technical)
Destino: docs/functional/dump.md y docs/api/dump.md
Opciones: --verify-build
```
