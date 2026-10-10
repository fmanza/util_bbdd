# Revisión de la documentación — nivel 1 (B5, D4–D5)

## Método

El de `../2026-10-10-api-1-0-final/02_DOC_REVIEW.md`: comprobador automático de imports (bloques recorridos por líneas;
10 imports en estas páginas, todos válidos: `build/logs/postv1_b5_doc_imports_{before,after}.txt`), lectura completa
de cada página, verificación de cada afirmación comprobable contra el código (introspección, `grep`, scripts del banco
con `--help`/`list`) y ejecución de los ejemplos tocados (el de pool contra el PostgreSQL del banco).
`zensical build --strict` sin incidencias tras cada bloque.

## Páginas revisadas

Rendimiento: `guides/performance_audit_guide.md`, `guides/performance_audit_constraints_guide.md`,
`guides/benchmarks.md` (+ `examples/benchmark_commit_cadence.md`). Constraints: `constraints_audit_index.md`,
`constraints_quick_reference.md`, `constraints_reading_guide.md` (consolidadas). Migración: `functional/migrate_*.md`
(6) y `api/migrate_*.md` (6). Barrido: `guides/comparator.md`, `functional/graph_analysis.md`,
`examples/graph_generation.md`. De paso: `api/bulk_crud.md` (`maintenance_scope`), `api/managers_async.md`.

## Hallazgos y correcciones

| Hallazgo | Dónde | Corrección |
|---|---|---|
| Guías de rendimiento y constraints en la raíz de `docs/` | 5 páginas | 2 movidas a `docs/guides/`; las 3 `constraints_*` (repetían la guía, rutas inexistentes `src/util_bbdd/introspect/`, `audit_manager.py`, `tests/bulk/`) consolidadas en la guía (decisión del usuario) y fuera del nav |
| SQL inexistente o incorrecto: `SET batch_size`, `SET audit_mode`, `PRAGMA parallel DML` (Oracle), `DISABLE CONSTRAINT … NOVALIDATE` mal ordenado, `CHECK_CONSTRAINTS = OFF`, `ALTER INDEX ALL … DISABLE` (desactiva el CLUSTERED), `VALIDATE CONSTRAINT` tras `DISABLE TRIGGER` (no valida nada), «SQLite sin re-validación» (existe `PRAGMA foreign_key_check`) | guía y páginas de constraints | Referencia rápida por motor alineada con `maintenance_scope` (`_execution/maintenance.py`) y SQL corregido |
| CLI inventado `bench_bulk.py run --table --scenarios` + `summarize` | 3 páginas | Banco real: `bench_dump.py` (`indexes`, `nocheck`) y `bench_bulk.py --engines --sizes --ops` |
| Contradicción: el caso de PostgreSQL desactivaba el trigger de auditoría que el propio caso declaraba no desactivable | guía de constraints | Fase 2 con `DROP` + `ADD … NOT VALID` + `VALIDATE CONSTRAINT` |
| «`dump` no admite origen SQLite» | `performance_audit_guide.md` | Sí lo admite (con aviso de tipos); es el banco el que no lo prepara |
| Enlaces a `docs/functional/dump.md` «(si existe)» | `performance_audit_guide.md` | `functional/dump_data_export.md`, `api/dump.md` |
| Tabla de pool «medida en AWS t3.large» y tiempos de PostgreSQL 15 sin fuente; recomendaban `max_overflow` en PostgreSQL (no lo admite) | `benchmarks.md` | Retiradas; remisión a la guía de conexiones (`pool_size` por motor) |
| Ejemplo async del pool con `AsyncDatabaseManager(..., pool_size=20)` (no existe ese parámetro) | `benchmarks.md` | `pool_size` en `conn_params`; ejecutado contra el banco. **Al ejecutarlo apareció el fallo de asyncpg** (hotfix `d369c8e3`) |
| «Cadencia de commit: 3–8× en MariaDB real» | `benchmarks.md`, `examples/benchmark_commit_cadence.md` | Contradecía la tabla medida de la misma página (+12 % en MariaDB): la cadencia no acelera, acota el undo log y permite reanudar |
| `pip install util_bbdd` / `util_bbdd[analysis]` (no está en PyPI) | `comparator.md`, `graph_analysis.md`, `graph_generation.md` | Instalación desde el repositorio (`git+…@v1.0.0`) |
| Destinos sin MySQL; «comentarios de vistas y rutinas no se migran»; precondiciones con drivers y «wrappers» de paramstyle (obsoletos desde ADR-003: `plan()` recibe un manager o `MetadataSource`); `VIEW_DEFINITION` truncada (se usa `OBJECT_DEFINITION`); «MariaDB no migra procedimientos ni funciones» (sí, en pass-through) | `functional/migrate_*` | Corregido contra `planner.py`, extractores y `WarningCode` |
| `SQLAlchemyError` al leer el catálogo (es `MetadataError`); `execute`/`validate_views` sin `audit_sink`; drivers `psycopg2`, `cx_Oracle`, «pymysql para MariaDB», «pyodbc con wrapper» | `api/migrate_*` | Corregido; `TypeError` con una conexión que no es manager ni `MetadataSource` |
| `maintenance_scope` sin `require_optimization`, con `*` y retorno `Generator[None…]` | `api/bulk_crud.md` | Firma real y `MaintenanceScopeResult` |

## Fuera de alcance (registrado)

- Nivel 2 (D4): ~85 páginas sin leer página a página (resto de `docs/functional`, `docs/api`, `docs/examples`,
  `docs/guides`).
- `docs/examples/migrate_*` no revisados (los cita cada página de API).
- `AsyncDatabaseManager("sqlserver")` no se pudo sondear aquí: falta el driver ODBC que usa aioodbc por defecto (IM002).
