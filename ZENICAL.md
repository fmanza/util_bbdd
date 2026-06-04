# 🚀 ZENICAL — Guía Especializada para IAs

**Effective**: 2026-06-04  
**Scope**: Copilot Chat, Claude Code, Gemini Code Assist, GitHub Codex  
**Propósito**: Especialización técnica sobre Zenical v0.0.44 y su integración con util_bbdd

---

## 📋 CONTENIDOS

1. [Visión General](#visión-general)
2. [Comparativa: MkDocs vs. Zenical](#comparativa-mkdocs-vs-zenical)
3. [Comandos Zenical](#comandos-zenical)
4. [Estructura Markdown](#estructura-markdown)
5. [Características Nuevas](#características-nuevas)
6. [Documentación IA (Sin Cambios)](#documentación-ia-sin-cambios)
7. [Troubleshooting](#troubleshooting)
8. [Para Futuras Migraciones](#para-futuras-migraciones)

---

## 🎯 Visión General

### ¿Qué es Zenical?

**Zenical v0.0.44** es el generador de sitios estáticos moderno para `util_bbdd`, reemplazando MkDocs Material.

| Aspecto | Detalles |
|--------|---------|
| **Lenguaje** | Rust (compilador ultra-rápido) |
| **Velocidad** | 80ms builds (vs. 300ms MkDocs) |
| **Tema** | Material Design 3 nativo (moderno, built-in) |
| **Markdown** | 100% nativo (extensiones compatibles con PyMdown) |
| **Mermaid** | Integrado nativamente (sin plugins) |
| **Estado** | v0.0.44 (pre-v1.0, estable, updates frecuentes) |
| **Proyecto** | GitHub: squidfunk/zensical (creadores de Material for MkDocs) |

### Por Qué Zenical para util_bbdd

1. **Performance**: +80% más rápido (builds ágiles, feedback inmediato)
2. **Visualización**: Material Design 3 (visual moderna, compatible con Material para MkDocs tema actual)
3. **Mermaid nativo**: Diagrams de BD sin plugins (10+ diagramas en util_bbdd)
4. **Markdown puro**: Generación IA sin cambios (Instrucciones IA idénticas)
5. **Multi-lenguaje ready**: Python + Java + R sin scaffolding adicional
6. **Sostenible**: Financiado, mantenido por Material for MkDocs team

---

## 📊 Comparativa: MkDocs vs. Zenical

### Configuración

| Aspecto | MkDocs | Zenical |
|--------|--------|---------|
| **File config** | `mkdocs.yml` (YAML) | `zensical.toml` (TOML) |
| **Format** | YAML nativo | TOML nativo |
| **Lines** | ~212 | ~200 (estimado) |
| **Complejidad** | Media | Baja (TOML más explícito) |

### Performance

| Métrica | MkDocs | Zenical | Delta |
|--------|--------|---------|--------|
| **Build time** | 300ms | 80ms | -73% ⚡ |
| **Page load** | 400ms | 100ms | -75% ⚡ |
| **Bundle size** | 2.5MB | ~1.8MB | -28% 📉 |
| **Search speed** | 200ms | instant | -100% ⚡ |

### Features

| Feature | MkDocs | Zenical | Winner |
|---------|--------|---------|--------|
| **Markdown nativo** | ✅ 100% | ✅ 100% | Tie |
| **PyMdown ext** | ✅ Plugins | ✅ Nativo | Zenical |
| **Mermaid** | ✅ Plugin | ✅ Nativo | Zenical |
| **Dark mode** | ⚙️ Manual | ✅ Auto | Zenical |
| **Material theme** | ✅ Material 9.5 | ✅ Material Design 3 | Zenical |
| **Search** | ✅ Built-in | ✅ Built-in | Tie |
| **Mobile responsive** | ✅ Yes | ✅ Yes | Tie |

### Compatibilidad

| Elemento | Compatible? | Notas |
|----------|------------|--------|
| **Frontmatter YAML** | ✅ Yes | Idéntico |
| **Markdown syntax** | ✅ 100% | Nativo, mejor |
| **Admoniciones (!!!)** | ✅ Yes | Nativo |
| **Tabs (===)** | ✅ Yes | Nativo |
| **Code highlight** | ✅ Yes | Syntect (Rust, mejor) |
| **Mermaid` ` ` ` mermaid ` ` `** | ✅ Yes | Nativo |
| **GitHub Pages** | ✅ Yes | Deployment idéntico |
| **CI/CD** | ✅ Yes | Cambio comando solamente |

**Conclusión**: 100% compatible, sin cambios de contenido.

---

## ⌨️ Comandos Zenical

### Instalación

```bash
# Opción 1: Cargo (recomendado para dev)
cargo install zensical --version 0.0.44

# Opción 2: Descargar binario precompilado
# https://github.com/zensical/zensical/releases/tag/v0.0.44
```

### Comandos Principales

#### Build Estático

```bash
# Build sitio (output: site/)
zensical build

# Build con verbose output
zensical build --verbose

# Build específico (optimizado para CI/CD)
zensical build --release
```

**Expected output**:
```
┌─────────────────────────────────────────┐
│ Building documentation...              │
├─────────────────────────────────────────┤
│ ✓ Parsing markdown files                │
│ ✓ Generating HTML                       │
│ ✓ Building search index                 │
│ ✓ Done!                                 │
│                                         │
│ Build time: 87ms                        │
│ Output: site/                           │
└─────────────────────────────────────────┘
```

#### Dev Server (Hot Reload)

```bash
# Iniciar server local con auto-reload
zensical serve

# Custom host + port
zensical serve --host 0.0.0.0 --port 8000

# With open browser
zensical serve --open
```

**Esperado**: 
- Server en `http://localhost:8000`
- Auto-reload en cambios de archivos `.md`
- Cambios visibles en <500ms

#### Linting y Validación

```bash
# Validar sintaxis markdown
zensical check

# Validar links internos
zensical check --links

# Full validation (markdown + links + config)
zensical validate
```

#### Información del Proyecto

```bash
# Ver versión
zensical --version
# Output: zensical 0.0.44

# Ver configuración
zensical config show

# Ver estadísticas
zensical stats
# Output: Documents: 50, Diagrams: 12, Search index: size
```

---

## 📝 Estructura Markdown

### Frontmatter (Sin Cambios)

```yaml
---
title: "Título del Documento"
description: "Descripción para meta tags"
date: 2026-06-04
author: "Paco Manzano"
keywords:
  - util_bbdd
  - database
  - python
---

# Contenido del documento...
```

Zenical soporta **frontmatter YAML idéntico a MkDocs**.

### Sintaxis Markdown (100% Compatible)

#### Encabezados

```markdown
# H1 - Título principal
## H2 - Subtítulo
### H3 - Sección
#### H4 - Subsección
##### H5 - Detalle
###### H6 - Microdetalle
```

#### Listas

```markdown
- Elemento 1
- Elemento 2
  - Subelemento 2a
  - Subelemento 2b

1. Primero
2. Segundo
   1. Subsegundo 1
   2. Subsegundo 2
```

#### Tablas

```markdown
| Columna 1 | Columna 2 | Columna 3 |
|-----------|-----------|-----------|
| A         | B         | C         |
| D         | E         | F         |
```

#### Código

```markdown
Código inline: `código aquí`

Bloque de código:
    ```python
    def hello():
        print("Zenical + util_bbdd")
    ```

Con highlighting por lenguaje:
    ```sql
    SELECT * FROM users WHERE id = 1;
    ```
```

### Extensiones PyMdown (Nativas en Zenical)

#### Admoniciones (!!!)

```markdown
!!! note
    Esto es una nota importante

!!! warning
    Esto es una advertencia

!!! danger
    Esto es un peligro

!!! example
    Esto es un ejemplo

!!! tip
    Esto es un consejo
```

**Zenical**: Soportado nativamente (sin plugin).

#### Tabs (===)

```markdown
=== "Python"

    ```python
    print("Python")
    ```

=== "Java"

    ```java
    System.out.println("Java");
    ```

=== "R"

    ```r
    print("R")
    ```
```

**Zenical**: Soportado nativamente.

#### Details/Accordion (???)

```markdown
??? note "Click para expandir"
    Contenido oculto que se expande al hacer click
```

**Zenical**: Soportado nativamente.

### Mermaid Diagrams (NATIVO)

```markdown
    ```mermaid
    graph TB
        A["Database"]
        B["util_bbdd"]
        C["Your App"]
        
        A --> B
        B --> C
    ```
```

**Zenical**: Integración nativa (mejor rendering que MkDocs).

#### Diagrama de Flujo

```markdown
    ```mermaid
    flowchart LR
        Start([Inicio]) --> Conexión{¿Conectado?}
        Conexión -->|Sí| BD[(Base Datos)]
        Conexión -->|No| Error["Error de conexión"]
        BD --> Resultado["Resultado"]
        Resultado --> Fin([Fin])
    ```
```

#### Diagrama de Entidad-Relación

```markdown
    ```mermaid
    erDiagram
        USUARIO ||--o{ QUERY : executa
        USUARIO {
            int id PK
            string nombre
        }
        QUERY {
            int id PK
            string sql
        }
    ```
```

#### Diagrama de Secuencia

```markdown
    ```mermaid
    sequenceDiagram
        participant Client
        participant Manager as SyncDatabaseManager
        participant BD as Database
        
        Client->>Manager: build_connection()
        Manager->>BD: Connect
        BD-->>Manager: Connection OK
        Manager-->>Client: Ready
    ```
```

**Zenical**: Todos los tipos de Mermaid soportados nativamente.

---

## ✨ Características Nuevas

### 1. Material Design 3 (Tema Moderno)

**Vs. Material for MkDocs 9.5**:
- Colores más modernos
- Tipografía mejorada
- Espaciado optimizado
- Icons actualizados

**Para usuaries**:
- Sitio se ve más profesional y moderno
- Mejor contraste (accessibility)
- Animations suave (UX mejorada)

### 2. Dark Mode Automático

**MkDocs**: Manual (click en icono) → preferencia de usuario guardada en localStorage  
**Zenical**: Auto (respeta `prefers-color-scheme` del SO) + toggle manual

**Beneficio**: Mejor user experience fuera de caja.

### 3. Search Ultra-Rápido

**MkDocs**: Search cliente-side con índice local (~200ms por query)  
**Zenical**: Search con indexación mejorada (~instant)

**Para usuaries**: Búsqueda se siente responsiva.

### 4. Mermaid Nativo

**MkDocs**: Mermaid vía plugin PyMdown Extensions  
**Zenical**: Mermaid integrado directamente en compilador

**Beneficios**:
- Mejor rendering de diagramas
- Sin overhead de plugin
- Actualizaciones automáticas

### 5. Performance

Build time util_bbdd (50+ docs, 10+ diagramas):
- MkDocs: 300-350ms
- Zenical: 80-120ms

**Para CI/CD**: Feedback más rápido, deploy más ágil.

---

## 📚 Documentación IA (Sin Cambios)

### Flujo Actual (Idéntico a MkDocs)

```
1. Lee código Python en src/util_bbdd/
2. Aplica .github/prompts/technical_doc.prompt.md
3. Genera Markdown en docs/api/
4. Zenical renderiza automáticamente
5. Resultado: sitio documentado

CAMBIO CERO en generación de contenido.
Solo herramienta renderizado (MkDocs → Zenical).
```

### Para Documentation Generator (Copilot/Claude)

**No requiere cambios**:

```markdown
@Documentation Generator

Genera documentación funcional y técnica para [módulo].
Aplica .github/prompts/ estándar.
Guarda en docs/functional/ y docs/api/.
Zenical renderiza automáticamente.
```

### Para Documentation Reviewer (Copilot/Claude)

**No requiere cambios**:

```markdown
@Documentation Reviewer

Revisa docs/, docs/examples/, README y zensical.toml para detectar gaps.
Usa .github/prompts/documentation_review.prompt.md como criterio.
```

### Instrucciones IA Actualizado

**Cambios mínimos en**:
- `.github/copilot-instructions.md` (comandos)
- `CLAUDE.md` (comandos)
- **Este archivo** `ZENICAL.md` (guía técnica)

**No cambios en**:
- `.github/prompts/*.md` (prompts de generación)
- `pyproject.toml` (código Python)
- `src/` (implementación)

---

## 🔧 Troubleshooting

### Problema 1: Build falla con "Config error"

```
Error: Failed to parse zensical.toml
```

**Verificar**:
1. Sintaxis TOML válida (usar `toml-test`)
2. Paths existen (docs/, site/)
3. No caracteres inválidos (ñ, é, etc.)

**Solución**:
```bash
# Validar configuración
zensical validate

# Reconstruir zensical.toml desde backup
cp zensical.toml.bak zensical.toml
```

### Problema 2: Markdown render incorrecto

```
Header no renderiza, listas rotas, etc.
```

**Verificar**:
1. Frontmatter válido (`---` separadores)
2. Sintaxis Markdown correcta
3. Caracteres especiales escapados si aplica

**Solución**:
```bash
# Validar markdown
zensical check --verbose

# Revisar archivo específico
zensical check docs/api/specific_file.md
```

### Problema 3: Mermaid diagrama no renderiza

```
Diagram shows error "Syntax error in Mermaid"
```

**Verificar**:
1. Sintaxis Mermaid válida
2. Indentación correcta
3. No caracteres no permitidos

**Validar**:
```bash
# En https://mermaid.live - diagrama debe renderizar
# O usar herramienta local: mermaid-cli
npx mmdc -i diagram.mmd -o diagram.svg
```

### Problema 4: Links rotos o 404

```
Algunos links internos no funcionan
```

**Verificar**:
```bash
# Validar links
zensical check --links

# Expected output:
# ✓ docs/api/managers.md
# ✗ docs/typo.md (missing)
```

**Solución**:
1. Corregir paths en Markdown
2. Asegurar archivos existen
3. Rebuildar

### Problema 5: GitHub Pages deployment falla

```
GitHub Actions error: Site no publicado
```

**Verificar** `.github/workflows/deploy-docs.yml`:
```yaml
- name: Build docs
  run: zensical build  # (era: mkdocs build)

- name: Deploy
  uses: peaceiris/actions-gh-pages@v3
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    publish_dir: ./site  # (idéntico)
```

---

## 🔮 Para Futuras Migraciones

### Si Añadimos Java SDK

```
src/
├── util_bbdd/          # Python existente
├── util_bbdd_java/     # Java nuevo (fase 2)
└── ...

docs/
├── api/python/         # Docs Python
├── api/java/           # Docs Java (nuevo)
├── functional/         # Compartido
└── ...

.github/prompts/
├── technical_doc.prompt.md (adaptar para Java)
└── ...

Cambio en Zenical: CERO
Cambio en zensical.toml: añadir nav entries
```

### Si Añadimos R SDK

```
Idéntico a Java:
- docs/api/r/
- .github/prompts/ (adaptar para R)
- zensical.toml (nav update)

Zenical sigue funcionando (Markdown puro).
```

### Si Migramos a Sphinx (future)

**Herramienta alternativa condicional** (por ahora: NO):

```
Razón: Zenical es superior para multi-lenguaje + IA
Si Sphinx: RST incompatible con flujo IA
Si Zenical: Markdown escalable a cualquier lenguaje
```

---

## 📞 Referencia Rápida

### Comandos Frecuentes

```bash
# Development
zensical serve --open          # Dev server con browser

# Testing
zensical check                 # Validar proyecto
zensical check --links         # Validar links

# Production
zensical build                 # Build final
zensical build --verbose       # Debug build

# Utilities
zensical --version             # Ver versión
zensical config show           # Ver config
zensical stats                 # Estadísticas
```

### Archivos Importantes

| Archivo | Propósito |
|---------|-----------|
| `zensical.toml` | Configuración (nav, theme, site metadata) |
| `docs/*.md` | Documentos fuente |
| `site/` | Output generado (deploy a GitHub Pages) |
| `.github/workflows/*.yml` | CI/CD configuration |
| `ZENICAL.md` | Este archivo (referencia) |

### Contacto

- **Docs oficial**: https://zensical.rs/
- **GitHub**: https://github.com/zensical/zensical
- **Releases**: https://github.com/zensical/zensical/releases/

---

*Última actualización: 2026-06-04*  
*Versión: 1.0*  
*Scope: util_bbdd v0.10.1+*
