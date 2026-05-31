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
```

| Parámetro | Tipo | Default | Descripción |
|---|---|---|---|
| `source_engine` | `Engine` | — | Engine SQLAlchemy del esquema origen (lectura) |
| `target_engine` | `Engine` | — | Engine SQLAlchemy del esquema destino (escritura) |
| `source_schema` | `str \| None` | `None` | Schema origen; `None` usa el default del engine |
| `target_schema` | `str \| None` | `None` | Schema destino; `None` usa el default del engine |
| `tables` | `list[str] \| None` | `None` | Tablas a volcar; `None` = todas las del origen |
| `chunk_size` | `int` | `5000` | Filas por chunk en lectura y en bulk insert |
| `output_dir` | `Path` | `Path()` | Directorio donde guardar el informe Excel |
| `truncate_target` | `bool` | `True` | `True` = vaciar destino antes de cargar; `False` = append |
| `bulk_audit_path` | `Path \| None` | `None` | Ruta del CSV de auditoría de `util_bbdd.bulk.audit`. Si se proporciona: (1) cada INSERT queda registrado en el CSV durante la carga y (2) al finalizar el volcado, `DumpResult.audit_summary` se popula con las métricas del CSV filtradas al rango temporal del volcado. `None` = sin auditoría de inserts. |

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

Ejecuta las 6 fases del volcado y retorna el resultado completo con el informe Excel.

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
```

| Atributo | Tipo | Descripción |
|---|---|---|
| `table_results` | `list[TableDumpResult]` | Resultado por tabla (incluye tablas faltantes) |
| `constraint_results` | `list[ConstraintResult]` | Resultado de rehabilitación de constraints |
| `load_order` | `list[str]` | Orden topológico aplicado (tablas con ciclos al final) |
| `cycles_detected` | `list[list[str]]` | Grupos de tablas con FK circular |
| `report` | `Path` | Ruta del fichero Excel generado |
| `audit_summary` | `DumpAuditSummary \| None` | Métricas de auditoría de inserts extraídas de `bulk.audit` al finalizar. `None` cuando `DumpConfig.bulk_audit_path` no está configurado o el CSV no contiene entradas del volcado actual. |

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

## TableDumpResult

Resultado del volcado de una tabla individual. Presente en `DumpResult.table_results`.

```python
@dataclass
class TableDumpResult:
    table_name: str
    source_rows: int          # -1 si no se pudo contar
    target_rows_before: int   # -1 si no se pudo contar
    target_rows_after: int    # -1 si no se pudo contar
    status: Literal["success", "missing_target", "skipped", "error"]
    skipped_columns: list[str]
    load_order_position: int  # -1 para tablas missing_target
    in_cycle: bool = False
    error_msg: str = ""
```

### Valores de `status`

| Valor | Significado |
|---|---|
| `"success"` | Todos los chunks cargados sin error |
| `"error"` | Al menos un chunk falló; `error_msg` contiene el detalle |
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
        diff: SchemaDiff,
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
| `Columnas Inexistentes` | Columnas de origen ausentes en destino |

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
- [API Comparador de Esquemas](schema-comparator.md) — `SchemaDiff` usado en el informe
