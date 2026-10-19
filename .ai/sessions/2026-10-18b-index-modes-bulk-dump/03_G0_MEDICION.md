# G0 — Medición de modos de índices y FK checks (2026-10-18/19)

Script: `scripts/bench_index_modes.py` (DDL directo en modo autónomo; carga con `BulkCrud.bulk_insert_from_df`).
Banco: PostgreSQL 17.11, MySQL 8.4.11, MariaDB 11.4.13, SQL Server 2022 (16.0.4295.3, pyodbc + ODBC 18, puerto 51833),
Oracle Free 23.26.3 (2 CPU). Calentamiento 1 tanda; 3 repeticiones (Oracle confirmación: 5) en orden alterno.
Cifras: mediana del **total** (desactivar + cargar + reconstruir), en segundos; Δ frente a `none` del mismo grupo.
«Gana» = criterio D3 (≥ 5 % y rangos intercuartílicos sin solape). Ficheros: `build/logs/bench_index_modes_*2026101[89].*`.

Perfiles: `sec2u` = PK + 2 secundarios no únicos (`a`, `b`, 1000 valores distintos) + 1 UNIQUE (`s1`);
`sec5u` = PK + 5 secundarios + 1 UNIQUE; `sec0`/`sec2` sin UNIQUE; `fk2` = `sec2` con FK en `a` y `b`.

## 1. Comprobaciones de corrección (`--probes`)

| Motor | Comprobación | Resultado |
|---|---|---|
| SQL Server | Heap con PK NONCLUSTERED + FK entrante, `ALTER INDEX ALL … DISABLE` | PK deshabilitada, **PK duplicada aceptada**, FK entrante `is_disabled=1, is_not_trusted=1` |
| SQL Server | … tras `ALTER INDEX ALL … REBUILD` | PK vuelve; **FK entrante sigue deshabilitada** → hotfix v3.1.1 (`5f11ffcb`) |
| MySQL 8.4 | `DROP INDEX` requerido por FK, `FOREIGN_KEY_CHECKS` 1 y 0 | Rechazado siempre (1553) |
| MariaDB 11.4 | ídem | Rechazado con 1; **permitido con 0** (la FK queda sin índice) |

## 2. En serie — criterio D3 a 3,5M filas (`sec2u`, orden de PK)

| Motor | `none` | `secondary` | `all` | Reconstruir (`all`) |
|---|---|---|---|---|
| PostgreSQL | 30,17 | 22,67 (**+24,8 %**) | 17,09 (**+43,4 %**) | 5,19 |
| MySQL | 82,30 | 68,81 (**+16,4 %**) | 62,97 (**+23,5 %**) | 7,27 |
| MariaDB | 67,51 | 61,51 (**+8,9 %**) | 57,66 (**+14,6 %**) | 6,36 |
| SQL Server | 75,52 | 58,83 (**+22,1 %**) | 51,86 (**+31,3 %**) | 2,96 |
| Oracle | 448,10 | 52,85 (**+88,2 %**) | 47,30 (**+89,4 %**) | 17,28 |

Todos ganan en ambos modos. En SQL Server, MySQL y MariaDB `all` no toca la PK (clustered).

### 1M filas (orden de PK)

| Motor | `sec2u`: secondary / all | `sec5u`: secondary / all |
|---|---|---|
| PostgreSQL | +20,4 % / +33,4 % | +38,9 % / +47,6 % |
| MySQL | +16,4 % / +22,3 % | +24,6 % / +30,9 % |
| MariaDB | +8,2 % / +7,5 % (**no gana**: solape) | +18,3 % / +22,5 % |
| SQL Server | +38,3 % / +48,5 % | +59,6 % / +66,2 % |
| Oracle | +84,8 % / +87,5 % | +95,5 % / +96,0 % |

### Orden aleatorio (1M, `sec2u`)

| Motor | secondary | all |
|---|---|---|
| PostgreSQL | +12,5 % | +42,3 % |
| MySQL | +7,5 % | +18,9 % |
| MariaDB | +12,8 % | +22,8 % |
| SQL Server | +31,5 % | +48,1 % |
| Oracle | +62,7 % | +96,4 % |

Con filas desordenadas `all` gana más (la PK y el UNIQUE se mantienen fuera de orden).

### Oracle: confirmación (1M, 5 repeticiones)

| Perfil | `none` | `secondary` | `all` |
|---|---|---|---|
| `sec0` (solo PK) | 9,39 | 9,31 (+0,8 %) | 9,33 (+0,7 %) |
| `sec2` | 69,29 | 11,34 (**+83,6 %**) | 10,90 (**+84,3 %**) |

Sin secundarios, 1M filas en ~9 s (coherente con `bench_parallel`, 10,5 s). Dos índices no únicos de baja cardinalidad
multiplican la carga por ~7 en Oracle Free (2 CPU). El efecto es real; su magnitud en servidores reales puede ser menor.

## 3. Paralelo (4 hilos, 1M, `sec2u`, orden de PK)

| Motor | Constraints | `none` | `secondary` | `all` |
|---|---|---|---|---|
| PostgreSQL | on / off | 3,60 / 3,73 | −4,2 % / −2,7 % | **−41,2 % / −38,2 %** |
| MySQL | on / off | 11,59 / 11,85 | +4,0 % / +5,8 % | −9,8 % / −4,3 % |
| MariaDB | on / off | 9,27 / 9,40 | −10,7 % / −11,2 % | −18,3 % / −15,0 % |
| SQL Server | on / off | 10,05 / 10,60 | **+34,2 % / +31,5 %** | **+32,9 % / +33,1 %** |
| Oracle | on / off | 92,42 / 70,82 | **+82,4 % / +81,1 %** | **+87,2 % / +81,6 %** |

Con 4 hilos la carga ya reparte el coste de los índices y la reconstrucción (en serie) no se amortiza en PostgreSQL,
MySQL y MariaDB: **pierden**. SQL Server y Oracle siguen ganando.

**Hallazgo (fallo en código publicado)**: Oracle, 4 hilos, `ParallelOptions(disable_constraints=True)`: tras la carga la
UNIQUE `uq_zz_bench_ix_s1` queda **DISABLED y sin índice** (4 de 6 tandas de `none`/`secondary`; «Restaurado: no»).
Hipótesis: cada worker ejecuta su `maintenance_scope` (en Oracle no hay desactivación previa al pool) y un
`ENABLE VALIDATE` concurrente con otro worker aún insertando falla con un aviso que no llega al resultado. `dump` no está
afectado (`ConstraintManager` desactiva una vez). Pendiente de RCA → candidato a hotfix.

## 4. MariaDB/MySQL: FK checks y `unique_checks` (1M, `fk2`)

| Motor | Base | `FOREIGN_KEY_CHECKS=0` | `unique_checks=0` | Ambos |
|---|---|---|---|---|
| MySQL | 22,69 | 20,66 (**−9 %**) | 21,90 (−3,5 %) | 20,58 (−9 %) |
| MariaDB | 19,22 | 17,41 (**−9 %**) | 18,45 (−4 %) | 16,87 (−12 %) |

- Los modos de índices no hacen nada en `fk2`: los dos secundarios los requiere una FK y se omiten (regla del PLAN).
- `FOREIGN_KEY_CHECKS=0` (ya existente con `disable_constraints=True`) gana un 9 % estable.
- `unique_checks=0` **no está bien medido**: `fk2` no tiene UNIQUE secundario. Pendiente con `sec2u`.

## 5. Consecuencias para el PLAN

| Grupo | Decisión con G0 |
|---|---|
| G1–G3 (`"secondary"` en serie) | **Justificado en los 5 motores** (D3 a 3,5M) |
| G6 (InnoDB DROP/ADD) | **Sube a 3.2.0**: MySQL +16 %, MariaDB +9 % a 3,5M; el argumento del change buffer no vale en estas versiones |
| G5 (`"all"`) | Justificado en los 5 motores en serie (+15 % a +89 % a 3,5M); sigue en 3.3.0 con las salvaguardas del AUDIT_PLAN |
| G4 (`ParallelOptions.disable_indexes`) | Con `"secondary"` compensa en SQL Server (−33 %), Oracle (−82 %) y poco en MySQL (−4 a −6 %); **empeora** en PostgreSQL (+3 a +4 %) y MariaDB (+11 %). Con `"all"` empeoran los tres. Decisión del usuario: aplicarlo y avisar; nunca automático |
| G5b (`validate_fks_after`) | Coste no medido todavía |
| `unique_checks` | Pendiente de medir con `sec2u` |

## 6. Pendientes de G0

- `unique_checks=0` con `sec2u` (MySQL/MariaDB).
- Coste de `validate_fks_after` (orphan-check) y de `WITH CHECK CHECK CONSTRAINT` en SQL Server (T2).
- `"all"` con FK entrantes (PostgreSQL/Oracle: retirada y recreación de FK hijas).
- RCA del fallo de Oracle en paralelo con `disable_constraints=True`.
