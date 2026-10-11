# Guía de distribución offline — `build_docs_zip.py`

## 1. Objetivo

Generar un fichero ZIP con el sitio de documentación compilado para su distribución offline
(entornos sin acceso a Internet, archivos de versión, adjuntos en releases de GitHub).

El script `scripts/build_docs_zip.py` encadena dos pasos en un solo comando:

1. **Build** — ejecuta `zensical build` o `mkdocs build` sobre el `mkdocs.yml` del proyecto.
2. **ZIP** — empaqueta el directorio `site/` resultante en `dist/util_bbdd-docs-{version}.zip`,
   donde `{version}` se lee automáticamente de `pyproject.toml`.

---

## 2. Requisitos previos

- Python 3.12+ (el del proyecto; el script usa `tomllib` de la stdlib y no requiere dependencias adicionales).
- Entorno virtual activado con las dependencias de documentación instaladas:

    ```bash
    pip install -e ".[docs]"
    ```

- `zensical` o `mkdocs` disponible en el `PATH` del entorno.

---

## 3. Uso local

### Caso habitual — build completo + ZIP

```bash
python scripts/build_docs_zip.py
```

Ejecuta `zensical build --strict` y genera `dist/util_bbdd-docs-{version}.zip`.

### Cambiar el builder a MkDocs

```bash
python scripts/build_docs_zip.py --builder mkdocs
```

### Desactivar `--strict`

```bash
python scripts/build_docs_zip.py --no-strict
```

Útil cuando hay advertencias conocidas que no bloquean la distribución.

### Zipear un `site/` ya construido (sin reconstruir)

```bash
python scripts/build_docs_zip.py --no-build
```

Empaqueta el contenido actual de `site/` sin lanzar el builder.
Falla con error si `site/` no existe.

### Salida en directorio personalizado

```bash
python scripts/build_docs_zip.py --output-dir /tmp/release
```

Acepta rutas absolutas y relativas a la raíz del repositorio.

---

## 4. Referencia de opciones

| Opción | Valor por defecto | Descripción |
|---|---|---|
| `--builder` | `zensical` | Builder a utilizar: `zensical` o `mkdocs` |
| `--no-strict` | _(strict activo)_ | Omite `--strict` en el comando de build |
| `--no-build` | _(build activo)_ | Salta el build; zipea `site/` existente |
| `--output-dir DIR` | `dist/` | Directorio de salida del ZIP |
| `--in-site` | _(desactivado)_ | Escribe `site/util_bbdd-docs-latest.zip` (+ `.sha256`) en lugar del ZIP versionado, para que el sitio publicado ofrezca la descarga ([Descargas](../downloads.md)) |

---

## 5. Salida generada

```
dist/
├── util_bbdd-docs-1.1.0.zip          ← contiene el volcado de site/
├── util_bbdd-docs-1.1.0.zip.sha256   ← hash SHA256 y nombre del ZIP
└── CHECKSUMS.txt                     ← histórico de hashes
```

Comprobar la integridad: `sha256sum -c util_bbdd-docs-1.1.0.zip.sha256` (Linux/macOS) o
`Get-FileHash util_bbdd-docs-1.1.0.zip -Algorithm SHA256` (PowerShell).

El ZIP replica la estructura de `site/` en su raíz. Para usar offline, basta descomprimirlo
y abrir `index.html` en un navegador.

El directorio `dist/` está excluido de git (`.gitignore`), por lo que el ZIP nunca se commitará
accidentalmente.

---

## 6. Integración con GitHub Actions

El workflow `.github/workflows/docs-release.yml` automatiza la generación y publicación del ZIP
en cada release de GitHub:

```
Disparador: push de tag v*  →  build + ZIP  →  adjunto en GitHub Release
```

**Cómo publicar una release con ZIP:**

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

Aparte, `.github/workflows/docs-zip-release.yml`, en cada push a `main` o `develop` que toque `docs/`, `mkdocs.yml` o
`pyproject.toml`, genera el ZIP como artefacto del workflow y crea o actualiza la release `docs-v<versión>` con el ZIP,
su `.sha256` y `CHECKSUMS.txt`.

El workflow:

1. Instala las dependencias de documentación.
2. Ejecuta `python scripts/build_docs_zip.py --builder zensical`.
3. Sube `dist/util_bbdd-docs-*.zip` y su `.sha256` como adjuntos de la release correspondiente al tag.

El ZIP queda disponible en la pestaña **Releases** de GitHub para cualquier usuario del proyecto.

También puede lanzarse manualmente desde la UI de GitHub (`workflow_dispatch`) o con la CLI:

```bash
gh workflow run docs-release.yml
```

---

## 7. Solución de problemas

| Escenario | Causa probable | Solución |
|---|---|---|
| `zensical: command not found` | Builder no instalado en el entorno activo | `pip install -e ".[docs]"` con el venv activado |
| `site/` vacío tras el build | Error silencioso del builder | Revisar la salida de `zensical build --strict` manualmente |
| `--no-build` falla indicando que `site/` no existe | No se ha ejecutado ningún build previo | Ejecutar sin `--no-build` primero |
| El ZIP no aparece en la release de GitHub | Tag no publicado o workflow sin permisos | Verificar que el tag se ha hecho `push` y que el repo tiene `contents: write` en el workflow |
| `tomllib.TOMLDecodeError` | `pyproject.toml` malformado | Validar el fichero con `python -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))"` |
