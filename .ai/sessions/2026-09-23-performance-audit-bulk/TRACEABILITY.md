# TRACEABILITY

## Session metadata
- id: 2026-09-23-performance-audit-bulk
- fecha: 2026-09-23
- rama: develop
- skill: performance-audit
- fase: PLAN + AUDIT_PLAN + AUDIT_CODE + VERSION (solo lectura, sin IMPLEMENT)

## Prompt issued
```
/performance-audit

Módulo: src/util_bbdd/bulk/
Operaciones: Todas (INSERT, UPDATE, DELETE)
Escala de datos: Benchmarks con 1K, 10K, 100K, 1M registros
Motores: Oracle, MySQL, PostgreSQL, SQL Server, SQLite
Restricciones: Mantener compatibilidad multi-BBDD y auditoría integrada
Alcance: Análisis + propuestas de remediación + quick wins
```
Seguido de: "Guardar en .ai/sessions/".

## Context supplied
- `.claude/commands/performance-audit.md`, `.github/prompts/performance_audit_bulk.prompt.md`, `.github/agents/performance-auditor.agent.md`
- Código completo de `src/util_bbdd/bulk/`
- Código fuente instalado de SQLAlchemy 2.0.50 y PyMySQL 1.1.2 (verificación del comportamiento de drivers)
- `.ai/sessions/INDEX.md`

## AI output summary
- Lectura completa de `bulk/` (21 ficheros).
- Métricas base no aportadas → declarado como supuesto y generadas en la sesión.
- `bench/bench_bulk.py`: benchmark por fases en SQLite a 1K/10K/100K/1M (copy, `to_dict`, normalización, prototipo vectorizado con verificación de equivalencia, INSERT/UPDATE/DELETE, `generar_sql` 10K, pico de memoria 100K con `tracemalloc`).
- `bench/bench_sqlgen.py`: coste de `text()` con 10.000 binds (vía MySQL), DELETE `IN` con 5000 binds, `generar_sql` actual frente a prototipo con `literal_processor` (33×, salida idéntica en la muestra).
- `bench/bench_mysql_strat.py`: `MySQLMultiRowInsertStrategy` frente a `DefaultInsertStrategy` sobre conexión SQLite (2,80 s vs 0,34 s por 100K) + cProfile (regex de `text()` y clave de caché).
- Verificado en PyMySQL que `executemany` reescribe INSERT a multi-fila con `%(name)s`.
- Verificado en SQLAlchemy (`sql/crud.py`, `mssql/pyodbc.py` y compilación con `MSDialect_pyodbc`) que, sin `create_engine(fast_executemany=True)`, el INSERT va por insertmanyvalues y el listener de fast_executemany no se activa.
- Comprobado que no hay tests de integración ni referencias al límite de 2100 parámetros de SQL Server.
- Veredictos emitidos: AUDIT_PLAN **GO_CONDICIONAL**; VERSION **SIGNIFICATIVO**. 16 hallazgos (2 CRÍTICA, 4 ALTA, 5 MEDIA, 1 BAJA, 4 INFO).
- Sin cambios en `src/`, `tests/` ni `docs/`.

## Artefactos generados

| Artefacto | Ruta | Estado |
|---|---|---|
| REQUEST | `.ai/sessions/2026-09-23-performance-audit-bulk/00_REQUEST.md` | emitido |
| CONTEXT SNAPSHOT | `.ai/sessions/2026-09-23-performance-audit-bulk/00_CONTEXT_SNAPSHOT.md` | emitido (G0 GO_CONDICIONAL) |
| PLAN + AUDIT_PLAN + AUDIT_CODE + VERSION | `.ai/sessions/2026-09-23-performance-audit-bulk/01_PERFORMANCE_AUDIT.md` | emitido |
| Benchmarks | `.ai/sessions/2026-09-23-performance-audit-bulk/bench/*.py` | reproducibles |

## Directrices para Futuras IAs
- **[bulk/MySQL]**: PyMySQL `Cursor.executemany` ya convierte un INSERT en INSERT multi-fila (`RE_INSERT_VALUES`, admite `%(name)s`, sentencias de hasta 1 MB). Cualquier estrategia multi-fila propia debe compararse contra `DefaultInsertStrategy` antes de adoptarse; la actual es 8× más lenta en cliente.
- **[bulk/SQL Server]**: registrar `cursor.fast_executemany` con un listener no basta para INSERT en SQLAlchemy ≥ 2.0.9: sin `create_engine(fast_executemany=True)` el dialecto usa insertmanyvalues y llama a `cursor.execute`, no a `executemany`. Solo el UPDATE se beneficia del listener.
- **[bulk/SQL Server]**: cualquier SQL con parámetros por lote debe respetar el límite de 2100 parámetros (SQLAlchemy usa 2099). La sintaxis `(a, b) IN ((..), (..))` no existe en SQL Server.
- **[bulk/normalización]**: el coste dominante en Python es `to_dict` + `normalize_sql_literal` por celda (62 % del INSERT 1M en SQLite). Cualquier optimización debe mantener la semántica: strip de textos, bytes → UTF-8, dict/list → JSON, NaN/NaT/NA → None, Timestamp → datetime, escalares numpy → nativos.
- **[bulk/auditoría]**: la auditoría CSV no es un cuello de botella (una fila por operación); no hace falta hacerla asíncrona.
- **[bulk/generar_sql]**: `generar_sql=True` es el valor por defecto de `bulk_*_from_df`; su coste (~165 µs/fila) afecta a quien no pase `generar_sql=False` explícitamente.
- **[bulk/benchmarks]**: los scripts de `bench/` usan SQLite; sirven para el coste Python, no para validar efectos del servidor.

## Veredicto final
Veredicto: CLOSED (auditoría entregada; veredicto técnico SIGNIFICATIVO)
Pendientes al cierre:
- Fase 0: banco de pruebas con los 5 motores reales (condición del GO_CONDICIONAL).
- Fase 1: `/hotfix` P-05 (DELETE SQL Server > 2100 parámetros / PK compuesta).
- Fases 2–5 según `01_PERFORMANCE_AUDIT.md` § VERSION.
