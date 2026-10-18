# PLAN — Modos de índices (ninguno / secundarios / todos) y FK checks compartidos por `bulk` y `dump`

> Versión consolidada: PLAN inicial + ampliación de modos y medición + `FOREIGN_KEY_CHECKS`. Las correcciones del
> AUDIT_PLAN (`02_AUDIT_PLAN.md` § Condiciones) **prevalecen** sobre este documento donde lo contradigan.

## 1. Objetivo

Acelerar la carga final por tabla en `bulk` (y unificar con `dump`) permitiendo desactivar los índices del destino
durante la carga y reconstruirlos al final, con tres modos: ninguno, solo secundarios no únicos, o todos los posibles.
Contexto de uso: cargas en varias iteraciones de calidad; la final, con datos ya validados, busca el máximo rendimiento.

## 2. Diagnóstico del estado actual

| Motor | `dump.IndexManager` (`dump/_indexes.py`) | `bulk` `TableMaintenance._disable_indexes` (`bulk/_execution/maintenance.py:213`) |
|---|---|---|
| SQL Server | `DISABLE`→`REBUILD` por índice, NONCLUSTERED **no únicos** | `ALTER INDEX ALL … DISABLE` **solo si la tabla es heap** |
| Oracle | `UNUSABLE`→`REBUILD` | nada |
| PostgreSQL | `DROP` + recreate desde `pg_get_indexdef` (DDL logueado antes) | nada |
| MariaDB/MySQL | no soportado | `DISABLE KEYS` solo MyISAM/Aria (InnoDB se omite: commit implícito, hallazgo 8 de 2026-09-24) |
| Transacción | conexión propia, commit por índice | conexión de `bulk_session`, sin commit propio |
| Resultado | `IndexActionResult` por índice + hoja «Índices» + evento de auditoría | `bool` interno; nada en `MaintenanceScopeResult` |
| Paralelo | desactivación global una vez | `ParallelBulkLoader` fuerza `disable_indexes=False` (`parallel_loader.py:846`, lock SCH-M) |

Problemas de `bulk`:

- SQL Server: prácticamente no-op (casi toda tabla tiene PK clustered).
- SQL Server en heaps: `ALL DISABLE` desactiva también PK/UNIQUE NONCLUSTERED → sin control de unicidad y FK entrantes
  deshabilitadas por el motor (verificar en banco si `REBUILD` las reactiva y deja *trusted*).
- Oracle y PostgreSQL sin soporte; semántica distinta de `dump`.

`FOREIGN_KEY_CHECKS` ya se usa en la ruta de constraints: `bulk` lo fija en la conexión de la sesión
(`maintenance.py:177/273`), `dump` con eventos `checkout`/`checkin` del pool (`dump/_constraints.py:165`). Al reactivar
no valida retroactivamente (resultado `unverified`).

Hallazgo: en Oracle, con `disable_constraints=True`, `bulk` (`maintenance.py:383`) y `dump` (`_constraints.py:385`)
**ya desactivan las UNIQUE** (lo que elimina su índice si lo creó la constraint; `ENABLE VALIDATE` lo recrea).

## 3. ¿Compartir estrategia? Sí

- El catálogo ya está compartido: `metadata.facts.secondary_nonunique_indexes`.
- Lo duplicado y divergente es el SQL de desactivar/restaurar y la selección de índices.
- Precedente de ubicación: `bulk/_support/dialect.py` (usado por `maintenance_scope`, `ParallelBulkLoader` y
  `dump.ConstraintManager`). `dump → bulk._support` y `bulk → metadata` ya existen: el diagrama de capas no cambia.
- Lo que **no** se comparte es la ejecución (semántica transaccional distinta, § 4.2).

## 4. Diseño

### 4.1 Componente compartido `bulk/_support/secondary_indexes.py` (nuevo)

- `SecondaryIndex` (frozen): `table`, `name`, `ddl | None`, `kind` (`secondary` / `unique` / `pk`).
- `SecondaryIndexStrategy` por motor, sin estado: `discover(conn, schema, table, mode)`, `disable_sql(idx)`,
  `restore_sql(idx)`, `ok_action` (`rebuilt` / `recreated`).
- `strategy_for(dialect) -> SecondaryIndexStrategy | None`.
- `IndexActionResult` se traslada a `bulk/_models.py`; `dump/_models.py` lo reexporta (mismo objeto).
- Nuevo `IndexMode = Literal["secondary", "all"]`.
- Nueva `IndexRebuildError` en `_core/exceptions.py` (reexportada en `util_bbdd.exceptions`).

### 4.2 Dos modos de ejecución

| Modo | Quién | Comportamiento |
|---|---|---|
| **Autónomo** (conexión propia, commit por índice, tolerante) | `dump.IndexManager`, desactivación previa de `ParallelBulkLoader` | Igual que `IndexManager` hoy |
| **En sesión** (conexión de `bulk_session`, sin commit) | `TableMaintenance` | SQL Server/PostgreSQL: DDL transaccional con `SAVEPOINT` por índice (`begin_nested`); rollback deshace todo. Oracle: commit implícito (como H-31), restauración en conexión nueva tras rollback (`after_end`). MySQL InnoDB: ver AUDIT_PLAN F1 |

Orden de restauración: índices → constraints (igual que `dump`). Invalidar la caché de metadatos
(`metadata/source.py:168`) tras desactivar y tras restaurar.

### 4.3 API (aditiva)

```python
IndexMode = Literal["secondary", "all"]

BulkCrud.maintenance_scope(..., disable_indexes: bool | IndexMode = False)
ParallelOptions(disable_indexes: bool | IndexMode = False)          # solo INSERT; desactivación previa al pool
DumpConfig(manage_indexes: bool | IndexMode = False)
# False = ninguno · True ≡ "secondary" · "all" = todos los posibles

BulkCrud.maintenance_scope(..., validate_fks_after: bool = False)   # MySQL/MariaDB (y PostgreSQL)
DumpConfig(validate_fks_after: bool = False)
```

- `MaintenanceScopeResult.index_results: list[IndexActionResult]`; `ParallelLoadResult.index_results`.
- `facts.clustered_index_count` deja de usarse en `bulk`: marcar obsoleto, no borrar.

### 4.4 Qué toca cada modo

| Motor | `"secondary"` | `"all"` añade | Nunca |
|---|---|---|---|
| SQL Server | NONCLUSTERED no únicos `DISABLE`→`REBUILD` | PK/UNIQUE NONCLUSTERED; FK entrantes reactivadas con `WITH CHECK CHECK CONSTRAINT` | índice **clustered** |
| Oracle | `NORMAL` no únicos `UNUSABLE`→`REBUILD` | PK/UNIQUE: `DISABLE CONSTRAINT … CASCADE` → `ENABLE VALIDATE` + FK hijas; índices únicos sin constraint: DROP + `DBMS_METADATA.GET_DDL` | PK de **IOT** |
| PostgreSQL | no únicos: DROP + `pg_get_indexdef` | únicos sin constraint; PK/UNIQUE `DROP/ADD CONSTRAINT` (`pg_get_constraintdef`); FK entrantes DROP antes y `NOT VALID` + `VALIDATE` después | — |
| MariaDB/MySQL InnoDB | **nuevo**: `DROP INDEX` + un único `ALTER TABLE … ADD INDEX …` (DDL de `information_schema.STATISTICS`), excluyendo índices requeridos por una FK | UNIQUE secundarios sin FK que los referencie | **PK** (clustered en InnoDB) |
| MyISAM/Aria | `DISABLE KEYS` | UNIQUE: DROP + ADD | PK |
| SQLite | solo apoyo de tests (decisión 4) | — | — |

InnoDB: ni con `FOREIGN_KEY_CHECKS=0` se puede borrar un índice requerido por una FK (verificar en MariaDB 11.4 y
MySQL 8.4 en G0).

### 4.5 Salvaguardas de `"all"`

1. Exige `disable_constraints=True` (decisión 1) y permisos DDL.
2. DDL de todo lo eliminado logueado antes del DROP y devuelto en el resultado.
3. Reconstrucción: PK/UNIQUE → secundarios → FK.
4. Fallo al reconstruir un único → `IndexRebuildError` con hasta N claves duplicadas (`GROUP BY … HAVING COUNT(*) > 1`)
   (decisión 2). En `"secondary"` se mantiene el comportamiento tolerante.
5. Aviso explícito en el log al activar `"all"`.

### 4.6 `FOREIGN_KEY_CHECKS` (MariaDB/MySQL)

- Se mantiene en la ruta de constraints (ya existe). Es un `SET`: sin commit implícito, sin privilegios especiales.
- Nuevo `validate_fks_after` (default `False`, decisión 5): orphan-check `NOT EXISTS … LIMIT 1` por FK, generalizando el
  SQL de PostgreSQL (`_pg_check_fk_orphans` en `bulk`, `_find_fk_orphan_pg` en `dump`) a `metadata/` y compartido.
- Aviso: con FK checks desactivados no se ejecutan los `ON DELETE/UPDATE CASCADE`.

### 4.7 Patrón para cargas iterativas (documentación)

| Iteración | Modo | Motivo |
|---|---|---|
| Validación (1…n−1) | `False` o `"secondary"` | PK/UNIQUE activos: los duplicados fallan pronto |
| Final, datos validados | `"all"` | Máximo rendimiento; la reconstrucción de únicos es la última comprobación |

## 5. G0 — Medición (previa a implementar; no toca `src/`)

- Script `scripts/bench_index_modes.py` con DDL directo.
- Motores: MariaDB 11.4, MySQL 8.4, PostgreSQL 17, Oracle Free 23 (con calentamiento), SQL Server 2022 (puerto 51833).
- Ejes:
  - modos `none` / `secondary` / `all`;
  - MariaDB/MySQL además: `FOREIGN_KEY_CHECKS` on/off, `unique_checks=0`, MyISAM `DISABLE KEYS` (referencia);
  - perfiles: PK + 0/2/5 secundarios; con y sin 1 UNIQUE; tabla padre con FK entrante; tabla hija con 1 y 2 FK;
  - orden de inserción: PK ordenada y aleatoria;
  - volumen 1M y 3,5M (10M opcional);
  - rutas: `maintenance_scope` en serie, `ParallelBulkLoader` 4 workers, `dump` de 3 tablas con FK.
- Métricas: tiempo de desactivar, cargar, reconstruir, total; % frente a `none`; coste de `validate_fks_after` y de
  `WITH CHECK CHECK CONSTRAINT`. Mediana de 3, misma semilla, tabla recreada.
- Configuración anotada y probada: PostgreSQL `maintenance_work_mem`, SQL Server `MAXDOP`, Oracle `PARALLEL`,
  InnoDB `innodb_sort_buffer_size`.
- Salida: `build/logs/bench_index_modes_<fecha>.txt` + CSV; tabla resumen para `docs/`.
- Criterio: se implementa una combinación motor × modo si gana **≥ 5 %** del total a 3,5M con ≥ 2 índices (decisión 3).

## 6. Grupos de IMPLEMENT

| Grupo | Contenido | Entrega | Depende de |
|---|---|---|---|
| G0 | Medición | previa | — |
| G1 | Estrategia compartida, `IndexMode`, `IndexActionResult` en `bulk/_models` (+ reexport) | 3.2.0 | — |
| G2 | `dump.IndexManager` como adaptador; `manage_indexes` acepta modo | 3.2.0 | G1 |
| G3 | `maintenance_scope` en sesión con `"secondary"` (savepoints, Oracle, `index_results`) | 3.2.0 | G1 |
| G4 | `ParallelOptions.disable_indexes` con desactivación previa al pool | 3.2.0 | G1 |
| G5 | `"all"` por motor | 3.3.0 | G0, G3 |
| G5b | `validate_fks_after` compartido (MySQL + PostgreSQL) | 3.2.0 | G0 |
| G6 | InnoDB DROP/ADD (y `unique_checks` si G0 lo justifica) | 3.3.0 | G0 |
| G7 | Evento de auditoría de índices en `bulk` (opcional) | 3.2.0 | G3 |
| G8 | Documentación: `docs/api/bulk_crud.md`, `docs/guides/performance_audit_constraints_guide.md`, `docs/guides/dump_guide.md`, docstring de `facts.secondary_nonunique_indexes`, CHANGELOG | ambas | todos |

## 7. Tests

- Unitarios: SQL por estrategia y modo; nunca clustered / PK InnoDB / IOT / únicos en `"secondary"`; log antes del DROP;
  rollback en sesión sin índices perdidos; `commit_every_n_chunks` + error restaura; paralelo: una desactivación y una
  reconstrucción aunque falle un worker; `IndexRebuildError` con duplicados; reexport `is`.
- Actualizar `tests/unit/bulk/test_maintenance_scope.py` (asserts de `ALL DISABLE`).
- Integración (`tests/integration/test_bulk_engines.py`): restauración tras éxito y error; heap con PK NONCLUSTERED
  (PK activa, FK entrantes `is_not_trusted = 0`); test de atomicidad InnoDB existente sigue pasando; savepoints.
- `pytest` también en shell limpio, sin URLs del banco.

## 8. Versión

- 3.2.0 (MINOR): G1–G4, G5b, G7. Cambio de comportamiento de `disable_indexes=True` en SQL Server/PostgreSQL/Oracle
  documentado en CHANGELOG.
- 3.3.0 (MINOR): G5, G6 según G0.
