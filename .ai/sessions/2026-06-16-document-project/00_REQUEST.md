# REQUEST — 2026-06-16-document-project

## Inputs recibidos

| Parámetro | Valor |
|---|---|
| Origen | `C:\Desarrollo\python\libs\util_bbdd` |
| Destino | `C:\Desarrollo\python\libs\util_bbdd\docs` |
| Generador | `mkdocs-material` |
| Idioma | `es` |
| Alcance | Proyecto completo |
| Verificación | Sin `--verify-build` explícito |

## Objetivo operativo

Revisión documental profunda tomando como referencia las instrucciones IA propias del proyecto (CLAUDE.md, SHARED_INSTRUCTIONS.md, `.ai/*.md`) para detectar y corregir:

1. Gaps en el checklist Fase 0b (assets MkDocs)
2. Contexto `.ai/` desactualizado respecto a v0.10.0
3. Documentación Arquetipo 10 (`docs/ai-config/claude.md`) incompleta
4. Inconsistencias entre instrucciones IA y documentación publicada

## Restricciones

- No modificar código fuente del origen (solo docs y contexto `.ai/`)
- No inventar módulos ni APIs no presentes en el código
- Usar las propias instrucciones IA del proyecto como criterio de completitud
