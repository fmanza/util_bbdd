# Auditoría de rendimiento (delta) — módulo `dump`

- Fecha: 2026-09-25 · Rama: `develop` (`cfbbf05`, v0.15.0) · Skill: `/performance-audit-dump`
- Base: auditoría completa `2026-09-25-performance-audit-dump` (`5557688`). Este informe solo recoge lo que ha cambiado
  desde entonces; los hallazgos PF-01…PF-07 y el análisis CB1–CB8 de aquel informe siguen vigentes salvo lo indicado.
- Motores: PostgreSQL 17, MySQL 8.4, MariaDB 11.4, SQL Server 2022 (pyodbc), Oracle 23 Free, SQLite (destino desde PG).
- Volumen: `large` (3,5M filas). Mediciones: `validation_report_delta_20260925.md`.
- Sin cambios en `src/`. Cambios de la sesión: `scripts/bench_dump.py` (banco real) y guías que describen su CLI.

---

## 1. Resumen ejecutivo

1. **El volcado es un 5–25 % más rápido que en `5557688` sin tocar `dump`.** PostgreSQL 19,1 s (−25 %), SQLite 21,3 s
   (−17 %), Oracle 57,6 s (−14 %), MariaDB 52,9 s (−8 %), MySQL 57,0 s (−8 %), SQL Server 65,8 s (−5 %). La parte
   atribuible con confianza es la preparación de filas (`prep` −30 % en todos los motores, P-33 de `bulk`); el resto
   (PG `write`, Oracle `read`) no tiene un cambio de código que lo explique y se trata como variación de entorno.
2. **La auditoría de `bulk` en el volcado (área nueva) no es un cuello**: ≤ ruido (±6 %) con CSV nuevo. El resumen final
   relee todo el CSV histórico: 0,72 s con 500K registros, lineal (≈ 1,4 µs/registro). Hallazgo menor (PF-08).
3. **Los fallos de corrección siguen ahí.** De PD-01…PD-09 solo se ha corregido la mitad de PD-06 (limpieza SQLite).
   PD-02 (PK sync con `target_schema`) y PD-03 (redump PostgreSQL) se han reproducido de nuevo en esta sesión.
4. **La línea base ya se puede reproducir con el repo**: `scripts/bench_dump.py` es ahora el banco real (roadmap 1.5/Q7
   hecho), con variantes de auditoría y resumen por mediana. Las guías que describían el banco anterior están alineadas.

**Veredicto: APROBADO CON CONDICIONES** (sin cambio respecto a la auditoría previa): corregir PD-01, PD-02, PD-03,
PD-05 y PD-08 (Fase 0) antes de los quick wins de la Fase 1.

---

## 2. PLAN — qué ha cambiado desde `5557688`

| Commit | Cambio | Efecto en el camino del volcado |
|---|---|---|
| `e1adcc2` P-33 | Vía rápida de columnas de texto en `dataframe_to_sql_records` | Sí: `prep` de todas las tablas (medido −30 %) |
| `d8df978` P-34, `dde13b2` | Generación de SQL por columnas, literales binarios | No (`generar_sql=True`, no lo usa `dump`) |
| `6768d3f`, `161aae2`, `5de5843` | `bulk_audit_strict`, contadores de auditoría, auditoría activa también con `max_parallel_tables > 1` | Solo con `bulk_audit_path` (desactivado por defecto) |
| `0cd5d82`, `aa5829d` | Hojas «Auditoría Bulk» y «Secuencias PK» en el Excel | `report` sigue en 0,01–0,03 s |
| `cf0eafc` | SQLite: `DELETE FROM` en la limpieza | Corrige la mitad de PD-06; `cleanup` 2,6 s en `redump` |
| `1b072cf`, `bcf2bc7` | Retirada de `AuditTransaction`, tipado | Sin efecto en rendimiento |

Método: banco real (`scripts/bench_dump.py`), 6 motores × {`baseline`, `audit`} × 3 + `audit_history` × 3 (PG) +
`redump` × 1 (PG, SQLite) + microbanco aislado de `AuditManager.leer_auditoria`.

## 3. AUDIT_PLAN

| Comprobación | Resultado |
|---|---|
| ¿La línea base es comparable con la previa? | Sí en esquema, datos (mismos contenedores, `setup` no re-ejecutado) y banco (`summarize` reproduce las medianas previas). No en estado del entorno (contenedores reiniciados): solo se atribuyen diferencias con un commit que las explique. |
| ¿Se re-miden las variantes Q1–Q6? | No: el código que prueban no ha cambiado. Sus Δ relativos se mantienen como hipótesis con la nueva línea base. |
| ¿Cubre el área nueva? | Sí: `audit` (coste de escritura) y `audit_history` (coste del resumen con CSV grande). |

## 4. AUDIT_CODE — hallazgos nuevos o con estado cambiado

### PF-08 — El resumen de auditoría relee todo el CSV histórico en cada volcado
- **Severidad**: BAJA · **Archivos**: `dump/orchestrator.py` (`_build_audit_summary`), `bulk/_audit/repository.py:183-210`
- **Descripción**: `AuditManager(audit_path, cache_enabled=False).leer_auditoria()` carga el CSV completo con
  `pd.read_csv` y convierte `timestamp` y `tiempo_seg` de todas las filas, para quedarse luego con las del volcado actual
  (`timestamp >= desde`). El CSV crece sin límite (≈ 700 registros por volcado `large` con `chunk_size=5000`).
- **Evidencia**: 500K registros → 0,72 s dentro del volcado; microbanco 100K/500K/2M → 0,16/0,71/2,88 s (lineal,
  ≈ 1,4 µs/registro, 60 % en `read_csv`). `format="mixed"` no es la causa (0,18 s frente a 0,14 s con formato fijo).
- **Remediación** (no urgente): calcular el resumen con los registros que el volcado ya conoce (los contadores de
  `BulkCrud`/`ParallelLoadResult` ya existen) y leer el CSV solo para detectar escrituras ajenas; o leer el CSV por
  bloques descartando los anteriores a `desde`. Documentar mientras tanto la rotación del CSV.

### Coste de la auditoría activa (área nueva) — sin hallazgo
- `audit` frente a `baseline`: −1 % a +6 % en 5 motores; PostgreSQL +22 % con repeticiones 18,6/23,7/23,2 s y el aumento
  en `read`/`write`, no en la auditoría (que se escribe una vez por tabla tras el commit). Se trata como ruido.
- La auditoría con `max_parallel_tables > 1` (lock por ruta de CSV) no se ha medido: con 3 tablas encadenadas por FK no
  hay tablas del mismo nivel. Queda como hipótesis de bajo riesgo (una escritura por tabla).

### Estado de los fallos de corrección de la auditoría previa

| ID | Severidad | Estado | Evidencia en esta sesión |
|---|---|---|---|
| PD-01 | CRÍTICA | Abierto | `validation.py:56-69` y `crud.py:856` sin cambios (el banco sigue usando columnas en MAYÚSCULAS en mssql) |
| PD-02 | ALTA | **Abierto, reproducido** | Sonda de identidad 0/n en PostgreSQL y Oracle; `pk_sync = []`; `orchestrator.py:834` sin cambios |
| PD-03 | ALTA | **Abierto, reproducido** | `redump` PG: `customers`/`orders` en `error` (`UniqueViolation`) |
| PD-04 | ALTA | Abierto | `_constraints.py` sin cambios en la validación PG |
| PD-05 | ALTA | Abierto | `read_sql` sin `coerce_float=False`; `strip()` conservado en la vía rápida P-33 (`normalize.py:255`) |
| PD-06 | MEDIA | **Mitad corregida** | Limpieza SQLite con `DELETE FROM` (`cf0eafc`), `redump` 3/3 `success`; `parallel_pk_ranges` sin limitar en SQLite |
| PD-07 | BAJA | Abierto | Sin validación del dialecto de origen |
| PD-08 | ALTA | Abierto | `crud.py:888,893` sin `resolve_fks=False` |
| PD-09 | MEDIA | Abierto | `_constraints.py:149-153` sin comprobación de `dbapi_conn is None` |

### CB1–CB8 con la nueva línea base
Sin cambios de veredicto. Pesos actuales (media de los 6 motores): escritura 45–75 %, lectura 18–41 %, `prep` 6–18 %
(antes 7–25 %), resto < 2 %. CB2 baja de «moderado» a «menor» tras P-33.

### PF-07 — Banco y guías: **corregido en esta sesión**
- `scripts/bench_dump.py` sustituido por el banco real (subcomandos `setup`/`run`/`one`/`summarize`/`list`; variantes
  nuevas `audit` y `audit_history`; informes y CSV en un directorio temporal borrado al terminar; SQLite en `<tmp>`).
- Guías alineadas con la nueva CLI: `docs/PERFORMANCE_AUDIT_GUIDE.md`, `.claude/performance-audit-guide.md` (incluye
  aviso de que `/quick-bench`, `/perf-proposal` y `/perf-validate` no son slash commands, y cifras «típicas» sustituidas
  por las medidas), `.github/prompts/performance_audit_dump_agent.prompt.md`, `.claude/commands/performance-audit-dump.md`.
- Pendiente: la tabla «Multi-Dialect Considerations» y los objetivos de mejora de `.claude/performance-audit-guide.md`
  siguen sin origen medido (fuera del alcance de esta sesión).

## 5. Priorización (cambios frente a la auditoría previa)

| ID | Cambio |
|---|---|
| Q7 (1.5) | **Hecho** en esta sesión |
| PD-06 (0.4) | Reducido a «forzar `parallel_pk_ranges`/`max_parallel_tables` = 1 en SQLite con aviso» |
| PF-08 | Nuevo, Fase 3 (prioridad 2/(2×1) = 1,00 si hay CSV de auditoría de larga vida; si no, despreciable) |
| Resto | Sin cambios. Las métricas de éxito de la Fase 1 se recalculan sobre la nueva línea base (roadmap) |
