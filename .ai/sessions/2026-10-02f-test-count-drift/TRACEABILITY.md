# TRACEABILITY

## Session metadata
- id: 2026-10-02f-test-count-drift
- fecha: 2026-10-02
- rama: develop
- skill: investigación + fix de entorno y tipado (aprobado por el usuario)
- fase: investigación + IMPLEMENT (commit propuesto)

## Prompt issued
«Investiga la diferencia de test» (537 tests de integración frente a 582 en el cierre de v0.28.0). Después: «si,
pregunta lo necesario» → corregir registros; instalar `pip install -e ".[dev,docs]"`; declarar `types-openpyxl` y
corregir; aviso en `tests/conftest.py`; declarar `psycopg2-binary` en `dev`.

## Context supplied
- Trazabilidades de `2026-10-02b-fix-audit-isolate` (cierre v0.28.0: 5993 passed, 436 skipped; 582 de integración;
  mypy limpio con 391 ficheros) y de las sesiones `2026-10-02c/d/e`.
- Worktree temporal de `v0.28.0` y venv temporal (scratchpad), sin tocar el entorno global durante la medición.

## Investigación (evidencia)

| Medición | Sin dependencias opcionales | Con `sqlglot` + `psycopg2` |
|---|---|---|
| v0.28.0, recogidos | 6287 | **6429** (= 5993 + 436 del cierre) |
| v0.28.0, `tests/integration` | 536 | **582** (= cierre) |
| HEAD, recogidos | 6395 | 6537 (6429 + 108 de esta jornada) |
| HEAD, `pytest` completo | 5973 passed, 422 skipped | 6101 passed, 436 skipped |

- Causa: el entorno de Python no tenía `sqlglot` (extras `dev` y `migrate`) ni `psycopg2` (no declarado): 9 módulos
  (`importorskip("sqlglot")`) y 3 (`psycopg2`) se saltan enteros al importarse y cuentan **un** salto cada uno; 20 tests
  más se saltan por `psycopg2`. `tests/integration/test_migrate_views_e2e.py` son 46 de los 582.
- mypy: de los «12 errores previos», 6 eran `import-not-found` de `sqlglot`, 2 la falta de `types-PyMySQL` (extra
  `dev`) y 4 en `_core/export_safety.py` por tener instalado `types-openpyxl` (no declarado, y la configuración trataba
  `openpyxl` como sin tipos). Idénticos en v0.28.0 con el mismo entorno: ninguno era una regresión.
- El entorno tampoco tenía `zensical` (extra `docs`) y fuera de pytest cargaba una copia antigua de `util_bbdd` de
  site-packages.
- Consecuencia: los tests de `migrate` que dependen de `sqlglot` (incluidos los 46 de vistas en integración) no se
  ejecutaron contra los cambios de la v0.29.0 durante el desarrollo. Ejecutados después en el venv: 6101 passed y
  582 passed — la v0.29.0 publicada queda validada.

## AI output summary
- Entorno: `pip install -e ".[dev,docs]"` (ahora `import util_bbdd` carga `src/`; `sqlglot`, `types-PyMySQL`,
  `zensical`, `psycopg2-binary` instalados).
- `pyproject.toml`: `types-openpyxl` y `psycopg2-binary` en `dev`; retirado el override `ignore_missing_imports` de
  `openpyxl`.
- `_core/export_safety.py`: firmas compatibles con `types-openpyxl` (`cell → Any`, `create_sheet(title: Any)`,
  `worksheets` en lugar de `_sheets` con variable tipada); `bulk/_execution/insert_strategies.py:150` con
  `type: ignore[import-untyped, unused-ignore]` (el ignore solo se usa si `psycopg2` está instalado).
- `tests/conftest.py`: aviso en la cabecera y junto a los recuentos si falta alguna distribución del extra `dev` (lee
  `pyproject.toml`); comprobado simulando la ausencia de `sqlglot` y `types-openpyxl`.
- Registros: notas de corrección en `2026-10-02c/02_IMPLEMENT_AUDIT_CODE_VERSION.md` y `2026-10-02d/TRACEABILITY.md`;
  `.ai/CURRENT_STATE.md` con las cifras de referencia; `SHARED_INSTRUCTIONS.md` § «Comandos de desarrollo» con el
  entorno de referencia; CHANGELOG `[Unreleased]`.
- Verificación en el entorno corregido: mypy **sin errores** (406 ficheros, con y sin `psycopg2`); ruff limpio;
  `pytest` **6101 passed, 436 skipped**; `zensical build --strict` sin avisos; integración en los 5 servidores del banco
  **582 passed**.

## Directrices para Futuras IAs
- **[tests]**: Mide siempre con `pip install -e ".[dev,docs]"`. Un `importorskip` a nivel de módulo convierte todo el
  módulo en **un** salto: si falta `sqlglot` o `psycopg2`, `pytest` sigue verde pero recoge ~140 tests menos y los
  recuentos no son comparables. `tests/conftest.py` avisa si falta algo del extra `dev`.
- **[tests]**: Referencia en este equipo (v0.29.0 + config-review): 6537 recogidos; 6101 passed, 436 skipped sin URLs
  de servidor; `tests/integration` 582 con las URLs del banco.
- **[mypy]**: Antes de llamar «previo» a un error de mypy, compáralo en un worktree de la versión anterior **con el mismo
  entorno**; los `import-not-found`/`import-untyped` y los de stubs (`types-openpyxl`) suelen ser del entorno.
- **[herramientas]**: Para medir otra versión sin tocar el entorno: `git worktree add --detach <dir> vX.Y.Z` y un venv
  con `--system-site-packages` en el scratchpad; retira el worktree al terminar (`git worktree remove --force`).

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Commit propuesto (no ejecutado): `fix(dev): entorno de tests reproducible (extras dev), tipos de openpyxl y aviso de dependencias`
