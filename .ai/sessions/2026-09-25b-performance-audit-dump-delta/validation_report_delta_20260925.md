# Informe de validación (delta) — módulo `dump`

- Fecha: 2026-09-25 · Rama: `develop` (`cfbbf05`, v0.15.0) · Banco: `scripts/bench_dump.py` (nuevo, banco real)
- Comparación: línea base de la auditoría previa (`5557688`, sesión `2026-09-25-performance-audit-dump`)
- Volumen `large` = 500K `customers` + 1M `orders` + 2M `order_items` = 3,5M filas. Mediana de 3 repeticiones salvo `redump` (1).
- Datos crudos: `results/results.jsonl`. Tabla completa: `python scripts/bench_dump.py summarize results/results.jsonl`.

## 1. Línea base actual frente a la previa

| Motor | Previa (s) | Actual (s) | Δ | read | prep | write | RSS (MB) | Verificación | Identidad |
|---|---|---|---|---|---|---|---|---|---|
| PostgreSQL | 25,5 | **19,1** | −25 % | 6,81 → 6,33 | 4,85 → 3,53 | 13,15 → 8,96 | 400 → 417 | 3/3 | **0/3** (PD-02) |
| MySQL | 61,9 | **57,0** | −8 % | 20,77 → 20,74 | 5,13 → 3,89 | 34,76 → 31,85 | 841 → 859 | 3/3 | 3/3 |
| MariaDB | 57,2 | **52,9** | −8 % | 20,89 → 20,68 | 5,01 → 3,70 | 30,69 → 28,00 | 842 → 859 | 3/3 | 3/3 |
| SQL Server (pyodbc) | 69,0 | **65,8** | −5 % | 11,81 → 12,14 | 5,50 → 3,70 | 50,66 → 49,04 | 146 → 164 | 3/3 | 3/3 |
| Oracle | 67,0 | **57,6** | −14 % | 27,84 → 23,61 | 4,94 → 3,44 | 31,21 → 29,26 | 154 → 171 | 3/3 | **0/3** (PD-02) |
| SQLite (desde PG) | 25,6 | **21,3** | −17 % | 6,57 → 6,13 | 5,98 → 3,66 | 12,65 → 11,35 | 404 → 421 | 3/3 | 3/3 |

Atribución:

- **`prep` baja 1,2–2,3 s en los 6 motores** (≈ −30 %): coherente con P-33 (vía rápida de columnas de texto en
  `dataframe_to_sql_records`, `e1adcc2`), único cambio en esa ruta desde `5557688`. Atribución con confianza alta.
- **`write` de PostgreSQL baja 4,2 s** y **`read` de Oracle 4,2 s**: ningún commit toca la lectura de `dump` ni la
  estrategia COPY. Parte del `write` de PostgreSQL puede ser la misma conversión (el `write` instrumentado incluye la
  preparación de filas dentro de `BatchStatementExecutor.execute`), pero no está demostrado. Los contenedores se
  reiniciaron antes de medir (cachés frías, otro reparto de memoria): tratar el resto como variación de entorno.
- Memoria pico: +17 MB en todos los motores (≈ +4 %, dentro del ruido de proceso). PF-02 sigue abierto (PG/MySQL/MariaDB
  materializan la tabla mayor: 417–859 MB).

## 2. Auditoría de `bulk` dentro del volcado (área nueva)

| Motor | baseline (s) | `audit` (s) | Δ | `audit_summary` (s) |
|---|---|---|---|---|
| PostgreSQL | 19,1 | 23,2 | +22 % (ver nota) | 0,03 |
| MySQL | 57,0 | 58,6 | +3 % | 0,01 |
| MariaDB | 52,9 | 54,0 | +2 % | 0,01 |
| SQL Server | 65,8 | 65,1 | −1 % | 0,01 |
| Oracle | 57,6 | 61,3 | +6 % | 0,01 |
| SQLite | 21,3 | 21,6 | +1 % | 0,01 |

- Nota PostgreSQL: repeticiones 18,6 · 23,7 · 23,2 s; el aumento se reparte entre `read` y `write` (no en la auditoría,
  que escribe una vez por tabla tras el commit), y `audit_history` —que también audita— da 19,9 s. Se trata como ruido.
- **Conclusión: el coste de la auditoría es ≤ ruido (±6 %)** con un CSV nuevo. Todas las mediciones con auditoría
  verifican (`audited_rows` = filas cargadas, `audit_failures = 0`).

### Resumen del CSV con historial (`audit_history`, PostgreSQL)

- CSV con 500.000 registros previos: `audit_summary` = **0,72 s** (total 19,9 s, +4 % frente a baseline).
- Microbanco aislado de `AuditManager.leer_auditoria` (sin BD):

| Registros | Tamaño | `leer_auditoria` | `read_csv` | `to_datetime` `mixed` | `to_datetime` formato fijo |
|---|---|---|---|---|---|
| 100.000 | 7,2 MB | 0,16 s | 0,09 s | 0,04 s | 0,03 s |
| 500.000 | 35,8 MB | 0,71 s | 0,40 s | 0,18 s | 0,14 s |
| 2.000.000 | 143,3 MB | 2,88 s | 1,64 s | 0,73 s | 0,54 s |

- Coste lineal ≈ 1,4 µs/registro, dominado por `read_csv`. Un volcado `large` añade 700 registros: 2M registros son
  ≈ 2.800 volcados. `format="mixed"` **no** es el cuello (−25 % de 0,18 s con formato fijo).

## 3. Re-verificación de fallos de corrección

| Hallazgo | Prueba | Resultado |
|---|---|---|
| PD-02 (PK sync con `target_schema`) | Sonda de identidad en las 21 mediciones | **Sigue abierto**: PostgreSQL y Oracle 0/n; `pk_sync = []` en todas |
| PD-03 (TRUNCATE PG de tablas referenciadas) | `redump` PostgreSQL | **Sigue abierto**: `customers` y `orders` en `error` (`UniqueViolation … COPY`) |
| PD-06 (SQLite, limpieza) | `redump` SQLite | **Corregido** (`cf0eafc`): 3/3 `success`, `cleanup` = 2,61 s (DELETE de 3,5M filas) |
| PD-06 (SQLite, `parallel_pk_ranges`) | Revisión de código | **Sigue abierto**: `_resolve_range_count` no limita SQLite |
| PD-01, PD-04, PD-05, PD-07, PD-08, PD-09 | Revisión de código (sin cambios en las líneas afectadas) | **Siguen abiertos** |

## 4. Límites

- Una sola sesión de medición tras reiniciar los contenedores; el ruido entre repeticiones llegó a ±20 % en una variante
  (PostgreSQL `audit`) y a +27 % en un arranque en frío (MySQL `baseline` #1, 71,8 s). Las medianas lo absorben.
- `redump` con 1 repetición: solo se usa como prueba de corrección, no de tiempo.
- No se re-midieron las variantes de optimización (Q1–Q6): el código que prueban no ha cambiado; sus ganancias relativas
  se mantienen como hipótesis con la nueva línea base (ver roadmap).
