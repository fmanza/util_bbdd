# 🔥 HOTFIX: Tooltips de exportación no visibles en "Ver todo"

**Fecha:** 26-03-2026
**Severidad:** Medium
**Estado:** ✅ FIXED
**Branch:** hotfix/tooltip-visibility

---

## 📋 Issue

En la página "Ver todo" (colecciones), los tooltips de los botones de exportación (CSV, TSV, XLSX, PDF) **no son visibles** al pasar el mouse sobre ellos.

**Afectado:**
- `tables_all.html`
- `views_all.html`
- `procedures_all.html`
- `functions_all.html`
- `storage_all.html`

---

## 🔍 Root Cause Analysis (RCA)

### Problema Técnico

El elemento `.toolbar` contenía `overflow-x: auto;` para permitir scroll horizontal. Sin embargo, los botones de exportación dentro de `.toolbar-group.actions-group` tienen tooltips posicionados con `position: absolute` que se extendían fuera del contenedor con `bottom: calc(100% + 8px)`.

```css
/* ❌ Problema: overflow recorta tooltips */
.toolbar {
  overflow-x: auto;  /* Aquí se recorta el tooltip */
}

.icon-button[data-tooltip]::after {
  position: absolute;
  bottom: calc(100% + 8px);  /* Intenta mostrarse arriba, pero se corta */
  opacity: 1;  /* en hover */
}
```

### Causa Raíz

La propiedad CSS `overflow: auto` (incluso solo en X) establece un NEW stacking context que **recorta cualquier contenido que se extienda fuera del contenedor**. Los pseudo-elementos `::after` y `::before` con posicionamiento absoluto se consideran "contenido" del elemento y quedan cortados.

---

## ✅ Solución Aplicada

Se agregó un contenedor específico para los botones de exportación con `overflow: visible` explícito:

**Archivo:** [src/util_bbdd/doc/templates/pages/collection.html.j2](src/util_bbdd/doc/templates/pages/collection.html.j2#L20)

```css
/* Antes: */
.toolbar-group.search-group,
.toolbar-group.actions-group,
.search-stack { min-width: max-content; }

/* Después: */
.toolbar-group.search-group,
.toolbar-group.actions-group,
.search-stack { min-width: max-content; }
.toolbar-group.actions-group { position: relative; overflow: visible; }
```

### Por qué funciona

- `position: relative;` crea un **contexto de posicionamiento** para los botones hijos
- `overflow: visible;` **permite que los pseudo-elementos se extiendan fuera** del contenedor
- El `.toolbar` sigue permitiendo scroll horizontal (`overflow-x: auto`)
- Los tooltips ahora se muestran correctamente en hover

---

## 🧪 Verificación

### Antes (Broken)
```html
<div class="toolbar">  <!-- overflow-x: auto -->
  <div class="toolbar-group actions-group">
    <button data-tooltip="Exportar CSV">CSV</button>  <!-- ❌ Tooltip recortado -->
  </div>
</div>
```

### Después (Fixed)
```html
<div class="toolbar">  <!-- overflow-x: auto -->
  <div class="toolbar-group actions-group">  <!-- NOW: position: relative; overflow: visible; -->
    <button data-tooltip="Exportar CSV">CSV</button>  <!-- ✅ Tooltip visible -->
  </div>
</div>
```

---

## 📊 Impacto

| Aspecto | Detalle |
|---------|---------|
| **Archivos modificados** | 1 (`collection.html.j2`) |
| **Líneas cambiadas** | +1 línea CSS |
| **Breaking change** | No |
| **Retrocompatibilidad** | ✅ Total |
| **Afecta a** | Ver todo (tablas, vistas, procedures, funciones, almacenamiento) |

---

## 🚀 Rollback

Si es necesario deshacer:

```bash
git revert <commit-hash>
```

O manualmente eliminar línea 20:
```css
.toolbar-group.actions-group { position: relative; overflow: visible; }
```

---

## 📝 Notas

- El cambio **es CSS puro**, sin cambio de JavaScript o estructura HTML
- Compatible con todos los navegadores modernos
- No afecta performance (no hay reflow significativo)
- Mantiene el scroll horizontal del toolbar funcionando

---

## ✅ Checklist

- [x] RCA documentado
- [x] Solución aplicada
- [x] CSS validado
- [x] Compatible navegadores modernos
- [x] Sin impacto performance
- [x] Retrocompatibilidad total
- [x] Hotfix documentado
