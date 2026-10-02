# 🚀 Guía de Configuración de GitHub Actions — util_bbdd

> **Última actualización**: 2026-10-02

## 📋 Checklist de Configuración

Antes de que funcione cualquier workflow, verifica estos requisitos:

### 1. **Tokens y Secretos** ✅

- [ ] `GITHUB_TOKEN`: Automático en GitHub Actions (no requiere configuración manual)
- [ ] `GH_PAT` (GitHub Personal Access Token): Requerido para acceder a repositorios privados
  - Ve a **Settings → Developer settings → Personal access tokens → Tokens (classic)**
  - Crea un token con permisos: `repo` (completo), `workflow`, `write:packages`
  - Guárdalo en **Settings → Secrets and variables → Actions → New repository secret** con nombre `GH_PAT`

### 2. **Permisos del Workflow** ✅

El workflow necesita permisos para escribir releases:

```yaml
permissions:
  contents: write  # ← Obligatorio para crear/actualizar releases
```

**Verifica en tu repo:**
1. Ve a **Settings → Actions → General**
2. En "Workflow permissions", selecciona **"Read and write permissions"** (no solo "Read")
3. Marca **"Allow GitHub Actions to create and approve pull requests"** (opcional, pero recomendado)

### 3. **Estructura de Directorios** ✅

El workflow espera:
```
c:\Desarrollo\python\libs\util_bbdd\
├── docs/                    ← Fuente de documentación
├── site/                    ← Generado por Zensical/MkDocs (creado en el workflow)
├── dist/                    ← Generado por build_docs_zip.py (debe crearse si no existe)
├── scripts/build_docs_zip.py  ← Script de construcción
├── pyproject.toml           ← Requiere [project] version
└── .github/workflows/       ← Los workflows aquí
    ├── docs.yml
    ├── docs-release.yml
    └── docs-zip-release.yml
```

**Si falta `dist/`:** el workflow lo crea ahora automáticamente con `mkdir -p dist`.

---

## 🔧 Problemas Comunes y Soluciones

### **Problema 1: "SHA256 file not found"**

```
⚠️ SHA256 file not found for version X.Y.Z
```

**Causa**: El script `build_docs_zip.py` no generó el archivo `.sha256`

**Solución**:
1. Verifica que el script se ejecute correctamente localmente:
   ```bash
   python scripts/build_docs_zip.py --builder zensical --output-dir dist
   ls -lh dist/
   ```
2. Asegúrate de que `util_bbdd.docs_build_plugin` exporte `SITE_ZIP_NAME` y `build_offline_zip`
3. En el workflow, el comando ahora crea `dist/` automáticamente

### **Problema 2: "dist/util_bbdd-docs-*.zip: No such file or directory"**

```
Error: No files found matching the path dist/util_bbdd-docs-*.zip
```

**Causa**: El ZIP no se generó (probablemente falló `zensical build`)

**Soluciones**:
1. Revisa el log anterior en el workflow para ver por qué falló `zensical build`
2. Verifica que Zensical esté instalado:
   ```bash
   pip install -e ".[docs]"
   which zensical
   ```
3. Intenta buildear localmente:
   ```bash
   zensical build --strict
   ```

### **Problema 3: "Permission denied" en GitHub Actions**

```
fatal: Permission denied to (user)/(repo).git
```

**Causa**: `GH_PAT` no está configurado o es inválido

**Solución**:
1. Crea un nuevo GitHub Personal Access Token (ver Checklist §1)
2. Guárdalo en **Secrets** con nombre exacto `GH_PAT`
3. En el workflow, configúralo ANTES de `pip install`:
   ```yaml
   - name: Configure git credentials
     run: git config --global url."https://x-access-token:${{ secrets.GH_PAT }}@github.com/".insteadOf "https://github.com/"
   ```

### **Problema 4: "Release creation failed"**

```
ncipollo/release-action failed with status 422
Error: Validation failed: Draft release type cannot have a tag name starting with 'v'
```

**Causa**: `ncipollo/release-action` no actualiza releases existentes correctamente

**Solución**: Ya está incluida en la versión mejorada:
- Usar `allowUpdates: true` y `replacesArtifacts: true`
- Usar `softprops/action-gh-release@v2` para uploads más simples (en `docs-release.yml`)

---

## 📊 Flujo de Ejecución Esperado

### Workflow: `docs-zip-release.yml`

**Cuándo se ejecuta:**
- Cuando se hace push a `main` o `develop` con cambios en:
  - `docs/**`
  - `mkdocs.yml`
  - `pyproject.toml`
  - `.github/workflows/docs-zip-release.yml`
- Manualmente: **Actions → "📦 Build & Publish Docs ZIP" → Run workflow**

**Pasos:**
1. ✅ Checkout del código
2. ✅ Setup Python 3.12 (con caché de pip)
3. ✅ Instalar dependencias (`pip install -e ".[docs]"`)
4. ✅ Buildear docs con Zensical (`zensical build --strict`)
5. ✅ Generar ZIP (`python scripts/build_docs_zip.py`)
6. ✅ Calcular SHA256 y crear checksums
7. ✅ Subir artifacts (retención 30 días)
8. ✅ Extraer versión de `pyproject.toml`
9. ✅ Crear GitHub Release con archivos

### Workflow: `docs-release.yml`

**Cuándo se ejecuta:**
- Cuando se crea un tag `v*.*.*` (p. ej. `v0.10.0`)
- Manualmente: **Actions → "Docs Release ZIP" → Run workflow** (especifica version)

**Pasos:**
1. ✅ Checkout del código
2. ✅ Setup Python 3.12
3. ✅ Configura git credentials
4. ✅ Instalar dependencias
5. ✅ Buildear docs y generar ZIP
6. ✅ Subir ZIP a la release

---

## 🧪 Testing Local

Para verificar que todo funciona **antes** de hacer push:

```bash
# 1. Instalar dependencias de docs
pip install -e ".[docs]"

# 2. Buildear documentación
zensical build --strict

# 3. Generar ZIP
mkdir -p dist
python scripts/build_docs_zip.py --builder zensical --output-dir dist

# 4. Verificar archivos generados
ls -lh dist/
cat dist/*.sha256
cat dist/CHECKSUMS.txt
```

**Resultado esperado:**
```
dist/
├── util_bbdd-docs-0.10.0.zip          (5-50 MB típicamente)
├── util_bbdd-docs-0.10.0.zip.sha256   (1 línea con hash)
└── CHECKSUMS.txt                       (log histórico de todos los builds)
```

---

## 🔍 Debugging en GitHub Actions

Si un workflow falla, accede al **log completo**:

1. Ve a **Actions** en tu repositorio
2. Selecciona el workflow fallido
3. Haz clic en **"Build Docs & Publish ZIP"** (el job)
4. Expande el paso que falló
5. **Copia el error completo** y úsalo para buscar en la sección "Problemas Comunes"

---

## 📚 Referencias

- [GitHub Actions: Secrets](https://docs.github.com/es/actions/security-guides/using-secrets-in-github-actions)
- [GitHub Actions: Permissions](https://docs.github.com/es/actions/using-jobs/assigning-permissions-to-jobs)
- [Zensical Documentation](https://zensical.io/)
- [ncipollo/release-action](https://github.com/ncipollo/release-action)
- [softprops/action-gh-release](https://github.com/softprops/action-gh-release)

---

*¿Necesitas ayuda adicional?* Incluye el **URL del workflow fallido** y el **error exacto** de los logs.
