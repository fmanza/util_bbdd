# GitHub Actions Final Setup & Validation Guide

> **Desde 3.1.0 (2026-10-18)** los workflows ya no usan `GH_PAT` ni configuran credenciales git: `util_bbdd` dejó de depender del paquete privado `util`. Lo que esta guía dice sobre `GH_PAT` es histórico.

## 📋 Estado Actual (Validado Localmente)

Todas las correcciones han sido aplicadas y validadas. Los siguientes componentes están funcionando correctamente:

✅ **Workflows**: `docs-zip-release.yml`, `docs-release.yml`, `tests.yml`  
✅ **Scripts**: `build_docs_zip.py` (Unicode compatible)  
✅ **Configuración**: `pyproject.toml` (mypy + ruff optimizado)  
✅ **Tests locales**: 5547+ tests ejecutándose correctamente  
✅ **Build de documentación**: Zensical 0.0.67 generando 328 archivos  
✅ **ZIP generation**: Dos archivos con checksums SHA256  

---

## 🚀 Pasos para Activar en GitHub

### Paso 1: Verificar Permisos en GitHub

1. Ve a tu repositorio en GitHub
2. Abre **Settings → Actions → General**
3. En "Workflow permissions", asegúrate de que está habilitado:
   - ☑ **"Read and write permissions"** (NO "Read repository contents permission")
4. Guarda los cambios

### Paso 2: Configurar GH_PAT (Solo si usas dependencias privadas)

Si tu librería depende de repositorios privados (como `util @ git+https://github.com/...`):

1. **Crear token personal** (PAT):
   - GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Crear token con scope: `repo` (full control of private repositories)
   - **Nota**: Copia el token, no lo perderás de vista

2. **Agregar como Secret en el repo**:
   - Abre tu repositorio en GitHub
   - Settings → Secrets and variables → Actions
   - Clic en "New repository secret"
   - Nombre: `GH_PAT`
   - Valor: Tu token personal
   - Guarda

**Si no usas dependencias privadas**: Ignora este paso. El workflow usará `GITHUB_TOKEN` automáticamente.

### Paso 3: Hacer Push de los Cambios

```bash
# Asegúrate de estar en la rama principal (main o develop)
cd c:\Desarrollo\python\libs\util_bbdd

# Commiteá los cambios
git add .github/workflows/ scripts/ pyproject.toml .github/GITHUB_ACTIONS_SETUP.md .github/GITHUB_ACTIONS_FINAL_SETUP.md
git commit -m "fix(ci): improve GitHub Actions workflows and Python 3.13/3.14 compatibility

- Fix mypy configuration for Python 3.12+ compatibility
- Add git credentials fallback (GH_PAT → GITHUB_TOKEN) in tests.yml
- Improve error handling in dependency installation
- Replace Unicode emojis with ASCII text in build_docs_zip.py for cross-platform CI compatibility
- Add comprehensive troubleshooting guide (GITHUB_ACTIONS_SETUP.md)"

# Push a GitHub
git push origin main
```

### Paso 4: Verificar Ejecución en GitHub

1. Ve a tu repositorio en GitHub
2. Haz clic en la pestaña **Actions**
3. Deberías ver el workflow `CI` ejecutándose

**Lo que esperar**:
- ✅ `tests.yml` ejecutará los tests en 6 combinaciones (ubuntu-latest + windows-latest × Python 3.12/3.13/3.14)
- ✅ Tras tests exitosos: `docs-zip-release.yml` generará ZIPs de documentación
- ✅ Cuando hagas push de un tag `v*.*.*`: `docs-release.yml` creará un Release en GitHub

---

## 🔍 Checklist de Validación Pre-Push

Ejecuta estos comandos **antes de hacer push**:

```bash
cd c:\Desarrollo\python\libs\util_bbdd

# 1. Verificar configuración
python scripts/verify_github_actions.py

# 2. Lint
python -m ruff check src/ tests/

# 3. Type-check (esperamos warnings de imports externos, pero sin errores de lógica)
python -m mypy src tests/unit/test_protocol_conformance.py

# 4. Tests (opcionalmente con coverage)
python -m pytest tests/unit -v --tb=short -x
```

**Resultado esperado**: Todos los comandos completan sin errores críticos.

---

## 📝 Cambios Realizados

### 1. `pyproject.toml`
- **Cambio**: Actualizado `[tool.mypy]` con `python_version = "3.12"` (compatible hacia adelante con 3.13/3.14)
- **Cambio**: Configurados overrides para módulos opcionales (sqlglot, pyodbc, asyncpg, etc.)
- **Cambio**: `ignore_missing_imports = true` para evitar falsos positivos

### 2. `.github/workflows/tests.yml`
- **Cambio**: Añadido fallback de git credentials (GH_PAT → GITHUB_TOKEN)
- **Cambio**: Mejorado manejo de errores en instalación de dependencias
- **Cambio**: Agregadas flags `--verbose` en caso de fallo

### 3. `.github/workflows/docs-zip-release.yml`
- **Cambio**: Checksum handling más robusto con validación condicional
- **Cambio**: Mejorada creación de releases con `ncipollo/release-action`

### 4. `.github/workflows/docs-release.yml`
- **Cambio**: Cambio a `softprops/action-gh-release@v2` (más confiable)
- **Cambio**: Mejor manejo de globs de archivos

### 5. `scripts/build_docs_zip.py`
- **Cambio**: Reemplazados todos los Unicode emojis (✅, 🔐, 📄, 📋) con ASCII text: `[OK]`, `[HASH]`, `[FILE]`, `[LIST]`
- **Cambio**: Encoding explícito `utf-8` en todas las operaciones de archivo

---

## ⚠️ Troubleshooting

### Problema: "Configure git credentials for private deps" falla

**Causa**: `GH_PAT` no está configurado o es inválido

**Solución**:
1. Si no usas dependencias privadas: Ignora, el workflow usa `GITHUB_TOKEN` como fallback
2. Si usas dependencias privadas: Configura el PAT según **Paso 2** arriba

### Problema: "Cannot find implementation or library stub for module named X"

**Causa**: Módulos opcionales de drivers no están instalados en CI

**Solución**: Normal. Estos son overrides en mypy que ignoran esos módulos intencionalmente.

### Problema: Tests fallan solo en GitHub Actions, pero pasan localmente

**Causa**: Versiones de Python diferentes (local 3.14 vs CI 3.12/3.13/3.14)

**Solución**:
1. Ejecuta tests en Python 3.12 localmente para reproducir:
   ```bash
   pyenv local 3.12  # o similar si usas version manager
   python -m pytest tests/unit -x
   ```
2. Si aún falla, consulta el log completo en GitHub Actions → tu workflow → job output

### Problema: ZIP no se genera en docs-zip-release.yml

**Causa**: Build de Zensical falló

**Solución**:
1. Verifica que `docs/` y `mkdocs.yml` existen
2. Ejecuta localmente: `zensical build --strict`
3. Revisa el log en GitHub Actions para el error específico

---

## 📊 Monitoreo Continuo

### Dónde ver los workflows en GitHub

- **Tab Actions**: Histórico de todas las ejecuciones
- **Settings → Actions → General**: Configuración de permisos
- **Settings → Secrets and variables → Actions**: Variables secretas

### Alertas a configurar (opcional)

Si tu repositorio es público, GitHub Actions es gratuito. Si es privado:
- Monitorea el uso en Settings → Billing and plans → Actions

---

## ✨ Próximos Pasos (Después de Validar)

1. **Tag de versión** para crear Release:
   ```bash
   git tag -a v0.29.0 -m "Release version 0.29.0"
   git push origin v0.29.0
   ```
   Esto triggereará `docs-release.yml` automáticamente.

2. **Monitorea el Release** en GitHub → Releases para confirmar que se creó con:
   - Documentación ZIP
   - Checksum SHA256

---

## 📞 Support

Si los workflows siguen fallando:

1. **Revisar el log completo** en GitHub Actions (haz clic en el job que falló)
2. **Ejecutar el comando localmente** para reproducir
3. **Consultar `.github/GITHUB_ACTIONS_SETUP.md`** para guía detallada de troubleshooting

---

*Última actualización: 2026-09-25*  
*Versión: 0.29.0*  
*Python requerido: 3.12+*
