# Instrucciones para GitHub Copilot Chat — util_bbdd

## ⚠️ Contexto previo obligatorio

Lee **primero** estos ficheros en este orden:

1. **[`SHARED_INSTRUCTIONS.md`](SHARED_INSTRUCTIONS.md)** — Fuente canónica: arquitectura de util_bbdd, SOLID,
   calidad, comandos de desarrollo, documentación, flujo de trabajo, Conventional Commits.
2. **Este fichero** — Especialización para Copilot Chat en VS Code/GitHub únicamente.

---

## Agentes disponibles en Copilot Chat

Usa estos agentes cuando solicites trabajo estructurado. Cada agente implementa una fase
del flujo canónico `PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION`.

| Agente | Fase | Propósito |
|---|---|---|
| **Workflow Director** | Clasificación | Clasificar la solicitud y elegir la fase o prompt siguiente |
| **Plan Architect** | PLAN + AUDIT_PLAN | Preparar plan, contrastar con código real, detectar riesgos y expansion de alcance |
| **Feature Implementer** | IMPLEMENT | Ejecutar cambios con alcance aprobado, aplicar patches acotados |
| **Hotfix Responder** | RCA + FIX + AUDIT_CODE + VERSION | RCA mínimo, fix acotado (P1/P2 sin refactorizar) |
| **Code Auditor** | AUDIT_CODE | Revisar bugs, edge cases, contratos, cobertura, arquitectura |
| **Security Reviewer** | security_review | Auditoría de seguridad independiente (auth, secretos, validación) |
| **Performance Auditor** | auditoría de rendimiento | Rendimiento de `bulk/` y `dump/` con impacto % estimado |
| **Documentation Reviewer** | audit (modo lectura) | Revisar docs, ejemplos, coherencia, gaps (sin editar) |
| **Documentation Generator** | IMPLEMENT (modo escritura) | Generar docs funcional/técnica con Mermaid en `docs/` |
| **Config Reviewer** | auditoría de configuración IA | Revisar y consolidar instrucciones IA, eliminar duplicación |
| **Explore** | lectura | Exploración rápida del repo, responder preguntas (sin editar) |
| **Maturity Assessment** | evaluación | Evaluar madurez del repositorio (estructura, tests, contratos, readiness) |
| **Version Closer** | VERSION | Resumir cambios, evidencias, pendientes, compatibilidad, rollback, directrices para futuras IAs |

Ver [`AGENTS.md`](AGENTS.md) para el registro completo.

---

## Flujo recomendado en Copilot Chat

Para cambios no triviales, usa el flujo estructurado con agentes:

```text
→ Workflow Director (clasificar)
→ Plan Architect (preparar PLAN + AUDIT_PLAN)
→ Feature Implementer (ejecutar IMPLEMENT)
→ Code Auditor (verificar AUDIT_CODE)
→ Version Closer (cerrar VERSION)
```

**Solicitud de ejemplo para nueva feature**:

```markdown
Trabaja sobre util_bbdd. Usa agentes si es necesario.

Objetivo: [describe el cambio]
Alcance: [rutas o módulos: bulk/, metadata/, dump/, etc.]
Restricciones: [compatibilidad, no refactor, docs, etc.]

Primero revisa .github/SHARED_INSTRUCTIONS.md.
Luego planifica, implementa, audita y cierra versión.
```

| Escenario | Recomendación |
|---|---|
| Cambio pequeño (1-2 archivos, acotado) | Copilot Chat directo (sin agentes) |
| Nueva feature compleja (5+ archivos) | Plan Architect → Feature Implementer |
| Bug P1/P2 que requiere RCA | Hotfix Responder |
| Auditoría de código existente | Code Auditor |
| Pregunta rápida sobre arquitectura | Explore |
| Documentación nueva o actualización | Documentation Generator |
| Revisión de docs para gaps | Documentation Reviewer |
| Cambios en instrucciones IA | Config Reviewer |

---

## Reglas específicas para Copilot Chat

### Uso de `#file:` y selección

- Si usas `#file:` o selecciones de código, contrástalo con el árbol real del repositorio
- No asumir rutas basadas en títulos de ficheros; verifica con `file_search` si es necesario

### Contradicciones y referencias

- Si una instrucción IA contradice `pyproject.toml` o el código real,
  **prioriza el código real** y explicita el supuesto en tu respuesta
- No propongas módulos, archivos o clases sin comprobar antes que existen en `src/util_bbdd/`
  (usa `grep_search` / `file_search`)

---

## Documentación con Copilot Chat

Punto único de entrada: **`@Documentation Generator`**. Arquetipos, secciones fijas y flujo por fases:
[`DOCUMENTATION_STANDARD.md`](DOCUMENTATION_STANDARD.md) §3 y §5. Reglas comunes (Zensical,
`mkdocs.yml`, Mermaid, no inventar, sin APIs de IA externas, validación de Markdown):
`SHARED_INSTRUCTIONS.md` § «Documentación obligatoria».

```markdown
@Documentation Generator

Genera documentación funcional y técnica para [ruta_del_módulo].
Aplica functional_doc.prompt.md y technical_doc.prompt.md.
Guarda en docs/functional/[nombre].md y docs/api/[nombre].md y actualiza mkdocs.yml.
No inventes capacidades; marca como pendiente lo no verificable.
```

Para auditar sin editar: **`@Documentation Reviewer`** con `.github/prompts/documentation_review.prompt.md`.

---

## Bootstrap de configuración IA a otro proyecto

Usa [`bootstrap_ai_config.prompt.md`](prompts/bootstrap_ai_config.prompt.md) (modelo **PULL**: se
invoca desde el proyecto destino) y audita el resultado con **Config Reviewer** en modo bootstrap.

---

## Integración con Claude Code

- Cambios hechos con Claude Code (`/new-feature`, `/hotfix`…) se auditan aquí con **Code Auditor**
- Documentación generada en Claude Code se revisa con **Documentation Reviewer**
- La configuración IA se sincroniza con **Config Reviewer** (`/config-review` en Claude Code)

---

## Checklist de sincronización

Sigue `SHARED_INSTRUCTIONS.md` § «Gobernanza de plataformas IA». Usa `grep_search` para verificar
que no quedan referencias heredadas antes de cerrar un PR de instrucciones IA.

---

*Actualizado: 2026-09-25*
