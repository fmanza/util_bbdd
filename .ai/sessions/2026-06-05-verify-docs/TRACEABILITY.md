# TRACEABILITY

## Session metadata
- id: 2026-06-05-verify-docs
- fecha: 2026-06-05
- rama: develop
- skill: new_feature
- fase: PLAN + IMPLEMENT + CLOSED

## Prompt issued

```
¿Se puede incluir descargar del sitio Web con mkdocs y zenical, si se puede proponer PLAN para su
actualización e incorporación a las instrucciones IA como opcion?
→ URL zensical https://zensical.org/, apruebo el plan

¿Se puede incluir descargar del sitio Web generado con mkdocs y/o zenical, --verify-tools?
Preparar PLAN
→ ambos modos (build / serve) coexistan desde el inicio

Como usar --verify-tools y --verify-build
→ Añadelo a la documentación ia en docs
```

## Context supplied

- `.github/DOCUMENTATION_STANDARD.md`
- `.github/agents/documentation-generator.agent.md`
- `.github/instructions/docs.instructions.md`
- `CLAUDE.md`
- `mkdocs.yml`
- `docs/claude_code_guide.md`

## AI output summary

1. **PLAN `--verify-tools`**: fetch webs oficiales MkDocs/Material/Zensical para validar configuración.
   Distinción clave: prohibir generación vía LLM externo; permitir consulta de referencia oficial.
2. **IMPLEMENT `--verify-tools`**: 4 ficheros actualizados con opción opt-in y procedimiento de 4 pasos.
3. **PLAN `--verify-build`**: dos modos — Modo A (`build --strict` + Read `site/`) y Modo B (`serve` + WebFetch localhost); tabla de verificaciones (alias bug, snippets, Mermaid, nav).
4. **IMPLEMENT `--verify-build`**: Paso 7 completo en `documentation-generator.agent.md`; sección en `docs.instructions.md`; Fase 7 en `CLAUDE.md`; tabla §5 actualizada en `DOCUMENTATION_STANDARD.md`.
5. **Guía de usuario**: `docs/doc_verification_guide.md` (Arquetipo 3, 5 secciones), registrada en `mkdocs.yml` bajo `Herramientas IA`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Paso 0 (`--verify-tools`) + Paso 7 (`--verify-build`) | `.github/agents/documentation-generator.agent.md` | modificado |
| Secciones `--verify-tools` y `--verify-build` | `.github/instructions/docs.instructions.md` | modificado |
| Fase 7, contrato documental §6 | `CLAUDE.md` | modificado |
| URLs §2.1, tabla §5 con Fases 6 y 6b | `.github/DOCUMENTATION_STANDARD.md` | modificado |
| Guía de usuario Arquetipo 3 | `docs/doc_verification_guide.md` | creado |
| Entrada nav `Herramientas IA` | `mkdocs.yml` | modificado |
| Registro sesión | `.ai/sessions/2026-06-05-verify-docs/` | creado |

## Veredicto final

Veredicto: CLOSED
Pendientes al cierre:
- Ninguno. Todas las opciones están documentadas e incorporadas en las instrucciones IA y en la guía pública.

## Directrices para Futuras IAs

- `--verify-tools` y `--verify-build` son **modificadores de prompt** para el agente `Documentation Generator`, no flags de CLI del sistema operativo.
- El Modo B de `--verify-build` requiere confirmación del usuario antes de arrancar el servidor (`zensical serve` / `mkdocs serve`).
- La distinción clave que no debe perderse: `--verify-tools` consulta webs externas de referencia; `--verify-build` ejecuta el build local y lee el HTML de `site/` o `localhost:8000`.
- El "alias bug" (directiva `:::` apunta a alias de variable, no a clase real) solo es detectado mediante `--verify-build`; no es visible en el Markdown fuente.
