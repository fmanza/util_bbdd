# 📥 Descargas

Descarga la documentación completa de **util_bbdd** en formato offline (ZIP).

---

## 📦 Documentación Offline

La documentación completa está disponible como un archivo ZIP comprimido que puedes descargar y abrir en cualquier navegador sin conexión a Internet.

### Características del ZIP

- ✅ **Búsqueda offline** — Índice de búsqueda completo
- ✅ **Navegación interactiva** — Menú y referencias cruzadas
- ✅ **Diagramas Mermaid** — Grafos de relaciones, flujos, arquitectura
- ✅ **Ejemplos de código** — CRUD, async, comparadores, migraciones
- ✅ **Responsive** — Compatible con móvil, tablet y desktop  

---

## 🔗 Descarga Actual

| Versión | Tamaño | Checksum | Fecha |
|---|---|---|---|
| [util_bbdd-docs-latest.zip](https://github.com/fmanza/util_bbdd/releases/latest) | ~2.5 MB | [.sha256](https://github.com/fmanza/util_bbdd/releases/latest) | 2026-06-06 |

**Cómo usar**

1. Descarga el ZIP desde el link superior
2. Extrae los archivos: `unzip util_bbdd-docs-latest.zip`
3. Elige una opción:

**Opción A (Recomendada - Búsqueda completa)**

- Windows: Abre PowerShell en la carpeta extraída y ejecuta: `python start-server.py`
- Linux/macOS: Abre terminal y ejecuta: `python3 start-server.py`
- El navegador se abrirá automáticamente en `http://localhost:8000`

**Opción B (Navegación sin búsqueda)**

- Abre directamente `index.html` en tu navegador
- Todos los menús y referencias funcionan correctamente
- La búsqueda no disponible en este modo (limitación de seguridad del navegador)

### ¿Por qué usar el servidor local?

La búsqueda offline usa **Web Workers** de JavaScript, que los navegadores **no permiten ejecutar desde archivos** (`file:///`) por razones de seguridad. El servidor local resuelve esto sirviendo la documentación a través de `http://`, permitiendo:

- ✅ Búsqueda completa e instantánea
- ✅ Diagramas Mermaid interactivos
- ✅ JavaScript habilitado para todas las características
- ✅ Mejor experiencia de usuario (sin limitaciones)

**Sin servidor**: navegación funcional, búsqueda deshabilitada (CORS).  
**Con servidor**: todas las características disponibles.

---

## 🔐 Validar Integridad (SHA256)

El archivo `.sha256` adjunto contiene el hash de integridad del ZIP. Descarga ambos archivos y valida usando tu plataforma.

### Método 1: Terminal (Linux/macOS)

```bash
# Descargar ZIP y checksum
wget https://github.com/fmanza/util_bbdd/releases/download/docs-vX.X.X/util_bbdd-docs-latest.zip
wget https://github.com/fmanza/util_bbdd/releases/download/docs-vX.X.X/util_bbdd-docs-latest.zip.sha256

# Validar con el archivo checksum
sha256sum -c util_bbdd-docs-latest.zip.sha256
# Salida esperada: util_bbdd-docs-latest.zip: OK ✅
```

### Método 2: PowerShell (Windows)

```powershell
# Opción A: Calcular SHA256 del ZIP y comparar manualmente
(Get-FileHash util_bbdd-docs-latest.zip -Algorithm SHA256).Hash

# Luego, abre util_bbdd-docs-latest.zip.sha256 y compara el valor
# Si coinciden: ✅ Archivo íntegro

# Opción B: Script automático
$hash = (Get-FileHash util_bbdd-docs-latest.zip -Algorithm SHA256).Hash
$checksum = (Get-Content util_bbdd-docs-latest.zip.sha256).Split()[0]
if ($hash -eq $checksum) { Write-Host "✅ Integridad verificada" } else { Write-Host "❌ Checksum no coincide" }
```

### Método 3: macOS (con shasum)

```bash
shasum -a 256 -c util_bbdd-docs-latest.zip.sha256
# Salida esperada: util_bbdd-docs-latest.zip: OK ✅
```

---

## 📋 Contenido del ZIP

```
util_bbdd-docs-latest.zip
├── index.html                      # Página de inicio
├── INSTALLATION.html               # Guía de instalación
├── api/
│   ├── managers-sync.html
│   ├── managers-async.html
│   ├── bulk-crud.html
│   └── ... (30+ referencias técnicas)
├── functional/
│   ├── managers-sync.html
│   ├── bulk-operations.html
│   └── ... (25+ guías funcionales)
├── examples/
│   ├── bulk-insert-csv.html
│   ├── schema-comparison.html
│   └── ... (15+ ejemplos prácticos)
├── css/
│   ├── material.css               # Tema Material Design 3
│   ├── mermaid.css
│   └── nav.css
├── js/
│   ├── mermaid.min.js             # Diagrams Mermaid
│   ├── search.js                  # Búsqueda offline
│   └── instant.js
└── search/
    └── search_index.json          # Índice de búsqueda
```

---

## 🛠️ Para Desarrolladores

### Generar ZIP Localmente

El ZIP se genera **automáticamente** durante el build de documentación a través del plugin `DocumentationZipPlugin`.

```bash
# Opción 1: Con MkDocs (recomendado)
python -m mkdocs build
# → Genera: site/util_bbdd-docs-latest.zip

# Opción 2: Con Zensical
zensical build
# → Genera: site/util_bbdd-docs-latest.zip

# Opción 3: VS Code Task (Ctrl+Shift+P)
Run Task → "build"
```

**Output**: `site/util_bbdd-docs-latest.zip` (generado automáticamente)

El archivo ZIP incluye automáticamente:
- Documentación HTML renderizada
- Servidor local (`start-server.py`) para búsqueda offline
- Instrucciones README (`README_OFFLINE.txt`)

### Validar Integridad

```bash
# Windows (PowerShell)
(Get-FileHash site/util_bbdd-docs-latest.zip -Algorithm SHA256).Hash

# Linux/macOS
sha256sum site/util_bbdd-docs-latest.zip

# Comparar manualmente con el SHA256 publicado en GitHub Releases
# ✅ Si coinciden, el archivo está íntegro
```

### Plugin de Documentación

El ZIP se genera mediante el plugin `DocumentationZipPlugin` integrado en `mkdocs.yml`:

```ini
[project.entry-points."mkdocs.plugins"]
documentation_zip = "util_bbdd.docs_build_plugin:DocumentationZipPlugin"
```

**Configuración**: Automática, no requiere parámetros. El plugin se ejecuta en el hook `on_post_build` de mkdocs.

---

## 📦 Versiones Anteriores

Todas las versiones publicadas están disponibles en:
- **GitHub Releases**: [fmanza/util_bbdd/releases](https://github.com/fmanza/util_bbdd/releases)
- Cada release incluye el ZIP de documentación adjunto

---

## ❓ FAQ

- **¿Cómo buscar en el ZIP offline?**  
  Abre `index.html` y usa el campo de búsqueda en la esquina superior (requiere JavaScript habilitado).

- **¿Puedo actualizar el ZIP?**  
  Sí. Descargar la última versión desde esta página. También puedes construir uno personalizado siguiendo los pasos de "Para Desarrolladores".

- **¿Incluye código fuente?**  
  No. El ZIP contiene solo documentación HTML/CSS/JS. El código fuente está en [GitHub](https://github.com/fmanza/util_bbdd).

- **¿Funcionan los links internos?**  
  Sí. Todos los links relativos funcionan dentro del ZIP.

- **¿Qué navegadores soporta?**  
  Todos los navegadores modernos (Chrome, Firefox, Safari, Edge). Requiere JavaScript habilitado para búsqueda.

---

## 🔗 Enlaces Relacionados

- [Configuración Zensical](https://github.com/fmanza/util_bbdd/blob/develop/ZENICAL.md) — Generadores de documentación
- [Guía de Instalación CI/CD](https://github.com/fmanza/util_bbdd/blob/develop/.github/docs-zip-setup-guide.md) — GitHub Actions y automatización
- [Guía offline ZIP](guides/docs_offline_zip_guide.md) — Documentación técnica del sistema
- [GitHub Repository](https://github.com/fmanza/util_bbdd) — Código fuente

---

*Última actualización: 2026-06-06*
