# Roadmap de mejora — módulo `dump`

> **Histórico.** Versión vigente: `.ai/sessions/2026-09-25b-performance-audit-dump-delta/improvement_roadmap_dump.md` (estado de cada paso y nueva línea base v0.15.0).

- Origen: `audit_report_dump_20260925.md` (hallazgos PD-xx de corrección y PF-xx de rendimiento) y `validation_report_20260925.md` (mediciones).
- Base de comparación: línea base `large` (3,5M filas) de la sesión `2026-09-25-performance-audit-dump`.
- Cada paso se entrega con su propio flujo (`/hotfix` para PD-xx, `/refactor` o `/new-feature` para Q-xx) y con una medición antes/después con `bench/bench_dump_real.py` (a llevar a `scripts/`, Q7).

## Fase 0 — Correcciones (antes que cualquier optimización)

| Paso | Hallazgo | Cambio | Flujo | Criterio de aceptación |
|---|---|---|---|---|
| 0.1 | PD-01 (CRÍTICA) | Casar columnas DataFrame ↔ tabla reflejada sin distinguir mayúsculas en `bulk` (mssql y resto), sin forzar un case por dialecto | `/hotfix` | `dump` y `BulkCrud` a SQL Server con columnas en minúsculas y en mixto: 3/3 tablas `success`. Test de integración mssql con columnas en minúsculas. |
| 0.2 | PD-02 (ALTA) | `_sync_pk_sequences` con el nombre lógico `esquema.tabla` | `/hotfix` | Sonda de identidad OK en PostgreSQL y Oracle con `target_schema`; `pk_sync_results` no vacío. |
| 0.3 | PD-03 (ALTA) | Limpieza en PostgreSQL con un único `TRUNCATE t1, t2, …` | `/hotfix` | Variante `redump` en PostgreSQL: 3/3 `success`. |
| 0.4 | PD-06 (MEDIA) | SQLite: `DELETE FROM` en la limpieza; `parallel_pk_ranges`/`max_parallel_tables` forzados a 1 con aviso | `/hotfix` | `redump` y `ranges4` en SQLite: 3/3 `success` y verificación OK. |
| 0.5 | PD-04 (ALTA) | Validación real de FKs en PostgreSQL (`NOT VALID` + `VALIDATE`, o comprobación de huérfanas) | `/hotfix` | Con una fila huérfana, el `ConstraintResult` sale `failed`. Coste de validación < 2 % del total a 3,5M filas. |
| 0.6 | PD-05 (ALTA) | Lectura sin pérdida: `coerce_float=False` + dtypes nullable (o `dtype_backend="pyarrow"`) en `read_sql`; no hacer `strip()` en la ruta de `dump` | `/hotfix` | Round-trip exacto de BIGINT > 2^53 con NULL, DECIMAL(38,10) y cadenas con espacios en los extremos. Medir que el tiempo de `read` + `prep` no empeora > 10 %. |
| 0.7 | PD-08 (ALTA) | `reflect_table` con `resolve_fks=False` (o `MetaData` compartido por instancia) | `/hotfix` | Volcado de 200 tablas encadenadas por FK sin `RecursionError`; reflexión de la cadena de 100 tablas en PostgreSQL < 5 s (hoy 45,6 s). |
| 0.8 | PD-09 (MEDIA) | `_fk_on`/`_fk_off` ignoran `dbapi_conn is None` | `/hotfix` | Un error durante la carga en MySQL/MariaDB llega intacto a quien llama. |
| 0.9 | PD-07 (BAJA) | Rechazar o avisar de un origen SQLite | `/hotfix` | Error claro en `DumpOrchestrator.__init__`. |

## Fase 1 — Quick wins (1–2 semanas)

| Paso | Mejora | Motores | Ganancia medida (large) | Riesgo | Notas |
|---|---|---|---|---|---|
| 1.1 (Q1) | `cursor.arraysize = chunk_size` en las lecturas de `dump` en Oracle | Oracle | **−29 %** (mediana de 3; lectura 27,5 → 8,3–9,8 s) | Bajo | Mayor contra un servidor remoto. No combinar con 1.3 ni con rangos en Oracle hasta medirlo con la implementación real (con el prototipo empeora). |
| 1.2 (Q2) | `stream_results=True, max_row_buffer=chunk_size` en la conexión de lectura (`_load_whole_table` y `_make_reader`) | PG, MySQL, MariaDB (en mssql/oracle es neutro) | Memoria pico −62 % (PG) / −83 % (MySQL/MariaDB); tiempo ±5 % | Bajo | Requisito de 1.3 en MySQL/MariaDB. |
| 1.3 (Q3) | Solape lectura/escritura: generador con 1 hilo lector y cola acotada (2 chunks), con propagación de errores y cierre | PG, MySQL, MariaDB, SQL Server, SQLite (Oracle: desactivado) | Validado junto con 1.2: PG −45 % (con lotes de 20K), MySQL −31 %, MariaDB −25 %, SQLite −16 %; SQL Server −19 % (1 rep.) | Medio | Prototipo en `bench/bench_dump_real.py::prefetch`. Encaja en `_load_whole_table` sin cambiar la API de `bulk`. |
| 1.4 (Q4) | Guía por motor para `parallel_pk_ranges` + aviso en MySQL/MariaDB (+14 %/+27 %) | todos | SQL Server −48 % (4 rangos + `stream_results`, mediana de 3; 8 rangos −2 %); PG −35 % y Oracle −23 % (1 rep.) | Bajo | Documentar la capacidad del pool necesaria (`pool_size ≥ rangos × tablas`). En PG no combinar con `stream_results` (+2 %, causa sin aclarar). |
| 1.5 (Q7) | Sustituir `scripts/bench_dump.py` por el banco real; corregir `.claude/performance-audit-guide.md`, `docs/PERFORMANCE_AUDIT_GUIDE.md` y los prompts `performance_audit_dump*` (cifras sin medir, comandos inexistentes, propuestas ya implementadas) | — | — | Bajo | Sin esto, la próxima auditoría vuelve a partir de una línea base falsa. |

**Métrica de éxito de la Fase 1 (large, mediana de 3):**

| Motor | Línea base | Objetivo tras la Fase 1 (sin paralelismo) | Con `parallel_pk_ranges=4` (opt-in) |
|---|---|---|---|
| PostgreSQL | 25,5 s | ≤ 16 s (con 2.1, lotes de 20K) y memoria ≤ 200 MB | no combinar con `stream_results` |
| MySQL | 61,9 s | ≤ 45 s y memoria ≤ 200 MB | no recomendado |
| MariaDB | 57,2 s | ≤ 45 s y memoria ≤ 200 MB | no recomendado |
| SQL Server | 69,0 s | ≤ 60 s | ≤ 38 s |
| Oracle | 67,0 s | ≤ 50 s | no recomendado (peor que `arraysize` solo) |
| SQLite (desde PG) | 25,6 s | ≤ 23 s y memoria ≤ 200 MB | no aplica (se fuerza 1) |

Las cifras exactas combinadas están en `validation_report_20260925.md` §2. Tolerancia de regresión: ≤ 5 % en cualquier motor o variante.

## Fase 2 — Medio plazo (2–4 semanas)

| Paso | Mejora | Motores | Ganancia medida | Riesgo |
|---|---|---|---|---|
| 2.1 (Q5) | Separar el tamaño de lectura del lote de escritura (o fijar un lote por motor): PostgreSQL COPY 20–50K, SQL Server ≤ 5K | PG, mssql | PG −31 % con 20K; protege a mssql de +57 % | Bajo |
| 2.2 (Q6) | `manage_indexes` recomendado u opcional-automático con volumen grande en PG/mssql | PG, mssql | PG −23 %, mssql −16 % | Medio (PG hace DROP/CREATE; el DDL se registra en el log antes) |
| 2.3 | Aviso de `_warn_chunk_size` solo si la tabla tiene columnas LOB/JSON | MySQL/MariaDB | — (ruido) | Bajo |

## Fase 3 — Largo plazo (1–2 meses)

| Paso | Mejora | Motores | Ganancia estimada | Riesgo |
|---|---|---|---|---|
| 3.1 (Q8) | Ruta sin pandas: tuplas del cursor (`fetchmany`) → estrategia de INSERT (COPY `write_row`, `executemany` de tuplas), con los conversores de tipo por columna resueltos una vez por tabla | todos | Microbanco de lectura: pandas cuesta 4,2–9,5 s por 2M filas → cota superior ≈ 7–8 s por volcado de 3,5M filas (PG −69 % en lectura + preparación, SQL Server −44 %, MySQL −32 %). Corrige PD-05 de raíz. | Medio-alto: nueva API en `bulk` (`bulk_insert_from_rows`) y conversión por tipo en lugar de por valor |
| 3.2 (Q9) | Introspección por lotes con `Inspector.get_multi_columns/get_multi_foreign_keys/get_multi_pk_constraint` y una sola reflexión por tabla compartida entre `dump` y `bulk` | todos | Hoy, análisis + reflexión: 95 ms/tabla (SQL Server), 54 (Oracle), 42 (PG) → ≈ 1,5 min por 1000 tablas en SQL Server | Medio |
| 3.3 | Hipótesis a medir: Oracle `/*+ APPEND_VALUES */` en el INSERT por arrays (direct path) | Oracle | Sin medir | Alto (bloqueo exclusivo de la tabla, ORA-12838 si se lee en la misma transacción) |

## Descartado (con evidencia)

- **Paralelizar PK sync (CB7)**: cuesta milisegundos por tabla una vez corregido PD-02.
- **Saltarse la validación de constraints (CB4)**: ahorra < 1 s a 3,5M filas (SQL Server 0,47 s, Oracle 0,73 s) a cambio de perder integridad.
- **`collect_row_counts=False` por defecto (CB5)**: < 1 % con tablas grandes y 6–18 % con cientos de tablas pequeñas (3,5–13 ms/tabla). Se mantiene `True` por defecto porque el informe pierde la volumetría; conviene documentarlo como palanca para esquemas con muchas tablas.
- **PostgreSQL COPY, SQL Server BULK INSERT, MySQL LOAD DATA** (propuestas del prompt): COPY ya existe (v0.10.0); la carga nativa de SQL Server se descartó con medición en P-17 (auditoría de `bulk`); `LOAD DATA LOCAL INFILE` exige `local_infile` y fichero intermedio, y ya se descartó en el diseño de `MySQLMultiRowInsertStrategy`.

## Issues sugeridos

Una issue por paso de las Fases 0 y 1, con la plantilla de `.claude/performance-audit-guide.md` («Integración con GitHub Roadmap»), etiquetas `performance`/`bug`, `dump` y `P0`/`P1`, y el enlace a este roadmap.
