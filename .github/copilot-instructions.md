# Instrucciones de Copilot Chat para util_bbdd

## ⚠️ Notas importantes

**Lea primero**: [`.github/SHARED_INSTRUCTIONS.md`](.github/SHARED_INSTRUCTIONS.md) para arquitectura, SOLID, patrones, flujos y políticas comunes a ambas plataformas.

Esta página contiene **solo especificidades de Copilot Chat**. Todo lo demás está centralizado en SHARED_INSTRUCTIONS.md.

---

## Agentes VS Code

Usa estos agentes para orquestar el flujo PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION:

- **Workflow Director** — clasificar solicitud, validar contexto, elegir fase siguiente
- **Plan Architect** — preparar PLAN y AUDIT_PLAN, detectar riesgos
- **Feature Implementer** — ejecutar IMPLEMENT con alcance aprobado
- **Hotfix Responder** — RCA, fix mínimo, verificación
- **Code Auditor** — AUDIT_CODE de implementaciones
- **Security Reviewer** — auditoría de seguridad independiente
- **Documentation Reviewer** — auditoría de documentación, ejemplos, gaps
- **Config Reviewer** — auditoría de ficheros de configuración IA
- **Maturity Assessment** — evaluar madurez del repositorio
- **Version Closer** — cierre de versión, release notes
- **Explore** — exploración rápida, Q&A sin modificaciones

**Ver detalles completos**: [`.github/AGENTS.md`](.github/AGENTS.md) — matriz de herramientas, flujos y ejemplos de invocación.

---

## Flujos estructurados para Copilot Chat

### Flujo manual (sin slash commands)

Escribe en Copilot Chat siguiendo esta estructura:

```markdown
Voy a [implementar nueva funcionalidad / corregir un bug / refactorizar].

Sigue el flujo PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION.

Contexto:
- Objetivo: [describe el objetivo final]
- Módulos: [lista módulos afectados]
- API: [describe cambios públicos, si aplica]
- Restricciones: [tiempo, breaking changes, etc.]

Primero: emite PLAN con rutas afectadas, componentes implicados, tipos y riesgos.
Luego: emite AUDIT_PLAN con riesgos funcionales/técnicos/seguridad y veredicto.
Después: IMPLEMENT por capas (Level 1 → 2 → 3) si veredicto es GO.
Finalmente: AUDIT_CODE con hallazgos y VERSION con commit + changelog.
```

### Referencias para Copilot Chat
- Mapeo Claude Code ↔ Copilot Chat: [`docs/v0.6.7/CLAUDE_COPILOT_MAPPING.md`](../docs/v0.6.7/CLAUDE_COPILOT_MAPPING.md)
- Ejemplos completos: [`docs/v0.6.7/COPILOT_CHAT_INTEGRATION_GUIDE.md`](../docs/v0.6.7/COPILOT_CHAT_INTEGRATION_GUIDE.md)
- Prompts por tarea: [`.github/prompts/`](.github/prompts/) — 9 prompts (new_feature, hotfix, refactor, etc.)

---

## Respuesta en markdown estructurado

- Usa markdown con secciones claras: `## Sección`, `### Subsección`
- Código en bloques con lenguaje: ` ```python`, ` ```sql`
- Listas con viñetas y sub-viñetas
- Tablas para comparaciones o matrices
- No confundas `PLAN`, `AUDIT_PLAN`, `IMPLEMENT`, `AUDIT_CODE`, `VERSION` — son fases distintas

---

*Actualizado: 2026-04-18 — Config Reviewer audit*
