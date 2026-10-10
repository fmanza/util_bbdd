# Revisión de la documentación para 1.0.0

## Método

Comprobaciones automáticas sobre `README.md`, `docs/**/*.md` y `docs/**/*.py` (excluidos `docs/v0.8.0/` y `docs/adr/`,
históricos):

1. **Imports**: cada `from util_bbdd… import …` / `import util_bbdd…` de los bloques de código (python, py, pycon o sin
   lenguaje; recorrido por líneas, respetando fences) se resuelve contra el paquete instalado. 198 imports.
2. **Métodos de los managers**: cada `manager.<m>(`, `mgr.<m>(`, `db.<m>(`… existe en `SyncDatabaseManager` o
   `AsyncDatabaseManager`.
3. **Métodos de otros puntos de entrada** (`crud.`, `comparator.`, `planner.`, `plan.`, `diff.`, `reporter.`…): sin
   hallazgos reales (solo falsos positivos de nombres de fichero y rutas de módulo).
4. **Barrido de texto**: `pip install util_bbdd` (PyPI), extra `[doc]`, `psycopg2`, `DeprecationWarning`, `0.x`/`1.0.0`.
5. Lectura completa del README, `docs/index.md`, `docs/installation.md`, `docs/api/intro.md`, `docs/api/index.md`,
   `docs/guides/postgresql_driver_guide.md` y de la parte afectada de `docs/guides/comparator.md`.
6. Ejecución real (scratchpad) de los ejemplos nuevos o tocados: Quick Start SQLite del README y de `docs/index.md`,
   carga con `BulkCrud`, documentación HTML con `DatabaseDocumentation`, verificación del comparador, bloque de
   verificación de `api/intro.md`.

Logs: `build/logs/api10final_doc_imports_{before,after}.txt`, `build/logs/api10final_doc_methods*_before.txt`.

## Hallazgos y correcciones

| Hallazgo | Dónde | Corrección |
|---|---|---|
| README con secciones duplicadas e históricas (v0.2, v0.5, v0.10 «vigente», evolución v0.6–v0.32) | `README.md` | Reescrito para 1.0 |
| Ejemplos con APIs inexistentes: `bulk_crud`/`bulk_crud_audit`, `PoolFactory.create(...)`, `util_bbdd.database_exceptions`, `manager.bulk_insert_from_csv`, tabla de excepciones con métodos inventados (`.handle_missing_query()`, `.reconnect()`…), `DatabaseConnectionError`/`DatabasePoolError` | `README.md` | Eliminados; ejemplos nuevos ejecutados |
| `pip install util_bbdd` (no está en PyPI; depende de `util` por URL de git) | README, `docs/index.md`, `docs/installation.md` | `pip install "util_bbdd @ git+…@v1.0.0"` |
| Extra `doc` inexistente | README, `api/database_documentation.md`, `examples/database_documentation_generation.md` (×2), `examples/diff_reporters.md`, `functional/database_documentation.md`, `guides/comparator.md` | Dependencias base; extra `analysis` para grafos |
| «Solo estos extras»: 4 de 9 | `docs/installation.md` | Tabla con los 9 |
| PostgreSQL con `psycopg2` como driver de los managers | `installation.md`, `postgresql_driver_guide.md`, `troubleshooting.md`, `connection_guide.md`, `docs/index.md` | psycopg 3 + psycopg-pool / asyncpg (verificado en `connection/postgresql/` y `factory/`) |
| Parámetros de pool de SQLAlchemy en PostgreSQL (`max_overflow`, `pool_pre_ping`, `pool_recycle`, `connect_args`) | `postgresql_driver_guide.md`, `installation.md`, README | Los de `PostgreSQLPoolConfig`/`PostgreSQLConnectionConfig` (`pool_size`, `pool_timeout`, `max_idle`, `sslmode`…) |
| `SchemaDiffReporter` importado de la raíz (nunca estuvo) | `api/intro.md` (×3), `guides/comparator.md` | `util_bbdd.comparar` |
| Verificación del comparador rota con SQLAlchemy 2 (`conn.execute("…")` sin `text()` y sin commit) | `guides/comparator.md` | `engine.begin()` + `text()`; ejecutado |
| Métodos inexistentes `fetch_current_schema()`, `get_database_documentation()` | `guides/drivers.md`, `connection_guide.md`, `mariadb_v0.35.0_charset_handling.md` (×3) | `get_schema_metadata()` |
| Motores async sin MySQL; Python 3.10+ para asyncpg | `api/index.md`, `postgresql_driver_guide.md` | MySQL añadido; Python 3.12+ |
| Guía de migración y notas en futuro («se retirarán en 1.0.0») | `api_1_0_migration.md`, `api/managers.md`, `migration_guide_v0.6.7.md`, SHARED_INSTRUCTIONS | En pasado; síntomas de 1.0 (`ImportError`, `AttributeError`) |
| Guías de migración v0.6.x enlazadas como «la» guía de migración | `onboarding_dev.md`, `legacy_versions.md`, `migration_guide.md` | Enlace a la guía 1.0 y nota de guía histórica |
| Portada y referencia de la API sin la superficie 1.0 | `docs/index.md`, `api/intro.md`, `api/index.md` | Sección «API pública 1.0» |

## Fuera de alcance (registrado, no corregido)

- `BulkCrud(audit_csv_path="audit.csv")` con `str` falla con `AuditConfigError: 'str' object has no attribute
  'parent'`. La firma es `Path | None`, así que es un uso fuera de contrato; aceptar `str | Path` sería un cambio
  aditivo (MINOR).
- Con `pytest --cov`, ~340 `ResourceWarning: unclosed database` (SQLite) en tests previos de `bulk` paralelo,
  `test_performance_advisor_once`, `test_reflect_fk_chain` y el comparador. Sin cobertura no aparecen (el trazador cambia
  cuándo se recolectan los objetos). Fugas en los tests o en esas rutas, no en los tests de esta sesión.
- `docs/guides/code_reusability_analysis_guide.md` muestra `util_bbdd._support.sql_normalizer.SQLNormalizer` como
  propuesta hipotética de ejemplo (no existe); se deja por ser ilustrativo.
- No se leyó página a página el resto de `docs/` (guías de rendimiento, auditoría de constraints, funcionales por
  motor): solo las comprobaciones automáticas 1–4.
