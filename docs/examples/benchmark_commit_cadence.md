<!-- mkdocs:
title: Benchmark – Commit Cadence en Bulk Insert
parent: examples
nav_order: 13
-->

# Benchmark: Impacto de `commit_every_n_chunks` en Cargas Masivas

## El Problema: Degradación de Rendimiento en MariaDB/MySQL

Cuando insertas **millones de filas** sin cadencia de commits, observas un patrón característico:

- **Primer millón**: Rápido (buffer pool absorbe, sin flush a disco)
- **A partir de 1M**: Degradación exponencial (latencia × 10 o más)

### Causa Raíz

En MariaDB/MySQL con InnoDB:

1. **Sin commits intermedios**, toda la carga corre en una única transacción `BEGIN...COMMIT`
2. El **undo log** crece linealmente (una entrada por fila sin commitear)
3. El **buffer pool** (128–256 MB por default) se satura
4. InnoDB empieza a hacer **flush** de páginas sucias al disco
5. Cada nueva inserción navega por un undo log más grande → latencia creciente
6. El **change buffer** se desborda → merges de índices secundarios fuerzan I/O

**Solución**: Usar `commit_every_n_chunks` para emitir `COMMIT` cada N lotes, liberando el undo log.

---

## Benchmark Script

Para demostrar el patrón, ejecuta el script incluido:

```bash
cd docs/examples/

# Test rápido (100K filas, ~1s)
python benchmark_commit_cadence.py --size small

# Test medio (500K filas, ~5s)
python benchmark_commit_cadence.py --size medium

# Test completo (1M filas, ~10s)
python benchmark_commit_cadence.py --size large

# Test extremo (2M filas, ~20s)
python benchmark_commit_cadence.py --size xlarge
```

### Ejemplo de Salida

```
================================================================================
Benchmark: commit_cadence en bulk insert (1,000,000 filas)
================================================================================

📊 Generando 1,000,000 filas de prueba... ✓ (35.2 MB)

Test 1: SIN cadencia de commits (transacción única)
  - Filas por commit: ∞ (una sola transacción)
  - Chunks: 200
  ✓ Tiempo: 8.45s

Test 2: CON cadencia de commits (cada 100K filas)
  - Filas por commit: 100000
  - Chunks: 200
  - Commits periódicos: ~10
  ✓ Tiempo: 7.92s

================================================================================
Resultados:
  - Sin cadencia: 8.45s
  - Con cadencia: 7.92s
  - Diferencia: -0.53s (-6.3%)
  - Speedup: 1.07×
================================================================================

✓ Con SQLite in-memory, la diferencia es mínima.
  El problema real aparece en MariaDB/MySQL con disco,
  donde undo log y buffer pool se saturan sin cadencia.

Recomendación para MariaDB 1 GB buffer pool:
  bulk = BulkCrud(engine, chunk_size=5_000, commit_every_n_chunks=20)
  bulk.bulk_insert_from_df(df, 'tabla_destino')
```

**Nota**: El script usa **SQLite in-memory** para portabilidad. En MariaDB real con disco, la degradación SIN cadencia sería **5–10× mayor**.

---

## Guía de Tuning por Servidor

Recomendaciones de `commit_every_n_chunks` según `innodb_buffer_pool_size`:

| Servidor | Buffer Pool | `commit_every_n_chunks` | Filas/commit aprox. | Caso de Uso |
|---|---|---|---|---|
| MariaDB 8.0 | 256 MB | 10 | 50 K | Desarrollo, sandbox |
| MariaDB 8.0 | 1 GB | 20 | 100 K | Producción estándar |
| MariaDB 8.0 | 4 GB+ | 50 | 250 K | Carga de alto volumen |
| MySQL 8.0 | 256 MB | 10 | 50 K | Desarrollo |
| MySQL 8.0 | 1 GB | 20 | 100 K | Producción estándar |
| MySQL 5.7 | 1 GB | 15 | 75 K | Soporte legacy |

---

## Configuración Crítica de MySQL/MariaDB

Además de `commit_every_n_chunks` en la aplicación, hay dos variables de sistema **críticas** que deben ajustarse antes de cargas masivas:

### 1. `innodb_buffer_pool_size`

**Impacto**: Controla la memoria que InnoDB usa para cachear páginas de tabla e índices. Un buffer pool más grande reduce flush a disco y degración de rendimiento.

**Verificar valor actual**:
```sql
SHOW VARIABLES LIKE 'innodb_buffer_pool_size';
-- Salida ejemplo:
-- | Variable_name            | Value      |
-- | innodb_buffer_pool_size  | 134217728  |  (128 MB por default)
```

**Configurar (1 GB)**:
```sql
SET GLOBAL innodb_buffer_pool_size = 1073741824;
-- Nota: Requiere reinicio del servidor para persistencia o
--       editar my.cnf/my.ini:
--       [mysqld]
--       innodb_buffer_pool_size = 1073741824
```

**Recomendaciones**:
- **Desarrollo**: 256 MB (default)
- **Producción estándar**: 1 GB (25–50% de RAM disponible)
- **Carga de alto volumen**: 4–8 GB (50–75% de RAM disponible)

**Impacto en bulk insert**: Un buffer pool de 256 MB vs. 1 GB puede reducir latencia en 5–10M filas de **2–3× a 1.2–1.5×** con cadencia de commits activada.

---

### 2. `max_allowed_packet`

**Impacto**: Limita el tamaño máximo de una sentencia SQL. Sentencias INSERT multi-fila grandes pueden exceder este límite si no se ajusta.

**Verificar valor actual**:
```sql
SHOW VARIABLES LIKE 'max_allowed_packet';
-- Salida ejemplo:
-- | Variable_name        | Value    |
-- | max_allowed_packet   | 16777216 |  (16 MB por default)
```

**Configurar (64 MB para bulk insert)**:
```sql
SET GLOBAL max_allowed_packet = 67108864;
-- Nota: Similar a innodb_buffer_pool_size, requiere reinicio o
--       editar my.cnf/my.ini:
--       [mysqld]
--       max_allowed_packet = 67108864
```

**Recomendaciones**:
- **Default**: 16 MB
- **Bulk insert estándar**: 32–64 MB
- **Cargas de muy alto volumen**: 128 MB (máximo seguro)

**Impacto en bulk insert**: Sin suficiente `max_allowed_packet`, verás errores como:
```
sqlalchemy.exc.DatabaseError: (mysql....) Got a packet bigger than 'max_allowed_packet' bytes
```

---

### Checklist: Configuración Pre-Carga Masiva

Antes de ejecutar `bulk_insert_from_df()` con millones de filas:

```sql
-- 1️⃣ Verificar configuración actual
SHOW VARIABLES LIKE 'innodb_buffer_pool_size';
SHOW VARIABLES LIKE 'max_allowed_packet';

-- 2️⃣ Ajustar si es necesario (ejemplos para 1M+ filas)
SET GLOBAL innodb_buffer_pool_size = 1073741824;    -- 1 GB
SET GLOBAL max_allowed_packet = 67108864;           -- 64 MB

-- 3️⃣ Verificar que se aplicaron
SHOW VARIABLES LIKE 'innodb_buffer_pool_size';
SHOW VARIABLES LIKE 'max_allowed_packet';

-- 4️⃣ Deshabilitar índices secundarios (opcional, para cargas muy grandes)
ALTER TABLE tabla_destino DISABLE KEYS;
-- ... ejecutar bulk insert ...
ALTER TABLE tabla_destino ENABLE KEYS;
```

---

## Ejemplo: Migración Oracle → MariaDB

### Sin Tuning (degradación observable)

```python
from util_bbdd import SyncDatabaseManager
from util_bbdd.bulk.crud import BulkCrud

# Oracle como origen
manager_oracle = SyncDatabaseManager(
    db_type="oracle",
    conn_params={"host": "oracle.prod", "port": 1521, "service_name": "PROD"}
)

# MariaDB como destino
manager_mariadb = SyncDatabaseManager(
    db_type="mysql",
    conn_params={"host": "mariadb.prod", "port": 3306, "database": "dest"}
)

# ❌ SIN cadencia → degradación observada
bulk = BulkCrud(manager_mariadb.engine)
bulk.bulk_insert_from_df(df_10m_rows, "tabla_destino")
# Latencia: 1M rows → 2s, 2M rows → 8s, 5M rows → 25s, 10M rows → 60s+
```

**Patrón observable**:
```
Tiempo (segundos)
      ↑
   60 |                    ╱╱╱╱╱╱╱╱
      |                 ╱╱
   30 |              ╱╱
      |           ╱╱
   15 |        ╱╱
      |      ╱
    2 |    ╱
      |╱━━━━━━━━━━━━━━━━━━━━━━━━
      └─────────────────────────→ Filas (1M, 2M, 5M, 10M)
```

### Con Tuning (rendimiento lineal)

```python
# ✅ CON cadencia → rendimiento lineal
bulk = BulkCrud(
    manager_mariadb.engine,
    chunk_size=5_000,
    commit_every_n_chunks=20,  # Commit cada 100K filas
)
bulk.bulk_insert_from_df(df_10m_rows, "tabla_destino")
# Latencia: 1M rows → 2s, 2M rows → 4s, 5M rows → 10s, 10M rows → 20s
```

**Patrón esperado**:
```
Tiempo (segundos)
      ↑
   20 |━━━━━━━━━━━━━━━━━━━━━━━━━
      |                          ╱ (pendiente ~ lineal)
   10 |                    ╱
      |              ╱
    4 |        ╱
      |    ╱
    2 |╱
      └─────────────────────────→ Filas (1M, 2M, 5M, 10M)
```

---

## Advertencias y Limitaciones

### 1. **Pérdida de Atomicidad**

Al activar `commit_every_n_chunks`, la carga deja de ser **atómica**:

```python
# ❌ Riesgo: Fallo a mitad de carga
bulk = BulkCrud(engine, commit_every_n_chunks=20)
try:
    bulk.bulk_insert_from_df(df_10m, "tabla")
except Exception:
    # Los primeros 4M filas fueron committeadas
    # Los últimos 6M no se insertaron
    # La tabla está en estado inconsistente
    pass
```

**Recomendación**: Si necesitas atomicidad, gestiona la transacción en la capa de aplicación:

```python
from sqlalchemy import create_engine

engine = create_engine("mysql+pymysql://...")

# Envuelve todo en una transacción controlada
try:
    with engine.begin() as conn:
        bulk.bulk_session():  # Usa sesión para commits internos
            # Si falla aquí, todo se rollback
            bulk.bulk_insert_from_df(df, "tabla")
except Exception:
    # Rollback automático
    raise
```

### 2. **Valores Recomendados son Heurísticos**

Los valores de la tabla anterior son **orientativos**. Mide latencia real en tu entorno:

```bash
# Medir latencia con tu BD real
time python -c "
from util_bbdd.bulk.crud import BulkCrud
from sqlalchemy import create_engine
import pandas as pd

engine = create_engine('mysql+pymysql://user:pwd@host/db')
bulk = BulkCrud(engine, commit_every_n_chunks=20)
df = pd.read_csv('datos.csv')
bulk.bulk_insert_from_df(df, 'tabla_destino')
"
# Si latencia es > 60s para 10M filas, aumenta commit_every_n_chunks
# Si overhead de commits es alto (latencia no mejora), reduce commit_every_n_chunks
```

### 3. **PostgreSQL y SQLite: Menos Crítico**

- **PostgreSQL**: No padece el mismo problema de undo log (MVCC más eficiente)
- **SQLite**: En memoria; sin impacto de I/O disco
- **Oracle**: SÍ padece; usar `commit_every_n_chunks` para cargas masivas

---

## Referencias

- [InnoDB Storage Engine - Change Buffer](https://dev.mysql.com/doc/refman/8.0/en/innodb-change-buffer.html)
- [InnoDB Undo Logs](https://dev.mysql.com/doc/refman/8.0/en/innodb-undo-logs.html)
- [Buffer Pool Size Configuration](https://dev.mysql.com/doc/refman/8.0/en/innodb-buffer-pool-resize.html)
- [util_bbdd: BulkCrud API](../api/bulk.md#bulkcrud)

---

*Actualizado: 2026-06-01*
