# Ejemplo completo de uso de Codex

## Resumen

Este documento muestra, con ejemplos completos y realistas, cómo se trabaja en este repositorio con **Codex** (extensión de OpenAI para VS Code).

Cubre:

- cómo Codex detecta el contexto del repositorio automáticamente
- cuáles son los archivos de configuración relevantes
- flujo de trabajo estructurado (similar a Claude Code)
- políticas aplicadas a Codex
- ejemplos completos por caso de uso
- diferencias con Claude Code y Copilot Chat

Para la configuración equivalente de Claude Code, consulta [claude_code_usage_complete_example.md](claude_code_usage_complete_example.md).
Para la configuración de Copilot Chat, consulta [github_usage_complete_example.md](github_usage_complete_example.md).

---

## Configuración de Codex para este repositorio

### Archivos que Codex puede leer automáticamente

| Archivo | Propósito |
|---|---|
| [../../AGENTS.md](../../AGENTS.md) | Instrucciones para Codex — contexto especializado del proyecto |
| [../../.github/SHARED_INSTRUCTIONS.md](../../.github/SHARED_INSTRUCTIONS.md) | Arquitectura, SOLID y políticas comunes |
| [../../pyproject.toml](../../pyproject.toml) | Versión, Python soportado, herramientas reales |
| [../../.claude/settings.json](../../.claude/settings.json) | Hooks y permisos de desarrollo |
| [../../.github/instructions/](../../.github/instructions/) | Reglas por ruta o tipo de archivo |

### Cómo Codex funciona en este repositorio

1. **Carga inicial**: Codex lee `AGENTS.md` y entiende el contexto de `project_copy`
2. **Validación de contexto**: Contrasta el código real con lo que ve en las instrucciones
3. **Edición manual**: Realiza cambios acotados con parches pequeños
4. **Verificación**: Ejecuta tests relevantes para validar

### Diferencia con Claude Code

| Aspecto | Codex | Claude Code |
|---|---|---|
| Slash commands | No aplica | Sí, `/new-feature`, `/hotfix`, etc. |
| Flujo estructurado | Manual o implícito | Obligatorio por comando |
| Contexto por defecto | Lee `AGENTS.md` + el código | Lee `CLAUDE.md` + comandos |
| Salida esperada | Código y cambios acotados | Salida estructurada (PLAN → VERSION) |
| Auditoría integrada | No | Sí, con `/audit-code` |
| Punto de entrada | `AGENTS.md` | `CLAUDE.md` |

---

## Cómo trabajar con Codex

### Paso 1: Formulación clara de la tarea

Abre Codex y describe la tarea con alcance concreto:

```text
Trabaja sobre project_copy.

Objetivo: [describe el cambio]
Alcance: [rutas o módulos]
Restricciones: [compatibilidad, no refactor, docs, etc.]

Primero revisa `.github/SHARED_INSTRUCTIONS.md` y el código real.
Después implementa con cambios acotados y ejecuta tests relevantes.
```

**Ejemplo real**:

```text
Objetivo: añadir soporte para personalización de prefijos de proyecto en generadores
Alcance: src/project_copy/services/generators.py, tests/unit/services/test_generators.py
Restricciones: 
  - Compatibilidad hacia atrás con API existente
  - No refactorizar PersonalizationEngine
  - Docs en docstrings y ejemplos
```

### Paso 2: Trabajo incremental

Codex debe:

1. **Leer el código real** — no inventar módulos
2. **Hacer cambios pequeños** — parches específicos, no refactors
3. **Respetar la arquitectura** — servicios, facades, CLIs
4. **Validar con tests** — ejecuta `pytest tests/unit/services -q`

Ejemplo de cambio acotado:

```python
# services/generators.py
def generate_project(self, name: str, prefix: str | None = None) -> Path:
    """Generate a new project structure.
    
    Args:
        name: Project name
        prefix: Optional prefix for project directories (default: 'gen_')
        
    Returns:
        Path to generated project
    """
```

### Paso 3: Verificación

Después de cada cambio:

```bash
# Lint
python -m ruff check src tests

# Type check
python -m mypy src

# Tests relevantes
python -m pytest tests/unit/services/test_generators.py -v
```

Si algún comando falla, Codex corrige antes de continuar.

---

## Criterios de cierre

Antes de terminar, Codex debe:

- ✅ Actualizar documentación si cambia CLI, API pública o archivos generados
- ✅ Sincronizar instrucciones IA si cambian reglas comunes
- ✅ Ejecutar pruebas relevantes o explicar por qué no se ejecutaron
- ✅ Resumir archivos modificados y comportamiento verificado

---

## Ejemplos completos

### Ejemplo 1. Cambio en un servicio

**Solicitud a Codex**:

```text
Trabaja sobre project_copy.

Objetivo: permitir que DuplicateProjectManager valide que el directorio destino sea vacío antes de copiar
Alcance: src/project_copy/services/project_manager.py
Restricciones: cambios mínimos, mantener la API pública

Revisa el código actual y propón la validación. Luego ejecuta tests relevantes.
```

**Flujo esperado de Codex**:

1. Lee `src/project_copy/services/project_manager.py`
2. Identifica la clase `DuplicateProjectManager` y su método principal
3. Propone una validación con excepción específica
4. Actualiza tests en `tests/unit/services/test_project_manager.py`
5. Ejecuta `python -m pytest tests/unit/services/test_project_manager.py -v`
6. Resume: "✅ Validación añadida. 3 tests nuevos pasan. API pública sin cambios."

### Ejemplo 2. Fix de bug acotado

**Solicitud a Codex**:

```text
Trabaja sobre project_copy.

Objetivo: corregir que PersonalizationEngine sobrescribe archivos README sin validación
Alcance: src/project_copy/services/personalization.py
Restricciones: solo fix mínimo, sin refactor

Después, verifica con tests.
```

**Flujo esperado de Codex**:

1. Lee el código afectado
2. Identifica la línea que sobrescribe sin validación
3. Añade lógica de validación simple
4. Añade test que valide el comportamiento
5. Ejecuta tests: `pytest tests/unit/services/test_personalization.py::test_personalization_respects_existing_readme -v`
6. Resume cambios y cierra

### Ejemplo 3. Actualización de documentación

**Solicitud a Codex**:

```text
Trabaja sobre project_copy.

Objetivo: documentar la función generate_project_with_metadata en README.md
Alcance: docs, README.md, ejemplos
Restricciones: no refactorizar código existente

Actualiza la documentación con un ejemplo claro.
```

**Flujo esperado de Codex**:

1. Lee la función en `src/project_copy/services/generators.py`
2. Lee `README.md` actual
3. Propone una sección o ejemplo
4. Verifica que los ejemplos sean ejecutables
5. Resume cambios en documentación

### Ejemplo 4. Auditoría independiente (requiere intervención del usuario)

Si quieres que Codex audite sin escribir código:

```text
Trabaja sobre project_copy.

Objetivo: revisar la función copy_project en FileSystemService
Alcance: src/project_copy/services/file_system.py
Quiero: bugs potenciales, edge cases, paths que falten validación, tests insuficientes

NO escribas código. Solo analiza.
```

**Salida esperada**:

- Lista de hallazgos potenciales
- Edge cases identificados
- Recomendaciones

---

## Integración con el flujo de desarrollo

### Flujo recomendado

```
Usa Codex para → cambios acotados en código, tests, documentación
Usa Claude Code para → PLAN/AUDIT_PLAN/IMPLEMENT/AUDIT_CODE/VERSION (flujos complejos)
Usa Copilot Chat para → consultas rápidas, exploración, orientación
```

### Cuándo prefieres a cada uno

| Tarea | Mejor opción | Razón |
|---|---|---|
| Cambio pequeño en 1-2 archivos | Codex | Rápido y directo |
| Nueva feature compleja | Claude Code | Flujo estructurado, auditoría |
| Pregunta rápida sobre código | Copilot Chat | Conversación natural |
| Auditoría de seguridad | Claude Code + Security Reviewer | Especialización dedicada |
| Documentación simple | Codex | Cambios puntuales |

---

## Comandos útiles referenciados

```bash
# Lint — verificar estilo
python -m ruff check src tests

# Format — aplicar formato automático
python -m ruff format src tests

# Type-check — verificar tipos
python -m mypy src

# Tests — ejecutar todas las pruebas
python -m pytest

# Tests específicos — enfoque en módulo
python -m pytest tests/unit/services -q

# Build — empaquetar
python -m build

# Documentación local
mkdocs serve
mkdocs build
```

---

## Resumen de diferencias

| Herramienta | Mejor para | Entrada principal |
|---|---|---|
| **Codex** | Cambios pequeños, acotados, verificables | Descripción clara + código real |
| **Claude Code** | Features complejas, flujos estructurados | `/command` + `CLAUDE.md` |
| **Copilot Chat** | Consultas, orientación, exploración | Preguntas naturales + `copilot-instructions.md` |
| **Agentes de Copilot** | Roles especializados, auditoría | Selección de agente + instrucciones |

---

*Actualizado: 2026-04-28*
