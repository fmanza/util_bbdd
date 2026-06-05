# TRACEABILITY

## Session metadata
- id: 2026-06-05-docs-offline-zip
- fecha: 2026-06-05
- rama: develop
- skill: new_feature
- fase: IMPLEMENT + CLOSED

## Prompt issued

```
Queremos incluir la posibilidad de descargar el sitio Web generado con mkdocs o zensical
en un ZIP, proponer alternativas.
→ Las dos (A1 script CLI + A3 GitHub Actions)

Documentar en docs en una guía el funcionamiento de scripts/build_docs_zip.py

Incluir como parte de la copia de .github/prompts/bootstrap_ai_config.prompt.md
y actualizar doc IA
```

## Context supplied

- `mkdocs.yml`
- `.github/DOCUMENTATION_STANDARD.md`
- `.github/prompts/bootstrap_ai_config.prompt.md`
- `.github/SHARED_INSTRUCTIONS.md`
- `.github/workflows/docs.yml`
- `docs/claude_code_guide.md`
- `docs/doc_verification_guide.md`
- `pyproject.toml`
- `.gitignore`

## AI output summary

1. **Análisis de alternativas**: propuestas A1 (script CLI), A2 (hook MkDocs), A3 (GitHub Actions), A4 (botón en sitio). Usuario eligió A1 + A3.
2. **`scripts/build_docs_zip.py`**: script CLI con `--builder`, `--no-strict`, `--no-build`, `--output-dir`; lee versión de `pyproject.toml`; genera `dist/util_bbdd-docs-{version}.zip`.
3. **`.github/workflows/docs-release.yml`**: workflow disparado en `push v*` y `workflow_dispatch`; llama al script y sube el ZIP a GitHub Release con `softprops/action-gh-release@v2`.
4. **`docs/docs_offline_zip_guide.md`**: guía completa (objetivo, prerequisitos, casos de uso, tabla de opciones, salida esperada, integración CI, troubleshooting); registrada en `mkdocs.yml` bajo `Herramientas IA`.
5. **`bootstrap_ai_config.prompt.md`**: ficheros añadidos a la tabla de dirección (Capa B) y a la sección §Capa B con nota de adaptación (builder, secrets, prefijo ZIP).
6. **Comandos de desarrollo**: `python scripts/build_docs_zip.py` añadido a `CLAUDE.md` y `SHARED_INSTRUCTIONS.md` como referencia canónica.
7. **`docs/claude_code_guide.md`**: bloque en §4 Verificación con comando, salida y enlace a guía completa.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Script CLI de build + ZIP | `scripts/build_docs_zip.py` | creado |
| Workflow GitHub Actions release | `.github/workflows/docs-release.yml` | creado |
| Guía de distribución offline | `docs/docs_offline_zip_guide.md` | creado |
| Entrada nav `Herramientas IA` | `mkdocs.yml` | modificado |
| Capa B + tabla de dirección | `.github/prompts/bootstrap_ai_config.prompt.md` | modificado |
| Comando en sección comandos | `CLAUDE.md` | modificado |
| Comando en sección comandos | `.github/SHARED_INSTRUCTIONS.md` | modificado |
| Bloque §4 Verificación | `docs/claude_code_guide.md` | modificado |
| Registro sesión | `.ai/sessions/2026-06-05-docs-offline-zip/` | creado |

## Directrices para Futuras IAs

- **[build_docs_zip]**: el script lee la versión desde `pyproject.toml` con `tomllib` (stdlib Python 3.11+); no requiere dependencias extra más allá de las docs (`.[docs]`).
- **[build_docs_zip]**: `--no-build` permite zipear un `site/` ya existente; falla con error claro si `site/` no existe.
- **[workflow docs-release]**: usa el mismo secret `GH_PAT` que `docs.yml` para resolver la dependencia privada `util`; no añadir un secret nuevo.
- **[bootstrap]**: `scripts/build_docs_zip.py` y `docs-release.yml` están en Capa B (no A): necesitan adaptación del builder por defecto, secrets y prefijo del ZIP al trasladar a otro proyecto.
- **[dist/]**: el directorio `dist/` ya está en `.gitignore`; los ZIPs nunca se commitarán accidentalmente.

## Veredicto final

Veredicto: CLOSED
Pendientes al cierre:
- Ninguno. Script, workflow, guía e instrucciones IA actualizadas y sincronizadas.
