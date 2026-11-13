# PLAN + AUDIT_PLAN — columna antes que tipo en los diagramas Mermaid

- Fecha: 2026-11-13 · Rama: `develop` (= `main` = `v5.7.0`, `62aba299`) · Flujo: `/new-feature` (MINOR)
- Petición: «Los diagramas en Mermaid de la base de datos documentada sale primero la columna el tipo y luego el
  Campo, se quiere al revés».

---

## Evidencia (verificada)

- Los diagramas de la documentación Markdown los genera `MermaidRelationshipGraph`
  (`src/util_bbdd/analysis/mermaid_er.py`, API pública de `util_bbdd.analysis` desde 5.3.0). Cada atributo se escribe
  en `_attribute()` (`mermaid_er.py:266-276`) como `tipo nombre [PK, FK, UK] ["nombre real"]`, la forma canónica de
  `erDiagram`.
- Mermaid dibuja los atributos **en el orden del texto** y no tiene opción para reordenar las columnas.
- Prueba con Mermaid 12.3.0 (el del sitio) en Chromium: `nombre tipo` se acepta sin error y dibuja `nombre | tipo |
  claves | comentario`. También con tipos con paréntesis o corchetes en segunda posición (`decimal(10_2)`,
  `timestamp[3]`, `character_varying(30)`), con prefijos `c_`/`t_`, con `PK/FK/UK` y con el comentario del nombre real.
  Motivo: los dos tokens comparten gramática, y `normalize_er_name` produce un subconjunto de lo que admite
  `normalize_er_type`.
- Graphviz (Word y HTML) ya pone **nombre y después tipo** (`graphviz_ext.py:365-373`): solo Mermaid va al revés.
- Dependencias: `tests/unit/test_analysis_mermaid_er.py` fija el texto (`INTEGER id PK`…); la portada Markdown tiene
  una leyenda (`_site_pages.py:22-32`) que no menciona el orden; `llms-full.txt` incluye las páginas con sus
  diagramas; util_bbdd_web solo comprueba que haya `erDiagram` (`test_documentation_markdown.py:107`).

---

## PLAN

### F1 — Orden de los atributos en `MermaidRelationshipGraph` · esfuerzo S

1. Nuevo parámetro `attribute_order: Literal["name_type", "type_name"] = "name_type"` en el constructor (D1, D2),
   validado como `column_mode` (`ValueError` si no es válido). Atributo público con el mismo nombre.
2. `_attribute()` escribe `nombre tipo` con `name_type` y `tipo nombre` con `type_name`; claves y comentario sin cambios.
3. El presupuesto de caracteres (`max_chars`) y la partición en bloques no cambian: misma longitud de línea.
4. Docstring de la clase y del método: el orden y por qué (consistencia con Graphviz; Mermaid no reordena).

### F2 — Documentación Markdown · esfuerzo S

1. `_pages.py` construye `MermaidRelationshipGraph` sin el parámetro: hereda `name_type` (D3: sin opción en `imprimir`).
2. Leyenda de la portada (`ER_LEGEND_ROWS`): nueva fila «Columnas de cada tabla: nombre, tipo, claves y, si se
   normalizó, el nombre real», para personas y para IA (el texto `erDiagram` deja de seguir la semántica tipo-nombre).

### F3 — Tests · esfuerzo S

1. `test_analysis_mermaid_er.py`: expectativas a `id INTEGER PK`…; caso nuevo con `attribute_order="type_name"` (texto
   antiguo, byte a byte) y valor inválido → `ValueError`.
2. Test de la leyenda y de una página de tabla generada con SQLite (orden `nombre tipo`).
3. `zensical build --strict` de una salida Markdown generada y prueba en Chromium con el Mermaid local (12.3.0) y con
   `mermaid@11` (lo que usan las vistas previas de GitHub y VS Code) — D4.

### F4 — Docs y VERSION 5.8.0 · esfuerzo S

1. `docs/api/analysis.md` (parámetro y orden), guía Markdown (§ diagramas), ejemplo si muestra el texto.
2. CHANGELOG `[5.8.0]` Changed + guía de migración de una línea (`attribute_order="type_name"`).
3. Gate: ruff, mypy, pytest local y en venv limpio `.[dev-full]`, `python -m build`; VERSION y publicación como en
   5.7.0 (push, `main`, tag, release con wheel) si el usuario lo pide.

---

## AUDIT_PLAN

| # | Riesgo | Mitigación | Severidad |
|---|---|---|---|
| R1 | El texto `erDiagram` deja de seguir la semántica de Mermaid (primer token = tipo): una herramienta o IA que interprete el texto tomaría el nombre por el tipo (está en `llms-full.txt`) | Fila nueva en la leyenda; los datos exactos de cada columna siguen en el front matter y en `catalog.json`; `attribute_order="type_name"` para quien necesite la forma canónica | Media |
| R2 | Otra versión de Mermaid (vistas previas de GitHub/VS Code con la 11, web con la 12.2.0) que no lo acepte | Verificado con 12.3.0; F3.3 lo prueba con `mermaid@11`. Si la 11 lo rechazara: NO_GO de F2 por defecto (solo la opción) | Media |
| R3 | Cambio visible en la salida de una clase pública (`util_bbdd.analysis`) | MINOR (5.8.0) con parámetro para volver al orden anterior; CHANGELOG con la migración | Baja |
| R4 | Regenerar una documentación versionada con git cambia todas las páginas con diagramas (diff de una vez) | Documentado en el CHANGELOG; `changes.md` no se ve afectado (compara `catalog.json`, no diagramas) | Baja |
| R5 | El hash del front matter cambiara y `changes.md` marcara todo como modificado | Comprobar que el hash no incluye los diagramas (se calcula sobre la estructura del objeto) | Baja |
| R6 | util_bbdd_web | Solo comprueba `erDiagram`; su visor dibuja con su Mermaid 12.2.0 (cubierto por R2) | Baja |

**Criterio de salida**: tests nuevos y existentes en verde, render correcto en Mermaid 11 y 12, `zensical build
--strict` sin incidencias y la leyenda presente en la portada.

**Rollback**: revertir el commit; quien ya tenga 5.8.0 vuelve al orden anterior con `attribute_order="type_name"`.

### Decisiones del usuario

- **D1**: `nombre tipo` por defecto en `MermaidRelationshipGraph` (recomendado: mismo orden que Graphviz y que pide el
  usuario) **o** mantener `tipo nombre` por defecto en la clase y aplicar `nombre tipo` solo en la documentación
  Markdown.
- **D2**: parámetro para conservar el orden anterior (`attribute_order="type_name"`) — recomendado: sí.
- **D3**: opción también en `imprimir["markdown"]` — recomendado: no (siempre `nombre tipo`; menos superficie).
- **D4**: exigir la prueba con `mermaid@11` antes de cambiar el valor por defecto — recomendado: sí.

Veredicto AUDIT_PLAN: **GO_CONDICIONAL** — sujeto a D1–D4 y a la prueba con `mermaid@11` (R2).
