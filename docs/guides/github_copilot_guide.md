# Guía de uso de GitHub Copilot Chat

## 1. Objetivo

Configurar y usar GitHub Copilot Chat con los agentes y prompts del repositorio para generar y revisar documentación de `util_bbdd`.

## 2. Requisitos Previos

- VS Code instalado (versión 1.85+)
- Suscripción activa a GitHub Copilot
- Extensión "GitHub Copilot" y "GitHub Copilot Chat" instaladas
- Repositorio `util_bbdd` clonado localmente
- Familiaridad con los agentes en `.github/agents/` y los prompts en `.github/prompts/`

## 3. Pasos

### Paso 1 — Instalar las extensiones necesarias

```bash
code --install-extension GitHub.copilot
code --install-extension GitHub.copilot-chat
```

Autenticarse con la cuenta de GitHub al primer inicio.

### Paso 2 — Entender la jerarquía de contexto

Copilot Chat aplica en este repositorio la siguiente jerarquía:

| Nivel | Archivo / Carpeta | Para qué sirve |
|---|---|---|
| 1 | `.github/copilot-instructions.md` | Política transversal del repositorio |
| 2 | `.github/agents/` | Roles especializados con límites de herramientas |
| 3 | `.github/instructions/` | Reglas por ruta o tipo de archivo |
| 4 | `.github/prompts/` | Flujos de trabajo para tareas concretas |

### Paso 3 — Usar agentes especializados

Los agentes son los ficheros `.github/agents/*.agent.md` (13; registro completo en `.github/AGENTS.md`). En el chat
de Copilot se elige el agente por su nombre. Los más usados para documentación:

| Agente (fichero) | Úsalo para |
|---|---|
| Documentation Generator (`documentation-generator`) | Generar documentación funcional o técnica de un módulo |
| Documentation Reviewer (`documentation-reviewer`) | Auditar documentación existente sin modificarla |
| Code Auditor (`code-auditor`) | Revisión técnica independiente de cambios |
| Plan Architect (`plan-architect`) | Diseñar un plan de implementación |
| Version Closer (`version-closer`) | Cerrar una versión con changelog y release notes |

### Paso 4 — Referenciar archivos en el prompt

Copilot Chat puede recibir contexto explícito con `#file:`:

```text
#file:.github/prompts/functional_doc.prompt.md
#file:src/util_bbdd/managers/sync_mgr.py

(con el agente Documentation Generator seleccionado)
Genera la documentación funcional del módulo indicado siguiendo las instrucciones del prompt.
Guarda en docs/functional/managers_sync.md y actualiza mkdocs.yml.
```

### Paso 5 — Generar documentación técnica con Mermaid

```text
#file:.github/prompts/technical_doc.prompt.md
#file:src/util_bbdd/bulk/crud.py

Genera documentación técnica con diagrama Mermaid. Tipo: flowchart TD.
Guarda en docs/api/bulk_crud.md.
```

## 4. Verificación

```bash
# Validar build de documentación — Zensical es el generador por defecto (lee mkdocs.yml)
zensical build

# Validación estricta de enlaces con MkDocs Material (recíproco, mismo mkdocs.yml)
python -m mkdocs build --strict

# Servir localmente para revisión visual (Zensical por defecto)
zensical serve
```

Navegar a `http://127.0.0.1:8000` y verificar que la nueva página aparece en la navegación y que los diagramas Mermaid se renderizan correctamente.

## 5. Variantes y Solución de Problemas

| Error / Síntoma | Causa probable | Solución |
|---|---|---|
| El agente no respeta el prompt | No se ha referenciado con `#file:` | Añadir `#file:.github/prompts/[nombre].prompt.md` al inicio del prompt |
| Copilot no encuentra el archivo | Ruta incorrecta en `#file:` | Usar ruta relativa desde la raíz del repositorio |
| La documentación generada inventa APIs | Prompt sin contexto de código real | Añadir `#file:src/...` con el archivo del módulo |
| `mkdocs build` falla con links rotos | Links a `.github/` incluidos en el Markdown generado | Reemplazar los links externos por referencias en texto plano |
| Agente no disponible | Copilot Chat no actualizado | Actualizar la extensión GitHub Copilot Chat a la última versión |
