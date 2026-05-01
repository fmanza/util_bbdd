# Instrucciones para GitHub Copilot Chat — util_bbdd

## ⚠️ Contexto previo obligatorio

Lee **primero**:
- **`.github/SHARED_INSTRUCTIONS.md`** — Fuente canónica: arquitectura TIMELOG, SOLID,
  calidad, comandos de desarrollo, documentación, flujo de trabajo, Conventional Commits.
- **Este fichero** — Especialización para Copilot Chat únicamente.

---

## Agentes disponibles en Copilot Chat

Usa estos agentes cuando solicites trabajo estructurado. Cada agente implementa una fase
del flujo canónico `PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION`.

| Agente | Fase | Propósito |
|---|---|---|
| **Workflow Director** | Clasificación | Clasificar solicitud (feature, hotfix, refactor, security_review, tech_debt, maturity_assessment, version_closure) |
| **Plan Architect** | PLAN + AUDIT_PLAN | Preparar plan, contrastar con código real, detectar riesgos y expansion de alcance |
| **Feature Implementer** | IMPLEMENT | Ejecutar cambios con alcance aprobado, aplicar patches acotados |
| **Hotfix Responder** | RCA + FIX + AUDIT_CODE + VERSION | RCA mínimo, fix acotado (P1/P2 sin refactorizar) |
| **Code Auditor** | AUDIT_CODE | Revisar bugs, edge cases, contratos, cobertura, arquitectura |
| **Security Reviewer** | security_review | Auditoría de seguridad independiente (auth, secretos, validación) |
| **Documentation Reviewer** | audit (modo lectura) | Revisar docs, ejemplos, coherencia, gaps (sin editar) |
| **Documentation Generator** | IMPLEMENT (modo escritura) | Generar docs funcional/técnica con Mermaid en `docs/` |
| **Config Reviewer** | AUDIT_CODE (configuración IA) | Revisar y consolidar instrucciones IA, eliminar duplicación |
| **Explore** | lectura | Exploración rápida del repo, responder preguntas (sin editar) |
| **Maturity Assessment** | evaluación | Evaluar madurez del repositorio (estructura, tests, contratos, readiness) |
| **Version Closer** | VERSION | Resumir cambios, evidencias, pendientes, compatibilidad, rollback |

Ver [`.github/AGENTS.md`](./.github/AGENTS.md) para registro completo.

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
Alcance: [rutas o módulos: timelog/, common/, etc.]
Restricciones: [compatibilidad, no refactor, docs, etc.]

Primero revisa .github/SHARED_INSTRUCTIONS.md.
Luego planifica, implementa, audita y cierra versión.
```

---

## Reglas específicas para Copilot Chat

### Uso de `#file:` y selección

- Si usas `#file:` o selecciones de código, contrástalo con el árbol real del repositorio
- No asumir rutas basadas en títulos de ficheros; verifica con `file_search` si es necesario

### Contradicciones y prioridades

- Si una instrucción IA contradice `pyproject.toml` o el código real,
  **prioriza el código real** y explícita el supuesto en tu respuesta
- Cuando referencias `util_bbdd` (proyecto histórico), valida que los módulos
  existan en el árbol actual

### Validación de referencias heredadas

No propongas módulos, archivos o estructuras que no existan:
- ❌ `servicios/`, `metadata/`, `bulk/` — no están en src/
- ❌ `SyncDatabaseManager`, `introspección SQL` — no están en el código actual
- ✅ Usa `grep_search` para validar antes de referenciar

### Sincronización de instrucciones IA

Si cambias reglas comunes, actualiza **en este orden**:

1. **`.github/SHARED_INSTRUCTIONS.md`** (fuente canónica) — cambios globales
2. **`.github/copilot-instructions.md`** (este fichero) — especialización Copilot, si aplica
3. **`CLAUDE.md`** — especialización Claude Code, si aplica
4. **`.github/AGENTS.md`** — actualizar si cambian agentes

**Validación**: Antes de cerrar PR de instrucciones IA, verifica que ambos ficheros
(copilot-instructions.md y CLAUDE.md) sean consistentes en estructura y que no haya
duplicación de contenido shared.

---

## Cuándo usar agentes vs. Claude Code vs. Copilot Chat directo

| Escenario | Recomendación | Razón |
|---|---|---|
| Cambio pequeño (1-2 archivos, acotado) | Copilot Chat directo (sin agentes) | Rápido y eficiente |
| Nueva feature compleja (5+ archivos, PLAN required) | Plan Architect → Feature Implementer | Flujo estructurado, verificación de riesgos |
| Bug P1/P2 que requiere RCA | Hotfix Responder | Especialización en hotfix, fix mínimo |
| Auditoría de código existente | Code Auditor | Independencia, verificación exhaustiva |
| Pregunta rápida sobre arquitectura | Explore | Lectura rápida, sin cambios |
| Documentación nueva o actualización | Documentation Generator | Escritura de docs con Mermaid |
| Revisión de docs para gaps | Documentation Reviewer | Auditoría sin escritura |
| Cambios en instrucciones IA | Config Reviewer | Especialización en DRY y gobernanza |

---

## Integración con Claude Code

Esta especialización es **compatible con Claude Code**:

- **Cambios aprobados en Claude Code** se pueden auditar con **Code Auditor** (Copilot)
- **Documentación generada en Claude Code** se revisa con **Documentation Reviewer** (Copilot)
- **Configuración IA** se sincroniza via **Config Reviewer**

**Flujo bidireccional recomendado**:
1. Claude Code: `/new-feature` → PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE
2. Copilot Chat: Code Auditor con cambios de Claude Code → verificación adicional
3. Copilot Chat: Version Closer → cierre final y changelog

---

## Checklist de sincronización

Cuando actualices **`.github/SHARED_INSTRUCTIONS.md`**, verifica:

- [ ] Ambos ficheros (copilot-instructions.md y CLAUDE.md) contienen referencias a secciones shared actualizadas
- [ ] No hay duplicación de contenido entre SHARED_INSTRUCTIONS.md y especializaciones
- [ ] Rutas de archivos son relativas y portables (`./.github/...`, no `file://...`)
- [ ] Tabla de gobernanza en SHARED_INSTRUCTIONS.md refleja responsabilidad de cada fichero
- [ ] Timestamps de actualización están sincronizados

---

*Actualizado: 2026-05-02*
