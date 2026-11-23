# TRACEABILITY

## Session metadata
- id: 2026-11-23-docs-al-dia-guias
- fecha: 2026-11-23
- rama: develop
- skill: documentation + version_closure
- fase: /doc-generator (inventario → funcional → técnica → guías → ejemplos → `zensical.toml` → revisión) + VERSION

## Prompt issued
1. «.github\agents\documentation-generator.agent.md, revisa el proyecto y actualiza toda la documentación» (`/doc-generator`, proyecto completo).
2. «corrige también el agente para que use docs/guides».
3. «sube mkdocstrings a >=1.0.8 y añade progress a .ai/architecture.md».
4. «lanzar zensical build --strict y luego haz commit de todo» · «haz push».
5. `/version-closure` sin inputs: supuestos declarados → versión **v5.9.1** (PATCH), esta sesión, cambios = `220f8c56` + `981c1261`.

## Context supplied
- `.github/agents/documentation-generator.agent.md`, `.github/DOCUMENTATION_STANDARD.md` (§3.3, §3.7, §3.9, §5)
- `CHANGELOG.md` (5.5.0–5.9.0), `zensical.toml`, `docs/`, `src/util_bbdd/metadata/table_filter.py`,
  `src/util_bbdd/migrate/planner.py`, `src/util_bbdd/dump/_models.py`, `scripts/gen_arquitectura_capas.py`
- `.github/agents/version-closer.agent.md`, `.github/prompts/version_closure.prompt.md`, `.github/instructions/sync.instructions.md`

## AI output summary
- Inventario: `nav` de `zensical.toml` sin huérfanos ni rotos; contraste por símbolos del CHANGELOG 5.5–5.9 con `docs/`.
- `zensical` no estaba en el venv: instalado el extra `docs`; el build falló con `TypeError: Highlight.__init__()
  missing 1 required positional argument: 'md'` (`mkdocstrings` 1.0.4 + `pymdown-extensions` 13.1.2). Con
  `mkdocstrings` 1.0.8, `zensical build --strict` sin incidencias.
- Agente Documentation Generator: tipo «3. Guías (`docs/guides/`)», Fase 3b, prompts `guide_doc`/`onboarding_dev`/
  `example_doc`, técnica solo en `docs/api/`; sincronizados `.claude/commands/doc-generator.md`, `.github/AGENTS.md`,
  `DOCUMENTATION_STANDARD.md` §5.
- Docs: 5 × `docs/api/migrate_*.md` (`table_filter`, `table_filter`/`frontier`, `outside_filter`, `FK_OUTSIDE_FILTER`),
  8 páginas funcionales, `docs/examples/dump_data_export.md`, `docs/guides/onboarding_dev.md`, `docs/guides/troubleshooting.md`.
- `pyproject.toml`: `mkdocstrings[python]>=1.0.8`; `.ai/architecture.md`: `progress/` en la capa 2.
- Commit `220f8c56` (docs) y push a `origin/develop`.
- VERSION: `CHANGELOG.md` `[5.9.1]`; campos de `sync.instructions.md` § 4 a 5.9.1 (pyproject, README ×2, `docs/index.md`,
  `docs/roadmap.md`, pie de `docs/architecture.md`, `.ai/CURRENT_STATE.md`, `SESSIONS_DIGEST.md`, `INDEX.md`) y las 19
  URL de instalación `@v5.9.0` → `@v5.9.1` (como en los cierres anteriores).

## Artefactos generados
| Artefacto | Ruta | Estado |
|---|---|---|
| Agente actualizado | `.github/agents/documentation-generator.agent.md` | completado |
| Documentación | `docs/api/`, `docs/functional/`, `docs/examples/`, `docs/guides/` | completado (`220f8c56`) |
| Cierre de versión | `CHANGELOG.md` `[5.9.1]` + campos de versión | completado |
| Logs | `build/logs/zensical_build.txt`, `build/logs/v5.9.1_*.txt` | generados |

## Tests y evidencias
Ejecutado en Windows, Python 3.14, venv local, el 2026-11-23 (logs en `build/logs/v5.9.1_*.txt`):
- `ruff check src tests` y `ruff format --check src tests`: limpios.
- `mypy src tests/unit/test_protocol_conformance.py`: sin errores (376 ficheros), tras instalar `types-PyMySQL` (del
  extra `dev`), que faltaba en el venv; antes, 5 errores `import-untyped` de `pymysql` por entorno.
- `pytest`: 7067 passed, 606 skipped, 0 failed. **No comparable** con 5.9.0 (7193/619): faltan en el venv `sqlglot`,
  `psycopg2-binary` y `types-openpyxl` del extra `dev` (aviso de `tests/conftest.py`) y se saltan módulos enteros.
- `tests/unit/test_docs_version.py` repetido tras cambiar los campos de versión: 6 passed.
- `zensical build --strict`: sin incidencias.
- `python -m build` e integración con el banco: no ejecutados.

## Directrices para Futuras IAs
- **[docs/build]**: `mkdocstrings` 1.0.4 no funciona con `pymdown-extensions` 13 (`Highlight.__init__() missing ... 'md'`
  al renderizar cualquier página `:::`); el extra `docs` exige `>=1.0.8`. Si `zensical build` cae con una traza de
  `mkdocstrings/_internal/handlers/rendering.py`, actualizar mkdocstrings antes de tocar `docs/`.
- **[docs/build]**: los avisos «page does not exist» hacia `*_autodoc.md` que preceden a una excepción de mkdocstrings son
  consecuencia del fallo de autodoc, no enlaces rotos reales.
- **[docs/inventario]**: para un «actualiza toda la documentación», contrastar los símbolos del CHANGELOG desde la
  última revisión con `grep -rl <símbolo> docs README.md` localiza las páginas desfasadas; las releases ya actualizan
  guías y versiones, lo que suele faltar son las páginas funcionales y las de API por motor (`docs/api/migrate_*.md`).
- **[docs/migrate]**: la firma de `MigrationPlanner.plan` está repetida en las 5 páginas `docs/api/migrate_*.md` (una por
  motor origen); cualquier cambio del planner hay que llevarlo a las cinco.
- **[agentes]**: el agente Documentation Generator cubre ya `docs/guides/` (tipo 3 y Fase 3b); la técnica va solo en
  `docs/api/`, nunca en la raíz de `docs/`.
- **[arquitectura]**: `progress/` es capa 2 (Level 1) en `LAYER` de `scripts/gen_arquitectura_capas.py`; la copia manual de
  `.ai/architecture.md` § Capas no lo listaba hasta esta sesión.
- **[versión]**: además de los campos de `sync.instructions.md` § 4, cada cierre cambia las URL `util_bbdd.git@vX.Y.Z` de
  README y `docs/` (excluido `docs/v0*`); no reemplazar `X.Y.Z` a secas, porque las anotaciones «(5.9.0)» de las
  funcionalidades deben quedarse.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit de cierre, tag `v5.9.1` y push de `develop` + tag: ejecutados a petición del usuario. Sin hacer: merge a `main`,
  release en GitHub y tag `docs-v5.9.1` (ZIP offline).
- `util_bbdd.egg-info/requires.txt` desfasado (`mkdocstrings>=0.25`): se regenera con `pip install -e .` / `python -m build`.
