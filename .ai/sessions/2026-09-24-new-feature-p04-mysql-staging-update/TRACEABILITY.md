# TRACEABILITY

## Session metadata
- id: 2026-09-24-new-feature-p04-mysql-staging-update
- fecha: 2026-09-24
- rama: develop
- skill: new_feature
- fase: PLAN + AUDIT_PLAN + IMPLEMENT + AUDIT_CODE + VERSION

## Prompt issued
```
si
```
(Respuesta a "¿Sigo con P-04?". A mitad de la sesión se abrió y cerró el hotfix P-22, con su propio commit, y se retomó P-04 desde `git stash`.)

## Context supplied
- `.ai/sessions/2026-09-23-performance-audit-bulk/01_PERFORMANCE_AUDIT.md` (P-04) y `02_BASELINE_MOTORES_REALES.md`.
- `src/util_bbdd/bulk/crud.py`, `src/util_bbdd/bulk/_execution/batch.py`.
- Servidores del banco: MySQL 8.4, MariaDB 11.4 (PyMySQL y `mariadbconnector`).

## AI output summary
- **Inputs** (diseño inicial): opcional (`update_via_staging=False` por defecto) porque requiere `CREATE TEMPORARY TABLES`. Alcance MySQL/MariaDB. SQL Server y PostgreSQL fuera: con pyodbc el UPDATE ya va a 33K filas/s, con pymssql el cuello es el INSERT (P-17) y PostgreSQL ya va a 24K filas/s.
- **Prototipo previo** (MySQL/MariaDB reales):
  - SQLAlchemy genera `UPDATE t, tmp SET … WHERE …`.
  - `CREATE/DROP TEMPORARY TABLE` no hace commit implícito (rollback verificado).
  - 100K filas en 1,4–1,6 s solo en la parte SQL.
- **IMPLEMENT**:
  - `batch.py`: `MySQLStagingUpdateStrategy`. Por lote: tabla temporal con PK + columnas a actualizar (tipos reflejados), deduplicación por PK (gana la última), carga con la estrategia INSERT del motor y columnas JSON sin reprocesar (P-19), `UPDATE … JOIN` y `DROP TEMPORARY TABLE IF EXISTS`. Ante error, limpia sin ocultar el error original.
  - `BatchStatementExecutor`: `execute(..., strategy=None)` y propiedad `insert_strategy`.
  - `crud.py`: `BulkCrud(update_via_staging: bool = False)` (efectivo solo en `mysql`/`mariadb`), usado en `bulk_update_from_df`.
  - `scripts/bench_bulk.py`: variante `p04-mysql-staging-update`.
  - Docs: `CHANGELOG.md` (Added), `docs/api/bulk-crud.md`, `docs/guides/benchmarks.md`.
- **Verificación de equivalencia** (MySQL/PyMySQL, MariaDB/PyMySQL, MariaDB/`mariadbconnector` × `chunk_size` 1, 2 y 5000):
  - Estado final idéntico al UPDATE por executemany: JSON, TINYINT, ENUM, DECIMAL, DATETIME(6), TIME, BLOB, texto, NULL, PK repetida en el mismo lote y en lotes distintos, PK inexistente.
  - Rollback completo en `bulk_session` con fallo en el 2º lote; sin tablas temporales restantes.
- **Hallazgos al verificar**:
  - P-22 (CRÍTICA): la caché de `MySQLMultiRowInsertStrategy` mezclaba tablas. Corregido en sesión propia, commit `84f693c`.
  - P-21 (ALTA): el UPDATE actual falla con BLOB si el valor es UTF-8 válido. Registrado.
- **Tests**:
  - `tests/unit/bulk/test_staging_update.py` (6, sin servidor).
  - `tests/integration/test_bulk_engines.py`: `test_update_via_staging_matches_executemany` (chunk 2 y 5000) y `test_update_via_staging_rolls_back_inside_bulk_session`.
- **Validación**:
  - `ruff check src tests scripts` limpio; `mypy src` y `mypy scripts/bench_bulk.py` limpios.
  - Suite: 4490 passed / 47 skipped. Integración 6 motores: 34 passed / 14 skipped (staging solo MySQL/MariaDB; JSON no aplica a SQL Server/Oracle). MariaDB con `mariadbconnector`: 8 passed.
- **Banco** (`bulk_update_from_df` completo, verificado con SQL; 10K y 100K × 3, 1M × 1):

| Filas | MySQL 8.4 | MariaDB 11.4 |
|---|---|---|
| 10K | 3,79 → 0,28 s (13,4×) | 3,36 → 0,26 s (12,8×) |
| 100K | 37,4 → 2,92 s (12,8×) | 33,6 → 2,66 s (12,6×) |
| 1M | 376,0 → 29,5 s (12,8×) | 331,4 → 27,1 s (12,2×) |

  - La cifra del prototipo (~24×) solo medía la parte SQL. Docstrings y CHANGELOG usan la medida completa (~12,5×). El resto del tiempo es la preparación en Python (P-03).

- **Decisión del usuario** ("Activarlo por defecto y commit"): `update_via_staging` pasa a `True` por defecto.
  - CHANGELOG marca el **cambio de comportamiento**: sin `CREATE TEMPORARY TABLES`, `bulk_update_from_df` falla en MySQL/MariaDB hasta pasar `update_via_staging=False`.
  - La variante del banco pasa a ser el control `mysql-update-executemany-legacy` (`update_via_staging=False`).
  - Verificado: `BulkCrud` por defecto hace el UPDATE de 100K en MySQL en 3,0 s, frente a 38,2 s del control.
  - Suite 4490 passed; integración 34 passed / 14 skipped; `mariadbconnector` 8 passed.

## AUDIT_CODE
- Bugs potenciales:
  - Requiere `CREATE TEMPORARY TABLES`; sin él falla al crear la temporal (activo por defecto: hay que pasar `update_via_staging=False`).
  - La temporal se elimina siempre; si su `DROP` falla tras otro error, se conserva el error original.
- Edge cases:
  - PK repetida: gana la última (igual que executemany).
  - PK nula o inexistente: no actualiza.
  - Lote vacío: no hace nada.
  - Otros motores: el flag se ignora (test con SQLite).
- Performance: una tabla temporal por lote (`chunk_size`); coste de DDL despreciable frente al UPDATE por fila.
- Seguridad: identificadores con `identifier_preparer`; valores como parámetros; nombre temporal generado internamente.
- Tipado: mypy limpio.
- Deuda técnica:
  - El rowcount de auditoría sigue siendo el número de filas del DataFrame (como antes).
  - SQL Server con pymssql y PostgreSQL no tienen equivalente.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| Estrategia y executor | `src/util_bbdd/bulk/_execution/batch.py` | completado |
| Parámetro `update_via_staging` | `src/util_bbdd/bulk/crud.py` | completado |
| Tests | `tests/unit/bulk/test_staging_update.py`, `tests/integration/test_bulk_engines.py` | nuevos |
| Banco | `scripts/bench_bulk.py` (variante de control `mysql-update-executemany-legacy`) | actualizado |
| Resultados | `.ai/sessions/2026-09-23-performance-audit-bulk/baseline/*_p04_*` y `*_p02_*` | archivados |
| Docs | `CHANGELOG.md`, `docs/api/bulk-crud.md`, `docs/guides/benchmarks.md` | actualizados |

## Directrices para Futuras IAs
- **[bulk/MySQL]**: el DDL de tablas temporales debe llevar `TEMPORARY` (también en el `DROP`); sin él MySQL hace commit implícito y rompe la atomicidad de `bulk_session`.
- **[bench]**: un prototipo que mide solo la parte SQL sobreestima la mejora. Publica la cifra de extremo a extremo del banco.

## Veredicto final
Veredicto: CLOSED
Pendientes al cierre:
- Ninguno. Commits `18ceb7a` (feat) y `c0f003a` (docs(ai)).
