# Ejemplo completo de uso de Claude Code

## Resumen

Este documento muestra, con ejemplos completos y realistas, cómo se trabaja en este repositorio con **Claude Code** (CLI y extensión VS Code de Anthropic).

Cubre:

- cómo se carga el contexto del repositorio automáticamente
- cómo funcionan los slash commands de `.claude/commands/`
- flujo de trabajo estructurado (PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION)
- políticas por tipo de tarea
- ejemplos completos por caso de uso

Para la configuración equivalente de Copilot Chat, consulta [github_usage_complete_example.md](github_usage_complete_example.md).

---

## Configuración de Claude Code para este repositorio

### Archivos que Claude Code carga automáticamente

| Archivo | Cuándo actúa |
|---|---|
| [../../CLAUDE.md](../../CLAUDE.md) | Siempre, en cada conversación |
| [../../.claude/commands/*.md](../../.claude/commands/) | Al invocar el slash command correspondiente |
| [../../.claude/settings.json](../../.claude/settings.json) | Al iniciar sesión (hooks y permisos) |

### Jerarquía de aplicación

```
CLAUDE.md                    ← política transversal, siempre activa
  └── .claude/commands/      ← flujos específicos, activados por slash command
        new_feature.md
        hotfix.md
        refactor.md
        audit_code.md
        security_review.md
        version_closure.md
```

La política base de [../../CLAUDE.md](../../CLAUDE.md) fija el marco de trabajo para toda interacción. Los slash commands añaden un flujo de salida estructurado para tareas concretas.

### Relación con la configuración de Copilot

Los artefactos de `.github/` (copilot-instructions, agents, prompts, instructions) se conservan y pueden usarse en paralelo con Copilot Chat. Claude Code los puede leer como contexto adicional pero no los ejecuta nativamente. El punto de entrada para Claude Code es exclusivamente `CLAUDE.md`.

---

## Slash commands disponibles

Escribe el comando en el chat de Claude Code para activar el flujo estructurado correspondiente.

| Comando | Archivo | Úsalo cuando |
|---|---|---|
| `/new-feature` | [../../.claude/commands/new-feature.md](../../.claude/commands/new-feature.md) | Añades comportamiento nuevo |
| `/hotfix` | [../../.claude/commands/hotfix.md](../../.claude/commands/hotfix.md) | Corriges un bug acotado |
| `/refactor` | [../../.claude/commands/refactor.md](../../.claude/commands/refactor.md) | Mejoras estructura sin cambiar comportamiento |
| `/audit-code` | [../../.claude/commands/audit-code.md](../../.claude/commands/audit-code.md) | Quieres revisión técnica con veredicto |
| `/security-review` | [../../.claude/commands/security-review.md](../../.claude/commands/security-review.md) | Quieres auditoría de seguridad independiente |
| `/tech-debt` | [../../.claude/commands/tech-debt.md](../../.claude/commands/tech-debt.md) | Quieres inventariar deuda técnica por módulo |
| `/maturity-assessment` | [../../.claude/commands/maturity-assessment.md](../../.claude/commands/maturity-assessment.md) | Quieres evaluar readiness del repositorio |
| `/version-closure` | [../../.claude/commands/version-closure.md](../../.claude/commands/version-closure.md) | Cierras una versión o bloque de cambios |

---

## Flujo de trabajo

### Secuencia obligatoria para cambios no triviales

```
PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION
```

Claude Code no debe empezar por código si el objetivo no está definido.

### Políticas por tipo de tarea

| Tarea | Restricción |
|---|---|
| `new_feature` | Prohibido refactorizar |
| `hotfix` | Solo fix mínimo. Prohibido refactorizar y optimizar |
| `refactor` | Sin cambios funcionales. API pública estable salvo justificación explícita |
| `security_review` | Hallazgos verificables, ordenados por severidad, con remediación accionable |

---

## Uso

### Caso 1. CLAUDE.md siempre activo

En cualquier conversación, la política de [../../CLAUDE.md](../../CLAUDE.md) está activa sin necesidad de mencionarla. Fija:

- el rol esperado (senior Python, multibase, sync/async)
- la arquitectura de 3 niveles y la regla de imports
- las reglas críticas multibase y SOLID
- la obligación de emitir PLAN y AUDIT_PLAN antes del código en cambios no triviales

Ejemplo de petición sin slash command:

```text
Necesito añadir documentación Markdown para vistas y relaciones FK en el renderer.
```

Efecto esperado:

- Claude identifica que es una feature y aplica la política `new_feature`
- emite PLAN y AUDIT_PLAN antes de proponer código
- no mezcla la feature con un refactor no solicitado

### Caso 2. Slash command para flujo estructurado

Cuando quieres imponer la secuencia completa de salida (PLAN → VERSION), usa el slash command correspondiente. El comando carga el fichero `.claude/commands/<nombre>.md` y Claude lo toma como contrato de salida para esa sesión.

Diferencia con Copilot:

| Copilot Chat | Claude Code |
|---|---|
| `@#sym:new_feature` (símbolo de prompt) | `/new-feature` (slash command) |
| Agentes seleccionados explícitamente en el chat | Claude gestiona internamente la especialización |
| `.github/prompts/*.prompt.md` | `.claude/commands/*.md` |

### Caso 3. Leer contexto adicional de `.ai/` y `.github/`

Claude Code puede leer cualquier archivo del repositorio. Para tareas que requieran contexto de sesiones previas, arquitectura detallada o estándares, puedes indicarlo en el mensaje:

```text
Lee .ai/architecture.md antes de proponer cambios en connection/.
```

o

```text
Consulta .github/copilot-instructions.md para las reglas SOLID antes de continuar.
```

---

## Ejemplos completos

### Ejemplo 1. `/new-feature`

Invocación:

```text
/new-feature

Objetivo: añadir exportación Markdown de vistas con Mermaid opcional.
Módulo(s) o clase(s) afectadas: src/util_bbdd/doc/render_markdown.py, tests/test_render_markdown.py
API pública esperada: parámetro opcional para habilitar diagramas Mermaid
Contrato de entrada: modelo de metadatos ya introspectado
Contrato de salida: Markdown portable y determinista
Reglas de negocio: no inventar metadatos, Mermaid solo con datos reales
Restricciones: sin dependencias nuevas
Motores o formatos afectados: Markdown
Archivos existentes relevantes: sí
```

Qué obliga este comando:

- presentar `PLAN` con rutas afectadas, componentes, tipos y riesgos
- presentar `AUDIT_PLAN` con riesgos funcionales, técnicos y de seguridad
- implementar por capas (Level 1 → 2 → 3)
- cerrar con `AUDIT_CODE` y `VERSION`
- no convertir la tarea en refactor general

### Ejemplo 2. `/hotfix`

Invocación:

```text
/hotfix

Bug: el renderer HTML pierde iconos offline cuando se exporta fuera del workspace.
Rutas afectadas: src/util_bbdd/doc/html_generator.py, tests/test_html_assets.py
Dato faltante o supuesto: se asume que la salida debe ser portable sin acceso a red.
```

Qué obliga este comando:

- arreglar solo la causa raíz
- no refactorizar ni optimizar fuera del bug
- incluir test que reproduzca el fallo si es viable
- emitir `PLAN`, `AUDIT_PLAN`, `IMPLEMENT`, `AUDIT_CODE` y `VERSION`

### Ejemplo 3. `/refactor`

Invocación:

```text
/refactor

Objetivo: separar construcción de payload de leyenda y render HTML sin cambiar comportamiento.
Módulos: src/util_bbdd/doc/html_generator.py
Contrato público: sin cambios
Restricciones: preservar snapshots y orden actual de salida
```

Qué obliga este comando:

- no introducir cambios funcionales
- priorizar responsabilidad única y legibilidad
- confirmar explícitamente antes de romper cualquier contrato público
- validar con `mypy src`, `ruff check src tests` y tests antes de cerrar

### Ejemplo 4. `/security-review`

Invocación:

```text
/security-review

Revisa la generación documental para detectar fuga de secretos, exposición de SQL sensible e inyección por identificadores.
Áreas: src/util_bbdd/doc, src/util_bbdd/analysis
```

Qué obliga este comando:

- ordenar hallazgos por severidad (crítico / alto / medio / bajo)
- separar hallazgos confirmados de hipótesis
- dar remediación accionable por hallazgo
- etiquetar supuestos y datos faltantes
- no mezclarlo con una feature

### Ejemplo 5. `/audit-code`

Invocación:

```text
/audit-code

Revisa src/util_bbdd/doc/html_generator.py y src/util_bbdd/doc/excel_generator.py.
Quiero bugs, edge cases, compatibilidad y tests faltantes.
```

Qué obliga este comando:

- emitir veredicto final (`APROBADO / APROBADO CON CONDICIONES / RECHAZADO`)
- citar evidencias concretas con `archivo:línea`
- diferenciar hallazgos confirmados de hipótesis

### Ejemplo 6. `/tech-debt`

Invocación:

```text
/tech-debt

Módulo objetivo: src/util_bbdd/metadata/
Deuda conocida o síntomas: hay `Any` sueltos en fetcher.py y duplicación de lógica entre SyncMetadataProvider y AsyncMetadataProvider.
Restricciones de scope: solo análisis (PLAN + AUDIT_CODE), sin IMPLEMENT por ahora.
Política de compatibilidad: no se autoriza romper contratos públicos.
```

Qué obliga este comando:

- confirmar los inputs antes de analizar; si falta alguno, declararlo como supuesto explícito
- clasificar cada ítem de deuda como `quick_win`, `fase_media` o `deuda_estructural`
- proponer quick wins con estrategia de prueba mínima
- emitir veredicto: `LIMPIO | DEUDA_MENOR | DEUDA_SIGNIFICATIVA | CRÍTICO`
- no mezclar deuda con nuevas features en el mismo PLAN

### Ejemplo 7. `/maturity-assessment`

Invocación:

```text
/maturity-assessment

Objetivo: evaluar readiness del repositorio para una publicación estable de la capa documental (doc/, analysis/).
```

Qué obliga este comando:

- revisar estructura, APIs públicas, tipado, seguridad, tests y documentación
- separar hallazgos en **bloqueantes** / **mejoras recomendadas** / **informativos**
- emitir veredicto: `PRODUCTION_READY | NEAR_READY | BLOCKED`

### Ejemplo 8. `/version-closure`

Invocación:

```text
/version-closure
```

Uso típico:

- después de alinear metadatos, CI y documentación
- al finalizar una release o un bloque coherente de cambios

Salida estructurada esperada (con secciones):

- **Commit message** — formato `release: v0.6.7 - <descripción>`
- **Changelog** — cambios por módulo clasificados por tipo (feat/fix/refactor/docs/chore)
- **Impacto en API pública** — cambios de firma, deprecaciones
- **Migraciones** — acciones requeridas por el consumidor
- **Compatibilidad** — motores afectados, rango Python 3.12–3.14
- **Rollback** — pasos y riesgos
- **Checklist final** — ruff + mypy + pytest + build + pyproject.toml + CHANGELOG.md
- **Pruebas ejecutadas o sugeridas**

---

## Comportamiento del hook de lint

[../../.claude/settings.json](../../.claude/settings.json) tiene configurado un hook `PostToolUse` que ejecuta automáticamente `ruff check src tests --quiet` tras cada edición de fichero (herramientas `Edit` o `Write`).

Efecto práctico:

- si Claude edita un `.py` y introduce un error de lint, el hook lo reporta inmediatamente en la misma sesión
- Claude Code puede leer el resultado del hook y corregir antes de continuar
- la salida está limitada a 15 líneas para no saturar el contexto

Para añadir más automatizaciones (p.ej. `mypy` al guardar, aviso antes de comandos destructivos), edita [../../.claude/settings.json](../../.claude/settings.json).

---

## Comandos de desarrollo

Comandos habituales en el terminal de Claude Code:

```bash
python -m ruff check src tests       # lint
python -m ruff format src tests      # format
python -m mypy src                   # type-check
python -m pytest                     # todos los tests
python -m pytest tests/path/test_x.py::TestClass::test_name  # test individual
python -m build                      # build del paquete
```

---

## FAQ

### Flujo y Procesos

#### ¿CLAUDE.md reemplaza a `.github/copilot-instructions.md`?

No los reemplaza. Son independientes: `CLAUDE.md` es el punto de entrada para Claude Code y `copilot-instructions.md` lo es para Copilot Chat. Ambos pueden coexistir. `CLAUDE.md` referencia a los archivos de `.github/` para contexto extendido.

#### ¿Cuándo uso un slash command y cuándo escribo directamente?

Escribe directamente para preguntas, exploraciones o cambios pequeños donde no necesitas imponer el ciclo completo PLAN → VERSION. Usa el slash command cuando quieras garantizar la secuencia estructurada de salida **o** la tarea sea relevante (feature, hotfix, refactor).

**Heurística:** Si la pregunta o cambio se puede responder en < 5 minutos sin riegos, probablemente no necesitas slash command. Si afecta arquitectura, contrato público o requiere auditoría, usa el comando.

#### ¿Qué archivo debo leer primero si soy nuevo en el repositorio?

Empieza por [../../CLAUDE.md](../../CLAUDE.md) y luego por [../../.ai/architecture.md](../../.ai/architecture.md). Si usas Copilot Chat, añade [../../.github/README.md](../../.github/README.md).

#### ¿Cómo indico que Claude Code lea el contexto de sesiones previas de `.ai/`?

Menciónalo en el mensaje: `"Lee .ai/sessions/INDEX.md para contexto de decisiones previas"`. Claude Code puede leer cualquier archivo del repositorio cuando se le indica o cuando lo considera necesario para la tarea.

---

### Slash Commands

#### ¿Los slash commands de `.claude/commands/` equivalen a los prompts de `.github/prompts/`?

Sí, son el equivalente funcional para Claude Code. El contenido está adaptado (la invocación es distinta), pero el contrato de salida es el mismo.

#### ¿Puedo usar `/new-feature` para un bug?

No es lo recomendable. Usa `/hotfix`, que prohíbe explícitamente refactorizar y optimizar fuera del fix.

#### ¿Qué hago si Claude Code propone un refactor que no pedí?

La política `new_feature` de `CLAUDE.md` lo prohíbe explícitamente. Recuérdaselo indicando que solo debe implementar el alcance aprobado en el PLAN, sin introducir cambios estructurales.

#### ¿Cuándo uso `/tech-debt` y cuándo uso `/audit-code`?

Usa `/audit-code` cuando quieras una revisión técnica general de un módulo o un cambio reciente (bugs, edge cases, contratos). Usa `/tech-debt` cuando el objetivo sea inventariar deuda acumulada con clasificación de prioridad (`quick_win / fase_media / deuda_estructural`) y un plan de abordaje por fases.

#### ¿Cuál es la diferencia entre `/maturity-assessment` y `/audit-code`?

`/audit-code` audita código concreto (módulo, archivo, PR) y emite un veredicto técnico puntual. `/maturity-assessment` evalúa el repositorio completo en múltiples dimensiones (estructura, APIs, tipado, seguridad, tests, documentación) y emite un veredicto de readiness para publicación o mantenimiento a largo plazo.

---

### Cambios y Merge

#### ¿Qué pasa si dos features tocan el mismo archivo?

Si dos ramas (`feature/oracle` y `feature/snowflake`) modifican el mismo comando o archivo en `.claude/commands/`:

1. **Merge local con resolución**: Git indicará conflicto. Abre el archivo y mantén cambios válidos de ambas ramas si son complementarios (p.ej. rama A añade sección "Cuándo usar", rama B añade "Ejemplo").

2. **Contexto carry-over**: Después de resolver conflict, Claude Code conserva el contexto de la sesión anterior. Si lo necesitas, abre un nuevo chat e indica: "Contexto: acabo de resolver merge conflict en [archivo]". Claude leerá el archivo actualizado.

3. **Puedo ejecutar `/audit-code` después para validar coherencia**: Post-merge, es recomendable correr `/audit-code` sobre el archivo mergeado para confirmar que mantiene estructura (ver COMMAND_TEMPLATE.md).

4. **Evita ediciones simultáneas**: Usa feature branches aisladas por módulo (no por comando) para reducir fricciones.

#### ¿Puedo ejecutar `/audit-code` y luego `/new-feature` en la misma sesión?

Sí, es seguro. El contexto de la sesión anterior (resultados de AUDIT_CODE) se conserva. Puedes usarlo como input:

```text
/audit-code
[Claude emite AUDIT_CODE con hallazgos]

Basándome en los hallazgos, ejecutar `/new-feature` para refactorizar:
Objetivo: aplicar recomendaciones de AUDIT_CODE sin cambiar contratos públicos.
```

Sin embargo, **ten cuidado con LoC**: si ambos comandos generan outputs grandes (> 10K líneas), el segundo comando puede sufrir token budget exhaustion. Ver `.claude/EDGE_CASES.md` (Escenario 1).

#### ¿Cómo hago rollback manual si mis cambios rompen?

Ejercicio completo:

1. **Identifica el commit que rompió**:
   ```bash
   git log --oneline | head -20
   git diff HEAD~1..HEAD src/archivo.py  # Quién cambió qué
   ```

2. **Verifica el estado actual**:
   ```bash
   python -m pytest tests/ --tb=short 2>&1 | tail -50
   ```

3. **Opción A: Revert limpio**:
   ```bash
   git revert <commit-hash>
   git commit  # Crea nuevo commit de revert, recuerda lo que pasó
   ```

4. **Opción B: Cherry-pick manual desde rama correcta**:
   ```bash
   git checkout main
   git checkout -b rollback-<ticket-id>
   git cherry-pick <commits-válidos>  # Re-aplica lo bueno
   ```

5. **Validar siempre**:
   ```bash
   python -m ruff format src tests
   python -m mypy src
   python -m pytest tests/ --cov=src
   ```

6. **Documentar**: Abre issue o comentario en PR explicando por qué el rollback fue necesario.

---

### Troubleshooting

#### ¿Qué significa GO / NO_GO / GO_CONDICIONAL en `/new-feature`?

Es el veredicto al final del AUDIT_PLAN, antes de pasar a IMPLEMENT:

- **GO**: el alcance y los riesgos son asumibles. Se puede implementar directamente.
- **NO_GO**: hay riesgos bloqueantes (p.ej. "breaking change sin deprecation", "cobertura de tests inadecuada") que deben resolverse antes de implementar.
- **GO_CONDICIONAL**: se puede implementar con las condiciones explícitas indicadas.

**Ejemplo GO_CONDICIONAL**:
```
Veredicto: GO_CONDICIONAL
Condiciones:
- [ ] Validación: Se debe incluir test de contrato sync/async (Manager.sync() == Manager.async())
- [ ] Security: Credenciales no deben ser loguadas ni expuestas en Markdown
- [ ] Cobertura: Mínimo 80% de cobertura en líneas nuevas
```

Claude Code **no debe** pasar a IMPLEMENT si el veredicto es NO_GO. Si es GO_CONDICIONAL, implementa pero verifica todas las condiciones antes de finalizar en VERSION.

#### ¿Qué pasa si falla mypy/pytest después de IMPLEMENT?

Workflow minimalista:

1. **Aísla el error**:
   ```bash
   python -m pytest tests/path/test_specific.py::TestClass::test_name -vv --tb=short
   python -m mypy src/util_bbdd/module/specific_file.py --show-error-codes
   ```

2. **Lee el cambio que rompió**:
   - Contrasta con qué esperaba el test
   - ¿API pública cambió? ¿Tipo retornado cambió?
   - ¿Mock fixture desactualizado?

3. **Elige solución**:
   - **A) Corregir test** (si código es correcto y test es obsoleto)
   - **B) Corregir código** (si código tiene bug)
   - **C) Deprecate + migration** (si es breaking change necesario)

4. **Validar post-fix**:
   ```bash
   python -m pytest tests/ --cov=src --cov-report=term-missing
   # Target: No peor cobertura que antes
   ```

5. **No ignores errores**: Si un test pasa artificialmente (p.ej. skipped), documéntalo como deuda técnica (ver `/tech-debt`).

#### ¿Dónde está la guía de troubleshooting más extendida?

Ver [`.claude/EDGE_CASES.md`](./.claude/EDGE_CASES.md) para 5+ escenarios concretos (comando interrumpido, merge conflict, test failures, LoC limit, regresión silenciosa) con pasos diagnósticos y soluciones paso a paso.

---

### Configuración

#### ¿Dónde configuro hooks o automatizaciones para Claude Code?

En [../../.claude/settings.json](../../.claude/settings.json). Actualmente tiene configurado un hook `PostToolUse` que ejecuta `ruff check src tests --quiet` automáticamente tras cada edición de fichero.

Para añadir más hooks (p.ej. `mypy`, `pytest --collect-only`):
1. Edita `.claude/settings.json` raíz
2. Copia la entrada existente bajo `PostToolUse`
3. Cambia `"command"` a tu nuevo comando (p.ej. `"mypy src"`)
4. Marca `"optional": true` si no quieres que bloquee

Para usar configuration local **sin commitear**:
1. Crea `.claude/settings.local.json` en tu máquina (ignored en `.gitignore`)
2. Sobrescribe solo los valores que quieras cambiar
3. Valores locales precedencia sobre `.claude/settings.json`

Ejemplo `settings.local.json`:
```json
{
  "PostToolUse": [
    {
      "description": "ruff check",
      "command": "python -m ruff check src tests --quiet",
      "optional": false
    }
  ]
}
```

#### ¿Cómo desabilito hooks si están ralentizando sesión?

Temporalmente:
```json
// .claude/settings.local.json
{
  "PostToolUse": []  // vacío = sin hooks
}
```

Permanentemente para un hook específico:
- Edita `.claude/settings.json`
- Marca `"optional": true` en los hooks que quieras permitir deshabilitar
- Tu `.claude/settings.local.json` puede vaciar el array PostToolUse
