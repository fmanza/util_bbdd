# 🚀 Zenical Migration Roadmap — Transición a zensical v0.0.44+

**Status**: 📋 Planned  
**Target Release**: v0.11.0 (post-v0.10.0)  
**Priority**: Medium (performance optimization)

---

## 📊 Ejecutivo

Migración de **MkDocs Material 9.5 → Zenical v0.0.44+** para ganar **+80% performance** en builds de documentación (300ms → 80ms).

| Métrica | MkDocs | Zenical | Ganancia |
|---------|--------|---------|----------|
| **Build time** | 300ms | 80ms | -73% ⚡ |
| **Page load** | 400ms | 100ms | -75% ⚡ |
| **Toolchain** | Python | Rust | Simplificación |

**Status Actual**: ✅ Planificación completa, configuración lista en `zensical.toml`, **Bloqueado en**: Zenical v0.0.44 aún no publicado en crates.io.

---

## 🔄 Fases de Migración

### **FASE 1: Esperar disponibilidad (2026-Q3)**
- ⏳ Zenical v0.0.44 publicación en crates.io o binarios precompilados
- Monitorear: https://github.com/squidfunk/zensical/releases
- Alternativa: usar binarios precompilados si crates.io sigue sin actualizar

**Acción**: Establecer alerta en repo (watch releases)

### **FASE 2: Validación local (1-2 horas)**
Una vez Zenical esté disponible:
```bash
# Instalación
cargo install zensical --version 0.0.44
# o descargar binario: https://github.com/squidfunk/zensical/releases

# Build con zensical.toml actual
zensical build

# Validar site/ idéntico a MkDocs
diff site/ site-mkdocs/
```

**Entrada**: `zensical.toml` (ya creado, 634 líneas)  
**Salida**: `site/` con +80% performance

### **FASE 3: CI/CD actualización (30 min)**
`.github/workflows/docs.yml` ya está actualizado en rama `migrate/zenical-pure`:
- Build: `mkdocs build` → `zensical build` ✅
- Deploy: `mkdocs gh-deploy` → `peaceiris/actions-gh-pages` ✅
- Paths: `mkdocs.yml` → `zensical.toml` ✅

**Entrada**: rama `migrate/zenical-pure` (5 commits, 4,950 LOC added)  
**Acción**: Merge a `develop` cuando Zenical esté disponible

### **FASE 4: Documentación actualización (1 hora)**
- `ZENICAL.md` ya existe con guía completa
- Actualizar `.github/copilot-instructions.md` y `CLAUDE.md` (ya hecho)
- CHANGELOG.md entrada v0.11.0

---

## 📦 Artefactos Completados

| Artefacto | Ubicación | Estado | Líneas |
|-----------|-----------|--------|--------|
| **Configuración Zenical** | `zensical.toml` | ✅ Listo | 634 |
| **CI/CD workflow** | `.github/workflows/docs.yml` | ✅ Listo | 80 |
| **IA Instructions** | `.github/copilot-instructions.md` | ✅ Actualizado | +7 refs |
| **IA Instructions** | `CLAUDE.md` | ✅ Actualizado | +2 refs |
| **Guía técnica** | `ZENICAL.md` | ✅ Completo | 450+ |
| **Plan** | `PLAN_MIGRATION_ZENICAL_PURE.md` | ✅ Doc histórico | 797 |
| **Decisiones** | `.ai/sessions/.../TRACEABILITY.md` | ✅ Archivado | 386 |
| **pyproject.toml** | `pyproject.toml` | ✅ Ready | -2 deps |

---

## ⏱️ Timeline

```
2026-06-04  ← Hoy: Planificación completa, Zenical aún no disponible
     ↓
2026-Q3     ← Esperar Zenical v0.0.44+ publicación
     ↓
<1 día      ← Validación local + merge (cuando Zenical esté disponible)
     ↓
v0.11.0     ← Release: +80% perf en CI/CD
```

---

## 🚫 Blockers

**Critical**: Zenical v0.0.44 **no está publicado en crates.io aún**
- Actual en crates.io: v0.0.3 (placeholder, no compilable)
- GitHub releases: No hay v0.0.44 publicado
- Solución: Esperar publicación oficial o usar binarios precompilados cuando estén disponibles

**Workaround**: Mantener MkDocs Material hasta que Zenical sea estable.

---

## 📝 Referencias

- Rama feature: `migrate/zenical-pure` (5 commits, listo para merge)
- Zenical repo: https://github.com/squidfunk/zensical
- PR bloqueada: #19 (abierta, esperando Zenical disponible)
- Guía IA: [ZENICAL.md](../ZENICAL.md)

---

## ✅ Checklist para Futuras IAs

When Zenical v0.0.44 becomes available:

- [ ] Verificar que `cargo install zensical --version 0.0.44` funciona
- [ ] Ejecutar `zensical build` desde repo root (usar `zensical.toml`)
- [ ] Validar que `site/` se genera idéntico a MkDocs
- [ ] Checkout rama `migrate/zenical-pure` y hacer merge a `develop`
- [ ] Ejecutar suite de tests (CI/CD jobs deben pasar)
- [ ] Medir build time real (validar ~80ms)
- [ ] Update `.github/SHARED_INSTRUCTIONS.md` con Zenical como "current"
- [ ] Crear CHANGELOG.md entry v0.11.0 con "✨ Performance: +80% doc builds (Zenical)"
- [ ] Cerrar PR #19
- [ ] Tag `v0.11.0` y push

---

*Document Type*: Roadmap (Strategic planning)  
*Status*: 🟠 Blocked on external dependency (Zenical availability)  
*Last Updated*: 2026-06-04  
*Owner*: Development Team
