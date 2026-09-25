# REQUEST

## Session metadata
- id: 2026-09-25-performance-audit-dump
- fecha: 2026-09-25
- rama: develop
- skill: performance-audit
- fase solicitada: FASE 1 (arquitectura) → FASE 2 (CB1–CB8) → FASE 3 (propuestas) → FASE 4 (informe + roadmap) → FASE 5 (validación con benchmark). Solo análisis: sin IMPLEMENT en `src/`.

## Solicitud original saneada
```
/performance-audit

Objetivo: todas las áreas
Baseline: ejecutar /quick-bench primero
Dialects: PostgreSQL, MySQL, SQL Server, Oracle
Volumen: large
Timeline: ASAP
Validation: sí
```

## Objetivo operativo de esta sesión
- Medir una línea base **real** de `DumpOrchestrator` a volumen `large` (500K + 1M + 2M = 3,5M filas) en PostgreSQL, MySQL, MariaDB, SQL Server, Oracle y SQLite, con desglose por fase.
- Validar los 8 cuellos hipotéticos CB1–CB8 contra código y medición, separando CONFIRMADO / REFUTADO / HIPÓTESIS.
- Proponer mejoras priorizadas (impacto/esfuerzo/riesgo) con recomendaciones por motor.
- Validar las propuestas que se pueden prototipar sin tocar `src/` (configuración del engine, flags de `DumpConfig`, parches en el propio banco).

## Restricciones explícitas
- Motores: PostgreSQL, MySQL, SQL Server, Oracle; **MariaDB y SQLite incluidos a petición del usuario durante la sesión** (inicialmente fuera de alcance).
- Solo análisis: no se edita `src/`. Las variantes se prototipan en el banco de la sesión.
- Timeline ASAP: 1 repetición por medición a volumen `large` (declarado como límite en el informe).

## Supuestos declarados
- `/quick-bench` no existe como comando (solo aparece descrito en `.claude/performance-audit-guide.md`). Su equivalente, `scripts/bench_dump.py`, **no sirve como línea base**: no llama a `DumpOrchestrator` (simula con `pd.to_sql`) y con su configuración por defecto falla (`unknown database bench_source`). Se sustituye por un banco real en `bench/bench_dump_real.py`.
- Servidores: contenedores del banco (`docker-compose.bench.yml`, 127.0.0.1, puertos no estándar). Origen y destino en el mismo servidor (esquemas `dump_src` → `dump_dst`).
- SQL Server se mide con `mssql+pyodbc` + ODBC Driver 18 (el recomendado tras P-17 de la auditoría de `bulk`).

## Resultado esperado
- `audit_report_dump_20260925.md` — informe ejecutivo + hallazgos (PLAN, AUDIT_PLAN, AUDIT_CODE).
- `improvement_roadmap_dump.md` — roadmap P1/P2/P3.
- `validation_report_20260925.md` — línea base y variantes medidas.
- `bench/bench_dump_real.py` + `baseline/` con resultados crudos.
- `TRACEABILITY.md` y entrada en `INDEX.md`.
