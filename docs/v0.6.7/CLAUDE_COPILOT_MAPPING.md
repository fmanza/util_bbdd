# Mapeo: Claude Code vs Copilot Chat

**Versión**: v0.6.7
**Propósito**: Equivalencias de slash commands entre Claude Code y Copilot Chat en VS Code
**Audiencia**: Usuarios de ambas plataformas

---

## Resumen

Este documento mapea los slash commands de **Claude Code** (Anthropic, CLI/extensión) a equivalentes en **Copilot Chat** (GitHub, VS Code integrado). Ambas plataformas soportan el flujo `PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION`, pero con activación diferente.

---

## Matriz de Equivalencias

| Función | Claude Code | Copilot Chat |
|---------|-----------|---|
| **Nueva funcionalidad** | `/new-feature` | `@prompt /new-feature`(1) o escritura manual(2) |
| **Corrección de bug** | `/hotfix` | `@prompt /hotfix`(1) o escritura manual(2) |
| **Refactor** | `/refactor` | `@prompt /refactor`(1) o escritura manual(2) |
| **Auditoría técnica** | `/audit-code` | `@prompt /audit-code`(1) o escritura manual(2) |
| **Seguridad** | `/security-review` | `@prompt /security-review`(1) o escritura manual(2) |
| **Deuda técnica** | `/tech-debt` | `@prompt /tech-debt`(1) o escritura manual(2) |
| **Evaluación** | `/maturity-assessment` | `@prompt /maturity-assessment`(1) o escritura manual(2) |
| **Cierre** | `/version-closure` | `@prompt /version-closure`(1) o escritura manual(2) |

**(1)** Si `.github/prompts/*.prompt.md` existe (Fase 2)
**(2)** Copilot Chat (Fase 1): escribir el contexto manualmente

---

## Opción 1: Copilot Chat - Escritura Manual (Disponible hoy)

Para activar el flujo PLAN→AUDIT_PLAN en **Copilot Chat sin prompts personalizados**:

### Ejemplo: Nueva Funcionalidad

Escribe esto en Copilot Chat:

```
Voy a implementar una nueva funcionalidad en util_bbdd.

Sigue el flujo PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION.

Política: prohibido refactorizar fuera del alcance.

Contexto:
- Objetivo: [tu descripción]
- Módulo(s) o clase(s): [p.ej. src/util_bbdd/doc/render_markdown.py]
- API pública esperada: [p.ej. parámetro opcional enable_mermaid]
- Contrato de entrada: [p.ej. modelo de metadatos ya introspectado]
- Contrato de salida: [p.ej. Markdown portable determinista]
- Reglas de negocio: [p.ej. no inventar metadatos, solo datos reales]
- Restricciones: [p.ej. sin dependencias nuevas]
- Motores afectados: [p.ej. Markdown]
- ¿Hay archivos relevantes existentes?: sí/no

Primero: emite PLAN con rutas afectadas, componentes implicados y riesgos.
Luego: emite AUDIT_PLAN con riesgos funcionales/técnicos/seguridad y veredicto (GO/NO_GO/GO_CONDICIONAL).
Después: IMPLEMENT por capas (Level 1 → 2 → 3).
Finalmente: AUDIT_CODE con hallazgos concretos y VERSION con commit message + changelog.
```

### Ejemplo: Hotfix

Escribe esto en Copilot Chat:

```
Hay un bug crítico en util_bbdd que necesita fix acotado.

Política: solo fix mínimo. Prohibido refactorizar y optimizar.

Sigue PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION.

Contexto:
- Bug: [descripción del bug]
- Archivos afectados: [ruta afectada]
- Síntomas: [cómo se manifiesta]
- Dato faltante o supuesto: [si hay incertidumbre]

Primero: PLAN con diagnóstico de causa raíz.
Luego: AUDIT_PLAN con riesgos de regresión.
Después: IMPLEMENT fix minimalista + test que reproduzca el fallo.
Finalmente: AUDIT_CODE + VERSION.
```

### Ejemplo: Auditoría técnica

Escribe esto en Copilot Chat:

```
Revisa esta módulo/archivo usando el protocolo de auditoría:

Módulos a revisar: [ruta]

Sigue este orden:
1. PLAN: scope y archivos analizados
2. AUDIT_PLAN: riesgos priorizados
3. AUDIT_CODE: hallazgos por categoría (bugs, edge cases, security, typing, tech debt)
   - Bugs potenciales (archivo:línea)
   - Edge cases no cubiertos
   - Performance issues
   - Seguridad (SQL injection, credenciales, inputs)
   - Tipado (Any sueltos, missing annotations)
   - Deuda técnica

Veredicto final: APROBADO / APROBADO CON CONDICIONES / RECHAZADO
```

**Ventaja**: Funciona **hoy, sin cambios a `.github/`**
**Desventaja**: Usuario debe recordar estructura PLAN/AUDIT_PLAN; no hay activación por atajo

---

## Opción 2: Copilot Chat - Prompts (Fase 2)

**Disponible después de crear `.github/prompts/*.prompt.md`**

```
@prompt /new-feature

Objetivo: ...
Módulo(s): ...
```

En VS Code, Copilot Chat injeta contenido de `.github/prompts/new-feature.prompt.md` automáticamente.

**Beneficio**: Flujo similar a Claude Code slash commands
**Contingencia**: Requiere que GitHub permita leer prompts desde archivos (validar con versión actual de Copilot Chat)

---

## Comparativa: Claude Code vs Copilot Chat

| Aspecto | Claude Code | Copilot Chat |
|--------|-----------|---|
| **Activación** | `/new-feature` | Manual o `@prompt` |
| **Configuración** | `.claude/settings.json` | `copilot-instructions.md` |
| **Hooks automáticos** | Sí (ruff, mypy, pytest) | No (manual validación) |
| **Contexto base** | `CLAUDE.md` siempre | `copilot-instructions.md` + `.github/instructions/` |
| **Agentes** | Internos a Claude | Seleccionables (`@#symbol:agentName`) |
| **Curva de aprendizaje** | Media (slash commands) | Media (necesita recordar estructura) |

---

## Recomendación por Perfil de Usuario

### Eres usuario de **Claude Code**
👉 Usa slash commands directo:
```
/new-feature
[completa contexto]
```

Consulta: [CLAUDE.md](../../CLAUDE.md) y [.claude/commands/](../../.claude/commands/)

### Eres usuario de **Copilot Chat** (hoy, Fase 1)
👉 Usa escritura manual (Opción 1):
```
Voy a implementar nueva funcionalidad: ...
Sigue PLAN → AUDIT_PLAN → IMPLEMENT
Contexto: [completa según template]
```

Consulta: [Sección "Opción 1" arriba](#opción-1-copilot-chat---escritura-manual-disponible-hoy)

### Eres usuario de **Copilot Chat** (futuro, Fase 2)
👉 Usa prompts si están disponibles:
```
@prompt /new-feature
[contexto]
```

O sigue leyendo este documento cuando `.github/prompts/` sea creado.

---

## Flujo PLAN→AUDIT_PLAN en Ambas Plataformas

Independientemente de la plataforma, el flujo esperado es idéntico:

### Paso 1: PLAN (Planificación)
```
- objetivo (1 línea)
- rutas afectadas (src/*, tests/*)
- componentes implicados (clases, funciones)
- tipos necesarios (dataclasses, Protocols)
- riesgos (funcionales, técnicos, seguridad)
```

### Paso 2: AUDIT_PLAN (Auditoría preliminar)
```
- riesgos funcionales (qué puede salir mal)
- riesgos técnicos (SOLID, performance, tipado, LSP/ISP)
- riesgos de seguridad (inputs, SQL, credenciales)
- simplificaciones posibles
- VEREDICTO: GO / NO_GO / GO_CONDICIONAL
```

### Paso 3: IMPLEMENT (Implementación)
```
- cambios por archivo
- código
- explicación breve
```

### Paso 4: AUDIT_CODE (Auditoría de código)
```
- bugs potenciales (archivo:línea)
- edge cases
- performance
- seguridad
- tipado
- deuda técnica
```

### Paso 5: VERSION (Cierre)
```
- commit message (Conventional Commits)
- changelog
- impacto en API pública
- rollback
- pruebas sugeridas
```

---

## Sincronización de Salidas

Ambas plataformas deben respetar estos **contratos de salida**:

| Artefacto | Formato | Validación |
|-----------|---------|-----------|
| **PLAN** | Markdown estructurado | Debe tener 5+ secciones (objetivo, rutas, componentes, etc.) |
| **AUDIT_PLAN** | Markdown con veredicto | Veredicto explícito: GO / NO_GO / GO_CONDICIONAL |
| **IMPLEMENT** | Bloques de código + explicación | Código debe ser válido (ruff + mypy) |
| **AUDIT_CODE** | Hallazgos con `archivo:línea` | Evidencia concreta, no genérica |
| **VERSION** | Conventional Commits + CHANGELOG | Commit message + impacto listado |

---

## Ejemplos de Contexto Esperado

### Ejemplo 1: new_feature (reducido)
```
- Objetivo: Exportar Markdown con Mermaid optional
- Módulo(s): src/util_bbdd/doc/render_markdown.py
- API: parámetro enable_mermaid (bool, default False)
- Contrato entrada: Schema ya introspectado
- Contrato salida: Markdown portable
- Reglas: no inventar metadatos, solo datos reales
- Restricciones: sin nuevas dependencias
- Motores: Markdown
- Archivos relevantes: sí
```

### Ejemplo 2: hotfix (reducido)
```
- Bug: renderer HTML pierde iconos offline cuando se exporta fuera workspace
- Archivos: src/util_bbdd/doc/html_generator.py
- Síntomas: iconos desaparecen en PDF/standalone, pero OK en web
- Supuesto: archivos de assets debe

n essere embebidos, no referenciados
```

### Ejemplo 3: audit-code (reducido)
```
- Módulos: src/util_bbdd/metadata/
- Revisar: bugs, edge cases, contratos sync/async, tipado, tests
```

---

## FAQ de Mapeo

### ¿Puedo usar el mismo contexto en ambas plataformas?
Sí. El contenido de PLAN/AUDIT_PLAN/IMPLEMENT es agnóstico de plataforma. Solo varía la **activación** (slash command vs escritura manual).

### ¿Qué pasa si Copilot Chat no soporta @prompt en mi versión?
Usa la Opción 1 (escritura manual). Los prompts en `.github/prompts/` son una mejora futura, no bloqueante.

### ¿Claude Code y Copilot Chat emitirán SEMPRE la misma salida?
No. Ambas son LLMs con parámetros de generación diferentes. El **contrato** (estructura PLAN/AUDIT_PLAN) es fijo, pero el contenido específico variará. Eso está OK.

### ¿Necesito usar ambas plataformas?
No. Elige una y sé consistente:
- **Claude Code**: Mejor para workflows complejos (hooks automáticos, agentes especializados)
- **Copilot Chat**: Mejor para integración nativa en VS Code (no requiere otra extensión)

### ¿Cuándo se migra a Opción 2 (prompts)?
Cuando `.github/prompts/*.prompt.md` sea creado (Fase 2 del plan). Hasta entonces, usa Opción 1.

---

## Próximos Pasos

1. **Hoy (Fase 1)**: Ambas plataformas tienen contrato PLAN→AUDIT_PLAN
   - Claude Code: slash commands activados
   - Copilot Chat: escritura manual (Opción 1)

2. **Semana 2 (Fase 2)**: Considerar `.github/prompts/`
   - Copilot Chat: `@prompt /new-feature` si está disponible

3. **Post-v0.6.7 (Fase 3)**: Agentes de Copilot para automatización

---

## Referencias

- **CLAUDE.md**: Política base, siempre activa en Claude Code
- **.claude/commands/**: 8 slash commands con estructura PLAN/AUDIT_PLAN
- **copilot-instructions.md**: Política base para Copilot Chat
- **COPILOT_CHAT_INTEGRATION_GUIDE.md**: Detalles de integración para Copilot Chat

---

**Mantener sincronizado**: Este documento es fuente de verdad para equivalencias. Si cambia una plataforma, actualizar aquí primero.
