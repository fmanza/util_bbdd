# QUICK REFERENCE: v0.6.7 GitHub Release — Acciones Inmediatas

**Type**: Checklist
**Audience**: Repository maintainer (fmanza)
**Status**: 🎯 Ready to execute
**Date**: 13 de abril de 2026

---

## 🔴 PRE-RELEASE: Validación Final

```bash
# 1. Verificar estado del código
cd c:\Desarrollo\python\libs\util_bbdd
git status
# Debe estar limpio (no hay cambios uncommitted)

# 2. Lint & Type Check
python -m ruff check src tests              # ✅ 0 errors
python -m mypy src                          # ✅ 0 errors

# 3. Tests
python -m pytest tests/ -v --cov=src      # ✅ 1703 PASS

# 4. Build
python -m build                             # ✅ SUCCESS
```

### Si alguno falla:
- Ver `.ai/GITHUB_RELEASE_PREPARATION_v0.6.7.md` sección "Rollback Plan"

---

## 🟡 RELEASE: Create & Push GitHub Release

```bash
# 5. Cambiar a main branch
git checkout main
git pull origin main

# 6. Merge desde develop (con --no-ff para crear merge commit)
git merge develop --no-ff \
  -m "chore(release): v0.6.7 final - update README architecture

- Update Architecture section from v0.6.3 to v0.6.7
- Document new comparar/ module (SchemaComparator, SchemaDiff)
- Formalize 3-level import rules (level 1→2→3, no reversal)
- Add canonical imports table from root package
- Remove duplicate entries (tipología visual)
- Update version roadmap through v0.6.7

Refs: v0.6.7-closure-2026-04-10.md, INTEGRATION_MAP.md"

# 7. Create annotated tag
git tag -a v0.6.7 \
  -m "Release v0.6.7 - Architecture documentation, Comparador integrado, Agentes de Copilot"

# 8. Push a GitHub (branch + tag)
git push origin main
git push origin v0.6.7

# 9. Verify en GitHub
# Go to: https://github.com/fmanza/util_bbdd/releases
# Deberías ver: v0.6.7 como un "release" aquí
```

---

## 🟢 POST-RELEASE: GitHub Release Notes

### En GitHub UI:
1. Ve a: https://github.com/fmanza/util_bbdd/releases
2. Click "Draft a new release"
3. Select tag: v0.6.7
4. Title: `v0.6.7 — Architecture Consolidation & Comparator Integration`
5. Description: Usar template de abajo (o copiar de `.ai/GITHUB_RELEASE_PREPARATION_v0.6.7.md`)

### Release Notes (short version):

```markdown
# v0.6.7 — Architecture Consolidation & Comparator Integration

**Release Date**: April 13, 2026
**Status**: Production-ready
**Python**: 3.12+

## Highlights

### 🏗️ Architecture Documentation Update
- README now documents explicit 3-level hierarchy (Level 1 → 2 → 3)
- Import rules formalized with allowed/prohibited flows
- New `comparar/` module documented for SchemaComparator

### 🔍 Comparador de Esquemas (NEW)
- `SchemaComparator.compare(source, target)` for multi-motor schema comparison
- `SchemaDiff` typed output with full change detection
- Extensible architecture: add new motors without editing core code
- Supports: MariaDB, PostgreSQL, Oracle, SQLite, SQL Server

### 🤖 Copilot Integration & Offline Development
- 10 specialized agents (Plan Architect, Feature Implementer, etc.)
- Dual-platform workflow (Claude Code ↔ Copilot Chat)
- Offline-capable development documented
- `.claude/` command templates ready

### 📦 Quality Metrics
- 1703 tests PASSING
- 0 lint errors (ruff)
- 0 type errors (mypy)
- 100% CI/CD green

## Breaking Changes

Exception aliases removed (migrate to canonical names):
- `DatabaseConnectionError` → `ConnectionError`
- `DatabasePoolError` → `PoolConnectionError`
- `DatabaseError` → `DatabaseException`
- See CHANGELOG.md for complete mapping

## Installation

```bash
pip install util_bbdd==0.6.7
```

## Downloads

- [Source (tar.gz)](https://github.com/fmanza/util_bbdd/archive/v0.6.7.tar.gz)
- [Source (zip)](https://github.com/fmanza/util_bbdd/archive/v0.6.7.zip)

## Migration

See `docs/MIGRATION_GUIDE.md` for updates to canonical imports.

## Contributors

- Paco Manzano ([@fmanza](https://github.com/fmanza))
- Copilot Agents (Code Auditor, Documentation Reviewer, Version Closer)
```

---

## 🔵 DEVELOPMENT: Inicio v0.6.8-dev

```bash
# 10. Volver a develop
git checkout develop

# 11. Verificar que develop está actualizado
git status              # Debe ser limpio
git pull origin develop

# 12. v0.6.8-dev ya está inicializado:
#     - pyproject.toml versión: 0.6.8.dev0 ✅
#     - CHANGELOG.md: [0.6.8] section ✅
#     - .ai/sessions/2026-04-13-v0.6.8/ ✅

# 13. Próximo paso: Phase 4 L1 optimization
#     Archivo: src/util_bbdd/comparar/comparator.py:54
#     Cambio: r"\[(\w+)\]" → r"\[([^\]]+)\]"
#     Tests: Agregar casos parametrizados

echo "✅ v0.6.8-dev list ready for Phase 4 work"
```

---

## 📊 Verificación Rápida (Post-Release)

```bash
# Confirmar tag en GitHub
git ls-remote --tags origin | grep v0.6.7

# Confirmar que main tiene los cambios
git log main --oneline -5
# Debe mostrar el merge commit con "chore(release): v0.6.7"

# Confirmar que develop está limpio
git log develop --oneline -5
# Debe estar sincronizado con main
```

---

## 🚨 Troubleshooting Rápido

### Merge conflict?
```bash
# No debería suceder si develop es clean, pero si...
git merge --abort
git pull origin develop
git checkout main
git pull origin main
git merge develop --no-ff  # retry
```

### Tag ya existe?
```bash
# Si ves "tag 'v0.6.7' already exists" durante git tag...
git tag -d v0.6.7           # delete local
git push origin :refs/tags/v0.6.7  # delete remote (cuidado!)
# Then recreate...
```

### Push falla?
```bash
# Asegúrate de tener permisos en repo
git remote -v
# Debe ser: origin      git@github.com:fmanza/util_bbdd.git (push)

# Si no, actualizar:
# git remote set-url origin git@github.com:fmanza/util_bbdd.git
```

---

## ⏱️ Timeline Estimado

| Paso | Tiempo | Status |
|------|--------|--------|
| Pre-release validation | 2 min | ✅ Ready |
| Git merge & tag | 1 min | ✅ Ready |
| GitHub push | 1 min | ✅ Ready |
| GitHub Release UI | 3 min | ✅ Ready |
| **Total** | **~7 min** | ✅ Ready |

---

## 📋 Checklist Final

```
PRE-RELEASE:
☐ git status clean
☐ ruff check: 0 errors
☐ mypy: 0 errors
☐ pytest: 1703 PASS
☐ python -m build: SUCCESS

RELEASE:
☐ git checkout main
☐ git pull origin main
☐ git merge develop --no-ff [mensaje]
☐ git tag -a v0.6.7 [mensaje]
☐ git push origin main
☐ git push origin v0.6.7

POST-RELEASE:
☐ GitHub Release UI: create release notes
☐ Verify tag en GitHub releases page
☐ git checkout develop
☐ git pull origin develop

NEXT:
☐ pyproject.toml tiene version 0.6.8.dev0 ✅
☐ CHANGELOG.md tiene [0.6.8] section ✅
☐ .ai/sessions/2026-04-13-v0.6.8/ inicializado ✅
☐ Ready para Phase 4 L1/L2/L3 work
```

---

## 📞 Quick Links

- **Release Prep Guide**: `.ai/GITHUB_RELEASE_PREPARATION_v0.6.7.md`
- **Version Closure**: `.ai/sessions/v0.6.7-version-closure-2026-04-13.md`
- **v0.6.8 Plan**: `.ai/sessions/2026-04-13-v0.6.8/00_REQUEST.md`
- **Validation Report**: `.ai/RELEASE_VALIDATION_v0.6.7_FINAL.md`

---

**🎯 Status**: Ready to execute GitHub release in ~7 minutes
