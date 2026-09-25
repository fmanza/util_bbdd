# Quick Start — Claude Code en util_bbdd

Bienvenido. Esta guía te ayuda a invocar slash commands rapidamente.

---

## Slash Commands Disponibles

### 1. `/new-feature` — Nueva Funcionalidad
```
/new-feature

Objetivo: [describe el cambio]
Alcance: [módulos: timelog/, common/, etc.]
Restricciones: [compatibilidad, no refactor, docs, etc.]
```
→ PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION

---

### 2. `/hotfix` — Bug P1/P2 Mínimo
```
/hotfix

Objetivo: [describe el bug]
Impacto: [P1/P2, qué falla]
Restricción: NO refactorizar, solo fix acotado
```
→ RCA → FIX → AUDIT_CODE → VERSION

---

### 3. `/audit-code` — Auditoría de Código
```
/audit-code

Rutas: [src/util_bbdd/bulk/, etc. o cambios específicos]
Foco: [bugs, edge cases, contratos, cobertura, arquitectura]
```
→ Modo lectura; entrega hallazgos y recomendaciones (no edita)

---

### 4. `/performance-audit-bulk` — Auditoría de Rendimiento (Bulk)

**👉 Este es el recomendado para auditar carga masiva (INSERT/UPDATE/DELETE)**

```
/performance-audit-bulk

Objetivo: Auditar rendimiento del módulo bulk (carga masiva de datos)

Alcance: src/util_bbdd/bulk/ — todas las clases y funciones

Inputs requeridos:
  - Objetivo: paralelización + batching (o: SQL, conexiones, memoria, auditoría, todas)
  - Baseline: no (¿ejecutar benchmark primero?)
  - Dialects: PostgreSQL + MySQL + SQL Server (o: Oracle, SQLite, todas)
  - Volumen: 100K registros típicos (o: 1K, 1M, otro)
  - Timeline: ASAP (o: próxima semana, flexible)
  - Validación post-audit: sí (o: no)

Puedes consultar internet para best practices.
```

→ PLAN → AUDIT_PLAN → AUDIT_CODE → VERSION (con % impacto)

**Referencia completa**: [`.claude/commands/performance-audit-bulk.md`](./commands/performance-audit-bulk.md)

---

### 5. `/security-review` — Auditoría de Seguridad
```
/security-review

Áreas críticas: [auth, secretos, validación de entrada, logging, dependencias]
Foco: [severidad, remediación, compatibilidad]
```
→ Findings by severity → Remediation

---

### 6. `/tech-debt` — Deuda Técnica
```
/tech-debt

Área: [módulo o package]
Restricción: NO implementar, solo análisis y priorización
```
→ Findings por severidad → Plan de remediación

---

### 7. `/maturity-assessment` — Evaluación de Madurez
```
/maturity-assessment

Alcance: [evaluación completa del repo]
Foco: [arquitectura, tipado, tests, cobertura, seguridad]
```
→ Executive summary → Findings → Maturity verdict

---

### 8. `/refactor` — Refactor Sin Cambios Funcionales
```
/refactor

Área: [módulo específico]
Objetivo: [p.ej. simplificar lógica, mejorar nombres, reducir LOC]
Restricción: NO cambios funcionales, solo mejoras de calidad
```
→ PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE

---

### 9. `/version-closure` — Cierre de Versión
```
/version-closure

Sesión completada: [describe qué hiciste]
```
→ Release notes → Changelog → Rollback → Handoff

---

## Configuración Local (Opcional)

Si la ejecución automática de hooks es lenta, personaliza `.claude/settings.local.json`:

```bash
# Crear archivo local (no se commitea)
cp .claude/settings.json.example .claude/settings.local.json

# Editar: desabilitar hooks lentos (p.ej. mypy)
# {
#   "hooks": {
#     "PostToolUse": [
#       {
#         "matcher": "Edit|Write",
#         "hooks": [
#           { "type": "command", "command": "python -m ruff check src tests --quiet" }
#         ]
#       }
#     ]
#   }
# }
```

---

## Checklist Antes de Invocar

- [ ] `.github/SHARED_INSTRUCTIONS.md` — Léelo (arquitectura, métodos, estándares)
- [ ] Este fichero — Identifica qué comando necesitas
- [ ] Contexto mínimo — Archivo abierto o sección seleccionada
- [ ] `.claude/commands/{comando}.md` — Consulta si es complejo

---

## Troubleshooting

**P: El comando tarda mucho (>5 min)**  
R: Aborta y reduce scope (p.ej. un módulo en lugar de todo el repo).

**P: No aparece el slash command en autocompletar**  
R: Actualiza el workspace o reinicia VS Code.

**P: Necesito personalizar un comando**  
R: Crea `.claude/settings.local.json` con hooks personalizados.

**P: Quiero que el agente consulte internet**  
R: Algunos comandos (p.ej. `/performance-audit-bulk`) permiten "consulta internet" para best practices.

---

## Referencias

- **Metodología canónica**: [`.github/SHARED_INSTRUCTIONS.md`](../.github/SHARED_INSTRUCTIONS.md)
- **Especializaciones Claude Code**: [`CLAUDE.md`](../CLAUDE.md)
- **Guías de comandos**: [`.claude/commands/`](./commands/)
- **Documentación oficial**: [`docs/`](../docs/) + [`README.md`](../README.md)

---

**Pro tips**:
- Cada comando genera artifacts (reports, roadmaps) que se guardan en raíz o `.ai/audit/`
- Puedes encadenar comandos (p.ej. PLAN con Plan Architect, luego IMPLEMENT con Feature Implementer)
- Siempre sincroniza cambios de instrucciones IA entre `SHARED_INSTRUCTIONS.md`, `CLAUDE.md` y `.github/copilot-instructions.md`

*Última actualización: 2026-09-25*
