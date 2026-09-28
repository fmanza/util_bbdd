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

| Origen | Fichero | Checksum |
|---|---|---|
| GitHub Releases (por versión) | `util_bbdd-docs-<versión>.zip` en [releases](https://github.com/fmanza/util_bbdd/releases) (tag `docs-v<versión>`) | `util_bbdd-docs-<versión>.zip.sha256` en la misma release |
| Este sitio (última publicada) | [util_bbdd-docs-latest.zip](https://fmanza.github.io/util_bbdd/util_bbdd-docs-latest.zip) | [util_bbdd-docs-latest.zip.sha256](https://fmanza.github.io/util_bbdd/util_bbdd-docs-latest.zip.sha256) |

Los dos ZIP tienen el mismo contenido (documentación, `start-server.py` y `README_OFFLINE.txt`).

**Cómo usar**

1. Descarga el ZIP desde el link superior
2. Extrae los archivos: `unzip util_bbdd-docs-<versión>.zip` (o `util_bbdd-docs-latest.zip`)
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
# Descargar ZIP y checksum (sustituye X.Y.Z por la versión)
wget https://github.com/fmanza/util_bbdd/releases/download/docs-vX.Y.Z/util_bbdd-docs-X.Y.Z.zip
wget https://github.com/fmanza/util_bbdd/releases/download/docs-vX.Y.Z/util_bbdd-docs-X.Y.Z.zip.sha256

# Validar con el archivo checksum
sha256sum -c util_bbdd-docs-X.Y.Z.zip.sha256
# Salida esperada: util_bbdd-docs-X.Y.Z.zip: OK ✅
```

### Método 2: PowerShell (Windows)

```powershell
# Opción A: Calcular SHA256 del ZIP y comparar manualmente
(Get-FileHash util_bbdd-docs-X.Y.Z.zip -Algorithm SHA256).Hash

# Luego, abre util_bbdd-docs-X.Y.Z.zip.sha256 y compara el valor
# Si coinciden: ✅ Archivo íntegro

# Opción B: Script automático
$hash = (Get-FileHash util_bbdd-docs-X.Y.Z.zip -Algorithm SHA256).Hash
$checksum = (Get-Content util_bbdd-docs-X.Y.Z.zip.sha256).Split()[0]
if ($hash -eq $checksum) { Write-Host "✅ Integridad verificada" } else { Write-Host "❌ Checksum no coincide" }
```

### Método 3: macOS (con shasum)

```bash
shasum -a 256 -c util_bbdd-docs-X.Y.Z.zip.sha256
# Salida esperada: util_bbdd-docs-X.Y.Z.zip: OK ✅
```

---

## 📋 Contenido del ZIP

```
util_bbdd-docs-X.Y.Z.zip
├── start-server.py                 # Servidor local (búsqueda offline)
├── README_OFFLINE.txt              # Instrucciones de uso sin conexión
├── index.html                      # Página de inicio
├── installation/index.html         # Guía de instalación
├── api/
│   ├── managers_sync/index.html
│   ├── bulk_crud/index.html
│   └── ... (referencias técnicas)
├── functional/
│   ├── bulk_operations/index.html
│   └── ... (documentación funcional)
├── examples/
│   ├── bulk_insert_csv/index.html
│   └── ... (ejemplos prácticos)
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

Zensical (el generador de CI) **no ejecuta plugins de MkDocs**, así que el ZIP se genera con
`scripts/build_docs_zip.py`, que empaqueta igual que el plugin `DocumentationZipPlugin` (misma función):

```bash
# ZIP versionado, como el de GitHub Releases → dist/util_bbdd-docs-<versión>.zip (+ .sha256 y CHECKSUMS.txt)
python scripts/build_docs_zip.py

# ZIP dentro del sitio, como el publicado → site/util_bbdd-docs-latest.zip (+ .sha256)
zensical build && python scripts/build_docs_zip.py --no-build --in-site

# Con MkDocs, el plugin lo genera en el propio build → site/util_bbdd-docs-latest.zip (+ .sha256)
python -m mkdocs build
```

El archivo ZIP incluye:
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

Con `mkdocs build`, el ZIP lo genera el plugin `DocumentationZipPlugin` declarado en `mkdocs.yml`
(con Zensical, `scripts/build_docs_zip.py`):

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
