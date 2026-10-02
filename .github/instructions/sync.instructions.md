---
applyTo: "CHANGELOG.md,docs/**,.ai/**"
---
# Sincronización de versiones — CHANGELOG, pyproject y documentación

> **TL;DR** — Antes de cerrar una versión, verifica que CHANGELOG.md, `pyproject.toml` y docs/
> estén sincronizados. Ejecuta `zensical build` (o `mkdocs build`) sin errores.

---

## Cuándo aplicar estas reglas

Aplica este checklist en la fase **VERSION** de cualquier flujo:

- `feat:` que añade API pública nueva
- `fix:`, `hotfix:` o `security:` que cambian comportamiento observable
- `perf:` con cambio medible de rendimiento o de opciones por defecto
- `refactor:` con renombramiento de símbolos exportados
- Cierre de sprint o release (slash command `/version-closure`)

---

## Checklist de sincronización obligatorio

### 1. CHANGELOG.md (raíz del repositorio)

- [ ] La versión nueva tiene entrada bajo `## [X.Y.Z] — YYYY-MM-DD`
- [ ] Secciones presentes según cambios: `Added`, `Changed`, `Fixed`, `Removed`, `Deprecated`
- [ ] Cada ítem referencia el módulo afectado: `bulk/`, `dump/`, `metadata/`, `migrate/`
- [ ] No hay entradas bajo `Unreleased` que deban estar en la versión cerrada

### 2. docs/CHANGELOG.md (si existe copia en docs/)

- [ ] Contenido idéntico al CHANGELOG.md raíz
- [ ] Si hay divergencia, prevalece el CHANGELOG.md raíz; actualiza docs/CHANGELOG.md

### 3. Matriz de compatibilidad (solo si existe)

Hoy el repo **no** tiene `COMPATIBILITY.md`; la compatibilidad se declara en `pyproject.toml` y en
`CHANGELOG.md`. Si se crea una matriz, cada versión nueva lleva las columnas
`Versión | Python | Dependencias clave | Estado` y se marca `✅ Activa` / `⚠️ Legacy` / `❌ EOL`.

### 4. Campos de versión (pyproject.toml y textos que la muestran)

Lista cerrada de lo que cambia con el número de versión; es lo único fuera de `CHANGELOG.md` y del `TRACEABILITY.md`
que puede editar **Version Closer** (`.github/agents/version-closer.agent.md`):

- [ ] `pyproject.toml`: `version = "X.Y.Z"`, igual que la última versión del CHANGELOG.md
- [ ] `README.md`: `**Version:** X.Y.Z` (cabecera) y `**Current Version: vX.Y.Z** (<resumen>)`
- [ ] `docs/index.md`: `**Version:** X.Y.Z`
- [ ] `docs/roadmap.md`: `**Versión vigente: vX.Y.Z.**`
- [ ] `docs/architecture.md`: pie de figura «Instantánea de `develop` en vX.Y.Z (fecha) … sobre N ficheros»
      (N lo da `python scripts/gen_arquitectura_capas.py`)
- [ ] `.ai/CURRENT_STATE.md`: fila de la versión, «Tests actuales» y «Próximos pasos»
- [ ] `.ai/sessions/SESSIONS_DIGEST.md`: fila de las sesiones de la versión
- [ ] `requires-python = ">=3.12"` sin modificar (no incrementar sin decisión explícita)

`tests/unit/test_docs_version.py` comprueba que coinciden con `pyproject.toml` el CHANGELOG (última versión publicada),
`README.md` (los dos), `docs/index.md`, `docs/roadmap.md` y el pie de figura de `docs/architecture.md`. Los dos
ficheros de `.ai/` no los comprueba: revísalos a mano.

### 5. Documentación (Zensical / MkDocs)

- [ ] `zensical build` (o `mkdocs build`) pasa sin errores ni warnings de links rotos
- [ ] Si se crearon páginas nuevas, están en `mkdocs.yml` bajo `nav:`
- [ ] Si se eliminaron páginas, se retiraron de `mkdocs.yml`

---

## Formato de entrada CHANGELOG

```markdown
## [0.8.2] — 2026-05-14

### Added
- `dump/`: nuevo formato de salida Parquet en el volcado masivo

### Fixed
- `bulk/`: corregido el literal de columnas binarias en el SQL generado

### Changed
- `metadata/`: la caché de metadatos se invalida al cambiar de esquema
```

---

## Reglas de versionado (SemVer)

| Tipo de cambio | Incremento |
|---|---|
| API pública nueva sin breaking changes | `MINOR` (0.X.0) |
| Breaking change en API pública | `MAJOR` (X.0.0) |
| Bugfix sin cambio de API | `PATCH` (0.0.X) |
| Cambio solo en docs o tests | `PATCH` (0.0.X) |

---

### 6. `.ai/sessions/*/TRACEABILITY.md` (cierre de sesión)

- [ ] Sección `## Directrices para Futuras IAs` presente y poblada (no vacía, no solo `-`)
- [ ] Cada directriz tiene el formato `**[área]**: <hecho verificable>`
- [ ] Veredicto final es `CLOSED` (o `GO` / `GO_CONDICIONAL` si la sesión queda abierta)

---

## Comando de validación final

```bash
zensical build --strict    # o: python -m mkdocs build --strict
```

El flag `--strict` convierte warnings en errores, garantizando que no queden links rotos
ni referencias a páginas inexistentes en `mkdocs.yml`.

---

*Actualizado: 2026-10-02*
