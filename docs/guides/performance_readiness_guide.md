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

# Verificar readiness automáticamente (una sola vez por Engine)
advisor = EngineReadinessAdvisor()
advisor.report_once(manager.engine)
```

---

## Parámetros Validados por Motor

### MySQL / MariaDB

| Parámetro | Tipo | Rango | Recomendación |
|-----------|------|-------|----------------|
| `innodb_flush_log_at_trx_commit` | Dinámico | 0, 1, 2 | **2** (equilibrio durabilidad/rendimiento en bulk) |
| `innodb_log_file_size` | Dinámico* | ≥512 MB | **1–2 GB** (evita rotación frecuente redo log >10GB datasets) |
| `innodb_write_io_threads` | Dinámico | ≥1 | **nCPU/2** en SSD (paralelismo escritura) |
| `innodb_buffer_pool_size` | Dinámico | ≥1 GB | **25–50% RAM** (25% mínimo, 50% óptimo) |
| `max_allowed_packet` | Dinámico | ≥16 MB | **64 MB** (INSERT multi-fila de ~1000 filas) |

**\*MySQL 8.0.30+: dinámico; 5.7: estático (requiere reinicio)**

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
# report_once() verifica solo una sola vez por Engine en el proceso
# Útil en ciclos con muchas instancias BulkCrud/DumpOrchestrator
advisor = EngineReadinessAdvisor()

# Primera instancia → verifica + reporta
advisor.report_once(manager.engine)

# Siguientes instancias → omite (ya verificado)
for i in range(10):
    bulk = BulkCrud(manager, ...)
    bulk.insert(df)  # sin re-verificar
```

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
-- Sesión actual
SET STATISTICS IO ON;
exec sp_configure 'max degree of parallelism', 4;
RECONFIGURE WITH OVERRIDE;

-- Permanente
EXEC sp_configure 'max degree of parallelism', 4;
RECONFIGURE;
```

---

## Integración con BulkCrud / DumpOrchestrator

```python
from util_bbdd import BulkCrud, SyncDatabaseManager
from util_bbdd.connection import EngineReadinessAdvisor

manager = SyncDatabaseManager(
    db_type="mysql",
    conn_params={...}
)

# Verificación automática en BulkCrud.__init__
advisor = EngineReadinessAdvisor()
bulk = BulkCrud(
    manager,
    table_name="users",
    audit_csv_path="audit.csv"
)
# → report_once(manager.engine) se ejecuta internamente

# Luego, sin re-verificar
for partition in partitions:
    bulk.insert_from_df(partition)
```

---

## Referencias

- [EngineReadinessAdvisor API](../api/validators_system.md)
- [Connection Guide](./connection_guide.md)
- [Benchmarks](./benchmarks.md)
- [Performance Audit Constraints](./performance_audit_constraints_guide.md)
