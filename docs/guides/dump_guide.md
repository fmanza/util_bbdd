# Guía: Volcado de datos entre motores

## 1. Objetivo

Copiar todos los datos de un esquema origen a otro destino (mismo motor o motores distintos)
respetando automáticamente el orden de las claves foráneas, con limpieza opcional del destino e
informe Excel de auditoría. Es un **how-to operativo**: para el detalle de las 7 fases y los
contratos completos, ver la [documentación funcional](../functional/dump_data_export.md) y la
[referencia técnica](../api/dump.md).

El volcado mueve **solo datos, nunca DDL**: las tablas destino deben existir previamente. Si
necesitas crear primero la estructura en otro motor, usa la
[guía de migración DDL](ddl_migration_guide.md).

## 2. Requisitos Previos

- Python 3.12+ con `util_bbdd` instalado y los drivers de **ambos** motores (ver [Instalación](../installation.md)).
- Dos engines SQLAlchemy **conectables**:
    - Origen: permiso `SELECT` sobre las tablas a volcar.
    - Destino: permisos `INSERT`, `DELETE`/`TRUNCATE` y gestión de constraints.
- Las **tablas destino ya creadas** (el volcado no aplica DDL).
- Un directorio donde escribir el informe Excel.

## 3. Pasos

### 3.1 Obtener los engines de origen y destino

Usa `SyncDatabaseManager.get_sqlalchemy_engine()` para que el engine incluya `pool_pre_ping=True`
y `pool_recycle=3600` (evita `Server has gone away` en MariaDB/MySQL):

```python
from util_bbdd.managers import SyncDatabaseManager

src_mgr = SyncDatabaseManager("postgresql", {
    "host": "prod-db", "user": "reader",
    "password": "<reemplazar>", "database": "ventas",
})
dst_mgr = SyncDatabaseManager("sqlserver", {
    "host": "analytics-db", "user": "writer",
    "password": "<reemplazar>", "database": "ventas_bi",
})
```

### 3.2 Configurar el volcado

```python
from pathlib import Path
from util_bbdd.dump import DumpConfig, DumpOrchestrator

config = DumpConfig(
    source_engine=src_mgr.get_sqlalchemy_engine(),
    target_engine=dst_mgr.get_sqlalchemy_engine(),
    source_schema="public",   # None = schema por defecto del engine
    target_schema="dbo",
    tables=None,              # None = todas las tablas del origen
    chunk_size=5000,          # bájalo si en MariaDB/MySQL un lote con TEXT/JSON supera max_allowed_packet
    truncate_target=True,     # vaciar destino antes de cargar (full refresh)
    output_dir=Path("reports"),
)
```

### 3.3 Ejecutar y recoger el resultado

```python
result = DumpOrchestrator(config).run()
```

`run()` ejecuta las 7 fases (introspección → análisis topológico FK → desactivar constraints →
limpieza → carga best-effort → rehabilitar constraints → informe Excel) y devuelve **siempre** un
`DumpResult`, incluso si alguna tabla falla (cada tabla es independiente).

## 4. Verificación

Inspecciona el `DumpResult` y abre el informe Excel:

```python
print("Orden de carga:", result.load_order)
print("Ciclos FK:", result.cycles_detected)
print("Informe:", result.report)

errores = [t for t in result.table_results if t.status == "error"]
for t in errores:
    print("ERROR:", t.table_name, "→", t.error_msg)
```

El volcado es correcto cuando: `errores` está vacío, `result.report` apunta a un fichero
`reports/dump_report_<timestamp>.xlsx` existente, y:
- Sus hojas **Auditoría Tablas**, **Tablas Faltantes** y **Columnas Inexistentes** no listan incidencias inesperadas.
- La hoja **Errores de Reactivación** **no debe existir** (solo aparece si hay error general de reactivación de constraints).
- Con `bulk_audit_path`, la hoja **Auditoría Bulk** no debe tener celdas resaltadas en rojo ni naranja.
- Con `sync_pk_sequences=True` (por defecto), la hoja **Secuencias PK** no debe tener estados `ERROR`.

## 5. Variantes y Solución de Problemas

| Escenario / Error | Causa probable | Solución |
|---|---|---|
| Tabla con `status="missing_target"` | Existe en origen pero no en destino | Crea la estructura primero (migración DDL); el volcado no aplica DDL |
| Columna en `skipped_columns` | No existe en la tabla destino | Alinea el esquema destino o ignórala si es intencional (best-effort) |
| `Server has gone away` (MariaDB) | Engine sin `pool_pre_ping` y chunks grandes | Usa `get_sqlalchemy_engine()` y baja `chunk_size` a 500 |
| Duplicados tras el volcado | `truncate_target=False` (append) sobre datos ya existentes | Usa `truncate_target=True` para un full refresh |
| Volcado lento con millones de filas | Carga secuencial y atómica por defecto | Activa palancas opt-in (ver abajo) |
| `DumpReportError` al terminar | No se pudo escribir el Excel (permisos, fichero abierto, disco lleno); la carga ya se hizo | Recuperar el resultado de `exc.result` y revisar `exc.output_path` |
| `DumpConstraintError` «Hay un diario de constraints pendiente» (4.4.0) | Un volcado anterior con el mismo `output_dir` murió a mitad (SQL Server, PostgreSQL, Oracle) y pudo dejar constraints desactivadas | `restore_constraints(target_engine, "reports/constraints_journal.json")` y repetir el volcado ([detalle](../api/dump.md)) |

**Palancas de rendimiento (opt-in, todas desactivadas por defecto y combinables):**

| Palanca | Parámetro `DumpConfig` | Efecto | Contrapartida |
|---|---|---|---|
| Cadencia de commit | `commit_every_n_chunks=N` | Commit cada N lotes; acota el undo log | La carga de la tabla deja de ser atómica |
| Gestión de índices | `manage_indexes=True` | Deshabilita índices secundarios no únicos durante la carga | DROP+recreate en PostgreSQL y MySQL/MariaDB InnoDB (destructivo; el DDL se loguea antes de borrar) |
| Paralelismo por tabla | `max_parallel_tables=N` | Tablas independientes en paralelo | Solo dentro del mismo nivel topológico FK |
| Paralelismo por rangos PK | `parallel_pk_ranges=N` o `"auto"` | Particiona una tabla con PK entera en N rangos; con `"auto"` (v3.0.0) solo donde las mediciones dicen que gana (hoy, destino SQL Server desde 3,5M filas) | Requiere destino sin triggers per-fila |

Para un script completo y la medición del impacto, ver el
[ejemplo ejecutable de volcado](../examples/dump_data_export.md) y la guía de
[Performance & Benchmarks](benchmarks.md).
