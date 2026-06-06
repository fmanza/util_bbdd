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

| Versión | Tamaño | SHA256 | Fecha |
|---|---|---|---|
| [util_bbdd-docs-latest.zip](../util_bbdd.zip) | ~2.5 MB | `SHA256_HASH_HERE` | 2026-06-06 |

**Cómo usar**:
1. Descarga el ZIP desde el link superior
2. Extrae los archivos: `unzip util_bbdd-docs-latest.zip`
3. **Opción A (Recomendada - Búsqueda completa)**:
   - Windows: Abre PowerShell en la carpeta extraída y ejecuta: `python start-server.py`
   - Linux/macOS: Abre terminal y ejecuta: `python3 start-server.py`
   - El navegador se abrirá automáticamente en `http://localhost:8000`
4. **Opción B (Navegación sin búsqueda)**:
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

El SHA256 se proporciona junto al ZIP para verificar que el archivo no ha sido corrupto durante la descarga.

### Método 1: Terminal (Linux/Mac)

```bash
# Descargar ZIP y checksum desde la release de GitHub
wget https://github.com/fmanza/util_bbdd/releases/download/docs-vX.X.X/util_bbdd-docs-X.X.X.zip
wget https://github.com/fmanza/util_bbdd/releases/download/docs-vX.X.X/util_bbdd-docs-X.X.X.zip.sha256

# Validar
sha256sum -c util_bbdd-docs-X.X.X.zip.sha256
# Salida: util_bbdd-docs-X.X.X.zip: OK ✅
```

### Método 2: PowerShell (Windows)

```powershell
# Calcular SHA256 del ZIP descargado
(Get-FileHash util_bbdd-docs-X.X.X.zip -Algorithm SHA256).Hash

# Comparar manualmente con el SHA256 publicado en la release
# ✅ Si coinciden, el archivo es íntegro
```

### Método 3: Visual (GitHub)

1. Abre la [Release en GitHub](https://github.com/fmanza/util_bbdd/releases)
2. Busca el SHA256 en el texto de la release (field "🔐 Integrity Verification")
3. Compara con la salida de tu terminal

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

```bash
# Opción 1: Con Zensical (recomendado)
zensical build
python scripts/build_docs_zip.py

# Opción 2: Con MkDocs
mkdocs build
python scripts/build_docs_zip.py

# Opción 3: VS Code Task (Ctrl+Shift+P)
Run Task → "docs: build + zip"
```

**Output**: `dist/util_bbdd-docs-{version}-{date}.zip`

### Validar Integridad

```bash
# Calcular SHA256
sha256sum dist/util_bbdd-docs-*.zip

# Comparar con el publicado (si está disponible)
# ✅ Si coinciden, el archivo está íntegro
```

### Opciones Avanzadas

```bash
# Build + ZIP con builder específico
python scripts/build_docs_zip.py --builder zensical

# Solo generar ZIP sin rebuild
python scripts/build_docs_zip.py --no-build

# ZIP en ubicación personalizada
python scripts/build_docs_zip.py --output-dir /tmp
```

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
- [Guía offline ZIP](docs_offline_zip_guide.md) — Documentación técnica del sistema
- [GitHub Repository](https://github.com/fmanza/util_bbdd) — Código fuente

---

*Última actualización: 2026-06-06*
