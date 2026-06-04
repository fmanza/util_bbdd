# Instrucciones para Claude Code — util_bbdd

Este fichero proporciona especialización a Claude Code cuando trabaja con util_bbdd,
incluyendo slash commands, hooks de desarrollo y configuración integrada.

---

## ⚠️ Contexto previo obligatorio

Lee **primero**:
- **`.github/SHARED_INSTRUCTIONS.md`** — Fuente canónica: arquitectura TIMELOG, SOLID, calidad,
  comandos, documentación, flujo de trabajo, Conventional Commits. **Esta es la base.**
- **Este fichero** — Especialización para Claude Code únicamente.

---

## Slash commands de Claude Code

Usa estos comandos para activar flujos estructurados con automatización integrada:

| Comando | Propósito | Entrada | Salida |
|---|---|---|---|
| `/new-feature` | Nueva funcionalidad | Descripción + módulos | PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION |
| `/hotfix` | Bug P1/P2 mínimo | Descripción + impacto | RCA → FIX → AUDIT_CODE → VERSION |
| `/refactor` | Refactor sin cambios funcionales | Área + objetivo | PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE |
| `/audit-code` | Auditoría técnica independiente | Rutas o cambios | Scope → Findings → Verdict |
| `/security-review` | Auditoría de seguridad | Áreas críticas | Findings by severity → Remediation |
| `/tech-debt` | Deuda técnica priorizada | Área o módulo | Findings por severidad → Plan de remediación |
| `/maturity-assessment` | Evaluación de madurez del repo | Área o evaluación completa | Executive summary → Findings → Maturity verdict |
| `/version-closure` | Cierre de versión | Sesión completada | Release notes → Changelog → Rollback → Handoff |

**Ejemplo de uso**:

```
/new-feature

Objetivo: Añadir soporte para exportación a Parquet en timelog/

Alcance: timelog/export_parquet.py (nuevo), tests/unit/timelog/test_export_parquet.py (nuevo)

Restricciones:
  - Mantener compatibilidad con exports existentes (Excel, CSV, JSON)
  - Usar pandas.DataFrame.to_parquet()
  - Documentación en docstrings + ejemplo en README
```

---

## Configuración: Hooks y PostToolUse

Lee [`.claude/README.md`](./.claude/README.md) para detalles completos sobre hooks:

```
.claude/
  settings.json           ← Configuración: ruff, mypy, pytest hooks
  settings.json.example   ← Plantilla de ejemplo
  settings.local.json     ← Personalización local (no versionado, git-ignored)
  commands/               ← Slash commands personalizados
  EDGE_CASES.md           ← Casos límite conocidos en el proyecto
  TESTING_GUIDE.md        ← Guía de testing con PostToolUse
```

**Orden de ejecución automático típico**:

1. **Cambios de código** → `ruff format src tests` (aplicar formato)
2. **Validación estilo** → `ruff check src tests` (linting)
3. **Validación tipos** → `mypy src` (type-checking)
4. **Ejecución tests** → `pytest` (tests relevantes o suite completa)
5. **Retroalimentación** → Si fallan tests, Claude Code itera correcciones

**Configuración manual** (si es necesario):
```bash
# Instalar hooks locales en .claude/settings.local.json
# (no afecta otros clones del repositorio)
cp .claude/settings.json.example .claude/settings.local.json
# Edita .claude/settings.local.json con configuración personal
```

---

## Flujo estructurado de Claude Code

Cada slash command activa un flujo completo con fases definidas:

### `/new-feature`
```
Fase 1: PLAN → Analizar objetivo, alcance, riesgos, candidatos para cambio
Fase 2: AUDIT_PLAN → Verificar plan, detectar expansion, validar viabilidad
Fase 3: IMPLEMENT → Aplicar cambios, actualizar tests, ejecutar suite
Fase 4: AUDIT_CODE → Revisión independiente de calidad
Fase 5: VERSION → Changelog, commit message, rollback documentation
```

### `/hotfix`
```
Fase 1: RCA (Root Cause Analysis) → Identificar causa raíz del bug
Fase 2: FIX → Aplicar fix mínimo acotado (NO refactorizar)
Fase 3: AUDIT_CODE → Verificar fix, edge cases, pruebas
Fase 4: VERSION → Changelog, commit, rollback steps
Restricción: No refactorizar ni optimizar; solo fix
```

### `/audit-code`
```
Fase 1: Scope → Identificar archivos y responsabilidades
Fase 2: Findings → Hallazgos verificables (bugs, edge cases, contratos rotos)
Fase 3: Verdict → APROBADO | APROBADO CON CONDICIONES | RECHAZADO
Nota: Modo lectura; no edita código. Entrega hallazgos y recomendaciones.
```

### `/tech-debt`
```
Fase 1: Scope → Identificar módulo o área con deuda acumulada
Fase 2: Findings → Clasificar deuda por severidad (alta / media / baja)
Fase 3: Plan → Ordenar por impacto/esfuerzo, proponer remediaciones acotadas
Nota: No aplica cambios; entrega plan de trabajo priorizado.
```

### `/maturity-assessment`
```
Fase 1: Scope → Inventariar estructura, contratos, tests y docs del repo
Fase 2: Findings → Evaluar madurez por área (arquitectura, tipado, cobertura, seguridad)
Fase 3: Verdict → Maturity level + blockers para publicación
Nota: Solo lectura; no edita código.
```

### `/version-closure`
```
Fase 1: Resumen → Consolidar todos los cambios de la sesión
Fase 2: Validación → Verificar CHANGELOG.md, COMPATIBILITY.md y mkdocs build
Fase 3: Handoff → Release notes, commit message, rollback strategy;
         poblar ## Directrices para Futuras IAs en .ai/sessions/*/TRACEABILITY.md
Nota: Ver .github/instructions/sync.instructions.md para checklist obligatorio.
```

---

## Integración con Copilot Chat

Esta especialización es **compatible con agentes Copilot Chat**:

| Cambio en Claude Code | Auditoría en Copilot Chat | Propósito |
|---|---|---|
| `/new-feature` + IMPLEMENT (cambios acotados) | Code Auditor (agente) | Verificación independiente |
| `/new-feature` + documentación en `docs/` | Documentation Reviewer (agente) | Validar ejemplos y coherencia |
| Cambios en `.github/SHARED_INSTRUCTIONS.md` | Config Reviewer (agente) | Validar DRY y consistencia entre plataformas |

**Flujo bidireccional recomendado**:

1. **Claude Code**: `/new-feature` → completa PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION
2. **Copilot Chat**: Code Auditor → verifica cambios de Claude Code independientemente
3. **Copilot Chat**: Version Closer → cierre final y changelog consolidado

**Comunicación entre plataformas**:
- Claude Code escribe cambios y ejecuta tests localmente
- Copilot Chat revisa y confirma que cambios son conformes (sin ejecutar)
- Si hay discrepancias, ambas plataformas usan SHARED_INSTRUCTIONS.md como fuente de verdad

---

## Comparativa: Claude Code vs. Copilot Chat

| Aspecto | Claude Code | Copilot Chat |
|---|---|---|
| **Invocación** | Slash commands (`/new-feature`, etc.) | Agentes con nombres + descripción |
| **Ejecución de tests** | Automática via PostToolUse (hooks) | Manual (run_task, run_in_terminal) |
| **Contexto inicial** | Archivo abierto + prompt slash command | Contexto seleccionado + agente name |
| **Mejor para** | Cambios estructurados, flujos completos | Consultas rápidas, auditorías independientes |
| **Ciclo de feedback** | Iterativo local (hosteado localmente) | Iterativo conversacional (en chat) |
| **Documentación** | `.claude/` (settings.json, TESTING_GUIDE.md) | `.github/copilot-instructions.md` |

---

## Documentación con Claude Code

Usa el **Documentation Generator** (agente) como **único punto de entrada** para crear o actualizar
documentación, tanto de un módulo concreto como del proyecto completo.
No uses un único prompt masivo: trabaja siempre por fases separadas.

Sigue el **flujo estándar de 7 fases** definido en [`.github/DOCUMENTATION_STANDARD.md` §5](.github/DOCUMENTATION_STANDARD.md#5-roles-de-agentes-y-flujo-de-trabajo)
y la estructura de `DOCUMENTATION_STANDARD.md` §3 (funcional) y §3.2 (técnica).

### Flujo por fases

```
Fase 1 — Inventariar: leer src/, README, docs/, docs/examples/, mkdocs.yml
Fase 2 — Mapeo funcional (Senior Product Owner): objetivo de negocio, precondiciones, flujo, reglas
Fase 3 — Documentación técnica: responsabilidad, Mermaid, API pública, contratos, errores
Fase 4 — Ejemplos verificables: código real, resultado determinista, sin credenciales reales
Fase 5 — Sincronizar mkdocs.yml: añadir/mover/retirar entradas de navegación
Fase 6 — Revisión final: validar Markdown, enlaces relativos y sintaxis Mermaid
```

### Solicitud para un módulo

```markdown
Lee [ruta_del_módulo] y genera documentación funcional y técnica.
Aplica .github/prompts/functional_doc.prompt.md y .github/prompts/technical_doc.prompt.md.
Guarda en docs/functional/[nombre].md y docs/api/[nombre].md.
Zensical renderiza automáticamente sin requiere actualización manual.
No inventes módulos ni capacidades; marca como pendiente lo no verificable.
```

### Solicitud para proyecto completo

```markdown
Revisa el proyecto completo y actualiza la documentación pública.
Fases: (1) inventariar módulos reales, (2) mapeo funcional (Senior PO),
(3) documentación técnica con Mermaid, (4) ejemplos verificables,
(5) Zenical renderiza automáticamente.
No inventes módulos ni capacidades; marca como pendiente lo no verificable.
No uses APIs externas por el momento.
```

### Contrato documental obligatorio

1. Revisar documentación existente antes de crear páginas nuevas; actualizar si el tema ya está cubierto.
2. Separar siempre los apartados **funcional**, **técnico** y **ejemplos** con secciones diferenciadas.
3. Usar MkDocs Material como generador estático; Mermaid.js para diagramas verificables.
4. Actualizar `mkdocs.yml` cuando se creen, muevan o eliminen páginas en `docs/`.
5. No inventar capacidades, módulos, APIs, salidas, errores ni dependencias.
6. Excluir generación documental mediante APIs externas por el momento.

### Auditoría de documentación (solo lectura)

```markdown
Revisa docs/, docs/examples/, README y mkdocs.yml para detectar gaps.
Usa .github/prompts/documentation_review.prompt.md como criterio.
Entrega hallazgos con severidad (Nivel 1/2/3) sin editar archivos.
```
Criterio de completitud: `zensical build` sin errores + todos los módulos de `src/` documentados.
---

## Checklist de sincronización

Cuando actualices **`.github/SHARED_INSTRUCTIONS.md`**, verifica:

- [ ] Ambos ficheros (CLAUDE.md y `.github/copilot-instructions.md`) contienen referencias sincronizadas
- [ ] No hay duplicación de reglas entre `SHARED_INSTRUCTIONS.md` y especializaciones
- [ ] Rutas de archivos son relativas (`./.github/`, `./.claude/`, no `file://...`)
- [ ] Tabla de gobernanza en SHARED_INSTRUCTIONS.md refleja responsabilidad de cada fichero
- [ ] Timestamps de actualización están sincronizados en ambos ficheros
- [ ] Si cambias slash commands, actualiza tabla de comandos en este fichero

---

## Comandos útiles referenciados

Consulta SHARED_INSTRUCTIONS.md para detalles completos:

```bash
python -m ruff check src tests      # Linting
python -m ruff format src tests     # Formato
python -m mypy src                  # Type-checking
python -m pytest                    # Tests
python -m build                     # Empaquetamiento
mkdocs serve                        # Documentación local
```

---

*Actualizado: 2026-06-02*
