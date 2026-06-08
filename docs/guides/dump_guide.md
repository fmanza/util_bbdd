# Guía: Volcado de datos entre motores

## 1. Objetivo

Copiar todos los datos de un esquema origen a otro destino (mismo motor o motores distintos)
respetando automáticamente el orden de las claves foráneas, con limpieza opcional del destino e
informe Excel de auditoría. Es un **how-to operativo**: para el detalle de las 7 fases y los
contratos completos, ver la [documentación funcional](../functional/dump-data-export.md) y la
[referencia técnica](../api/dump.md).

El volcado mueve **solo datos, nunca DDL**: las tablas destino deben existir previamente. Si
necesitas crear primero la estructura en otro motor, usa la
[guía de migración DDL](ddl_migration_guide.md).

## 2. Requisitos Previos

- Python 3.12+ con `util_bbdd` instalado y los drivers de **ambos** motores (ver [Instalación](../installation.md)).
- `pandas` y `openpyxl` disponibles (dependencias del módulo de volcado; `openpyxl` es necesario para el informe Excel).
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
    chunk_size=5000,          # baja a 500 si el destino MariaDB tiene columnas TEXT/JSON
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
`reports/dump_report_<timestamp>.xlsx` existente, y sus hojas **Auditoría Tablas**,
**Tablas Faltantes** y **Columnas Inexistentes** no listan incidencias inesperadas.

## 5. Variantes y Solución de Problemas

| Escenario / Error | Causa probable | Solución |
|---|---|---|
| Tabla con `status="missing_target"` | Existe en origen pero no en destino | Crea la estructura primero (migración DDL); el volcado no aplica DDL |
| Columna en `skipped_columns` | No existe en la tabla destino | Alinea el esquema destino o ignórala si es intencional (best-effort) |
| `Server has gone away` (MariaDB) | Engine sin `pool_pre_ping` y chunks grandes | Usa `get_sqlalchemy_engine()` y baja `chunk_size` a 500 |
| Duplicados tras el volcado | `truncate_target=False` (append) sobre datos ya existentes | Usa `truncate_target=True` para un full refresh |
| Volcado lento con millones de filas | Carga secuencial y atómica por defecto | Activa palancas opt-in (ver abajo) |
| Error al generar el informe | Falta `openpyxl` | `pip install openpyxl` |

**Palancas de rendimiento (opt-in, todas desactivadas por defecto y combinables):**

| Palanca | Parámetro `DumpConfig` | Efecto | Contrapartida |
|---|---|---|---|
| Cadencia de commit | `commit_every_n_chunks=N` | Commit cada N lotes; acota el undo log | La carga de la tabla deja de ser atómica |
| Gestión de índices | `manage_indexes=True` | Deshabilita índices secundarios durante la carga | DROP+recreate en PostgreSQL (destructivo) |
| Paralelismo por tabla | `max_parallel_tables=N` | Tablas independientes en paralelo | Solo dentro del mismo nivel topológico FK |
| Paralelismo por rangos PK | `parallel_pk_ranges=N` | Particiona una tabla con PK entera en N rangos | Requiere destino sin triggers per-fila |

Para un script completo y la medición del impacto, ver el
[ejemplo ejecutable de volcado](../examples/dump_data_export.md) y la guía de
[Performance & Benchmarks](benchmarks.md).
