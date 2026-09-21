# Guía de uso de Claude Code

## 1. Objetivo

Configurar y usar Claude Code con los slash commands del repositorio para generar código, documentación y revisiones en `util_bbdd`.

## 2. Requisitos Previos

- VS Code instalado (versión 1.85+) o terminal con acceso al CLI de Claude Code
- Cuenta de Anthropic activa
- Repositorio `util_bbdd` clonado localmente
- Familiaridad con la estructura del repositorio: `CLAUDE.md` (política transversal), `.claude/commands/` (slash commands), `.github/prompts/` (prompts de documentación)

## 3. Pasos

### Paso 1 — Instalar Claude Code

```bash
# Extensión VS Code
code --install-extension anthropic.claude-code

# O instalar el CLI globalmente
npm install -g @anthropic-ai/claude-code
```

### Paso 2 — Entender la jerarquía de contexto

Claude Code carga automáticamente en cada sesión:

| Archivo | Cuándo actúa |
|---|---|
| `CLAUDE.md` | Siempre, en cada conversación |
| `.claude/commands/*.md` | Al invocar el slash command correspondiente |
| `.claude/settings.json` | Al iniciar sesión (hooks y permisos) |

El fichero `CLAUDE.md` fija la política transversal del repositorio. Los slash commands añaden flujos estructurados para tareas concretas.

### Paso 3 — Usar slash commands

Escribe el comando en el chat para activar el flujo estructurado:

| Comando | Úsalo cuando |
|---|---|
| `/new-feature` | Añades comportamiento nuevo |
| `/hotfix` | Corriges un bug acotado |
| `/refactor` | Mejoras estructura sin cambiar comportamiento |
| `/audit-code` | Quieres revisión técnica con veredicto |
| `/security-review` | Quieres auditoría de seguridad independiente |
| `/tech-debt` | Quieres inventariar deuda técnica |
| `/maturity-assessment` | Quieres evaluar readiness del repositorio |
| `/version-closure` | Cierras una versión o bloque de cambios |

### Paso 4 — Flujo obligatorio para cambios no triviales

La secuencia que impone `CLAUDE.md` para cualquier cambio no trivial es:

```
PLAN → AUDIT_PLAN → IMPLEMENT → AUDIT_CODE → VERSION
```

No empezar por código si el objetivo no está definido.

### Paso 5 — Generar documentación

```text
Lee src/util_bbdd/managers/sync_mgr.py y genera documentación funcional
usando el prompt en .github/prompts/functional_doc.prompt.md.
Guarda el resultado en docs/functional/managers-sync.md.
Actualiza mkdocs.yml si la página es nueva.
```

## 4. Verificación

```bash
# Validar el build de documentación — Zensical es el generador por defecto (lee mkdocs.yml)
zensical build

# Validación estricta de enlaces con MkDocs Material (recíproco, mismo mkdocs.yml)
python -m mkdocs build --strict

# Ejecutar los tests para verificar que el código sigue funcionando
python -m pytest

# Generar ZIP de la documentación para distribución offline o release de GitHub
python scripts/build_docs_zip.py
# → dist/util_bbdd-docs-{version}.zip
# Opciones: --builder mkdocs | --no-strict | --no-build | --output-dir <dir>
# Ver docs/docs_offline_zip_guide.md para la guía completa.

# Regenerar el diagrama de capas e imports de docs/architecture.md tras cambiar imports entre paquetes de src/
python scripts/gen_arquitectura_capas.py
# Falla sin escribir nada si el dibujo ya no coincide con el código; --edges imprime la tabla medida.
# Ver docs/guides/architecture_diagram_guide.md para la guía completa.
```

Para confirmar que los hooks de Claude Code están activos, crea o edita un archivo en `src/` y verifica que los hooks de `ruff` y `mypy` se ejecutan automáticamente al guardar.

## 5. Variantes y Solución de Problemas

| Error / Síntoma | Causa probable | Solución |
|---|---|---|
| Claude no encuentra `CLAUDE.md` | No estás en la raíz del repositorio | Abrir VS Code desde la raíz del repositorio (`code .`) |
| Slash command no disponible | Claude Code no instalado o no activado | Verificar que la extensión está activa y autenticada |
| Hook de ruff falla al guardar | Código con errores de estilo | Revisar la salida del terminal y corregir los errores indicados |
| Claude inventa APIs o módulos | Prompt sin contexto de código real | Añadir la ruta del archivo al prompt (`Lee src/...`) |
| `mkdocs build` falla con links rotos | Documentación generada con rutas incorrectas | Revisar las rutas relativas del `.md` generado |
