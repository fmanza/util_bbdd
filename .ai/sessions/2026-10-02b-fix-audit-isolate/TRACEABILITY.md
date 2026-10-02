# TRACEABILITY

## Session metadata
- id: 2026-10-02b-fix-audit-isolate
- fecha: 2026-10-02
- rama: develop (base `8c5796e`)
- flujo: `/audit-code` alcance B (`on_error="isolate"` de extremo a extremo) → APROBADO con 4 hallazgos BAJA → «si y
  añade» los dos abiertos de la 0.27.0 (B-3 y I-2) → correcciones

## AUDIT_CODE (resumen)
- Sin hallazgos críticos ni medios. Sondas: `probe_audit_isolate.py`.
- **B-1 (seguridad, confirmado)**: `partition` llegaba al CSV sin neutralizar fórmulas (`'=HYPERLINK("x")'`).
- **B-2 (confirmado)**: `row_offset`/`max_rejects` rechazaban `numpy.int64` (`chunk_size` sí los acepta).
- **B-3 (confirmado)**: la doc de `max_rejects` no mencionaba el presupuesto común de `rejects_scope`.
- **B-4 (confirmado por lectura)**: tras un fallo capturado dentro de `rejects_scope`, `*_from_df` avanzaba todo y
  `*_from_chunks` solo los chunks terminados.
- Abiertos de la 0.27.0, ahora corregidos: **B-3 (0.27.0)** el test de `UpdateAutoIncrement` usaba el conector de
  MariaDB contra una URL de MySQL; **I-2** el banco medía MariaDB dos veces por defecto (y avisaba dos veces del puerto).

## AI output summary
- `rejects.py`: `optional_non_negative_int()` (con `operator.index`, como `chunk_size`); `validate_isolation` lo usa.
- `crud.py`: `rejects_scope` valida `partition` y `row_offset` con él (B-1, B-2); `max_rejects` normalizado; los streams
  anotan las filas recibidas antes de procesar cada chunk (B-4: misma regla que `*_from_df`); docstrings.
- `docs/api/bulk_crud.md`: `max_rejects` con `rejects_scope`.
- `scripts/bench_bulk.py`: `DEFAULT_ENGINES` sin `mariadb_connector`; la URL derivada sin pasar por
  `resolve_engine_url("mariadb")` (un solo aviso).
- `tests/integration/test_update_auto_increment_mariadb.py`: la variante del conector se salta si la URL no es de MariaDB.
- Tests: partición no entera, enteros de numpy, B-4 (con mutación detectada), presupuesto común en `batcherrors`,
  motores por defecto del banco.

## Validación
`ruff`/`mypy` limpios (391); `pytest` 5993 passed, 436 skipped; `tests/integration` 582 passed; `zensical build
--strict` sin avisos.

## VERSION — v0.28.0 (`/version-closure`)
- Alcance (`97b595d..HEAD`): plan (`8761ea6`), `rejects_scope` y corrección de `disable_constraints` (`349d212`,
  `8c5796e`), correcciones del audit-code (`83f58fe`).
- SemVer MINOR: API nueva (`BulkCrud.rejects_scope`); cambios observables solo con `on_error="isolate"` (posiciones y
  `max_rejects` correctos con `disable_constraints`; `partition` solo entera; enteros de numpy aceptados; avance del ámbito
  tras fallo) y en el banco (`--engines` por defecto). Sin incompatibilidades ni migraciones; Python `>=3.12`.
- Versión `0.28.0` en `pyproject.toml`, `README.md`, `docs/index.md`, `docs/roadmap.md` y pie de `docs/architecture.md`;
  `CHANGELOG.md` `[Unreleased]` → `[0.28.0] - 2026-10-02`; `.ai/CURRENT_STATE.md` y `SESSIONS_DIGEST.md`.
- Checklist: `ruff`/`format --check` y `mypy` (391) limpios; `pytest` 5993 passed / 436 skipped;
  `tests/integration` 582 passed; `python -m build` → `util_bbdd-0.28.0`; `zensical build --strict` sin avisos.
- Rollback: tag `v0.27.1` o `git revert` de `83f58fe` y `349d212`; quien use `rejects_scope` recibe `AttributeError`.
- Limitaciones: issue del ORA-03106 sin publicar; S-1 NO_GO; sin lock entre procesos para los CSV.
- Handoff: push de `develop` y tag `v0.28.0`.

## Directrices para Futuras IAs
- **[bulk/validación]**: los parámetros enteros públicos se validan con `operator.index` (aceptan numpy), no con
  `isinstance(x, int)`: `validate_chunk_size`, `optional_non_negative_int`.
- **[bulk/rejects]**: en `rejects_scope`, una operación avanza la posición con todas las filas que recibió, también si
  falla; los llamadores de `__isolating` anotan `rows` antes de procesar.

## Veredicto final
Veredicto: CLOSED
