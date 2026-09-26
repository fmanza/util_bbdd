# Roadmap de mejora — módulo `dump` (actualizado)

- Sustituye a `.ai/sessions/2026-09-25-performance-audit-dump/improvement_roadmap_dump.md` (se conserva como histórico).
- Origen: auditoría completa previa + `audit_report_dump_delta_20260925.md` + `validation_report_delta_20260925.md`.
- Línea base de referencia: v0.15.0 (`cfbbf05`), `large` (3,5M filas), mediana de 3 con `scripts/bench_dump.py`.
- Cada paso con su propio flujo (`/hotfix` para PD-xx, `/refactor` o `/new-feature` para Q-xx) y medición antes/después:
  `python scripts/bench_dump.py run --engines <motores> --variants baseline,<variante> --volume large --repeat 3 --out <sesión>/…`

## Fase 0 — Correcciones (antes que cualquier optimización)

| Paso | Hallazgo | Estado | Cambio | Criterio de aceptación |
|---|---|---|---|---|
| 0.1 | PD-01 (CRÍTICA) | **Hecho** (sesión `2026-09-25d-hotfix-bulk-column-case`) | Casar columnas DataFrame ↔ tabla reflejada sin distinguir mayúsculas en `bulk` | `dump` y `BulkCrud` a SQL Server con columnas en minúsculas y mixtas: 3/3 `success`. El banco de `dump` pasa a crear columnas en minúsculas en mssql. |
| 0.2 | PD-02 (ALTA) | **Hecho** (sesión `2026-09-25c-hotfix-dump-pk-sync-truncate`) | `_sync_pk_sequences` con el nombre lógico `esquema.tabla` | Identidad 3/3 en PostgreSQL y Oracle en `scripts/bench_dump.py`; `pk_sync_results` no vacío |
| 0.3 | PD-03 (ALTA) | **Hecho** (sesión `2026-09-25c-hotfix-dump-pk-sync-truncate`) | Un único `TRUNCATE t1, t2, …` en PostgreSQL | `redump` PostgreSQL: 3/3 `success` |
| 0.4 | PD-06 (MEDIA) | **Hecho** (`cf0eafc`: limpieza; sesión `2026-09-26e-hotfix-dump-sqlite-single-writer`: sin paralelismo) | Forzar `parallel_pk_ranges` y `max_parallel_tables` = 1 en SQLite con aviso | `ranges4` en SQLite: 3/3 `success` y verificación OK |
| 0.5 | PD-04 (ALTA) | **Hecho** (sesión `2026-09-26b-hotfix-dump-pg-fk-validation`) | Validación real de FKs en PostgreSQL | Con una fila huérfana, `ConstraintResult` `failed`; coste < 2 % |
| 0.6 | PD-05 (ALTA) | **Hecho** (sesión `2026-09-26-hotfix-dump-fidelity`) | `coerce_float=False` + dtypes nullable en `read_sql`; sin `strip()` en la ruta de `dump` (también en la vía rápida P-33) | Round-trip exacto de BIGINT > 2^53 con NULL, DECIMAL(38,10) y cadenas con espacios; `read` + `prep` no empeora > 10 % |
| 0.7 | PD-08 (ALTA) | **Hecho** (sesión `2026-09-25e-hotfix-bulk-reflect-fk-chain`) | `reflect_table` con `resolve_fks=False` | 200 tablas encadenadas sin `RecursionError`; cadena de 100 en PG < 5 s |
| 0.8 | PD-09 (MEDIA) | **Hecho** (sesión `2026-09-26d-hotfix-dump-mariadb-checkin`) | `_fk_on`/`_fk_off` ignoran `dbapi_conn is None` | El error original llega intacto en MySQL/MariaDB |
| 0.9 | PD-07 (BAJA) | **Hecho** (sesión `2026-09-26f-hotfix-dump-sqlite-source`: aviso, no rechazo; la premisa venía de la matriz de `migrate`) | Rechazar o avisar de un origen SQLite | Error claro en `DumpOrchestrator.__init__` |
| 0.10 | PD-10 (MEDIA, nuevo) | **Hecho** (sesión `2026-09-26c-hotfix-mssql-decimal-precision`; causa real: contexto `decimal` de 28 dígitos en pyodbc) | SQL Server + `fast_executemany`: enviar `Decimal` sin perder precisión (p. ej. como `str`, que en el microbanco cuesta lo mismo que `float`) o fijar `setinputsizes` para columnas DECIMAL | DECIMAL(38,10) con 38 dígitos exacto en `dump` y `BulkCrud` a SQL Server; escritura sin empeorar > 5 % |
| 0.11 | PD-11 (ALTA, nuevo) | **Hecho** (sesión `2026-09-26h-hotfix-dump-pk-sync-ranges`) | Reflejar en la `BulkCrud` principal las tablas cargadas por rangos antes de la Fase 5a | `ranges4` en Oracle y PostgreSQL: 3 × `synced` e identidad OK |
| 0.13 | PD-13 (MEDIA, nuevo) | Abierto (sesión `2026-09-26u-tests-integracion-dump`) | Con pymssql + insertmanyvalues de SQLAlchemy, un `Decimal` en notación exponencial (`-1E-10`, `0E-10`) convierte a `float` la columna del INSERT multi-fila | DECIMAL de más de 15 dígitos exacto con pymssql en lotes con ceros/valores pequeños; quitar el `xfail` de `test_dump_copies_values_exactly[mssql]` |

## Fase 1 — Quick wins

| Paso | Mejora | Estado | Ganancia medida en la auditoría previa | Notas |
|---|---|---|---|---|
| 1.1 (Q1) | `arraysize = chunk_size` en lecturas Oracle | **Hecho** (sesión `2026-09-26g-refactor-dump-oracle-arraysize`) | −29 % medido (58,6 → 41,4 s) | Con rangos (1 rep.): 32,9 s, ya no empeora; pendiente PD-11 |
| 1.2 (Q2) | `stream_results=True, max_row_buffer=chunk_size` en la lectura | **Hecho** (sesión `2026-09-26i-refactor-dump-stream-results`) | Memoria −62 % (PG) / −83 % (MySQL/MariaDB); tiempo ±5 % | Requisito de 1.3 en MySQL/MariaDB. Memoria actual: 417 / 859 MB |
| 1.3 (Q3) | Solape lectura/escritura (1 hilo lector, cola de 2 chunks) | **Hecho** (sesión `2026-09-26j-refactor-dump-read-write-overlap`: MySQL −29 %, MariaDB −25 %, SQL Server −17 %, PG −15 %) | PG −45 % (con lotes de 20K), MySQL −31 %, MariaDB −25 %, SQLite −16 %, SQL Server −19 % | Prototipo: variante `prefetch` de `scripts/bench_dump.py` |
| 1.4 (Q4) | Guía por motor y aviso para `parallel_pk_ranges` | **Hecho** (sesión `2026-09-26k-refactor-dump-ranges-guidance`: SQL Server −37 %, PG −9 %, Oracle −2 %, MySQL/MariaDB +84–94 % con aviso) | SQL Server −48 % (4 rangos + stream) | Perjudicial en MySQL/MariaDB |
| 1.5 (Q7) | Banco real en `scripts/` y guías | **Hecho** (2026-09-25b) | — | Pendiente menor: tabla «Multi-Dialect Considerations» de `.claude/performance-audit-guide.md` sin origen medido |

**Métrica de éxito de la Fase 1** (nueva línea base; objetivo = Δ validado previamente aplicado a la nueva base, a
confirmar con la implementación real, ya que `prep` ha bajado y el peso relativo de lectura y escritura ha subido):

| Motor | Línea base v0.15.0 | Objetivo sin paralelismo | Con `parallel_pk_ranges=4` (opt-in) |
|---|---|---|---|
| PostgreSQL | 19,1 s · 417 MB | ≤ 12 s (con 2.1) y ≤ 200 MB | no combinar con `stream_results` |
| MySQL | 57,0 s · 859 MB | ≤ 42 s y ≤ 200 MB | no recomendado |
| MariaDB | 52,9 s · 859 MB | ≤ 42 s y ≤ 200 MB | no recomendado |
| SQL Server | 65,8 s · 164 MB | ≤ 55 s | ≤ 36 s |
| Oracle | 57,6 s · 171 MB | ≤ 43 s | no recomendado |
| SQLite (desde PG) | 21,3 s · 421 MB | ≤ 19 s y ≤ 200 MB | no aplica (se fuerza 1) |

Tolerancia de regresión: ≤ 5 % en cualquier motor o variante (mediana de 3).

## Resultado de la Fase 1 (2026-09-26, `large`, 3,5M filas)

| Motor | Línea base v0.15.0 | Tras Fase 0 + Fase 1 | Memoria pico |
|---|---|---|---|
| PostgreSQL | 19,1 s | ≈ 14,8 s | 417 → 170 MB |
| MySQL | 57,0 s | ≈ 38 s | 859 → 162 MB |
| MariaDB | 52,9 s | ≈ 37,5 s | 859 → 162 MB |
| SQL Server | 65,8 s | ≈ 57–63 s (ruidoso); ≈ 34–44 s con `parallel_pk_ranges=4` | 164 MB |
| Oracle | 57,6 s | ≈ 32–38 s | 171 MB |
| SQLite (desde PG) | 21,3 s | ≈ 19,8 s | 421 → 175 MB |

Detalle en las sesiones `2026-09-26g` (Q1), `2026-09-26i` (Q2), `2026-09-26j` (Q3) y `2026-09-26k` (Q4).

## Fase 2 — Medio plazo

| Paso | Mejora | Motores | Ganancia medida | Riesgo |
|---|---|---|---|---|
| 2.1 (Q5) | Separar tamaño de lectura y lote de escritura (PG COPY 20–50K, SQL Server ≤ 5K) | PG, mssql | PG −31 % con 20K; protege a mssql de +57 % | Bajo | **Hecho** (sesión `2026-09-26p-feature-dump-write-batch-size`: `write_batch_size`, PG −22 %) |
| 2.2 (Q6) | `manage_indexes` recomendado u automático en PG/mssql con volumen grande | PG, mssql | PG −23 %, mssql −16 % | Medio | **Hecho** (solo documentación: Oracle −14 %, SQL Server −8 %, PG neutro tras Q3; sin activación automática) |
| 2.3 | Aviso de `_warn_chunk_size` solo con columnas LOB/JSON | MySQL/MariaDB | — (ruido) | Bajo | **Hecho** (sesión `2026-09-26q-refactor-dump-lob-warning`) |

## Resultado de la Fase 2 (2026-09-26)

- **Q5**: `DumpConfig.write_batch_size`; PostgreSQL −22 % (lotes de 20 000 por defecto), resto sin cambios.
- **Q6**: solo documentación; tras Q3 la ganancia de `manage_indexes` es pequeña (Oracle −14 %, SQL Server −8 %, PG neutro).
- **2.3**: el aviso de `max_allowed_packet` solo sale con columnas TEXT/BLOB/JSON.
- Además: PF-09 (MariaDB Connector/Python con `executemany` del driver, −64 %) y PD-12 (UPDATE por staging sin BD por defecto).

## Fase 3 — Largo plazo

| Paso | Mejora | Ganancia estimada | Riesgo |
|---|---|---|---|
| 3.1 (Q8) | Ruta sin pandas: tuplas del cursor → estrategia de INSERT | Cota superior previa ≈ 7–8 s por volcado; tras P-33 algo menor (`prep` ya bajó ≈ 1,5 s) | Medio-alto |
| 3.2 (Q9) | Introspección por lotes y una sola reflexión por tabla | ≈ 1,5 min por 1000 tablas en SQL Server | Medio | **Replanteado** (sesión `2026-09-26s-q9-medicion`: SQL Server/MySQL/SQLite no implementan `get_multi_*` en SQLAlchemy 2.0.50; hoy SQL Server 177 ms/tabla, PG 53, MySQL 67) |
| 3.3 | Hipótesis: Oracle `/*+ APPEND_VALUES */` | Sin medir | Alto |
| 3.4 (PF-08, nuevo) | Resumen de auditoría sin releer todo el CSV (contadores del volcado + lectura acotada) | 0,72 s con 500K registros; 2,9 s con 2M (lineal) | Bajo | **Hecho** (sesión `2026-09-26r-refactor-dump-audit-summary-tail`: 0,69 → 0,01 s) |

## Descartado (con evidencia)

- Paralelizar PK sync (CB7), saltarse la validación de constraints (CB4), `collect_row_counts=False` por defecto (CB5),
  PostgreSQL COPY / SQL Server BULK INSERT / MySQL LOAD DATA: sin cambios respecto al roadmap previo.
- **Nuevo:** optimizar `to_datetime(format="mixed")` en la lectura del CSV de auditoría: 0,18 → 0,14 s con 500K
  registros; el coste está en `read_csv`.
- **Nuevo:** desactivar la auditoría de `bulk` en el volcado por rendimiento: coste ≤ ruido (±6 %).
