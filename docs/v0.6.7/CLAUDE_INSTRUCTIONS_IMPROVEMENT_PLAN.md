# Plan de Mejora de Instrucciones Claude para VS Code

**Versión**: v0.6.7-dev
**Fecha**: 10 de abril de 2026
**Alcance**: Auditoría y mejora de la integración Claude Code con Copilot Chat en VS Code
**Objetivo**: Elevar la usabilidad y consistencia de instrucciones para Claude Code y Copilot Chat

---

## Resumen ejecutivo

Se ha realizado una auditoría de:
- `CLAUDE.md` — política base transversal
- `.claude/` — slash commands y configuración de hooks
- `docs/examples/claude_code_usage_complete_example.md` — documentación de ejemplo

Se identificaron **10 categorías de mejora** que impactan la experiencia de usuario, consistencia y robustez de la configuración. Los hallazgos se clasifican según impacto: **bloqueante** (4), **mejora recomendada** (4) y **informativo** (2).

---

## Hallazgos por categoría

### 1. **[BLOQUEANTE] Falta mapeo explícito entre Claude Code y Copilot Chat**

#### Problema
- Los slash commands de `.claude/commands/` están optimizados para Claude Code (CLI/extensión Anthropic)
- No existe documentación clara sobre cómo traducir estas instrucciones a Copilot Chat (GitHub/VS Code)
- Usuarios de Copilot Chat no saben cómo activar el flujo `PLAN → AUDIT_PLAN → IMPLEMENT`
- El documento `claude_code_usage_complete_example.md` asume Claude Code; falta equivalencia con Copilot

#### Impacto
- Confusión sobre qué herramientas usar
- Adopción parcial de la metodología PLAN/AUDIT_PLAN
- Inconsistencia entre equipos (algunos usan Claude Code, otros Copilot Chat)

#### Evidencia
- `.claude/commands/` no tiene metadata sobre compatibilidad Copilot
- `claude_code_usage_complete_example.md:80–90` menciona "Diferencia con Copilot" pero no detalla mapeo completo
- `CLAUDE.md` no menciona cómo activar comandos equivalentes en Copilot Chat

#### Solución propuesta
- Crear matriz de equivalencias: slash command Claude Code ↔ prompt Copilot Chat
- Añadir sección "Equivalencia Copilot Chat" en cada archivo `.claude/commands/*.md`
- Documentar cómo invocar flujos desde Copilot: `@prompt /new-feature` (si existe) o equivalente

#### Prioridad
**ALTA** — bloquea adopción coherente de la metodología en ambas plataformas

---

### 2. **[BLOQUEANTE] Configuración de hooks incompleta en settings.json**

#### Problema
- `.claude/settings.json` solo tiene un hook: `ruff check` en `PostToolUse`
- Falta validación automática de `mypy`, `pytest` y estructura de cambios
- No hay mecanismo para detectar/advertir sobre refactors en contexto `new_feature`
- No hay restricción de herramientas por tipo de comando (p.ej. hotfix debería prohibir ediciones amplias)

#### Impacto
- Cambios se aplican sin validación de tipos inmediata
- Riesgo de regresiones no detectadas en tiempo de hooks
- Incapacidad de enforcer políticas per-command (p.ej. new_feature sin refactor)

#### Evidencia
```json
// settings.json línea 1-9: solo ruff, sin mypy ni pytest
"PostToolUse": [
  { "matcher": "Edit|Write", "hooks": [ { "type": "command", "command": "python -m ruff check src tests --quiet 2>&1 | head -15" } ] }
]
```

#### Solución propuesta
- Ampliar `PostToolUse` con hooks para `mypy src` y/o `pytest` (con throttling para no saturar)
- Crear `PreToolUse` hook para validar que el comando activado sea compatible con la operación (p.ej. `new_feature` + refactor → warning)
- Documentar en `.claude/settings.json.example` qué hooks se pueden configurar
- Permitir sobrescritura en `.claude/settings.local.json` por usuario

#### Prioridad
**ALTA** — impacta calidad e iteración rápida durante desarrollo

---

### 3. **[BLOQUEANTE] Falta validación de inputs en comandos**

#### Problema
- Comandos como `/new-feature`, `/tech-debt` piden "contexto a completar" pero no validan que esté completo
- Si el usuario salta secciones, el comando procede igual (degradado)
- No hay mecanismo de checklist interactivo para confirmar inputs

#### Impacto
- Planificación incompleta que lleva a reimplementaciones
- PLA**Ns** inconsistentes (algunos detallan riesgos, otros no)
- Falsos positivos en auditorías (análisis sobre inputs incompletos)

#### Evidencia
```markdown
## Contexto a completar
- Objetivo:
- Módulo(s) o clase(s) afectadas:
...
Si falta alguno, decláralos como supuesto explícito antes de continuar.
```
— La instrucción es declarativa, no hay mecanismo de enforcement

#### Solución propuesta
- Cambiar a sintaxis de checklist interactivo o prompt estructurado
- Implementar validación en `.claude/commands/*.md`: si campos críticos están vacíos, emitir párrafo de clarificación y pedir confirmación
- Considerar usar `vscode_askQuestions` tool (si disponible en Claude Code) para inputs críticos
- Documentar el flujo: "Si alguno de estos campos está vacío, **detente y aclara antes de continuar**"

#### Prioridad
**ALTA** — impacta calidad de planificación

---

### 4. **[BLOQUEANTE] `.claude/settings.local.json` sin documentación**

#### Problema
- Archivo existe pero está vacío o sin comentarios
- No hay guía sobre qué configuraciones son personalizables
- Usuarios no saben si pueden sobrescribir hooks globales, cambiar timeouts, restringir herramientas

#### Impacto
- Confusion sobre customización
- Posibilidad de errores silenciosos (settings.local.json ignorado)

#### Evidencia
Archivo `settings.local.json` existe pero es un JSON válido sin contenido útil

#### Solución propuesta
- Crear `settings.local.json.example` con anotaciones de ejemplo
- Documentar en un README dentro de `.claude/` qué campos son soportados:
  - Sobrescritura de hooks por tipo de comando
  - Whitelist/blacklist de herramientas
  - Timeouts, max output, verbosity
- Incluir sección en CLAUDE.md sobre configuración local

#### Prioridad
**MEDIA** — mejora experiencia de usuario avanzado

---

### 5. **[MEJORA RECOMENDADA] Manejo de edge cases no documentado**

#### Problema
- No hay documentación sobre qué hacer cuando:
  - Un comando se interrumpe a mitad de ejecución
  - Hay conflictos de merge durante IMPLEMENT
  - Pruebas fallan parcialmente después de IMPLEMENT
  - Un archivo está bajo LoC limit (mypy/ruff no lo procesa)
  - Cambios reviertes líneas de otro developer

#### Impacto
- Usuarios tienen que improvisar procedimientos
- Riesgo de inconsistencia o pérdida de contexto

#### Solución propuesta
- Crear documento `.claude/EDGE_CASES.md` con troubleshooting por escenario
- Incluir en cada comando una sección "Qué hacer si falla" o "Rollback"
- Documentar procedimiento estándar: `UNDO → Leo el error → Reviso PLAN → Reconozco contexto`

#### Prioridad
**MEDIA** — mejora robustez

---

### 6. **[MEJORA RECOMENDADA] Inconsistencia en profundidad de comandos**

#### Problema
- `audit-code.md` es muy conciso (25 líneas) vs `new-feature.md` muy detallado (40 líneas)
- Falta consistencia en tono y nivel de ejemplos
- Algunos comandos mencionan "ejemplo" pero sin formato concreto

#### Impacto
- Experiencia desigual para usuarios
- Dificultad para predecir formato de salida

#### Evidencia
```markdown
# audit_code (25 líneas)
# new_feature (40 líneas)
# tech_debt (55 líneas)
```

#### Solución propuesta
- Estandarizar estructura de cada comando:
  1. Descripción breve
  2. Cuándo usar
  3. **Inputs requeridos** (confirmación interactiva)
  4. **Política de cambios** (prohibiciones explícitas)
  5. **Devuelve en este orden** (con ejemplo de formato de salida)
  6. **Ejemplo de entrada** (pequeño caso de referencia)
  7. **Ejemplo de salida esperada** (bloque markdown con formato)
  8. **Rollback si algo falla**

#### Prioridad
**MEDIA** — mejora consistencia y onboarding

---

### 7. **[MEJORA RECOMENDADA] FAQ incompleta**

#### Problema
- `claude_code_usage_complete_example.md:FAQ` (líneas 391–530) no cubre:
  - Qué hacer si dos cambios en el mismo archivo compiten
  - Cómo combinar múltiples slash commands en una sesión (p.ej. `/audit-code` → `/new-feature`)
  - Cómo manejar breaking changes entre versiones en IMPLEMENT
  - Diferencia entre "GO_CONDICIONAL" y cancelar la ejecución
  - Cuándo no usar slash commands (o sea, cuándo escribir directamente)

#### Impacto
- Usuarios no saben cómo resolver conflictos realistas
- Incertidumbre sobre composición de comandos

#### Solución propuesta
- Expandir FAQ con respuestas a casos reales:
  - "¿Dos features tocan el mismo archivo?" → estrategia de merge local
  - "¿Puedo run `/audit-code` y luego `/new-feature` en la misma sesión?" → sí, con context carry-over
  - "¿Qué significa GO_CONDICIONAL exactamente?" → ejemplo concreto
  - "¿Cuándo no usar slash commands?" → guía de decisión
- Referenciar `.claude/EDGE_CASES.md` para troubleshooting

#### Prioridad
**MEDIA** — mejora autoservicio

---

### 8. **[MEJORA RECOMENDADA] Falta de snapshots/fixtures como referencia**

#### Problema
- Comandos no indican cómo validar cambios con pruebas específicas
- No hay mención a snapshots testing (p.ej. `pytest --snapshot`)
- Falta referencia a fixtures compartidas o data test estándar

#### Impacto
- Usuarios no saben qué fixtures usar en tests nuevos
- Posibilidad de tests que no coincidan con estándares del proyecto

#### Solución propuesta
- Crear referencia compartida: `.claude/TESTING_GUIDE.md`
  - Fixtures comunes por módulo (metadata, connection, bulk crud)
  - Patrón de snapshot testing para doc/render
  - Cómo excluir datos no deterministas (timestamps, UUIDs)
- Enlazar desde IMPLEMENT steps de cada comando
- Añadir a settings.json hook de pytest con `--tb=short` para legibilidad

#### Prioridad
**MEDIA** — acelera codificación de pruebas

---

### 9. **[INFORMATIVO] Falta mención a "Modo sin conexión" o restricción de herramientas**

#### Problema
- No está documentado si Claude Code puede trabajar sin acceso a internet
- No hay indicación de qué herramientas pueden/no pueden usarse en contextos offline (p.ej. `vscode_askQuestions` requiere UI)

#### Impacto
- Bajo (la mayoría de usuarios están conectados)
- Pero importante para CI/CD o entornos restringidos

#### Solución propuesta
- Añadir a CLAUDE.md sección "Ejecución offline":
  - Qué comandos funcionan sin red (p.ej. análisis estático, lint)
  - Qué requiere acceso (p.ej. GitHub search, SonarQube)
  - Cómo configurar respaldo si falla acceso remoto
- Documentar restricción de tools por `.claude/settings.json` (si soportado)

#### Prioridad
**BAJA** — caso de uso minoritario pero importante para CI patterns

---

### 10. **[INFORMATIVO] Falta integración con `.github/`instructions y prompts**

#### Problema
- Existe `.github/instructions/` con reglas (architecture, python, tests, render)
- Existe `.github/copilot-instructions.md` con referencia a agentes
- No hay documento que sincronice expectativas entre:
  - `.claude/commands/*.md` (para Claude Code)
  - `.github/prompts/` (para Copilot Chat)
  - `.github/instructions/` (reglas universales)

#### Impacto
- Bajo (ambas configuraciones coexisten)
- Pero potencial desvío si se actualizan por separado

#### Solución propuesta
- Crear `.github/INTEGRATION_MAP.md` que documente:
  - Qué archivos aplican a Claude Code vs Copilot Chat
  - Cuándo prevalece `.claude/` sobre `.github/instructions/`
  - Checklist para sincronización cuando se actualiza un flujo
- Referenciar desde CLAUDE.md y `.github/copilot-instructions.md`

#### Prioridad
**BAJA** — prevención de desvío futuro

---

## Plan de implementación

### Fase 1: Bloqueantes (Semana 1-2)
- [ ] **Tarea 1.1**: Crear matriz de equivalencias Claude Code ↔ Copilot Chat
  - Archivo: `docs/v0.6.7/CLAUDE_COPILOT_MAPPING.md`
  - Propietario: Arquitectura
  - Esfuerzo: 2h

- [ ] **Tarea 1.2**: Ampliar `settings.json` con hooks mypy + pytest
  - Archivo: `.claude/settings.json`
  - Propietario: DevOps / Configuración
  - Esfuerzo: 1h
  - Incluir: `settings.json.example`

- [ ] **Tarea 1.3**: Implementar validación interactiva de inputs en comandos
  - Archivos: `.claude/commands/*.md` (8 ficheros)
  - Propietario: Documentation
  - Esfuerzo: 4h
  - Incluir: checklist + confirmación explícita

- [ ] **Tarea 1.4**: Documentar `.claude/settings.local.json`
  - Archivo: `.claude/settings.local.json.example` + README en `.claude/`
  - Propietario: Documentation
  - Esfuerzo: 1h

### Fase 2: Mejoras recomendadas (Semana 2-3)
- [ ] **Tarea 2.1**: Crear `.claude/EDGE_CASES.md` con troubleshooting
  - Esfuerzo: 2h
  - Cubrir: interrupciones, merge conflicts, test failures, rollback

- [ ] **Tarea 2.2**: Estandarizar estructura de comandos con ejemplos de salida
  - Archivos: `.claude/commands/*.md` + `.claude/COMMAND_TEMPLATE.md`
  - Esfuerzo: 3h
  - Incluir: ejemplo de entrada + salida esperada en cada comando

- [ ] **Tarea 2.3**: Expandir FAQ en `claude_code_usage_complete_example.md`
  - Esfuerzo: 2h
  - Nuevas entradas: merge, sesiones largas, breaking changes, GO_CONDICIONAL

- [ ] **Tarea 2.4**: Crear `.claude/TESTING_GUIDE.md`
  - Esfuerzo: 2h
  - Cubrir: fixtures, snapshots, datos deterministas, pytest patterns

### Fase 3: Informativos (Semana 3+)
- [ ] **Tarea 3.1**: Añadir sección "Ejecución offline" en CLAUDE.md
  - Esfuerzo: 1h

- [ ] **Tarea 3.2**: Crear `.github/INTEGRATION_MAP.md`
  - Esfuerzo: 1.5h

---

## Archivos a crear / modificar

### Creación (nuevos)
1. `docs/v0.6.7/CLAUDE_COPILOT_MAPPING.md` — matriz de equivalencias
2. `.claude/settings.json.example` — configuración de ejemplo
3. `.claude/EDGE_CASES.md` — troubleshooting
4. `.claude/COMMAND_TEMPLATE.md` — plantilla estándar para comandos
5. `.claude/TESTING_GUIDE.md` — guía de testing
6. `.claude/README.md` — descripción de archivos en `.claude/`
7. `.github/INTEGRATION_MAP.md` — integración con Copilot/GitHub

### Modificación
1. `.claude/settings.json` — ampliar hooks
2. `.claude/settings.local.json.example` — documentar campos customizables
3. `.claude/commands/*.md` (8 ficheros) — añadir validación interactiva + ejemplos
4. `CLAUDE.md` — referenciar nueva documentación + offline section
5. `docs/examples/claude_code_usage_complete_example.md` — expandir FAQ + añadir ejemplos Copilot Chat

---

## Criterios de aceptación

### Global
- [ ] Todos los hallazgos bloqueantes abordados
- [ ] Documentación coherente entre Claude Code y Copilot Chat
- [ ] Ejemplos reales de entrada/salida en cada comando
- [ ] FAQ ampliada con casos de uso reales
- [ ] Métrica: cero preguntas recurrentes sobre "cómo activar PLAN en Copilot Chat"

### Por hallazgo
1. **Mapeo Claude Code ↔ Copilot Chat**
   - Matriz de equivalencias documentada
   - Cada comando tiene sección "Equivalencia Copilot Chat"

2. **Hooks mejorados**
   - `ruff check` + `mypy src` + `pytest --co` (recolecta sin ejecutar)
   - Tiempo de ejecución total < 10s

3. **Validación de inputs**
   - Cada comando tiene checklist de confirmación
   - Ejemplo de "qué pasa si falta un input"

4. **Edge cases**
   - Documento 30+ líneas cubriendo 5+ escenarios
   - Cada escenario con solución probada

---

## Referencias

- **CLAUDE.md**: Política base transversal, debe actualizarse para referenciar nuevos doc
- **`.claude/commands/`**: 8 archivos, estandarización pendiente
- **`.github/copilot-instructions.md`**: Contexto de agentes para Copilot
- **`docs/examples/claude_code_usage_complete_example.md`**: Documentación de ejemplo, FAQ incompleta
- **`.github/instructions/`**: Reglas específicas por área (architecture, python, tests, render)

---

## Próximos pasos

1. **Validar plan con stakeholders**: ¿Prioridad correcta? ¿Scope completo?
2. **Asignar ownership**: ¿Quién lidera cada fase?
3. **Ejecutar Fase 1 en paralelo**:
   - Mapeo Claude/Copilot (docs)
   - Hooks settings.json (config)
   - Validación inputs (docs + commands)
   - settings.local.json (docs)
4. **Medir impacto** post-implementación: ¿Menores preguntas de soporte? ¿Mejor adopción de PLAN/AUDIT_PLAN?

---

## Notas

- Este plan **no incluye cambios funcionales** a CLAUDE.md policy ni archivos de `.github/instructions/`
- Alcance es **puramente operativo y documental**
- Cambios son **no-breaking** para usuarios existentes
- Se recomienda ejecutar Fase 1 antes de cualquier nueva feature que use `.claude/commands/`
