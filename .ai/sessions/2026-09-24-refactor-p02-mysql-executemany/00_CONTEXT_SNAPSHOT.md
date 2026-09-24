# CONTEXT SNAPSHOT

## Contexto del repositorio revisado
- `.ai/sessions/2026-09-23-performance-audit-bulk/01_PERFORMANCE_AUDIT.md` (P-02) y `02_BASELINE_MOTORES_REALES.md`
- `src/util_bbdd/bulk/_execution/batch.py` (`MySQLMultiRowInsertStrategy`, `InsertStrategyResolver`)
- `tests/unit/bulk/test_insert_strategies.py`, `test_insert_strategies_cache.py`, `test_mysql_min_packet_calculation.py`
- SQLAlchemy 2.0.50 `sql/compiler.py` (`IdentifierPreparer._double_percents`), PyMySQL 1.1.2 `cursors.py` (`executemany`)

## Estado actual observado
- Árbol limpio tras `ab8d6e5` y `5cb8915`.
- Contenedores del banco en marcha (MySQL 8.4, MariaDB 11.4); conector `mariadb` 1.1.14 instalado.

## Estado Git relevante
- Rama activa: develop
- Cambios locales pre-existentes: ninguno
- Último tag / versión publicada: v0.10.0 (release 0.11.0 en `CHANGELOG.md`)

## Clasificación metodológica
- Tipo principal: refactor (rendimiento sin cambio funcional)
- Estado real de alcance: acotado a la estrategia INSERT de mysql/mariadb
- Consecuencia: la igualdad de valores guardados se verifica contra servidores reales antes de cerrar.

## Gate G0 · Context Ready
Veredicto: GO
