# Commit — 2026-06-05-docs-offline-zip

## Mensaje de commit

```
feat(docs): añadir distribución offline ZIP del sitio de documentación

- scripts/build_docs_zip.py: CLI que encadena zensical/mkdocs build + shutil.make_archive;
  genera dist/util_bbdd-docs-{version}.zip leyendo la versión de pyproject.toml.
  Opciones: --builder, --no-strict, --no-build, --output-dir.
- .github/workflows/docs-release.yml: workflow disparado en push v* y workflow_dispatch;
  sube el ZIP como adjunto a la GitHub Release con softprops/action-gh-release@v2.
- docs/docs_offline_zip_guide.md: guía completa (prerequisitos, casos de uso, tabla de
  opciones, integración CI, troubleshooting); registrada en mkdocs.yml bajo Herramientas IA.
- bootstrap_ai_config.prompt.md: script y workflow añadidos a Capa B con nota de adaptación.
- CLAUDE.md + SHARED_INSTRUCTIONS.md: python scripts/build_docs_zip.py en comandos de desarrollo.
- docs/claude_code_guide.md: bloque §4 Verificación con comando y enlace a guía.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

## Ficheros a incluir en este commit (solo esta sesión)

```bash
git add scripts/build_docs_zip.py
git add .github/workflows/docs-release.yml
git add docs/docs_offline_zip_guide.md
git add mkdocs.yml
git add .github/prompts/bootstrap_ai_config.prompt.md
git add CLAUDE.md
git add .github/SHARED_INSTRUCTIONS.md
git add docs/claude_code_guide.md
git add .ai/sessions/2026-06-05-docs-offline-zip/
```

## Ficheros a excluir de este commit (cambios pre-existentes de otras sesiones)

```bash
# NO incluir — pertenecen a sesiones anteriores aún no commiteadas:
# .claude/settings.json
# .ai/sessions/INDEX.md
# .ai/CURRENT_STATE.md
# .ai/DECISIONS_LOG.md
# .ai/sessions/SESSIONS_DIGEST.md
# Todos los D (deleted) de .ai/sessions/20**/
```
