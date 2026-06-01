# Volcado de Datos entre Bases de Datos

Este ejemplo muestra cómo copiar todos los datos de un esquema **PostgreSQL** a un esquema **SQL Server** usando `DumpOrchestrator`.

El mismo patrón funciona para cualquier combinación de motores soportados.

---

## Caso de uso

Un equipo de analítica necesita refrescar su entorno SQL Server con los datos de producción de PostgreSQL. El proceso debe:

1. Respetar el orden de las FKs (no cargar `items` antes que `orders`).
2. Limpiar el destino antes de cargar (modo refresco completo).
3. Continuar aunque alguna tabla falle (best-effort).
4. Generar un informe Excel de auditoría con el resultado.

---

## Código completo

```python
from pathlib import Path
from sqlalchemy import create_engine

from util_bbdd.dump import DumpConfig, DumpOrchestrator

# 1. Engines
src_engine = create_engine(
    "postgresql+psycopg2://user:password@prod-server:5432/production_db"
)
dst_engine = create_engine(
    "mssql+pymssql://user:password@analytics-server/analytics_db"
)

# 2. Configuración
config = DumpConfig(
    source_engine=src_engine,
    target_engine=dst_engine,
    source_schema="public",          # esquema origen en PostgreSQL
    target_schema="dbo",             # esquema destino en SQL Server
    chunk_size=1_000,                # filas por chunk (ver sección Performance)
    output_dir=Path("reports"),      # directorio para el informe Excel
    truncate_target=True,            # vaciar destino antes de cargar
)

# 3. Ejecutar volcado
result = DumpOrchestrator(config).run()

# 4. Revisar resultado
print(f"Informe: {result.report}")
print(f"Orden de carga: {result.load_order}")

if result.cycles_detected:
    print(f"Ciclos FK detectados: {result.cycles_detected}")

for tr in result.table_results:
    print(
        f"  [{tr.status.upper():15}] {tr.table_name:30} "
        f"origen={tr.source_rows:>8}  destino={tr.target_rows_after:>8}"
    )
    if tr.skipped_columns:
        print(f"    Columnas omitidas: {', '.join(tr.skipped_columns)}")
    if tr.error_msg:
        print(f"    ERROR: {tr.error_msg}")

# 5. Constraints con incidencias
failed = [cr for cr in result.constraint_results if cr.status != "enabled"]
if failed:
    print("\nConstraints con incidencias al rehabilitar:")
    for cr in failed:
        print(f"  [{cr.status.upper()}] {cr.table_name}.{cr.constraint_name}: {cr.error_msg}")
```

---

## Volcado cross-engine con SyncDatabaseManager (MariaDB destino)

Cuando el destino es MariaDB, el engine debe configurarse con `pool_pre_ping=True` y `pool_recycle=3600` para evitar errores de conexión entre tablas. La forma recomendada es usar `SyncDatabaseManager.get_sqlalchemy_engine()`, que ya los incluye:

```python
from pathlib import Path
from util_bbdd.dump import DumpConfig, DumpOrchestrator
from util_bbdd.managers import SyncDatabaseManager

# Engine origen (PostgreSQL)
src_mgr = SyncDatabaseManager("postgresql", {
    "host": "prod-server", "user": "reader",
    "password": "***", "database": "production_db",
})
src_engine = src_mgr.get_sqlalchemy_engine()

# Engine destino (MariaDB) — pool_pre_ping + pool_recycle ya incluidos
dst_mgr = SyncDatabaseManager("mariadb", {
    "host": "replica-server", "user": "writer",
    "password": "***", "database": "replica_db",
})
dst_engine = dst_mgr.get_sqlalchemy_engine()

config = DumpConfig(
    source_engine=src_engine,
    target_engine=dst_engine,
    chunk_size=500,         # reducir si hay columnas TEXT/JSON extensas
    output_dir=Path("reports"),
    truncate_target=True,
)
result = DumpOrchestrator(config).run()
```

!!! info "Comparación case-insensitive entre motores"
    PostgreSQL devuelve nombres de tabla en minúsculas (`orders`); MariaDB puede devolverlos en mayúsculas (`ORDERS`). El módulo aplica comparación **case-insensitive** tanto para tablas como para columnas, de modo que ambas se reconocen como la misma tabla y el volcado funciona correctamente.

---

## Volcado selectivo de tablas

Para copiar solo un subconjunto de tablas, especifica la lista en `DumpConfig.tables`:

```python
config = DumpConfig(
    source_engine=src_engine,
    target_engine=dst_engine,
    tables=["customers", "orders", "order_items"],  # solo estas 3 tablas
    output_dir=Path("reports"),
)
result = DumpOrchestrator(config).run()
```

El orden topológico se calcula solo sobre las tablas especificadas.

---

## Modo append (sin truncar destino)

Si quieres añadir datos sin borrar los existentes (modo incremental):

```python
config = DumpConfig(
    source_engine=src_engine,
    target_engine=dst_engine,
    truncate_target=False,    # no vaciar destino
    output_dir=Path("reports"),
)
```

!!! warning "Duplicados"
    En modo append, si los datos ya existen en destino con las mismas PKs, la carga fallará con `IntegrityError`. Usa este modo solo cuando los datos de origen son estrictamente nuevos.

---

## Interpretar el informe Excel

El fichero `dump_report_<timestamp>.xlsx` contiene tres hojas (cuatro si `manage_indexes=True`):

### Hoja 1 — Auditoría Tablas

Muestra el estado de cada tabla con código de colores:

| Color | Significado |
|---|---|
| 🟢 Verde | `SUCCESS` — datos cargados correctamente |
| 🔴 Rojo | `ERROR` — fallo durante la carga (ver columna "Error") |
| 🟡 Amarillo | `SKIPPED` — sin columnas comunes entre origen y destino |
| 🟠 Naranja | `MISSING_TARGET` — tabla no existe en destino |

Al pie de esta hoja aparece una sección con constraints que no pudieron rehabilitarse.

### Hoja 2 — Tablas Faltantes

Lista de tablas presentes en origen que no tienen correspondencia en destino. Para cada una se indica la acción sugerida: crear la tabla con el DDL del origen.

### Hoja 3 — Columnas Inexistentes

Columnas presentes en origen pero ausentes en destino. Estas columnas se omitieron del volcado automáticamente.

### Hoja 4 — Índices *(solo con `manage_indexes=True`)*

Resultado de deshabilitar y reconstruir los índices secundarios por tabla: índice, dialecto, acción (`REBUILT`, `RECREATED`, `FAILED`, `UNSUPPORTED`) y mensaje de error si aplica.

---

## Auditoría de inserts con bulk.audit

Para registrar cada lote INSERT en el subsistema de auditoría de `util_bbdd.bulk.audit` y obtener métricas al finalizar, configura `bulk_audit_path` en `DumpConfig`:

```python
from pathlib import Path
from sqlalchemy import create_engine

from util_bbdd.dump import DumpConfig, DumpOrchestrator

src_engine = create_engine("postgresql+psycopg2://user:password@prod-server:5432/production_db")
dst_engine = create_engine("mssql+pymssql://user:password@analytics-server/analytics_db")

config = DumpConfig(
    source_engine=src_engine,
    target_engine=dst_engine,
    source_schema="public",
    target_schema="dbo",
    output_dir=Path("reports"),
    bulk_audit_path=Path("audit/dump_audit.csv"),   # activa auditoría de inserts
)

result = DumpOrchestrator(config).run()

# audit_summary está disponible cuando bulk_audit_path está configurado
# y el volcado ha generado al menos un INSERT registrado
if result.audit_summary is not None:
    s = result.audit_summary
    print(f"Lotes INSERT registrados : {s.total_operaciones}")
    print(f"Filas insertadas (audit) : {s.total_filas:,}")
    print(f"Tiempo total inserción   : {s.tiempo_total_seg:.1f}s")
    print(f"Tiempo medio por lote    : {s.tiempo_promedio_seg:.3f}s")
    print(f"Tablas auditadas         : {s.tablas_auditadas}")
    print(f"Tabla más activa         : {s.tabla_mas_activa}")
    print(f"CSV de auditoría         : {s.audit_path}")
else:
    print("Sin resumen de auditoría (bulk_audit_path no configurado o volcado sin inserts).")
```

### Cuándo `audit_summary` es `None`

| Situación | `audit_summary` |
|---|---|
| `bulk_audit_path=None` (default) | `None` — auditoría desactivada |
| `bulk_audit_path` configurado, volcado sin inserts (todas las tablas `skipped` o `missing_target`) | `None` — el CSV no contiene entradas del volcado |
| `bulk_audit_path` configurado y hay inserts | `DumpAuditSummary` con métricas del volcado |

### Analizar el CSV de auditoría tras el volcado

El CSV acumula operaciones de múltiples volcados y otras operaciones `bulk_crud`. Para explorar los datos directamente:

```python
from util_bbdd.bulk.audit import AuditManager

mgr = AuditManager(Path("audit/dump_audit.csv"))

# Estadísticas globales del CSV (todos los volcados acumulados)
stats = mgr.obtener_estadisticas()
print(stats)

# Filtrar solo inserts de una tabla concreta
df = mgr.filtrar_por_tabla("orders")
print(df)

# Operaciones que tardaron más de 2 segundos
lentas = mgr.obtener_operaciones_lentas(umbral_segundos=2.0)
print(lentas)

# Exportar resumen agrupado por tabla a Excel
ruta_excel = mgr.exportar_resumen_excel(agrupar_por="tabla")
print(f"Resumen de auditoría: {ruta_excel}")
```

---

## Volcado de alto volumen con palancas de rendimiento

Para esquemas grandes, `DumpConfig` expone cuatro palancas **opt-in** (todas desactivadas por defecto). Este ejemplo las combina: paraleliza tablas independientes, particiona las tablas grandes por rangos de PK, deshabilita índices secundarios durante la carga y acota el tamaño de transacción.

```python
from pathlib import Path
from sqlalchemy import create_engine

from util_bbdd.dump import DumpConfig, DumpOrchestrator

# El pool debe tolerar la concurrencia total:
#   pool_size + max_overflow >= max_parallel_tables * parallel_pk_ranges
# (en AMBOS engines: origen para las lecturas, destino para los inserts).
# Aquí 4 * 2 = 8 conexiones concurrentes → pool de 8 + 4 de overflow.
src_engine = create_engine(
    "postgresql+psycopg2://user:password@prod-server:5432/production_db",
    pool_size=8, max_overflow=4,
)
dst_engine = create_engine(
    "mssql+pymssql://user:password@analytics-server/analytics_db",
    pool_size=8, max_overflow=4,
)

config = DumpConfig(
    source_engine=src_engine,
    target_engine=dst_engine,
    source_schema="public",
    target_schema="dbo",
    chunk_size=10_000,
    output_dir=Path("reports"),
    truncate_target=True,
    bulk_audit_path=Path("audit/dump_audit.csv"),  # auditoría concurrente-segura
    # --- palancas de rendimiento ---
    max_parallel_tables=4,        # tablas independientes en paralelo (mismo nivel FK)
    parallel_pk_ranges=2,         # cada tabla con PK entera única → 2 rangos en paralelo
    manage_indexes=True,          # deshabilita/reconstruye índices secundarios no únicos
    commit_every_n_chunks=20,     # commit cada 20 lotes (acota la transacción)
)

result = DumpOrchestrator(config).run()

# Resultado de la gestión de índices (None si manage_indexes=False)
if result.index_results is not None:
    for ir in result.index_results:
        print(f"  [{ir.action.upper():11}] {ir.table_name}.{ir.index_name}")

# La auditoría funciona bajo paralelismo (escrituras al CSV serializadas por lock)
if result.audit_summary is not None:
    print(f"Lotes INSERT registrados: {result.audit_summary.total_operaciones}")
```

!!! warning "Atomicidad y triggers"
    Con `commit_every_n_chunks` la carga de cada tabla **deja de ser atómica**: un fallo a mitad deja committeados los lotes anteriores. Con `parallel_pk_ranges > 1` el destino **no** debe tener triggers per-fila dependientes del orden de inserción.

!!! info "Degradación automática"
    Si `pool_size + max_overflow` no alcanza `max_parallel_tables × parallel_pk_ranges`, el volcado **degrada** la concurrencia a la capacidad real del pool y emite un `WARNING` (no falla). Dimensiona los engines en consecuencia.

### Cuándo activar cada palanca

| Palanca | Actívala cuando… |
|---|---|
| `max_parallel_tables` | Hay muchas tablas medianas **independientes** (sin FK entre ellas) |
| `parallel_pk_ranges` | Dominan **pocas tablas muy grandes** con PK de una única columna entera |
| `manage_indexes` | Las tablas destino tienen **muchos índices secundarios** |
| `commit_every_n_chunks` | Una tabla es tan grande que una sola transacción **desborda el undo/redo log** |

---

## Troubleshooting

### La tabla tiene ciclos FK (`in_cycle=True`)

Las tablas con dependencias circulares no pueden ordenarse topológicamente. El módulo las detecta y las carga al final (con constraints ya deshabilitadas). Si la carga falla igualmente, puede indicar que los datos violan la restricción FK.

**Solución:** Revisar los datos circulares en origen. En muchos casos, una de las referencias puede ser nullable y el orden de inserción debe ser manual.

### Columnas omitidas inesperadamente

Si `skipped_columns` contiene columnas que esperabas cargar, verifica que el nombre exacto de la columna coincide en ambos esquemas (incluyendo capitalización).

El módulo usa comparación **case-insensitive**, pero si la columna simplemente no existe en destino, se omite. Crea la columna en destino con el DDL correspondiente.

### `InterfaceError: Server has gone away` (MariaDB, error 2006)

Se produce cuando una **conexión ociosa del pool** es usada por el servidor después de que el servidor la cerró (p.ej., mientras se procesaban datos del motor origen).

**Causas comunes:**
- Engine creado con `create_engine()` sin `pool_pre_ping=True`
- Servidor MariaDB con `wait_timeout` configurado bajo

**Solución:** Usa `SyncDatabaseManager.get_sqlalchemy_engine()`, que ya incluye `pool_pre_ping=True` y `pool_recycle=3600`:

```python
from util_bbdd.managers import SyncDatabaseManager
dst_engine = SyncDatabaseManager("mariadb", conn_params).get_sqlalchemy_engine()
```

O si creas el engine directamente:
```python
dst_engine = create_engine(url, pool_pre_ping=True, pool_recycle=3600)
```

El `DumpOrchestrator` emite un `WARNING` al inicializar si detecta que el engine MariaDB carece de estas configuraciones.

---

### `InterfaceError: Lost connection to server during query` (MariaDB, error 2013)

Se produce cuando el paquete INSERT supera el `max_allowed_packet` del servidor MariaDB. Es diferente al error 2006: ocurre **durante una query activa**, no en conexión ociosa.

**Causas comunes:**
- Tabla con columnas `TEXT`, `BLOB`, o `JSON` con contenido de varios KB por fila
- `chunk_size` demasiado alto (5 000 filas × 5 KB/fila = 25 MB > límite de 16 MB)

**Solución 1 — Reducir `chunk_size`:**

```python
config = DumpConfig(
    ...,
    chunk_size=500,   # reduce el tamaño del paquete INSERT
)
```

**Solución 2 — Aumentar `max_allowed_packet` en el servidor:**

```sql
SET GLOBAL max_allowed_packet = 67108864;  -- 64 MB
```

El `DumpOrchestrator` emite un `WARNING` al inicializar si `chunk_size > 1000` con destino MariaDB/MySQL.

---

### Constraint failed al rehabilitar

Si `ConstraintResult.status == "failed"`, significa que los datos cargados infringen la restricción. El informe Excel incluye el mensaje de error de la BD.

**Causas habituales:**
- Datos huérfanos (FK referencia a una fila que no existe en la tabla referenciada)
- Datos duplicados en columnas UNIQUE
- Valores NULL en columnas NOT NULL

**Solución:** Corregir los datos en origen o ajustar el orden de carga mediante `DumpConfig.tables`.

### Performance y `chunk_size`

`chunk_size` controla cuántas filas se leen del origen y se insertan en destino por cada lote. El valor adecuado depende del motor destino y del tipo de datos:

**Para destinos que no son MariaDB/MySQL** (SQL Server, PostgreSQL, Oracle):

```python
config = DumpConfig(
    source_engine=src_engine,
    target_engine=dst_engine,
    chunk_size=10_000,    # tablas < 100 MB
    # chunk_size=50_000,  # tablas > 1 GB (ajustar según RAM)
    output_dir=Path("reports"),
)
```

**Para destinos MariaDB/MySQL — riesgo `max_allowed_packet`:**

Tablas con columnas `TEXT`, `BLOB`, o `JSON` con contenido extenso pueden superar el límite `max_allowed_packet` del servidor (por defecto 16 MB en MariaDB antiguas), produciendo `Lost connection to server during query`. El `DumpOrchestrator` emite un `WARNING` al inicializar si `chunk_size > 1000` con destino MariaDB.

```python
config = DumpConfig(
    source_engine=src_engine,
    target_engine=dst_engine,
    chunk_size=500,   # seguro para columnas JSON/TEXT extensas
    output_dir=Path("reports"),
)
```

| Tipo de tabla destino MariaDB | `chunk_size` recomendado |
|---|---|
| Solo columnas numéricas/fecha | `2000`–`5000` |
| Con columnas `VARCHAR` medias | `1000`–`2000` |
| Con columnas `TEXT` o `JSON` extensas | `100`–`500` |

Alternativa server-side: `SET GLOBAL max_allowed_packet = 67108864;` (64 MB).

---

## Ver también

- [Documentación Funcional — Volcado de Datos](../functional/dump-data-export.md)
- [API Técnica — Volcado de Datos](../api/dump.md)
- [Comparación de Esquemas](schema_comparison.md) — analizar diferencias antes de volcar
