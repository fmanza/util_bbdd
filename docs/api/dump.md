# API — Volcado de Datos (`util_bbdd.dump`)

Referencia técnica del módulo `dump`. Para el objetivo de negocio y el flujo de las 6 fases, consulta la [documentación funcional](../functional/dump-data-export.md).

---

## Imports canónicos

```python
from util_bbdd.dump import (
    DumpConfig,
    DumpOrchestrator,
    DumpResult,
    DumpAuditSummary,
    PKSyncResult,
    TableDumpResult,
    ConstraintManager,
    ConstraintResult,
    DumpReporter,
)
```

---

## DumpConfig

Configuración de un volcado. Se pasa al constructor de `DumpOrchestrator`.

```python
@dataclass
class DumpConfig:
    source_engine: Engine
    target_engine: Engine
    source_schema: str | None = None
    target_schema: str | None = None
    tables: list[str] | None = None
    chunk_size: int = 5000
    output_dir: Path = Path()
    truncate_target: bool = True
    bulk_audit_path: Path | None = None
    collect_row_counts: bool = True
    sync_pk_sequences: bool = True
```

| Parámetro | Tipo | Default | Descripción |
|---|---|---|---|
| `source_engine` | `Engine` | — | Engine SQLAlchemy del esquema origen (lectura) |
| `target_engine` | `Engine` | — | Engine SQLAlchemy del esquema destino (escritura). **MariaDB/MySQL:** crear con `pool_pre_ping=True` y `pool_recycle=3600` para evitar `InterfaceError: Server has gone away`. `SyncDatabaseManager.get_sqlalchemy_engine()` los incluye por defecto. |
| `source_schema` | `str \| None` | `None` | Schema origen; `None` usa el default del engine |
| `target_schema` | `str \| None` | `None` | Schema destino; `None` usa el default del engine |
| `tables` | `list[str] \| None` | `None` | Tablas a volcar; `None` = todas las del origen |
| `chunk_size` | `int` | `5000` | Filas por chunk en lectura y en bulk insert. **MariaDB/MySQL con columnas TEXT/BLOB/JSON extensas:** valores altos pueden superar `max_allowed_packet` del servidor (16 MB por defecto), produciendo `InterfaceError: Lost connection to server during query`. Usar `500` o menos para estas tablas. `DumpOrchestrator` emite `WARNING` si `chunk_size > 1000` con destino MariaDB/MySQL. |
| `output_dir` | `Path` | `Path()` | Directorio donde guardar el informe Excel |
| `truncate_target` | `bool` | `True` | `True` = vaciar destino antes de cargar; `False` = append. **SQL Server:** usa `TRUNCATE TABLE` en tablas sin FK entrantes (instantáneo) y `DELETE FROM` solo en tablas referenciadas por FK de otras tablas del esquema — TRUNCATE falla en SQL Server cuando existe una FK entrante aunque esté en NOCHECK. La detección es automática; si falla, el volcado reintenta con `DELETE`. |
| `bulk_audit_path` | `Path \| None` | `None` | Ruta del CSV de auditoría de `util_bbdd.bulk.audit`. Si se proporciona: (1) cada INSERT queda registrado en el CSV durante la carga y (2) al finalizar el volcado, `DumpResult.audit_summary` se popula con las métricas del CSV filtradas al rango temporal del volcado. `None` = sin auditoría de inserts. |
| `collect_row_counts` | `bool` | `True` | Si `True`, ejecuta `COUNT(*)` sobre origen y destino por tabla para obtener volumetría. Si `False`, omite todos los conteos y usa `-1` como sentinel en `TableDumpResult.source_rows`, `target_rows_before` y `target_rows_after`. Útil en volcados de alto volumen donde el conteo es costoso (Snowflake, Oracle sin estadísticas actualizadas, tablas de decenas de millones de filas). El informe Excel muestra `—` para los valores `-1`. |
| `sync_pk_sequences` | `bool` | `True` | Si `True` (default), ejecuta la Fase 6a tras la carga: resincroniza los contadores PK (sequence / IDENTITY / AUTO_INCREMENT) del destino al valor `MAX(pk)` real de cada tabla. Motores soportados: PostgreSQL, SQL Server, MariaDB/MySQL, Oracle ≥ 12c. Los resultados quedan en `DumpResult.pk_sync_results`. Usar `False` para gestionar la resincronización manualmente o si los permisos requeridos no están disponibles. |

### Optimizaciones automáticas de inserción

`DumpOrchestrator` delega la carga de datos en `BulkCrud`, que aplica automáticamente la estrategia INSERT óptima según el motor destino:

| Motor destino | Estrategia aplicada | Ganancia típica |
|---|---|---|
| **PostgreSQL + psycopg2** | `psycopg2.extras.execute_values` — un único `INSERT ... VALUES ...` multi-row por chunk | 3–5× vs `executemany` |
| **SQL Server + pyodbc** | `cursor.fast_executemany = True` vía listener `before_cursor_execute` | 5–15× vs `executemany` |
| **Otros motores** | `executemany` estándar del driver | — |

Estas optimizaciones están activas por defecto y no requieren configuración en `DumpConfig`. Para deshabilitar `fast_executemany` en SQL Server (p.ej. por incompatibilidad con pyodbc antiguo), crear el engine y pasar `BulkCrud(enable_fast_executemany=False)` directamente — `DumpOrchestrator` no expone este control en `DumpConfig`.

---

## DumpOrchestrator

Orquesta el volcado completo. Punto de entrada público del módulo.

```python
class DumpOrchestrator:
    def __init__(self, config: DumpConfig) -> None: ...
    def run(self) -> DumpResult: ...
```

### `__init__(config)`

Prepara los inspectores SQLAlchemy de origen y destino. No abre conexiones hasta llamar a `run()`.

### `run() → DumpResult`

Ejecuta las 7 fases del volcado y retorna el resultado completo con el informe Excel.

Puede propagar `SQLAlchemyError` si la conexión a origen o destino falla antes de comenzar.

---

## DumpResult

Resultado completo de un volcado. Retornado por `DumpOrchestrator.run()`.

```python
@dataclass
class DumpResult:
    table_results: list[TableDumpResult]
    constraint_results: list[ConstraintResult]
    load_order: list[str]
    cycles_detected: list[list[str]]
    report: Path
    audit_summary: DumpAuditSummary | None = None
    pk_sync_results: list[PKSyncResult] | None = None
```

| Atributo | Tipo | Descripción |
|---|---|---|
| `table_results` | `list[TableDumpResult]` | Resultado por tabla (incluye tablas faltantes) |
| `constraint_results` | `list[ConstraintResult]` | Resultado de rehabilitación de constraints |
| `load_order` | `list[str]` | Orden topológico aplicado (tablas con ciclos al final) |
| `cycles_detected` | `list[list[str]]` | Grupos de tablas con FK circular |
| `report` | `Path` | Ruta del fichero Excel generado |
| `audit_summary` | `DumpAuditSummary \| None` | Métricas de auditoría de inserts extraídas de `bulk.audit` al finalizar. `None` cuando `DumpConfig.bulk_audit_path` no está configurado o el CSV no contiene entradas del volcado actual. |
| `pk_sync_results` | `list[PKSyncResult] \| None` | Resultado de la resincronización de contadores PK (Fase 6a). `None` cuando `DumpConfig.sync_pk_sequences=False` o no hay columnas con identity/autoincrement en las tablas cargadas. |

---

## DumpAuditSummary

Métricas de auditoría de inserts generadas al finalizar el volcado. Disponible en `DumpResult.audit_summary` cuando `DumpConfig.bulk_audit_path` está configurado.

```python
@dataclass
class DumpAuditSummary:
    total_operaciones: int
    total_filas: int
    tiempo_total_seg: float
    tiempo_promedio_seg: float
    tablas_auditadas: int
    tabla_mas_activa: str | None
    audit_path: Path
```

| Atributo | Tipo | Descripción |
|---|---|---|
| `total_operaciones` | `int` | Número de lotes INSERT registrados en el CSV de auditoría durante el volcado |
| `total_filas` | `int` | Suma de filas insertadas según el CSV de auditoría |
| `tiempo_total_seg` | `float` | Tiempo total de inserción en segundos (redondeado a 3 decimales) |
| `tiempo_promedio_seg` | `float` | Tiempo medio por lote INSERT (redondeado a 3 decimales) |
| `tablas_auditadas` | `int` | Número de tablas distintas con al menos un INSERT registrado |
| `tabla_mas_activa` | `str \| None` | Tabla con mayor número de lotes INSERT; `None` si no hay entradas |
| `audit_path` | `Path` | Ruta del CSV de auditoría consultado |

### Relación con `bulk.audit`

`DumpAuditSummary` se construye leyendo el CSV de `util_bbdd.bulk.audit` al finalizar el volcado. Solo se incluyen las entradas cuyo `timestamp >= inicio_del_volcado`, para aislar este volcado de operaciones previas en el mismo CSV.

El CSV de auditoría contiene una fila por lote INSERT, no por tabla. Una tabla grande con `chunk_size=5000` y 50 000 filas genera 10 entradas en el CSV, todas reflejadas en `total_operaciones`.

---

## PKSyncResult

Resultado de sincronizar el contador PK de una columna tras la carga masiva (Fase 6a). Presente en `DumpResult.pk_sync_results` y también disponible desde `util_bbdd.bulk`.

```python
@dataclass
class PKSyncResult:
    table_name: str
    column_name: str
    engine_dialect: str
    max_value: int | None
    status: Literal["synced", "skipped", "no_rows", "unsupported", "error"]
    error_msg: str = ""
```

| Atributo | Tipo | Descripción |
|---|---|---|
| `table_name` | `str` | Nombre de la tabla |
| `column_name` | `str` | Nombre de la columna PK sincronizada |
| `engine_dialect` | `str` | Dialecto del motor (`"postgresql"`, `"mssql"`, etc.) |
| `max_value` | `int \| None` | `MAX(pk)` leído antes del sync; `None` si la tabla estaba vacía |
| `status` | `Literal` | Resultado de la operación (ver tabla de valores) |
| `error_msg` | `str` | Detalle del error cuando `status="error"` o `"unsupported"` |

### Valores de `status`

| Valor | Significado |
|---|---|
| `"synced"` | Contador actualizado al `MAX(pk)` real. El próximo INSERT sin PK explícita usará `MAX + 1`. |
| `"skipped"` | Columna sin sequence vinculada (PK natural, UUID). No se ejecutó ninguna operación. |
| `"no_rows"` | Tabla vacía tras la carga. Contador reiniciado al valor semilla del motor (1 para PostgreSQL/MariaDB, 0 para SQL Server). |
| `"unsupported"` | Motor o patrón no soportado. Oracle < 12c (trigger + sequence manual) cae aquí. |
| `"error"` | Fallo de permisos u otro error SQL. Ver `error_msg`. La Fase 6a continúa con la siguiente columna (best-effort). |

### Permisos requeridos por motor

| Motor | Permiso mínimo |
|---|---|
| **PostgreSQL** | Propietario de la tabla o `SUPERUSER` (para `setval()` en schemas ajenos) |
| **SQL Server** | `ALTER TABLE` permission o membresía en `db_owner` (para `DBCC CHECKIDENT`) |
| **MariaDB/MySQL** | `ALTER` privilege sobre la tabla |
| **Oracle ≥ 12c** | `SELECT` en `ALL_TAB_IDENTITY_COLS` (disponible por defecto) + `ALTER ANY SEQUENCE` o propietario de la sequence |

---

## TableDumpResult

Resultado del volcado de una tabla individual. Presente en `DumpResult.table_results`.

```python
@dataclass
class TableDumpResult:
    table_name: str
    source_rows: int          # -1 si no se pudo contar o collect_row_counts=False
    target_rows_before: int   # -1 si no se pudo contar o collect_row_counts=False
    target_rows_after: int    # -1 si no se pudo contar o collect_row_counts=False
    status: Literal["success", "missing_target", "skipped", "error"]
    skipped_columns: list[str]
    load_order_position: int  # -1 para tablas missing_target
    in_cycle: bool = False
    error_msg: str = ""
```

### Valores de `status`

| Valor | Significado |
|---|---|
| `"success"` | Todos los chunks cargados sin error (table-atomic: un error en cualquier chunk hace rollback de toda la tabla) |
| `"error"` | La carga falló; `error_msg` contiene el detalle. Errores de lectura del origen llevan prefijo `"Error leyendo origen: "` |
| `"skipped"` | No hay columnas comunes entre origen y destino |
| `"missing_target"` | La tabla no existe en el destino |

---

## ConstraintManager

Gestiona la desactivación y reactivación de constraints en el motor destino. Usar como context manager garantiza que `enable_all()` se ejecuta incluso si la carga lanza una excepción.

```python
class ConstraintManager:
    def __init__(self, engine: Engine, schema: str | None = None) -> None: ...
    def __enter__(self) -> ConstraintManager: ...
    def __exit__(self, ...) -> None: ...  # llama enable_all()
    def disable_all(self, tables: list[str]) -> None: ...
    def enable_all(self) -> list[ConstraintResult]: ...
    constraint_results: list[ConstraintResult]  # poblado tras __exit__
```

### Uso como context manager

```python
mgr = ConstraintManager(target_engine, schema="dbo")
with mgr:
    mgr.disable_all(tables=["orders", "items"])
    # ... carga de datos ...
# mgr.constraint_results disponible aquí
```

### Comportamiento por motor

| Motor | `disable_all` | `enable_all` | Status retornado |
|---|---|---|---|
| **SQL Server** | `NOCHECK CONSTRAINT ALL` por tabla | `WITH CHECK CHECK CONSTRAINT ALL` | `enabled` / `failed` |
| **MariaDB/MySQL** | Listener `SET FK_CHECKS=0` + `dispose()` | Elimina listener + `dispose()` | `unverified` (sin validación retroactiva) |
| **PostgreSQL** | `DISABLE TRIGGER ALL` por tabla | `ENABLE TRIGGER ALL` + `VALIDATE CONSTRAINT` por FK | `enabled` / `failed` |
| **Oracle** | `DISABLE CONSTRAINT` por constraint (filtra `SYS_C%`) | `ENABLE VALIDATE CONSTRAINT` | `enabled` / `failed` |
| **Otros** | No-op + warning en log | Retorna `[]` | — |

---

## ConstraintResult

Resultado de rehabilitar una constraint individual.

```python
@dataclass
class ConstraintResult:
    table_name: str
    constraint_name: str
    dialect: str
    status: Literal["enabled", "failed", "unverified"]
    error_msg: str = ""
```

| `status` | Significado |
|---|---|
| `"enabled"` | Constraint reactivada y validada correctamente |
| `"failed"` | Error al reactivar; datos pueden infringir la restricción |
| `"unverified"` | Reactivada pero sin validación retroactiva (MariaDB) |

---

## DumpReporter

Genera el informe Excel de auditoría. Llamado automáticamente por `DumpOrchestrator.run()`.

```python
class DumpReporter:
    def __init__(self, output_dir: Path) -> None: ...
    def generate(
        self,
        table_results: list[TableDumpResult],
        missing_tables: list[str],
        constraint_results: list[ConstraintResult],
        cycles: list[list[str]],
    ) -> Path: ...
```

### `generate(...) → Path`

Crea un fichero `dump_report_<timestamp>.xlsx` en `output_dir` y retorna su ruta. El directorio se crea automáticamente si no existe.

El fichero contiene tres hojas:

| Hoja | Contenido |
|---|---|
| `Auditoría Tablas` | Volumetría y estado por tabla; constraints con incidencias al pie |
| `Tablas Faltantes` | Tablas de origen sin correspondencia en destino |
| `Columnas Inexistentes` | Columnas de origen ausentes en destino (derivadas de `TableDumpResult.skipped_columns`) |

---

## Excepciones

Las operaciones de volcado propagan excepciones de SQLAlchemy sin envolver. Las más habituales:

| Excepción | Cuándo |
|---|---|
| `sqlalchemy.exc.SQLAlchemyError` | Fallo de conexión, error SQL, timeout |
| `sqlalchemy.exc.OperationalError` | Credenciales inválidas, host no alcanzable |
| `sqlalchemy.exc.IntegrityError` | Violación de constraint durante la carga (tabla marcada como `error`, no se relanza) |

Los errores a nivel de tabla se capturan internamente y se registran en `TableDumpResult.error_msg`; el proceso continúa con la siguiente tabla.

---

## Ver también

- [Documentación Funcional — Volcado de Datos](../functional/dump-data-export.md)
- [Ejemplo ejecutable — Volcado PostgreSQL → SQL Server](../examples/dump_data_export.md)
