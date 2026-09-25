# Guía de uso de Codex (OpenAI)

## 1. Objetivo

Configurar y usar la extensión Codex de OpenAI para generar documentación y código en `util_bbdd` con prompts explícitos.

## 2. Requisitos Previos

- VS Code instalado (versión 1.85+)
- Cuenta de OpenAI con acceso a la API de Codex
- Extensión "Codex" de OpenAI instalada en VS Code
- Repositorio `util_bbdd` clonado localmente
- API Key de OpenAI disponible

## 3. Pasos

### Paso 1 — Instalar la extensión

```bash
code --install-extension openai.codex
```

En los ajustes de VS Code (`Ctrl+,` → buscar "Codex"), configurar:

- `codex.apiKey`: tu API Key de OpenAI
- `codex.model`: modelo preferido (usa el más reciente disponible en tu cuenta)

### Paso 2 — Entender qué archivos lee Codex automáticamente

Codex carga automáticamente el `AGENTS.md` de la **raíz** del repositorio, que remite al resto:

| Archivo | Propósito |
|---|---|
| `AGENTS.md` (raíz) | Entry point de Codex: contexto obligatorio, flujo y reglas específicas |
| `.github/SHARED_INSTRUCTIONS.md` | Arquitectura, SOLID y políticas comunes |
| `.github/AGENTS.md` | Registro de agentes y flujos especializados |
| `pyproject.toml` | Versión, Python soportado, herramientas reales |
| `.github/instructions/` | Reglas por ruta o tipo de archivo |

### Paso 3 — Flujo de trabajo recomendado

La secuencia equivalente a la de otros agentes:

```
PLAN → IMPLEMENTAR → VERIFICAR
```

Nunca pedir código sin haber dado el contexto del módulo real.

### Paso 4 — Generar documentación funcional

```text
Lee src/util_bbdd/managers/sync_mgr.py y genera documentación funcional
siguiendo las instrucciones del archivo .github/prompts/functional_doc.prompt.md.
Guarda el resultado en docs/functional/managers-sync.md.
```

### Paso 5 — Generar documentación técnica con Mermaid

```text
Usando el prompt en .github/prompts/technical_doc.prompt.md, genera documentación
técnica para src/util_bbdd/bulk/crud.py. Tipo de diagrama: flowchart TD.
Guarda en docs/api/bulk-crud.md y añade la entrada en mkdocs.yml.
```

### Paso 6 — Diferencias con Claude Code y Copilot Chat

| Aspecto | Codex | Claude Code | Copilot Chat |
|---|---|---|---|
| Contexto inicial | `AGENTS.md` (raíz) automático | `CLAUDE.md` automático | `copilot-instructions.md` automático |
| Slash commands | No | Sí (`/new-feature`, etc.) | Agentes (`@nombre`) |
| Ejecución de tests | Manual | Automática (hooks) | Manual |
| Mejor para | Módulo concreto con prompt explícito | Flujos completos | Auditorías y revisiones |

## 4. Verificación

```bash
# Validar build de documentación — Zensical es el generador por defecto (lee mkdocs.yml)
zensical build

# Validación estricta de enlaces con MkDocs Material (recíproco, mismo mkdocs.yml)
python -m mkdocs build --strict
```

Si el build pasa sin errores, la documentación generada es válida. Revisar visualmente con:

```bash
# Servidor local por defecto (Zensical)
zensical serve

# Alternativa recíproca con MkDocs Material
python -m mkdocs serve
```

Navegar a `http://127.0.0.1:8000` y comprobar la nueva página.

## 5. Variantes y Solución de Problemas

| Error / Síntoma | Causa probable | Solución |
|---|---|---|
| Error de autenticación | API Key incorrecta o expirada | Regenerar la API Key en `platform.openai.com` y actualizar la configuración de VS Code |
| Codex inventa módulos o APIs | Prompt sin contexto del código real | Incluir el contenido del archivo fuente en el prompt o pegar el código directamente |
| `mkdocs build` falla | Documentación con rutas incorrectas o links rotos | Revisar las rutas relativas del `.md` generado; corregir referencias a archivos fuera de `docs/` |
| Diagrama Mermaid no válido | Sintaxis incorrecta generada por el modelo | Validar en [mermaid.live](https://mermaid.live); pedir regeneración con restricciones más explícitas |
