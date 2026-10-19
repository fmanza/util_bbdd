# TRACEABILITY

## Session metadata
- id: 2026-10-19b-docs-args-d4
- fecha: 2026-10-19
- rama: develop
- skill: documentation + version_closure
- fase: IMPLEMENT (docstrings y docs) + VERSION (v4.0.0)

## Prompt issued
1. «D4: 28 métodos sin Args: en módulos sin página de documentación automática. revisa documentación con los últimos
   cambios»
2. `/version-closure` sin inputs. Supuestos declarados: versión v4.0.0 (el `[Unreleased]` era MAJOR por `oracledb`),
   cierra los commits `b9136462`, `48e18fe9`, `fdd9d3fe` y el trabajo D4; sesión nueva `2026-10-19b-docs-args-d4`.

## Context supplied
- `.ai/CURRENT_STATE.md` (fila D4), `.ai/sessions/2026-10-16i-documentation-review/TRACEABILITY.md`
- `git log`/`git show --stat` de `b9136462`, `48e18fe9`, `fdd9d3fe`; `CHANGELOG.md` `[Unreleased]`
- `.github/agents/version-closer.agent.md`, `.github/prompts/version_closure.prompt.md`,
  `.github/instructions/sync.instructions.md`

## AI output summary
- La lista de los 28 métodos de D4 no estaba guardada; se rehízo con un script `ast` en el scratchpad (métodos y
  funciones públicos con parámetros y docstring sin `Args:`): 25 en los módulos que nombra D4 + 3 de `metadata.facts`
  (tocado por los últimos commits).
- `Args:` (y `Returns:` donde aportaba) en `bulk/_execution/parallel_planner.py` (`rule`, `plan`),
  `bulk/_execution/range_partitioner.py` (`validate_disjoint`, `is_rangeable`), `bulk/options.py`
  (`RetryOptions.should_retry`, `BulkOptions.of`, `BulkOptions.for_worker`), `metadata/snapshot_cache.py` (5),
  `metadata/source.py` (`fetch_all`, `CatalogSource.snapshot`, `AsyncCatalogSource.snapshot`),
  `metadata/catalog_registry.py` (2), `metadata/_charset_detection.py` (3), `migrate/charset.py` (2),
  `migrate/emitters/oracle.py` (`emit`, `emit_statements`), `migrate/emitters/mysql.py` (`strip_int_display_width`),
  `metadata/facts.py` (`secondary_nonunique_indexes`, `unique_indexes`, `inbound_foreign_keys`).
- Revisión de docs frente a los 3 commits: extra `oracle`, `"skipped"`, `recovery_ddl` y únicos sin constraint ya
  estaban documentados. Corregido `docs/api/bulk_parallel.md` (`skipped` = DDL no obtenido, no recreación fallida) y
  añadido en `docs/guides/drivers.md` el requisito de `libclntsh` sin versión del modo thick con `oracledb>=26`.
- VERSION: `CHANGELOG.md` `[Unreleased]` → `[4.0.0] - 2026-10-19` (con entrada `docs`), campos de versión
  (`pyproject.toml`, `README.md` ×2, `docs/index.md`, `docs/roadmap.md`, pie de `docs/architecture.md`: 342 ficheros,
  sin paquetes nuevos), `.ai/CURRENT_STATE.md` (versión, fila v4.0.0, tests, D4 hecho, R8), `SESSIONS_DIGEST.md`,
  `INDEX.md` (esta sesión; `2026-10-19-oracle-unique-index-all` pasa a CLOSED).
- Validaciones ejecutadas: `ruff check` y `ruff format --check` limpios; `mypy src tests/unit/test_protocol_conformance.py`
  sin errores (342 ficheros); `pytest` completo sin URLs del banco 6374 passed, 595 skipped
  (`build/logs/d4_pytest.txt`); `mkdocs build --strict` limpio (`build/logs/d4_mkdocs_strict.txt`, salida en el
  scratchpad); `python -m build` correcto; `tests/unit/test_docs_version.py` 6 passed tras el cambio a 4.0.0;
  `gen_arquitectura_capas.py --edges` sin error.
- No ejecutado: `pytest` con el banco en este cierre; `zensical build --strict` (se usó `mkdocs build --strict`).

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Docstrings `Args:` | `src/util_bbdd/{bulk,metadata,migrate}/…` (11 ficheros) | completado |
| Docs | `docs/api/bulk_parallel.md`, `docs/guides/drivers.md` | completado |
| Cierre | `CHANGELOG.md` [4.0.0], campos de versión, `.ai/CURRENT_STATE.md`, `SESSIONS_DIGEST.md`, `INDEX.md` | completado |

## Directrices para Futuras IAs
- **[docs/D4]**: el recuento de métodos sin `Args:` se reproduce con `ast`: funciones y métodos públicos (sin `_`
  inicial, salvo `__init__`) con parámetros distintos de `self`/`cls`, sin `@overload`, cuyo docstring no contiene
  `Args:`. Sobre todo `src/util_bbdd` salen ~240 en módulos públicos; la mayoría son resúmenes de una línea
  deliberados (decisión de D4), no deuda.
- **[docs/índices]**: `IndexActionResult.action="skipped"` (4.0.0) significa que el índice no se tocó porque no se pudo
  obtener su DDL (único sin constraint de Oracle sin privilegios de catálogo); un índice borrado que no se recrea es
  `"failed"` y su DDL va en `error_msg` y en `IndexRebuildError.recovery_ddl`.
- **[dependencias]**: desde 4.0.0 `oracledb` es el extra `oracle`; las instrucciones de instalación con `@vX.Y.Z` solo
  admiten `[oracle]` a partir de `@v4.0.0` (en `@v3.4.1` funciona porque `oracledb` aún era dependencia base).
- **[docs/drivers]**: con `oracledb>=26` el modo thick en Linux/macOS exige `libclntsh.so`/`libclntsh.dylib` sin
  versión; está en `docs/guides/drivers.md` § Thick Mode, no solo en el CHANGELOG.
- **[VERSION]**: el pie de `docs/architecture.md` cuenta los `.py` de `src/util_bbdd` (342 en 4.0.0); si no se añaden ni
  quitan ficheros ni imports entre paquetes, basta cambiar versión y fecha sin regenerar el SVG.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- R8: tag `v4.0.0`, push de `develop`, fast-forward de `main` y CI (lo hace el usuario); después, instrucciones de
  instalación a `@v4.0.0`.
- R6 sigue pendiente (push y tags de 3.1.1–3.3.0, ya creados en local).
