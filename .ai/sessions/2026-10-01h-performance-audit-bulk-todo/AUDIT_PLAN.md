# AUDIT_PLAN — implementación del roadmap de `bulk/` (Fases 0–2)

Revisión de `PLAN.md` contra el código (`e80059e`), contra mediciones previas del proyecto y con comprobaciones en los
servidores del banco (2026-10-01).

**Veredicto: GO_CONDICIONAL** — Fases 0 y 1.1–1.4 listas para implementar; 1.5 (B-04) y la parte MySQL/MariaDB de 2.3
(B-05) condicionadas a repetir mediciones; tres decisiones de comportamiento para el usuario (§ Decisiones).

## Supuestos verificados

| # | Supuesto del plan | Verificación | Resultado |
|---|---|---|---|
| V-1 | Las notas de excepción están disponibles | Python ≥ 3.12 (`pyproject.toml`); `BaseException.add_note` existe desde 3.11 | OK |
| V-2 | `restore_binary_values` admite `SqlColumns` | `sql_helpers.py:113-115` | OK |
| V-3 | `update()` de SQLAlchemy genera `UPDATE … FROM` en PG | Prototipo E4: 1M verificado | OK |
| V-4 | El usuario del banco puede crear temporales en PG | `has_database_privilege(current_database(), 'TEMP')` → `True` | OK |
| V-5 | El código de error es accesible por driver | psycopg `orig.sqlstate` (`42704`, `25P02`); oracledb `orig.args[0].code` = 60 / `full_code` = `ORA-00060`; PyMySQL `orig.args[0]` (`_mysql_errno`, `staging_update.py:133`) | OK |
| V-6 | El SQL de catálogo va en `metadata/` | Precedente `metadata/postgresql/tables.py:455` (`fetch_can_disable_triggers_sql`) usado desde `bulk/_support/dialect.py` | OK: 0.4 y 1.1 siguen el patrón |
| V-7 | `ParallelBulkLoader` usa una `BulkCrud` por partición durante todos sus intentos | `parallel_loader.py:394-423` (se crea antes del bucle de reintentos) | OK: `crud.rows_committed` es el prefijo de la partición en 2.1 |
| V-8 | `dump` construye el loader con `commit_every_n_chunks` del volcado | `dump/orchestrator.py:576,779-789` | OK: 2.1 también le afecta (ver R-7) |

## Riesgos y correcciones incorporadas al plan

### R-1 · PostgreSQL no admite el fallback «reaccionar al error» de MySQL (1.1) — CORREGIDO EN EL PLAN
En MySQL un `CREATE TEMPORARY TABLE` denegado no aborta la transacción (`staging_update.py:52-55`). En PG sí:
comprobado en el banco, tras un `CREATE` fallido cualquier sentencia da `InFailedSqlTransaction` (`25P02`); con
`begin_nested()` (savepoint) la transacción sigue viva. El plan usa una **comprobación previa** del privilegio TEMP
(una consulta por instancia). Alternativa si se prefiere no consultar: savepoint por lote (coste a medir).

### R-2 · `SqlColumns` troceado se convierte en dicts (0.3) — CORREGIDO EN EL PLAN
`BatchStatementExecutor._execute_on_connection` trocea con `records[start:start + chunk_size]` (`executors.py:330-331`) y
`SqlColumns.__getitem__(slice)` construye un dict por fila (`sql_helpers.py:62-63`): la mejora desaparecería sin que
falle ningún test. El plan añade `execute_columns` sin troceo por filas. Test obligatorio: espía de
`SqlColumns.__getitem__` que no debe llamarse en la vía columnas.

### R-3 · Un contador por instancia no da el prefijo de una operación (2.1) — CORREGIDO EN EL PLAN
`RowLedger` (`session.py:93-109`) es de la sesión: un commit periódico confirma también las filas pendientes de
operaciones anteriores (2a, v0.17.4). La diferencia de `rows_committed` antes/después de una llamada **no** es el
prefijo de esa llamada cuando hay varias operaciones en la misma `bulk_session`. El plan añade el sub-libro por
operación. En `ParallelBulkLoader` no hay problema (una sola operación por partición y `BulkCrud`, V-7).

### R-4 · OPENJSON y tipos de PK (0.4)
`json.dumps` no serializa `datetime`, `bytes` ni `Decimal`, y el `CAST` desde texto JSON depende del formato. El plan
limita OPENJSON a `int`, `str`, `Decimal` (como texto) y `UUID`; el resto usa la estrategia actual. Comprobar en
integración `VARCHAR` con espacios finales (comparación con `ANSI_PADDING`) y collation del `CAST` (`OPENJSON` devuelve
`nvarchar(max)`: con PK `VARCHAR` el `CAST` explícito evita la conversión implícita en la columna, que impediría el
uso del índice).

### R-5 · Paralelismo en MySQL/MariaDB: mediciones contradictorias (2.3, 2.4)
La auditoría midió INSERT 2,06×/1,88× y UPDATE 2,3×/1,8× con 2–4 hilos (datos en memoria). `DumpConfig` documenta
que `parallel_pk_ranges=4` **casi duplica el tiempo** en MySQL y MariaDB (`dump/_models.py:126-127`), aunque allí cada
hilo además lee del origen. Antes de documentar o recomendar paralelismo en MySQL/MariaDB: repetir E7 con
`--repeat 3` y una variante con lectura desde otra BD. Si se reproduce el empeoramiento, `update()/delete()` avisan en
MySQL/MariaDB como ya hace `dump`.

### R-6 · Tamaño de lote: SQL Server contradice la auditoría (1.5)
Para PG coinciden dos mediciones independientes: auditoría (6,0 → 4,8 s con 20.000) y `dump` (−31 % a 3,5M,
`dump/_models.py:130`). Para SQL Server, `dump` midió que 20.000 es **un 81 % más lento**, frente a −10 % en la
auditoría (una repetición). Conclusión: 1.5 solo puede cambiar PG (COPY) y el tope del `DELETE … IN` de MySQL/MariaDB;
SQL Server queda como está. Repetir E6 con `--repeat 3` antes de implementar. `dump` ya tiene el mecanismo
(`write_batch_size`): reutilizarlo en lugar de duplicarlo (mover la agrupación de chunks a `bulk/_support/`).

### R-7 · Reanudación dentro de `dump` (2.1)
Al retirar el `ValueError` de cadencia + reintentos, `dump` no cambia (no pasa `max_retries`, `orchestrator.py:779-789`),
pero conviene exponerlo después en `DumpConfig` (fuera de alcance; anotar en el CHANGELOG como posible siguiente paso).

### R-8 · Cambios de clasificación de reintentos (1.2)
Hoy se reintentan permanentes de PyMySQL y no el deadlock de Oracle. El cambio puede alterar el tiempo hasta fallar
de cargas existentes en ambos sentidos. Mitigación: CHANGELOG «Changed» con la tabla por driver y un parámetro
`retry_on: Callable[[BaseException], bool] | None` para quien necesite su propio criterio. El deadlock de SQL Server
con pyodbc no se ha reproducido: incluir un test de integración que lo provoque (dos conexiones, orden de bloqueo
cruzado) antes de dar por buena la regla del error nativo 1205.

### R-9 · Coste del DDL por lote en PG (1.1)
El prototipo crea y borra una temporal por lote (200 por millón): entradas en `pg_class`/`pg_attribute` y bloat del
catálogo en cargas muy largas. Medido sin problema a 1M; para 10M+, valorar una temporal por operación con
`TRUNCATE` entre lotes. Medir ambas en la sesión de 1.1 (10M filas) y elegir.

### R-10 · Superficie pública
Aditivos: `last_operation_rows_committed`, `retry_backoff`, `retry_on`, `PartitionResult.retry_wait_seconds`,
`bulk_update_from_chunks`, `bulk_delete_from_chunks`, `ParallelBulkLoader.update/delete`, `StagingUpdateStrategy`.
Cambios de comportamiento: staging en PG por defecto (1.1), qué se reintenta (1.2), espera entre reintentos por defecto
(1.3), cadencia + reintentos permitidos (2.1). Ninguna firma existente cambia. `.github/AGENTS.md` y prompts: sin cambios.

## Pruebas requeridas por punto

| Punto | Unit | Integración (5 servidores) | Banco (1M) |
|---|---|---|---|
| 0.2 | nota en INSERT/UPDATE/DELETE, tipo y `str` sin cambios | PK duplicada en PG y MySQL | — |
| 0.3 | equivalencia estricta dict ↔ columnas; espía R-2 | PG psycopg/psycopg2, MySQL, MariaDB con JSON/binarios/NULL | PG, MySQL, MariaDB INSERT |
| 0.4 | SQL y parámetro; fallback por tipo y por nivel | SQL Server: 5 tipos de PK, sesión, cadencia | SQL Server DELETE 1K–1M |
| 1.1 | perfiles por dialecto; sin TEMP → fallback | PG: equivalencia completa, `esquema.tabla`, rollback | PG UPDATE 1M y 10M (R-9) |
| 1.2 | tabla de excepciones por driver | deadlock real PG, MySQL, SQL Server | — |
| 1.3 | esperas con semilla, tope, `(0, 0)` | — | — |
| 1.4 | SQL compuesto | SQL Server PK compuesta | SQL Server DELETE 1M compuesta |
| 2.1 | sub-libro por operación (R-3), `_skip_rows` | fallo + reanudación sin duplicados, 6 motores | fallo al 60 %: ≤ 1,1× |
| 2.2 | equivalencia con `from_df`, cierre del generador | 5 servidores | — |
| 2.3 | particiones, errores, contadores | 5 servidores | UPDATE 1M 1/2/4 hilos ×3 (R-5) |

## Orden de ejecución confirmado
0.1 → 0.2 → 0.3 → 0.4 → 1.1 → 1.2 → 1.3 → 1.4 → `/version-closure` (minor) → 2.2 → 2.1 → 2.3 → 2.4 →
`/version-closure`. Respecto al PLAN, 2.2 pasa delante de 2.1: la reanudación de UPDATE/DELETE en el loader necesita las
vías `from_chunks`. 1.5 queda fuera hasta repetir E6 (R-6).

## Decisiones para el usuario
- **D-1** (1.1): ¿staging de UPDATE activo por defecto en PostgreSQL (como en MySQL, con fallback si falta TEMP)?
  Recomendado: sí.
- **D-2** (1.3): ¿espera por defecto entre reintentos `(0,5 s, 30 s)` o mantener `(0, 0)` y que quien quiera la active?
  Recomendado: `(0,5, 30)`; solo actúa si `max_retries > 0` (por defecto 0).
- **D-3** (2.1): ¿retirar el `ValueError` de cadencia + reintentos en `ParallelBulkLoader` y reanudar desde
  `rows_committed`? Recomendado: sí, documentando que el lector debe dar las filas en orden estable.
