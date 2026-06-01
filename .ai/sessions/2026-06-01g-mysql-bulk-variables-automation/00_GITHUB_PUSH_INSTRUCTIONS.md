# Instrucciones de GitHub Push — Sesión 2026-06-01g

## 📋 Resumen Ejecutivo

**PR #18** está **abierta y lista** esperando review de mantainers.

El código está completamente implementado, validado (lint ✅, type-check ✅, pytest ✅) y documentado.

---

## 🔧 Pasos para Sincronizar y Enviar

### 1. Verificar estado local

```bash
# Ver rama activa
git branch -v

# Ver commits no enviados
git log --oneline origin/develop..HEAD

# Mostrar estado del árbol
git status
```

**Esperado**: Rama `develop`, archivos limpios o cambios en `.ai/sessions/` únicamente

### 2. Actualizar rama develop desde origin

```bash
git fetch origin develop
git merge --ff-only origin/develop
```

**Alternativa** (si hay divergencia):
```bash
git rebase origin/develop
```

### 3. Verificar PR #18 en GitHub

```bash
# Ver estado del PR (requiere GitHub CLI)
gh pr view 18

# Abrir en navegador
gh pr view 18 --web
```

**Esperado**:
- Estado: OPEN
- Base branch: main
- Head branch: develop
- Checks: Todos verdes (CI/CD, lint, type-check, tests)

### 4. Hacer commit de cambios de sesión (si es necesario)

Si hay cambios nuevos en `.ai/sessions/`:

```bash
git add .ai/sessions/2026-06-01g-mysql-bulk-variables-automation/

git commit -m "docs(.ai): TRACEABILITY + COMMIT_MESSAGE + RESUMEN_FINAL para sesión MySQL variables automation"
```

### 5. Push a develop

```bash
git push origin develop

# Verificar
git log --oneline -3 origin/develop..HEAD  # Debe estar vacío
```

---

## 🔍 Verificar PR en GitHub

### Vía GitHub CLI

```bash
gh pr view 18

# Mostrar cambios del PR
gh pr diff 18

# Listar reviewers
gh pr view 18 --json reviewers
```

### Vía Navegador

Visita: https://github.com/fmanza/util_bbdd/pull/18

Verificar:
- [ ] PR #18 abierta en `develop` → `main`
- [ ] Título: `feat(connection/bulk): automatización de variables MySQL/MariaDB para bulk operations`
- [ ] Descripción con cambios principales
- [ ] Checks: Todos pasando (tick verde)
- [ ] No hay conflictos con main
- [ ] Reviewers asignados (si es necesario)

---

## ⏳ Esperando Review

### Si el reviewer solicita cambios

1. Hacer cambios locales
2. Commit con prefijo: `fix(review): <descripción>` o `refactor(pr-feedback): <descripción>`
3. Push a develop
4. El PR se actualiza automáticamente

### Si hay conflictos con main

```bash
git fetch origin main
git rebase origin/main

# Si hay conflictos, resolverlos en editor
git add .
git rebase --continue

git push origin develop --force-with-lease
```

### Si necesitas forzar actualización de PR

```bash
# Rebase a main
git rebase origin/main

# Push forzado (seguro)
git push origin develop --force-with-lease
```

---

## ✅ Checklist Pre-Merge

Antes de que el maintainer mergee, verificar:

- [ ] **Código**
  - [ ] Lint pasando (ruff)
  - [ ] Type-check pasando (mypy)
  - [ ] Tests pasando (pytest 3728+)
  - [ ] No hay breaking changes

- [ ] **Documentación**
  - [ ] CHANGELOG.md actualizado (sección "Added")
  - [ ] Docstrings 100% completos
  - [ ] README actualizado (si aplica)

- [ ] **GitHub**
  - [ ] Commits con Conventional Commits format
  - [ ] Descripción del PR completa
  - [ ] No hay conflictos
  - [ ] Todos los checks verdes

- [ ] **Quality**
  - [ ] Backward compatibility 100%
  - [ ] Permisos/seguridad validados
  - [ ] No hay hard-coded valores de prueba

---

## 🚀 Post-Merge (Después del Merge a Main)

Una vez que el maintainer mergee PR #18 a main:

### 1. Actualizar rama develop

```bash
git fetch origin main
git merge origin/main

git push origin develop
```

### 2. Crear tag de versión

```bash
git tag -a v0.10.0 -m "feat(connection/bulk): automatización de variables MySQL/MariaDB para bulk operations"

git push origin v0.10.0
```

### 3. Actualizar versión en pyproject.toml (opcional, si no se hizo automáticamente)

```bash
# En pyproject.toml, actualizar:
# version = "0.10.0"

git add pyproject.toml
git commit -m "chore: bump version to 0.10.0"
git push origin develop
```

### 4. Crear release en GitHub

```bash
gh release create v0.10.0 --notes-file CHANGELOG.md

# O vía navegador:
# https://github.com/fmanza/util_bbdd/releases/new
```

### 5. Publicar en PyPI (si aplica)

```bash
python -m build
python -m twine upload dist/*
```

---

## 📞 Soporte

Si surgen problemas durante push/merge:

1. **Verificar logs**: `git log --oneline -10`
2. **Revisar diff**: `git diff origin/develop..HEAD`
3. **Revisar tests**: `pytest` (ejecutar localmente)
4. **Revisar linting**: `ruff check src tests`
5. **Contactar maintainer** si persiste el problema

---

## 🔗 Referencias Rápidas

| Recurso | URL |
|---|---|
| **PR #18** | https://github.com/fmanza/util_bbdd/pull/18 |
| **Commits** | https://github.com/fmanza/util_bbdd/commits/develop |
| **Issues** | https://github.com/fmanza/util_bbdd/issues |
| **CHANGELOG** | https://github.com/fmanza/util_bbdd/blob/develop/CHANGELOG.md |
| **Releases** | https://github.com/fmanza/util_bbdd/releases |

---

## 💡 Notas Importantes

1. **PR está abierta**: No es necesario crear una nueva PR
2. **Cambios de código ya están en develop**: Solo documentación de sesión pendiente
3. **Backward compatible**: 0 breaking changes, safe to merge
4. **Validaciones verdes**: Lint ✅, type-check ✅, pytest ✅

**Próximo paso**: Esperar review + aprobación del maintainer para merge a main.

---

**Estado**: 🟢 Ready for Review
**Última actualización**: 2026-06-02
**PR**: #18 (OPEN)
