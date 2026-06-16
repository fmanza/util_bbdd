# CONTEXT SNAPSHOT — 2026-06-16-document-project

## Estado del repositorio

- **Rama activa**: `develop`
- **Último commit**: `6156ad9 docs: documentar RangePartitioner, HashPartitioner y maintenance_scope + Arquetipo 10`
- **Commits nuevos desde sesión anterior** (2026-06-11): ninguno — no hay cambios de código sin documentar
- **Versión**: 0.10.0 (pyproject.toml)

## Ficheros leídos en esta sesión

### Configuración y contexto
- `mkdocs.yml` — configuración MkDocs Material completa
- `pyproject.toml` — versión, dependencias, entry points
- `.gitignore` — patrones de exclusión
- `CLAUDE.md` — instrucciones especializadas Claude Code
- `.github/SHARED_INSTRUCTIONS.md` — instrucciones canónicas multi-plataforma
- `.ai/product.md` (estado previo: v0.8.0 stale)
- `.ai/architecture.md` (estado previo: v0.8.0 stale)
- `.ai/standards.md` (estado previo: Python 3.11+, black como formatter)
- `.ai/runtime.md` (estado previo: Python 3.11+, faltaba scripts/build_docs_zip.py)
- `.ai/CURRENT_STATE.md`
- `.ai/glossary.md`
- `.ai/sessions/INDEX.md`
- `.ai/sessions/2026-06-11-document-project/TRACEABILITY.md`

### Documentación existente
- `docs/index.md` — landing page (v0.10.0 ✅)
- `docs/architecture.md` — arquitectura (✅ actualizada)
- `docs/functional/bulk-parallel-loading.md` — carga paralela (✅ actualizada en sesión anterior)
- `docs/ai-config/claude.md` — Arquetipo 10 (faltaba /security-review)

### Assets verificados
- `docs/assets/css/nav.css` ✅
- `docs/assets/css/mermaid.css` ✅
- `docs/assets/js/mermaid.js` ✅
- `docs/assets/js/sidebar-toggle.js` ❌ → CREADO en esta sesión

## Estado de build previo

Según sesión 2026-06-11: `mkdocs build --strict → 0 warnings · 0 errores ✅`

## Orígenes externos consultados

- `C:\Desarrollo\python\libs\doc_ia\docs\assets\js\sidebar-toggle.js` — fuente del JS copiado/adaptado (STORAGE_KEY cambiado a `util_bbdd_sidebar_collapsed`)
