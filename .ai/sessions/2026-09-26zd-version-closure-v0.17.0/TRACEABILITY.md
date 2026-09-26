# TRACEABILITY

## Session metadata
- id: 2026-09-26zd-version-closure-v0.17.0
- fecha: 2026-09-26
- rama: develop
- skill: version-closure
- origen: el usuario pidió cerrar como v0.17.0 los cambios posteriores a v0.16.1

## Versión
- **v0.17.0** (MINOR): parámetro nuevo y opcional `reflect_foreign_keys` en `BulkCrud` y `ParallelBulkLoader`. No
  rompe la API: con el valor por defecto nada cambia.

## Contenido (sobre v0.16.1)
- `3a3bc17` Q8 medido y aparcado: la ruta sin pandas ganaría como mucho ≈ 2 s por 3,5M filas.
- `d2729f8` Q9: en SQL Server, las FK de todo el esquema en una consulta para el orden de carga y la limpieza del
  volcado. El SQL va en `metadata/sqlserver`.
- `53c63ea` Q9b: `reflect_foreign_keys=False` en las `BulkCrud` y el `ParallelBulkLoader` de `dump`.
- `966add7` 3.3: hipótesis `APPEND_VALUES` de Oracle medida y descartada.
- `53e29da` (usuario) prompts y guías de auditoría de rendimiento de la desactivación de constraints.
- `06779c1` enlaces relativos de `docs/CONSTRAINTS_AUDIT_INDEX.md`. Rompían `tests/unit/test_docs_links.py`; se
  corrigieron con autorización del usuario.

## Checklist (`.github/instructions/sync.instructions.md`)
- [x] `ruff check` y `ruff format --check`: limpios.
- [x] `mypy src tests/unit/test_protocol_conformance.py`: sin errores.
- [x] `pytest` sin URLs de servidor: **5079 passed / 199 skipped**. Los 6 saltos nuevos son los tests de integración
  nuevos sin servidor.
- [x] `pytest tests/integration` con las URLs del banco (5 servidores): **338 passed**.
- [x] `python -m build`: `util_bbdd-0.17.0`.
- [x] `pyproject.toml` → `0.17.0`. `CHANGELOG.md`: `[0.17.0] - 2026-09-26` con introducción y secciones *Added*,
  *Changed* y *Fixed*; `[Unreleased]` vacío.
- [x] `mkdocs build --strict`: sin errores.

## Commits y push
- `df94154` `release: v0.17.0 - …` y tag anotado `v0.17.0`; después, este `docs(ai)`.
- Push de `develop` y del tag `v0.17.0` a `origin`; `main` no se toca. El remoto no había divergido antes del push
  (`3d4e52d`).
- **Push verificado**: `origin/develop` `3d4e52d..0441617`; `git ls-remote --tags origin v0.17.0` → `696514f` (objeto
  del tag anotado sobre `df94154`).

## Rollback
- Quitar el tag remoto si nadie lo ha consumido: `git push origin :refs/tags/v0.17.0`.
- Revertir el release: `git revert df94154`.
- Cada mejora tiene su propio commit: `d2729f8` y `53c63ea` se revierten por separado.

## Pendientes al cierre
- Roadmap de rendimiento de `dump`: Fases 0–3 cerradas (hechas, aparcadas o descartadas).
- Banco: con el lector en paralelo, el desglose por fases solapa `read` y `write`; solo el total es fiable.
- Guías de constraints del usuario: no siguen la convención de `docs/` (nombres en mayúsculas, fuera de `docs/guides/`),
  no están en la navegación de `mkdocs.yml` ni en `.github/AGENTS.md`.
- Contenedores del banco en marcha: origen `large` cargado, destino Oracle vacío.

## Directrices para Futuras IAs
- **[git]**: no uses `git add -A` en este repositorio. El usuario crea ficheros en paralelo; añade solo las rutas
  propias de la sesión. En esta sesión se coló una vez y se deshizo con `git reset --soft` antes del push.
- **[docs]**: `tests/unit/test_docs_links.py` solo admite enlaces a páginas de `docs/`. Las rutas de `.github/` se citan
  como código, sin enlace.

## Veredicto final
Veredicto: CLOSED
