# Guía de Generación de Documentación desde VS Code

## 1. Objetivo

Generar documentación funcional y técnica de `util_bbdd` usando las herramientas de IA disponibles en VS Code.

## 2. Requisitos Previos

- VS Code instalado (versión 1.85+)
- Al menos una de las herramientas de IA disponibles:

| Herramienta | Requisito | Instalación |
|---|---|---|
| **Claude Code** | Cuenta Anthropic | Extensión "Claude Code" en VS Code |
| **Copilot Chat** | Suscripción GitHub Copilot | Extensión "GitHub Copilot Chat" |
| **Codex** | Cuenta OpenAI | Extensión "Codex" de OpenAI |

- Repositorio `util_bbdd` clonado localmente con dependencias instaladas (`pip install -e ".[dev]"`)
- Familiaridad con los prompts en `.github/prompts/` (`functional_doc.prompt.md`, `technical_doc.prompt.md`, `guide_doc.prompt.md`, `example_doc.prompt.md`)

## 3. Pasos

### Paso 1 — Instalar y configurar la herramienta elegida

**Claude Code:**

```bash
# En el terminal integrado de VS Code
code --install-extension anthropic.claude-code
```

Autenticarse con la cuenta de Anthropic al primer inicio.

**Copilot Chat:**

Instalar la extensión `GitHub Copilot` desde el Marketplace. Activar la suscripción en [github.com/features/copilot](https://github.com/features/copilot).

**Codex:**

Instalar la extensión `Codex` de OpenAI desde el Marketplace. Configurar la API Key de OpenAI en los ajustes de la extensión.

### Paso 2 — Seleccionar el tipo de documentación a generar

| Tipo | Audiencia | Prompt base | Destino en docs/ |
|---|---|---|---|
| Funcional | Jefes de proyecto, QA | `functional_doc.prompt.md` | `docs/functional/` |
| Técnica | Desarrolladores | `technical_doc.prompt.md` | `docs/api/` |
| Guía | Usuarios finales | `guide_doc.prompt.md` | `docs/` raíz |
| Ejemplo | Desarrolladores | `example_doc.prompt.md` | `docs/examples/` |

### Paso 3 — Ejecutar el prompt correspondiente

**Con Claude Code:**

```text
Lee src/util_bbdd/managers/sync_mgr.py y genera documentación funcional
usando el prompt en .github/prompts/functional_doc.prompt.md.
Guarda el resultado en docs/functional/managers_sync.md.
```

**Con Copilot Chat:**

```text
#file:.github/prompts/functional_doc.prompt.md
#file:src/util_bbdd/managers/sync_mgr.py

Genera la documentación funcional del módulo indicado siguiendo las instrucciones del prompt.
```

**Con Codex:**

```text
Usando el prompt en .github/prompts/technical_doc.prompt.md, genera documentación
técnica para src/util_bbdd/bulk/crud.py. Guarda en docs/api/bulk_crud.md.
```

### Paso 4 — Actualizar mkdocs.yml

Tras crear o mover una página, añadir la entrada correspondiente en `mkdocs.yml` bajo `nav:`:

```yaml
- Referencia Técnica:
    - Bulk Operations:
        - CRUD Masivo: api/bulk_crud.md
```

### Paso 5 — Validar el build

```bash
# En el terminal integrado (Ctrl + `)
# Zensical es el generador por defecto (lee mkdocs.yml)
zensical build

# Validación estricta de enlaces con MkDocs Material (recíproco, mismo mkdocs.yml)
python -m mkdocs build --strict
```

## 4. Verificación

```bash
# Construir el sitio y comprobar que no hay errores (Zensical por defecto)
zensical build

# Validación estricta de enlaces con MkDocs Material (recíproco, mismo mkdocs.yml)
python -m mkdocs build --strict

# Si pasa, servir localmente para revisión visual (Zensical por defecto)
zensical serve
```

Navegar a `http://127.0.0.1:8000` y comprobar que la nueva página aparece en la navegación y que los diagramas Mermaid se renderizan correctamente.

Output esperado de un build correcto:

```
INFO    -  Documentation built in X.X seconds
```

## 5. Variantes y Solución de Problemas

| Error / Síntoma | Causa probable | Solución |
|---|---|---|
| `Aborted with N warnings in strict mode` | Links rotos en la documentación generada | Revisar los links del fichero `.md` generado; corregir rutas relativas |
| La herramienta IA inventa capacidades | El prompt no referencia el código real | Añadir `#file:src/...` al prompt o especificar la ruta del módulo explícitamente |
| Diagrama Mermaid no se renderiza | Sintaxis Mermaid inválida | Validar el bloque `mermaid` en [mermaid.live](https://mermaid.live) antes de guardar |
| La página no aparece en el sitio | Entrada faltante en `mkdocs.yml` | Añadir la ruta bajo `nav:` en `mkdocs.yml` |
| `zensical: command not found` | Zensical no instalado | `pip install zensical` |
| `mkdocs: command not found` | MkDocs no instalado | `pip install mkdocs-material mkdocstrings[python]` |
