# Guía: Validación de Parámetros de Rendimiento (EngineReadinessAdvisor)

## Introducción

`EngineReadinessAdvisor` verifica automáticamente parámetros críticos de base de datos antes de ejecutar operaciones masivas (bulk INSERT/UPDATE/DELETE, volcado de datos). Detecta configuraciones subóptimas sin requerir permisos de administrador.

**Uso típico:**

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd.connection import EngineReadinessAdvisor

# Crear manager
manager = SyncDatabaseManager(
    db_type="postgresql",
    conn_params={"host": "localhost", "database": "mydb", "pool_size": 10}
)

# Verificar readiness (una sola vez por Engine en el proceso; BulkCrud lo hace al crearse)
advisor = EngineReadinessAdvisor()
advisor.report_once(manager.get_sqlalchemy_engine())

# O el informe completo, sin pasar por el LOG: hallazgos + condiciones de la verificación
report = manager.get_engine_readiness()
print(report.supported, report.dynamic, [(f.level, f.param) for f in report.findings])
```

Además del LOG, los hallazgos aparecen en los documentos y los Excel de auditoría (ver
[Informes: documentación y Excel de auditoría](#6-informes-documentacion-y-excel-de-auditoria)).

---

## Parámetros Validados por Motor

### MySQL / MariaDB

| Parámetro | Tipo | Rango | Recomendación |
|-----------|------|-------|----------------|
| `innodb_flush_log_at_trx_commit` | Dinámico | 0, 1, 2 | **2** (equilibrio durabilidad/rendimiento en bulk) |
| `innodb_log_file_size` | Estático* | ≥512 MB | **1–2 GB** (evita rotación frecuente redo log >10GB datasets) |
| `innodb_write_io_threads` | Estático en MySQL | ≥1 | **nCPU/2** en SSD (paralelismo escritura; en `my.cnf`, requiere reinicio) |
| `innodb_buffer_pool_size` | Dinámico | ≥1 GB | **25–50% RAM** (25% mínimo, 50% óptimo) |
| `max_allowed_packet` | Dinámico | ≥16 MB | **64 MB** (INSERT multi-fila de ~1000 filas) |

**\*MySQL 8.0.30+: `innodb_log_file_size` está obsoleta; el tamaño del redo log se ajusta en caliente con
`innodb_redo_log_capacity`. MySQL 5.7 y MariaDB anteriores a 10.9: en `my.cnf`, requiere reinicio.**

**Ejemplo de hallazgos:**

```
✅ OK — innodb_buffer_pool_size = 1 GB
⚠️ WARNING — innodb_flush_log_at_trx_commit = 1 (cambiar a 2 para bulk)
🔴 CRITICAL — innodb_flush_log_at_trx_commit = 0 (inseguro)
```

---

### PostgreSQL

| Parámetro | Tipo | Rango | Recomendación |
|-----------|------|-------|----------------|
| `shared_buffers` | Estático* | ≥256 MB | **1 GB** (25% RAM, requiere reinicio) |
| `effective_cache_size` | Dinámico | ≥512 MB | **4 GB** (50% RAM, hint al planner) |
| `work_mem` | Dinámico | ≥16 MB | **64 MB** (sort/hash en memoria) |
| `maintenance_work_mem` | Dinámico | ≥64 MB | **256 MB** (CREATE INDEX post-bulk) |
| `random_page_cost` | Dinámico | 0.1–4.0 | **1.1** en SSD; **4.0** en HDD |
| `synchronous_commit` | Dinámico | on/off/local | **on** en producción; **off** en staging |

**\*Estático: requiere reinicio en postgresql.conf**

**Ejemplo:**

```python
advisor = EngineReadinessAdvisor()
findings = advisor.check("postgresql", {"pool_size": 10}, connection=conn)

# Hallazgos posibles:
# ℹ️ INFO — effective_cache_size = 2 GB (aumentar a 4+ GB)
# ✅ OK — shared_buffers = 1 GB
```

---

### SQL Server

| Parámetro | Tipo | Rango | Recomendación |
|-----------|------|-------|----------------|
| `max_degree_of_parallelism` (MAXDOP) | Dinámico | 0–64 | **nCPU/2** (evita overhead en queries pequeñas) |
| `cost_threshold_for_parallelism` | Dinámico | ≥1 | **50–100** (umbral de costo para paralelismo) |
| `fill_factor` | Dinámico | 0–100 | **0 (100%)** para carga inicial masiva |
| `recovery_model` | Dinámico | FULL/BULK_LOGGED/SIMPLE | **BULK_LOGGED** durante carga masiva |

**Ejemplo:**

```python
advisor.report("mssql", {"pool_size": 10, "database": "mydb"}, connection=conn)
# ℹ️ INFO — max_degree_of_parallelism = 0 (ajustar a nCPU/2)
# ✅ OK — cost_threshold_for_parallelism = 75
```

---

### Oracle

| Parámetro | Tipo | Rango | Recomendación |
|-----------|------|-------|----------------|
| `pga_aggregate_target` | Dinámico | ≥256 MB | **1–4 GB** (memoria proceso, sort/hash) |
| `sga_target` | Dinámico | ≥512 MB | **4–16 GB** (buffer cache, log buffer) |
| `undo_retention` | Dinámico | ≥900 s | **≥3600 s** (evita "snapshot too old" en queries largas) |
| `cursor_sharing` | Dinámico | EXACT/FORCE | **EXACT** (FORCE invalida bind variables) |

---

### SQLite

| Parámetro | Tipo | Rango | Recomendación |
|-----------|------|-------|----------------|
| `journal_mode` | Dinámico | DELETE/WAL/... | **WAL** (mejora escritura concurrente) |
| `synchronous` | Dinámico | OFF/NORMAL/FULL/EXTRA | **NORMAL** en bulk (reduce fsync) |
| `cache_size` | Dinámico | ≥512 KB | **-65536** (64 MB en KiB negativos) |
| `temp_store` | Dinámico | FILE/MEMORY | **MEMORY** (acelera temporales) |

---

## Niveles de Hallazgos

| Nivel | Significado | Acción |
|-------|-------------|--------|
| **OK** | ✅ Parámetro óptimo | Ninguna (procede) |
| **INFO** | ℹ️ Mejora sugerida | Opcional; recomendado para grandes volúmenes |
| **WARNING** | ⚠️ Por debajo de recomendado | Considerar ajuste antes de bulk |
| **CRITICAL** | 🔴 Inseguro / bloqueante | Ajustar inmediatamente antes de producción |

---

## Uso Avanzado

### 1. Checks Estáticos (sin conexión)

```python
advisor = EngineReadinessAdvisor()

# Solo valida parámetros de pool/config (sin conectar)
findings = advisor.check(
    db_type="postgresql",
    conn_params={
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 30,
        "sslmode": "disable"  # ℹ️ INFO: sin cifrado en tránsito
    }
)

for f in findings:
    print(f"{f.level}: {f.param} = {f.current}")
    if f.recommendation:
        print(f"  → {f.recommendation}")
```

### 2. Checks Dinámicos (con conexión)

```python
# Valida parámetros de servidor vía SHOW/consultas
with manager.engine.connect() as conn:
    findings = advisor.check(
        db_type="postgresql",
        conn_params=manager.conn_params,
        connection=conn
    )
```

### 3. Reportes Consolidados

```python
# Emite un único log estructurado con todos los hallazgos
advisor.report(
    db_type="mysql",
    conn_params=manager.conn_params,
    connection=conn
)

# Salida de ejemplo:
# ╔═══════════════════════════════════╗
# ║  ENGINE READINESS REPORT  ·  mysql  ║
# ╚═══════════════════════════════════╝
#   [🔴 CRIT]  innodb_flush_log_at_trx_commit=0    → Cambiar a 2
#   [⚠️ WARN]  innodb_buffer_pool_size=256 MB     → Recomendado ≥1 GB
#   [✅ OK]    pool_size=10
# ─────────────────────────────────────
#   Resumen: 1 CRITICAL · 1 WARNING · 1 OK
```

### 4. Verificación Única por Engine

```python
from util_bbdd import BulkCrud

engine = manager.get_sqlalchemy_engine()
advisor = EngineReadinessAdvisor()

# Primera vez en el proceso → verifica, escribe el bloque en el LOG y guarda el informe
assert advisor.report_once(engine) is True

# Siguientes → no repite (tampoco BulkCrud, que llama a report_once al crearse)
for df in particiones:
    BulkCrud(engine).bulk_insert_from_df(df, "users")
assert advisor.report_once(engine) is False
```

`report_once()` es seguro con varios hilos y la clave es el objeto `Engine`, no su URL: dos engines al mismo servidor se
verifican por separado y `engine.dispose()` no provoca una nueva verificación.

### 5. Informe estructurado (`EngineReadinessReport`)

| Método | Devuelve | Cuándo usarlo |
|---|---|---|
| `check(db_type, conn_params, *, connection=None)` | `list[AdvisoryFinding]` | Hallazgos sueltos, ordenados por severidad |
| `report(db_type, conn_params, *, connection=None)` | `list[AdvisoryFinding]` | Igual que `check`, y además escribe el bloque en el LOG |
| `assess(db_type, conn_params, *, engine=None)` | `EngineReadinessReport` | Hallazgos más las condiciones de la verificación. Los checks estáticos usan `conn_params`; `engine` solo aporta la conexión para los dinámicos |
| `report_once(engine)` | `bool` | Verifica e informa una vez por engine; guarda el informe |
| `engine_report(engine, *, timeout=60.0)` | `EngineReadinessReport` | El informe guardado por `report_once()`, sin nueva conexión. Si el engine no se había verificado, lo verifica; si otro hilo lo está verificando, espera hasta `timeout` |
| `describe_engine(engine)` | `str` | `dialecto · host:puerto/base`, sin usuario ni contraseña |
| `SyncDatabaseManager.get_engine_readiness()` | `EngineReadinessReport` | `assess()` con los `conn_params` del manager y una conexión de `get_sqlalchemy_engine()` |

`EngineReadinessReport` (de `util_bbdd.connection`) distingue «sin hallazgos» de «no verificado»:

| Campo | Significado |
|---|---|
| `db_type` | Motor verificado |
| `findings` | Hallazgos, por severidad descendente |
| `checked_at` | Momento de la verificación, en UTC |
| `dynamic` | `True` si hubo conexión y se intentaron los checks de variables del servidor |
| `supported` | `False` si el motor no tiene checks (p.ej. HSQLDB); `findings` vacío |
| `error` | Por qué no hubo checks dinámicos. Solo lleva el tipo de la excepción, nunca su mensaje (puede contener la URL) |

```python
report = EngineReadinessAdvisor().assess("mysql", {"pool_size": 2})
report.dynamic, report.error   # (False, 'Sin engine: solo checks estáticos')
[(f.level, f.param) for f in report.findings]   # [('WARNING', 'pool_size')]
```

`engine_report()` y `report_once()` nunca lanzan excepciones: si la verificación falla, el informe lleva el motivo en
`error` y quien lo usa (carga, volcado, documentación) sigue adelante.

### 6. Informes: documentación y Excel de auditoría

Los mismos hallazgos, con la misma presentación (verificación, resumen por severidad y hallazgos ordenados), aparecen en:

| Salida | Dónde | Cuándo |
|---|---|---|
| `DatabaseDocumentation` (Word, Excel, HTML) | Sección «Condiciones del motor», al final | Con `imprimir={"condiciones_motor": {"imprimir_condiciones_motor": True}}` ([referencia](../api/database_documentation.md#seccion-condiciones-del-motor)) |
| `dump_report_*.xlsx` de `DumpOrchestrator` | Última hoja, «Condiciones del motor», con un bloque para el origen y otro para el destino | Siempre ([referencia](../api/dump_reporter.md)) |
| `auditoria.xlsx` de `AuditManager.exportar_resumen_excel()` | Última hoja, `Condiciones_motor` | Con `crud.audit_manager`, siempre; con un `AuditManager` creado aparte, si recibe `engine=` ([referencia](../api/bulk_audit.md)) |

```python
from pathlib import Path

from util_bbdd import BulkCrud
from util_bbdd.bulk import AuditManager

crud = BulkCrud(engine, audit_csv_path=Path("audit/audit.csv"))  # verifica el engine al crearse
crud.bulk_insert_from_df(df, "users")
crud.audit_manager.exportar_resumen_excel()  # ... + hoja Condiciones_motor, sin nueva conexión

# Tras ParallelBulkLoader, con un AuditManager propio:
AuditManager(Path("audit/audit.csv")).exportar_resumen_excel(engine=engine)
```

Los textos de esa presentación salen de un único sitio, `util_bbdd.audit.readiness.ReadinessRows`: cambiar uno cambia
todas las salidas.

---

## Permisos Requeridos

| Motor | Permisos Mínimos | Notas |
|-------|-----------------|-------|
| **MySQL** | INFORMATION_SCHEMA | Sin SUPER required |
| **PostgreSQL** | Conexión estándar | SHOW es público |
| **SQL Server** | VIEW SERVER STATE (opcional) | Fallback graceful si no disponible |
| **Oracle** | SELECT ANY DICTIONARY (opcional) | SELECT_CATALOG_ROLE alternativa |
| **SQLite** | Ninguno | Acceso directo al archivo |

---

## Troubleshooting

### Parámetro no validado

**Causa:** Motor/versión vieja sin el parámetro.  
**Solución:** No genera error; se omite el check (graceful fallback).

### "Snapshot too old" en Oracle

**Causa:** `undo_retention` muy bajo para queries largas.  
**Solución:**
```sql
ALTER SYSTEM SET undo_retention=3600;
ALTER SYSTEM SET undo_tablespace=UNDOTBS1;
```

### PostgreSQL `shared_buffers` baja

**Causa:** Default ~128 MB, insuficiente en bulk.  
**Solución:** Reinicio requerido.
```bash
# postgresql.conf
shared_buffers = 1GB  # 25% RAM típica

# Luego:
sudo systemctl restart postgresql
```

### SQL Server MAXDOP ilimitado

**Causa:** `max_degree_of_parallelism = 0`.  
**Solución:**
```sql
-- Todo el servidor (opción avanzada: requiere 'show advanced options' = 1)
EXEC sp_configure 'max degree of parallelism', 4;
RECONFIGURE;

-- Solo esta base de datos (SQL Server 2016+)
ALTER DATABASE SCOPED CONFIGURATION SET MAXDOP = 4;

-- Solo una consulta
SELECT ... OPTION (MAXDOP 4);
```

No existe `SET MAXDOP` como sentencia de sesión.

---

## Integración con BulkCrud / DumpOrchestrator

```python
from util_bbdd import BulkCrud, DumpOrchestrator, SyncDatabaseManager
from util_bbdd.dump import DumpConfig

manager = SyncDatabaseManager(db_type="mysql", conn_params={...})
engine = manager.get_sqlalchemy_engine()

# BulkCrud.__init__ llama a report_once(engine): primera instancia verifica, las demás no
bulk = BulkCrud(engine, audit_csv_path="audit.csv")
for partition in partitions:
    bulk.bulk_insert_from_df(partition, "users")

# DumpOrchestrator verifica origen y destino al empezar (una vez por engine en el proceso)
# y los muestra en la hoja «Condiciones del motor» del informe Excel
DumpOrchestrator(DumpConfig(source_engine=origen, target_engine=engine)).run()
```

---

## Referencias

- [EngineReadinessAdvisor API](../api/engine_readiness_advisor.md)
- [Connection Guide](./connection_guide.md)
- [Benchmarks](./benchmarks.md)
- [Performance Audit Constraints](./performance_audit_constraints_guide.md)
